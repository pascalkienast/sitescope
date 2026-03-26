import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geo"))

import debug as debug_module  # noqa: E402
from geo.transforms import make_bbox  # noqa: E402
from main import app  # noqa: E402


def _empty_api_result(name: str) -> dict:
    return {
        "name": name,
        "type": "api",
        "url": "https://example.com",
        "capabilities_ok": True,
        "data_test_ok": True,
        "response_time_ms": 1,
        "error": None,
        "layers_tested": [],
        "sample_data": "ok",
        "parsed_raw_data": None,
        "original_raw_response_preview": None,
    }


class DebugEndpointTests(unittest.TestCase):
    def test_debug_sources_parses_html_and_respects_custom_coordinates(self):
        expected_bbox = ",".join(
            f"{value:.3f}" for value in make_bbox(47.9898, 11.499, 50)
        )
        sample_html = """
        <!DOCTYPE html>
        <html>
          <head><style>body { font-family: Arial; }</style></head>
          <body>
            <table>
              <tr><td>Gebietsname</td><td>Straßlach-Dingharting</td></tr>
              <tr><td>Status</td><td>festgesetzt</td></tr>
            </table>
          </body>
        </html>
        """
        service = {
            "url": "https://example.com/wms",
            "description": "Test Layer",
            "layers": ["twsg"],
            "version": "1.3.0",
            "crs": "EPSG:25832",
            "info_format": "text/html",
        }

        async def fake_get(_self, url, params=None, timeout=None, **_kwargs):
            request = httpx.Request("GET", url, params=params)
            if params and params.get("REQUEST") == "GetCapabilities":
                return httpx.Response(
                    200,
                    text="<WMS_Capabilities/>",
                    request=request,
                )
            if params and params.get("REQUEST") == "GetFeatureInfo":
                self.assertEqual(params["BBOX"], expected_bbox)
                return httpx.Response(
                    200,
                    text=sample_html,
                    headers={"content-type": "text/html"},
                    request=request,
                )
            raise AssertionError(f"Unexpected request: {url} {params}")

        async def fake_open_meteo(_client, *, lat, lng):
            self.assertEqual((lat, lng), (47.9898, 11.499))
            return _empty_api_result("Open-Meteo Archive")

        async def fake_opentopodata(_client, *, lat, lng):
            self.assertEqual((lat, lng), (47.9898, 11.499))
            return _empty_api_result("OpenTopoData (Elevation)")

        async def fake_openrouter(_client):
            return _empty_api_result("OpenRouter (LLM)")

        with patch.object(
            debug_module,
            "WMS_DIAGNOSTIC_SOURCE_GROUPS",
            [("Nature", {"twsg": service})],
        ), patch(
            "debug.httpx.AsyncClient.get",
            new=fake_get,
        ), patch.object(
            debug_module,
            "_check_open_meteo",
            new=fake_open_meteo,
        ), patch.object(
            debug_module,
            "_check_opentopodata",
            new=fake_opentopodata,
        ), patch.object(
            debug_module,
            "_check_openrouter",
            new=fake_openrouter,
        ):
            client = TestClient(app)
            response = client.get("/api/debug/sources?lat=47.9898&lng=11.499")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["test_point"]["lat"], 47.9898)
        self.assertEqual(payload["test_point"]["lng"], 11.499)
        self.assertEqual(payload["total_sources"], 4)

        wms_source = payload["sources"][0]
        self.assertEqual(wms_source["key"], "twsg")
        self.assertIn("Gebietsname=Straßlach-Dingharting", wms_source["sample_data"])
        self.assertNotIn("<!DOCTYPE", wms_source["sample_data"])
        self.assertIn("<!DOCTYPE html>", wms_source["original_raw_response_preview"])

        fields = wms_source["parsed_raw_data"]["blocks"][0]["fields"]
        parsed = {field["key"]: field["value"] for field in fields}
        self.assertEqual(parsed["Gebietsname"], "Straßlach-Dingharting")
        self.assertEqual(parsed["Status"], "festgesetzt")


if __name__ == "__main__":
    unittest.main()
