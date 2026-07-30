"""Tests for reusable spatial operations."""

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from app.analysis.spatial_ops import (
    clip_layer,
    compute_geometry_stats,
    merge_layers,
    spatial_join,
)


def test_clip_returns_only_features_within_boundary() -> None:
    inputs = gpd.GeoDataFrame(
        {"name": ["inside", "outside"]},
        geometry=[Point(1, 1), Point(5, 5)],
        crs="EPSG:3857",
    )
    boundary = gpd.GeoDataFrame(
        geometry=[box(0, 0, 2, 2)],
        crs="EPSG:3857",
    )

    result = clip_layer(inputs, boundary)

    assert result["name"].tolist() == ["inside"]


def test_merge_combines_layers_and_aligns_crs() -> None:
    first = gpd.GeoDataFrame(
        {"name": ["origin"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    second = gpd.GeoDataFrame(
        {"name": ["east"]},
        geometry=[Point(1113194.9079, 0)],
        crs="EPSG:3857",
    )

    result = merge_layers([first, second])

    assert len(result) == 2
    assert result.crs.to_epsg() == 4326
    assert result.geometry.iloc[1].x == pytest.approx(10.0, rel=1e-6)


@pytest.mark.parametrize("predicate", ["intersects", "within"])
def test_spatial_join_point_to_polygon_predicates(predicate: str) -> None:
    points = gpd.GeoDataFrame(
        {"point_name": ["inside", "outside"]},
        geometry=[Point(1, 1), Point(5, 5)],
        crs="EPSG:3857",
    )
    polygons = gpd.GeoDataFrame(
        {"zone": ["target"]},
        geometry=[box(0, 0, 2, 2)],
        crs="EPSG:3857",
    )

    result = spatial_join(points, polygons, predicate)

    assert result["point_name"].tolist() == ["inside"]
    assert result["zone"].tolist() == ["target"]


def test_spatial_join_contains_predicate() -> None:
    polygons = gpd.GeoDataFrame(
        {"zone": ["target"]},
        geometry=[box(0, 0, 2, 2)],
        crs="EPSG:3857",
    )
    points = gpd.GeoDataFrame(
        {"point_name": ["inside", "outside"]},
        geometry=[Point(1, 1), Point(5, 5)],
        crs="EPSG:3857",
    )

    result = spatial_join(polygons, points, "contains")

    assert result["zone"].tolist() == ["target"]
    assert result["point_name"].tolist() == ["inside"]


def test_geometry_statistics_are_accurate_for_known_square() -> None:
    frame = gpd.GeoDataFrame(
        {"name": ["square"]},
        geometry=[box(0, 0, 2, 2)],
        crs="EPSG:3857",
    )

    result = compute_geometry_stats(frame)
    feature = result["features"][0]

    assert feature["area"] == 4.0
    assert feature["perimeter"] == 8.0
    assert feature["centroid"] == {"x": 1.0, "y": 1.0}
    assert feature["vertex_count"] == 4
    assert result["total_area"] == 4.0
    assert result["total_perimeter"] == 8.0
    assert result["total_vertices"] == 4
