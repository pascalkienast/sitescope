"""
📐 Zoning & Land Use Agent (Stretch Goal)

Placeholder for:
- Bau-Nutzungsverordnung / Flächennutzungspläne
- Climate data (Open-Meteo: snow load, heavy rain statistics)
- Land use classification

This agent returns basic climate data from Open-Meteo as a starting point.
Full zoning data requires municipality-specific WMS services.
"""

import logging
from typing import Optional

import httpx

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel

logger = logging.getLogger(__name__)

# Open-Meteo API for climate data (free, no API key)
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


class ZoningAgent(BaseAgent):
    category = AgentCategory.ZONING
    agent_name = "Zoning & Land Use Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []

        # Fetch climate context from Open-Meteo
        climate = await self._get_climate_context(lat, lng)
        if climate:
            findings.append(climate)

        # Placeholder for actual zoning data
        findings.append(
            AgentFinding(
                title="Zoning data not yet integrated",
                description=(
                    "Detailed Bebauungsplan and Flächennutzungsplan data requires "
                    "municipality-specific WMS services. This is a stretch goal — "
                    "check the local Bauamt portal for zoning information."
                ),
                risk_level=RiskLevel.UNKNOWN,
                source_name="Placeholder",
                source_url="https://www.ldbv.bayern.de/",
            )
        )

        return findings

    async def _get_climate_context(
        self, lat: float, lng: float
    ) -> Optional[AgentFinding]:
        """Fetch basic climate statistics from Open-Meteo for context."""
        params = {
            "latitude": lat,
            "longitude": lng,
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "daily": "precipitation_sum,snowfall_sum,temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Berlin",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(OPEN_METEO_URL, params=params)
                response.raise_for_status()
                data = response.json()

            daily = data.get("daily", {})
            precip = daily.get("precipitation_sum", [])
            snow = daily.get("snowfall_sum", [])

            total_precip = sum(p for p in precip if p is not None)
            max_daily_precip = max((p for p in precip if p is not None), default=0)
            total_snow = sum(s for s in snow if s is not None)

            risk = RiskLevel.LOW
            if max_daily_precip > 50:
                risk = RiskLevel.MEDIUM
            if max_daily_precip > 80:
                risk = RiskLevel.HIGH

            return AgentFinding(
                title="Climate Context (2023)",
                description=(
                    f"Annual precipitation: {total_precip:.0f}mm. "
                    f"Max daily rainfall: {max_daily_precip:.1f}mm. "
                    f"Total snowfall: {total_snow:.1f}cm. "
                    f"{'Heavy rain events detected — consider drainage planning.' if max_daily_precip > 40 else 'Normal precipitation pattern.'}"
                ),
                risk_level=risk,
                evidence=f"precip_total={total_precip:.0f}mm, max_daily={max_daily_precip:.1f}mm, snow={total_snow:.1f}cm",
                source_name="Open-Meteo Archive",
                source_url="https://open-meteo.com/",
            )

        except Exception as e:
            logger.warning("Open-Meteo query failed: %s", e)
            return None
