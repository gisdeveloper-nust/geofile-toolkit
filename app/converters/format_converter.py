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
    elif normalized_format == "gpx":
        geometry_types = set(output_frame.geometry.geom_type.dropna())
        if geometry_types and geometry_types <= {"Point", "MultiPoint"}:
            gpx_frame = output_frame.explode(index_parts=False)
            layer = "waypoints"
        elif geometry_types and geometry_types <= {
            "LineString",
            "MultiLineString",
        }:
            gpx_frame = output_frame
            layer = "tracks"
        else:
            raise ValueError(
                "GPX output supports point-only or line-only datasets"
            )
        gpx_frame.to_file(
            output,
            layer=layer,
            driver="GPX",
            engine="fiona",
            index=False,
            GPX_USE_EXTENSIONS="YES",
        )
    elif normalized_format == "csv":
        geometry_types = set(output_frame.geometry.geom_type.dropna())
        if geometry_types - {"Point"}:
            raise ValueError("CSV output supports Point geometries only")
        csv_frame = output_frame.copy()
        csv_frame["longitude"] = csv_frame.geometry.x
        csv_frame["latitude"] = csv_frame.geometry.y
        csv_frame.drop(columns=csv_frame.geometry.name).to_csv(output, index=False)
    else:
        raise ValueError(
            f"Unsupported target format '{target_format}'; "
            "expected shapefile, geojson, kml, gpx, or csv"
        )

    return str(output)
