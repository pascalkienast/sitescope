"use client";

import type { RiskLevel } from "@/lib/types";
import { RISK_META } from "@/lib/types";

interface RiskBadgeProps {
  level: RiskLevel;
  size?: "sm" | "md" | "lg";
}

export function RiskBadge({ level, size = "md" }: RiskBadgeProps) {
  const meta = RISK_META[level];

  const sizeClasses = {
    sm: "text-[10px] px-1.5 py-0.5",
    md: "text-xs px-2.5 py-1",
    lg: "text-sm px-3 py-1.5",
  };

  return (
    <span
      className={`inline-flex items-center font-bold rounded-full ${sizeClasses[size]}`}
      style={{
        color: meta.color,
        backgroundColor: meta.bg,
      }}
    >
      {level}
    </span>
  );
}
