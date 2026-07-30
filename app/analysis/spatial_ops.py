"""Reusable GeoPandas spatial operations."""

import geopandas as gpd
import pandas as pd


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
