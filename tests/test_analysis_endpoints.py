"""Integration tests for downloadable spatial analysis endpoints."""

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _feature_collection(features: list[dict]) -> bytes:
    return json.dumps(
        {"type": "FeatureCollection", "features": features}
    ).encode("utf-8")


POINTS = _feature_collection(
    [
        {
            "type": "Feature",
            "properties": {"name": "inside"},
            "geometry": {"type": "Point", "coordinates": [1, 1]},
        },
        {
            "type": "Feature",
            "properties": {"name": "outside"},
            "geometry": {"type": "Point", "coordinates": [5, 5]},
        },
    ]
)

BOUNDARY = _feature_collection(
    [
        {
            "type": "Feature",
            "properties": {"zone": "target"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]
                ],
            },
        }
    ]
)


def test_clip_endpoint_upload_to_download_round_trip() -> None:
    response = client.post(
        "/analyze/clip",
        files={
            "input_file": (
                "points.geojson",
                POINTS,
                "application/geo+json",
            ),
            "clip_file": (
                "boundary.geojson",
                BOUNDARY,
                "application/geo+json",
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/geo+json")
    result = response.json()
    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["name"] == "inside"


def test_spatial_join_endpoint_upload_to_download_round_trip() -> None:
    response = client.post(
        "/analyze/spatial-join",
        files={
            "left_file": (
                "points.geojson",
                POINTS,
                "application/geo+json",
            ),
            "right_file": (
                "boundary.geojson",
                BOUNDARY,
                "application/geo+json",
            ),
        },
        data={"predicate": "within"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/geo+json")
    result = response.json()
    assert len(result["features"]) == 1
    properties = result["features"][0]["properties"]
    assert properties["name"] == "inside"
    assert properties["zone"] == "target"
