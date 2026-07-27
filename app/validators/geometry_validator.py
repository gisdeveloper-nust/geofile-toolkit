"""Validity checks for Shapely geometries."""

from typing import Any, Iterable

import geopandas as gpd
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity


def _coordinate_sequences(geom: BaseGeometry) -> Iterable[list[tuple[Any, ...]]]:
    if hasattr(geom, "exterior") and geom.exterior is not None:
        yield list(geom.exterior.coords)
        for ring in geom.interiors:
            yield list(ring.coords)
    elif hasattr(geom, "coords"):
        yield list(geom.coords)
    elif hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from _coordinate_sequences(part)


def _has_duplicate_points(geom: BaseGeometry) -> bool:
    for coordinates in _coordinate_sequences(geom):
        comparable = coordinates[:-1] if len(coordinates) > 1 and coordinates[0] == coordinates[-1] else coordinates
        if any(left == right for left, right in zip(comparable, comparable[1:])):
            return True
    return False


def check_validity(geom: BaseGeometry | None) -> dict[str, Any]:
    """Return validity details for a single geometry."""
    if geom is None:
        return {
            "is_valid": False,
            "issue_type": "missing_geometry",
            "description": "Geometry is missing",
        }
    if geom.is_empty:
        return {
            "is_valid": False,
            "issue_type": "empty_geometry",
            "description": "Geometry is empty",
        }
    if _has_duplicate_points(geom):
        return {
            "is_valid": False,
            "issue_type": "duplicate_points",
            "description": "Geometry contains consecutive duplicate points",
        }
    if geom.is_valid:
        return {"is_valid": True, "issue_type": None, "description": "Valid Geometry"}

    description = explain_validity(geom)
    normalized = description.lower()
    if "self-intersection" in normalized:
        issue_type = "self_intersection"
    elif "ring" in normalized:
        issue_type = "invalid_ring"
    else:
        issue_type = "invalid_geometry"

    return {
        "is_valid": False,
        "issue_type": issue_type,
        "description": description,
    }


def detect_geometry_issues(gdf: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    """Return one issue record for every invalid feature in a GeoDataFrame."""
    issues: list[dict[str, Any]] = []
    for feature_index, geometry in gdf.geometry.items():
        result = check_validity(geometry)
        if not result["is_valid"]:
            issues.append(
                {
                    "feature_index": feature_index,
                    "issue_type": result["issue_type"],
                    "description": result["description"],
                }
            )
    return issues
