import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geo"))

import area_analysis  # noqa: E402
from main import app  # noqa: E402
from models import AnalyzeResponse, AgentCategory, AgentResult, RiskLevel  # noqa: E402


class AreaEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_area_units_splits_polygon_and_caps_units(self):
        response = self.client.post(
            "/api/area/units",
            json={
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [11.45, 48.08],
                            [11.70, 48.08],
                            [11.70, 48.22],
                            [11.45, 48.22],
                            [11.45, 48.08],
                        ]
                    ],
                },
                "max_units": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "open_data_grid")
        self.assertFalse(payload["exact_parcels"])
        self.assertEqual(len(payload["units"]), 3)
        self.assertIn("approximative Analysezellen", payload["warnings"][0])
        self.assertEqual(payload["units"][0]["geometry"]["type"], "Polygon")
        self.assertGreater(payload["units"][0]["area_sqm"], 0)

    def test_area_units_rejects_invalid_polygon(self):
        response = self.client.post(
            "/api/area/units",
            json={
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [11.50, 48.10],
                            [11.65, 48.20],
                            [11.65, 48.10],
                            [11.50, 48.20],
                            [11.50, 48.10],
                        ]
                    ],
                }
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid polygon geometry", response.json()["detail"])

    def test_area_units_rejects_polygon_outside_bavaria(self):
        response = self.client.post(
            "/api/area/units",
            json={
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [2.30, 48.80],
                            [2.40, 48.80],
                            [2.40, 48.90],
                            [2.30, 48.90],
                            [2.30, 48.80],
                        ]
                    ],
                }
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("outside Bavaria", response.json()["detail"])

    def test_area_analyze_uses_agent_only_flow_and_respects_concurrency_limit(self):
        testcase = self
        current_runs = 0
        max_runs = 0

        async def fake_analyze_without_report(self, lat, lng, *, wms_buffer_m):
            nonlocal current_runs, max_runs
            testcase.assertEqual(wms_buffer_m, area_analysis.AREA_WMS_BUFFER_M)
            current_runs += 1
            max_runs = max(max_runs, current_runs)
            await asyncio.sleep(0.01)
            current_runs -= 1

            risk = RiskLevel.HIGH if lat > 48.12 else RiskLevel.LOW
            return AnalyzeResponse(
                success=True,
                report=None,
                agent_results=[
                    AgentResult(
                        category=AgentCategory.FLOOD,
                        agent_name="Flood & Water Agent",
                        risk_level=risk,
                        summary="stub",
                    ),
                    AgentResult(
                        category=AgentCategory.NATURE,
                        agent_name="Nature & Environment Agent",
                        risk_level=RiskLevel.NONE,
                        summary="stub",
                    ),
                ],
                errors=[],
            )

        with patch.object(
            area_analysis.Orchestrator,
            "analyze_without_report",
            new=fake_analyze_without_report,
        ):
            response = self.client.post(
                "/api/area/analyze",
                json={
                    "units": [
                        {"id": "cell-01", "label": "Analysezelle 1", "lat": 48.11, "lng": 11.55},
                        {"id": "cell-02", "label": "Analysezelle 2", "lat": 48.13, "lng": 11.56},
                        {"id": "cell-03", "label": "Analysezelle 3", "lat": 48.14, "lng": 11.57},
                        {"id": "cell-04", "label": "Analysezelle 4", "lat": 48.10, "lng": 11.58},
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["units_analyzed"], 4)
        self.assertEqual(max_runs, area_analysis.AREA_CONCURRENCY)

        unit_results = {item["id"]: item for item in payload["unit_results"]}
        self.assertEqual(unit_results["cell-02"]["overall_risk_level"], "HIGH")
        self.assertEqual(unit_results["cell-01"]["overall_risk_level"], "LOW")

        flood_rollup = next(
            item for item in payload["category_rollup"] if item["category"] == "flood"
        )
        self.assertEqual(flood_rollup["highest_risk"], "HIGH")
        self.assertEqual(flood_rollup["affected_units"], ["cell-01", "cell-02", "cell-03", "cell-04"])

    def test_area_analyze_returns_partial_results_when_one_unit_crashes(self):
        async def fake_analyze_without_report(self, lat, lng, *, wms_buffer_m):
            if lat > 48.12:
                raise RuntimeError("upstream timeout")

            return AnalyzeResponse(
                success=True,
                report=None,
                agent_results=[
                    AgentResult(
                        category=AgentCategory.FLOOD,
                        agent_name="Flood & Water Agent",
                        risk_level=RiskLevel.LOW,
                        summary="stub",
                    )
                ],
                errors=[],
            )

        with patch.object(
            area_analysis.Orchestrator,
            "analyze_without_report",
            new=fake_analyze_without_report,
        ):
            response = self.client.post(
                "/api/area/analyze",
                json={
                    "units": [
                        {"id": "cell-01", "label": "Analysezelle 1", "lat": 48.11, "lng": 11.55},
                        {"id": "cell-02", "label": "Analysezelle 2", "lat": 48.13, "lng": 11.56},
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["units_analyzed"], 2)

        unit_results = {item["id"]: item for item in payload["unit_results"]}
        self.assertEqual(unit_results["cell-01"]["overall_risk_level"], "LOW")
        self.assertEqual(unit_results["cell-02"]["overall_risk_level"], "UNKNOWN")
        self.assertEqual(unit_results["cell-02"]["agent_results"], [])
        self.assertIn("Analysezelle konnte nicht verarbeitet werden", unit_results["cell-02"]["errors"][0])

    def test_area_pdf_returns_pdf_for_partial_area_analysis(self):
        response = self.client.post(
            "/api/report/area/pdf",
            json={
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [11.55, 48.11],
                            [11.57, 48.11],
                            [11.57, 48.13],
                            [11.55, 48.13],
                            [11.55, 48.11],
                        ]
                    ],
                },
                "units": [
                    {
                        "id": "cell-01",
                        "label": "Analysezelle 1",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [11.55, 48.11],
                                [11.56, 48.11],
                                [11.56, 48.12],
                                [11.55, 48.12],
                                [11.55, 48.11],
                            ]],
                        },
                        "sample_point": {"lat": 48.115, "lng": 11.555},
                        "area_sqm": 950.0,
                    },
                    {
                        "id": "cell-02",
                        "label": "Analysezelle 2",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [11.56, 48.11],
                                [11.57, 48.11],
                                [11.57, 48.12],
                                [11.56, 48.12],
                                [11.56, 48.11],
                            ]],
                        },
                        "sample_point": {"lat": 48.115, "lng": 11.565},
                        "area_sqm": 940.0,
                    },
                ],
                "analysis": {
                    "success": True,
                    "mode": "open_data_grid",
                    "exact_parcels": False,
                    "warnings": [
                        "Nur approximative Analysezellen. Offene bayerische Daten stellen keine exakten Flurstücksvektoren bereit."
                    ],
                    "units_analyzed": 1,
                    "unit_results": [
                        {
                            "id": "cell-01",
                            "label": "Analysezelle 1",
                            "lat": 48.115,
                            "lng": 11.555,
                            "overall_risk_level": "MEDIUM",
                            "agent_results": [
                                {
                                    "category": "flood",
                                    "agent_name": "Flood & Water Agent",
                                    "risk_level": "MEDIUM",
                                    "summary": "HQ100 area intersects the sample point.",
                                    "findings": [],
                                    "layers_queried": 3,
                                    "layers_with_data": 1,
                                    "errors": [],
                                    "execution_time_ms": 123,
                                }
                            ],
                            "errors": [],
                        }
                    ],
                    "category_rollup": [
                        {
                            "category": "flood",
                            "highest_risk": "MEDIUM",
                            "affected_units": ["cell-01"],
                        },
                        {
                            "category": "nature",
                            "highest_risk": "NONE",
                            "affected_units": [],
                        },
                        {
                            "category": "heritage",
                            "highest_risk": "NONE",
                            "affected_units": [],
                        },
                        {
                            "category": "zoning",
                            "highest_risk": "NONE",
                            "affected_units": [],
                        },
                        {
                            "category": "infrastructure",
                            "highest_risk": "LOW",
                            "affected_units": ["cell-01"],
                        },
                    ],
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_area_pdf_rejects_unknown_unit_reference(self):
        response = self.client.post(
            "/api/report/area/pdf",
            json={
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [11.55, 48.11],
                            [11.57, 48.11],
                            [11.57, 48.13],
                            [11.55, 48.13],
                            [11.55, 48.11],
                        ]
                    ],
                },
                "units": [
                    {
                        "id": "cell-01",
                        "label": "Analysezelle 1",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [11.55, 48.11],
                                [11.56, 48.11],
                                [11.56, 48.12],
                                [11.55, 48.12],
                                [11.55, 48.11],
                            ]],
                        },
                        "sample_point": {"lat": 48.115, "lng": 11.555},
                        "area_sqm": 950.0,
                    }
                ],
                "analysis": {
                    "success": True,
                    "mode": "open_data_grid",
                    "exact_parcels": False,
                    "warnings": [],
                    "units_analyzed": 1,
                    "unit_results": [
                        {
                            "id": "cell-02",
                            "label": "Analysezelle 2",
                            "lat": 48.115,
                            "lng": 11.565,
                            "overall_risk_level": "LOW",
                            "agent_results": [],
                            "errors": [],
                        }
                    ],
                    "category_rollup": [],
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unknown units", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
