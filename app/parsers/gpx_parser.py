"""GPX metadata parser."""

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import fiona
import geopandas as gpd

GPX_LAYERS = ("waypoints", "tracks", "routes")
SUPPORTED_GPX_VERSIONS = {"1.0", "1.1"}


class GPXParseError(ValueError):
    """Raised when GPX input is malformed or unsupported."""


def _validate_gpx_document(path: Path) -> None:
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise GPXParseError(f"Malformed GPX XML: {exc}") from exc
    except OSError as exc:
        raise GPXParseError(f"Unable to read GPX file: {exc}") from exc

    if root.tag.rsplit("}", 1)[-1] != "gpx":
        raise GPXParseError("Document root must be a GPX element")
    version = root.attrib.get("version")
    if version not in SUPPORTED_GPX_VERSIONS:
        raise GPXParseError(
            f"Unsupported GPX version '{version or 'missing'}'; expected 1.0 or 1.1"
        )

    feature_elements = {"wpt", "trk", "rte"}
    if not any(
        element.tag.rsplit("}", 1)[-1] in feature_elements
        for element in root.iter()
    ):
        raise GPXParseError("GPX contains no waypoints, tracks, or routes")


def parse_gpx(filepath: str) -> dict[str, Any]:
    """Read GPX waypoints, tracks, and routes and return layer metadata."""
    path = Path(filepath)
    if path.suffix.lower() != ".gpx":
        raise GPXParseError("Expected a file with the .gpx extension")
    _validate_gpx_document(path)

    try:
        available_layers = set(fiona.listlayers(path))
    except (fiona.errors.FionaError, OSError, ValueError) as exc:
        raise GPXParseError(f"Unable to inspect GPX layers: {exc}") from exc

    layer_counts = {layer: 0 for layer in GPX_LAYERS}
    geometry_types: set[str] = set()
    attribute_fields: dict[str, str] = {}
    bounds: list[list[float]] = []
    crs: str | None = None

    for layer in GPX_LAYERS:
        if layer not in available_layers:
            continue
        try:
            frame = gpd.read_file(
                path, layer=layer, driver="GPX", engine="fiona"
            )
        except (fiona.errors.FionaError, OSError, ValueError) as exc:
            raise GPXParseError(f"Unable to parse GPX layer '{layer}': {exc}") from exc
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
    if sum(layer_counts.values()) == 0:
        raise GPXParseError("GPX contains no readable waypoints, tracks, or routes")

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
