"""
Parsers for WMS GetFeatureInfo responses.

German WMS services return feature info in various formats:
- text/plain: Simple key=value or tabular text
- application/vnd.ogc.gml: GML/XML with feature attributes
- text/html: HTML tables (less common)

These parsers extract structured data from each format.
"""

import re
from typing import Optional
from lxml import etree


def parse_text_feature_info(response_text: str) -> list[dict]:
    """
    Parse a text/plain GetFeatureInfo response.

    Typical format from Bayern LfU:
    ```
    Layer 'hwgf_uesg_hq100'
    Feature Info:
      OBJECTID = '12345'
      GEWAESSER = 'Isar'
      FESTSETZUNG = 'ja'
    ```

    Or sometimes:
    ```
    GetFeatureInfo results:

    Layer 'einzeldenkmalO'
    Feature 1:
    aktennummer = 'D-1-62-000-1234'
    kurzansprache = 'Wohnhaus'
    ```

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

        # Detect layer header
        layer_match = re.match(r"Layer\s*['\"]?([^'\"]+)['\"]?", line, re.IGNORECASE)
        if layer_match:
            current_layer = layer_match.group(1).strip()
            # Start a new feature context
            if current_feature and current_feature.get("_attributes"):
                features.append(current_feature)
            current_feature = {"_layer": current_layer, "_attributes": {}}
            continue

        # Detect feature header (some services use "Feature N:")
        feature_match = re.match(r"Feature\s+(\d+)\s*:", line, re.IGNORECASE)
        if feature_match:
            if current_feature and current_feature.get("_attributes"):
                features.append(current_feature)
            current_feature = {"_layer": current_layer, "_attributes": {}}
            continue

        # Parse key=value pairs
        kv_match = re.match(r"([A-Za-z_][\w.]*)\s*=\s*['\"]?(.*?)['\"]?\s*$", line)
        if kv_match and current_feature is not None:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()
            # Skip empty/null values
            if value and value.lower() not in ("null", "none", ""):
                current_feature["_attributes"][key] = value
            continue

        # Also try colon-separated format: "key: value"
        colon_match = re.match(r"([A-Za-z_][\w.]*)\s*:\s+(.+)$", line)
        if colon_match and current_feature is not None:
            key = colon_match.group(1).strip()
            value = colon_match.group(2).strip()
            if value and value.lower() not in ("null", "none"):
                current_feature["_attributes"][key] = value
            continue

    # Don't forget the last feature
    if current_feature and current_feature.get("_attributes"):
        features.append(current_feature)

    return features


def parse_gml_feature_info(gml_text: str) -> list[dict]:
    """
    Parse a GML (application/vnd.ogc.gml) GetFeatureInfo response.

    GML responses wrap features in XML elements. We extract all leaf
    text values as key-value pairs.
    """
    if not gml_text or not gml_text.strip():
        return []

    features = []

    try:
        root = etree.fromstring(gml_text.encode("utf-8"))
    except etree.XMLSyntaxError:
        # Try removing XML declaration issues
        cleaned = re.sub(r"<\?xml[^>]+\?>", "", gml_text).strip()
        try:
            root = etree.fromstring(cleaned.encode("utf-8"))
        except etree.XMLSyntaxError:
            return []

    # Find all feature members (various namespace patterns)
    # GML uses gml:featureMember, gml:featureMembers, or just featureMember
    ns = {
        "gml": "http://www.opengis.net/gml",
        "wfs": "http://www.opengis.net/wfs",
    }

    # Try multiple XPath patterns
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

    # If no feature members found, try the root's direct children
    if not feature_elements:
        feature_elements = list(root)

    for elem in feature_elements:
        attrs = {}
        layer_name = _local_name(elem.tag)

        for child in elem.iter():
            if child.text and child.text.strip():
                key = _local_name(child.tag)
                value = child.text.strip()
                if key and value and key != layer_name:
                    attrs[key] = value

        if attrs:
            features.append({"_layer": layer_name, "_attributes": attrs})

    return features


def _local_name(tag: str) -> str:
    """Strip namespace from an XML tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def has_meaningful_data(features: list[dict]) -> bool:
    """Check if parsed features contain actual data (not just empty results)."""
    for f in features:
        attrs = f.get("_attributes", {})
        if attrs:
            return True
    return False


def features_to_flat_dict(features: list[dict]) -> dict:
    """
    Flatten a list of features into a single dict for simple queries.
    Uses layer_name.attribute_name as keys for disambiguation.
    """
    result = {}
    for f in features:
        layer = f.get("_layer", "unknown")
        for key, value in f.get("_attributes", {}).items():
            flat_key = f"{layer}.{key}"
            result[flat_key] = value
    return result
