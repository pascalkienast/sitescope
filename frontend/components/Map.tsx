"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import maplibregl from "maplibre-gl";
import MapboxDraw from "@mapbox/mapbox-gl-draw";
import type { DemoLocation } from "@/lib/types";
import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";

interface MapProps {
  onClick: (lat: number, lng: number, polygon?: [number, number][]) => void;
  selectedCoords: { lat: number; lng: number } | null;
  demoLocations: DemoLocation[];
}

// Munich center as default view
const DEFAULT_CENTER: [number, number] = [11.576, 48.137];
const DEFAULT_ZOOM = 12;

// Free OpenStreetMap tile source
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

export function Map({ onClick, selectedCoords, demoLocations }: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const drawRef = useRef<MapboxDraw | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [hasPolygon, setHasPolygon] = useState(false);

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    // Initialize draw control
    const Draw = new MapboxDraw({
      displayControlsDefault: false,
      defaultMode: "simple_select",
      styles: [
        {
          id: "gl-draw-polygon-fill",
          type: "fill",
          filter: ["all", ["==", "$type", "Polygon"]],
          paint: {
            "fill-color": "#3B82F6",
            "fill-opacity": 0.2,
          },
        },
        {
          id: "gl-draw-polygon-stroke",
          type: "line",
          filter: ["all", ["==", "$type", "Polygon"]],
          paint: {
            "line-color": "#3B82F6",
            "line-width": 2,
          },
        },
        {
          id: "gl-draw-polygon-vertex",
          type: "circle",
          filter: ["all", ["==", "$type", "Point"], ["==", "meta", "vertex"]],
          paint: {
            "circle-radius": 5,
            "circle-color": "#3B82F6",
            "circle-stroke-color": "#fff",
            "circle-stroke-width": 2,
          },
        },
      ],
    });

    map.addControl(Draw as unknown as maplibregl.IControl, "top-left");
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
      }),
      "top-right"
    );

    mapRef.current = map;
    drawRef.current = Draw;

    // Handle polygon creation
    map.on("draw.create", (e) => {
      const features = e.features;
      if (features && features.length > 0) {
        const polygon = features[0];
        if (polygon.geometry && polygon.geometry.type === "Polygon") {
          const coords = polygon.geometry.coordinates[0] as [number, number][];
          setHasPolygon(true);

          // Calculate centroid of polygon
          const centroid = calculateCentroid(coords);
          onClick(centroid.lat, centroid.lng, coords);
        }
      }
    });

    // Handle polygon deletion
    map.on("draw.delete", () => {
      setHasPolygon(false);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      drawRef.current = null;
    };
  }, []);

  // Handle draw mode toggle
  const toggleDrawMode = useCallback(() => {
    const draw = drawRef.current;
    if (!draw) return;

    if (drawMode) {
      draw.changeMode("simple_select");
      setDrawMode(false);
    } else {
      draw.changeMode("draw_polygon");
      setDrawMode(true);
    }
  }, [drawMode]);

  // Clear polygon
  const clearPolygon = useCallback(() => {
    const draw = drawRef.current;
    if (!draw) return;

    draw.deleteAll();
    setHasPolygon(false);
    setDrawMode(false);
  }, []);

  // Handle map clicks (only when not in draw mode)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      // Don't handle click if in draw mode
      if (drawMode) return;

      const { lat, lng } = e.lngLat;

      // Clear any existing polygon first
      const draw = drawRef.current;
      if (draw) {
        draw.deleteAll();
        setHasPolygon(false);
      }

      onClick(lat, lng);
    };

    map.on("click", handleClick);
    return () => {
      map.off("click", handleClick);
    };
  }, [onClick, drawMode]);

  // Update marker on selected coords
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Remove old marker
    if (markerRef.current) {
      markerRef.current.remove();
      markerRef.current = null;
    }

    if (selectedCoords) {
      // Create a pulsing marker element
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
        .setLngLat([selectedCoords.lng, selectedCoords.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<strong>Analyzing…</strong><br/>
             ${selectedCoords.lat.toFixed(4)}, ${selectedCoords.lng.toFixed(4)}`
          )
        )
        .addTo(map);

      markerRef.current = marker;

      // Fly to the location
      map.flyTo({
        center: [selectedCoords.lng, selectedCoords.lat],
        zoom: Math.max(map.getZoom(), 14),
        duration: 800,
      });
    }
  }, [selectedCoords]);

  // Add demo location markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !demoLocations.length) return;

    const markers: maplibregl.Marker[] = [];

    for (const loc of demoLocations) {
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
        " 
        onmouseenter="this.style.opacity='1';this.style.transform='scale(1.3)'" 
        onmouseleave="this.style.opacity='0.7';this.style.transform='scale(1)'"
        title="${loc.name}"></div>
      `;

      el.addEventListener("click", (e) => {
        e.stopPropagation();
        // Clear any existing polygon first
        const draw = drawRef.current;
        if (draw) {
          draw.deleteAll();
          setHasPolygon(false);
        }
        onClick(loc.lat, loc.lng);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([loc.lng, loc.lat])
        .addTo(map);

      markers.push(marker);
    }

    return () => {
      markers.forEach((m) => m.remove());
    };
  }, [demoLocations, onClick]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* Draw mode controls */}
      <div className="absolute top-3 left-3 z-10 flex gap-2">
        <button
          onClick={toggleDrawMode}
          className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all ${
            drawMode
              ? "bg-blue-600 text-white"
              : "bg-white text-gray-700 hover:bg-gray-50 border border-gray-200"
          }`}
          title={drawMode ? "Cancel drawing" : "Draw polygon"}
        >
          {drawMode ? "Cancel" : "Draw Area"}
        </button>

        {hasPolygon && (
          <button
            onClick={clearPolygon}
            className="px-3 py-1.5 text-sm font-medium rounded-lg bg-white text-gray-700 hover:bg-gray-50 border border-gray-200 transition-all"
            title="Clear polygon"
          >
            Clear
          </button>
        )}
      </div>

      {/* Mode indicator */}
      {drawMode && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 bg-blue-600 text-white text-sm px-4 py-1.5 rounded-full shadow-lg">
          Click to add points, double-click to finish
        </div>
      )}

      {/* Polygon info */}
      {hasPolygon && !drawMode && (
        <div className="absolute bottom-3 left-3 z-10 bg-blue-50 text-blue-800 text-sm px-3 py-2 rounded-lg border border-blue-200 shadow">
          Analyzing polygon area
        </div>
      )}
    </div>
  );
}

function calculateCentroid(coords: [number, number][]): { lat: number; lng: number } {
  let latSum = 0;
  let lngSum = 0;
  const n = coords.length;

  for (const [lng, lat] of coords) {
    latSum += lat;
    lngSum += lng;
  }

  return {
    lat: latSum / n,
    lng: lngSum / n,
  };
}
