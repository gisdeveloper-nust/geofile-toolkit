"""Tests for shapefile metadata parsing."""

from pathlib import Path

import fiona
import geopandas as gpd
import pytest
from shapely.geometry import Point

from app.parsers.shapefile_parser import ShapefileParseError, parse_shapefile


def _write_valid_shapefile(directory: Path) -> Path:
    shapefile = directory / "places.shp"
    frame = gpd.GeoDataFrame(
        {"name": ["Alpha", "Beta"], "value": [1, 2]},
        geometry=[Point(10, 20), Point(30, 40)],
        crs="EPSG:4326",
    )
    frame.to_file(shapefile, engine="fiona")
    return shapefile


def test_valid_shapefile_parses_correctly(tmp_path: Path) -> None:
    result = parse_shapefile(str(_write_valid_shapefile(tmp_path)))

    assert result["geometry_type"] == "Point"
    assert result["feature_count"] == 2
    assert result["crs"]
    assert result["bounding_box"] == [10.0, 20.0, 30.0, 40.0]
    assert set(result["attribute_fields"]) == {"name", "value"}


def test_missing_shx_raises_clear_error(tmp_path: Path) -> None:
    shapefile = _write_valid_shapefile(tmp_path)
    shapefile.with_suffix(".shx").unlink()

    with pytest.raises(ShapefileParseError, match=r"Missing required.*\.shx"):
        parse_shapefile(str(shapefile))


def test_empty_shapefile_raises_clear_error(tmp_path: Path) -> None:
    shapefile = tmp_path / "empty.shp"
    schema = {"geometry": "Point", "properties": {"name": "str"}}
    with fiona.open(
        shapefile,
        mode="w",
        driver="ESRI Shapefile",
        schema=schema,
        crs="EPSG:4326",
    ):
        pass

    with pytest.raises(ShapefileParseError, match="contains no features"):
        parse_shapefile(str(shapefile))


def test_corrupt_shapefile_raises_clear_error(tmp_path: Path) -> None:
    shapefile = tmp_path / "corrupt.shp"
    shapefile.write_bytes(b"not a shapefile")
    shapefile.with_suffix(".shx").write_bytes(b"invalid index")
    shapefile.with_suffix(".dbf").write_bytes(b"invalid attributes")

    with pytest.raises(ShapefileParseError, match="Unable to read shapefile"):
        parse_shapefile(str(shapefile))
