"""Tests for per-key processing usage tracking."""

import json

from fastapi.testclient import TestClient

from app.auth.api_key import generate_key, get_usage, record_usage
from main import app

client = TestClient(app)


def _geojson_bytes(name: str = "Alpha") -> bytes:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": name},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [10, 20],
                    },
                }
            ],
        }
    ).encode("utf-8")


def test_record_usage_increments_per_key_and_endpoint() -> None:
    api_key = generate_key(label="usage-unit")["key"]

    record_usage(api_key, "/parse/geojson", 125)
    record_usage(api_key, "/convert", 375)
    record_usage(api_key, "/parse/geojson", 500)

    usage = get_usage(api_key)
    assert usage["total_requests"] == 3
    assert usage["total_bytes_processed"] == 1000
    assert usage["by_endpoint"] == {
        "/parse/geojson": 2,
        "/convert": 1,
    }
    assert usage["last_used_at"] is not None


def test_usage_me_returns_accurate_authenticated_totals() -> None:
    api_key = generate_key(label="usage-endpoint")["key"]
    headers = {"X-API-Key": api_key}
    first_payload = _geojson_bytes("First")
    second_payload = _geojson_bytes("Second")

    for filename, payload in (
        ("first.geojson", first_payload),
        ("second.geojson", second_payload),
    ):
        response = client.post(
            "/parse/geojson",
            headers=headers,
            files={"file": (filename, payload, "application/geo+json")},
        )
        assert response.status_code == 200

    response = client.get("/usage/me", headers=headers)

    assert response.status_code == 200
    usage = response.json()
    assert usage["total_requests"] == 2
    assert usage["by_endpoint"] == {"/parse/geojson": 2}
    assert usage["total_bytes_processed"] == len(first_payload) + len(second_payload)
    assert usage["last_used_at"] is not None
