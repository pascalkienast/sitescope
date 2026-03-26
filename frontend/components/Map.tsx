"use client";

import { useRef, useEffect, useCallback } from "react";
import maplibregl from "maplibre-gl";
import type { DemoLocation } from "@/lib/types";

interface MapProps {
  onClick: (lat: number, lng: number) => void;
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
  const markerRef = useRef<maplibregl.Marker | null>(null);

  // Initialize map
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

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Handle map clicks
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      const { lat, lng } = e.lngLat;
      onClick(lat, lng);
    };

    map.on("click", handleClick);
    return () => {
      map.off("click", handleClick);
    };
  }, [onClick]);

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
    <div ref={containerRef} className="w-full h-full" />
  );
}
