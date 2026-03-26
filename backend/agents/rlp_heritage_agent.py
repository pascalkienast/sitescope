"""
🏛️ RLP Heritage & Monuments Agent

Queries GDKE RLP WMS services for:
- Landesdenkmalpflege (State Monument Protection)
- Denkmalzonen (Heritage Zones)
- Archaeological monuments (EDM)
"""

import logging
from typing import Optional

from .base import BaseAgent, calculate_centroid
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_RLP_HERITAGE

logger = logging.getLogger(__name__)


class RLPHeritageAgent(BaseAgent):
    category = AgentCategory.HERITAGE
    agent_name = "RLP Heritage & Monuments Agent"

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

        for service_key, service_cfg in WMS_RLP_HERITAGE.items():
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
                        "RLP Heritage layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_heritage_layer(layer_name, result, service_cfg)
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        if not findings:
            findings.append(
                AgentFinding(
                    title="No heritage monument detected",
                    description="Location is not within any mapped heritage zone in RLP.",
                    risk_level=RiskLevel.NONE,
                    source_name="GDKE RLP Denkmalkartierung",
                    source_url="https://www.geoportal.rlp.de/",
                )
            )

        return findings

    def _interpret_heritage_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for RLP heritage layers."""
        raw = result.get("raw_response", "")
        features = result.get("features", [])

        if "denkmalzonen" in layer_name.lower():
            return AgentFinding(
                title="Heritage Zone (Denkmalzone)",
                description=(
                    "Location is within a designated heritage zone (Denkmalzone). "
                    "Any construction or modification requires approval from the monument authority."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="GDKE RLP Denkmalkartierung",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "landesdenkmal" in layer_name.lower() or "pgis" in layer_name.lower():
            return AgentFinding(
                title="State Protected Monument",
                description=(
                    "Location contains or is adjacent to a state-protected monument (Landesdenkmal). "
                    "Development restrictions apply; contact GDKE for permits."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="GDKE RLP Denkmalkartierung",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "edm_flaechen" in layer_name.lower() or "edm_linien" in layer_name.lower():
            return AgentFinding(
                title="Archaeological Monument (EDM)",
                description=(
                    "Location intersects with an archaeological monument in the EDM (Elektronische Denkmaltopographie) system. "
                    "Ground-disturbing activities require archaeological investigation."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="GDKE RLP Denkmalkartierung",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "edm_punkte" in layer_name.lower():
            return AgentFinding(
                title="Archaeological Point Feature (EDM)",
                description=(
                    "Location is near a documented archaeological point feature. "
                    "Verify exact extent and potential subsurface presence before development."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="GDKE RLP Denkmalkartierung",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "bga" in layer_name.lower():
            return AgentFinding(
                title="Historic Garden Area",
                description=(
                    "Location is within or adjacent to a historic garden area (Historische Gartenanlage). "
                    "Special protection applies under landscape conservation law."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="GDKE RLP Denkmalkartierung",
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
        return raw[:200] if raw.strip() else "Heritage feature detected via WMS GetFeatureInfo"
