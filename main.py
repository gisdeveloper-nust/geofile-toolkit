"""GeoFile Toolkit application entry point."""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.models.schemas import ParseResult
from app.parsers.geojson_parser import GeoJSONParseError, parse_geojson
from app.parsers.shapefile_parser import ShapefileParseError, parse_shapefile

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
