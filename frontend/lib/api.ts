/**
 * API client for the SiteScope backend.
 */

import type { AnalyzeResponse, DemoLocation } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Run site analysis for a coordinate.
 */
export async function analyzeSite(
  lat: number,
  lng: number
): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Analysis failed (${res.status}): ${text}`);
  }

  return res.json();
}

/**
 * Download PDF report for a coordinate.
 * Returns a Blob that can be saved as a file.
 */
export async function downloadPDF(lat: number, lng: number): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/report/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`PDF generation failed (${res.status}): ${text}`);
  }

  return res.blob();
}

/**
 * Fetch demo locations from the backend.
 */
export async function getDemoLocations(): Promise<DemoLocation[]> {
  const res = await fetch(`${API_BASE}/api/demo`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.locations || [];
}

/**
 * Check backend health.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Helper: trigger browser file download from a Blob.
 */
export function saveBlobAs(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
