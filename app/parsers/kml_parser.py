"""KML metadata parser."""

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import fiona
import geopandas as gpd


class KMLParseError(ValueError):
    """Raised when KML input is malformed or unsupported."""


def _enable_kml_driver() -> None:
    """Enable Fiona's GDAL-backed KML driver for read operations."""
    fiona.supported_drivers["KML"] = "rw"


def parse_kml(filepath: str) -> dict[str, Any]:
    """Read a KML file and return geometry and attribute metadata."""
    path = Path(filepath)
    if path.suffix.lower() != ".kml":
        raise KMLParseError("Expected a file with the .kml extension")

    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise KMLParseError(f"Malformed KML XML: {exc}") from exc
    except OSError as exc:
        raise KMLParseError(f"Unable to read KML file: {exc}") from exc

    element_names = {element.tag.rsplit("}", 1)[-1] for element in root.iter()}
    if "Placemark" not in element_names:
        unsupported = element_names.intersection(
            {"GroundOverlay", "PhotoOverlay", "ScreenOverlay"}
        )
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise KMLParseError(
                f"Unsupported KML content ({names}); at least one Placemark is required"
            )
        raise KMLParseError("KML contains no Placemark elements")

    _enable_kml_driver()
    try:
        frame = gpd.read_file(path, driver="KML", engine="fiona")
    except (fiona.errors.FionaError, OSError, ValueError) as exc:
        raise KMLParseError(f"Unable to parse KML: {exc}") from exc

    if frame.empty or frame.geometry.dropna().empty:
        raise KMLParseError("KML contains no supported Placemark geometries")

    geometry_types = sorted(frame.geometry.geom_type.dropna().unique().tolist())
    geometry_type = (
        geometry_types[0]
        if len(geometry_types) == 1
        else (
            f"Mixed ({', '.join(geometry_types)})"
            if geometry_types
            else "Unknown"
        )
    )
    attribute_fields = {
        column: str(dtype)
        for column, dtype in frame.drop(columns=frame.geometry.name).dtypes.items()
    }

    return {
        "geometry_type": geometry_type,
        "feature_count": len(frame),
        "crs": frame.crs.to_string() if frame.crs else None,
        "bounding_box": frame.total_bounds.tolist(),
        "attribute_fields": attribute_fields,
    }
