"""GeoFile Toolkit application entry point."""

import base64
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from zipfile import BadZipFile, ZipFile

import geopandas as gpd
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pyproj import CRS
from pyproj.exceptions import CRSError

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.middleware.rate_limiter import RATE_LIMIT_STRING, limiter
from app.auth.api_key import generate_key
from app.auth.dependencies import verify_api_key
from app.jobs.job_queue import get_job, submit_job
from app.converters.base_converter import load_any
from app.converters.format_converter import convert
from app.analysis.topology_checker import summarize_topology_issues
from app.analysis.spatial_ops import (
    clip_layer,
    compute_geometry_stats,
    merge_layers,
    spatial_join,
)
from app.models.schemas import (
    ConversionResult,
    GeometryStatsResult,
    ParseResult,
    RepairReport,
    TopologyReport,
    ValidationReport,
)
from app.parsers.csv_parser import CSVParseError, parse_csv
from app.parsers.geojson_parser import GeoJSONParseError, parse_geojson
from app.parsers.gpx_parser import GPXParseError, parse_gpx
from app.parsers.kml_parser import KMLParseError, parse_kml
from app.parsers.shapefile_parser import ShapefileParseError, parse_shapefile
from app.repairs.geometry_repair import repair_batch
from app.utils.batch_processor import process_zip
from app.utils.file_cleanup import cleanup_temp_files
from app.validators.geometry_validator import detect_geometry_issues

app = FastAPI(title="GeoFile Toolkit")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_AUTH_DEP = [Depends(verify_api_key)]


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


class KeyGenerateRequest(BaseModel):
    """Optional label to attach to the generated API key."""

    label: str = ""


class KeyGenerateResponse(BaseModel):
    """Newly generated API key and metadata."""

    key: str
    label: str
    created_at: str


# ---------------------------------------------------------------------------
# Auth endpoint (public — no key required to create the first key)
# ---------------------------------------------------------------------------


@app.post("/auth/keys", response_model=KeyGenerateResponse, status_code=201)
def create_api_key(body: KeyGenerateRequest = KeyGenerateRequest()) -> KeyGenerateResponse:
    """Generate a new API key and return it.  Store it securely — it will not be shown again."""
    record = generate_key(label=body.label)
    return KeyGenerateResponse(**record)


# ---------------------------------------------------------------------------
# Job status endpoint (authenticated)
# ---------------------------------------------------------------------------


@app.get("/jobs/{job_id}", dependencies=_AUTH_DEP)
def get_job_status(job_id: str) -> dict:
    """Return the current status and result of an async job.

    Status values: ``pending`` | ``processing`` | ``complete`` | ``failed``

    When ``status`` is ``complete`` the ``result`` field contains the
    job's output.  When ``status`` is ``failed`` the ``error`` field
    describes what went wrong.
    """
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return record.to_dict()


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report whether the API process is healthy."""
    return {"status": "healthy"}


def _extract_zip_safely(archive: ZipFile, destination: Path) -> None:
    destination_root = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if destination_root not in member_path.parents and member_path != destination_root:
            raise HTTPException(status_code=400, detail="Archive contains an unsafe path")
    archive.extractall(destination)


def _background_workspace(background_tasks: BackgroundTasks) -> Path:
    workspace = Path(mkdtemp(prefix="geofile-toolkit-"))
    background_tasks.add_task(cleanup_temp_files, workspace)
    return workspace


async def _load_uploaded_spatial_file(
    file: UploadFile,
    workspace: Path,
    prefix: str,
) -> gpd.GeoDataFrame:
    upload_directory = workspace / prefix
    upload_directory.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename or "upload").name
    upload_path = upload_directory / filename
    upload_path.write_bytes(await file.read())

    source_path = upload_path
    if upload_path.suffix.lower() == ".zip":
        try:
            with ZipFile(upload_path) as archive:
                _extract_zip_safely(archive, upload_directory)
        except BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid ZIP archive") from exc
        shapefiles = list(upload_directory.rglob("*.shp"))
        if len(shapefiles) != 1:
            raise HTTPException(
                status_code=400,
                detail="A Shapefile ZIP must contain exactly one .shp file",
            )
        source_path = shapefiles[0]

    try:
        return load_any(str(source_path))
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Unable to load spatial file: {exc}"
        ) from exc


@app.post("/parse/shapefile", response_model=ParseResult, dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def parse_shapefile_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> ParseResult:
    """Extract an uploaded shapefile archive and return its metadata."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a ZIP archive")

    workspace = _background_workspace(background_tasks)
    archive_path = workspace / "upload.zip"
    archive_path.write_bytes(await file.read())

    try:
        with ZipFile(archive_path) as archive:
            _extract_zip_safely(archive, workspace)
    except BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid ZIP archive") from exc

    shapefiles = [
        path
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix.lower() == ".shp"
    ]
    if not shapefiles:
        raise HTTPException(
            status_code=400, detail="Archive does not contain a .shp file"
        )
    if len(shapefiles) > 1:
        raise HTTPException(
            status_code=400, detail="Archive must contain exactly one shapefile"
        )

    try:
        result = parse_shapefile(str(shapefiles[0]))
    except ShapefileParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ParseResult(**result)


@app.post("/parse/geojson", response_model=ParseResult, dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def parse_geojson_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> ParseResult:
    """Parse an uploaded GeoJSON document and return its metadata."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() not in {".geojson", ".json"}:
        raise HTTPException(
            status_code=400, detail="Upload must be a .geojson or .json file"
        )

    workspace = _background_workspace(background_tasks)
    upload_path = workspace / Path(filename).name
    upload_path.write_bytes(await file.read())
    try:
        result = parse_geojson(str(upload_path))
    except GeoJSONParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ParseResult(**result)


@app.post("/parse/kml", response_model=ParseResult, dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def parse_kml_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> ParseResult:
    """Parse an uploaded KML document and return its metadata."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".kml":
        raise HTTPException(status_code=400, detail="Upload must be a .kml file")

    workspace = _background_workspace(background_tasks)
    upload_path = workspace / Path(filename).name
    upload_path.write_bytes(await file.read())
    try:
        result = parse_kml(str(upload_path))
    except KMLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ParseResult(**result)


@app.post("/parse/gpx", dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def parse_gpx_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict:
    """Parse an uploaded GPX document and return layer metadata."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".gpx":
        raise HTTPException(status_code=400, detail="Upload must be a .gpx file")

    workspace = _background_workspace(background_tasks)
    upload_path = workspace / Path(filename).name
    upload_path.write_bytes(await file.read())
    try:
        return parse_gpx(str(upload_path))
    except GPXParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/parse/csv", dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def parse_csv_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lat_col: str | None = Query(None),
    lon_col: str | None = Query(None),
) -> dict:
    """Parse uploaded CSV latitude/longitude rows as point features."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Upload must be a .csv file")

    workspace = _background_workspace(background_tasks)
    upload_path = workspace / Path(filename).name
    upload_path.write_bytes(await file.read())
    try:
        return parse_csv(str(upload_path), lat_col=lat_col, lon_col=lon_col)
    except CSVParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/analyze/topology", response_model=TopologyReport, dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def analyze_topology_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> TopologyReport:
    """Analyze polygon overlaps, gaps, and slivers in an uploaded layer."""
    workspace = _background_workspace(background_tasks)
    frame = await _load_uploaded_spatial_file(file, workspace, "topology")
    try:
        return summarize_topology_issues(frame)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/analyze/clip", dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def analyze_clip_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    input_file: UploadFile = File(...),
    clip_file: UploadFile = File(...),
) -> FileResponse:
    """Clip an uploaded layer and return downloadable GeoJSON."""
    workspace = _background_workspace(background_tasks)
    input_frame = await _load_uploaded_spatial_file(
        input_file, workspace, "clip-input"
    )
    clip_frame = await _load_uploaded_spatial_file(
        clip_file, workspace, "clip-boundary"
    )
    try:
        clipped = clip_layer(input_frame, clip_frame)
        output_path = workspace / "clipped.geojson"
        convert(clipped, "geojson", str(output_path))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Clip failed: {exc}") from exc

    return FileResponse(
        path=output_path,
        media_type="application/geo+json",
        filename="clipped.geojson",
        background=background_tasks,
    )


@app.post("/analyze/merge", dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def analyze_merge_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> FileResponse:
    """Merge uploaded layers and return downloadable GeoJSON."""
    if len(files) < 2:
        raise HTTPException(
            status_code=400, detail="Upload at least two layers to merge"
        )

    workspace = _background_workspace(background_tasks)
    frames = [
        await _load_uploaded_spatial_file(file, workspace, f"merge-{index}")
        for index, file in enumerate(files)
    ]
    try:
        merged = merge_layers(frames)
        output_path = workspace / "merged.geojson"
        convert(merged, "geojson", str(output_path))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Merge failed: {exc}") from exc

    return FileResponse(
        path=output_path,
        media_type="application/geo+json",
        filename="merged.geojson",
        background=background_tasks,
    )


@app.post("/analyze/spatial-join", dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def analyze_spatial_join_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    predicate: str = Form(...),
) -> FileResponse:
    """Spatially join two uploaded layers and return downloadable GeoJSON."""
    workspace = _background_workspace(background_tasks)
    left_frame = await _load_uploaded_spatial_file(
        left_file, workspace, "join-left"
    )
    right_frame = await _load_uploaded_spatial_file(
        right_file, workspace, "join-right"
    )
    try:
        joined = spatial_join(left_frame, right_frame, predicate)
        output_path = workspace / "spatial_join.geojson"
        convert(joined, "geojson", str(output_path))
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Spatial join failed: {exc}"
        ) from exc

    return FileResponse(
        path=output_path,
        media_type="application/geo+json",
        filename="spatial_join.geojson",
        background=background_tasks,
    )


@app.post("/analyze/stats", response_model=GeometryStatsResult, dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def analyze_stats_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> GeometryStatsResult:
    """Return geometry measurements for an uploaded spatial layer."""
    workspace = _background_workspace(background_tasks)
    frame = await _load_uploaded_spatial_file(file, workspace, "stats")
    return GeometryStatsResult(**compute_geometry_stats(frame))


@app.post("/validate/geojson", response_model=ValidationReport, dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def validate_geojson_upload(
    request: Request,
    file: UploadFile = File(...),
) -> ValidationReport:
    """Validate every geometry in an uploaded GeoJSON document."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() not in {".geojson", ".json"}:
        raise HTTPException(
            status_code=400, detail="Upload must be a .geojson or .json file"
        )

    with TemporaryDirectory(prefix="geofile-toolkit-") as temporary_directory:
        upload_path = Path(temporary_directory) / Path(filename).name
        upload_path.write_bytes(await file.read())
        try:
            metadata = parse_geojson(str(upload_path))
        except GeoJSONParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        frame = gpd.read_file(upload_path)
        issues = detect_geometry_issues(frame)

    invalid_count = len(issues)
    feature_count = metadata["feature_count"]
    return ValidationReport(
        feature_count=feature_count,
        valid_count=feature_count - invalid_count,
        invalid_count=invalid_count,
        issues=issues,
    )


@app.post("/repair/geojson", dependencies=_AUTH_DEP)
@limiter.limit(RATE_LIMIT_STRING)
async def repair_geojson_upload(request: Request, file: UploadFile = File(...)) -> Response:
    """Repair GeoJSON geometries and return a downloadable repaired document."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() not in {".geojson", ".json"}:
        raise HTTPException(
            status_code=400, detail="Upload must be a .geojson or .json file"
        )

    with TemporaryDirectory(prefix="geofile-toolkit-") as temporary_directory:
        upload_path = Path(temporary_directory) / Path(filename).name
        upload_path.write_bytes(await file.read())
        try:
            metadata = parse_geojson(str(upload_path))
        except GeoJSONParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        frame = gpd.read_file(upload_path)
        repaired_frame, repairs = repair_batch(frame)
        repaired_geojson = repaired_frame.to_json()

    report = RepairReport(
        feature_count=metadata["feature_count"],
        repaired_count=sum(item["status"] == "fixed" for item in repairs),
        unfixable_count=sum(item["status"] == "unfixable" for item in repairs),
        repairs=repairs,
    )
    encoded_report = base64.urlsafe_b64encode(
        report.model_dump_json().encode("utf-8")
    ).decode("ascii")
    download_name = f"{Path(filename).stem}_repaired.geojson"

    return Response(
        content=repaired_geojson,
        media_type="application/geo+json",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
            "X-Repair-Report": encoded_report,
            "X-Repair-Report-Encoding": "base64url",
        },
    )


@app.post("/convert", dependencies=_AUTH_DEP, response_model=None)
@limiter.limit(RATE_LIMIT_STRING)
async def convert_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_format: str = Form(...),
    target_crs: str | None = Form(None),
    async_mode: bool = Query(False, alias="async"),
) -> FileResponse | dict:
    """Convert an uploaded geospatial file and return it as a download.

    Pass ``?async=true`` to receive a ``{"job_id": "..."}`` immediately and
    poll ``GET /jobs/{job_id}`` for completion.
    """
    filename = Path(file.filename or "upload").name

    # Validate format params eagerly before any expensive I/O so that
    # format errors are returned synchronously even in async mode.
    source_formats = {
        ".shp": "shapefile",
        ".geojson": "geojson",
        ".json": "geojson",
        ".kml": "kml",
    }
    file_suffix = Path(filename).suffix.lower()
    source_format_hint = source_formats.get(file_suffix)
    if file_suffix not in {".zip"} and source_format_hint is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported source format; upload Shapefile ZIP, GeoJSON, or KML",
        )

    target_aliases = {
        "shapefile": "shapefile",
        "shp": "shapefile",
        "geojson": "geojson",
        "json": "geojson",
        "kml": "kml",
    }
    normalized_target = target_aliases.get(target_format.strip().lower())
    if normalized_target is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported target format; use shapefile, geojson, or kml",
        )

    effective_target_crs = target_crs
    if target_crs:
        try:
            parsed_target_crs = CRS.from_user_input(target_crs)
        except CRSError as exc:
            raise HTTPException(
                status_code=400, detail=f"Unsupported CRS code: {target_crs}"
            ) from exc
        if normalized_target == "kml" and parsed_target_crs != CRS.from_epsg(4326):
            raise HTTPException(
                status_code=400,
                detail="KML output supports only EPSG:4326",
            )
    elif normalized_target == "kml":
        effective_target_crs = "EPSG:4326"

    # Read file bytes once; the rest can run in the background.
    file_bytes = await file.read()
    workspace = Path(mkdtemp(prefix="geofile-toolkit-"))

    if async_mode:
        job_id = submit_job(
            _sync_convert,
            workspace,
            filename,
            file_bytes,
            normalized_target,
            effective_target_crs,
        )
        return {"job_id": job_id}

    # Synchronous path — keep existing behaviour.
    background_tasks.add_task(cleanup_temp_files, workspace)
    try:
        result_dict = _sync_convert(
            workspace, filename, file_bytes, normalized_target, effective_target_crs
        )
    except HTTPException:
        cleanup_temp_files(workspace)
        raise
    except Exception as exc:
        cleanup_temp_files(workspace)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    download_path = Path(result_dict["download_path"])
    return FileResponse(
        path=download_path,
        media_type=result_dict["media_type"],
        filename=download_path.name,
        headers={
            "X-Conversion-Result": result_dict["encoded_result"],
            "X-Conversion-Result-Encoding": "base64url",
        },
        background=background_tasks,
    )


def _sync_convert(
    workspace: Path,
    filename: str,
    file_bytes: bytes,
    normalized_target: str,
    effective_target_crs: str | None,
) -> dict:
    """Blocking conversion logic, safe to run in a thread-pool worker."""
    upload_path = workspace / filename
    upload_path.write_bytes(file_bytes)

    source_path = upload_path
    source_formats = {
        ".shp": "shapefile",
        ".geojson": "geojson",
        ".json": "geojson",
        ".kml": "kml",
    }
    source_format = source_formats.get(upload_path.suffix.lower())
    if upload_path.suffix.lower() == ".zip":
        with ZipFile(upload_path) as archive:
            _extract_zip_safely_sync(archive, workspace)
        shapefiles = list(workspace.rglob("*.shp"))
        if len(shapefiles) != 1:
            raise ValueError(
                "A Shapefile ZIP must contain exactly one .shp file"
            )
        source_path = shapefiles[0]
        source_format = "shapefile"

    if source_format is None:
        raise ValueError("Unsupported source format")
    if source_format == normalized_target:
        raise ValueError(
            f"Unsupported format combination: {source_format} to {normalized_target}"
        )

    extensions = {"shapefile": ".shp", "geojson": ".geojson", "kml": ".kml"}
    output_path = workspace / f"{source_path.stem}_converted{extensions[normalized_target]}"

    frame = load_any(str(source_path))
    convert(frame, normalized_target, str(output_path), effective_target_crs)

    download_path = output_path
    media_type = {
        ".geojson": "application/geo+json",
        ".kml": "application/vnd.google-earth.kml+xml",
    }.get(output_path.suffix, "application/octet-stream")
    if normalized_target == "shapefile":
        download_path = workspace / f"{source_path.stem}_converted.zip"
        with ZipFile(download_path, mode="w") as archive:
            for component in output_path.parent.glob(f"{output_path.stem}.*"):
                archive.write(component, arcname=component.name)
        media_type = "application/zip"

    result_meta = ConversionResult(
        original_filename=filename,
        source_format=source_format,
        target_format=normalized_target,
        target_crs=effective_target_crs,
        output_filename=download_path.name,
    )
    encoded_result = base64.urlsafe_b64encode(
        result_meta.model_dump_json().encode("utf-8")
    ).decode("ascii")

    return {
        "download_path": str(download_path),
        "media_type": media_type,
        "encoded_result": encoded_result,
    }


def _extract_zip_safely_sync(archive: ZipFile, destination: Path) -> None:
    """Zip-slip-safe extraction (sync version for thread workers)."""
    destination_root = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if destination_root not in member_path.parents and member_path != destination_root:
            raise ValueError("Archive contains an unsafe path")
    archive.extractall(destination)


@app.post("/batch/process", dependencies=_AUTH_DEP, response_model=None)
@limiter.limit(RATE_LIMIT_STRING)
async def batch_process_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    operation: str = Form(...),
    async_mode: bool = Query(False, alias="async"),
) -> list[dict] | dict:
    """Process mixed spatial files from an uploaded ZIP archive.

    Pass ``?async=true`` to receive ``{"job_id": "..."}`` immediately and
    poll ``GET /jobs/{job_id}`` for completion.
    """
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=400, detail="Upload must be a ZIP archive")

    file_bytes = await file.read()
    workspace = Path(mkdtemp(prefix="geofile-toolkit-"))
    upload_path = workspace / Path(filename).name
    upload_path.write_bytes(file_bytes)

    def _sync_batch() -> list[dict]:
        try:
            return process_zip(str(upload_path), operation)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        finally:
            # Cleanup only when the job itself owns the workspace.
            if async_mode:
                cleanup_temp_files(workspace)

    if async_mode:
        job_id = submit_job(_sync_batch)
        return {"job_id": job_id}

    background_tasks.add_task(cleanup_temp_files, workspace)
    try:
        return _sync_batch()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
