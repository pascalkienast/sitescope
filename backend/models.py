"""
Pydantic models for SiteScope requests, responses, and internal data.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


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
    polygon: Optional[list[list[float]]] = Field(
        None,
        description="Optional polygon coordinates as [[lng, lat], [lng, lat], ...] in WGS84"
    )


class PDFRequest(BaseModel):
    """Request body for /report/pdf endpoint."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    polygon: Optional[list[list[float]]] = Field(
        None,
        description="Optional polygon coordinates as [[lng, lat], [lng, lat], ...] in WGS84"
    )


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


class HealthResponse(BaseModel):
    """Response from /health endpoint."""
    status: str = "ok"
    version: str = "0.1.0"
    agents_available: list[str] = Field(default_factory=list)
