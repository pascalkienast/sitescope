/**
 * SiteScope TypeScript interfaces.
 * Mirrors the backend Pydantic models.
 */

export type RiskLevel = "HIGH" | "MEDIUM" | "LOW" | "NONE" | "UNKNOWN";

export type AgentCategory =
  | "flood"
  | "nature"
  | "heritage"
  | "zoning"
  | "infrastructure";

export interface RawDataField {
  key: string;
  value: string;
}

export interface RawDataBlock {
  title: string;
  layer_name?: string | null;
  fields: RawDataField[];
}

export interface ParsedRawData {
  format: "key_value";
  source_format: "html" | "gml" | "text" | "json" | "unknown";
  feature_count: number;
  blocks: RawDataBlock[];
}

export interface AgentFinding {
  title: string;
  description: string;
  risk_level: RiskLevel;
  evidence: string;
  source_url: string;
  source_name: string;
  layer_name: string;
  parsed_raw_data?: ParsedRawData | null;
  original_raw_response_preview?: string | null;
  raw_data?: string;
}

export interface AgentResult {
  category: AgentCategory;
  agent_name: string;
  risk_level: RiskLevel;
  summary: string;
  findings: AgentFinding[];
  layers_queried: number;
  layers_with_data: number;
  errors: string[];
  execution_time_ms: number;
}

export interface RiskCategoryReport {
  category: AgentCategory;
  category_label: string;
  emoji: string;
  risk_level: RiskLevel;
  summary: string;
  findings: AgentFinding[];
  recommended_actions: string[];
  source_links: string[];
}

export interface RedFlagReport {
  lat: number;
  lng: number;
  address: string;
  overall_risk_level: RiskLevel;
  executive_summary: string;
  key_red_flags: string[];
  categories: RiskCategoryReport[];
  generated_at: string;
  analysis_duration_ms: number;
  agents_run: number;
  total_layers_queried: number;
}

export interface AnalyzeResponse {
  success: boolean;
  report: RedFlagReport | null;
  agent_results: AgentResult[];
  errors: string[];
}

export interface DemoLocation {
  name: string;
  lat: number;
  lng: number;
  expected: string[];
}

/** Risk level display metadata */
export const RISK_META: Record<
  RiskLevel,
  { color: string; bg: string; label: string }
> = {
  HIGH: { color: "#DC2626", bg: "#FEE2E2", label: "High Risk" },
  MEDIUM: { color: "#D97706", bg: "#FEF3C7", label: "Medium Risk" },
  LOW: { color: "#059669", bg: "#D1FAE5", label: "Low Risk" },
  NONE: { color: "#6B7280", bg: "#F3F4F6", label: "No Risk" },
  UNKNOWN: { color: "#9CA3AF", bg: "#F9FAFB", label: "Unknown" },
};

/** Category display metadata */
export const CATEGORY_META: Record<
  AgentCategory,
  { emoji: string; label: string }
> = {
  flood: { emoji: "🌊", label: "Flood & Water Risk" },
  nature: { emoji: "🌿", label: "Nature & Environment" },
  heritage: { emoji: "🏛️", label: "Heritage / Monuments" },
  zoning: { emoji: "📐", label: "Zoning & Land Use" },
  infrastructure: { emoji: "⚡", label: "Infrastructure" },
};
