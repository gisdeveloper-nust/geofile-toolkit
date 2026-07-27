"""GeoFile Toolkit application entry point."""

import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import geopandas as gpd
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from pyproj import CRS
from pyproj.exceptions import CRSError

from app.converters.base_converter import load_any
from app.converters.format_converter import convert
from app.models.schemas import (
    ConversionResult,
    ParseResult,
    RepairReport,
    ValidationReport,
)
from app.parsers.geojson_parser import GeoJSONParseError, parse_geojson
from app.parsers.kml_parser import KMLParseError, parse_kml
from app.parsers.shapefile_parser import ShapefileParseError, parse_shapefile
from app.repairs.geometry_repair import repair_batch
from app.validators.geometry_validator import detect_geometry_issues

app = FastAPI(title="GeoFile Toolkit")


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


@app.post("/parse/shapefile", response_model=ParseResult)
async def parse_shapefile_upload(
    file: UploadFile = File(...),
) -> ParseResult:
    """Extract an uploaded shapefile archive and return its metadata."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a ZIP archive")

    with TemporaryDirectory(prefix="geofile-toolkit-") as temporary_directory:
        workspace = Path(temporary_directory)
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


@app.post("/parse/geojson", response_model=ParseResult)
async def parse_geojson_upload(file: UploadFile = File(...)) -> ParseResult:
    """Parse an uploaded GeoJSON document and return its metadata."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() not in {".geojson", ".json"}:
        raise HTTPException(
            status_code=400, detail="Upload must be a .geojson or .json file"
        )

    with TemporaryDirectory(prefix="geofile-toolkit-") as temporary_directory:
        upload_path = Path(temporary_directory) / Path(filename).name
        upload_path.write_bytes(await file.read())
        try:
            result = parse_geojson(str(upload_path))
        except GeoJSONParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ParseResult(**result)


@app.post("/parse/kml", response_model=ParseResult)
async def parse_kml_upload(file: UploadFile = File(...)) -> ParseResult:
    """Parse an uploaded KML document and return its metadata."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".kml":
        raise HTTPException(status_code=400, detail="Upload must be a .kml file")

    with TemporaryDirectory(prefix="geofile-toolkit-") as temporary_directory:
        upload_path = Path(temporary_directory) / Path(filename).name
        upload_path.write_bytes(await file.read())
        try:
            result = parse_kml(str(upload_path))
        except KMLParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ParseResult(**result)


@app.post("/validate/geojson", response_model=ValidationReport)
async def validate_geojson_upload(
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


@app.post("/repair/geojson")
async def repair_geojson_upload(file: UploadFile = File(...)) -> Response:
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


@app.post("/convert")
async def convert_upload(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    target_crs: str | None = Form(None),
) -> Response:
    """Convert an uploaded geospatial file and return it as a download."""
    filename = Path(file.filename or "upload").name
    with TemporaryDirectory(prefix="geofile-toolkit-") as temporary_directory:
        workspace = Path(temporary_directory)
        upload_path = workspace / filename
        upload_path.write_bytes(await file.read())

        source_path = upload_path
        source_formats = {
            ".shp": "shapefile",
            ".geojson": "geojson",
            ".json": "geojson",
            ".kml": "kml",
        }
        source_format = source_formats.get(upload_path.suffix.lower())
        if upload_path.suffix.lower() == ".zip":
            try:
                with ZipFile(upload_path) as archive:
                    _extract_zip_safely(archive, workspace)
            except BadZipFile as exc:
                raise HTTPException(status_code=400, detail="Invalid ZIP archive") from exc
            shapefiles = list(workspace.rglob("*.shp"))
            if len(shapefiles) != 1:
                raise HTTPException(
                    status_code=400,
                    detail="A Shapefile ZIP must contain exactly one .shp file",
                )
            source_path = shapefiles[0]
            source_format = "shapefile"

        if source_format is None:
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
        if source_format == normalized_target:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format combination: {source_format} to {normalized_target}",
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

        extensions = {
            "shapefile": ".shp",
            "geojson": ".geojson",
            "kml": ".kml",
        }
        output_path = workspace / f"{source_path.stem}_converted{extensions[normalized_target]}"
        try:
            frame = load_any(str(source_path))
            convert(
                frame,
                normalized_target,
                str(output_path),
                effective_target_crs,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Conversion failed: {exc}") from exc

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

        result = ConversionResult(
            original_filename=filename,
            source_format=source_format,
            target_format=normalized_target,
            target_crs=effective_target_crs,
            output_filename=download_path.name,
        )
        encoded_result = base64.urlsafe_b64encode(
            result.model_dump_json().encode("utf-8")
        ).decode("ascii")
        content = download_path.read_bytes()

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{download_path.name}"',
            "X-Conversion-Result": encoded_result,
            "X-Conversion-Result-Encoding": "base64url",
        },
    )
