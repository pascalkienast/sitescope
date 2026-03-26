"""
🌿 Nature & Environment Agent

Queries Bayern LfU WMS services for:
- Schutzgebiete (NSG, LSG, Natura 2000 FFH, Vogelschutz/SPA)
- Geotope (geological features)
- Trinkwasserschutzgebiete (drinking water protection zones)
- Bodenschätzung (soil assessment)
"""

import logging

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel
from config import WMS_NATURE

logger = logging.getLogger(__name__)

# Map layer names to human descriptions and risk assessments
NATURE_LAYER_META = {
    "naturschutzgebiet": {
        "title": "Nature Reserve (NSG)",
        "description": (
            "Location is within a Naturschutzgebiet (NSG). "
            "Strict protection — construction and land use changes are generally prohibited. "
            "Any development requires exceptional permits from the upper nature conservation authority."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🌳",
    },
    "landschaftsschutzgebiet": {
        "title": "Landscape Protection Area (LSG)",
        "description": (
            "Location is within a Landschaftsschutzgebiet (LSG). "
            "Development is restricted but not categorically excluded. "
            "Projects must demonstrate compatibility with landscape character."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🏞️",
    },
    "natura2000_ffh": {
        "title": "Natura 2000 FFH Habitat",
        "description": (
            "Location is within a Fauna-Flora-Habitat (FFH) area under EU Habitats Directive. "
            "Any project likely to significantly affect the site requires an impact assessment "
            "(FFH-Verträglichkeitsprüfung). EU-level protection."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🦎",
    },
    "natura2000_spa": {
        "title": "Natura 2000 Bird Protection Area (SPA)",
        "description": (
            "Location is within a Special Protection Area (SPA) under EU Birds Directive. "
            "Similar restrictions as FFH areas — projects must not disturb protected bird species."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🐦",
    },
    "geotopflaeche": {
        "title": "Geotope (Area)",
        "description": (
            "Location overlaps with a registered geotope — a geologically significant area. "
            "These are protected under BayNatSchG. Excavation and construction may be restricted."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🪨",
    },
    "geotoppunkt": {
        "title": "Geotope (Point Feature)",
        "description": (
            "A registered geotope point feature is near this location. "
            "May require consideration in planning but less restrictive than area geotopes."
        ),
        "risk": RiskLevel.LOW,
        "emoji": "📍",
    },
    "trinkwasserschutzgebiet": {
        "title": "Drinking Water Protection Zone",
        "description": (
            "Location is within a Trinkwasserschutzgebiet. "
            "Strict regulations apply regarding soil disturbance, chemical storage, "
            "and wastewater handling. Zone I/II: severe restrictions. Zone III: moderate."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "💧",
    },
    "bodenschaetzung": {
        "title": "Soil Assessment Data Available",
        "description": (
            "Official Bodenschätzung data is available for this location. "
            "Contains soil quality information relevant for foundation planning "
            "and agricultural land valuation."
        ),
        "risk": RiskLevel.LOW,
        "emoji": "🟤",
    },
}


class NatureAgent(BaseAgent):
    category = AgentCategory.NATURE
    agent_name = "Nature & Environment Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        for service_key, service_cfg in WMS_NATURE.items():
            client = self._create_wms_client(service_cfg["url"])
            layers = service_cfg["layers"]
            total_layers += len(layers)

            results = await client.query_all_layers_individually(lat, lng, layers)

            for layer_name, result in results.items():
                if result.get("error"):
                    logger.warning(
                        "Nature layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_nature_layer(
                        layer_name, result, service_cfg
                    )
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        if not findings:
            findings.append(
                AgentFinding(
                    title="No nature/environment restrictions detected",
                    description=(
                        "Location is not within any mapped nature reserve, "
                        "Natura 2000 area, geotope, or drinking water protection zone."
                    ),
                    risk_level=RiskLevel.NONE,
                    source_name="Bayern LfU Naturschutz",
                    source_url="https://www.lfu.bayern.de/natur/index.htm",
                )
            )

        return findings

    def _interpret_nature_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for a nature/environment layer."""
        raw = result.get("raw_response", "")
        features = result.get("features", [])

        meta = NATURE_LAYER_META.get(layer_name.lower())
        if not meta:
            # Generic finding for unknown layers
            meta = {
                "title": f"Environmental feature: {layer_name}",
                "description": f"Environmental data detected for layer {layer_name}.",
                "risk": RiskLevel.MEDIUM,
            }

        # Extract name/designation from features
        name = self._extract_name(features)
        title = meta["title"]
        if name:
            title = f"{meta['title']}: {name}"

        return AgentFinding(
            title=title,
            description=meta["description"],
            risk_level=meta["risk"],
            evidence=self._extract_evidence(features, raw),
            source_url=service_cfg["url"],
            source_name=f"Bayern LfU – {service_cfg['description']}",
            layer_name=layer_name,
            raw_data=raw[:500],
        )

    def _extract_name(self, features: list[dict]) -> str | None:
        """Try to extract the name of the protected area."""
        name_keys = ["name", "gebiet", "bezeichnung", "schutzgebiet", "gebietsname"]
        for f in features:
            attrs = f.get("_attributes", {})
            for key, val in attrs.items():
                if key.lower() in name_keys:
                    return val
        return None

    def _extract_evidence(self, features: list[dict], raw: str) -> str:
        """Extract key evidence from parsed features."""
        if features:
            parts = []
            for f in features[:3]:
                attrs = f.get("_attributes", {})
                for key, val in list(attrs.items())[:5]:
                    parts.append(f"{key}={val}")
            return "; ".join(parts) if parts else raw[:200]
        return raw[:200] if raw.strip() else "Feature detected via WMS GetFeatureInfo"
