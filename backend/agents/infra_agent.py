"""
⚡ Infrastructure Agent (Stretch Goal)

Placeholder for:
- Grid connectivity analysis
- Elevation / topography (Open Topo Data)
- Distance to major roads / rail

Starts with elevation data from Open Topo Data API (free).
"""

import logging
from typing import Optional

import httpx

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel

logger = logging.getLogger(__name__)

# Open Topo Data API (free, no key required)
OPEN_TOPO_URL = "https://api.opentopodata.org/v1/eudem25m"


class InfraAgent(BaseAgent):
    category = AgentCategory.INFRASTRUCTURE
    agent_name = "Infrastructure Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []

        # Fetch elevation data
        elevation = await self._get_elevation(lat, lng)
        if elevation:
            findings.append(elevation)

        # Placeholder for grid connectivity
        findings.append(
            AgentFinding(
                title="Grid connectivity data not yet integrated",
                description=(
                    "Detailed infrastructure data (power grid, water/sewage connections, "
                    "broadband availability) requires integration with utility providers. "
                    "This is a stretch goal for future development."
                ),
                risk_level=RiskLevel.UNKNOWN,
                source_name="Placeholder",
            )
        )

        return findings

    async def _get_elevation(
        self, lat: float, lng: float
    ) -> Optional[AgentFinding]:
        """Get elevation from Open Topo Data."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    OPEN_TOPO_URL,
                    params={"locations": f"{lat},{lng}"},
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if results:
                elevation_m = results[0].get("elevation")
                if elevation_m is not None:
                    # Basic risk assessment based on elevation
                    risk = RiskLevel.LOW
                    note = "Normal elevation."
                    if elevation_m < 200:
                        risk = RiskLevel.LOW
                        note = "Low-lying area — verify flood plain status."
                    elif elevation_m > 1000:
                        risk = RiskLevel.MEDIUM
                        note = "High elevation — consider snow load and accessibility."

                    return AgentFinding(
                        title=f"Elevation: {elevation_m:.0f}m above sea level",
                        description=(
                            f"Site elevation is approximately {elevation_m:.0f}m. {note} "
                            "Elevation affects drainage, flood risk, snow load requirements, "
                            "and construction logistics."
                        ),
                        risk_level=risk,
                        evidence=f"elevation={elevation_m:.1f}m (EU-DEM 25m resolution)",
                        source_name="Open Topo Data (EU-DEM)",
                        source_url="https://www.opentopodata.org/",
                    )

        except Exception as e:
            logger.warning("Open Topo Data query failed: %s", e)
        return None
