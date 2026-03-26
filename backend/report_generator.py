"""
Report Generator — uses MiniMax M2.5 (via OpenRouter) to produce
a structured Red Flag Report from agent outputs.
"""

import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from geo.parsers import parsed_raw_data_to_text
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

You will receive structured data from multiple analysis agents (flood risk, nature protection, heritage, etc.).

## STRICT DATA-GROUNDING RULES (MANDATORY)

1. You MUST ONLY reference findings explicitly listed in the agent data below. If an agent found NONE/no data for a category, say exactly that — do NOT speculate about risks that are not evidenced by actual WMS query results.
2. For each claim in your summary, cite the specific agent finding that supports it (e.g. "According to the Flood Agent, the site is in an HQ100 zone").
3. If all agents returned NONE/no findings, the executive summary MUST state: "No significant risks were identified from available geodata sources. All queried WMS layers returned no data for this location."
4. Do NOT invent, assume, or speculate about risks. If a WMS layer returned no data, that means NO risk was detected for that layer — do not suggest it "might still exist" or add caveats about undetected risks beyond a single standard disclaimer.
5. The "key_red_flags" array MUST be empty if no agent found any HIGH or MEDIUM risk findings.
6. The overall_risk_level MUST reflect the actual highest risk level found across all agent findings. If all findings are NONE/LOW, the overall level must be LOW or NONE.
7. Do NOT fabricate source URLs. Only include URLs that appear in the agent data.

## YOUR TASKS

1. Synthesize the findings into a clear, professional executive summary that ONLY references actual data
2. List key red flags — ONLY those backed by actual HIGH/MEDIUM findings from agents
3. Determine overall risk rating based SOLELY on the agent findings
4. Suggest recommended actions for each risk category

Write in clear, professional English suitable for a due diligence report. Reference German laws (WHG, BayNatSchG, BayDSchG) only when the agent data contains findings that trigger those laws.

Respond ONLY with valid JSON matching this exact structure:
{
  "overall_risk_level": "HIGH" | "MEDIUM" | "LOW",
  "executive_summary": "2-3 paragraph summary citing specific agent findings",
  "key_red_flags": ["ONLY issues backed by actual agent findings with HIGH/MEDIUM risk"],
  "categories": [
    {
      "category": "flood" | "nature" | "heritage" | "zoning" | "infrastructure",
      "recommended_actions": ["specific next steps for this category"],
      "source_links": ["ONLY URLs from agent data, never fabricated"]
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

        # === DEBUG: Log full LLM request ===
        logger.debug("=" * 80)
        logger.debug("LLM REQUEST — Model: %s", self.model)
        logger.debug("=" * 80)
        logger.debug("SYSTEM PROMPT:\n%s", SYSTEM_PROMPT)
        logger.debug("-" * 80)
        logger.debug("USER PROMPT (agent data):\n%s", data_summary)
        logger.debug("-" * 80)
        logger.debug("Parameters: temperature=0.3, max_tokens=2000")
        logger.debug("=" * 80)

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

            # === DEBUG: Log full LLM response ===
            logger.debug("=" * 80)
            logger.debug("LLM RESPONSE — Raw:")
            logger.debug("%s", raw_content)
            if hasattr(response, "usage") and response.usage:
                logger.debug(
                    "Token usage: prompt=%s, completion=%s, total=%s",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    response.usage.total_tokens,
                )
            logger.debug("=" * 80)

            # Try to extract JSON from the response (handle markdown code blocks)
            json_str = raw_content
            if "```json" in json_str:
                json_str = json_str.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in json_str:
                json_str = json_str.split("```", 1)[1].split("```", 1)[0]

            parsed = json.loads(json_str.strip())

            # === DEBUG: Log parsed JSON ===
            logger.debug("LLM PARSED JSON:\n%s", json.dumps(parsed, indent=2, ensure_ascii=False))

            return parsed

        except json.JSONDecodeError as e:
            logger.warning("LLM returned invalid JSON: %s", e)
            logger.debug("LLM raw content that failed to parse:\n%s", raw_content)
            return None
        except Exception as e:
            logger.warning("LLM call failed: %s — using fallback", e)
            return None

    def _format_agent_data(
        self, lat: float, lng: float, agent_results: list[AgentResult]
    ) -> str:
        """Format agent results as a structured text prompt for the LLM.

        Includes raw evidence, source URLs for citation, and an explicit
        section listing layers that returned NO data (so the LLM knows
        what was checked and found empty vs. what was never checked).
        """
        lines = [
            f"# Site Analysis Data for ({lat:.4f}, {lng:.4f})",
            f"Location: Bavaria, Germany",
            f"Analysis Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "IMPORTANT: The data below is the ONLY source of truth. "
            "Do NOT add any information that is not explicitly present here.",
            "",
        ]

        # Track layers with no data across all agents
        all_empty_layers: list[str] = []
        all_queried_count = 0
        all_with_data_count = 0

        for result in agent_results:
            meta = CATEGORY_META.get(result.category, {})
            emoji = meta.get("emoji", "")
            label = meta.get("label", result.category.value)

            lines.append(f"## {emoji} {label}")
            lines.append(f"Overall Risk: {result.risk_level.value}")
            lines.append(f"Agent: {result.agent_name}")
            lines.append(f"Layers Queried: {result.layers_queried}")
            lines.append(f"Layers With Data: {result.layers_with_data}")
            lines.append(f"Summary: {result.summary}")
            lines.append("")

            all_queried_count += result.layers_queried
            all_with_data_count += result.layers_with_data

            if not result.findings:
                lines.append("Findings: NONE — no data returned from any queried layer.")
                lines.append("")
            else:
                # Separate findings with actual data vs NONE findings
                positive_findings = [f for f in result.findings if f.risk_level != RiskLevel.NONE]
                none_findings = [f for f in result.findings if f.risk_level == RiskLevel.NONE]

                for i, finding in enumerate(result.findings, 1):
                    lines.append(f"### Finding {i}: {finding.title}")
                    lines.append(f"Risk Level: {finding.risk_level.value}")
                    lines.append(f"Description: {finding.description}")
                    if finding.evidence:
                        lines.append(f"Evidence (raw): {finding.evidence}")
                    if finding.layer_name:
                        lines.append(f"WMS Layer: {finding.layer_name}")
                    if finding.source_name:
                        lines.append(f"Source: {finding.source_name}")
                    if finding.source_url:
                        lines.append(f"Source URL: {finding.source_url}")
                    parsed_raw_data = parsed_raw_data_to_text(
                        finding.parsed_raw_data,
                        max_blocks=2,
                        max_fields_per_block=8,
                    )
                    if parsed_raw_data:
                        lines.append(f"Raw Data (parsed): {parsed_raw_data}")
                    lines.append("")

                # Track layers that returned nothing
                for f in none_findings:
                    layer_desc = f.layer_name or f.title
                    all_empty_layers.append(f"{label}: {layer_desc}")

            if result.errors:
                lines.append(f"Errors: {', '.join(result.errors)}")
                lines.append("")

        # Summary section: what was NOT found
        lines.append("---")
        lines.append("## Summary of Data Coverage")
        lines.append(f"Total WMS/API layers queried: {all_queried_count}")
        lines.append(f"Layers that returned data: {all_with_data_count}")
        lines.append(f"Layers that returned NO data: {all_queried_count - all_with_data_count}")
        lines.append("")

        if all_empty_layers:
            lines.append("### Layers Queried But Found EMPTY (no risk detected):")
            for layer in all_empty_layers:
                lines.append(f"  - {layer}")
            lines.append("")

        if all_with_data_count == 0:
            lines.append(
                "⚠️ ALL queried layers returned NO data for this location. "
                "This means no risks were detected by any geodata source. "
                "Your report MUST reflect this: overall risk should be LOW/NONE "
                "and no red flags should be listed."
            )
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
