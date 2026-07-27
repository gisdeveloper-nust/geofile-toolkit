"""Pydantic response schemas for GeoFile Toolkit."""

from typing import Literal

from pydantic import BaseModel, Field


class ParseResult(BaseModel):
    """Metadata returned after successfully parsing a shapefile."""

    geometry_type: str
    feature_count: int = Field(ge=1)
    crs: str | None = None
    bounding_box: list[float] = Field(min_length=4, max_length=4)
    attribute_fields: dict[str, str]


class GeometryIssue(BaseModel):
    """An issue associated with one GeoDataFrame feature."""

    feature_index: int | str
    issue_type: str
    description: str


class ValidationReport(BaseModel):
    """Summary of non-mutating geometry validation."""

    feature_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    issues: list[GeometryIssue]


class RepairAction(GeometryIssue):
    """Outcome of attempting to repair one invalid feature."""

    status: Literal["fixed", "unfixable"]


class RepairReport(BaseModel):
    """Summary of a batch geometry repair operation."""

    feature_count: int = Field(ge=0)
    repaired_count: int = Field(ge=0)
    unfixable_count: int = Field(ge=0)
    repairs: list[RepairAction]
