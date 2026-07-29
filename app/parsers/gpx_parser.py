"""GPX metadata parser."""

from typing import Any

import fiona
import geopandas as gpd

GPX_LAYERS = ("waypoints", "tracks", "routes")


def parse_gpx(filepath: str) -> dict[str, Any]:
    """Read GPX waypoints, tracks, and routes and return layer metadata."""
    available_layers = set(fiona.listlayers(filepath))
    layer_counts = {layer: 0 for layer in GPX_LAYERS}
    geometry_types: set[str] = set()
    attribute_fields: dict[str, str] = {}
    bounds: list[list[float]] = []
    crs: str | None = None

    for layer in GPX_LAYERS:
        if layer not in available_layers:
            continue
        frame = gpd.read_file(filepath, layer=layer, driver="GPX", engine="fiona")
        layer_counts[layer] = len(frame)
        if frame.empty:
            continue
        geometry_types.update(frame.geometry.geom_type.dropna().unique().tolist())
        attribute_fields.update(
            {
                column: str(dtype)
                for column, dtype in frame.drop(
                    columns=frame.geometry.name
                ).dtypes.items()
            }
        )
        if not frame.geometry.dropna().empty:
            bounds.append(frame.total_bounds.tolist())
        if crs is None and frame.crs:
            crs = frame.crs.to_string()

    combined_bounds = (
        [
            min(item[0] for item in bounds),
            min(item[1] for item in bounds),
            max(item[2] for item in bounds),
            max(item[3] for item in bounds),
        ]
        if bounds
        else []
    )
    ordered_types = sorted(geometry_types)
    geometry_type = (
        ordered_types[0]
        if len(ordered_types) == 1
        else f"Mixed ({', '.join(ordered_types)})"
    )

    return {
        "geometry_type": geometry_type,
        "feature_count": sum(layer_counts.values()),
        "crs": crs,
        "bounding_box": combined_bounds,
        "attribute_fields": attribute_fields,
        "layer_counts": layer_counts,
    }
