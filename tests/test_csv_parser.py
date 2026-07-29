"""Tests for CSV latitude/longitude parsing."""

from pathlib import Path

import pytest

from app.parsers.csv_parser import CSVParseError, parse_csv


def test_valid_csv_with_explicit_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "custom.csv"
    csv_path.write_text(
        "name,Ycoord,Xcoord\nAlpha,20,10\nBeta,40,30\n",
        encoding="utf-8",
    )

    result = parse_csv(str(csv_path), lat_col="Ycoord", lon_col="Xcoord")

    assert result["feature_count"] == 2
    assert result["geometry_type"] == "Point"
    assert result["bounding_box"] == [10.0, 20.0, 30.0, 40.0]
    assert result["latitude_column"] == "Ycoord"
    assert result["longitude_column"] == "Xcoord"


def test_likely_coordinate_columns_are_auto_detected(tmp_path: Path) -> None:
    csv_path = tmp_path / "automatic.csv"
    csv_path.write_text(
        "name,Latitude,Longitude\nAlpha,20,10\n",
        encoding="utf-8",
    )

    result = parse_csv(str(csv_path))

    assert result["feature_count"] == 1
    assert result["latitude_column"] == "Latitude"
    assert result["longitude_column"] == "Longitude"


@pytest.mark.parametrize(
    ("coordinates", "message"),
    [
        ("not-a-number,10", "must be numeric"),
        ("91,10", "Latitude values must be between"),
        ("20,181", "Longitude values must be between"),
    ],
)
def test_invalid_coordinates_are_rejected(
    tmp_path: Path,
    coordinates: str,
    message: str,
) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(
        f"name,lat,lon\nAlpha,{coordinates}\n",
        encoding="utf-8",
    )

    with pytest.raises(CSVParseError, match=message):
        parse_csv(str(csv_path))
