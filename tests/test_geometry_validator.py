"""Tests for geometry validity checks."""

import geopandas as gpd
from shapely.geometry import Point, Polygon

from app.validators.geometry_validator import (
    check_validity,
    detect_geometry_issues,
)


def test_valid_geometry_passes() -> None:
    result = check_validity(Point(10, 20))

    assert result == {
        "is_valid": True,
        "issue_type": None,
        "description": "Valid Geometry",
    }


def test_self_intersecting_polygon_is_detected() -> None:
    bow_tie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])

    result = check_validity(bow_tie)

    assert result["is_valid"] is False
    assert result["issue_type"] == "self_intersection"
    assert "Self-intersection" in result["description"]


def test_batch_detection_includes_feature_index() -> None:
    bow_tie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])
    frame = gpd.GeoDataFrame(geometry=[Point(0, 0), bow_tie])

    issues = detect_geometry_issues(frame)

    assert len(issues) == 1
    assert issues[0]["feature_index"] == 1
    assert issues[0]["issue_type"] == "self_intersection"
