"""
🏛️ Heritage / Monuments Agent

Queries BLfD (Bayerisches Landesamt für Denkmalpflege) WMS for:
- Einzeldenkmäler (individual monuments)
- Bodendenkmäler (archaeological sites)
- Bauensembles (architectural ensembles)
- Landschaftsdenkmäler (landscape monuments)
"""

import logging

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_HERITAGE

logger = logging.getLogger(__name__)

HERITAGE_LAYER_META = {
    "einzeldenkmalo": {
        "title": "Listed Building (Einzeldenkmal)",
        "description": (
            "A listed individual monument (Einzeldenkmal) exists at or near this location. "
            "Protected under BayDSchG Art. 6. Demolition, alteration, or construction "
            "affecting the monument's appearance requires permit from Denkmalschutzbehörde."
        ),
        "risk": RiskLevel.HIGH,
    },
    "bodendenkmalo": {
        "title": "Archaeological Site (Bodendenkmal)",
        "description": (
            "An archaeological ground monument (Bodendenkmal) is registered at this location. "
            "Any ground disturbance (excavation, foundation work) requires prior archaeological "
            "survey. Unexpected finds during construction trigger mandatory reporting and work stoppage."
        ),
        "risk": RiskLevel.HIGH,
    },
    "bauensembleo": {
        "title": "Architectural Ensemble (Bauensemble)",
        "description": (
            "Location is within a protected architectural ensemble (Bauensemble). "
            "New construction must harmonize with the ensemble's character. "
            "Façade design, building height, and materials are subject to review."
        ),
        "risk": RiskLevel.MEDIUM,
    },
    "landschaftsdenkmalo": {
        "title": "Landscape Monument (Landschaftsdenkmal)",
        "description": (
            "A protected landscape monument exists at this location. "
            "Development must preserve the historic landscape character."
        ),
        "risk": RiskLevel.MEDIUM,
    },
}


class HeritageAgent(BaseAgent):
    category = AgentCategory.HERITAGE
    agent_name = "Heritage / Monuments Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        for service_key, service_cfg in WMS_HERITAGE.items():
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
                        "Heritage layer %s error: %s", layer_name, result["error"]
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_heritage_layer(
                        layer_name, result, service_cfg
                    )
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        if not findings:
            findings.append(
                AgentFinding(
                    title="No heritage restrictions detected",
                    description=(
                        "No listed monuments, archaeological sites, or protected ensembles "
                        "found at this location in the BLfD register."
                    ),
                    risk_level=RiskLevel.NONE,
                    source_name="BLfD Bayern",
                    source_url="https://www.blfd.bayern.de/",
                )
            )

        return findings

    def _interpret_heritage_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        """Interpret GetFeatureInfo result for a heritage layer."""
        raw = result.get("raw_response", "")
        features = result.get("features", [])
        raw_kwargs = self._raw_data_kwargs(result)

        meta = HERITAGE_LAYER_META.get(layer_name.lower())
        if not meta:
            meta = {
                "title": f"Heritage feature: {layer_name}",
                "description": f"Heritage data detected for layer {layer_name}.",
                "risk": RiskLevel.MEDIUM,
            }

        # Try to extract monument details
        file_number = self._extract_attr(features, ["aktennummer", "denkmalnummer", "nummer"])
        name = self._extract_attr(
            features,
            ["kurzansprache", "tradobjbez", "funktion", "name", "bezeichnung", "beschreibung"],
        )
        address = self._extract_attr(features, ["adresse", "strasse", "ort"])

        title = meta["title"]
        details = []
        if file_number:
            details.append(f"File: {file_number}")
        if name:
            details.append(name)
        if address:
            details.append(f"Address: {address}")

        if details:
            title = f"{meta['title']} — {', '.join(details)}"

        return AgentFinding(
            title=title,
            description=meta["description"],
            risk_level=meta["risk"],
            evidence=self._extract_evidence(features, raw),
            source_url=service_cfg["url"],
            source_name="BLfD Bayern Denkmäler",
            layer_name=layer_name,
            **raw_kwargs,
        )

    def _extract_attr(self, features: list[dict], keys: list[str]) -> str | None:
        """Extract first matching attribute from features."""
        for f in features:
            attrs = f.get("_attributes", {})
            for key, val in attrs.items():
                if key.lower() in keys:
                    return val
        return None

    def _extract_evidence(self, features: list[dict], raw: str) -> str:
        """Extract evidence text from features."""
        if features:
            parts = []
            for f in features[:3]:
                attrs = f.get("_attributes", {})
                for key, val in list(attrs.items())[:5]:
                    parts.append(f"{key}={val}")
            return "; ".join(parts) if parts else raw[:200]
        return raw[:200] if raw.strip() else "Feature detected via WMS GetFeatureInfo"
