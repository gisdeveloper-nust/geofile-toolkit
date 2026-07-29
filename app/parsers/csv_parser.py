"""CSV latitude/longitude parser."""

from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

LATITUDE_NAMES = ("lat", "latitude", "y")
LONGITUDE_NAMES = ("lon", "lng", "long", "longitude", "x")


class CSVParseError(ValueError):
    """Raised when CSV coordinate data cannot be parsed safely."""


def _detect_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {column.strip().lower(): column for column in columns}
    return next(
        (normalized[name] for name in candidates if name in normalized),
        None,
    )


def parse_csv(
    filepath: str,
    lat_col: str | None = None,
    lon_col: str | None = None,
) -> dict[str, Any]:
    """Read CSV coordinates and return point geometry metadata."""
    path = Path(filepath)
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise CSVParseError(f"Unable to read CSV: {exc}") from exc
    if frame.empty:
        raise CSVParseError("CSV contains no data rows")

    latitude_column = lat_col or _detect_column(frame.columns.tolist(), LATITUDE_NAMES)
    longitude_column = lon_col or _detect_column(
        frame.columns.tolist(), LONGITUDE_NAMES
    )
    missing_columns = [
        label
        for label, column in (
            ("latitude", latitude_column),
            ("longitude", longitude_column),
        )
        if column is None or column not in frame.columns
    ]
    if missing_columns:
        raise CSVParseError(
            "Missing coordinate column(s): "
            + ", ".join(missing_columns)
            + ". Specify lat_col and lon_col explicitly."
        )

    latitude = pd.to_numeric(frame[latitude_column], errors="coerce")
    longitude = pd.to_numeric(frame[longitude_column], errors="coerce")
    if latitude.isna().any() or longitude.isna().any():
        raise CSVParseError("Latitude and longitude values must be numeric")
    if not latitude.between(-90, 90).all():
        raise CSVParseError("Latitude values must be between -90 and 90")
    if not longitude.between(-180, 180).all():
        raise CSVParseError("Longitude values must be between -180 and 180")

    frame = frame.copy()
    frame[latitude_column] = latitude
    frame[longitude_column] = longitude
    geo_frame = gpd.GeoDataFrame(
        frame,
        geometry=gpd.points_from_xy(
            frame[longitude_column],
            frame[latitude_column],
        ),
        crs="EPSG:4326",
    )

    return {
        "geometry_type": "Point",
        "feature_count": len(geo_frame),
        "crs": geo_frame.crs.to_string(),
        "bounding_box": geo_frame.total_bounds.tolist(),
        "attribute_fields": {
            column: str(dtype) for column, dtype in frame.dtypes.items()
        },
        "latitude_column": latitude_column,
        "longitude_column": longitude_column,
    }
