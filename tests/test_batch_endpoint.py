"""Integration test for the mixed-file batch endpoint."""

import json
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_batch_endpoint_processes_three_mixed_files() -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "GeoJSON point"},
                "geometry": {"type": "Point", "coordinates": [10, 20]},
            }
        ],
    }
    kml = """<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <name>KML point</name>
    <Point><coordinates>30,40,0</coordinates></Point>
  </Placemark>
</kml>
"""
    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, mode="w") as archive:
        archive.writestr("point.geojson", json.dumps(geojson))
        archive.writestr("point.csv", "name,latitude,longitude\nCSV point,60,50\n")
        archive.writestr("point.kml", kml)

    response = client.post(
        "/batch/process",
        files={
            "file": (
                "mixed.zip",
                archive_buffer.getvalue(),
                "application/zip",
            )
        },
        data={"operation": "parse"},
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 3
    assert {item["filename"] for item in results} == {
        "point.csv",
        "point.geojson",
        "point.kml",
    }
    assert all(item["status"] == "success" for item in results)
    assert all(item["result"]["feature_count"] == 1 for item in results)
