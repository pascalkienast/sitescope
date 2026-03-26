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

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


# =============================================================================
# LLM Configuration — OpenRouter (MiniMax M2.5, free tier)
# =============================================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "minimax/minimax-m2.5"

# =============================================================================
# WMS Service URLs — Bayern LfU & BLfD (all free, no API keys)
# =============================================================================

# 🌊 Flood & Water
WMS_FLOOD = {
    "ueberschwemmungsgebiete": {
        "url": "https://www.lfu.bayern.de/gdi/wms/wasser/ueberschwemmungsgebiete",
        "layers": [
            "hwgf_hq100",
            "hwgf_hqextrem",
        ],
        "description": "Überschwemmungsgebiete (HQ100 / HQextrem)",
    },
    "wassertiefen": {
        "url": "https://www.lfu.bayern.de/gdi/wms/wasser/wassertiefen",
        "layers": ["wt_hq100", "wt_hqextrem"],
        "description": "Wassertiefen bei Hochwasser",
    },
    "oberflaechenabfluss": {
        "url": "https://www.lfu.bayern.de/gdi/wms/wasser/oberflaechenabfluss",
        "layers": [
            "senken_aufstau",
            "fliesswege",
        ],
        "description": "Oberflächenabfluss bei Starkregen",
    },
}

# 🌿 Nature & Environment
WMS_NATURE = {
    "schutzgebiete": {
        "url": "https://www.lfu.bayern.de/gdi/wms/natur/schutzgebiete",
        "layers": [
            "naturschutzgebiet",
            "landschaftsschutzgebiet",
            "fauna_flora_habitat_gebiet",
            "vogelschutzgebiet",
        ],
        "description": "NSG, LSG, Natura 2000 FFH & Vogelschutz",
    },
    "geotope": {
        "url": "https://www.lfu.bayern.de/gdi/wms/geologie/geotope",
        "layers": ["geotoplage"],
        "description": "Geotope",
    },
    "trinkwasserschutz": {
        "url": "https://www.lfu.bayern.de/gdi/wms/wasser/wsg",
        "layers": ["twsg"],
        "description": "Trinkwasserschutzgebiete",
    },
    "bodenfunktion": {
        "url": "https://www.lfu.bayern.de/gdi/wms/boden/bfk25",
        "layers": ["bfk25_nat_ertragsfaehigkeit_gesamt"],
        "description": "Bodenfunktionskarte (natürliche Ertragsfähigkeit)",
    },
}

# 🏛️ Heritage / Monuments
WMS_HERITAGE = {
    "denkmal": {
        "url": "https://geoservices.bayern.de/od/wms/gdi/v1/denkmal",
        "layers": [
            "einzeldenkmalO",
            "bodendenkmalO",
            "bauensembleO",
            "landschaftsdenkmalO",
        ],
        "description": "BLfD Baudenkmäler, Bodendenkmäler, Ensembles",
    },
}

# Default CRS for German WMS services
DEFAULT_CRS = "EPSG:25832"
# Map CRS (WGS84)
MAP_CRS = "EPSG:4326"

# GetFeatureInfo parameters
# NOTE: text/plain returns HTTP 400 on many Bayern LfU ArcGIS WMS services.
# text/html works universally across all tested endpoints.
DEFAULT_INFO_FORMAT = "text/html"
GML_INFO_FORMAT = "application/vnd.ogc.gml"

# Default map tile size for GetMap/GetFeatureInfo
DEFAULT_TILE_SIZE = 256
# Buffer around click point in meters (for BBOX calculation)
DEFAULT_BUFFER_M = 50

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
