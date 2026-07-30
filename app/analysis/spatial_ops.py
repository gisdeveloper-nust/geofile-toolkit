"""Reusable GeoPandas spatial operations."""

import geopandas as gpd


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
