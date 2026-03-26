"""
PDF export — renders the Red Flag Report as a styled PDF via WeasyPrint.
"""

import logging
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from models import RedFlagReport, RiskLevel

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_report_pdf(report: RedFlagReport) -> bytes:
    """
    Render a RedFlagReport to PDF bytes.

    Uses Jinja2 to generate HTML from the report template,
    then converts to PDF via WeasyPrint.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["risk_color"] = risk_color
    env.filters["risk_bg"] = risk_bg

    template = env.get_template("report.html")

    html_content = template.render(
        report=report,
        RiskLevel=RiskLevel,
    )

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes


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
