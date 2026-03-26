"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AreaPanel } from "@/components/AreaPanel";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { ReportPanel } from "@/components/ReportPanel";
import {
  analyzeAreaUnits,
  analyzeSite,
  fetchAreaUnits,
  getDemoLocations,
} from "@/lib/api";
import type {
  AnalysisMode,
  AnalyzeResponse,
  AreaAnalyzeResponse,
  AreaUnit,
  DemoLocation,
  GeoJsonPolygon,
  LatLng,
} from "@/lib/types";

const Map = dynamic(() => import("@/components/Map").then((module) => module.Map), {
  ssr: false,
  loading: () => (
    <div className="flex-1 bg-gray-100 flex items-center justify-center">
      <p className="text-gray-500">Loading map…</p>
    </div>
  ),
});

export default function Home() {
  const [mode, setMode] = useState<AnalysisMode>("point");
  const [demoLocations, setDemoLocations] = useState<DemoLocation[]>([]);
  const [showParcelOverlay, setShowParcelOverlay] = useState(false);

  const [pointAnalyzing, setPointAnalyzing] = useState(false);
  const [pointResult, setPointResult] = useState<AnalyzeResponse | null>(null);
  const [selectedCoords, setSelectedCoords] = useState<LatLng | null>(null);
  const [pointError, setPointError] = useState<string | null>(null);

  const [areaVertices, setAreaVertices] = useState<LatLng[]>([]);
  const [areaClosed, setAreaClosed] = useState(false);
  const [areaPreviewLoading, setAreaPreviewLoading] = useState(false);
  const [areaAnalyzing, setAreaAnalyzing] = useState(false);
  const [areaError, setAreaError] = useState<string | null>(null);
  const [areaWarnings, setAreaWarnings] = useState<string[]>([]);
  const [areaUnits, setAreaUnits] = useState<AreaUnit[]>([]);
  const [selectedAreaUnitIds, setSelectedAreaUnitIds] = useState<string[]>([]);
  const [areaResult, setAreaResult] = useState<AreaAnalyzeResponse | null>(null);

  useEffect(() => {
    getDemoLocations().then(setDemoLocations).catch(() => {});
  }, []);

  async function runPointAnalysis(
    coords: LatLng,
    { switchToPoint = false }: { switchToPoint?: boolean } = {}
  ) {
    if (pointAnalyzing || areaPreviewLoading || areaAnalyzing) return;

    if (switchToPoint) {
      setMode("point");
    }

    setSelectedCoords(coords);
    setPointAnalyzing(true);
    setPointError(null);
    setPointResult(null);

    try {
      const response = await analyzeSite(coords.lat, coords.lng);
      if (!response.success && response.errors?.length > 0) {
        const isCoverageError = response.errors.some(
          (error) =>
            error.includes("outside Bavaria") || error.includes("outside coverage")
        );
        setPointError(
          isCoverageError
            ? `__COVERAGE__${response.errors[0]}`
            : response.errors.join("; ")
        );
      } else {
        setPointResult(response);
      }
    } catch (error) {
      setPointError(error instanceof Error ? error.message : "Analysis failed");
    } finally {
      setPointAnalyzing(false);
    }
  }

  function resetAreaState({ clearPolygon = false }: { clearPolygon?: boolean } = {}) {
    setAreaPreviewLoading(false);
    setAreaAnalyzing(false);
    setAreaError(null);
    setAreaWarnings([]);
    setAreaUnits([]);
    setSelectedAreaUnitIds([]);
    setAreaResult(null);
    if (clearPolygon) {
      setAreaVertices([]);
      setAreaClosed(false);
    }
  }

  function handleModeChange(nextMode: AnalysisMode) {
    setMode(nextMode);
    if (nextMode === "point") {
      setShowParcelOverlay(false);
    }
  }

  function handleAreaVertexAdd(lat: number, lng: number) {
    if (areaClosed || areaPreviewLoading || areaAnalyzing) return;
    resetAreaState();
    setAreaVertices((current) => [...current, { lat, lng }]);
  }

  async function handleAreaComplete(lat: number, lng: number) {
    if (areaClosed || areaPreviewLoading || areaAnalyzing) return;

    const nextVertices = appendVertexIfNeeded(areaVertices, { lat, lng });
    if (nextVertices.length < 3) return;

    const polygon = buildPolygon(nextVertices);
    if (!polygon) return;

    setAreaVertices(nextVertices);
    setAreaClosed(true);
    setAreaPreviewLoading(true);
    setAreaError(null);
    setAreaWarnings([]);
    setAreaUnits([]);
    setSelectedAreaUnitIds([]);
    setAreaResult(null);

    try {
      const response = await fetchAreaUnits(polygon);
      setAreaWarnings(response.warnings);
      setAreaUnits(response.units);
      setSelectedAreaUnitIds(response.units.map((unit) => unit.id));
      if (response.units.length === 0) {
        setAreaError("No approximate analysis cells could be derived from this polygon.");
      }
    } catch (error) {
      setAreaError(error instanceof Error ? error.message : "Area preview failed");
      setAreaClosed(false);
    } finally {
      setAreaPreviewLoading(false);
    }
  }

  function handleCloseArea() {
    if (areaClosed || areaVertices.length < 3) return;
    const firstVertex = areaVertices[0];
    void handleAreaComplete(firstVertex.lat, firstVertex.lng);
  }

  function handleUndoArea() {
    if (!areaVertices.length) return;
    resetAreaState();
    setAreaClosed(false);
    setAreaVertices((current) => current.slice(0, -1));
  }

  function handleClearArea() {
    resetAreaState({ clearPolygon: true });
  }

  function handleToggleAreaUnit(unitId: string) {
    setAreaError(null);
    setAreaResult(null);
    setSelectedAreaUnitIds((current) =>
      current.includes(unitId)
        ? current.filter((value) => value !== unitId)
        : [...current, unitId]
    );
  }

  function handleSelectAllAreaUnits() {
    setAreaResult(null);
    setSelectedAreaUnitIds(areaUnits.map((unit) => unit.id));
  }

  function handleClearAreaSelection() {
    setAreaResult(null);
    setSelectedAreaUnitIds([]);
  }

  async function handleAnalyzeArea() {
    if (areaPreviewLoading || areaAnalyzing) return;
    const selectedUnits = areaUnits
      .filter((unit) => selectedAreaUnitIds.includes(unit.id))
      .map((unit) => ({
        id: unit.id,
        label: unit.label,
        lat: unit.sample_point.lat,
        lng: unit.sample_point.lng,
      }));

    if (selectedUnits.length === 0) return;

    setAreaAnalyzing(true);
    setAreaError(null);
    setAreaResult(null);

    try {
      const response = await analyzeAreaUnits(selectedUnits);
      setAreaWarnings(response.warnings);
      setAreaResult(response);
    } catch (error) {
      setAreaError(error instanceof Error ? error.message : "Area analysis failed");
    } finally {
      setAreaAnalyzing(false);
    }
  }

  function handleAreaUnitMapClick(unitId: string) {
    const analyzedUnit = areaResult?.unit_results.find((unit) => unit.id === unitId);
    if (analyzedUnit) {
      void runPointAnalysis(
        { lat: analyzedUnit.lat, lng: analyzedUnit.lng },
        { switchToPoint: true }
      );
      return;
    }

    handleToggleAreaUnit(unitId);
  }

  const showPointPanel =
    mode === "point" && (pointResult !== null || pointAnalyzing || pointError !== null);

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between gap-4 shrink-0 z-10">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-2xl">🔍</span>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-gray-900 leading-tight">
              SiteScope
            </h1>
            <p className="text-xs text-gray-500">
              Punkt- und Flächen-Screening für Bayern
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          <div className="inline-flex rounded-lg bg-gray-100 p-1">
            <button
              onClick={() => handleModeChange("point")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                mode === "point"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              Punkt
            </button>
            <button
              onClick={() => handleModeChange("area")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                mode === "area"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              Fläche
            </button>
          </div>

          {mode === "area" && (
            <>
              <button
                onClick={handleCloseArea}
                disabled={areaClosed || areaVertices.length < 3 || areaPreviewLoading || areaAnalyzing}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Fläche schließen
              </button>
              <button
                onClick={() => setShowParcelOverlay((current) => !current)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                  showParcelOverlay
                    ? "border-amber-300 bg-amber-50 text-amber-800"
                    : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                Parzellarkarte
              </button>
              <button
                onClick={handleUndoArea}
                disabled={areaVertices.length === 0}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Undo
              </button>
              <button
                onClick={handleClearArea}
                disabled={areaVertices.length === 0 && areaUnits.length === 0}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Clear
              </button>
            </>
          )}

          {mode === "point" && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 mr-1 hidden sm:inline">
                Demo:
              </span>
              {demoLocations.map((location) => (
                <button
                  key={location.name}
                  onClick={() =>
                    void runPointAnalysis({ lat: location.lat, lng: location.lng })
                  }
                  disabled={pointAnalyzing}
                  className="px-2.5 py-1 text-xs bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed hidden md:inline-block"
                  title={`${location.name} (${location.expected.join(", ")})`}
                >
                  {location.name.split(",")[0]}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        <div className="flex-1 relative">
          <Map
            mode={mode}
            onPointClick={(lat, lng) => void runPointAnalysis({ lat, lng })}
            selectedCoords={selectedCoords}
            demoLocations={demoLocations}
            showDemoMarkers={mode === "point"}
            areaVertices={areaVertices}
            areaClosed={areaClosed}
            areaUnits={areaUnits}
            selectedAreaUnitIds={selectedAreaUnitIds}
            areaResult={areaResult}
            onAreaVertexAdd={handleAreaVertexAdd}
            onAreaComplete={(lat, lng) => void handleAreaComplete(lat, lng)}
            onAreaUnitClick={handleAreaUnitMapClick}
            showParcelOverlay={showParcelOverlay}
          />
        </div>

        {mode === "area" && (
          <div className="w-full sm:w-[440px] md:w-[480px] shrink-0 border-l border-gray-200 bg-white overflow-hidden flex flex-col">
            <AreaPanel
              hasPolygon={areaClosed}
              draftVertexCount={areaVertices.length}
              previewLoading={areaPreviewLoading}
              analyzing={areaAnalyzing}
              error={areaError}
              warnings={areaWarnings}
              units={areaUnits}
              selectedUnitIds={selectedAreaUnitIds}
              result={areaResult}
              onToggleUnit={handleToggleAreaUnit}
              onSelectAll={handleSelectAllAreaUnits}
              onClearSelection={handleClearAreaSelection}
              onAnalyzeSelected={() => void handleAnalyzeArea()}
              onOpenDetailedReport={(coords) =>
                void runPointAnalysis(coords, { switchToPoint: true })
              }
            />
          </div>
        )}

        {showPointPanel && (
          <div className="w-full sm:w-[440px] md:w-[480px] shrink-0 border-l border-gray-200 bg-white overflow-hidden flex flex-col">
            {pointAnalyzing && <LoadingOverlay coords={selectedCoords} />}
            {pointError && !pointAnalyzing && (
              <div className="p-6">
                {pointError.startsWith("__COVERAGE__") ? (
                  <div className="bg-amber-50 border border-amber-200 text-amber-800 p-5 rounded-lg">
                    <div className="flex items-start gap-3">
                      <span className="text-2xl shrink-0">📍</span>
                      <div>
                        <p className="font-semibold text-base">Outside Coverage Area</p>
                        <p className="text-sm mt-2 leading-relaxed">
                          {pointError.replace("__COVERAGE__", "")}
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
                    <p className="text-sm mt-1">{pointError}</p>
                  </div>
                )}
              </div>
            )}
            {pointResult && !pointAnalyzing && selectedCoords && (
              <ReportPanel result={pointResult} coords={selectedCoords} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function buildPolygon(vertices: LatLng[]): GeoJsonPolygon | null {
  if (vertices.length < 3) {
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

function appendVertexIfNeeded(vertices: LatLng[], nextVertex: LatLng): LatLng[] {
  const lastVertex = vertices[vertices.length - 1];
  if (
    lastVertex &&
    Math.abs(lastVertex.lat - nextVertex.lat) < 1e-7 &&
    Math.abs(lastVertex.lng - nextVertex.lng) < 1e-7
  ) {
    return vertices;
  }

  return [...vertices, nextVertex];
}
