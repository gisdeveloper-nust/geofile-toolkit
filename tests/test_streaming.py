"""Tests for chunked uploads and maximum file-size enforcement."""

import json

from fastapi.testclient import TestClient

import main
from app.auth.api_key import generate_key
from app.utils.streaming import save_upload_file

client = TestClient(main.app)


def _geojson_bytes(extra_text: str) -> bytes:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"description": extra_text},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [10, 20],
                    },
                }
            ],
        }
    ).encode("utf-8")


def test_large_file_upload_uses_streaming_path(monkeypatch) -> None:
    api_key = generate_key(label="streaming-success")["key"]
    payload = _geojson_bytes("x" * 1024)
    used_streaming_path = False

    async def save_with_test_threshold(upload, destination):
        nonlocal used_streaming_path
        used_streaming_path = upload.size is None or upload.size > 64
        return await save_upload_file(
            upload,
            destination,
            threshold=64,
            chunk_size=32,
            max_bytes=4096,
        )

    monkeypatch.setattr(main, "save_upload_file", save_with_test_threshold)
    response = client.post(
        "/parse/geojson",
        headers={"X-API-Key": api_key},
        files={"file": ("large.geojson", payload, "application/geo+json")},
    )

    assert response.status_code == 200
    assert used_streaming_path is True
    assert response.json()["feature_count"] == 1


def test_oversized_upload_is_rejected_with_413(monkeypatch) -> None:
    api_key = generate_key(label="streaming-limit")["key"]
    payload = _geojson_bytes("x" * 1024)

    async def save_with_test_limit(upload, destination):
        return await save_upload_file(
            upload,
            destination,
            threshold=64,
            chunk_size=32,
            max_bytes=128,
        )

    monkeypatch.setattr(main, "save_upload_file", save_with_test_limit)
    response = client.post(
        "/parse/geojson",
        headers={"X-API-Key": api_key},
        files={"file": ("oversized.geojson", payload, "application/geo+json")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == (
        "File exceeds maximum upload size of 128 bytes"
    )
