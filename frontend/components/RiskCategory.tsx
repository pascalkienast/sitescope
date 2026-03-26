"use client";

import { useState } from "react";
import type {
  RiskCategoryReport,
  AgentFinding,
  ParsedRawData,
} from "@/lib/types";
import { RiskBadge } from "./RiskBadge";
import { RISK_META } from "@/lib/types";

interface RiskCategoryProps {
  category: RiskCategoryReport;
}

export function RiskCategory({ category }: RiskCategoryProps) {
  const [expanded, setExpanded] = useState(
    // Auto-expand categories with HIGH/MEDIUM risk
    category.risk_level === "HIGH" || category.risk_level === "MEDIUM"
  );

  const riskMeta = RISK_META[category.risk_level];

  return (
    <div
      className="border rounded-lg overflow-hidden transition-all"
      style={{ borderColor: `${riskMeta.color}30` }}
    >
      {/* Category header — clickable */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 transition-colors text-left"
      >
        <span className="text-xl shrink-0">{category.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-gray-900 truncate">
            {category.category_label}
          </div>
          {!expanded && (
            <p className="text-xs text-gray-500 truncate mt-0.5">
              {category.summary}
            </p>
          )}
        </div>
        <RiskBadge level={category.risk_level} size="sm" />
        <svg
          className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-100 p-3 space-y-3">
          <p className="text-sm text-gray-600">{category.summary}</p>

          {/* Findings */}
          {category.findings.map((finding, i) => (
            <FindingCard key={i} finding={finding} />
          ))}

          {/* Recommended actions */}
          {category.recommended_actions.length > 0 && (
            <div className="mt-3">
              <h4 className="text-xs font-semibold text-gray-700 mb-1.5">
                Recommended Actions
              </h4>
              <ul className="space-y-1">
                {category.recommended_actions.map((action, i) => (
                  <li
                    key={i}
                    className="flex gap-2 text-xs text-gray-600"
                  >
                    <span className="text-blue-500 shrink-0">→</span>
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Source links */}
          {category.source_links.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-100">
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Sources
              </span>
              <div className="flex flex-wrap gap-1 mt-1">
                {category.source_links.map((link, i) => (
                  <a
                    key={i}
                    href={link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-blue-600 hover:text-blue-800 
                      bg-blue-50 px-1.5 py-0.5 rounded truncate max-w-[200px]"
                    title={link}
                  >
                    {new URL(link).hostname}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FindingCard({ finding }: { finding: AgentFinding }) {
  const [showRaw, setShowRaw] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const riskMeta = RISK_META[finding.risk_level];
  const hasParsedRaw =
    !!finding.parsed_raw_data && finding.parsed_raw_data.blocks.length > 0;
  const hasLegacyRaw = !hasParsedRaw && !!finding.raw_data;
  const hasOriginalPreview = !!finding.original_raw_response_preview;

  return (
    <div
      className="rounded-md p-2.5 text-sm"
      style={{
        backgroundColor: `${riskMeta.bg}`,
        borderLeft: `3px solid ${riskMeta.color}`,
      }}
    >
      <div className="flex items-start gap-2">
        <RiskBadge level={finding.risk_level} size="sm" />
        <span className="font-medium text-xs text-gray-900 leading-snug">
          {finding.title}
        </span>
      </div>

      <p className="text-xs text-gray-600 mt-1.5 leading-relaxed">
        {finding.description}
      </p>

      {finding.evidence && (
        <p className="text-[10px] text-gray-500 mt-1.5 italic">
          Evidence: {finding.evidence}
        </p>
      )}

      {finding.source_name && (
        <p className="text-[10px] text-gray-400 mt-1">
          Source: {finding.source_name}
        </p>
      )}

      {(hasParsedRaw || hasLegacyRaw) && (
        <div className="mt-2 space-y-2">
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="text-[10px] text-blue-600 hover:underline"
          >
            {showRaw ? "Hide raw data" : "Show raw data"}
          </button>

          {showRaw && hasParsedRaw && finding.parsed_raw_data && (
            <ParsedRawDataView parsedRawData={finding.parsed_raw_data} />
          )}

          {showRaw && hasLegacyRaw && (
            <pre className="text-[9px] text-gray-500 bg-white/70 p-2 rounded overflow-x-auto">
              {finding.raw_data}
            </pre>
          )}
        </div>
      )}

      {hasOriginalPreview && (
        <div className="mt-2">
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className="text-[10px] text-gray-500 hover:underline"
          >
            {showOriginal ? "Hide original response" : "Original response"}
          </button>

          {showOriginal && (
            <pre className="text-[9px] text-gray-500 mt-1 bg-white/70 p-2 rounded overflow-x-auto whitespace-pre-wrap break-words">
              {finding.original_raw_response_preview}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function ParsedRawDataView({ parsedRawData }: { parsedRawData: ParsedRawData }) {
  return (
    <div className="rounded-md bg-white/70 border border-white/80 p-2 space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-gray-400">
        Parsed {parsedRawData.source_format} response
      </p>

      {parsedRawData.blocks.map((block, index) => (
        <div key={`${block.title}-${index}`} className="rounded border border-gray-200 bg-white p-2">
          <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
            <span className="text-[10px] font-semibold text-gray-700">
              {block.title}
            </span>
            {block.layer_name && (
              <span className="text-[9px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                Layer: {block.layer_name}
              </span>
            )}
          </div>

          <div className="space-y-1">
            {block.fields.map((field, fieldIndex) => (
              <div
                key={`${field.key}-${fieldIndex}`}
                className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-[10px] leading-snug"
              >
                <span className="font-medium text-gray-600">
                  {field.key}
                </span>
                <span className="text-gray-700 break-words">
                  {field.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
