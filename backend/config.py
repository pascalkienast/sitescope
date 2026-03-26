"""
SiteScope configuration — API URLs, timeouts, and settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    openrouter_api_key: str = ""

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # WMS/WFS timeouts
    wms_timeout: int = 30
    max_agents_parallel: int = 5

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


# =============================================================================
# LLM Configuration — OpenRouter (MiniMax M2.5, free tier)
# =============================================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "minimax/minimax-m2.5"

# =============================================================================
# WMS defaults — Bayern LfU & BLfD (all free, no API keys)
# =============================================================================

# Default CRS for German WMS services
DEFAULT_CRS = "EPSG:25832"
# Map CRS (WGS84)
MAP_CRS = "EPSG:4326"
# Default WMS version
DEFAULT_WMS_VERSION = "1.3.0"

# GetFeatureInfo parameters
# NOTE: text/plain returns HTTP 400 on many Bayern LfU ArcGIS WMS services.
# text/html works universally across all tested endpoints.
DEFAULT_INFO_FORMAT = "text/html"
GML_INFO_FORMAT = "application/vnd.ogc.gml"

# Default map tile size for GetMap/GetFeatureInfo
DEFAULT_TILE_SIZE = 256
# Buffer around click point in meters (for BBOX calculation)
DEFAULT_BUFFER_M = 50


def _wms_service(
    url: str,
    description: str,
    layers: list[str],
    *,
    version: str = DEFAULT_WMS_VERSION,
    crs: str = DEFAULT_CRS,
    info_format: str = DEFAULT_INFO_FORMAT,
    probe: str = "feature_info",
) -> dict:
    """Create a normalized WMS service configuration entry."""
    return {
        "url": url,
        "layers": layers,
        "description": description,
        "version": version,
        "crs": crs,
        "info_format": info_format,
        "probe": probe,
    }


# =============================================================================
# WMS Service URLs — Bayern sources verified from the audit docs
# =============================================================================

# 🌊 Flood & Water
WMS_FLOOD = {
    "ueberschwemmungsgebiete": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/wasser/ueberschwemmungsgebiete",
        "Überschwemmungsgebiete",
        ["hwgf_hqhaeufig", "hwgf_hq100", "hwgf_hqextrem", "hwgg_hq100"],
    ),
    "wassertiefen": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/wasser/wassertiefen",
        "Wassertiefen bei Hochwasser",
        ["wt_hqhaeufig", "wt_hq100", "wt_hqextrem", "wt_hwgg_hq100"],
    ),
    "oberflaechenabfluss": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/wasser/oberflaechenabfluss",
        "Oberflächenabfluss bei Starkregen",
        ["senken_aufstau", "fliesswege"],
    ),
    "lawinenkataster": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/wasser/lawinenkataster",
        "Lawinenkataster",
        ["ueberwachte_lawinenstriche", "nicht_ueberwachte_lawinenstriche"],
    ),
}

# Monitor-only sources without GetFeatureInfo support.
WMS_MONITORING_ONLY = {
    "hohegrundwasserstaende": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/wasser/hohegrundwasserstaende",
        "Hohe Grundwasserstände",
        ["hwk_hgw"],
        probe="get_map",
    ),
}

# 🌿 Nature & Environment
WMS_NATURE = {
    "schutzgebiete": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/natur/schutzgebiete",
        "NSG, LSG, Natura 2000 FFH & Vogelschutz",
        [
            "naturschutzgebiet",
            "landschaftsschutzgebiet",
            "nationalpark",
            "biosphaerenreservat",
            "fauna_flora_habitat_gebiet",
            "vogelschutzgebiet",
        ],
    ),
    "geotope": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/geologie/geotope",
        "Geotope",
        ["geotoplage"],
    ),
    "wasserschutzgebiete": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/wasser/wsg",
        "Trink- und Heilquellenschutzgebiete",
        ["twsg", "hqsg"],
    ),
    "bodenfunktion": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/boden/bfk25",
        "Bodenfunktionskarte (natürliche Ertragsfähigkeit)",
        ["bfk25_nat_ertragsfaehigkeit_gesamt"],
    ),
    "biotopkartierung": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/natur/biotopkartierung",
        "Biotopkartierung",
        ["bio_abk", "bio_sbk", "bio_fbk"],
    ),
    "oekoflaechenkataster": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/natur/oefk",
        "Ökoflächenkataster",
        ["oefk_ankauf", "oefk_ae", "oefk_flurb", "oefk_oek"],
    ),
}

# 🏛️ Heritage / Monuments
WMS_HERITAGE = {
    "denkmal": _wms_service(
        "https://geoservices.bayern.de/od/wms/gdi/v1/denkmal",
        "BLfD Baudenkmäler, Bodendenkmäler, Ensembles",
        [
            "einzeldenkmalO",
            "bodendenkmalO",
            "bauensembleO",
            "landschaftsdenkmalO",
        ],
        info_format=GML_INFO_FORMAT,
    ),
}

# 📐 Zoning & Land Use
WMS_ZONING = {
    "laermkarten": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/laerm/hauptverkehrsstrassen",
        "Lärmkarten Hauptverkehrsstraßen",
        ["mroadbylden2022", "mroadbyln2022"],
    ),
    "rohstoff_gewinnungsstellen": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/geologie/rohstoff_gewinnungsstellen",
        "Rohstoff-Gewinnungsstellen",
        ["gf_webgis_umriss_aktiv", "gf_webgis_umriss_inaktiv"],
    ),
}

# ⚡ Infrastructure & Ground Conditions
WMS_INFRASTRUCTURE = {
    "georisiken": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/geologie/georisiken",
        "Georisiken",
        [
            "ghk_senkungsgebiete",
            "ghk_dol_erdf",
            "ghk_hang_extrem",
            "ghk_hang",
            "ghk_rutschanf",
            "ghk_tief_rutsch",
            "ghk_sturz_o_wald",
        ],
    ),
    "digk25": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/geologie/digk25",
        "Ingenieurgeologie dIGK25",
        ["baugrund_digk25"],
    ),
    "dgk25": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/geologie/dgk25",
        "Geologie dGK25",
        ["geoleinheit_dgk25", "strukturln_dgk25"],
    ),
    "hk100": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/geologie/hk100",
        "Hydrogeologie dHK100",
        ["hk100_klass", "hk100_deck", "hk100_stockw"],
    ),
    "buek200": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/boden/buek200by",
        "Bodenübersichtskarte BÜK200",
        ["buek200"],
    ),
    "uebk25": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/boden/uebk25",
        "Übersichtsbodenkarte UEBK25",
        ["kartiereinheiten_uebk25"],
    ),
    "geothermie": _wms_service(
        "https://www.lfu.bayern.de/gdi/wms/energieatlas/geothermie",
        "Energie-Atlas Geothermie",
        [
            "gwwp_entzugsleistung_kw_100m",
            "ews_entzugsleistung_kw",
            "ewk_hk_entzugsleistung_wm2",
        ],
    ),
}

WMS_AGENT_SOURCE_GROUPS = (
    ("Flood", WMS_FLOOD),
    ("Nature", WMS_NATURE),
    ("Heritage", WMS_HERITAGE),
    ("Zoning", WMS_ZONING),
    ("Infrastructure", WMS_INFRASTRUCTURE),
)

WMS_DIAGNOSTIC_SOURCE_GROUPS = WMS_AGENT_SOURCE_GROUPS + (
    ("Flood", WMS_MONITORING_ONLY),
)

# Demo locations for the hackathon
DEMO_LOCATIONS = [
    {
        "name": "Isar/Flaucher, München",
        "lat": 48.116,
        "lng": 11.557,
        "expected": ["flood"],
    },
    {
        "name": "Marienplatz, München",
        "lat": 48.137,
        "lng": 11.576,
        "expected": ["heritage"],
    },
    {
        "name": "Englischer Garten",
        "lat": 48.164,
        "lng": 11.605,
        "expected": ["nature", "flood"],
    },
    {
        "name": "Nymphenburger Schloss",
        "lat": 48.158,
        "lng": 11.503,
        "expected": ["heritage", "nature"],
    },
    {
        "name": "Olympiapark",
        "lat": 48.175,
        "lng": 11.552,
        "expected": ["heritage"],
    },
]
