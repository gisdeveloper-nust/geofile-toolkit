"""Reusable GeoPandas spatial operations."""

import geopandas as gpd
import pandas as pd
from shapely.geometry.base import BaseGeometry


def clip_layer(
    input_gdf: gpd.GeoDataFrame,
    clip_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Clip an input layer to the combined geometry of a boundary layer."""
    if input_gdf.crs is None or clip_gdf.crs is None:
        raise ValueError("Both input and clip layers must define a CRS")
    aligned_clip = (
        clip_gdf
        if input_gdf.crs == clip_gdf.crs
        else clip_gdf.to_crs(input_gdf.crs)
    )
    return gpd.clip(input_gdf, aligned_clip, keep_geom_type=False)


def merge_layers(gdf_list: list[gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    """Merge layers after reprojecting them to the first layer's CRS."""
    if not gdf_list:
        raise ValueError("At least one layer is required for merge")
    common_crs = gdf_list[0].crs
    if common_crs is None or any(frame.crs is None for frame in gdf_list):
        raise ValueError("Every layer must define a CRS before merge")

    aligned_layers = [
        frame if frame.crs == common_crs else frame.to_crs(common_crs)
        for frame in gdf_list
    ]
    merged = pd.concat(aligned_layers, ignore_index=True, sort=False)
    return gpd.GeoDataFrame(
        merged,
        geometry=gdf_list[0].geometry.name,
        crs=common_crs,
    )


def spatial_join(
    left_gdf: gpd.GeoDataFrame,
    right_gdf: gpd.GeoDataFrame,
    predicate: str,
) -> gpd.GeoDataFrame:
    """Join two layers using intersects, within, or contains."""
    normalized_predicate = predicate.strip().lower()
    if normalized_predicate not in {"intersects", "within", "contains"}:
        raise ValueError(
            "Spatial join predicate must be intersects, within, or contains"
        )
    if left_gdf.crs is None or right_gdf.crs is None:
        raise ValueError("Both spatial join layers must define a CRS")
    aligned_right = (
        right_gdf
        if left_gdf.crs == right_gdf.crs
        else right_gdf.to_crs(left_gdf.crs)
    )
    return gpd.sjoin(
        left_gdf,
        aligned_right,
        how="inner",
        predicate=normalized_predicate,
    )


def _ring_vertex_count(coordinates) -> int:
    values = list(coordinates)
    if len(values) > 1 and values[0] == values[-1]:
        return len(values) - 1
    return len(values)


def _vertex_count(geometry: BaseGeometry | None) -> int:
    if geometry is None or geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return _ring_vertex_count(geometry.exterior.coords) + sum(
            _ring_vertex_count(ring.coords) for ring in geometry.interiors
        )
    if hasattr(geometry, "geoms"):
        return sum(_vertex_count(part) for part in geometry.geoms)
    if hasattr(geometry, "coords"):
        return len(geometry.coords)
    return 0


def compute_geometry_stats(gdf: gpd.GeoDataFrame) -> dict:
    """Return per-feature and dataset-level geometry measurements."""
    features: list[dict] = []
    total_area = 0.0
    total_perimeter = 0.0
    total_vertices = 0

    for feature_index, geometry in gdf.geometry.items():
        area = float(geometry.area) if geometry is not None else 0.0
        perimeter = float(geometry.length) if geometry is not None else 0.0
        vertex_count = _vertex_count(geometry)
        centroid = (
            {"x": float(geometry.centroid.x), "y": float(geometry.centroid.y)}
            if geometry is not None and not geometry.is_empty
            else None
        )
        native_index = (
            feature_index.item()
            if hasattr(feature_index, "item")
            else feature_index
        )
        features.append(
            {
                "feature_index": native_index,
                "area": area,
                "perimeter": perimeter,
                "centroid": centroid,
                "vertex_count": vertex_count,
            }
        )
        total_area += area
        total_perimeter += perimeter
        total_vertices += vertex_count

    return {
        "feature_count": len(gdf),
        "crs": gdf.crs.to_string() if gdf.crs else None,
        "features": features,
        "total_area": total_area,
        "total_perimeter": total_perimeter,
        "total_vertices": total_vertices,
    }
