"""
SiteScope FastAPI Backend

Main entry point. Exposes:
- POST /api/analyze     — run full site analysis, return JSON report
- POST /api/report/pdf  — run analysis and return PDF
- GET  /api/demo        — list demo locations
- GET  /health          — health check
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv

from config import get_settings, DEMO_LOCATIONS, OPENROUTER_MODEL
from models import AnalyzeRequest, AnalyzeResponse, HealthResponse, PDFRequest
from orchestrator import Orchestrator
from pdf_export import render_report_pdf
from debug import router as debug_router

# Load .env from project root
load_dotenv("../.env")
load_dotenv(".env")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Silence noisy third-party loggers
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    settings = get_settings()
    has_key = bool(settings.openrouter_api_key)
    logger.info(
        "SiteScope starting — LLM: %s | API key: %s",
        OPENROUTER_MODEL,
        "configured" if has_key else "NOT SET (fallback mode)",
    )
    yield
    logger.info("SiteScope shutting down")


app = FastAPI(
    title="SiteScope API",
    description="Agentic AI Red Flag Report Generator for Site Due Diligence",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register debug/diagnostics router
app.include_router(debug_router)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        agents_available=[
            "FloodAgent",
            "NatureAgent",
            "HeritageAgent",
            "ZoningAgent",
            "InfraAgent",
        ],
    )


# Bavaria bounding box (approximate)
BAVARIA_BBOX = {
    "lat_min": 47.27,
    "lat_max": 50.56,
    "lng_min": 8.97,
    "lng_max": 13.84,
}


def _is_in_bavaria(lat: float, lng: float) -> bool:
    """Check whether a coordinate falls within Bavaria's bounding box."""
    return (
        BAVARIA_BBOX["lat_min"] <= lat <= BAVARIA_BBOX["lat_max"]
        and BAVARIA_BBOX["lng_min"] <= lng <= BAVARIA_BBOX["lng_max"]
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Run full site analysis for a given coordinate.

    Dispatches all agents in parallel, generates a Red Flag Report
    via LLM, and returns structured JSON.
    """
    logger.info("Analyze request: (%.4f, %.4f)", request.lat, request.lng)

    # --- Bavaria boundary check ---
    if not _is_in_bavaria(request.lat, request.lng):
        logger.info(
            "Rejected: (%.4f, %.4f) is outside Bavaria", request.lat, request.lng
        )
        return AnalyzeResponse(
            success=False,
            report=None,
            agent_results=[],
            errors=[
                f"Location ({request.lat:.4f}, {request.lng:.4f}) is outside Bavaria (Bayern). "
                "SiteScope currently only supports locations within Bavaria, where our "
                "geodata sources (Bayern LfU, BLfD) are available."
            ],
        )

    orchestrator = Orchestrator(include_stretch=True)
    result = await orchestrator.analyze(request.lat, request.lng)

    if not result.success:
        logger.warning("Analysis had errors: %s", result.errors)

    return result


@app.post("/api/report/pdf")
async def report_pdf(request: PDFRequest):
    """
    Run analysis and return the report as a downloadable PDF.
    """
    logger.info("PDF report request: (%.4f, %.4f)", request.lat, request.lng)

    orchestrator = Orchestrator(include_stretch=True)
    result = await orchestrator.analyze(request.lat, request.lng)

    if not result.report:
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {', '.join(result.errors)}",
        )

    try:
        pdf_bytes = render_report_pdf(result.report)
    except Exception as e:
        logger.exception("PDF rendering failed")
        raise HTTPException(
            status_code=500,
            detail=f"PDF rendering failed: {e}",
        )

    filename = f"sitescope-report-{request.lat:.4f}-{request.lng:.4f}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/demo")
async def demo_locations():
    """Return list of interesting demo locations."""
    return {"locations": DEMO_LOCATIONS}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )
