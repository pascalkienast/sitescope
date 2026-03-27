"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Feature, FeatureCollection, Polygon } from "geojson";
import type {
  AnalysisMode,
  AreaAnalyzeResponse,
  AreaUnit,
  DemoLocation,
  LatLng,
} from "@/lib/types";

interface MapProps {
  mode: AnalysisMode;
  onPointClick: (lat: number, lng: number) => void;
  selectedCoords: LatLng | null;
  demoLocations: DemoLocation[];
  showDemoMarkers: boolean;
  areaVertices: LatLng[];
  areaClosed: boolean;
  areaUnits: AreaUnit[];
  selectedAreaUnitIds: string[];
  areaResult: AreaAnalyzeResponse | null;
  activeAreaUnitId: string | null;
  onAreaVertexAdd: (lat: number, lng: number) => void;
  onAreaComplete: (lat: number, lng: number) => void;
  onAreaUnitClick: (unitId: string) => void;
  showParcelOverlay: boolean;
}

const DEFAULT_CENTER: [number, number] = [11.576, 48.137];
const DEFAULT_ZOOM = 12;
const PARCEL_BASEMAP_TILES = [
  // The official WMTS is stable and switches to the ALKIS parcel map
  // in the highest zoom levels, unlike the flaky public WMS variant.
  "https://wmtsod1.bayernwolke.de/wmts/by_amtl_karte/smerc/{z}/{x}/{y}",
  "https://wmtsod2.bayernwolke.de/wmts/by_amtl_karte/smerc/{z}/{x}/{y}",
  "https://wmtsod3.bayernwolke.de/wmts/by_amtl_karte/smerc/{z}/{x}/{y}",
];

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    },
  },
  layers: [
    {
      id: "osm-tiles",
      type: "raster",
      source: "osm",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

export function Map(props: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const demoMarkersRef = useRef<maplibregl.Marker[]>([]);
  const mapReadyRef = useRef(false);
  const latestRef = useRef(props);
  latestRef.current = props;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
      }),
      "top-right"
    );

    const handleLoad = () => {
      mapReadyRef.current = true;
      ensureMapLayers(map);
      syncDraftSource(
        map,
        latestRef.current.mode === "area" ? latestRef.current.areaVertices : [],
        latestRef.current.mode === "area" && latestRef.current.areaClosed
      );
      syncUnitsSource(
        map,
        latestRef.current.mode === "area" ? latestRef.current.areaUnits : [],
        latestRef.current.mode === "area" ? latestRef.current.selectedAreaUnitIds : [],
        latestRef.current.mode === "area" ? latestRef.current.areaResult : null,
        latestRef.current.mode === "area" ? latestRef.current.activeAreaUnitId : null
      );
      syncParcelOverlay(map, latestRef.current.mode, latestRef.current.showParcelOverlay);
    };

    const handleClick = (event: maplibregl.MapMouseEvent) => {
      const current = latestRef.current;
      if (current.mode === "point") {
        const { lat, lng } = event.lngLat;
        current.onPointClick(lat, lng);
        return;
      }

      const clickedUnitId = findUnitIdAtPoint(map, event.point);
      if (clickedUnitId) {
        current.onAreaUnitClick(clickedUnitId);
        return;
      }

      if (current.areaClosed) {
        return;
      }

      const clickedDraftVertexIndex = findDraftVertexIndexAtPoint(map, event.point);
      if (clickedDraftVertexIndex === 0 && current.areaVertices.length >= 3) {
        current.onAreaComplete(
          current.areaVertices[0].lat,
          current.areaVertices[0].lng
        );
        return;
      }

      if (clickedDraftVertexIndex !== null) {
        return;
      }

      const clickDetail = (event.originalEvent as MouseEvent | undefined)?.detail ?? 1;
      if (clickDetail > 1) {
        return;
      }

      current.onAreaVertexAdd(event.lngLat.lat, event.lngLat.lng);
    };

    const handleDoubleClick = (event: maplibregl.MapMouseEvent) => {
      const current = latestRef.current;
      if (current.mode !== "area" || current.areaClosed || current.areaVertices.length < 2) {
        return;
      }

      event.preventDefault();
      current.onAreaComplete(event.lngLat.lat, event.lngLat.lng);
    };

    const handleMouseMove = (event: maplibregl.MapMouseEvent) => {
      const current = latestRef.current;
      const unitId =
        current.mode === "area" ? findUnitIdAtPoint(map, event.point) : null;
      const draftVertexIndex =
        current.mode === "area" && !current.areaClosed
          ? findDraftVertexIndexAtPoint(map, event.point)
          : null;

      if (unitId) {
        map.getCanvas().style.cursor = "pointer";
        return;
      }

      if (draftVertexIndex === 0 && current.areaVertices.length >= 3) {
        map.getCanvas().style.cursor = "pointer";
        return;
      }

      if (current.mode === "area" && !current.areaClosed) {
        map.getCanvas().style.cursor = "crosshair";
        return;
      }

      map.getCanvas().style.cursor = current.mode === "point" ? "crosshair" : "default";
    };

    map.on("load", handleLoad);
    map.on("click", handleClick);
    map.on("dblclick", handleDoubleClick);
    map.on("mousemove", handleMouseMove);

    mapRef.current = map;

    return () => {
      demoMarkersRef.current.forEach((marker) => marker.remove());
      demoMarkersRef.current = [];
      markerRef.current?.remove();
      markerRef.current = null;
      mapReadyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;

    if (props.mode === "area") {
      map.doubleClickZoom.disable();
    } else {
      map.doubleClickZoom.enable();
    }

    syncDraftSource(map, props.mode === "area" ? props.areaVertices : [], props.mode === "area" && props.areaClosed);
    syncUnitsSource(
      map,
      props.mode === "area" ? props.areaUnits : [],
      props.mode === "area" ? props.selectedAreaUnitIds : [],
      props.mode === "area" ? props.areaResult : null,
      props.mode === "area" ? props.activeAreaUnitId : null
    );
    syncParcelOverlay(map, props.mode, props.showParcelOverlay);
  }, [
    props.mode,
    props.showParcelOverlay,
    props.areaVertices,
    props.areaClosed,
    props.areaUnits,
    props.selectedAreaUnitIds,
    props.areaResult,
    props.activeAreaUnitId,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    syncDraftSource(
      map,
      props.mode === "area" ? props.areaVertices : [],
      props.mode === "area" && props.areaClosed
    );
  }, [props.areaVertices, props.areaClosed, props.mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    syncUnitsSource(
      map,
      props.mode === "area" ? props.areaUnits : [],
      props.mode === "area" ? props.selectedAreaUnitIds : [],
      props.mode === "area" ? props.areaResult : null,
      props.mode === "area" ? props.activeAreaUnitId : null
    );
  }, [
    props.areaUnits,
    props.selectedAreaUnitIds,
    props.areaResult,
    props.activeAreaUnitId,
    props.mode,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (markerRef.current) {
      markerRef.current.remove();
      markerRef.current = null;
    }

    if (props.mode !== "point" || !props.selectedCoords) {
      return;
    }

    const el = document.createElement("div");
    el.innerHTML = `
      <div style="
        width: 24px; height: 24px;
        background: #3B82F6;
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 8px rgba(59,130,246,0.5);
        cursor: pointer;
      "></div>
    `;

    const marker = new maplibregl.Marker({ element: el })
      .setLngLat([props.selectedCoords.lng, props.selectedCoords.lat])
      .setPopup(
        new maplibregl.Popup({ offset: 12 }).setHTML(
          `<strong>Analyzing…</strong><br/>${props.selectedCoords.lat.toFixed(4)}, ${props.selectedCoords.lng.toFixed(4)}`
        )
      )
      .addTo(map);

    markerRef.current = marker;

    map.flyTo({
      center: [props.selectedCoords.lng, props.selectedCoords.lat],
      zoom: Math.max(map.getZoom(), 14),
      duration: 800,
    });
  }, [props.mode, props.selectedCoords]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    demoMarkersRef.current.forEach((marker) => marker.remove());
    demoMarkersRef.current = [];

    if (!props.showDemoMarkers || props.mode !== "point" || !props.demoLocations.length) {
      return;
    }

    const markers = props.demoLocations.map((location) => {
      const el = document.createElement("div");
      el.innerHTML = `
        <div style="
          width: 12px; height: 12px;
          background: #6366F1;
          border: 2px solid white;
          border-radius: 50%;
          box-shadow: 0 1px 4px rgba(0,0,0,0.3);
          cursor: pointer;
          opacity: 0.7;
          transition: opacity 0.2s;
        " title="${location.name}"></div>
      `;

      el.addEventListener("mouseenter", () => {
        const target = el.firstElementChild as HTMLElement | null;
        if (target) {
          target.style.opacity = "1";
          target.style.transform = "scale(1.3)";
        }
      });
      el.addEventListener("mouseleave", () => {
        const target = el.firstElementChild as HTMLElement | null;
        if (target) {
          target.style.opacity = "0.7";
          target.style.transform = "scale(1)";
        }
      });
      el.addEventListener("click", (domEvent) => {
        domEvent.stopPropagation();
        latestRef.current.onPointClick(location.lat, location.lng);
      });

      return new maplibregl.Marker({ element: el })
        .setLngLat([location.lng, location.lat])
        .addTo(map);
    });

    demoMarkersRef.current = markers;

    return () => {
      markers.forEach((marker) => marker.remove());
    };
  }, [props.demoLocations, props.mode, props.showDemoMarkers]);

  useEffect(() => {
    const map = mapRef.current;
    const polygon = buildPolygon(props.areaVertices, props.areaClosed);
    if (!map || !polygon || props.mode !== "area") return;

    const ring = polygon.coordinates[0];
    const bounds = ring.reduce(
      (acc, [lng, lat]) => acc.extend([lng, lat]),
      new maplibregl.LngLatBounds([ring[0][0], ring[0][1]], [ring[0][0], ring[0][1]])
    );

    map.fitBounds(bounds, {
      padding: 60,
      duration: 600,
      maxZoom: 15,
    });
  }, [props.areaVertices, props.areaClosed, props.mode]);

  return <div ref={containerRef} className="w-full h-full" />;
}

function ensureMapLayers(map: maplibregl.Map) {
  if (!map.getSource("parcel-overlay")) {
    map.addSource("parcel-overlay", {
      type: "raster",
      tiles: PARCEL_BASEMAP_TILES,
      tileSize: 256,
    });
  }

  if (!map.getLayer("parcel-overlay")) {
    map.addLayer({
      id: "parcel-overlay",
      type: "raster",
      source: "parcel-overlay",
      layout: { visibility: "none" },
      paint: { "raster-opacity": 1 },
    });
  }

  if (!map.getSource("area-draft")) {
    map.addSource("area-draft", {
      type: "geojson",
      data: emptyFeatureCollection(),
    });
  }

  if (!map.getLayer("area-draft-fill")) {
    map.addLayer({
      id: "area-draft-fill",
      type: "fill",
      source: "area-draft",
      filter: ["==", ["get", "kind"], "polygon"],
      paint: {
        "fill-color": "#2563EB",
        "fill-opacity": 0.14,
      },
    });
  }

  if (!map.getLayer("area-draft-line")) {
    map.addLayer({
      id: "area-draft-line",
      type: "line",
      source: "area-draft",
      filter: ["==", ["get", "kind"], "line"],
      paint: {
        "line-color": "#1D4ED8",
        "line-width": 3,
        "line-dasharray": [2, 1],
      },
    });
  }

  if (!map.getLayer("area-draft-vertices")) {
    map.addLayer({
      id: "area-draft-vertices",
      type: "circle",
      source: "area-draft",
      filter: ["==", ["get", "kind"], "vertex"],
      paint: {
        "circle-radius": [
          "case",
          ["==", ["get", "isFirst"], true],
          7,
          5,
        ],
        "circle-color": [
          "case",
          ["==", ["get", "isFirst"], true],
          "#F59E0B",
          "#1D4ED8",
        ],
        "circle-stroke-width": 2,
        "circle-stroke-color": "#FFFFFF",
      },
    });
  }

  if (!map.getSource("area-units")) {
    map.addSource("area-units", {
      type: "geojson",
      data: emptyFeatureCollection(),
    });
  }

  if (!map.getLayer("area-units-fill")) {
    map.addLayer({
      id: "area-units-fill",
      type: "fill",
      source: "area-units",
      paint: {
        "fill-color": [
          "case",
          ["==", ["get", "status"], "analyzed"],
          [
            "match",
            ["get", "risk"],
            "HIGH",
            "#DC2626",
            "MEDIUM",
            "#D97706",
            "LOW",
            "#059669",
            "NONE",
            "#6B7280",
            "#9CA3AF",
          ],
          ["==", ["get", "selected"], true],
          "#2563EB",
          "#94A3B8",
        ],
        "fill-opacity": [
          "case",
          ["==", ["get", "active"], true],
          0.36,
          ["==", ["get", "status"], "analyzed"],
          0.24,
          ["==", ["get", "selected"], true],
          0.18,
          0.08,
        ],
      },
    });
  }

  if (!map.getLayer("area-units-line")) {
    map.addLayer({
      id: "area-units-line",
      type: "line",
      source: "area-units",
      paint: {
        "line-color": [
          "case",
          ["==", ["get", "status"], "analyzed"],
          [
            "match",
            ["get", "risk"],
            "HIGH",
            "#B91C1C",
            "MEDIUM",
            "#B45309",
            "LOW",
            "#047857",
            "NONE",
            "#6B7280",
            "#64748B",
          ],
          ["==", ["get", "selected"], true],
          "#1D4ED8",
          "#64748B",
        ],
        "line-width": [
          "case",
          ["==", ["get", "active"], true],
          3.5,
          ["==", ["get", "selected"], true],
          2.5,
          1.5,
        ],
      },
    });
  }
}

function syncParcelOverlay(
  map: maplibregl.Map,
  mode: AnalysisMode,
  showParcelOverlay: boolean
) {
  if (!map.getLayer("parcel-overlay") || !map.getLayer("osm-tiles")) return;

  const showOfficialBasemap = mode === "area" && showParcelOverlay;
  map.setLayoutProperty(
    "parcel-overlay",
    "visibility",
    showOfficialBasemap ? "visible" : "none"
  );
  map.setLayoutProperty(
    "osm-tiles",
    "visibility",
    showOfficialBasemap ? "none" : "visible"
  );
}

function syncDraftSource(
  map: maplibregl.Map,
  vertices: LatLng[],
  areaClosed: boolean
) {
  const source = map.getSource("area-draft") as maplibregl.GeoJSONSource | undefined;
  if (!source) return;
  source.setData(buildDraftFeatures(vertices, areaClosed));
}

function syncUnitsSource(
  map: maplibregl.Map,
  areaUnits: AreaUnit[],
  selectedAreaUnitIds: string[],
  areaResult: AreaAnalyzeResponse | null,
  activeAreaUnitId: string | null
) {
  const source = map.getSource("area-units") as maplibregl.GeoJSONSource | undefined;
  if (!source) return;
  source.setData(
    buildUnitFeatures(areaUnits, selectedAreaUnitIds, areaResult, activeAreaUnitId)
  );
}

function findUnitIdAtPoint(
  map: maplibregl.Map,
  point: maplibregl.Point
): string | null {
  if (!map.getLayer("area-units-fill")) {
    return null;
  }

  const feature = map.queryRenderedFeatures(point, {
    layers: ["area-units-fill"],
  })[0];

  const unitId = feature?.properties?.unitId;
  return typeof unitId === "string" ? unitId : null;
}

function findDraftVertexIndexAtPoint(
  map: maplibregl.Map,
  point: maplibregl.Point
): number | null {
  if (!map.getLayer("area-draft-vertices")) {
    return null;
  }

  const feature = map.queryRenderedFeatures(point, {
    layers: ["area-draft-vertices"],
  })[0];

  const rawValue = feature?.properties?.vertexIndex;
  const parsed = typeof rawValue === "string" ? Number.parseInt(rawValue, 10) : rawValue;
  return typeof parsed === "number" && Number.isFinite(parsed) ? parsed : null;
}

function buildDraftFeatures(vertices: LatLng[], areaClosed: boolean) {
  const features: Feature[] = vertices.map((vertex, index) => ({
    type: "Feature",
    properties: {
      kind: "vertex",
      id: `vertex-${index}`,
      vertexIndex: index,
      isFirst: index === 0,
    },
    geometry: {
      type: "Point",
      coordinates: [vertex.lng, vertex.lat],
    },
  }));

  if (vertices.length >= 2) {
    const coordinates = vertices.map((vertex) => [vertex.lng, vertex.lat]);
    if (areaClosed && vertices.length >= 3) {
      coordinates.push([vertices[0].lng, vertices[0].lat]);
    }

    features.push({
      type: "Feature",
      properties: { kind: "line" },
      geometry: {
        type: "LineString",
        coordinates,
      },
    });
  }

  const polygon = buildPolygon(vertices, areaClosed);
  if (polygon) {
    features.push({
      type: "Feature",
      properties: { kind: "polygon" },
      geometry: polygon,
    });
  }

  return {
    type: "FeatureCollection",
    features,
  } satisfies FeatureCollection;
}

function buildUnitFeatures(
  areaUnits: AreaUnit[],
  selectedAreaUnitIds: string[],
  areaResult: AreaAnalyzeResponse | null,
  activeAreaUnitId: string | null
) {
  const resultMap = new globalThis.Map(
    areaResult?.unit_results.map((unit) => [unit.id, unit]) ?? []
  );

  return {
    type: "FeatureCollection",
    features: areaUnits.map((unit) => {
      const result = resultMap.get(unit.id);
      return {
        type: "Feature",
        properties: {
          unitId: unit.id,
          label: unit.label,
          selected: selectedAreaUnitIds.includes(unit.id),
          active: unit.id === activeAreaUnitId,
          status: result ? "analyzed" : "preview",
          risk: result?.overall_risk_level ?? "UNKNOWN",
        },
        geometry: unit.geometry,
      };
    }),
  } satisfies FeatureCollection;
}

function buildPolygon(vertices: LatLng[], areaClosed: boolean): Polygon | null {
  if (!areaClosed || vertices.length < 3) {
    return null;
  }

  return {
    type: "Polygon",
    coordinates: [
      [
        ...vertices.map((vertex) => [vertex.lng, vertex.lat]),
        [vertices[0].lng, vertices[0].lat],
      ],
    ],
  };
}

function emptyFeatureCollection() {
  return {
    type: "FeatureCollection",
    features: [],
  } satisfies FeatureCollection;
}
