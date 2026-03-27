"""
Batch analysis helpers for polygon-derived area units.
"""

from __future__ import annotations

import asyncio
import logging

from models import (
    AgentCategory,
    AreaAnalyzeRequest,
    AreaAnalyzeResponse,
    AreaCategoryRollup,
    AreaUnitResult,
    RiskLevel,
)
from orchestrator import Orchestrator
from risk import highest_risk

logger = logging.getLogger(__name__)

AREA_MODE = "open_data_grid"
AREA_WARNINGS = [
    "Nur approximative Analysezellen. Offene bayerische Daten stellen keine exakten Flurstücksvektoren bereit.",
]
AREA_WMS_BUFFER_M = 10.0
AREA_MAX_UNITS = 20
AREA_CONCURRENCY = 2


async def analyze_area_request(request: AreaAnalyzeRequest) -> AreaAnalyzeResponse:
    """Analyze selected area units with bounded concurrency and no LLM synthesis."""
    orchestrator = Orchestrator(include_stretch=True)
    semaphore = asyncio.Semaphore(AREA_CONCURRENCY)

    async def run_unit(unit) -> AreaUnitResult:
        async with semaphore:
            try:
                response = await orchestrator.analyze_without_report(
                    unit.lat,
                    unit.lng,
                    wms_buffer_m=AREA_WMS_BUFFER_M,
                )
                return AreaUnitResult(
                    id=unit.id,
                    label=unit.label,
                    lat=unit.lat,
                    lng=unit.lng,
                    overall_risk_level=highest_risk(
                        agent_result.risk_level for agent_result in response.agent_results
                    ),
                    agent_results=response.agent_results,
                    errors=response.errors,
                )
            except Exception as exc:
                logger.exception("Area analysis unit %s failed", unit.id)
                return AreaUnitResult(
                    id=unit.id,
                    label=unit.label,
                    lat=unit.lat,
                    lng=unit.lng,
                    overall_risk_level=RiskLevel.UNKNOWN,
                    agent_results=[],
                    errors=[
                        f"Analysezelle konnte nicht verarbeitet werden: {type(exc).__name__}: {exc}"
                    ],
                )

    unit_results = await asyncio.gather(*(run_unit(unit) for unit in request.units))

    return AreaAnalyzeResponse(
        success=True,
        mode=AREA_MODE,
        exact_parcels=False,
        warnings=list(AREA_WARNINGS),
        units_analyzed=len(unit_results),
        unit_results=unit_results,
        category_rollup=_build_category_rollup(unit_results),
    )


def _build_category_rollup(unit_results: list[AreaUnitResult]) -> list[AreaCategoryRollup]:
    rollup: list[AreaCategoryRollup] = []

    for category in AgentCategory:
        category_results = []
        affected_units: list[str] = []

        for unit_result in unit_results:
            for agent_result in unit_result.agent_results:
                if agent_result.category != category:
                    continue

                category_results.append(agent_result.risk_level)
                if agent_result.risk_level not in (RiskLevel.NONE, RiskLevel.UNKNOWN):
                    affected_units.append(unit_result.id)

        rollup.append(
            AreaCategoryRollup(
                category=category,
                highest_risk=highest_risk(category_results),
                affected_units=affected_units,
            )
        )

    return rollup
