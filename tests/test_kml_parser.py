"""Tests for KML metadata parsing."""

from pathlib import Path

import pytest

from app.parsers.kml_parser import KMLParseError, parse_kml


def test_valid_kml_parses_correctly(tmp_path: Path) -> None:
    kml_path = tmp_path / "places.kml"
    kml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Alpha</name>
      <Point><coordinates>10,20,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Beta</name>
      <Point><coordinates>30,40,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
""",
        encoding="utf-8",
    )

    result = parse_kml(str(kml_path))

    assert result["geometry_type"] == "Point"
    assert result["feature_count"] == 2
    assert result["crs"]
    assert result["bounding_box"] == [10.0, 20.0, 30.0, 40.0]
    assert "Name" in result["attribute_fields"]


def test_malformed_xml_raises_clear_error(tmp_path: Path) -> None:
    kml_path = tmp_path / "malformed.kml"
    kml_path.write_text("<kml><Placemark></kml>", encoding="utf-8")

    with pytest.raises(KMLParseError, match="Malformed KML XML"):
        parse_kml(str(kml_path))


def test_unsupported_kml_is_handled_gracefully(tmp_path: Path) -> None:
    kml_path = tmp_path / "overlay.kml"
    kml_path.write_text(
        """<kml xmlns="http://www.opengis.net/kml/2.2">
  <GroundOverlay>
    <name>Unsupported overlay</name>
    <Icon><href>image.png</href></Icon>
  </GroundOverlay>
</kml>
""",
        encoding="utf-8",
    )

    with pytest.raises(KMLParseError, match="Unsupported KML content"):
        parse_kml(str(kml_path))
