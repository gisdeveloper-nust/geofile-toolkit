"""Output writers for supported geospatial formats."""

from pathlib import Path

import fiona
import geopandas as gpd


def convert(
    gdf: gpd.GeoDataFrame,
    target_format: str,
    output_path: str,
) -> str:
    """Write a GeoDataFrame as Shapefile, GeoJSON, or KML."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized_format = target_format.strip().lower()

    if normalized_format in {"shapefile", "shp"}:
        gdf.to_file(output, driver="ESRI Shapefile", engine="fiona", index=False)
    elif normalized_format in {"geojson", "json"}:
        gdf.to_file(output, driver="GeoJSON", engine="fiona", index=False)
    elif normalized_format == "kml":
        fiona.supported_drivers["KML"] = "rw"
        gdf.to_file(output, driver="KML", engine="fiona", index=False)
    else:
        raise ValueError(
            f"Unsupported target format '{target_format}'; "
            "expected shapefile, geojson, or kml"
        )

    return str(output)
