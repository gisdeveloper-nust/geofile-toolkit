"""GeoJSON metadata parser."""

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import geopandas as gpd


class GeoJSONParseError(ValueError):
    """Raised when GeoJSON input cannot be parsed."""


def parse_geojson(filepath: str) -> dict[str, Any]:
    """Read GeoJSON data and return geometry and attribute metadata."""
    path = Path(filepath)
    try:
        with path.open(encoding="utf-8") as source:
            document = json.load(source)
    except JSONDecodeError as exc:
        raise GeoJSONParseError(
            f"Malformed JSON in '{path.name}': {exc.msg}"
        ) from exc
    except OSError as exc:
        raise GeoJSONParseError(f"Unable to read GeoJSON file: {exc}") from exc

    if not isinstance(document, dict):
        raise GeoJSONParseError("GeoJSON document must be a JSON object")
    missing_keys = [key for key in ("type", "features") if key not in document]
    if missing_keys:
        raise GeoJSONParseError(
            f"GeoJSON is missing required key(s): {', '.join(missing_keys)}"
        )
    if document["type"] != "FeatureCollection":
        raise GeoJSONParseError("GeoJSON type must be 'FeatureCollection'")
    if not isinstance(document["features"], list):
        raise GeoJSONParseError("GeoJSON 'features' must be an array")
    if not document["features"]:
        raise GeoJSONParseError("GeoJSON FeatureCollection contains no features")

    try:
        frame = gpd.read_file(path)
    except (OSError, ValueError) as exc:
        raise GeoJSONParseError(f"Unable to parse GeoJSON: {exc}") from exc

    geometry_types = sorted(frame.geometry.geom_type.dropna().unique().tolist())
    geometry_type = (
        geometry_types[0]
        if len(geometry_types) == 1
        else (
            f"Mixed ({', '.join(geometry_types)})"
            if geometry_types
            else "Unknown"
        )
    )
    attribute_fields = {
        column: str(dtype)
        for column, dtype in frame.drop(columns=frame.geometry.name).dtypes.items()
    }

    return {
        "geometry_type": geometry_type,
        "feature_count": len(frame),
        "crs": frame.crs.to_string() if frame.crs else None,
        "bounding_box": frame.total_bounds.tolist(),
        "attribute_fields": attribute_fields,
    }
