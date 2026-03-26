"""
🌊 RLP Flood & Water Agent

Queries Wasserportal RLP WMS services for:
- Gesetzlich festgesetzte Überschwemmungsgebiete
- Hochwassergefahrenkarte (HQ100, HQextrem)
"""

import logging
from typing import Optional

from .base import BaseAgent, calculate_centroid
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_RLP_FLOOD

logger = logging.getLogger(__name__)


class RLPFloodAgent(BaseAgent):
    category = AgentCategory.FLOOD
    agent_name = "RLP Flood & Water Agent"

    async def _run_analysis(
        self,
        lat: float,
        lng: float,
        polygon: Optional[list[list[float]]] = None,
    ) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        # If we have a polygon, use its centroid for point-based queries
        query_lat, query_lng = lat, lng
        if polygon and len(polygon) >= 3:
            query_lat, query_lng = calculate_centroid(polygon)

        for service_key, service_cfg in WMS_RLP_FLOOD.items():
            client = self._create_wms_client(
                service_cfg["url"],
                version=service_cfg.get("version"),
                crs=service_cfg.get("crs"),
            )
            layers = service_cfg["layers"]
            total_layers += len(layers)

            results = await client.query_all_layers_individually(
                query_lat,
                query_lng,
                layers,
                info_format=service_cfg.get("info_format", DEFAULT_INFO_FORMAT),
            )

            for layer_name, result in results.items():
                if result.get("error"):
                    logger.warning(
                        "RLP Flood layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_flood_layer(
                        layer_name, result, service_cfg
                    )
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        if not findings:
            findings.append(
                AgentFinding(
                    title="No flood zone detected",
                    description="Location is not within any mapped flood zone in RLP.",
                    risk_level=RiskLevel.NONE,
                    source_name="Wasserportal RLP",
                    source_url="https://geodienste-wasser.rlp-umwelt.de/",
                )
            )

        return findings

    def _interpret_flood_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for a specific RLP flood layer."""
        raw = result.get("raw_response", "")
        features = result.get("features", [])

        if "risikogebiete" in layer_name.lower() or "ueberschwemmung" in layer_name.lower():
            return AgentFinding(
                title="Risk Area Outside Designated Flood Zone",
                description=(
                    "Location is within a risk area outside designated flood zones (HQ200/HQextrem). "
                    "Although outside legally designated Überschwemmungsgebiete, this area still "
                    "has flood risk potential during extreme events."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="RLP Gesetzlich festgesetzte Überschwemmungsgebiete",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "hq" in layer_name.lower():
            return AgentFinding(
                title="Flood Risk Area",
                description=(
                    "Location intersects with RLP flood mapping. "
                    "Check specific HQ level and water depths for development implications."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="RLP Hochwassergefahrenkarte",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        return None

    def _extract_evidence(self, features: list[dict], raw: str) -> str:
        """Extract key evidence text from parsed features."""
        if features:
            parts = []
            for f in features[:3]:
                attrs = f.get("_attributes", {})
                for key, val in list(attrs.items())[:5]:
                    parts.append(f"{key}={val}")
            return "; ".join(parts) if parts else raw[:200]
        return raw[:200] if raw.strip() else "Feature detected via WMS GetFeatureInfo"
