"""
Coordinate transformations between WGS84 (EPSG:4326) and UTM Zone 32N (EPSG:25832).

German geo services typically operate in EPSG:25832 (ETRS89 / UTM Zone 32N).
The frontend map works in WGS84 (lat/lng). This module bridges the two.
"""

from pyproj import Transformer

# Create transformers (thread-safe, reusable)
_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
_to_wgs = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def wgs84_to_utm32(lat: float, lng: float) -> tuple[float, float]:
    """
    Convert WGS84 lat/lng to EPSG:25832 (UTM Zone 32N).

    Args:
        lat: Latitude in WGS84
        lng: Longitude in WGS84

    Returns:
        (easting, northing) in EPSG:25832
    """
    easting, northing = _to_utm.transform(lng, lat)
    return easting, northing


def utm32_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """
    Convert EPSG:25832 (UTM Zone 32N) to WGS84 lat/lng.

    Args:
        easting: Easting in EPSG:25832
        northing: Northing in EPSG:25832

    Returns:
        (lat, lng) in WGS84
    """
    lng, lat = _to_wgs.transform(easting, northing)
    return lat, lng


def make_bbox(
    lat: float, lng: float, buffer_m: float = 50.0
) -> tuple[float, float, float, float]:
    """
    Create a BBOX in EPSG:25832 centered on a WGS84 point.

    The BBOX is a square of `2 * buffer_m` meters around the point.

    Args:
        lat: Latitude in WGS84
        lng: Longitude in WGS84
        buffer_m: Half-width of the BBOX in meters (default: 50m)

    Returns:
        (min_x, min_y, max_x, max_y) in EPSG:25832
    """
    easting, northing = wgs84_to_utm32(lat, lng)
    return (
        easting - buffer_m,
        northing - buffer_m,
        easting + buffer_m,
        northing + buffer_m,
    )


def make_bbox_wgs84(
    lat: float, lng: float, buffer_deg: float = 0.001
) -> tuple[float, float, float, float]:
    """
    Create a BBOX in WGS84 centered on a point.

    Args:
        lat: Latitude
        lng: Longitude
        buffer_deg: Half-width in degrees (default: ~100m)

    Returns:
        (min_lng, min_lat, max_lng, max_lat) in WGS84
    """
    return (
        lng - buffer_deg,
        lat - buffer_deg,
        lng + buffer_deg,
        lat + buffer_deg,
    )
