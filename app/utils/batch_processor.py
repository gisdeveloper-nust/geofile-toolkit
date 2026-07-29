"""Batch processing for ZIP archives of mixed spatial files."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import BadZipFile, ZipFile

from app.converters.base_converter import load_any
from app.converters.format_converter import convert
from app.parsers.csv_parser import parse_csv
from app.parsers.geojson_parser import parse_geojson
from app.parsers.gpx_parser import parse_gpx
from app.parsers.kml_parser import parse_kml
from app.parsers.shapefile_parser import parse_shapefile
from app.validators.geometry_validator import detect_geometry_issues

SUPPORTED_SOURCE_SUFFIXES = {".shp", ".geojson", ".json", ".kml", ".gpx", ".csv"}


def _extract_safely(archive: ZipFile, destination: Path) -> None:
    destination_root = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if destination_root not in member_path.parents and member_path != destination_root:
            raise ValueError("Archive contains an unsafe path")
    archive.extractall(destination)


def _parse_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".shp":
        return parse_shapefile(str(path))
    if suffix in {".geojson", ".json"}:
        return parse_geojson(str(path))
    if suffix == ".kml":
        return parse_kml(str(path))
    if suffix == ".gpx":
        return parse_gpx(str(path))
    if suffix == ".csv":
        return parse_csv(str(path))
    raise ValueError(f"Unsupported spatial file: {path.name}")


def _run_operation(path: Path, operation: str, workspace: Path) -> dict[str, Any]:
    normalized_operation, _, requested_target = operation.lower().partition(":")
    if normalized_operation == "parse":
        return _parse_file(path)
    if normalized_operation == "validate":
        frame = load_any(str(path))
        issues = detect_geometry_issues(frame)
        return {
            "feature_count": len(frame),
            "valid_count": len(frame) - len(issues),
            "invalid_count": len(issues),
            "issues": issues,
        }
    if normalized_operation == "convert":
        target_format = requested_target or "geojson"
        extension = {
            "shapefile": ".shp",
            "geojson": ".geojson",
            "kml": ".kml",
            "gpx": ".gpx",
            "csv": ".csv",
        }.get(target_format)
        if extension is None:
            raise ValueError(f"Unsupported batch conversion target: {target_format}")
        frame = load_any(str(path))
        output_path = workspace / "converted" / f"{path.stem}{extension}"
        convert(frame, target_format, str(output_path))
        return {
            "target_format": target_format,
            "feature_count": len(frame),
            "output_filename": output_path.name,
            "output_size": output_path.stat().st_size,
        }
    raise ValueError("Operation must be parse, validate, or convert[:target_format]")


def process_zip(zip_path: str, operation: str) -> list[dict[str, Any]]:
    """Extract and process every supported spatial file in a ZIP archive."""
    archive_path = Path(zip_path)
    with TemporaryDirectory(prefix="geofile-batch-") as temporary_directory:
        workspace = Path(temporary_directory)
        try:
            with ZipFile(archive_path) as archive:
                _extract_safely(archive, workspace)
        except BadZipFile as exc:
            raise ValueError("Invalid ZIP archive") from exc

        inputs = sorted(
            path
            for path in workspace.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES
        )
        results: list[dict[str, Any]] = []
        total_files = len(inputs)
        for position, path in enumerate(inputs, start=1):
            item: dict[str, Any] = {
                "filename": str(path.relative_to(workspace)),
                "position": position,
                "total_files": total_files,
            }
            try:
                item["result"] = _run_operation(path, operation, workspace)
                item["status"] = "success"
            except Exception as exc:
                item["status"] = "failure"
                item["error"] = str(exc)
            results.append(item)
        return results
