"""Tests for the installable GeoFile Toolkit CLI."""

import json
from pathlib import Path

from click.testing import CliRunner

from cli.main import geofile


def _write_point_geojson(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Alpha"},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [10, 20],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_parse_command_prints_spatial_summary(tmp_path: Path) -> None:
    source = tmp_path / "point.geojson"
    _write_point_geojson(source)

    result = CliRunner().invoke(geofile, ["parse", str(source)])

    assert result.exit_code == 0, result.output
    assert "Geometry: Point" in result.output
    assert "Features: 1" in result.output
    assert "Bounding box: [10.0, 20.0, 10.0, 20.0]" in result.output


def test_convert_command_detects_output_format(tmp_path: Path) -> None:
    source = tmp_path / "point.geojson"
    output = tmp_path / "point.csv"
    _write_point_geojson(source)

    result = CliRunner().invoke(
        geofile,
        ["convert", str(source), str(output)],
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert "longitude" in output.read_text(encoding="utf-8")
    assert f"Converted file: {output}" in result.output


def test_validate_command_reports_clean_geometry(tmp_path: Path) -> None:
    source = tmp_path / "point.geojson"
    _write_point_geojson(source)

    result = CliRunner().invoke(geofile, ["validate", str(source)])

    assert result.exit_code == 0, result.output
    assert "No issues found." in result.output
