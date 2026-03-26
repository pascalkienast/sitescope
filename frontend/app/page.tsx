"use client";

import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { ReportPanel } from "@/components/ReportPanel";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { analyzeSite, getDemoLocations } from "@/lib/api";
import type { AnalyzeResponse, DemoLocation } from "@/lib/types";

// Dynamic import for map (requires browser APIs)
const Map = dynamic(() => import("@/components/Map").then((m) => m.Map), {
  ssr: false,
  loading: () => (
    <div className="flex-1 bg-gray-100 flex items-center justify-center">
      <p className="text-gray-500">Loading map…</p>
    </div>
  ),
});

export default function Home() {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [selectedCoords, setSelectedCoords] = useState<{
    lat: number;
    lng: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [demoLocations, setDemoLocations] = useState<DemoLocation[]>([]);

  // Load demo locations on mount
  useEffect(() => {
    getDemoLocations().then(setDemoLocations).catch(() => {});
  }, []);

  const handleMapClick = useCallback(
    async (lat: number, lng: number) => {
      if (analyzing) return;

      setSelectedCoords({ lat, lng });
      setAnalyzing(true);
      setError(null);
      setResult(null);

      try {
        const response = await analyzeSite(lat, lng);
        // Check if backend returned a coverage-area error (success=false with errors)
        if (!response.success && response.errors?.length > 0) {
          const isCoverageError = response.errors.some(
            (e) => e.includes("outside Bavaria") || e.includes("outside coverage")
          );
          if (isCoverageError) {
            setError(`__COVERAGE__${response.errors[0]}`);
          } else {
            setError(response.errors.join("; "));
          }
        } else {
          setResult(response);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Analysis failed"
        );
      } finally {
        setAnalyzing(false);
      }
    },
    [analyzing]
  );

  const handleDemoClick = useCallback(
    (loc: DemoLocation) => {
      handleMapClick(loc.lat, loc.lng);
    },
    [handleMapClick]
  );

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shrink-0 z-10">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🔍</span>
          <div>
            <h1 className="text-lg font-bold text-gray-900 leading-tight">
              SiteScope
            </h1>
            <p className="text-xs text-gray-500">
              Red Flag Report Generator
            </p>
          </div>
        </div>

        {/* Demo locations */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 mr-1 hidden sm:inline">Demo:</span>
          {demoLocations.map((loc) => (
            <button
              key={loc.name}
              onClick={() => handleDemoClick(loc)}
              disabled={analyzing}
              className="px-2.5 py-1 text-xs bg-blue-50 text-blue-700 rounded-full
                hover:bg-blue-100 transition-colors disabled:opacity-50
                disabled:cursor-not-allowed hidden md:inline-block"
              title={`${loc.name} (${loc.expected.join(", ")})`}
            >
              {loc.name.split(",")[0]}
            </button>
          ))}
        </div>
      </header>

      {/* Main content: Map + Report Panel */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Map takes full width, report overlays on the right */}
        <div className="flex-1 relative">
          <Map
            onClick={handleMapClick}
            selectedCoords={selectedCoords}
            demoLocations={demoLocations}
          />
        </div>

        {/* Report panel — slides in from right */}
        {(result || analyzing || error) && (
          <div className="w-full sm:w-[440px] md:w-[480px] shrink-0 border-l border-gray-200 bg-white overflow-hidden flex flex-col">
            {analyzing && <LoadingOverlay coords={selectedCoords} />}
            {error && !analyzing && (
              <div className="p-6">
                {error.startsWith("__COVERAGE__") ? (
                  <div className="bg-amber-50 border border-amber-200 text-amber-800 p-5 rounded-lg">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl shrink-0">📍</span>
                      <div>
                        <p className="font-semibold text-base">Outside Coverage Area</p>
                        <p className="text-sm mt-2 leading-relaxed">
                          {error.replace("__COVERAGE__", "")}
                        </p>
                        <p className="text-xs mt-3 text-amber-600">
                          Try clicking a location within Bavaria on the map, or use one of the demo locations above.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-red-50 text-red-700 p-4 rounded-lg">
                    <p className="font-medium">Analysis Error</p>
                    <p className="text-sm mt-1">{error}</p>
                  </div>
                )}
              </div>
            )}
            {result && !analyzing && (
              <ReportPanel
                result={result}
                coords={selectedCoords!}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
