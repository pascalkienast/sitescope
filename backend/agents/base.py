"""
Base agent class for SiteScope analysis agents.

Each agent is responsible for one risk category. It queries
relevant WMS/WFS services and returns structured findings.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Optional

from models import AgentResult, AgentFinding, AgentCategory, RiskLevel
from geo.wms_client import WMSClient
from geo.wfs_client import WFSClient
from geo.parsers import (
    build_parsed_raw_data,
    make_original_raw_response_preview,
    parsed_raw_data_to_text,
)
from config import DEFAULT_CRS, DEFAULT_WMS_VERSION

logger = logging.getLogger(__name__)


def calculate_centroid(polygon: list[list[float]]) -> tuple[float, float]:
    """
    Calculate the centroid of a polygon.

    Args:
        polygon: List of [lng, lat] coordinates

    Returns:
        (lat, lng) tuple
    """
    if not polygon:
        return 0.0, 0.0

    lat_sum = sum(coord[1] for coord in polygon)
    lng_sum = sum(coord[0] for coord in polygon)
    n = len(polygon)

    return lat_sum / n, lng_sum / n


class BaseAgent(ABC):
    """Abstract base class for all SiteScope agents."""

    category: AgentCategory
    agent_name: str

    def __init__(self, wms_timeout: int = 30):
        self.wms_timeout = wms_timeout
        self.layers_queried = 0

    async def analyze(
        self,
        lat: float,
        lng: float,
        polygon: Optional[list[list[float]]] = None
    ) -> AgentResult:
        """
        Run the full analysis for a location.

        Handles timing, error catching, and result assembly.
        Subclasses implement _run_analysis().

        Args:
            lat: Latitude
            lng: Longitude
            polygon: Optional polygon coordinates as [[lng, lat], ...]
        """
        start = time.monotonic()
        result = AgentResult(
            category=self.category,
            agent_name=self.agent_name,
        )

        try:
            polygon_str = ""
            if polygon:
                polygon_str = f" (polygon with {len(polygon)} points)"
            logger.debug(
                "Agent %s starting analysis for (%.4f, %.4f)%s",
                self.agent_name, lat, lng, polygon_str
            )
            findings = await self._run_analysis(lat, lng, polygon)
            result.findings = findings
            result.layers_queried = self.layers_queried
            result.layers_with_data = sum(1 for f in findings if f.evidence)
            result.risk_level = self._calculate_overall_risk(findings)
            result.summary = self._build_summary(findings)

            # === DEBUG: Log all findings ===
            logger.debug(
                "Agent %s finished: %d findings, %d with data, risk=%s",
                self.agent_name, len(findings), result.layers_with_data, result.risk_level.value,
            )
            for i, f in enumerate(findings):
                logger.debug(
                    "  Finding %d: [%s] %s — evidence=%s, layer=%s",
                    i + 1, f.risk_level.value, f.title,
                    f.evidence[:200] if f.evidence else "NONE",
                    f.layer_name or "N/A",
                )
        except Exception as e:
            logger.exception("Agent %s failed", self.agent_name)
            result.errors.append(f"{type(e).__name__}: {e}")
            result.risk_level = RiskLevel.UNKNOWN

        result.execution_time_ms = int((time.monotonic() - start) * 1000)
        logger.debug("Agent %s completed in %dms", self.agent_name, result.execution_time_ms)
        return result

    @abstractmethod
    async def _run_analysis(
        self,
        lat: float,
        lng: float,
        polygon: Optional[list[list[float]]] = None,
    ) -> list[AgentFinding]:
        """
        Execute the actual analysis. Subclasses override this.

        Args:
            lat: Latitude
            lng: Longitude
            polygon: Optional polygon coordinates as [[lng, lat], ...]

        Returns:
            A list of AgentFindings from querying relevant services.
        """
        ...

    def _calculate_overall_risk(self, findings: list[AgentFinding]) -> RiskLevel:
        """Derive overall risk from individual findings — highest wins."""
        if not findings:
            return RiskLevel.NONE

        priority = {
            RiskLevel.HIGH: 4,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 2,
            RiskLevel.NONE: 1,
            RiskLevel.UNKNOWN: 0,
        }
        max_risk = max(findings, key=lambda f: priority.get(f.risk_level, 0))
        return max_risk.risk_level

    def _build_summary(self, findings: list[AgentFinding]) -> str:
        """Build a human-readable summary from findings."""
        if not findings:
            return f"No {self.category.value} risks identified at this location."

        active = [f for f in findings if f.risk_level not in (RiskLevel.NONE, RiskLevel.UNKNOWN)]
        if not active:
            return f"No significant {self.category.value} risks found."

        parts = []
        for f in active:
            parts.append(f"[{f.risk_level.value}] {f.title}: {f.description}")
        return " | ".join(parts)

    def _create_wms_client(
        self,
        base_url: str,
        *,
        version: str | None = None,
        crs: str | None = None,
    ) -> WMSClient:
        """Create a WMS client configured for this agent."""
        return WMSClient(
            base_url=base_url,
            timeout=self.wms_timeout,
            version=version or DEFAULT_WMS_VERSION,
            crs=crs or DEFAULT_CRS,
        )

    def _raw_data_kwargs(self, result: dict) -> dict:
        """Build normalized raw-data fields for an AgentFinding."""
        raw_response = result.get("raw_response", "")
        features = result.get("features", [])
        parsed_raw_data = build_parsed_raw_data(features, raw_response)
        return {
            "parsed_raw_data": parsed_raw_data,
            "original_raw_response_preview": make_original_raw_response_preview(
                raw_response
            ),
            # Deprecated compatibility field for older clients.
            "raw_data": parsed_raw_data_to_text(
                parsed_raw_data,
                max_blocks=3,
                max_fields_per_block=10,
            ),
        }

    def _create_wfs_client(
        self,
        base_url: str,
        *,
        version: str = "1.1.0",
    ) -> WFSClient:
        """Create a WFS client configured for polygon queries."""
        return WFSClient(
            base_url=base_url,
            timeout=self.wms_timeout,
            version=version,
        )
