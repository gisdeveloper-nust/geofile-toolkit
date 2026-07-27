"""Automatic repair helpers for invalid Shapely geometries."""

from typing import Any

import geopandas as gpd
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from app.validators.geometry_validator import check_validity


def repair_geometry(geom: BaseGeometry | None) -> BaseGeometry | None:
    """Repair an invalid geometry with ``buffer(0)`` and ``make_valid``."""
    if geom is None or geom.is_empty or geom.is_valid:
        return geom

    try:
        buffered = geom.buffer(0)
        if not buffered.is_empty and buffered.is_valid:
            return buffered
    except Exception:
        # GEOS can reject severely damaged coordinate structures; make_valid is
        # the secondary strategy for those cases.
        pass

    try:
        repaired = make_valid(geom)
        if not repaired.is_empty and repaired.is_valid:
            return repaired
    except Exception:
        pass

    return geom


def repair_batch(
    gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    """Repair all fixable geometries and return the repaired data and report."""
    repaired_frame = gdf.copy()
    report: list[dict[str, Any]] = []

    for feature_index, geometry in repaired_frame.geometry.items():
        original_result = check_validity(geometry)
        if original_result["is_valid"]:
            continue

        repaired_geometry = repair_geometry(geometry)
        repaired_result = check_validity(repaired_geometry)
        if repaired_result["is_valid"]:
            repaired_frame.at[feature_index, repaired_frame.geometry.name] = (
                repaired_geometry
            )
            status = "fixed"
            description = "Geometry repaired successfully"
        else:
            status = "unfixable"
            description = repaired_result["description"]

        report.append(
            {
                "feature_index": feature_index,
                "status": status,
                "issue_type": original_result["issue_type"],
                "description": description,
            }
        )

    return repaired_frame, report
