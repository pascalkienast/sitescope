"use client";

import type { ReactNode } from "react";
import type {
  AnalyzeResponse,
  AreaAnalyzeResponse,
  AreaUnit,
  AreaUnitResult,
  RiskLevel,
} from "@/lib/types";
import { CATEGORY_META, RISK_META } from "@/lib/types";
import { ReportPanel } from "./ReportPanel";
import { RiskBadge } from "./RiskBadge";

interface AreaPanelProps {
  view: "overview" | "detail";
  hasPolygon: boolean;
  draftVertexCount: number;
  previewLoading: boolean;
  analyzing: boolean;
  error: string | null;
  warnings: string[];
  units: AreaUnit[];
  selectedUnitIds: string[];
  result: AreaAnalyzeResponse | null;
  detailUnit: AreaUnitResult | null;
  detailReport: AnalyzeResponse | null;
  detailLoading: boolean;
  detailError: string | null;
  areaPdfDownloading: boolean;
  onToggleUnit: (unitId: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onAnalyzeSelected: () => void;
  onDownloadAreaPDF: () => void;
  onOpenDetailedReport: (unitId: string) => void;
  onCloseDetailedReport: () => void;
  onRetryDetailedReport: () => void;
}

export function AreaPanel({
  view,
  hasPolygon,
  draftVertexCount,
  previewLoading,
  analyzing,
  error,
  warnings,
  units,
  selectedUnitIds,
  result,
  detailUnit,
  detailReport,
  detailLoading,
  detailError,
  areaPdfDownloading,
  onToggleUnit,
  onSelectAll,
  onClearSelection,
  onAnalyzeSelected,
  onDownloadAreaPDF,
  onOpenDetailedReport,
  onCloseDetailedReport,
  onRetryDetailedReport,
}: AreaPanelProps) {
  if (view === "detail" && detailUnit) {
    return (
      <AreaDetailView
        unit={detailUnit}
        report={detailReport}
        loading={detailLoading}
        error={detailError}
        onBack={onCloseDetailedReport}
        onRetry={onRetryDetailedReport}
      />
    );
  }

  const selectedCount = selectedUnitIds.length;
  const analyzedCount = result?.unit_results.length ?? 0;
  const totalArea = units.reduce((sum, unit) => sum + unit.area_sqm, 0);
  const analyzedArea = result
    ? result.unit_results.reduce((sum, unitResult) => {
        const unit = units.find((candidate) => candidate.id === unitResult.id);
        return sum + (unit?.area_sqm ?? 0);
      }, 0)
    : 0;
  const overallRisk = result ? getHighestRisk(result.unit_results) : null;

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-100 shrink-0 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-gray-900">Flächenanalyse</h2>
            <p className="text-xs text-amber-700 mt-1">
              Approximativ, keine amtliche Flurstückszerlegung
            </p>
          </div>
          <span className="text-[11px] font-medium px-2 py-1 rounded-full bg-amber-50 text-amber-700">
            Open-Data-Grid
          </span>
        </div>

        {(hasPolygon || result) && (
          <div className="grid grid-cols-2 gap-2">
            <SummaryCard
              label="Vorschauzellen"
              value={units.length.toString()}
              note={totalArea > 0 ? `${formatArea(totalArea)} in Vorschau` : "Noch keine Fläche"}
            />
            <SummaryCard
              label={result ? "Analysiert" : "Ausgewählt"}
              value={result ? `${analyzedCount} / ${units.length}` : selectedCount.toString()}
              note={
                result
                  ? `${formatArea(analyzedArea)} im Batch ausgewertet`
                  : "Wähle die Zellen für die Analyse"
              }
            />
            <SummaryCard
              label="Status"
              value={
                overallRisk ? (
                  <RiskBadge level={overallRisk} size="sm" />
                ) : (
                  <span className="text-sm font-semibold text-gray-500">Offen</span>
                )
              }
              note={
                overallRisk
                  ? RISK_META[overallRisk].label
                  : "Analyse noch nicht gestartet"
              }
            />
            <SummaryCard
              label="Export"
              value={
                <button
                  onClick={onDownloadAreaPDF}
                  disabled={!result || areaPdfDownloading || analyzing || previewLoading}
                  className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gray-900 text-white text-xs font-medium hover:bg-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {areaPdfDownloading ? "PDF wird erstellt..." : "Flächen-PDF"}
                </button>
              }
              note={
                result
                  ? `${analyzedCount} von ${units.length} Zellen werden exportiert`
                  : "Nach abgeschlossener Analyse verfügbar"
              }
            />
          </div>
        )}

        {warnings.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
            {warnings.map((warning, index) => (
              <p key={index} className="text-xs text-amber-800 leading-relaxed">
                {warning}
              </p>
            ))}
          </div>
        )}

        {!result && hasPolygon && units.length > 0 && (
          <>
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

            <button
              onClick={onAnalyzeSelected}
              disabled={selectedCount === 0 || previewLoading || analyzing}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzing ? "Auswahl wird analysiert..." : "Analyse starten"}
            </button>
          </>
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
            body="Das Polygon wird serverseitig in Analysezellen zerlegt."
          />
        )}

        {analyzing && (
          <LoadingCard
            title="Batchanalyse läuft"
            body="Die ausgewählten Analysezellen werden ohne LLM-Bericht abgefragt."
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
            <SectionLabel text="Vorschau und Auswahl" />
            {units.map((unit) => {
              const selected = selectedUnitIds.includes(unit.id);
              return (
                <label
                  key={unit.id}
                  className={`flex items-start gap-3 rounded-xl border p-3 cursor-pointer transition-colors ${
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
                      <p className="text-sm font-semibold text-gray-900">{unit.label}</p>
                      <span className="text-[10px] text-gray-500">
                        {formatArea(unit.area_sqm)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">
                      Analysepunkt: {formatCoords(unit.sample_point.lat, unit.sample_point.lng)}
                    </p>
                  </div>
                </label>
              );
            })}
          </div>
        )}

        {result && (
          <div className="space-y-4">
            <div className="space-y-3">
              <SectionLabel text="Zusammenfassung" />
              {result.units_analyzed < units.length && (
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-3">
                  <p className="text-sm font-semibold text-blue-900">
                    Teilreport für die aktuelle Auswahl
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    Export und Übersicht beziehen sich auf {result.units_analyzed} von {units.length} verfügbaren Analysezellen.
                  </p>
                </div>
              )}

              <div className="grid grid-cols-1 gap-2">
                {result.category_rollup.map((entry) => {
                  const meta = CATEGORY_META[entry.category];
                  const riskMeta = RISK_META[entry.highest_risk];
                  return (
                    <div
                      key={entry.category}
                      className="rounded-xl border bg-white p-3"
                      style={{ borderColor: `${riskMeta.color}25` }}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-gray-900">
                            {meta.emoji} {meta.label}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {entry.affected_units.length} betroffene Zellen
                          </p>
                        </div>
                        <RiskBadge level={entry.highest_risk} size="sm" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-3">
              <SectionLabel text="Analysierte Zellen" />
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

function AreaDetailView({
  unit,
  report,
  loading,
  error,
  onBack,
  onRetry,
}: {
  unit: AreaUnitResult;
  report: AnalyzeResponse | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-4 border-b border-gray-100 shrink-0">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 text-xs font-medium text-blue-700 hover:text-blue-800"
          >
            <span aria-hidden="true">←</span>
            Zurück zur Flächenübersicht
          </button>
        </div>
        <div className="p-4">
          <LoadingCard
            title="Detailreport wird geladen"
            body={`Der vollständige Punkt-Report für ${unit.label} wird erzeugt.`}
          />
        </div>
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-4 border-b border-gray-100 shrink-0">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 text-xs font-medium text-blue-700 hover:text-blue-800"
          >
            <span aria-hidden="true">←</span>
            Zurück zur Flächenübersicht
          </button>
        </div>
        <div className="p-4 space-y-3">
          <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
            <p className="font-medium text-sm">Detailreport fehlgeschlagen</p>
            <p className="text-xs mt-1 leading-relaxed">{error}</p>
          </div>
          <button
            onClick={onRetry}
            className="w-full px-3 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-black transition-colors"
          >
            Erneut versuchen
          </button>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-4">
        <InstructionCard
          title="Kein Detailreport verfügbar"
          body="Für diese Analysezelle liegt aktuell noch kein Detailreport vor."
        />
      </div>
    );
  }

  return (
    <ReportPanel
      result={report}
      coords={{ lat: unit.lat, lng: unit.lng }}
      title={unit.label}
      subtitle="Detailreport innerhalb der Flächenanalyse"
      onBack={onBack}
      backLabel="Zurück zur Flächenübersicht"
    />
  );
}

function AreaResultCard({
  unitResult,
  onOpenDetailedReport,
}: {
  unitResult: AreaUnitResult;
  onOpenDetailedReport: (unitId: string) => void;
}) {
  const activeCategories = unitResult.agent_results.filter(
    (agentResult) =>
      agentResult.risk_level !== "NONE" && agentResult.risk_level !== "UNKNOWN"
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900">{unitResult.label}</p>
          <p className="text-xs text-gray-500 mt-1">
            {formatCoords(unitResult.lat, unitResult.lng)}
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
        <p className="text-xs text-gray-500">Keine aktiven Kategorien gemeldet.</p>
      )}

      {unitResult.errors.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-2">
          {unitResult.errors.map((entry, index) => (
            <p key={index} className="text-[11px] text-yellow-800">
              {entry}
            </p>
          ))}
        </div>
      )}

      <button
        onClick={() => onOpenDetailedReport(unitResult.id)}
        className="w-full px-3 py-2 rounded-lg bg-gray-900 text-white text-xs font-medium hover:bg-black transition-colors"
      >
        Detailreport öffnen
      </button>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
        {label}
      </p>
      <div className="mt-2 text-sm font-semibold text-gray-900">{value}</div>
      <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">{note}</p>
    </div>
  );
}

function SectionLabel({ text }: { text: string }) {
  return (
    <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
      {text}
    </h3>
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

function formatCoords(lat: number, lng: number) {
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

function getHighestRisk(unitResults: AreaUnitResult[]): RiskLevel {
  if (unitResults.some((unitResult) => unitResult.overall_risk_level === "HIGH")) {
    return "HIGH";
  }
  if (unitResults.some((unitResult) => unitResult.overall_risk_level === "MEDIUM")) {
    return "MEDIUM";
  }
  if (unitResults.some((unitResult) => unitResult.overall_risk_level === "LOW")) {
    return "LOW";
  }
  if (unitResults.some((unitResult) => unitResult.overall_risk_level === "NONE")) {
    return "NONE";
  }
  return "UNKNOWN";
}
