"""
Pydantic models for SiteScope requests, responses, and internal data.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Enums
# =============================================================================


class RiskLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class AgentCategory(str, Enum):
    FLOOD = "flood"
    NATURE = "nature"
    HERITAGE = "heritage"
    ZONING = "zoning"
    INFRASTRUCTURE = "infrastructure"


# =============================================================================
# Request Models
# =============================================================================


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude (WGS84)")
    lng: float = Field(..., ge=-180, le=180, description="Longitude (WGS84)")


class GeoJSONPolygon(BaseModel):
    """Minimal GeoJSON Polygon representation in WGS84."""

    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]

    @model_validator(mode="after")
    def validate_polygon(self) -> "GeoJSONPolygon":
        if not self.coordinates:
            raise ValueError("Polygon must include at least one linear ring.")

        for ring in self.coordinates:
            if len(ring) < 4:
                raise ValueError("Each polygon ring must have at least 4 positions.")
            if ring[0] != ring[-1]:
                raise ValueError("Each polygon ring must be closed.")
            for position in ring:
                if len(position) != 2:
                    raise ValueError("Each polygon position must be [lng, lat].")
                lng, lat = position
                if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                    raise ValueError("Polygon coordinates must be valid WGS84 coordinates.")

        return self


class AreaUnitsRequest(BaseModel):
    """Request body for /api/area/units."""

    polygon: GeoJSONPolygon
    max_units: int = Field(default=20, ge=1, le=20)


class SamplePoint(BaseModel):
    """Representative point in WGS84."""

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class AreaUnit(BaseModel):
    """Approximate analysis unit derived from a polygon selection."""

    id: str
    label: str
    geometry: GeoJSONPolygon
    sample_point: SamplePoint
    area_sqm: float = Field(..., ge=0)


class AreaAnalyzeUnitRequest(BaseModel):
    """Selected unit forwarded to /api/area/analyze."""

    id: str
    label: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class AreaAnalyzeRequest(BaseModel):
    """Request body for /api/area/analyze."""

    units: list[AreaAnalyzeUnitRequest] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_unit_ids(self) -> "AreaAnalyzeRequest":
        unit_ids = [unit.id for unit in self.units]
        if len(set(unit_ids)) != len(unit_ids):
            raise ValueError("Area analysis units must have unique ids.")
        return self


class PDFRequest(BaseModel):
    """Request body for /report/pdf endpoint."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


# =============================================================================
# Agent Data Models
# =============================================================================


class WMSLayerResult(BaseModel):
    """Result from a single WMS layer query."""
    layer_name: str
    service_url: str
    raw_response: str = ""
    has_data: bool = False
    attributes: dict = Field(default_factory=dict)
    error: Optional[str] = None


class RawDataField(BaseModel):
    """One normalized key/value pair from a raw datasource response."""
    key: str
    value: str


class RawDataBlock(BaseModel):
    """A logical feature/layer block for displaying parsed raw data."""
    title: str
    layer_name: Optional[str] = None
    fields: list[RawDataField] = Field(default_factory=list)


class ParsedRawData(BaseModel):
    """Structured raw data for UI, PDF, and prompt rendering."""
    format: str = "key_value"
    source_format: str = "unknown"
    feature_count: int = 0
    blocks: list[RawDataBlock] = Field(default_factory=list)


class AgentFinding(BaseModel):
    """A single finding from an agent."""
    title: str
    description: str
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    evidence: str = ""
    source_url: str = ""
    source_name: str = ""
    layer_name: str = ""
    parsed_raw_data: Optional[ParsedRawData] = None
    original_raw_response_preview: Optional[str] = None
    raw_data: Optional[str] = None


class AgentResult(BaseModel):
    """Complete result from one agent's analysis."""
    category: AgentCategory
    agent_name: str
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    summary: str = ""
    findings: list[AgentFinding] = Field(default_factory=list)
    layers_queried: int = 0
    layers_with_data: int = 0
    errors: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0


# =============================================================================
# Report Models
# =============================================================================


class RiskCategoryReport(BaseModel):
    """Report section for a single risk category."""
    category: AgentCategory
    category_label: str
    emoji: str
    risk_level: RiskLevel
    summary: str
    findings: list[AgentFinding] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)


class RedFlagReport(BaseModel):
    """The complete Red Flag Report."""
    # Location
    lat: float
    lng: float
    address: str = ""

    # Executive summary
    overall_risk_level: RiskLevel
    executive_summary: str
    key_red_flags: list[str] = Field(default_factory=list)

    # Per-category breakdown
    categories: list[RiskCategoryReport] = Field(default_factory=list)

    # Metadata
    generated_at: str = ""
    analysis_duration_ms: int = 0
    agents_run: int = 0
    total_layers_queried: int = 0


# =============================================================================
# API Response Models
# =============================================================================


class AnalyzeResponse(BaseModel):
    """Response from /analyze endpoint."""
    success: bool = True
    report: Optional[RedFlagReport] = None
    agent_results: list[AgentResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AreaUnitsResponse(BaseModel):
    """Response from /api/area/units."""

    mode: Literal["open_data_grid"] = "open_data_grid"
    exact_parcels: bool = False
    warnings: list[str] = Field(default_factory=list)
    units: list[AreaUnit] = Field(default_factory=list)


class AreaUnitResult(BaseModel):
    """Batch analysis result for one selected area unit."""

    id: str
    label: str
    lat: float
    lng: float
    overall_risk_level: RiskLevel
    agent_results: list[AgentResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AreaCategoryRollup(BaseModel):
    """Roll-up of a category across all analyzed area units."""

    category: AgentCategory
    highest_risk: RiskLevel
    affected_units: list[str] = Field(default_factory=list)


class AreaAnalyzeResponse(BaseModel):
    """Response from /api/area/analyze."""

    success: bool = True
    mode: Literal["open_data_grid"] = "open_data_grid"
    exact_parcels: bool = False
    warnings: list[str] = Field(default_factory=list)
    units_analyzed: int = 0
    unit_results: list[AreaUnitResult] = Field(default_factory=list)
    category_rollup: list[AreaCategoryRollup] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Response from /health endpoint."""
    status: str = "ok"
    version: str = "0.1.0"
    agents_available: list[str] = Field(default_factory=list)
