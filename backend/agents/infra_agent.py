"""
⚡ Infrastructure Agent (Stretch Goal)

Placeholder for:
- Grid connectivity analysis
- Elevation / topography (Open Topo Data)
- Distance to major roads / rail

Starts with elevation data from Open Topo Data API (free).
"""

import logging
from typing import Optional

import httpx

from .base import BaseAgent
from models import AgentFinding, AgentCategory, RiskLevel
from config import DEFAULT_INFO_FORMAT, WMS_INFRASTRUCTURE

logger = logging.getLogger(__name__)

# Open Topo Data API (free, no key required)
OPEN_TOPO_URL = "https://api.opentopodata.org/v1/eudem25m"

INFRA_LAYER_META = {
    "ghk_senkungsgebiete": {
        "title": "Subsidence Risk Area",
        "description": (
            "Location intersects mapped subsidence-prone terrain in the Bavarian georisk dataset."
        ),
        "risk": RiskLevel.HIGH,
    },
    "ghk_dol_erdf": {
        "title": "Sinkhole / Collapse Risk",
        "description": (
            "Location intersects a mapped sinkhole or collapse-prone area. "
            "Detailed geotechnical review is required before excavation."
        ),
        "risk": RiskLevel.HIGH,
    },
    "ghk_hang_extrem": {
        "title": "Extreme Slope Failure Hazard",
        "description": (
            "Location intersects the extreme scenario for shallow slope instability."
        ),
        "risk": RiskLevel.HIGH,
    },
    "ghk_hang": {
        "title": "Slope Failure Hazard",
        "description": (
            "Location intersects a mapped shallow slope instability area."
        ),
        "risk": RiskLevel.MEDIUM,
    },
    "ghk_rutschanf": {
        "title": "Landslide Susceptibility",
        "description": (
            "Location is within a mapped landslide-susceptible area."
        ),
        "risk": RiskLevel.MEDIUM,
    },
    "ghk_tief_rutsch": {
        "title": "Deep-Seated Landslide Hazard",
        "description": (
            "Location intersects a mapped deep-seated landslide area."
        ),
        "risk": RiskLevel.HIGH,
    },
    "ghk_sturz_o_wald": {
        "title": "Rockfall / Blockfall Hazard",
        "description": (
            "Location intersects a mapped rockfall or blockfall hazard zone."
        ),
        "risk": RiskLevel.HIGH,
    },
    "baugrund_digk25": {
        "title": "Engineering Geology Data Available",
        "description": (
            "The dIGK25 engineering geology map provides site-specific ground condition context "
            "for foundation planning."
        ),
        "risk": RiskLevel.LOW,
    },
    "geoleinheit_dgk25": {
        "title": "Detailed Geological Unit Available",
        "description": (
            "The dGK25 geological map provides detailed stratigraphic information for this location."
        ),
        "risk": RiskLevel.LOW,
    },
    "strukturln_dgk25": {
        "title": "Geological Structural Lineament",
        "description": (
            "A geological structural element is mapped at this location."
        ),
        "risk": RiskLevel.MEDIUM,
    },
    "hk100_klass": {
        "title": "Hydrogeological Classification",
        "description": (
            "The dHK100 hydrogeology dataset reports groundwater-relevant subsurface conditions."
        ),
        "risk": RiskLevel.LOW,
    },
    "hk100_deck": {
        "title": "Hydrogeological Cover Layer",
        "description": (
            "Cover-layer information is available for this location in the dHK100 dataset."
        ),
        "risk": RiskLevel.LOW,
    },
    "hk100_stockw": {
        "title": "Groundwater Storey Data",
        "description": (
            "Groundwater storey information is mapped at this location."
        ),
        "risk": RiskLevel.LOW,
    },
    "buek200": {
        "title": "Regional Soil Overview",
        "description": (
            "Regional soil overview data is available from the Bavarian BÜK200 map."
        ),
        "risk": RiskLevel.LOW,
    },
    "kartiereinheiten_uebk25": {
        "title": "Detailed Soil Mapping Unit",
        "description": (
            "Detailed soil mapping information is available from the UEBK25 dataset."
        ),
        "risk": RiskLevel.LOW,
    },
    "gwwp_entzugsleistung_kw_100m": {
        "title": "Groundwater Heat Pump Potential",
        "description": (
            "The Bavarian Energy Atlas provides groundwater heat pump potential at this location."
        ),
        "risk": RiskLevel.LOW,
    },
    "ews_entzugsleistung_kw": {
        "title": "Borehole Geothermal Potential",
        "description": (
            "The Bavarian Energy Atlas provides geothermal borehole potential at this location."
        ),
        "risk": RiskLevel.LOW,
    },
    "ewk_hk_entzugsleistung_wm2": {
        "title": "Horizontal Collector Potential",
        "description": (
            "The Bavarian Energy Atlas provides horizontal ground collector potential at this location."
        ),
        "risk": RiskLevel.LOW,
    },
}


class InfraAgent(BaseAgent):
    category = AgentCategory.INFRASTRUCTURE
    agent_name = "Infrastructure Agent"

    async def _run_analysis(self, lat: float, lng: float) -> list[AgentFinding]:
        findings = []
        total_layers = 0

        # Fetch elevation data
        elevation = await self._get_elevation(lat, lng)
        if elevation:
            findings.append(elevation)

        for service_key, service_cfg in WMS_INFRASTRUCTURE.items():
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
                        "Infrastructure layer %s error: %s",
                        layer_name,
                        result["error"],
                    )
                    continue

                if result["has_data"]:
                    finding = self._interpret_infra_layer(
                        layer_name, result, service_cfg
                    )
                    if finding:
                        findings.append(finding)

        self.layers_queried = total_layers

        # Placeholder for grid connectivity
        findings.append(
            AgentFinding(
                title="Utility connectivity data not yet integrated",
                description=(
                    "Detailed infrastructure data (power grid, water/sewage connections, "
                    "broadband availability) requires integration with utility providers. "
                    "This is a stretch goal for future development."
                ),
                risk_level=RiskLevel.UNKNOWN,
                source_name="Placeholder",
            )
        )

        return findings

    def _interpret_infra_layer(
        self, layer_name: str, result: dict, service_cfg: dict
    ) -> AgentFinding | None:
        raw = result.get("raw_response", "")
        features = result.get("features", [])
        raw_kwargs = self._raw_data_kwargs(result)
        meta = INFRA_LAYER_META.get(layer_name.lower())
        if not meta:
            return None

        title = meta["title"]
        summary_attr = self._extract_attr(
            features,
            [
                "Baugrundtyp",
                "Geologische Einheit",
                "Einheit",
                "Kurz-Legende",
                "Boden",
                "Hydrogeologische Eigenschaften",
            ],
        )
        if summary_attr:
            title = f"{title}: {summary_attr}"

        return AgentFinding(
            title=title,
            description=meta["description"],
            risk_level=meta["risk"],
            evidence=self._extract_evidence(features, raw),
            source_url=service_cfg["url"],
            source_name=f"Bayern LfU – {service_cfg['description']}",
            layer_name=layer_name,
            **raw_kwargs,
        )

    async def _get_elevation(
        self, lat: float, lng: float
    ) -> Optional[AgentFinding]:
        """Get elevation from Open Topo Data."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    OPEN_TOPO_URL,
                    params={"locations": f"{lat},{lng}"},
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if results:
                elevation_m = results[0].get("elevation")
                if elevation_m is not None:
                    # Basic risk assessment based on elevation
                    risk = RiskLevel.LOW
                    note = "Normal elevation."
                    if elevation_m < 200:
                        risk = RiskLevel.LOW
                        note = "Low-lying area — verify flood plain status."
                    elif elevation_m > 1000:
                        risk = RiskLevel.MEDIUM
                        note = "High elevation — consider snow load and accessibility."

                    return AgentFinding(
                        title=f"Elevation: {elevation_m:.0f}m above sea level",
                        description=(
                            f"Site elevation is approximately {elevation_m:.0f}m. {note} "
                            "Elevation affects drainage, flood risk, snow load requirements, "
                            "and construction logistics."
                        ),
                        risk_level=risk,
                        evidence=f"elevation={elevation_m:.1f}m (EU-DEM 25m resolution)",
                        source_name="Open Topo Data (EU-DEM)",
                        source_url="https://www.opentopodata.org/",
                    )

        except Exception as e:
            logger.warning("Open Topo Data query failed: %s", e)
        return None

    def _extract_attr(self, features: list[dict], keys: list[str]) -> str | None:
        lower_keys = {key.lower() for key in keys}
        for feature in features:
            for key, value in feature.get("_attributes", {}).items():
                if key.lower() in lower_keys:
                    return str(value)
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
