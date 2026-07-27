"""Shared loading behavior for supported geospatial formats."""

from pathlib import Path

import fiona
import geopandas as gpd


def load_any(filepath: str) -> gpd.GeoDataFrame:
    """Auto-detect and load a Shapefile, GeoJSON, or KML file."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".shp":
        return gpd.read_file(path, engine="fiona")
    if suffix in {".geojson", ".json"}:
        return gpd.read_file(path, engine="fiona")
    if suffix == ".kml":
        fiona.supported_drivers["KML"] = "rw"
        return gpd.read_file(path, driver="KML", engine="fiona")

    raise ValueError(
        f"Unsupported input format '{suffix or '(none)'}'; "
        "expected .shp, .geojson, .json, or .kml"
    )
