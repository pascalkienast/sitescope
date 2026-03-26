"""
SiteScope Debug / Diagnostics Router

GET /api/debug/sources — tests all external data sources concurrently
and returns a structured health report.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter

from config import (
    WMS_FLOOD,
    WMS_NATURE,
    WMS_HERITAGE,
    OPENROUTER_BASE_URL,
    DEFAULT_CRS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["debug"])

# Munich Marienplatz — known coordinate for data tests
TEST_LAT, TEST_LNG = 48.137, 11.576
# Timeout per individual check
CHECK_TIMEOUT = 15.0

# EPSG:25832 approximate coords for Munich center (pre-computed)
# pyproj is available but let's keep it simple with a known transform
MUNICH_EPSG25832_X, MUNICH_EPSG25832_Y = 691607.0, 5334759.0
BBOX_BUFFER = 50  # meters


def _bbox_25832() -> str:
    """Return a small BBOX around Munich in EPSG:25832."""
    x, y = MUNICH_EPSG25832_X, MUNICH_EPSG25832_Y
    b = BBOX_BUFFER
    return f"{x - b},{y - b},{x + b},{y + b}"


async def _check_wms_service(
    client: httpx.AsyncClient,
    category: str,
    key: str,
    svc: dict[str, Any],
) -> dict:
    """Test a single WMS service: GetCapabilities + GetFeatureInfo."""
    result: dict[str, Any] = {
        "name": f"{category} — {svc['description']}",
        "key": key,
        "type": "wms",
        "url": svc["url"],
        "capabilities_ok": False,
        "data_test_ok": False,
        "response_time_ms": 0,
        "error": None,
        "layers_tested": [],
        "sample_data": None,
    }

    t0 = time.monotonic()
    try:
        # 1) GetCapabilities
        cap_url = svc["url"]
        cap_resp = await client.get(
            cap_url,
            params={"SERVICE": "WMS", "REQUEST": "GetCapabilities"},
            timeout=CHECK_TIMEOUT,
        )
        cap_resp.raise_for_status()
        body = cap_resp.text
        result["capabilities_ok"] = (
            "WMS_Capabilities" in body or "WMT_MS_Capabilities" in body
        )

        # 2) GetFeatureInfo on the first layer
        test_layer = svc["layers"][0]
        result["layers_tested"] = [test_layer]
        bbox = _bbox_25832()
        gfi_params = {
            "SERVICE": "WMS",
            "REQUEST": "GetFeatureInfo",
            "VERSION": "1.1.1",
            "LAYERS": test_layer,
            "QUERY_LAYERS": test_layer,
            "SRS": DEFAULT_CRS,
            "BBOX": bbox,
            "WIDTH": "256",
            "HEIGHT": "256",
            "X": "128",
            "Y": "128",
            "INFO_FORMAT": "text/plain",
        }
        gfi_resp = await client.get(
            svc["url"], params=gfi_params, timeout=CHECK_TIMEOUT
        )
        gfi_resp.raise_for_status()
        gfi_text = gfi_resp.text[:500]
        result["data_test_ok"] = True
        result["sample_data"] = gfi_text.strip() if gfi_text.strip() else "(empty — no features at test point)"

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


async def _check_open_meteo(client: httpx.AsyncClient) -> dict:
    """Test Open-Meteo archive API."""
    result: dict[str, Any] = {
        "name": "Open-Meteo Archive",
        "type": "api",
        "url": "https://archive-api.open-meteo.com/v1/archive",
        "capabilities_ok": False,
        "data_test_ok": False,
        "response_time_ms": 0,
        "error": None,
        "layers_tested": [],
        "sample_data": None,
    }

    t0 = time.monotonic()
    try:
        resp = await client.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": TEST_LAT,
                "longitude": TEST_LNG,
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "daily": "temperature_2m_max",
            },
            timeout=CHECK_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        result["capabilities_ok"] = True
        result["data_test_ok"] = "daily" in data
        result["sample_data"] = str(data.get("daily", {}))[:300]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


async def _check_opentopodata(client: httpx.AsyncClient) -> dict:
    """Test OpenTopoData elevation API."""
    result: dict[str, Any] = {
        "name": "OpenTopoData (Elevation)",
        "type": "api",
        "url": "https://api.opentopodata.org/v1/eudem25m",
        "capabilities_ok": False,
        "data_test_ok": False,
        "response_time_ms": 0,
        "error": None,
        "layers_tested": [],
        "sample_data": None,
    }

    t0 = time.monotonic()
    try:
        resp = await client.get(
            f"https://api.opentopodata.org/v1/eudem25m?locations={TEST_LAT},{TEST_LNG}",
            timeout=CHECK_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        result["capabilities_ok"] = data.get("status") == "OK"
        results_list = data.get("results", [])
        if results_list:
            result["data_test_ok"] = results_list[0].get("elevation") is not None
            result["sample_data"] = str(results_list[0])[:300]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


async def _check_openrouter(client: httpx.AsyncClient) -> dict:
    """Test OpenRouter API auth by listing models."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    result: dict[str, Any] = {
        "name": "OpenRouter (LLM)",
        "type": "api",
        "url": OPENROUTER_BASE_URL,
        "capabilities_ok": False,
        "data_test_ok": False,
        "response_time_ms": 0,
        "error": None,
        "layers_tested": [],
        "sample_data": None,
    }

    if not api_key:
        result["error"] = "OPENROUTER_API_KEY not set"
        return result

    t0 = time.monotonic()
    try:
        resp = await client.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=CHECK_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        result["capabilities_ok"] = True
        result["data_test_ok"] = len(models) > 0
        names = [m.get("id", "?") for m in models[:5]]
        result["sample_data"] = f"{len(models)} models available. First 5: {names}"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


@router.get("/sources")
async def debug_sources():
    """
    Run ALL external data source checks concurrently and return results.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "SiteScope-Debug/1.0"},
    ) as client:
        # Build list of WMS check coroutines
        tasks: list[asyncio.Task] = []

        for key, svc in WMS_FLOOD.items():
            tasks.append(_check_wms_service(client, "Flood", key, svc))
        for key, svc in WMS_NATURE.items():
            tasks.append(_check_wms_service(client, "Nature", key, svc))
        for key, svc in WMS_HERITAGE.items():
            tasks.append(_check_wms_service(client, "Heritage", key, svc))

        # Non-WMS APIs
        tasks.append(_check_open_meteo(client))
        tasks.append(_check_opentopodata(client))
        tasks.append(_check_openrouter(client))

        # Run all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Normalize exceptions into result dicts
    sources = []
    for r in results:
        if isinstance(r, Exception):
            sources.append({
                "name": "Unknown",
                "type": "error",
                "url": "",
                "capabilities_ok": False,
                "data_test_ok": False,
                "response_time_ms": 0,
                "error": f"{type(r).__name__}: {r}",
                "layers_tested": [],
                "sample_data": None,
            })
        else:
            sources.append(r)

    # Determine overall status
    total = len(sources)
    ok_count = sum(1 for s in sources if s["capabilities_ok"] and s.get("data_test_ok"))
    cap_only = sum(1 for s in sources if s["capabilities_ok"] and not s.get("data_test_ok"))
    failed = total - ok_count - cap_only

    if ok_count == total:
        overall = "ok"
    elif failed >= total // 2:
        overall = "critical"
    else:
        overall = "degraded"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "total_sources": total,
        "healthy": ok_count,
        "degraded": cap_only,
        "failed": failed,
        "sources": sources,
    }
