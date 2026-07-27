"""Integration tests for upload-to-download format conversion."""

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.converters.base_converter import load_any
from main import app

client = TestClient(app)

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

KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Alpha</name>
      <Point><coordinates>10,20,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def test_geojson_upload_downloads_kml(tmp_path: Path) -> None:
    response = client.post(
        "/convert",
        files={
            "file": (
                "places.geojson",
                json.dumps(GEOJSON).encode(),
                "application/geo+json",
            )
        },
        data={"target_format": "kml"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.google-earth.kml+xml"
    )
    downloaded = tmp_path / "downloaded.kml"
    downloaded.write_bytes(response.content)
    result = load_any(str(downloaded))
    assert len(result) == 1
    assert result.geometry.iloc[0].x == 10


def test_kml_upload_downloads_shapefile_zip(tmp_path: Path) -> None:
    response = client.post(
        "/convert",
        files={"file": ("places.kml", KML, "application/vnd.google-earth.kml+xml")},
        data={"target_format": "shapefile"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(response.content)) as archive:
        archive.extractall(tmp_path)
        names = archive.namelist()

    assert any(name.endswith(".shp") for name in names)
    assert any(name.endswith(".shx") for name in names)
    assert any(name.endswith(".dbf") for name in names)
    shapefile = next(tmp_path.glob("*.shp"))
    result = load_any(str(shapefile))
    assert len(result) == 1
    assert result.geometry.iloc[0].y == 20
