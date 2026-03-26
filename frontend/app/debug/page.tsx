"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { ParsedRawData } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const DEFAULT_TEST_POINT = { lat: 48.137, lng: 11.576 };
const TEST_PRESETS = [
  { label: "Marienplatz", lat: 48.137, lng: 11.576 },
  { label: "Straßlach", lat: 47.9898, lng: 11.499 },
  { label: "Englischer Garten", lat: 48.1642, lng: 11.6037 },
];

interface TestPoint {
  lat: number;
  lng: number;
  buffer_m: number;
  bbox_25832: number[];
}

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
  parsed_raw_data?: ParsedRawData | null;
  original_raw_response_preview?: string | null;
}

interface DebugResponse {
  timestamp: string;
  overall_status: "ok" | "degraded" | "critical";
  total_sources: number;
  healthy: number;
  degraded: number;
  failed: number;
  test_point: TestPoint;
  sources: SourceResult[];
}

function formatCoord(value: number) {
  return value.toFixed(6);
}

function readCoordinate(
  rawValue: string | null,
  fallback: number,
  min: number,
  max: number,
) {
  if (!rawValue) return fallback;
  const value = Number.parseFloat(rawValue);
  if (!Number.isFinite(value) || value < min || value > max) return fallback;
  return value;
}

function buildDebugUrl(lat: number, lng: number) {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lng: lng.toString(),
  });
  return `${API_BASE}/api/debug/sources?${params.toString()}`;
}

function StatusIcon({ ok, partial }: { ok: boolean; partial?: boolean }) {
  if (ok) return <span className="text-emerald-500 text-lg">OK</span>;
  if (partial) return <span className="text-amber-500 text-lg">WARN</span>;
  return <span className="text-red-500 text-lg">ERR</span>;
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
      label: "Degraded - Some Sources Unavailable",
    },
    critical: {
      bg: "bg-red-50 border-red-200",
      text: "text-red-800",
      label: "Critical - Multiple Sources Down",
    },
  };

  const current = config[status] ?? config.critical;

  return (
    <div className={`rounded-2xl border px-6 py-5 ${current.bg}`}>
      <div className={`text-2xl font-semibold ${current.text}`}>
        {current.label}
      </div>
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
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-[60px] text-right font-mono text-xs text-slate-500">
        {ms}ms
      </span>
    </div>
  );
}

function DebugContent() {
  const searchParams = useSearchParams();
  const initialLat = readCoordinate(
    searchParams.get("lat"),
    DEFAULT_TEST_POINT.lat,
    -90,
    90,
  );
  const initialLng = readCoordinate(
    searchParams.get("lng") ?? searchParams.get("lon"),
    DEFAULT_TEST_POINT.lng,
    -180,
    180,
  );

  const [data, setData] = useState<DebugResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [latInput, setLatInput] = useState(formatCoord(initialLat));
  const [lngInput, setLngInput] = useState(formatCoord(initialLng));
  const [activeCoords, setActiveCoords] = useState({
    lat: initialLat,
    lng: initialLng,
  });

  const fetchData = useCallback(async (coords: { lat: number; lng: number }) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(buildDebugUrl(coords.lat, coords.lng));
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
    void fetchData(activeCoords);
  }, [activeCoords, fetchData]);

  const toggleExpand = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const submitCoords = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const lat = Number.parseFloat(latInput.replace(",", "."));
    const lng = Number.parseFloat(lngInput.replace(",", "."));

    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setError("Latitude must be between -90 and 90.");
      return;
    }

    if (!Number.isFinite(lng) || lng < -180 || lng > 180) {
      setError("Longitude must be between -180 and 180.");
      return;
    }

    setLatInput(formatCoord(lat));
    setLngInput(formatCoord(lng));
    setActiveCoords({ lat, lng });

    if (typeof window !== "undefined") {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.set("lat", lat.toString());
      nextUrl.searchParams.set("lng", lng.toString());
      window.history.replaceState({}, "", nextUrl);
    }
  };

  const applyPreset = (lat: number, lng: number) => {
    setLatInput(formatCoord(lat));
    setLngInput(formatCoord(lng));
    setError(null);
    setActiveCoords({ lat, lng });

    if (typeof window !== "undefined") {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.set("lat", lat.toString());
      nextUrl.searchParams.set("lng", lng.toString());
      window.history.replaceState({}, "", nextUrl);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#f8fafc,_#eef2ff_45%,_#f8fafc_100%)]">
      <header className="sticky top-0 z-10 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-slate-400 transition-colors hover:text-slate-700"
            >
              ← Back
            </Link>
            <h1 className="text-xl font-bold text-slate-900">
              SiteScope Diagnostics
            </h1>
          </div>
          <button
            onClick={() => void fetchData(activeCoords)}
            disabled={loading}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-all ${
              loading
                ? "cursor-wait bg-slate-100 text-slate-400"
                : "bg-slate-950 text-white hover:bg-slate-800 active:scale-95"
            }`}
          >
            {loading ? "Running checks..." : "Re-run Checks"}
          </button>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6">
        <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-sm backdrop-blur">
          <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Test Coordinates
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-900">
                  Probe the debug sources against any point
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                  The dashboard now parses WMS HTML/GML/text responses into
                  feature fields. Use custom coordinates to check what each
                  source returns at a specific location.
                </p>
              </div>

              <form
                onSubmit={submitCoords}
                className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-[1fr_1fr_auto]"
              >
                <label className="text-sm text-slate-600">
                  Latitude
                  <input
                    value={latInput}
                    onChange={(event) => setLatInput(event.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900 outline-none transition focus:border-slate-400"
                    placeholder="48.137000"
                  />
                </label>
                <label className="text-sm text-slate-600">
                  Longitude
                  <input
                    value={lngInput}
                    onChange={(event) => setLngInput(event.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900 outline-none transition focus:border-slate-400"
                    placeholder="11.576000"
                  />
                </label>
                <button
                  type="submit"
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 sm:self-end"
                >
                  Test coords
                </button>
              </form>

              <div className="flex flex-wrap gap-2">
                {TEST_PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    onClick={() => applyPreset(preset.lat, preset.lng)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700/70">
                Current Probe
              </p>
              <dl className="mt-4 space-y-3 text-sm">
                <MetaRow
                  label="Lat / Lng"
                  value={`${formatCoord(activeCoords.lat)} / ${formatCoord(activeCoords.lng)}`}
                />
                <MetaRow
                  label="BBOX Buffer"
                  value={
                    data?.test_point
                      ? `${data.test_point.buffer_m}m`
                      : "50m"
                  }
                />
                <MetaRow
                  label="EPSG:25832 BBOX"
                  value={
                    data?.test_point?.bbox_25832?.length === 4
                      ? data.test_point.bbox_25832.join(", ")
                      : "Waiting for response"
                  }
                />
                <MetaRow
                  label="Checked At"
                  value={
                    data
                      ? new Date(data.timestamp).toLocaleString("de-DE", {
                          dateStyle: "medium",
                          timeStyle: "medium",
                        })
                      : "Pending"
                  }
                />
              </dl>
            </div>
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <strong>Failed to fetch diagnostics:</strong> {error}
          </div>
        )}

        {loading && !data && (
          <div className="space-y-4">
            <div className="h-24 animate-pulse rounded-2xl bg-slate-200" />
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-28 animate-pulse rounded-2xl bg-slate-200"
              />
            ))}
          </div>
        )}

        {data && (
          <>
            <OverallBanner status={data.overall_status} />

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatCard
                label="Total Sources"
                value={data.total_sources}
                color="text-slate-900"
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

            <div className="space-y-3">
              {data.sources.map((src, idx) => {
                const isOk = src.capabilities_ok && src.data_test_ok;
                const isPartial = src.capabilities_ok && !src.data_test_ok;
                const isExpanded = expanded.has(idx);

                return (
                  <article
                    key={`${src.name}-${idx}`}
                    className={`overflow-hidden rounded-2xl border bg-white/90 shadow-sm transition-all ${
                      isOk
                        ? "border-emerald-100"
                        : isPartial
                        ? "border-amber-100"
                        : "border-red-100"
                    }`}
                  >
                    <button
                      onClick={() => toggleExpand(idx)}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left"
                    >
                      <StatusIcon ok={isOk} partial={isPartial} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-slate-900">
                          {src.name}
                        </div>
                        <div className="truncate font-mono text-xs text-slate-400">
                          {src.url}
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-medium ${
                            src.type === "wms"
                              ? "bg-blue-50 text-blue-700"
                              : "bg-violet-50 text-violet-700"
                          }`}
                        >
                          {src.type.toUpperCase()}
                        </span>
                        <ResponseTimeBar ms={src.response_time_ms} />
                        <svg
                          className={`h-4 w-4 text-slate-400 transition-transform ${
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

                    {isExpanded && (
                      <div className="space-y-4 border-t border-slate-100 px-5 pb-5 pt-4">
                        <div className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
                          <Detail
                            label="Capabilities"
                            value={src.capabilities_ok ? "OK" : "Failed"}
                          />
                          <Detail
                            label="Data Test"
                            value={src.data_test_ok ? "OK" : "Failed"}
                          />
                          <Detail
                            label="Response Time"
                            value={`${src.response_time_ms}ms`}
                          />
                          <Detail
                            label="Layers Tested"
                            value={
                              src.layers_tested.length > 0
                                ? src.layers_tested.join(", ")
                                : "None"
                            }
                          />
                        </div>

                        {src.error && (
                          <div className="rounded-xl bg-red-50 p-3 font-mono text-xs text-red-700 break-all">
                            {src.error}
                          </div>
                        )}

                        {src.parsed_raw_data && (
                          <ParsedRawDataPanel parsedRawData={src.parsed_raw_data} />
                        )}

                        {!src.parsed_raw_data && src.sample_data && (
                          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                              Sample excerpt
                            </div>
                            <p className="font-mono text-xs leading-6 text-slate-600">
                              {src.sample_data}
                            </p>
                          </div>
                        )}

                        {src.original_raw_response_preview && (
                          <details className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Original response
                            </summary>
                            <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-white p-3 font-mono text-xs text-slate-600">
                              {src.original_raw_response_preview}
                            </pre>
                          </details>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function DebugPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-slate-500">Loading diagnostics...</div>
      </div>
    }>
      <DebugContent />
    </Suspense>
  );
}

function ParsedRawDataPanel({
  parsedRawData,
}: {
  parsedRawData: ParsedRawData;
}) {
  return (
    <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
          Parsed {parsedRawData.source_format} response
        </span>
        <span className="rounded-full bg-white px-2 py-1 text-[11px] text-emerald-700">
          {parsedRawData.feature_count} features
        </span>
      </div>

      <div className="space-y-3">
        {parsedRawData.blocks.map((block, index) => (
          <div
            key={`${block.title}-${index}`}
            className="rounded-xl border border-white/80 bg-white p-3"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-slate-800">
                {block.title}
              </span>
              {block.layer_name && (
                <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500">
                  Layer: {block.layer_name}
                </span>
              )}
            </div>

            <div className="space-y-2">
              {block.fields.map((field, fieldIndex) => (
                <div
                  key={`${field.key}-${fieldIndex}`}
                  className="grid gap-x-3 gap-y-1 text-sm leading-6 sm:grid-cols-[180px_1fr]"
                >
                  <span className="font-medium text-slate-500">
                    {field.key}
                  </span>
                  <span className="break-words text-slate-800">
                    {field.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
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
    <div className="rounded-2xl border border-slate-100 bg-white/90 px-5 py-4 shadow-sm">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-slate-400">{label}:</span>
      <span className="text-slate-700">{value}</span>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words font-mono text-xs text-slate-800">{value}</dd>
    </div>
  );
}
