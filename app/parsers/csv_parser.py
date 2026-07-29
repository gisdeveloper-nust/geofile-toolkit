"""CSV latitude/longitude parser."""

from typing import Any

import geopandas as gpd
import pandas as pd

LATITUDE_NAMES = ("lat", "latitude", "y")
LONGITUDE_NAMES = ("lon", "lng", "long", "longitude", "x")


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
    frame = pd.read_csv(filepath)
    latitude_column = lat_col or _detect_column(frame.columns.tolist(), LATITUDE_NAMES)
    longitude_column = lon_col or _detect_column(
        frame.columns.tolist(), LONGITUDE_NAMES
    )
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
