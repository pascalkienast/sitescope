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
from config import DEFAULT_INFO_FORMAT, WMS_NATURE

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
    "fauna_flora_habitat_gebiet": {
        "title": "Natura 2000 FFH Habitat",
        "description": (
            "Location is within a Fauna-Flora-Habitat (FFH) area under EU Habitats Directive. "
            "Any project likely to significantly affect the site requires an impact assessment "
            "(FFH-Verträglichkeitsprüfung). EU-level protection."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🦎",
    },
    "vogelschutzgebiet": {
        "title": "Natura 2000 Bird Protection Area (SPA)",
        "description": (
            "Location is within a Special Protection Area (SPA) under EU Birds Directive. "
            "Similar restrictions as FFH areas — projects must not disturb protected bird species."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🐦",
    },
    "geotoplage": {
        "title": "Geotope",
        "description": (
            "Location overlaps with a registered geotope — a geologically significant area. "
            "These are protected under BayNatSchG. Excavation and construction may be restricted."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🪨",
    },
    "twsg": {
        "title": "Drinking Water Protection Zone",
        "description": (
            "Location is within a Trinkwasserschutzgebiet. "
            "Strict regulations apply regarding soil disturbance, chemical storage, "
            "and wastewater handling. Zone I/II: severe restrictions. Zone III: moderate."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "💧",
    },
    "hqsg": {
        "title": "Healing Spring Protection Zone",
        "description": (
            "Location is within a Heilquellenschutzgebiet. "
            "Groundwater interventions and construction measures are subject to strict water-law review."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "💧",
    },
    "bfk25_nat_ertragsfaehigkeit_gesamt": {
        "title": "Soil Function Data (Natural Yield)",
        "description": (
            "Bodenfunktionskarte data available for this location. "
            "Shows natural yield capacity of the soil, relevant for foundation planning "
            "and agricultural land valuation."
        ),
        "risk": RiskLevel.LOW,
        "emoji": "🟤",
    },
    "bio_abk": {
        "title": "Protected Biotope",
        "description": (
            "Location overlaps with the Bavarian biotope register. "
            "Protected biotopes trigger strong conservation constraints under nature protection law."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🌱",
    },
    "bio_sbk": {
        "title": "Protected Urban Biotope",
        "description": (
            "Location overlaps with an urban biotope mapping entry. "
            "Protected habitat structures can materially constrain redevelopment."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🌱",
    },
    "bio_fbk": {
        "title": "Protected Lowland Biotope",
        "description": (
            "Location overlaps with a lowland biotope mapping entry. "
            "Protected biotope status requires ecological compatibility review."
        ),
        "risk": RiskLevel.HIGH,
        "emoji": "🌱",
    },
    "oefk_ankauf": {
        "title": "Ecological Compensation Area",
        "description": (
            "Location overlaps with the Bavarian ecological compensation cadastre. "
            "Compensation areas can restrict development or require offset coordination."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🌾",
    },
    "oefk_ae": {
        "title": "Compensation / Replacement Area",
        "description": (
            "Location is registered as an Ausgleichs- oder Ersatzfläche. "
            "Interventions typically require nature-conservation coordination."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🌾",
    },
    "oefk_flurb": {
        "title": "Land Consolidation Eco Area",
        "description": (
            "Location is part of an ecological area from Flurbereinigung planning. "
            "Land-use changes should be checked against compensation obligations."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🌾",
    },
    "oefk_oek": {
        "title": "Eco Account Area",
        "description": (
            "Location is registered in the ecological compensation account. "
            "Existing offset obligations may limit buildability or require coordination."
        ),
        "risk": RiskLevel.MEDIUM,
        "emoji": "🌾",
    },
}


class NatureAgent(BaseAgent):
    category = AgentCategory.NATURE
    agent_name = "Nature & Environment Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        for service_key, service_cfg in WMS_NATURE.items():
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
            )

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
