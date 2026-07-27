"""KML metadata parser."""

from typing import Any

import fiona
import geopandas as gpd


def _enable_kml_driver() -> None:
    """Enable Fiona's GDAL-backed KML driver for read operations."""
    fiona.supported_drivers["KML"] = "rw"


def parse_kml(filepath: str) -> dict[str, Any]:
    """Read a KML file and return geometry and attribute metadata."""
    _enable_kml_driver()
    frame = gpd.read_file(filepath, driver="KML", engine="fiona")
    geometry_types = sorted(frame.geometry.geom_type.dropna().unique().tolist())
    geometry_type = (
        geometry_types[0]
        if len(geometry_types) == 1
        else f"Mixed ({', '.join(geometry_types)})"
    )
    attribute_fields = {
        column: str(dtype)
        for column, dtype in frame.drop(columns=frame.geometry.name).dtypes.items()
    }

    return {
        "geometry_type": geometry_type,
        "feature_count": len(frame),
        "crs": frame.crs.to_string() if frame.crs else None,
        "bounding_box": frame.total_bounds.tolist(),
        "attribute_fields": attribute_fields,
    }
