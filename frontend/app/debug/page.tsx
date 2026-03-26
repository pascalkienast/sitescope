"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface SourceResult {
  name: string;
  key?: string;
  type: string;
  url: string;
  capabilities_ok: boolean;
  data_test_ok: boolean;
  response_time_ms: number;
  error: string | null;
  layers_tested: string[];
  sample_data: string | null;
}

interface DebugResponse {
  timestamp: string;
  overall_status: "ok" | "degraded" | "critical";
  total_sources: number;
  healthy: number;
  degraded: number;
  failed: number;
  sources: SourceResult[];
}

function StatusIcon({ ok, partial }: { ok: boolean; partial?: boolean }) {
  if (ok) return <span className="text-emerald-500 text-lg">✅</span>;
  if (partial) return <span className="text-amber-500 text-lg">⚠️</span>;
  return <span className="text-red-500 text-lg">❌</span>;
}

function OverallBanner({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    ok: {
      bg: "bg-emerald-50 border-emerald-200",
      text: "text-emerald-800",
      label: "All Systems Operational",
    },
    degraded: {
      bg: "bg-amber-50 border-amber-200",
      text: "text-amber-800",
      label: "Degraded — Some Sources Unavailable",
    },
    critical: {
      bg: "bg-red-50 border-red-200",
      text: "text-red-800",
      label: "Critical — Multiple Sources Down",
    },
  };

  const c = config[status] ?? config.critical;

  return (
    <div className={`rounded-xl border-2 px-6 py-4 ${c.bg}`}>
      <div className={`text-xl font-bold ${c.text}`}>{c.label}</div>
    </div>
  );
}

function ResponseTimeBar({ ms }: { ms: number }) {
  const max = 15000;
  const pct = Math.min((ms / max) * 100, 100);
  const color =
    ms < 2000 ? "bg-emerald-400" : ms < 5000 ? "bg-amber-400" : "bg-red-400";

  return (
    <div className="flex items-center gap-2 min-w-[140px]">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 font-mono w-[60px] text-right">
        {ms}ms
      </span>
    </div>
  );
}

export default function DebugPage() {
  const [data, setData] = useState<DebugResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/debug/sources`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const json: DebugResponse = await res.json();
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const toggleExpand = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-gray-400 hover:text-gray-700 transition-colors"
            >
              ← Back
            </Link>
            <h1 className="text-xl font-bold text-gray-900">
              🔬 SiteScope Diagnostics
            </h1>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              loading
                ? "bg-gray-100 text-gray-400 cursor-wait"
                : "bg-gray-900 text-white hover:bg-gray-700 active:scale-95"
            }`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    className="opacity-25"
                  />
                  <path
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    className="opacity-75"
                  />
                </svg>
                Running checks…
              </span>
            ) : (
              "🔄 Re-run Checks"
            )}
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800">
            <strong>Failed to fetch diagnostics:</strong> {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !data && (
          <div className="space-y-4">
            <div className="h-16 bg-gray-200 rounded-xl animate-pulse" />
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-20 bg-gray-200 rounded-xl animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Results */}
        {data && (
          <>
            {/* Overall banner */}
            <OverallBanner status={data.overall_status} />

            {/* Summary stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard
                label="Total Sources"
                value={data.total_sources}
                color="text-gray-900"
              />
              <StatCard
                label="Healthy"
                value={data.healthy}
                color="text-emerald-600"
              />
              <StatCard
                label="Degraded"
                value={data.degraded}
                color="text-amber-600"
              />
              <StatCard
                label="Failed"
                value={data.failed}
                color="text-red-600"
              />
            </div>

            {/* Timestamp */}
            <p className="text-xs text-gray-400 text-right">
              Last check:{" "}
              {new Date(data.timestamp).toLocaleString("de-DE", {
                dateStyle: "medium",
                timeStyle: "medium",
              })}
            </p>

            {/* Source cards */}
            <div className="space-y-3">
              {data.sources.map((src, idx) => {
                const isOk = src.capabilities_ok && src.data_test_ok;
                const isPartial = src.capabilities_ok && !src.data_test_ok;
                const isExpanded = expanded.has(idx);

                return (
                  <div
                    key={idx}
                    className={`bg-white rounded-xl border transition-all ${
                      isOk
                        ? "border-emerald-100"
                        : isPartial
                        ? "border-amber-100"
                        : "border-red-100"
                    }`}
                  >
                    {/* Main row */}
                    <button
                      onClick={() => toggleExpand(idx)}
                      className="w-full text-left px-5 py-4 flex items-center gap-4"
                    >
                      <StatusIcon ok={isOk} partial={isPartial} />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 truncate">
                          {src.name}
                        </div>
                        <div className="text-xs text-gray-400 font-mono truncate">
                          {src.url}
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span
                          className={`text-xs px-2 py-1 rounded-full font-medium ${
                            src.type === "wms"
                              ? "bg-blue-50 text-blue-700"
                              : "bg-purple-50 text-purple-700"
                          }`}
                        >
                          {src.type.toUpperCase()}
                        </span>
                        <ResponseTimeBar ms={src.response_time_ms} />
                        <svg
                          className={`w-4 h-4 text-gray-400 transition-transform ${
                            isExpanded ? "rotate-180" : ""
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={2}
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </div>
                    </button>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="px-5 pb-4 pt-0 border-t border-gray-100 space-y-2">
                        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
                          <Detail
                            label="Capabilities"
                            value={src.capabilities_ok ? "✅ OK" : "❌ Failed"}
                          />
                          <Detail
                            label="Data Test"
                            value={src.data_test_ok ? "✅ OK" : "❌ Failed"}
                          />
                          <Detail
                            label="Response Time"
                            value={`${src.response_time_ms}ms`}
                          />
                          {src.layers_tested.length > 0 && (
                            <Detail
                              label="Layers Tested"
                              value={src.layers_tested.join(", ")}
                            />
                          )}
                        </div>

                        {src.error && (
                          <div className="bg-red-50 rounded-lg p-3 text-xs text-red-700 font-mono break-all">
                            {src.error}
                          </div>
                        )}

                        {src.sample_data && (
                          <div>
                            <div className="text-xs font-medium text-gray-500 mb-1">
                              Sample Data
                            </div>
                            <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 font-mono whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                              {src.sample_data}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 px-4 py-3">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-400">{label}:</span>
      <span className="text-gray-700">{value}</span>
    </div>
  );
}
