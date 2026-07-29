"""Tests for mixed-file ZIP batch processing."""

import json
from pathlib import Path
from zipfile import ZipFile

from app.utils.batch_processor import process_zip

GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Alpha"},
            "geometry": {"type": "Point", "coordinates": [10, 20]},
        }
    ],
}

KML = """<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <name>Alpha</name>
    <Point><coordinates>10,20,0</coordinates></Point>
  </Placemark>
</kml>
"""


def test_batch_with_all_valid_files(tmp_path: Path) -> None:
    archive_path = tmp_path / "valid.zip"
    with ZipFile(archive_path, mode="w") as archive:
        archive.writestr("point.geojson", json.dumps(GEOJSON))
        archive.writestr("point.csv", "name,lat,lon\nAlpha,20,10\n")
        archive.writestr("point.kml", KML)

    results = process_zip(str(archive_path), "parse")

    assert len(results) == 3
    assert all(item["status"] == "success" for item in results)
    assert {item["result"]["feature_count"] for item in results} == {1}


def test_corrupt_file_is_isolated(tmp_path: Path) -> None:
    archive_path = tmp_path / "mixed.zip"
    with ZipFile(archive_path, mode="w") as archive:
        archive.writestr("valid.csv", "name,lat,lon\nAlpha,20,10\n")
        archive.writestr("corrupt.geojson", '{"type": "FeatureCollection",')

    results = process_zip(str(archive_path), "parse")
    statuses = {item["filename"]: item["status"] for item in results}

    assert statuses == {
        "corrupt.geojson": "failure",
        "valid.csv": "success",
    }
    corrupt_result = next(
        item for item in results if item["filename"] == "corrupt.geojson"
    )
    assert "Malformed JSON" in corrupt_result["error"]


def test_empty_zip_is_handled(tmp_path: Path) -> None:
    archive_path = tmp_path / "empty.zip"
    with ZipFile(archive_path, mode="w"):
        pass

    assert process_zip(str(archive_path), "parse") == []
