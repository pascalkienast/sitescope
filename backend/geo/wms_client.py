"""
Generic WMS client for GetMap and GetFeatureInfo requests.

Works with any OGC WMS 1.1.1 / 1.3.0 service. Designed for
Bayern LfU and BLfD WMS endpoints but fully generic.
"""

import logging
from typing import Optional

import httpx

from .transforms import make_bbox, wgs84_to_utm32
from .parsers import parse_text_feature_info, parse_gml_feature_info
from config import DEFAULT_CRS, DEFAULT_INFO_FORMAT, DEFAULT_TILE_SIZE, DEFAULT_BUFFER_M

logger = logging.getLogger(__name__)


class WMSClient:
    """Async WMS client for GetMap and GetFeatureInfo operations."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        version: str = "1.1.1",
        crs: str = DEFAULT_CRS,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.version = version
        self.crs = crs
        # WMS 1.1.1 uses SRS, 1.3.0 uses CRS
        self._crs_key = "SRS" if version == "1.1.1" else "CRS"

    async def get_feature_info(
        self,
        lat: float,
        lng: float,
        layers: list[str],
        info_format: str = DEFAULT_INFO_FORMAT,
        buffer_m: float = DEFAULT_BUFFER_M,
        tile_size: int = DEFAULT_TILE_SIZE,
        query_layers: Optional[list[str]] = None,
    ) -> dict:
        """
        Send a GetFeatureInfo request and return parsed results.

        Args:
            lat: Latitude (WGS84)
            lng: Longitude (WGS84)
            layers: WMS layer names to query
            info_format: Response format (text/plain, application/vnd.ogc.gml)
            buffer_m: Buffer around point in meters for BBOX
            tile_size: Pixel size of the virtual tile
            query_layers: Layers to query (defaults to all layers)

        Returns:
            Dict with 'features', 'raw_response', 'has_data', and 'error' keys
        """
        bbox = make_bbox(lat, lng, buffer_m)
        query_layers = query_layers or layers

        # Click point is at the center of the tile
        pixel_x = tile_size // 2
        pixel_y = tile_size // 2

        params = {
            "SERVICE": "WMS",
            "VERSION": self.version,
            "REQUEST": "GetFeatureInfo",
            "LAYERS": ",".join(layers),
            "QUERY_LAYERS": ",".join(query_layers),
            self._crs_key: self.crs,
            "BBOX": ",".join(str(v) for v in bbox),
            "WIDTH": str(tile_size),
            "HEIGHT": str(tile_size),
            "INFO_FORMAT": info_format,
            "FEATURE_COUNT": "50",
        }

        # WMS 1.1.1 uses X/Y, 1.3.0 uses I/J
        if self.version == "1.1.1":
            params["X"] = str(pixel_x)
            params["Y"] = str(pixel_y)
        else:
            params["I"] = str(pixel_x)
            params["J"] = str(pixel_y)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                raw = response.text
                logger.debug(
                    "GetFeatureInfo %s layers=%s → %d bytes",
                    self.base_url,
                    layers,
                    len(raw),
                )

                # Parse based on format
                if "gml" in info_format.lower() or "xml" in info_format.lower():
                    features = parse_gml_feature_info(raw)
                else:
                    features = parse_text_feature_info(raw)

                return {
                    "features": features,
                    "raw_response": raw,
                    "has_data": len(features) > 0,
                    "error": None,
                }

        except httpx.TimeoutException:
            logger.warning("Timeout querying %s", self.base_url)
            return {
                "features": [],
                "raw_response": "",
                "has_data": False,
                "error": f"Timeout after {self.timeout}s querying {self.base_url}",
            }
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d from %s", e.response.status_code, self.base_url)
            return {
                "features": [],
                "raw_response": e.response.text[:500] if e.response else "",
                "has_data": False,
                "error": f"HTTP {e.response.status_code} from {self.base_url}",
            }
        except Exception as e:
            logger.exception("Error querying %s", self.base_url)
            return {
                "features": [],
                "raw_response": "",
                "has_data": False,
                "error": f"Error: {type(e).__name__}: {e}",
            }

    async def get_map(
        self,
        lat: float,
        lng: float,
        layers: list[str],
        buffer_m: float = 200.0,
        tile_size: int = 512,
        image_format: str = "image/png",
        transparent: bool = True,
    ) -> Optional[bytes]:
        """
        Get a map tile (PNG) centered on a WGS84 point.

        Useful for generating overlay images for the report.

        Args:
            lat: Latitude (WGS84)
            lng: Longitude (WGS84)
            layers: WMS layer names
            buffer_m: Half-width of the map extent in meters
            tile_size: Output image size in pixels
            image_format: Output format (image/png, image/jpeg)
            transparent: Whether background should be transparent

        Returns:
            Image bytes or None on error
        """
        bbox = make_bbox(lat, lng, buffer_m)

        params = {
            "SERVICE": "WMS",
            "VERSION": self.version,
            "REQUEST": "GetMap",
            "LAYERS": ",".join(layers),
            self._crs_key: self.crs,
            "BBOX": ",".join(str(v) for v in bbox),
            "WIDTH": str(tile_size),
            "HEIGHT": str(tile_size),
            "FORMAT": image_format,
            "TRANSPARENT": str(transparent).upper(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "image" in content_type:
                    return response.content
                else:
                    logger.warning(
                        "GetMap returned non-image: %s (%s)",
                        content_type,
                        response.text[:200],
                    )
                    return None

        except Exception as e:
            logger.exception("GetMap error for %s", self.base_url)
            return None

    async def query_all_layers_individually(
        self,
        lat: float,
        lng: float,
        layers: list[str],
        info_format: str = DEFAULT_INFO_FORMAT,
        buffer_m: float = DEFAULT_BUFFER_M,
    ) -> dict[str, dict]:
        """
        Query each layer individually for more precise results.

        Some WMS services return better data when layers are queried
        one at a time rather than all together.

        Returns:
            Dict mapping layer_name → GetFeatureInfo result
        """
        results = {}
        for layer in layers:
            result = await self.get_feature_info(
                lat=lat,
                lng=lng,
                layers=[layer],
                info_format=info_format,
                buffer_m=buffer_m,
            )
            results[layer] = result
        return results
