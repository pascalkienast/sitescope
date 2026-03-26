"""
Generic WFS client for GetFeature requests.

Optional complement to WMS — some services expose richer attribute
data via WFS than GetFeatureInfo. Not all Bayern services have WFS,
so this is used where available.
"""

import logging
from typing import Optional

import httpx
from lxml import etree

from .transforms import make_bbox

logger = logging.getLogger(__name__)


class WFSClient:
    """Async WFS client for GetFeature operations."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        version: str = "2.0.0",
        crs: str = "EPSG:25832",
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.version = version
        self.crs = crs

    async def get_feature_bbox(
        self,
        lat: float,
        lng: float,
        type_names: list[str],
        buffer_m: float = 50.0,
        max_features: int = 50,
    ) -> dict:
        """
        Request features within a BBOX around a WGS84 point.

        Args:
            lat: Latitude (WGS84)
            lng: Longitude (WGS84)
            type_names: WFS feature type names
            buffer_m: Buffer around point in meters
            max_features: Maximum features to return

        Returns:
            Dict with 'features', 'raw_response', 'has_data', 'error'
        """
        bbox = make_bbox(lat, lng, buffer_m)
        bbox_str = ",".join(str(v) for v in bbox) + f",{self.crs}"

        # WFS 2.0 uses TYPENAMES, earlier versions use TYPENAME
        type_key = "TYPENAMES" if self.version >= "2.0.0" else "TYPENAME"
        count_key = "COUNT" if self.version >= "2.0.0" else "MAXFEATURES"

        params = {
            "SERVICE": "WFS",
            "VERSION": self.version,
            "REQUEST": "GetFeature",
            type_key: ",".join(type_names),
            "BBOX": bbox_str,
            "SRSNAME": self.crs,
            count_key: str(max_features),
            "OUTPUTFORMAT": "application/gml+xml; version=3.2",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                raw = response.text
                features = self._parse_wfs_response(raw)

                return {
                    "features": features,
                    "raw_response": raw,
                    "has_data": len(features) > 0,
                    "error": None,
                }

        except httpx.TimeoutException:
            return {
                "features": [],
                "raw_response": "",
                "has_data": False,
                "error": f"WFS timeout after {self.timeout}s",
            }
        except Exception as e:
            logger.exception("WFS error for %s", self.base_url)
            return {
                "features": [],
                "raw_response": "",
                "has_data": False,
                "error": f"WFS error: {type(e).__name__}: {e}",
            }

    def _parse_wfs_response(self, xml_text: str) -> list[dict]:
        """Parse a WFS GetFeature GML response into feature dicts."""
        if not xml_text or not xml_text.strip():
            return []

        features = []
        try:
            root = etree.fromstring(xml_text.encode("utf-8"))
        except etree.XMLSyntaxError:
            logger.warning("Failed to parse WFS GML response")
            return []

        # Find all member elements
        for member in root.iter():
            tag = _local_name(member.tag)
            if tag in ("member", "featureMember", "featureMembers"):
                for feature_elem in member:
                    attrs = {}
                    feature_type = _local_name(feature_elem.tag)
                    for child in feature_elem:
                        child_name = _local_name(child.tag)
                        if child.text and child.text.strip():
                            attrs[child_name] = child.text.strip()
                    if attrs:
                        features.append(
                            {"_layer": feature_type, "_attributes": attrs}
                        )

        return features


def _local_name(tag: str) -> str:
    """Strip namespace from an XML tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag
