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
import math
from typing import Optional

import httpx

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_ZONING

logger = logging.getLogger(__name__)

# Open-Meteo API for climate data (free, no API key)
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

ZONING_LAYER_META = {
    "gf_webgis_umriss_aktiv": {
        "title": "Active Raw Material Extraction Area",
        "description": (
            "Location overlaps with an active raw material extraction or quarry footprint. "
            "Noise, traffic, dust, and land-use conflicts should be expected."
        ),
        "risk": RiskLevel.MEDIUM,
    },
    "gf_webgis_umriss_inaktiv": {
        "title": "Former Raw Material Extraction Area",
        "description": (
            "Location overlaps with an inactive extraction footprint. "
            "Historic land disturbance may affect redevelopment or geotechnical assumptions."
        ),
        "risk": RiskLevel.LOW,
    },
}


class ZoningAgent(BaseAgent):
    category = AgentCategory.ZONING
    agent_name = "Zoning & Land Use Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        # Fetch climate context from Open-Meteo
        climate = await self._get_climate_context(lat, lng)
        if climate:
            findings.append(climate)

        for service_key, service_cfg in WMS_ZONING.items():
            client = self._create_wms_client(
                service_cfg["url"],
                version=service_cfg.get("version"),
                crs=service_cfg.get("crs"),
            )
            layers = service_cfg["layers"]
            total_layers += len(layers)

            results = await client.query_all_layers_individually(
                lat,
                lng,
                layers,
                info_format=service_cfg.get("info_format", DEFAULT_INFO_FORMAT),
                buffer_m=self.wms_buffer_m,
            )

            for layer_name, result in results.items():
                if result.get("error"):
                    logger.warning(
                        "Zoning layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_zoning_layer(
                        layer_name, result, service_cfg
                    )
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        # Placeholder for actual zoning data
        findings.append(
            AgentFinding(
                title="Municipal zoning plans not yet integrated",
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

    def _interpret_zoning_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        raw = result.get("raw_response", "")
        features = result.get("features", [])
        raw_kwargs = self._raw_data_kwargs(result)
        layer_key = layer_name.lower()

        if layer_key in ("mroadbylden2022", "mroadbyln2022"):
            level = self._extract_numeric(features, ["pegel", "db"])
            if layer_key == "mroadbylden2022":
                risk = RiskLevel.HIGH if level and level >= 75 else RiskLevel.MEDIUM if level and level >= 65 else RiskLevel.LOW
                period = "day-evening-night"
            else:
                risk = RiskLevel.HIGH if level and level >= 65 else RiskLevel.MEDIUM if level and level >= 55 else RiskLevel.LOW
                period = "night"

            return AgentFinding(
                title=f"Road Noise Exposure ({period}){f': {level:.1f} dB(A)' if level is not None else ''}",
                description=(
                    "Official Bavarian noise mapping for major roads reports noise exposure "
                    f"for the {period} period at this location."
                ),
                risk_level=risk,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Lärmkarten",
                layer_name=layer_name,
                **raw_kwargs,
            )

        meta = ZONING_LAYER_META.get(layer_key)
        if not meta:
            return None

        return AgentFinding(
            title=meta["title"],
            description=meta["description"],
            risk_level=meta["risk"],
            evidence=self._extract_evidence(features, raw),
            source_url=service_cfg["url"],
            source_name=f"Bayern LfU – {service_cfg['description']}",
            layer_name=layer_name,
            **raw_kwargs,
        )

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

    def _extract_numeric(
        self, features: list[dict], key_fragments: list[str]
    ) -> float | None:
        for feature in features:
            for key, value in feature.get("_attributes", {}).items():
                key_lower = key.lower()
                if not any(fragment in key_lower for fragment in key_fragments):
                    continue
                try:
                    numeric = float(str(value).replace(",", "."))
                    if math.isnan(numeric):
                        continue
                    return numeric
                except ValueError:
                    continue
        return None

    def _extract_evidence(self, features: list[dict], raw: str) -> str:
        if features:
            parts = []
            for feature in features[:3]:
                attrs = feature.get("_attributes", {})
                for key, value in list(attrs.items())[:5]:
                    parts.append(f"{key}={value}")
            return "; ".join(parts) if parts else raw[:200]
        return raw[:200] if raw.strip() else "Feature detected via WMS GetFeatureInfo"
