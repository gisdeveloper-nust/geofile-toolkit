"""Tests for GPX metadata parsing."""

from pathlib import Path

import pytest

from app.parsers.gpx_parser import GPXParseError, parse_gpx

VALID_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="GeoFile Toolkit"
     xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="20" lon="10"><name>Waypoint</name></wpt>
  <rte>
    <name>Route</name>
    <rtept lat="20" lon="10"/>
    <rtept lat="21" lon="11"/>
  </rte>
  <trk>
    <name>Track</name>
    <trkseg>
      <trkpt lat="20" lon="10"/>
      <trkpt lat="22" lon="12"/>
    </trkseg>
  </trk>
</gpx>
"""


def test_valid_gpx_parses_correctly(tmp_path: Path) -> None:
    gpx_path = tmp_path / "mixed.gpx"
    gpx_path.write_text(VALID_GPX, encoding="utf-8")

    result = parse_gpx(str(gpx_path))

    assert result["feature_count"] == 3
    assert result["layer_counts"] == {
        "waypoints": 1,
        "tracks": 1,
        "routes": 1,
    }
    assert result["geometry_type"] == "Mixed (LineString, MultiLineString, Point)"
    assert result["bounding_box"] == [10.0, 20.0, 12.0, 22.0]


def test_empty_gpx_is_handled(tmp_path: Path) -> None:
    gpx_path = tmp_path / "empty.gpx"
    gpx_path.write_text(
        '<gpx version="1.1" creator="test" '
        'xmlns="http://www.topografix.com/GPX/1/1"/>',
        encoding="utf-8",
    )

    with pytest.raises(GPXParseError, match="contains no waypoints"):
        parse_gpx(str(gpx_path))


def test_malformed_gpx_raises_clear_error(tmp_path: Path) -> None:
    gpx_path = tmp_path / "malformed.gpx"
    gpx_path.write_text('<gpx version="1.1"><wpt></gpx>', encoding="utf-8")

    with pytest.raises(GPXParseError, match="Malformed GPX XML"):
        parse_gpx(str(gpx_path))
