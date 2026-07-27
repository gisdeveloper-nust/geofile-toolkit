"""Tests for automatic geometry repair."""

import geopandas as gpd
from shapely.geometry import Polygon

from app.repairs.geometry_repair import repair_batch, repair_geometry


def test_repair_fixes_known_bad_geometry() -> None:
    bow_tie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])
    assert not bow_tie.is_valid

    repaired = repair_geometry(bow_tie)

    assert repaired is not None
    assert repaired.is_valid
    assert not repaired.is_empty


def test_unfixable_geometry_is_reported() -> None:
    frame = gpd.GeoDataFrame({"name": ["missing"]}, geometry=[None])

    repaired_frame, report = repair_batch(frame)

    assert repaired_frame.geometry.iloc[0] is None
    assert report == [
        {
            "feature_index": 0,
            "status": "unfixable",
            "issue_type": "missing_geometry",
            "description": "Geometry is missing",
        }
    ]
