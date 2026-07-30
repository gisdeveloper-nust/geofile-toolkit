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


class ConversionRequest(BaseModel):
    """Parameters controlling a geospatial file conversion."""

    source_format: str | None = None
    target_format: str
    target_crs: str | None = None


class ConversionResult(BaseModel):
    """Metadata describing a completed conversion."""

    original_filename: str
    source_format: str
    target_format: str
    target_crs: str | None = None
    output_filename: str


class TopologyIssue(BaseModel):
    """One polygon topology defect."""

    issue_type: Literal["overlap", "gap", "sliver"]
    feature_indices: list[int | str]
    area: float = Field(ge=0)
    severity: Literal["low", "medium", "high"]
    description: str


class TopologyReport(BaseModel):
    """Aggregate polygon topology analysis."""

    feature_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    overlap_count: int = Field(ge=0)
    gap_count: int = Field(ge=0)
    sliver_count: int = Field(ge=0)
    severity_counts: dict[str, int]
    highest_severity: Literal["none", "low", "medium", "high"]
    issues: list[TopologyIssue]
