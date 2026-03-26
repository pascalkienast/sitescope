"""
🌿 RLP Nature & Conservation Agent

Queries INSPIRE RLP WMS services for:
- Protected Sites (Natura 2000, FFH, Vogelschutz)
- Conservation areas
"""

import logging
from typing import Optional

from .base import BaseAgent, calculate_centroid
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_RLP_NATURE

logger = logging.getLogger(__name__)


class RLPNatureAgent(BaseAgent):
    category = AgentCategory.NATURE
    agent_name = "RLP Nature & Conservation Agent"

    async def _run_analysis(
        self,
        lat: float,
        lng: float,
        polygon: Optional[list[list[float]]] = None,
    ) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        query_lat, query_lng = lat, lng
        if polygon and len(polygon) >= 3:
            query_lat, query_lng = calculate_centroid(polygon)

        for service_key, service_cfg in WMS_RLP_NATURE.items():
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
                        "RLP Nature layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_nature_layer(layer_name, result, service_cfg)
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        if not findings:
            findings.append(
                AgentFinding(
                    title="No protected nature area detected in queryable RLP services",
                    description=(
                        "Location is not within any queryable protected nature site in RLP. "
                        "Note: The INSPIRE Naturschutz RLP service does not support GetFeatureInfo queries, "
                        "so detailed protected area data cannot be retrieved. Visual overlay available at "
                        "https://inspire.naturschutz.rlp.de/"
                    ),
                    risk_level=RiskLevel.NONE,
                    source_name="RLP Nature Services",
                    source_url="https://inspire.naturschutz.rlp.de/",
                )
            )

        return findings

    def _interpret_nature_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for RLP nature/conservation layers."""
        raw = result.get("raw_response", "")
        features = result.get("features", [])

        if "conservation" in layer_name.lower() or "natura" in layer_name.lower():
            return AgentFinding(
                title="Special Area of Conservation (FFH)",
                description=(
                    "Location is within a Natura 2000 / Special Area of Conservation (SAC/FFH). "
                    "Development activities require strict assessment under EU nature conservation law."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="INSPIRE Schutzgebiete RLP",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "bird" in layer_name.lower() or "vogel" in layer_name.lower():
            return AgentFinding(
                title="Special Protection Area (SPA/Vogelschutzgebiet)",
                description=(
                    "Location is within a Special Protection Area for birds. "
                    "EU Birds Directive applies; development may be significantly restricted."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="INSPIRE Schutzgebiete RLP",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "protected" in layer_name.lower():
            return AgentFinding(
                title="Protected Site",
                description=(
                    "Location intersects with an INSPIRE-mapped protected site in RLP. "
                    "Check specific protection status and applicable regulations."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="INSPIRE Schutzgebiete RLP",
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
        return raw[:200] if raw.strip() else "Protected site detected via WMS GetFeatureInfo"
