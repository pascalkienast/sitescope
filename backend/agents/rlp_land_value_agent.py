"""
💰 RLP Land Values & Property Agent

Queries VBORIS RLP WMS services for:
- Bodenrichtwerte (Standard Land Values)
- Property valuation information
"""

import logging
from typing import Optional

from .base import BaseAgent, calculate_centroid
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_RLP_LAND_VALUES

logger = logging.getLogger(__name__)


class RLPLandValueAgent(BaseAgent):
    category = AgentCategory.INFRASTRUCTURE
    agent_name = "RLP Land Values Agent"

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

        for service_key, service_cfg in WMS_RLP_LAND_VALUES.items():
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
                        "RLP Land Value layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_land_value_layer(layer_name, result, service_cfg)
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        if not findings:
            findings.append(
                AgentFinding(
                    title="Bodenrichtwerte (Land Value) - No specific data at this location",
                    description=(
                        "The query point is within the VBORIS RLP service coverage area, "
                        "but no specific Bodenrichtwert (standard land value) polygon covers this exact location. "
                        "This may indicate a rural area without recent property transactions, or the point falls "
                        "between mapped land value zones. For official land value data, contact the local "
                        "Gutachterausschuss."
                    ),
                    risk_level=RiskLevel.NONE,
                    source_name="VBORIS RLP Bodenrichtwerte",
                    source_url="https://www.vboris.rlp.de/",
                )
            )

        return findings

    def _interpret_land_value_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for RLP land value layers."""
        raw = result.get("raw_response", "")
        features = result.get("features", [])

        evidence = self._extract_evidence(features, raw)

        if "bodenrichtwerte" in layer_name.lower() or "basis" in layer_name.lower():
            return AgentFinding(
                title="Standard Land Value (Bodenrichtwert) Available",
                description=(
                    "Bodenrichtwert (standard land value) data is available for this location. "
                    "Use the evidence data for property valuation reference. "
                    "Note: Actual property value depends on additional factors including use type."
                ),
                risk_level=RiskLevel.NONE,
                evidence=evidence,
                source_url=service_cfg["url"],
                source_name="VBORIS RLP Bodenrichtwerte",
                layer_name=layer_name,
                raw_data=raw[:500],
            )

        if "rlp" in layer_name.lower():
            return AgentFinding(
                title="Regional Land Value Reference",
                description=(
                    "Regional land value reference data is available for this RLP location. "
                    "Check specific zone and value type for property assessment."
                ),
                risk_level=RiskLevel.NONE,
                evidence=evidence,
                source_url=service_cfg["url"],
                source_name="VBORIS RLP Bodenrichtwerte",
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
                    if key.lower() in ["bodenrichtwert", "brw", "wert", "zone", "art"]:
                        parts.append(f"{key}={val}")
            if parts:
                return "; ".join(parts)
            for f in features[:2]:
                attrs = f.get("_attributes", {})
                for key, val in list(attrs.items())[:3]:
                    parts.append(f"{key}={val}")
            return "; ".join(parts) if parts else raw[:200]
        return raw[:200] if raw.strip() else "Land value data detected via WMS GetFeatureInfo"
