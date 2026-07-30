"""Tests for polygon topology analysis."""

import geopandas as gpd
from shapely.geometry import box

from app.analysis.topology_checker import (
    check_topology,
    summarize_topology_issues,
)


def _frame(*polygons) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": [f"polygon-{index}" for index in range(len(polygons))]},
        geometry=list(polygons),
        crs="EPSG:3857",
    )


def test_clean_adjacent_dataset_passes() -> None:
    frame = _frame(box(0, 0, 1, 1), box(1, 0, 2, 1))

    report = summarize_topology_issues(frame)

    assert report.issue_count == 0
    assert report.overlap_count == 0
    assert report.gap_count == 0
    assert report.sliver_count == 0
    assert report.highest_severity == "none"


def test_overlapping_polygons_are_detected() -> None:
    frame = _frame(box(0, 0, 2, 2), box(1, 0, 3, 2))

    result = check_topology(frame)

    assert result["overlap_count"] == 1
    overlap = next(
        issue for issue in result["issues"] if issue["issue_type"] == "overlap"
    )
    assert overlap["feature_indices"] == [0, 1]
    assert overlap["area"] == 2.0


def test_gap_between_adjacent_coverage_polygons_is_detected() -> None:
    frame = _frame(box(0, 0, 1, 1), box(2, 0, 3, 1))

    result = check_topology(frame)

    assert result["gap_count"] == 1
    gap = next(issue for issue in result["issues"] if issue["issue_type"] == "gap")
    assert gap["area"] == 1.0
