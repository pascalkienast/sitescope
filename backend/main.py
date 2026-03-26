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

# Load .env from project root
load_dotenv("../.env")
load_dotenv(".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
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


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Run full site analysis for a given coordinate.

    Dispatches all agents in parallel, generates a Red Flag Report
    via LLM, and returns structured JSON.
    """
    logger.info("Analyze request: (%.4f, %.4f)", request.lat, request.lng)

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
