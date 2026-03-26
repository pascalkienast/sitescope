"use client";

import type {
  AreaAnalyzeResponse,
  AreaUnit,
  AreaUnitResult,
  LatLng,
} from "@/lib/types";
import { CATEGORY_META, RISK_META } from "@/lib/types";
import { RiskBadge } from "./RiskBadge";

interface AreaPanelProps {
  hasPolygon: boolean;
  draftVertexCount: number;
  previewLoading: boolean;
  analyzing: boolean;
  error: string | null;
  warnings: string[];
  units: AreaUnit[];
  selectedUnitIds: string[];
  result: AreaAnalyzeResponse | null;
  onToggleUnit: (unitId: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onAnalyzeSelected: () => void;
  onOpenDetailedReport: (coords: LatLng) => void;
}

export function AreaPanel({
  hasPolygon,
  draftVertexCount,
  previewLoading,
  analyzing,
  error,
  warnings,
  units,
  selectedUnitIds,
  result,
  onToggleUnit,
  onSelectAll,
  onClearSelection,
  onAnalyzeSelected,
  onOpenDetailedReport,
}: AreaPanelProps) {
  const selectedCount = selectedUnitIds.length;

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-100 shrink-0 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-gray-900">
              Flächenanalyse
            </h2>
            <p className="text-xs text-amber-700 mt-1">
              Approximativ, keine amtliche Flurstückszerlegung
            </p>
          </div>
          <span className="text-[11px] font-medium px-2 py-1 rounded-full bg-amber-50 text-amber-700">
            Open-Data-Grid
          </span>
        </div>

        {warnings.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
            {warnings.map((warning, index) => (
              <p key={index} className="text-xs text-amber-800 leading-relaxed">
                {warning}
              </p>
            ))}
          </div>
        )}

        {hasPolygon && !result && units.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={onSelectAll}
              className="px-2.5 py-1 text-xs rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
            >
              Alle auswählen
            </button>
            <button
              onClick={onClearSelection}
              className="px-2.5 py-1 text-xs rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
            >
              Auswahl leeren
            </button>
            <span className="text-xs text-gray-500 ml-auto">
              {selectedCount} / {units.length} markiert
            </span>
          </div>
        )}

        {hasPolygon && !result && units.length > 0 && (
          <button
            onClick={onAnalyzeSelected}
            disabled={selectedCount === 0 || previewLoading || analyzing}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {analyzing ? "Analysiere Auswahl…" : "Analyse starten"}
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto report-scroll p-4 space-y-4">
        {!hasPolygon && (
          <InstructionCard
            title="Polygon zeichnen"
            body="Setze Eckpunkte mit einfachen Klicks auf der Karte. Schließe die Fläche danach über den Button `Fläche schließen` oder indem du den ersten Punkt erneut anklickst."
            footer="Undo, Fläche schließen und Clear stehen oben im Header zur Verfügung."
          />
        )}

        {!hasPolygon && draftVertexCount > 0 && (
          <InstructionCard
            title="Polygon im Aufbau"
            body={`Bisher ${draftVertexCount} Eckpunkte gesetzt. Für eine Fläche brauchst du mindestens 3 Punkte.`}
          />
        )}

        {previewLoading && (
          <LoadingCard
            title="Vorschau wird berechnet"
            body="Polygon wird serverseitig in Analysezellen zerlegt."
          />
        )}

        {analyzing && (
          <LoadingCard
            title="Batchanalyse läuft"
            body="Die ausgewählten Analysezellen werden ohne LLM-Report abgefragt."
          />
        )}

        {error && !previewLoading && !analyzing && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
            <p className="font-medium text-sm">Flächenanalyse fehlgeschlagen</p>
            <p className="text-xs mt-1 leading-relaxed">{error}</p>
          </div>
        )}

        {!result && hasPolygon && !previewLoading && !analyzing && units.length === 0 && !error && (
          <InstructionCard
            title="Keine Analysezellen gefunden"
            body="Die Fläche liefert in der aktuellen Approximation keine nutzbaren Analysezellen."
          />
        )}

        {!result && units.length > 0 && !previewLoading && !analyzing && (
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Vorschau
            </h3>
            {units.map((unit) => {
              const selected = selectedUnitIds.includes(unit.id);
              return (
                <label
                  key={unit.id}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    selected
                      ? "border-blue-300 bg-blue-50"
                      : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggleUnit(unit.id)}
                    className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-gray-900">
                        {unit.label}
                      </p>
                      <span className="text-[10px] text-gray-500">
                        {formatArea(unit.area_sqm)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">
                      Sample point: {formatCoords(unit.sample_point)}
                    </p>
                  </div>
                </label>
              );
            })}
          </div>
        )}

        {result && (
          <div className="space-y-4">
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Rollup nach Kategorie
              </h3>
              <div className="grid grid-cols-1 gap-2">
                {result.category_rollup.map((entry) => {
                  const meta = CATEGORY_META[entry.category];
                  const riskMeta = RISK_META[entry.highest_risk];
                  return (
                    <div
                      key={entry.category}
                      className="rounded-lg border p-3"
                      style={{ borderColor: `${riskMeta.color}30` }}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg">{meta.emoji}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-gray-900">
                            {meta.label}
                          </p>
                          <p className="text-xs text-gray-500">
                            Betroffene Zellen: {entry.affected_units.length}
                          </p>
                        </div>
                        <RiskBadge level={entry.highest_risk} size="sm" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Analysierte Zellen
              </h3>
              {result.unit_results.map((unitResult) => (
                <AreaResultCard
                  key={unitResult.id}
                  unitResult={unitResult}
                  onOpenDetailedReport={onOpenDetailedReport}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AreaResultCard({
  unitResult,
  onOpenDetailedReport,
}: {
  unitResult: AreaUnitResult;
  onOpenDetailedReport: (coords: LatLng) => void;
}) {
  const activeCategories = unitResult.agent_results.filter(
    (agentResult) =>
      agentResult.risk_level !== "NONE" && agentResult.risk_level !== "UNKNOWN"
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-900">{unitResult.label}</p>
          <p className="text-xs text-gray-500 mt-1">
            {formatCoords({ lat: unitResult.lat, lng: unitResult.lng })}
          </p>
        </div>
        <RiskBadge level={unitResult.overall_risk_level} size="sm" />
      </div>

      {activeCategories.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {activeCategories.map((agentResult) => {
            const meta = CATEGORY_META[agentResult.category];
            return (
              <span
                key={`${unitResult.id}-${agentResult.category}`}
                className="text-[11px] px-2 py-1 rounded-full bg-gray-100 text-gray-700"
              >
                {meta.emoji} {meta.label}: {agentResult.risk_level}
              </span>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-gray-500">
          Keine aktiven Kategorien gemeldet.
        </p>
      )}

      {unitResult.errors.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-2">
          {unitResult.errors.map((error, index) => (
            <p key={index} className="text-[11px] text-yellow-800">
              {error}
            </p>
          ))}
        </div>
      )}

      <button
        onClick={() =>
          onOpenDetailedReport({ lat: unitResult.lat, lng: unitResult.lng })
        }
        className="w-full px-3 py-2 rounded-lg bg-gray-900 text-white text-xs font-medium hover:bg-black transition-colors"
      >
        Detaillierten Punkt-Report öffnen
      </button>
    </div>
  );
}

function InstructionCard({
  title,
  body,
  footer,
}: {
  title: string;
  body: string;
  footer?: string;
}) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <p className="text-sm font-semibold text-gray-900">{title}</p>
      <p className="text-xs text-gray-600 mt-1 leading-relaxed">{body}</p>
      {footer && <p className="text-[11px] text-gray-500 mt-2">{footer}</p>}
    </div>
  );
}

function LoadingCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <div>
          <p className="text-sm font-semibold text-blue-900">{title}</p>
          <p className="text-xs text-blue-700 mt-1">{body}</p>
        </div>
      </div>
    </div>
  );
}

function formatArea(areaSqm: number) {
  return `${Math.round(areaSqm).toLocaleString("de-DE")} m²`;
}

function formatCoords(coords: LatLng) {
  return `${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)}`;
}
