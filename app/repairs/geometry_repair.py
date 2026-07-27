"""Automatic repair helpers for invalid Shapely geometries."""

from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid


def repair_geometry(geom: BaseGeometry | None) -> BaseGeometry | None:
    """Repair an invalid geometry with ``buffer(0)`` and ``make_valid``."""
    if geom is None or geom.is_empty or geom.is_valid:
        return geom

    try:
        buffered = geom.buffer(0)
        if not buffered.is_empty and buffered.is_valid:
            return buffered
    except Exception:
        # GEOS can reject severely damaged coordinate structures; make_valid is
        # the secondary strategy for those cases.
        pass

    try:
        repaired = make_valid(geom)
        if not repaired.is_empty and repaired.is_valid:
            return repaired
    except Exception:
        pass

    return geom
