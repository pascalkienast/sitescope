"""
Helpers for deriving approximate analysis units from a polygon selection.
"""

from __future__ import annotations

from typing import Iterable

from pyproj import Transformer
from shapely.geometry import Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.validation import explain_validity

from models import AreaUnit, GeoJSONPolygon, SamplePoint

BAVARIA_BBOX = {
    "lat_min": 47.27,
    "lat_max": 50.56,
    "lng_min": 8.97,
    "lng_max": 13.84,
}

GRID_SIZE = 5
DEFAULT_MAX_UNITS = 20

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
_TO_WGS = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
_BAVARIA_POLYGON = box(
    BAVARIA_BBOX["lng_min"],
    BAVARIA_BBOX["lat_min"],
    BAVARIA_BBOX["lng_max"],
    BAVARIA_BBOX["lat_max"],
)


def build_area_units(
    polygon_model: GeoJSONPolygon,
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    grid_size: int = GRID_SIZE,
) -> tuple[list[AreaUnit], list[str]]:
    """Split a polygon selection into ranked approximate analysis units."""
    polygon_wgs = _polygon_from_model(polygon_model)
    warnings: list[str] = [
        "Approximate analysis cells only. Open Bavarian data does not expose exact parcel vectors."
    ]

    if not polygon_wgs.is_valid:
        raise ValueError(f"Invalid polygon geometry: {explain_validity(polygon_wgs)}")
    if polygon_wgs.is_empty or polygon_wgs.area <= 0:
        raise ValueError("Polygon area must be greater than zero.")
    if not polygon_wgs.intersects(_BAVARIA_POLYGON):
        raise ValueError("Polygon is outside Bavaria's supported coverage area.")
    if not _BAVARIA_POLYGON.contains(polygon_wgs):
        warnings.append(
            "Only the part of the polygon inside Bavaria's approximate coverage box is considered."
        )
        polygon_wgs = polygon_wgs.intersection(_BAVARIA_POLYGON)

    polygon_utm = transform(_TO_UTM.transform, polygon_wgs)
    units = _grid_intersections(polygon_utm, max_units=max_units, grid_size=grid_size)

    if len(units) == max_units:
        warnings.append(f"Selection capped at the largest {max_units} analysis cells.")

    return units, warnings


def polygon_intersects_bavaria(polygon_model: GeoJSONPolygon) -> bool:
    """Return whether a polygon intersects the approximate Bavaria bbox."""
    return _polygon_from_model(polygon_model).intersects(_BAVARIA_POLYGON)


def _polygon_from_model(polygon_model: GeoJSONPolygon) -> Polygon:
    return shape(polygon_model.model_dump())


def _grid_intersections(
    polygon_utm: BaseGeometry,
    *,
    max_units: int,
    grid_size: int,
) -> list[AreaUnit]:
    min_x, min_y, max_x, max_y = polygon_utm.bounds
    width = (max_x - min_x) / grid_size
    height = (max_y - min_y) / grid_size

    candidates: list[tuple[float, float, BaseGeometry]] = []

    for col in range(grid_size):
        for row in range(grid_size):
            cell = box(
                min_x + col * width,
                min_y + row * height,
                min_x + (col + 1) * width,
                min_y + (row + 1) * height,
            )
            intersection = polygon_utm.intersection(cell)
            if intersection.is_empty or intersection.area <= 0:
                continue

            polygon_part = _largest_polygon(intersection)
            if polygon_part is None or polygon_part.area <= 0:
                continue

            coverage_ratio = polygon_part.area / cell.area if cell.area else 0
            candidates.append((coverage_ratio, polygon_part.area, polygon_part))

    ranked_units = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)[
        :max_units
    ]

    units: list[AreaUnit] = []
    for index, (_, area_sqm, geometry_utm) in enumerate(ranked_units, start=1):
        geometry_wgs = transform(_TO_WGS.transform, geometry_utm)
        point_wgs = transform(_TO_WGS.transform, geometry_utm.representative_point())
        geometry_mapping = mapping(geometry_wgs)
        units.append(
            AreaUnit(
                id=f"cell-{index:02d}",
                label=f"Analysezelle {index}",
                geometry=GeoJSONPolygon(**geometry_mapping),
                sample_point=SamplePoint(lat=point_wgs.y, lng=point_wgs.x),
                area_sqm=round(area_sqm, 2),
            )
        )

    return units


def _largest_polygon(geometry: BaseGeometry) -> Polygon | None:
    if geometry.geom_type == "Polygon":
        return geometry
    if geometry.geom_type == "MultiPolygon":
        polygons = list(geometry.geoms)
        return max(polygons, key=lambda geom: geom.area, default=None)

    polygons = [
        geom
        for geom in _iter_polygon_parts(geometry.geoms if hasattr(geometry, "geoms") else [])
        if geom.area > 0
    ]
    return max(polygons, key=lambda geom: geom.area, default=None)


def _iter_polygon_parts(geometries: Iterable[BaseGeometry]) -> Iterable[Polygon]:
    for geometry in geometries:
        if geometry.geom_type == "Polygon":
            yield geometry
        elif hasattr(geometry, "geoms"):
            yield from _iter_polygon_parts(geometry.geoms)
