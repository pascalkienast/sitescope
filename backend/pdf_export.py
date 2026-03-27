"""
PDF export — renders the Red Flag Report as a styled PDF via WeasyPrint.
"""

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from models import AreaPDFRequest, RedFlagReport, RiskLevel
from risk import highest_risk

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
CATEGORY_LABELS = {
    "flood": "Hochwasser & Wasser",
    "nature": "Natur & Umwelt",
    "heritage": "Denkmalschutz",
    "zoning": "Planung & Nutzung",
    "infrastructure": "Infrastruktur",
}


def render_report_pdf(report: RedFlagReport) -> bytes:
    """
    Render a RedFlagReport to PDF bytes.

    Uses Jinja2 to generate HTML from the report template,
    then converts to PDF via WeasyPrint.
    """
    env = _build_environment()
    template = env.get_template("report.html")
    html_content = template.render(
        report=report,
        RiskLevel=RiskLevel,
    )

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes


def render_area_report_pdf(request: AreaPDFRequest) -> bytes:
    """Render an analyzed area selection to PDF bytes."""
    env = _build_environment()
    template = env.get_template("area_report.html")

    unit_lookup = {unit.id: unit for unit in request.units}
    unit_sections = []
    analyzed_area_sqm = 0.0

    for unit_result in request.analysis.unit_results:
        unit = unit_lookup[unit_result.id]
        analyzed_area_sqm += unit.area_sqm
        active_agents = [
            {
                "label": CATEGORY_LABELS.get(agent_result.category, agent_result.category),
                "risk_level": risk_token(agent_result.risk_level),
                "summary": agent_result.summary,
            }
            for agent_result in unit_result.agent_results
            if agent_result.risk_level not in (RiskLevel.NONE, RiskLevel.UNKNOWN)
        ]

        unit_sections.append(
            {
                "id": unit_result.id,
                "label": unit_result.label,
                "coords": format_coords(unit_result.lat, unit_result.lng),
                "area_label": format_area(unit.area_sqm),
                "risk_level": risk_token(unit_result.overall_risk_level),
                "active_agents": active_agents,
                "errors": unit_result.errors,
            }
        )

    html_content = template.render(
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
        overall_risk=risk_token(
            highest_risk(
                unit_result.overall_risk_level
                for unit_result in request.analysis.unit_results
            )
        ),
        polygon_points=max(len(request.polygon.coordinates[0]) - 1, 0),
        units_total=len(request.units),
        units_analyzed=len(request.analysis.unit_results),
        coverage_label=(
            f"{len(request.analysis.unit_results)} von {len(request.units)} Analysezellen analysiert"
        ),
        area_total_label=format_area(sum(unit.area_sqm for unit in request.units)),
        area_analyzed_label=format_area(analyzed_area_sqm),
        warnings=request.analysis.warnings,
        rollup=[
            {
                "label": CATEGORY_LABELS.get(entry.category, entry.category),
                "risk_level": risk_token(entry.highest_risk),
                "affected_units_count": len(entry.affected_units),
            }
            for entry in request.analysis.category_rollup
        ],
        unit_sections=unit_sections,
    )

    return HTML(string=html_content).write_pdf()


def risk_color(level: RiskLevel) -> str:
    """Map risk level to CSS color."""
    return {
        RiskLevel.HIGH: "#DC2626",
        RiskLevel.MEDIUM: "#F59E0B",
        RiskLevel.LOW: "#10B981",
        RiskLevel.NONE: "#6B7280",
        RiskLevel.UNKNOWN: "#9CA3AF",
    }.get(level, "#6B7280")


def risk_bg(level: RiskLevel) -> str:
    """Map risk level to background CSS color."""
    return {
        RiskLevel.HIGH: "#FEE2E2",
        RiskLevel.MEDIUM: "#FEF3C7",
        RiskLevel.LOW: "#D1FAE5",
        RiskLevel.NONE: "#F3F4F6",
        RiskLevel.UNKNOWN: "#F9FAFB",
    }.get(level, "#F9FAFB")


def format_area(area_sqm: float) -> str:
    return f"{round(area_sqm):,} m²".replace(",", ".")


def format_coords(lat: float, lng: float) -> str:
    return f"{lat:.4f}, {lng:.4f}"


def risk_token(level: RiskLevel | str) -> str:
    if isinstance(level, RiskLevel):
        return level.value
    return str(level).replace("RiskLevel.", "")


def _build_environment() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["risk_color"] = risk_color
    env.filters["risk_bg"] = risk_bg
    return env
