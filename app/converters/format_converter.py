"""Output writers for supported geospatial formats."""

from pathlib import Path

import fiona
import geopandas as gpd
from pyproj import CRS
from pyproj.exceptions import CRSError


def convert(
    gdf: gpd.GeoDataFrame,
    target_format: str,
    output_path: str,
    target_crs: str | None = None,
) -> str:
    """Write a GeoDataFrame as Shapefile, GeoJSON, or KML."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized_format = target_format.strip().lower()
    output_frame = gdf

    if target_crs:
        if gdf.crs is None:
            raise ValueError("Cannot reproject data without a source CRS")
        try:
            destination_crs = CRS.from_user_input(target_crs)
        except CRSError as exc:
            raise ValueError(f"Unsupported target CRS '{target_crs}'") from exc
        output_frame = gdf.to_crs(destination_crs)

    if normalized_format in {"shapefile", "shp"}:
        output_frame.to_file(
            output, driver="ESRI Shapefile", engine="fiona", index=False
        )
    elif normalized_format in {"geojson", "json"}:
        output_frame.to_file(output, driver="GeoJSON", engine="fiona", index=False)
    elif normalized_format == "kml":
        fiona.supported_drivers["KML"] = "rw"
        output_frame.to_file(output, driver="KML", engine="fiona", index=False)
    else:
        raise ValueError(
            f"Unsupported target format '{target_format}'; "
            "expected shapefile, geojson, or kml"
        )

    return str(output)
