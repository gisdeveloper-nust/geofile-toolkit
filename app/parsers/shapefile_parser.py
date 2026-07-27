"""Shapefile metadata parser."""

from pathlib import Path
from typing import Any

import fiona
import geopandas as gpd


class ShapefileParseError(ValueError):
    """Raised when a shapefile cannot be parsed safely."""


def _require_component(shapefile: Path, suffix: str) -> None:
    component = shapefile.with_suffix(suffix)
    if not component.is_file():
        raise ShapefileParseError(
            f"Missing required shapefile component: {component.name}"
        )


def parse_shapefile(filepath: str) -> dict[str, Any]:
    """Parse a shapefile and return its geometry and attribute metadata."""
    shapefile = Path(filepath)
    if not shapefile.is_file():
        raise ShapefileParseError(f"Shapefile not found: {shapefile}")
    if shapefile.suffix.lower() != ".shp":
        raise ShapefileParseError("Expected a file with the .shp extension")

    _require_component(shapefile, ".shx")
    _require_component(shapefile, ".dbf")

    try:
        with fiona.open(shapefile) as source:
            feature_count = len(source)
            schema = source.schema or {}
            geometry_type = schema.get("geometry") or "Unknown"
            fields = dict(schema.get("properties") or {})
            crs = source.crs_wkt or (source.crs.to_string() if source.crs else None)
            bounds = list(source.bounds) if feature_count else None
    except (fiona.errors.FionaError, OSError, ValueError) as exc:
        raise ShapefileParseError(
            f"Unable to read shapefile '{shapefile.name}': {exc}"
        ) from exc

    if feature_count == 0:
        raise ShapefileParseError(f"Shapefile '{shapefile.name}' contains no features")

    # Read with the Fiona engine to validate geometries and ensure the parser uses
    # the same geospatial stack as the API.
    try:
        frame = gpd.read_file(shapefile, engine="fiona")
    except (fiona.errors.FionaError, OSError, ValueError) as exc:
        raise ShapefileParseError(
            f"Unable to parse shapefile '{shapefile.name}': {exc}"
        ) from exc

    geometry_types = sorted(frame.geometry.geom_type.dropna().unique().tolist())
    if geometry_types:
        geometry_type = (
            geometry_types[0]
            if len(geometry_types) == 1
            else f"Mixed ({', '.join(geometry_types)})"
        )

    return {
        "geometry_type": geometry_type,
        "feature_count": feature_count,
        "crs": crs,
        "bounding_box": bounds,
        "attribute_fields": fields,
    }
