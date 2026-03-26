"use client";

import { useState, useCallback } from "react";
import type { AnalyzeResponse } from "@/lib/types";
import { RiskBadge } from "./RiskBadge";
import { RiskCategory } from "./RiskCategory";
import { downloadPDF, saveBlobAs } from "@/lib/api";

interface ReportPanelProps {
  result: AnalyzeResponse;
  coords: { lat: number; lng: number };
}

export function ReportPanel({ result, coords }: ReportPanelProps) {
  const [downloading, setDownloading] = useState(false);
  const report = result.report;

  const handleDownloadPDF = useCallback(async () => {
    if (!coords) return;
    setDownloading(true);
    try {
      const blob = await downloadPDF(coords.lat, coords.lng);
      saveBlobAs(
        blob,
        `sitescope-${coords.lat.toFixed(4)}-${coords.lng.toFixed(4)}.pdf`
      );
    } catch (err) {
      alert(
        `PDF download failed: ${
          err instanceof Error ? err.message : "Unknown error"
        }`
      );
    } finally {
      setDownloading(false);
    }
  }, [coords]);

  if (!report) {
    return (
      <div className="p-6">
        <div className="bg-yellow-50 text-yellow-700 p-4 rounded-lg">
          <p className="font-medium">Partial Results</p>
          <p className="text-sm mt-1">
            Report generation failed, but agent data is available.
          </p>
          {result.errors.map((err, i) => (
            <p key={i} className="text-xs mt-1 text-yellow-600">
              {err}
            </p>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Report header — fixed */}
      <div className="p-4 border-b border-gray-100 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-bold text-gray-900">
            🔍 Red Flag Report
          </h2>
          <RiskBadge level={report.overall_risk_level} size="lg" />
        </div>

        <p className="text-xs text-gray-500">
          {coords.lat.toFixed(4)}, {coords.lng.toFixed(4)}
          {report.address ? ` — ${report.address}` : ""}
          <span className="mx-1.5">·</span>
          {report.agents_run} agents
          <span className="mx-1.5">·</span>
          {report.analysis_duration_ms}ms
        </p>

        {/* PDF download */}
        <button
          onClick={handleDownloadPDF}
          disabled={downloading}
          className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-1.5 
            bg-blue-600 text-white text-xs font-medium rounded-lg 
            hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {downloading ? (
            <>
              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Generating PDF…
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download PDF Report
            </>
          )}
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto report-scroll p-4 space-y-4">
        {/* Executive Summary */}
        <div className="bg-blue-50 border-l-4 border-blue-500 p-3 rounded-r-lg">
          <h3 className="text-xs font-semibold text-blue-900 mb-1">
            Executive Summary
          </h3>
          <p className="text-sm text-blue-800 leading-relaxed">
            {report.executive_summary}
          </p>
        </div>

        {/* Key Red Flags */}
        {report.key_red_flags.length > 0 && (
          <div className="bg-red-50 border border-red-200 p-3 rounded-lg">
            <h3 className="text-xs font-semibold text-red-900 mb-2">
              🚩 Key Red Flags
            </h3>
            <ul className="space-y-1">
              {report.key_red_flags.map((flag, i) => (
                <li
                  key={i}
                  className="flex gap-2 text-sm text-red-800"
                >
                  <span className="text-red-400 shrink-0">•</span>
                  {flag}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Risk Categories */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
            Detailed Analysis
          </h3>
          {report.categories.map((cat) => (
            <RiskCategory key={cat.category} category={cat} />
          ))}
        </div>

        {/* Errors section */}
        {result.errors.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 p-3 rounded-lg">
            <h3 className="text-xs font-semibold text-yellow-800 mb-1">
              ⚠️ Warnings
            </h3>
            {result.errors.map((err, i) => (
              <p key={i} className="text-xs text-yellow-700">
                {err}
              </p>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="pt-3 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 leading-relaxed">
            This report was generated automatically using publicly available
            geodata from Bayern LfU, BLfD, Open-Meteo, and OpenTopoData.
            It is a preliminary screening tool and does not replace
            professional due diligence.
          </p>
        </div>
      </div>
    </div>
  );
}
