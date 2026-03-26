"""
Orchestrator — dispatches agents in parallel and collects results.

Runs all MVP agents concurrently via asyncio.gather, then passes
the combined output to the report generator.
"""

import asyncio
import logging
import time

from agents import FloodAgent, NatureAgent, HeritageAgent, ZoningAgent, InfraAgent
from models import AgentResult, AnalyzeResponse
from report_generator import ReportGenerator
from config import DEFAULT_BUFFER_M, get_settings

logger = logging.getLogger(__name__)

# MVP agents (always run)
MVP_AGENTS = [FloodAgent, NatureAgent, HeritageAgent]
# Stretch agents (run if time allows)
STRETCH_AGENTS = [ZoningAgent, InfraAgent]


class Orchestrator:
    """Dispatches analysis agents and assembles the final report."""

    def __init__(self, include_stretch: bool = True):
        settings = get_settings()
        self.wms_timeout = settings.wms_timeout
        self.include_stretch = include_stretch
        self.report_generator = ReportGenerator()

    def _agent_classes(self) -> list[type]:
        # Build agent list
        agent_classes = list(MVP_AGENTS)
        if self.include_stretch:
            agent_classes.extend(STRETCH_AGENTS)
        return agent_classes

    def _build_agents(self, *, wms_buffer_m: float) -> tuple[list[type], list]:
        agent_classes = self._agent_classes()
        agents = [
            cls(wms_timeout=self.wms_timeout, wms_buffer_m=wms_buffer_m)
            for cls in agent_classes
        ]
        return agent_classes, agents

    async def run_agents(
        self,
        lat: float,
        lng: float,
        *,
        wms_buffer_m: float,
    ) -> tuple[list[AgentResult], list[str]]:
        """Run all configured agents without generating the synthesized report."""
        start = time.monotonic()
        agent_classes, agents = self._build_agents(wms_buffer_m=wms_buffer_m)

        logger.info("Starting agent run at (%.4f, %.4f) with %d agents", lat, lng, len(agents))

        tasks = [agent.analyze(lat, lng) for agent in agents]
        agent_results: list[AgentResult] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Handle any exceptions that slipped through
        clean_results = []
        errors = []
        for i, result in enumerate(agent_results):
            if isinstance(result, Exception):
                agent_name = agent_classes[i].__name__
                error_msg = f"Agent {agent_name} crashed: {type(result).__name__}: {result}"
                logger.error(error_msg)
                errors.append(error_msg)
            else:
                clean_results.append(result)
                if result.errors:
                    errors.extend(result.errors)

        logger.info(
            "All agents completed in %dms: %d results, %d errors",
            int((time.monotonic() - start) * 1000),
            len(clean_results),
            len(errors),
        )
        return clean_results, errors

    async def analyze_without_report(
        self,
        lat: float,
        lng: float,
        *,
        wms_buffer_m: float,
    ) -> AnalyzeResponse:
        """Run all agents but skip LLM/report generation."""
        agent_results, errors = await self.run_agents(
            lat,
            lng,
            wms_buffer_m=wms_buffer_m,
        )

        return AnalyzeResponse(
            success=True,
            report=None,
            agent_results=agent_results,
            errors=errors,
        )

    async def analyze(self, lat: float, lng: float) -> AnalyzeResponse:
        """
        Run full site analysis for a given coordinate.

        1. Dispatch all agents in parallel
        2. Collect results
        3. Generate Red Flag Report via LLM
        4. Return structured response
        """
        start = time.monotonic()
        agent_results, errors = await self.run_agents(
            lat,
            lng,
            wms_buffer_m=DEFAULT_BUFFER_M,
        )

        # Generate the Red Flag Report
        try:
            report = await self.report_generator.generate(
                lat=lat,
                lng=lng,
                agent_results=agent_results,
            )
        except Exception as e:
            logger.exception("Report generation failed")
            errors.append(f"Report generation failed: {e}")
            report = None

        total_ms = int((time.monotonic() - start) * 1000)
        if report:
            report.analysis_duration_ms = total_ms

        return AnalyzeResponse(
            success=report is not None,
            report=report,
            agent_results=agent_results,
            errors=errors,
        )
