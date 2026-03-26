"""
🌊 Flood & Water Agent

Queries Bayern LfU WMS services for:
- Überschwemmungsgebiete (flood zones HQ100 / HQextrem)
- Wassertiefen (water depths at HQ100 / HQextrem)
- Oberflächenabfluss (surface runoff from heavy rain)
"""

import logging

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_FLOOD

logger = logging.getLogger(__name__)


class FloodAgent(BaseAgent):
    category = AgentCategory.FLOOD
    agent_name = "Flood & Water Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        for service_key, service_cfg in WMS_FLOOD.items():
            client = self._create_wms_client(
                service_cfg["url"],
                version=service_cfg.get("version"),
                crs=service_cfg.get("crs"),
            )
            layers = service_cfg["layers"]
            total_layers += len(layers)

            # Query each layer individually for precise attribution
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
                        "Flood layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_flood_layer(
                        layer_name, result, service_cfg
                    )
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        # If no findings, add explicit "no flood risk" finding
        if not findings:
            findings.append(
                AgentFinding(
                    title="No flood zone detected",
                    description="Location is not within any mapped flood zone (HQ100, HQextrem) or surface runoff area.",
                    risk_level=RiskLevel.NONE,
                    source_name="Bayern LfU Hochwasser",
                    source_url="https://www.lfu.bayern.de/wasser/hw_risikomanagement_umsetzung/index.htm",
                )
            )

        return findings

    def _interpret_flood_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for a specific flood layer."""

        raw = result.get("raw_response", "")
        features = result.get("features", [])
        raw_kwargs = self._raw_data_kwargs(result)

        # Layer-specific interpretation
        if "hq100" in layer_name.lower():
            return AgentFinding(
                title="HQ100 Flood Zone",
                description=(
                    "Location is within a statistically 100-year flood zone (HQ100). "
                    "This is a legally designated flood area (§76 WHG). "
                    "Construction restrictions and insurance implications apply."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Überschwemmungsgebiete",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif "hqextrem" in layer_name.lower():
            return AgentFinding(
                title="HQextrem Flood Zone",
                description=(
                    "Location is within an extreme flood zone (HQextrem). "
                    "This represents rare but possible extreme flooding events "
                    "beyond the 100-year return period."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Überschwemmungsgebiete",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif "hqhaeufig" in layer_name.lower():
            return AgentFinding(
                title="Frequent Flood Zone",
                description=(
                    "Location is within a frequent flood area (HQhäufig). "
                    "Seasonal or recurrent flood exposure is likely."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Überschwemmungsgebiete",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif "wt_hq100" in layer_name.lower():
            depth = self._extract_depth(features)
            risk = RiskLevel.HIGH if depth and depth > 0.5 else RiskLevel.MEDIUM
            return AgentFinding(
                title=f"Water Depth HQ100{f': {depth:.1f}m' if depth else ''}",
                description=(
                    f"Expected water depth at HQ100 flood event"
                    f"{f': approximately {depth:.1f} meters' if depth else ' detected'}. "
                    "Relevant for structural planning, basement viability, and damage assessment."
                ),
                risk_level=risk,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Wassertiefen",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif "wt_hqhaeufig" in layer_name.lower():
            depth = self._extract_depth(features)
            return AgentFinding(
                title=f"Water Depth HQhäufig{f': {depth:.1f}m' if depth else ''}",
                description=(
                    f"Expected water depth during frequent flood events"
                    f"{f': approximately {depth:.1f} meters' if depth else ' detected'}."
                ),
                risk_level=RiskLevel.HIGH,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Wassertiefen",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif "wt_hqextrem" in layer_name.lower():
            depth = self._extract_depth(features)
            return AgentFinding(
                title=f"Water Depth HQextrem{f': {depth:.1f}m' if depth else ''}",
                description=(
                    f"Expected water depth at extreme flood event"
                    f"{f': approximately {depth:.1f} meters' if depth else ' detected'}."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Wassertiefen",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif layer_name.lower() == "wt_hwgg_hq100":
            depth = self._extract_depth(features)
            return AgentFinding(
                title=f"Water Depth Flood-Hazard Area{f': {depth:.1f}m' if depth else ''}",
                description=(
                    "Expected water depth inside mapped flood-hazard areas outside legally designated flood zones."
                ),
                risk_level=RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Wassertiefen",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif "starkregen" in layer_name.lower() or layer_name.lower() in ("senken_aufstau", "fliesswege"):
            if layer_name.lower() == "senken_aufstau":
                severity = "terrain depressions & ponding"
                risk = RiskLevel.MEDIUM
            elif layer_name.lower() == "fliesswege":
                severity = "flow paths during heavy rain"
                risk = RiskLevel.MEDIUM
            else:
                severity = "extreme" if "extrem" in layer_name else "rare"
                risk = RiskLevel.HIGH if severity == "extreme" else RiskLevel.MEDIUM
            return AgentFinding(
                title=f"Surface Runoff Risk ({severity})",
                description=(
                    f"Location shows surface runoff risk: {severity}. "
                    "Flash flood potential from pluvial flooding independent of rivers."
                ),
                risk_level=risk,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Oberflächenabfluss",
                layer_name=layer_name,
                **raw_kwargs,
            )

        elif layer_name.lower() in (
            "ueberwachte_lawinenstriche",
            "nicht_ueberwachte_lawinenstriche",
        ):
            monitored = layer_name.lower() == "ueberwachte_lawinenstriche"
            return AgentFinding(
                title="Avalanche Cadastre",
                description=(
                    "Location intersects the Bavarian avalanche cadastre. "
                    f"{'A monitored avalanche track' if monitored else 'An unmonitored avalanche track'} "
                    "is mapped at this location."
                ),
                risk_level=RiskLevel.HIGH if monitored else RiskLevel.MEDIUM,
                evidence=self._extract_evidence(features, raw),
                source_url=service_cfg["url"],
                source_name="Bayern LfU Lawinenkataster",
                layer_name=layer_name,
                **raw_kwargs,
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

    def _extract_depth(self, features: list[dict]) -> float | None:
        """Try to extract a numeric water depth value from features."""
        for f in features:
            attrs = f.get("_attributes", {})
            for key, val in attrs.items():
                key_lower = key.lower()
                if any(w in key_lower for w in ("tiefe", "depth", "wt", "value")):
                    try:
                        return float(val.replace(",", "."))
                    except (ValueError, AttributeError):
                        continue
        return None
