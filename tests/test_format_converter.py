"""Tests for uniform geospatial format conversion."""

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from app.converters.base_converter import load_any
from app.converters.format_converter import convert


def _sample_frame() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["Alpha"]},
        geometry=[Point(10, 20)],
        crs="EPSG:4326",
    )


def _write_kml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Alpha</name>
      <Point><coordinates>10,20,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
""",
        encoding="utf-8",
    )


def test_shapefile_to_geojson(tmp_path: Path) -> None:
    source = tmp_path / "source.shp"
    output = tmp_path / "converted.geojson"
    _sample_frame().to_file(source, driver="ESRI Shapefile", engine="fiona")

    converted_path = convert(load_any(str(source)), "geojson", str(output))
    result = load_any(converted_path)

    assert Path(converted_path) == output
    assert len(result) == 1
    assert result.geometry.iloc[0].equals(Point(10, 20))


def test_geojson_to_kml(tmp_path: Path) -> None:
    source = tmp_path / "source.geojson"
    output = tmp_path / "converted.kml"
    _sample_frame().to_file(source, driver="GeoJSON", engine="fiona")

    converted_path = convert(load_any(str(source)), "kml", str(output))
    result = load_any(converted_path)

    assert Path(converted_path) == output
    assert len(result) == 1
    assert result.geometry.iloc[0].equals(Point(10, 20))


def test_kml_to_shapefile_with_crs_reprojection(tmp_path: Path) -> None:
    source = tmp_path / "source.kml"
    output = tmp_path / "converted.shp"
    _write_kml(source)

    converted_path = convert(
        load_any(str(source)),
        "shapefile",
        str(output),
        target_crs="EPSG:3857",
    )
    result = load_any(converted_path)

    assert result.crs.to_epsg() == 3857
    assert result.geometry.iloc[0].x == pytest.approx(1113194.91, rel=1e-6)
    assert result.geometry.iloc[0].y == pytest.approx(2273030.93, rel=1e-6)
