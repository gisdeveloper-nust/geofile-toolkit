"""Tests for GeoJSON metadata parsing."""

import json
from pathlib import Path

import pytest

from app.parsers.geojson_parser import GeoJSONParseError, parse_geojson


def test_valid_geojson_parses_correctly(tmp_path: Path) -> None:
    geojson_path = tmp_path / "places.geojson"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Alpha", "value": 1},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [10.0, 20.0],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Beta", "value": 2},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [30.0, 40.0],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = parse_geojson(str(geojson_path))

    assert result["geometry_type"] == "Point"
    assert result["feature_count"] == 2
    assert result["bounding_box"] == [10.0, 20.0, 30.0, 40.0]
    assert set(result["attribute_fields"]) == {"name", "value"}


def test_malformed_json_raises_clear_error(tmp_path: Path) -> None:
    geojson_path = tmp_path / "malformed.geojson"
    geojson_path.write_text('{"type": "FeatureCollection",', encoding="utf-8")

    with pytest.raises(GeoJSONParseError, match="Malformed JSON"):
        parse_geojson(str(geojson_path))


def test_empty_feature_collection_raises_clear_error(tmp_path: Path) -> None:
    geojson_path = tmp_path / "empty.geojson"
    geojson_path.write_text(
        '{"type": "FeatureCollection", "features": []}',
        encoding="utf-8",
    )

    with pytest.raises(GeoJSONParseError, match="contains no features"):
        parse_geojson(str(geojson_path))
