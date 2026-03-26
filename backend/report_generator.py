"""
Report Generator — uses MiniMax M2.5 (via OpenRouter) to produce
a structured Red Flag Report from agent outputs.
"""

import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from models import (
    AgentResult,
    RedFlagReport,
    RiskCategoryReport,
    RiskLevel,
    AgentCategory,
)
from config import get_settings, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

CATEGORY_META = {
    AgentCategory.FLOOD: {"label": "Flood & Water Risk", "emoji": "🌊"},
    AgentCategory.NATURE: {"label": "Nature & Environment", "emoji": "🌿"},
    AgentCategory.HERITAGE: {"label": "Heritage / Monuments", "emoji": "🏛️"},
    AgentCategory.ZONING: {"label": "Zoning & Land Use", "emoji": "📐"},
    AgentCategory.INFRASTRUCTURE: {"label": "Infrastructure", "emoji": "⚡"},
}

SYSTEM_PROMPT = """You are SiteScope, an expert site due diligence analyst specializing in German real estate and construction law.

You are generating a Red Flag Report — a structured risk assessment for a specific geographic location in Bavaria, Germany.

You will receive structured data from multiple analysis agents (flood risk, nature protection, heritage, etc.). Your job is to:

1. Synthesize the findings into a clear, professional executive summary
2. Identify the key red flags (most critical risks)
3. Determine an overall risk rating (HIGH, MEDIUM, LOW)
4. Suggest recommended actions for each risk category

Write in clear, professional English suitable for a due diligence report. Be specific about regulatory implications (cite German laws like WHG, BayNatSchG, BayDSchG where relevant). Do not invent data — only reference what the agents found.

Respond ONLY with valid JSON matching this exact structure:
{
  "overall_risk_level": "HIGH" | "MEDIUM" | "LOW",
  "executive_summary": "2-3 paragraph summary of key findings",
  "key_red_flags": ["list of the most critical issues"],
  "categories": [
    {
      "category": "flood" | "nature" | "heritage" | "zoning" | "infrastructure",
      "recommended_actions": ["specific next steps for this category"],
      "source_links": ["relevant authority portal URLs"]
    }
  ]
}"""


class ReportGenerator:
    """Generates Red Flag Reports using MiniMax M2.5 via OpenRouter."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key,
        )
        self.model = OPENROUTER_MODEL

    async def generate(
        self,
        lat: float,
        lng: float,
        agent_results: list[AgentResult],
    ) -> RedFlagReport:
        """
        Generate a complete Red Flag Report from agent results.

        Uses the LLM for executive summary, risk assessment, and
        recommendations. Falls back to rule-based generation if
        the LLM is unavailable.
        """
        # Build per-category reports from agent data
        category_reports = self._build_category_reports(agent_results)

        # Try LLM-enhanced report generation
        llm_analysis = await self._get_llm_analysis(lat, lng, agent_results)

        if llm_analysis:
            return self._merge_llm_with_data(
                lat, lng, category_reports, llm_analysis
            )
        else:
            # Fallback: rule-based report without LLM
            return self._build_fallback_report(lat, lng, category_reports)

    def _build_category_reports(
        self, agent_results: list[AgentResult]
    ) -> list[RiskCategoryReport]:
        """Build per-category report sections from agent data."""
        reports = []
        for result in agent_results:
            meta = CATEGORY_META.get(
                result.category,
                {"label": result.category.value, "emoji": "❓"},
            )
            reports.append(
                RiskCategoryReport(
                    category=result.category,
                    category_label=meta["label"],
                    emoji=meta["emoji"],
                    risk_level=result.risk_level,
                    summary=result.summary,
                    findings=result.findings,
                    recommended_actions=[],
                    source_links=[
                        f.source_url for f in result.findings if f.source_url
                    ],
                )
            )
        return reports

    async def _get_llm_analysis(
        self, lat: float, lng: float, agent_results: list[AgentResult]
    ) -> dict | None:
        """Call MiniMax M2.5 via OpenRouter for report synthesis."""
        settings = get_settings()
        if not settings.openrouter_api_key:
            logger.warning("No OPENROUTER_API_KEY set — using fallback report generation")
            return None

        # Build the data summary for the LLM
        data_summary = self._format_agent_data(lat, lng, agent_results)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": data_summary},
                ],
                temperature=0.3,
                max_tokens=2000,
                extra_headers={
                    "HTTP-Referer": "https://sitescope.dev",
                    "X-Title": "SiteScope Red Flag Report",
                },
            )

            raw_content = response.choices[0].message.content.strip()

            # Try to extract JSON from the response (handle markdown code blocks)
            json_str = raw_content
            if "```json" in json_str:
                json_str = json_str.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in json_str:
                json_str = json_str.split("```", 1)[1].split("```", 1)[0]

            return json.loads(json_str.strip())

        except json.JSONDecodeError as e:
            logger.warning("LLM returned invalid JSON: %s", e)
            return None
        except Exception as e:
            logger.warning("LLM call failed: %s — using fallback", e)
            return None

    def _format_agent_data(
        self, lat: float, lng: float, agent_results: list[AgentResult]
    ) -> str:
        """Format agent results as a structured text prompt for the LLM."""
        lines = [
            f"# Site Analysis Data for ({lat:.4f}, {lng:.4f})",
            f"Location: Bavaria, Germany",
            f"Analysis Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        for result in agent_results:
            meta = CATEGORY_META.get(result.category, {})
            emoji = meta.get("emoji", "")
            label = meta.get("label", result.category.value)

            lines.append(f"## {emoji} {label}")
            lines.append(f"Overall Risk: {result.risk_level.value}")
            lines.append(f"Agent: {result.agent_name}")
            lines.append(f"Summary: {result.summary}")
            lines.append("")

            for i, finding in enumerate(result.findings, 1):
                lines.append(f"### Finding {i}: {finding.title}")
                lines.append(f"Risk Level: {finding.risk_level.value}")
                lines.append(f"Description: {finding.description}")
                if finding.evidence:
                    lines.append(f"Evidence: {finding.evidence}")
                if finding.source_name:
                    lines.append(f"Source: {finding.source_name}")
                lines.append("")

            if result.errors:
                lines.append(f"Errors: {', '.join(result.errors)}")
                lines.append("")

        return "\n".join(lines)

    def _merge_llm_with_data(
        self,
        lat: float,
        lng: float,
        category_reports: list[RiskCategoryReport],
        llm_analysis: dict,
    ) -> RedFlagReport:
        """Merge LLM analysis with agent data into the final report."""
        # Apply LLM recommendations to category reports
        llm_categories = {
            c.get("category"): c
            for c in llm_analysis.get("categories", [])
            if isinstance(c, dict)
        }

        for report in category_reports:
            llm_cat = llm_categories.get(report.category.value, {})
            if llm_cat:
                report.recommended_actions = llm_cat.get("recommended_actions", [])
                extra_links = llm_cat.get("source_links", [])
                # Merge unique links
                existing = set(report.source_links)
                for link in extra_links:
                    if link not in existing:
                        report.source_links.append(link)

        overall_str = llm_analysis.get("overall_risk_level", "UNKNOWN")
        try:
            overall_risk = RiskLevel(overall_str)
        except ValueError:
            overall_risk = RiskLevel.UNKNOWN

        return RedFlagReport(
            lat=lat,
            lng=lng,
            overall_risk_level=overall_risk,
            executive_summary=llm_analysis.get("executive_summary", ""),
            key_red_flags=llm_analysis.get("key_red_flags", []),
            categories=category_reports,
            generated_at=datetime.now(timezone.utc).isoformat(),
            agents_run=len(category_reports),
            total_layers_queried=sum(
                len(c.findings) for c in category_reports
            ),
        )

    def _build_fallback_report(
        self,
        lat: float,
        lng: float,
        category_reports: list[RiskCategoryReport],
    ) -> RedFlagReport:
        """Build a report without LLM — pure rule-based."""
        # Determine overall risk
        risk_priority = {
            RiskLevel.HIGH: 4,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 2,
            RiskLevel.NONE: 1,
            RiskLevel.UNKNOWN: 0,
        }
        if category_reports:
            overall = max(
                category_reports,
                key=lambda c: risk_priority.get(c.risk_level, 0),
            ).risk_level
        else:
            overall = RiskLevel.UNKNOWN

        # Build summary from findings
        red_flags = []
        for cat in category_reports:
            for f in cat.findings:
                if f.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
                    red_flags.append(f"{cat.emoji} {f.title}")

        summary_parts = [
            f"Site analysis for coordinates ({lat:.4f}, {lng:.4f}) in Bavaria, Germany.",
        ]
        if red_flags:
            summary_parts.append(
                f"Identified {len(red_flags)} potential risk(s) requiring attention."
            )
        else:
            summary_parts.append("No significant risks identified at this location.")

        return RedFlagReport(
            lat=lat,
            lng=lng,
            overall_risk_level=overall,
            executive_summary=" ".join(summary_parts),
            key_red_flags=red_flags,
            categories=category_reports,
            generated_at=datetime.now(timezone.utc).isoformat(),
            agents_run=len(category_reports),
            total_layers_queried=sum(
                len(c.findings) for c in category_reports
            ),
        )
