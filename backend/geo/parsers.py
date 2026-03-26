"""
Parsers and raw-data normalizers for WMS GetFeatureInfo responses.

German WMS services return feature info in several formats:
- text/plain: key=value or simple tabular text
- application/vnd.ogc.gml: GML/XML feature collections
- text/html: ArcGIS-style HTML tables

This module parses those responses into structured feature dicts and
normalizes them for UI, PDF, and LLM consumption.
"""

from __future__ import annotations

import re
from typing import Optional

from lxml import etree

from models import ParsedRawData, RawDataBlock, RawDataField

PLACEHOLDER_VALUES = {"", "null", "none", "nan", "n/a", "na"}
RAW_PREVIEW_LIMIT = 1200
RAW_FALLBACK_EXCERPT_LIMIT = 800


def parse_text_feature_info(response_text: str) -> list[dict]:
    """
    Parse a text/plain GetFeatureInfo response.

    Returns a list of dicts, one per feature found.
    """
    if not response_text or not response_text.strip():
        return []

    features = []
    current_feature: Optional[dict] = None
    current_layer: Optional[str] = None

    for line in response_text.splitlines():
        line = line.strip()

        if not line:
            continue

        layer_match = re.match(r"Layer\s*['\"]?([^'\"]+)['\"]?", line, re.IGNORECASE)
        if layer_match:
            current_layer = layer_match.group(1).strip()
            if current_feature and current_feature.get("_attributes"):
                features.append(current_feature)
            current_feature = {"_layer": current_layer, "_attributes": {}}
            continue

        feature_match = re.match(r"Feature\s+(\d+)\s*:", line, re.IGNORECASE)
        if feature_match:
            if current_feature and current_feature.get("_attributes"):
                features.append(current_feature)
            current_feature = {"_layer": current_layer, "_attributes": {}}
            continue

        kv_match = re.match(r"([A-Za-z_][\w.]*)\s*=\s*['\"]?(.*?)['\"]?\s*$", line)
        if kv_match and current_feature is not None:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()
            if _is_meaningful_value(value):
                current_feature["_attributes"][key] = value
            continue

        colon_match = re.match(r"([A-Za-z_][\w.]*)\s*:\s+(.+)$", line)
        if colon_match and current_feature is not None:
            key = colon_match.group(1).strip()
            value = colon_match.group(2).strip()
            if _is_meaningful_value(value):
                current_feature["_attributes"][key] = value
            continue

    if current_feature and current_feature.get("_attributes"):
        features.append(current_feature)

    return features


def parse_gml_feature_info(gml_text: str) -> list[dict]:
    """
    Parse a GML/XML GetFeatureInfo response.

    We extract all leaf text values as key/value pairs.
    """
    if not gml_text or not gml_text.strip():
        return []

    features = []

    try:
        root = etree.fromstring(gml_text.encode("utf-8"))
    except etree.XMLSyntaxError:
        cleaned = re.sub(r"<\?xml[^>]+\?>", "", gml_text).strip()
        try:
            root = etree.fromstring(cleaned.encode("utf-8"))
        except etree.XMLSyntaxError:
            return []

    ns = {
        "gml": "http://www.opengis.net/gml",
        "wfs": "http://www.opengis.net/wfs",
    }

    feature_elements = []
    for xpath in [
        ".//gml:featureMember/*",
        ".//gml:featureMembers/*",
        ".//*[local-name()='featureMember']/*",
        ".//*[local-name()='featureMembers']/*",
    ]:
        try:
            found = root.xpath(xpath, namespaces=ns)
            if found:
                feature_elements = found
                break
        except etree.XPathError:
            continue

    if not feature_elements:
        feature_elements = list(root)

    for elem in feature_elements:
        attrs = {}
        layer_name = _local_name(elem.tag)

        for child in elem.iter():
            if child is elem:
                continue
            if child.text and child.text.strip():
                key = _local_name(child.tag)
                value = child.text.strip()
                if key and _is_meaningful_value(value) and key != layer_name:
                    attrs[key] = value

        if attrs:
            features.append({"_layer": layer_name, "_attributes": attrs})

    return features


def parse_html_feature_info(html_text: str) -> list[dict]:
    """
    Parse a text/html GetFeatureInfo response from ArcGIS-style WMS services.

    Supports both the Bayern LfU titel/wert tables and generic two-column
    tables where the first cell is a key and the remaining cells contain
    the corresponding value.
    """
    if not html_text or not html_text.strip():
        return []

    if "Kein Treffer" in html_text and "<table" not in html_text.lower():
        return []

    try:
        root = etree.HTML(html_text)
    except etree.XMLSyntaxError:
        return []

    if root is None:
        return []

    features = []
    tables = root.xpath("//table[not(ancestor::table)]")
    for table in tables:
        attrs = {}
        for row in table.xpath(".//tr"):
            cells = row.xpath("./th|./td")
            texts = [_normalize_whitespace(" ".join(cell.itertext())) for cell in cells]
            texts = [text for text in texts if text]
            if len(texts) < 2:
                continue

            key = texts[0].rstrip(":")
            value = " | ".join(texts[1:])
            if _is_meaningful_value(value):
                attrs[key] = value

        if attrs:
            features.append({"_layer": "html", "_attributes": attrs})

    return features


def _local_name(tag: str) -> str:
    """Strip namespace from an XML tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_meaningful_value(value: object) -> bool:
    normalized = _normalize_whitespace(str(value)).lower()
    return normalized not in PLACEHOLDER_VALUES


def has_meaningful_data(features: list[dict]) -> bool:
    """Check if parsed features contain actual data (not just empty results)."""
    for feature in features:
        attrs = feature.get("_attributes", {})
        for value in attrs.values():
            if _is_meaningful_value(value):
                return True
    return False


def features_to_flat_dict(features: list[dict]) -> dict:
    """
    Flatten a list of features into a single dict for simple queries.
    Uses layer_name.attribute_name as keys for disambiguation.
    """
    result = {}
    for feature in features:
        layer = feature.get("_layer", "unknown")
        for key, value in feature.get("_attributes", {}).items():
            flat_key = f"{layer}.{key}"
            result[flat_key] = value
    return result


def detect_response_format(raw_response: str) -> str:
    """Infer the response format from the raw payload."""
    if not raw_response or not raw_response.strip():
        return "unknown"

    lower = raw_response.lstrip().lower()
    if lower.startswith("{") or lower.startswith("["):
        return "json"
    if any(marker in lower for marker in ("<!doctype html", "<html", "<table", "<body")):
        return "html"
    if any(marker in lower for marker in ("<gml:", "featuremember", "<wfs:", "<?xml", "<featurecollection")):
        return "gml"
    if "=" in raw_response or ":" in raw_response:
        return "text"
    return "unknown"


def sanitize_response_excerpt(
    raw_response: str,
    *,
    source_format: Optional[str] = None,
    max_chars: int = RAW_FALLBACK_EXCERPT_LIMIT,
) -> str:
    """Convert a raw response into plain readable text without markup noise."""
    if not raw_response or not raw_response.strip():
        return ""

    source_format = source_format or detect_response_format(raw_response)
    text = ""

    if source_format == "html":
        try:
            root = etree.HTML(raw_response)
            if root is not None:
                etree.strip_elements(root, "script", "style", with_tail=False)
                bodies = root.xpath("//body")
                target = bodies[0] if bodies else root
                text = " ".join(_normalize_whitespace(chunk) for chunk in target.itertext())
        except etree.XMLSyntaxError:
            text = ""
    elif source_format == "gml":
        try:
            root = etree.fromstring(raw_response.encode("utf-8"))
            text = " ".join(_normalize_whitespace(chunk) for chunk in root.itertext())
        except etree.XMLSyntaxError:
            text = ""
    else:
        text = raw_response

    normalized = _normalize_whitespace(text)
    return _clip_text(normalized, max_chars=max_chars)


def build_parsed_raw_data(
    features: list[dict],
    raw_response: str,
) -> Optional[ParsedRawData]:
    """Build a normalized raw-data object from parsed features and the original response."""
    source_format = detect_response_format(raw_response)
    blocks: list[RawDataBlock] = []

    for index, feature in enumerate(features, start=1):
        attrs = feature.get("_attributes", {}) or {}
        fields = []
        for key, value in attrs.items():
            if str(key).startswith("_"):
                continue
            normalized_value = _normalize_whitespace(str(value))
            if not _is_meaningful_value(normalized_value):
                continue
            fields.append(RawDataField(key=_normalize_whitespace(str(key)), value=normalized_value))

        if fields:
            layer_name = _normalize_whitespace(str(feature.get("_layer", "")))
            if layer_name.lower() in {"", "html", "unknown", "none"}:
                layer_name = None
            blocks.append(
                RawDataBlock(
                    title=f"Feature {index}",
                    layer_name=layer_name,
                    fields=fields,
                )
            )

    if not blocks:
        excerpt = sanitize_response_excerpt(raw_response, source_format=source_format)
        if excerpt:
            blocks.append(
                RawDataBlock(
                    title="Response excerpt",
                    fields=[RawDataField(key="text", value=excerpt)],
                )
            )

    if not blocks:
        return None

    return ParsedRawData(
        format="key_value",
        source_format=source_format,
        feature_count=len(features),
        blocks=blocks,
    )


def parsed_raw_data_to_text(
    parsed_raw_data: Optional[ParsedRawData],
    *,
    max_blocks: Optional[int] = None,
    max_fields_per_block: Optional[int] = None,
) -> Optional[str]:
    """Serialize parsed raw data to a compact plain-text representation."""
    if not parsed_raw_data or not parsed_raw_data.blocks:
        return None

    block_chunks = []
    selected_blocks = parsed_raw_data.blocks[:max_blocks] if max_blocks else parsed_raw_data.blocks
    for block in selected_blocks:
        header = block.title
        if block.layer_name:
            header = f"{header} [{block.layer_name}]"

        selected_fields = block.fields[:max_fields_per_block] if max_fields_per_block else block.fields
        field_parts = [f"{field.key}={field.value}" for field in selected_fields]
        if max_fields_per_block and len(block.fields) > max_fields_per_block:
            field_parts.append(f"... {len(block.fields) - max_fields_per_block} more fields")

        block_chunks.append(f"{header}: {'; '.join(field_parts)}")

    if max_blocks and len(parsed_raw_data.blocks) > max_blocks:
        block_chunks.append(f"... {len(parsed_raw_data.blocks) - max_blocks} more blocks")

    return " | ".join(block_chunks)


def make_original_raw_response_preview(
    raw_response: str,
    *,
    max_chars: int = RAW_PREVIEW_LIMIT,
) -> Optional[str]:
    """Keep a capped preview of the original raw response for debug inspection."""
    if not raw_response or not raw_response.strip():
        return None
    return _clip_text(raw_response.strip(), max_chars=max_chars)


def _clip_text(text: str, *, max_chars: int) -> str:
    """Clip text without losing the overall meaning of the excerpt."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
