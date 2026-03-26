"""
SiteScope Debug / Diagnostics Router

GET /api/debug/sources — tests all external data sources concurrently
and returns a structured health report.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Query

from config import (
    DEFAULT_INFO_FORMAT,
    DEFAULT_WMS_VERSION,
    OPENROUTER_BASE_URL,
    WMS_DIAGNOSTIC_SOURCE_GROUPS,
    WMS_RLP_DIAGNOSTIC_SOURCE_GROUPS,
    RLP_BBOX,
)
from geo import (
    build_parsed_raw_data,
    make_bbox,
    make_original_raw_response_preview,
    parse_gml_feature_info,
    parse_html_feature_info,
    parse_text_feature_info,
    parsed_raw_data_to_text,
    sanitize_response_excerpt,
)
from models import ParsedRawData, RawDataBlock, RawDataField

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["debug"])

# Munich Marienplatz — known coordinate for data tests
DEFAULT_TEST_LAT, DEFAULT_TEST_LNG = 48.137, 11.576
# Timeout per individual check
CHECK_TIMEOUT = 15.0

BBOX_BUFFER = 50  # meters


def _is_in_rlp(lat: float, lng: float) -> bool:
    """Check if coordinates are within RLP bounding box."""
    return (
        RLP_BBOX["lat_min"] <= lat <= RLP_BBOX["lat_max"]
        and RLP_BBOX["lng_min"] <= lng <= RLP_BBOX["lng_max"]
    )


def _bbox_25832(lat: float, lng: float) -> str:
    """Return a small BBOX in EPSG:25832 around the selected test point."""
    return ",".join(f"{value:.3f}" for value in make_bbox(lat, lng, BBOX_BUFFER))


def _parse_feature_info_payload(
    raw_response: str,
    *,
    info_format: str,
) -> ParsedRawData | None:
    """Parse a WMS GetFeatureInfo payload into structured raw data."""
    format_hint = (info_format or "").lower()
    if "gml" in format_hint or "xml" in format_hint:
        features = parse_gml_feature_info(raw_response)
    elif "html" in format_hint:
        features = parse_html_feature_info(raw_response)
    else:
        features = parse_text_feature_info(raw_response)
    return build_parsed_raw_data(features, raw_response)


def _stringify_sample_value(value: Any) -> str:
    """Render nested sample values compactly for the debug dashboard."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _build_sample_blocks(
    data: dict[str, Any],
    *,
    title: str,
    layer_name: str | None = None,
    source_format: str = "json",
) -> ParsedRawData | None:
    """Create a structured key/value sample block from a plain dict."""
    fields = []
    for key, value in data.items():
        if value is None:
            continue
        rendered = _stringify_sample_value(value).strip()
        if not rendered:
            continue
        fields.append(RawDataField(key=str(key), value=rendered))

    if not fields:
        return None

    return ParsedRawData(
        format="key_value",
        source_format=source_format,
        feature_count=1,
        blocks=[
            RawDataBlock(
                title=title,
                layer_name=layer_name,
                fields=fields,
            )
        ],
    )


def _attach_structured_sample(
    result: dict[str, Any],
    *,
    parsed_raw_data: ParsedRawData | None,
    raw_response: str | None = None,
) -> None:
    """Populate legacy and new sample fields consistently."""
    result["parsed_raw_data"] = (
        parsed_raw_data.model_dump() if parsed_raw_data is not None else None
    )
    result["sample_data"] = (
        parsed_raw_data_to_text(parsed_raw_data, max_blocks=1, max_fields_per_block=6)
        if parsed_raw_data is not None
        else None
    )
    result["original_raw_response_preview"] = (
        make_original_raw_response_preview(raw_response or "")
        if raw_response
        else None
    )

    if result["sample_data"] is None and raw_response:
        result["sample_data"] = sanitize_response_excerpt(raw_response, max_chars=300)


def _build_feature_info_params(
    svc: dict[str, Any],
    layer: str,
    *,
    lat: float,
    lng: float,
) -> dict[str, str]:
    version = svc.get("version", DEFAULT_WMS_VERSION)
    crs = svc.get("crs", "EPSG:25832")
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetFeatureInfo",
        "VERSION": version,
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "BBOX": _bbox_25832(lat, lng),
        "WIDTH": "256",
        "HEIGHT": "256",
        "INFO_FORMAT": svc.get("info_format", DEFAULT_INFO_FORMAT),
        "FEATURE_COUNT": "10",
        "STYLES": "",
    }
    if version == "1.1.1":
        params["SRS"] = crs
        params["X"] = "128"
        params["Y"] = "128"
    else:
        params["CRS"] = crs
        params["I"] = "128"
        params["J"] = "128"
    return params


def _build_get_map_params(
    svc: dict[str, Any],
    layer: str,
    *,
    lat: float,
    lng: float,
) -> dict[str, str]:
    version = svc.get("version", DEFAULT_WMS_VERSION)
    crs = svc.get("crs", "EPSG:25832")
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": version,
        "LAYERS": layer,
        "BBOX": _bbox_25832(lat, lng),
        "WIDTH": "256",
        "HEIGHT": "256",
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "STYLES": "",
    }
    if version == "1.1.1":
        params["SRS"] = crs
    else:
        params["CRS"] = crs
    return params


async def _check_wms_service(
    client: httpx.AsyncClient,
    category: str,
    key: str,
    svc: dict[str, Any],
    *,
    lat: float,
    lng: float,
    region: str = "BAVARIA",
) -> dict:
    """Test a single WMS service: GetCapabilities + GetFeatureInfo."""
    result: dict[str, Any] = {
        "name": f"{category} — {svc['description']}",
        "key": key,
        "type": "wms",
        "region": region,
        "url": svc["url"],
        "capabilities_ok": False,
        "data_test_ok": False,
        "response_time_ms": 0,
        "error": None,
        "layers_tested": [],
        "sample_data": None,
        "parsed_raw_data": None,
        "original_raw_response_preview": None,
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

        # 2) GetFeatureInfo or GetMap on a representative layer
        test_layer = svc["layers"][0]
        result["layers_tested"] = [test_layer]
        probe = svc.get("probe", "feature_info")
        if probe == "get_map":
            map_resp = await client.get(
                svc["url"],
                params=_build_get_map_params(svc, test_layer, lat=lat, lng=lng),
                timeout=CHECK_TIMEOUT,
            )
            map_resp.raise_for_status()
            result["data_test_ok"] = "image" in map_resp.headers.get("content-type", "")
            _attach_structured_sample(
                result,
                parsed_raw_data=_build_sample_blocks(
                    {
                        "content_type": map_resp.headers.get(
                            "content-type",
                            "unknown",
                        ),
                        "bytes": len(map_resp.content),
                    },
                    title="Map response",
                    layer_name=test_layer,
                    source_format="text",
                ),
            )
        else:
            gfi_resp = await client.get(
                svc["url"],
                params=_build_feature_info_params(svc, test_layer, lat=lat, lng=lng),
                timeout=CHECK_TIMEOUT,
            )
            gfi_resp.raise_for_status()
            gfi_text = gfi_resp.text
            result["data_test_ok"] = True
            parsed_raw_data = _parse_feature_info_payload(
                gfi_text,
                info_format=svc.get("info_format", DEFAULT_INFO_FORMAT),
            )
            _attach_structured_sample(
                result,
                parsed_raw_data=parsed_raw_data,
                raw_response=gfi_text,
            )
            if not result["sample_data"]:
                result["sample_data"] = "(empty — no features at test point)"

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


async def _check_open_meteo(client: httpx.AsyncClient, *, lat: float, lng: float) -> dict:
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
        "parsed_raw_data": None,
        "original_raw_response_preview": None,
    }

    t0 = time.monotonic()
    try:
        resp = await client.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lng,
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
        daily = data.get("daily", {})
        _attach_structured_sample(
            result,
            parsed_raw_data=_build_sample_blocks(
                {
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "daily": daily,
                },
                title="Sample response",
            ),
            raw_response=json.dumps(data, ensure_ascii=False),
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


async def _check_opentopodata(
    client: httpx.AsyncClient,
    *,
    lat: float,
    lng: float,
) -> dict:
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
        "parsed_raw_data": None,
        "original_raw_response_preview": None,
    }

    t0 = time.monotonic()
    try:
        resp = await client.get(
            f"https://api.opentopodata.org/v1/eudem25m?locations={lat},{lng}",
            timeout=CHECK_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        result["capabilities_ok"] = data.get("status") == "OK"
        results_list = data.get("results", [])
        if results_list:
            result["data_test_ok"] = results_list[0].get("elevation") is not None
            _attach_structured_sample(
                result,
                parsed_raw_data=_build_sample_blocks(
                    results_list[0],
                    title="Sample response",
                ),
                raw_response=json.dumps(data, ensure_ascii=False),
            )
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
        "parsed_raw_data": None,
        "original_raw_response_preview": None,
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
        _attach_structured_sample(
            result,
            parsed_raw_data=_build_sample_blocks(
                {
                    "model_count": len(models),
                    "first_models": names,
                },
                title="Available models",
            ),
            raw_response=json.dumps({"model_count": len(models), "first_models": names}),
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["response_time_ms"] = round((time.monotonic() - t0) * 1000)
    return result


@router.get("/sources")
async def debug_sources(
    lat: float = Query(DEFAULT_TEST_LAT, ge=-90, le=90),
    lng: float = Query(DEFAULT_TEST_LNG, ge=-180, le=180),
    lon: float | None = Query(None, ge=-180, le=180),
):
    """
    Run ALL external data source checks concurrently and return results.
    """
    selected_lng = lon if lon is not None else lng

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={
            "User-Agent": "SiteScope-Debug/1.0",
            # Disable auto gzip — some Bayern LfU ArcGIS servers send
            # malformed gzip for error responses, causing DecodingError.
            "Accept-Encoding": "identity",
        },
    ) as client:
        # Build list of WMS check coroutines
        tasks: list = []

        for category, services in WMS_DIAGNOSTIC_SOURCE_GROUPS:
            for key, svc in services.items():
                tasks.append(
                    _check_wms_service(
                        client,
                        category,
                        key,
                        svc,
                        lat=lat,
                        lng=selected_lng,
                    )
                )

        # RLP WMS sources (test at RLP test point for diagnostic)
        for category, services in WMS_RLP_DIAGNOSTIC_SOURCE_GROUPS:
            for key, svc in services.items():
                tasks.append(
                    _check_wms_service(
                        client,
                        category,
                        key,
                        svc,
                        lat=50.353,  # RLP test point
                        lng=7.597,
                        region="RLP",
                    )
                )

        # Non-WMS APIs
        tasks.append(_check_open_meteo(client, lat=lat, lng=selected_lng))
        tasks.append(_check_opentopodata(client, lat=lat, lng=selected_lng))
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
                "parsed_raw_data": None,
                "original_raw_response_preview": None,
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

    bbox = make_bbox(lat, selected_lng, BBOX_BUFFER)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "total_sources": total,
        "healthy": ok_count,
        "degraded": cap_only,
        "failed": failed,
        "test_point": {
            "lat": lat,
            "lng": selected_lng,
            "buffer_m": BBOX_BUFFER,
            "bbox_25832": [round(value, 3) for value in bbox],
        },
        "sources": sources,
    }
