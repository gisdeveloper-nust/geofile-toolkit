"""Shared loading behavior for supported geospatial formats."""

from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd

from app.parsers.csv_parser import parse_csv


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
    if suffix == ".gpx":
        available_layers = set(fiona.listlayers(path))
        frames = [
            gpd.read_file(path, layer=layer, driver="GPX", engine="fiona")
            for layer in ("waypoints", "tracks", "routes")
            if layer in available_layers
        ]
        nonempty_frames = [frame for frame in frames if not frame.empty]
        if not nonempty_frames:
            raise ValueError("GPX contains no loadable spatial features")
        return gpd.GeoDataFrame(
            pd.concat(nonempty_frames, ignore_index=True),
            geometry="geometry",
            crs=nonempty_frames[0].crs,
        )
    if suffix == ".csv":
        metadata = parse_csv(str(path))
        frame = pd.read_csv(path)
        return gpd.GeoDataFrame(
            frame,
            geometry=gpd.points_from_xy(
                pd.to_numeric(frame[metadata["longitude_column"]]),
                pd.to_numeric(frame[metadata["latitude_column"]]),
            ),
            crs="EPSG:4326",
        )

    raise ValueError(
        f"Unsupported input format '{suffix or '(none)'}'; "
        "expected .shp, .geojson, .json, .kml, .gpx, or .csv"
    )
