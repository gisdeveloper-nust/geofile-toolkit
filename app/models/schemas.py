"""Pydantic response schemas for GeoFile Toolkit."""

from pydantic import BaseModel, Field


class ParseResult(BaseModel):
    """Metadata returned after successfully parsing a shapefile."""

    geometry_type: str
    feature_count: int = Field(ge=1)
    crs: str | None = None
    bounding_box: list[float] = Field(min_length=4, max_length=4)
    attribute_fields: dict[str, str]
