"use client";

import { useState } from "react";
import type { RiskCategoryReport, AgentFinding } from "@/lib/types";
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
  const riskMeta = RISK_META[finding.risk_level];

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

      {finding.raw_data && (
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="text-[10px] text-blue-600 mt-1 hover:underline"
        >
          {showRaw ? "Hide raw data" : "Show raw data"}
        </button>
      )}
      {showRaw && finding.raw_data && (
        <pre className="text-[9px] text-gray-500 mt-1 bg-white/60 p-2 rounded overflow-x-auto">
          {finding.raw_data}
        </pre>
      )}
    </div>
  );
}
