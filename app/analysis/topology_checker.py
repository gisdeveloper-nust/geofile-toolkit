"""Polygon topology checks using Shapely and GeoPandas spatial indexes."""

from typing import Any

import geopandas as gpd
from shapely import union_all
from shapely.geometry import MultiPolygon, Polygon


def _native_index(value: Any) -> int | str:
    return value.item() if hasattr(value, "item") else value


def _severity(area: float, reference_area: float) -> str:
    ratio = area / reference_area if reference_area else 0
    if ratio >= 0.1:
        return "high"
    if ratio >= 0.01:
        return "medium"
    return "low"


def _polygon_parts(geometry: Any) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return []


def check_topology(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """Detect polygon overlaps, coverage gaps, and unusually small slivers."""
    if gdf.empty:
        return {
            "feature_count": 0,
            "issues": [],
            "overlap_count": 0,
            "gap_count": 0,
            "sliver_count": 0,
        }

    geometries = gdf.geometry.dropna()
    if geometries.empty or not geometries.geom_type.isin(
        {"Polygon", "MultiPolygon"}
    ).all():
        raise ValueError("Topology analysis requires polygon geometries")

    areas = geometries.area
    reference_area = float(areas.median()) or float(areas.sum()) or 1.0
    tolerance = max(reference_area * 1e-9, 1e-12)
    sliver_threshold = reference_area * 0.01
    issues: list[dict[str, Any]] = []

    positions = {index: position for position, index in enumerate(gdf.index)}
    for left_index, left_geometry in geometries.items():
        for right_index in gdf.sindex.query(left_geometry, predicate="intersects"):
            right_label = gdf.index[right_index]
            if right_label not in positions:
                continue
            if positions[right_label] <= positions[left_index]:
                continue
            right_geometry = gdf.geometry.iloc[right_index]
            intersection = left_geometry.intersection(right_geometry)
            overlap_area = float(intersection.area)
            if overlap_area > tolerance:
                issues.append(
                    {
                        "issue_type": "overlap",
                        "feature_indices": [
                            _native_index(left_index),
                            _native_index(right_label),
                        ],
                        "area": overlap_area,
                        "severity": _severity(overlap_area, reference_area),
                        "description": "Polygon interiors overlap",
                    }
                )

    coverage = union_all(geometries.to_list())
    candidate_gaps = coverage.convex_hull.difference(coverage)
    for gap in _polygon_parts(candidate_gaps):
        gap_area = float(gap.area)
        if gap_area > tolerance:
            issues.append(
                {
                    "issue_type": "gap",
                    "feature_indices": [],
                    "area": gap_area,
                    "severity": _severity(gap_area, reference_area),
                    "description": "Polygon coverage contains an enclosed or internal gap",
                }
            )

    for feature_index, area in areas.items():
        feature_area = float(area)
        if tolerance < feature_area < sliver_threshold:
            issues.append(
                {
                    "issue_type": "sliver",
                    "feature_indices": [_native_index(feature_index)],
                    "area": feature_area,
                    "severity": "low",
                    "description": "Polygon area is below the sliver threshold",
                }
            )

    return {
        "feature_count": len(gdf),
        "issues": issues,
        "overlap_count": sum(
            issue["issue_type"] == "overlap" for issue in issues
        ),
        "gap_count": sum(issue["issue_type"] == "gap" for issue in issues),
        "sliver_count": sum(issue["issue_type"] == "sliver" for issue in issues),
    }
