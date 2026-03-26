import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geo"))

from parsers import (  # noqa: E402
    build_parsed_raw_data,
    parse_gml_feature_info,
    parse_html_feature_info,
    parse_text_feature_info,
    sanitize_response_excerpt,
)


class ParsedRawDataTests(unittest.TestCase):
    def test_html_feature_info_becomes_key_value_blocks(self):
        html = """
        <!DOCTYPE html>
        <html>
          <head>
            <style>
              body { font-family: Arial; }
            </style>
          </head>
          <body>
            <table>
              <tr><td class="titel">Gebietsname</td><td class="wert">Straßlach-Dingharting</td></tr>
              <tr><td class="titel">Status</td><td class="wert">festgesetzt</td></tr>
              <tr><td class="titel">Rechtsbehörde</td><td class="wert">Landratsamt München</td></tr>
            </table>
          </body>
        </html>
        """

        features = parse_html_feature_info(html)
        parsed = build_parsed_raw_data(features, html)

        self.assertEqual(len(features), 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.source_format, "html")
        self.assertEqual(parsed.feature_count, 1)
        self.assertEqual(parsed.blocks[0].title, "Feature 1")
        self.assertEqual(parsed.blocks[0].fields[0].key, "Gebietsname")
        self.assertEqual(parsed.blocks[0].fields[0].value, "Straßlach-Dingharting")
        serialized = {field.key: field.value for field in parsed.blocks[0].fields}
        self.assertEqual(serialized["Status"], "festgesetzt")
        self.assertNotIn("<style", serialized["Gebietsname"])

    def test_gml_feature_info_preserves_layer_and_attributes(self):
        gml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs" xmlns:gml="http://www.opengis.net/gml" xmlns:app="https://example.com">
          <gml:featureMember>
            <app:Denkmal>
              <app:aktennummer>D-1-62-000-1234</app:aktennummer>
              <app:kurzansprache>Wohnhaus</app:kurzansprache>
            </app:Denkmal>
          </gml:featureMember>
        </wfs:FeatureCollection>
        """

        features = parse_gml_feature_info(gml)
        parsed = build_parsed_raw_data(features, gml)

        self.assertEqual(len(features), 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.source_format, "gml")
        self.assertEqual(parsed.blocks[0].layer_name, "Denkmal")
        self.assertEqual(parsed.blocks[0].fields[0].key, "aktennummer")
        self.assertEqual(parsed.blocks[0].fields[0].value, "D-1-62-000-1234")

    def test_text_feature_info_preserves_key_value_pairs(self):
        response_text = """
        Layer 'hwgf_hq100'
        Feature 1:
        OBJECTID = '12345'
        FESTSETZUNG = 'ja'
        GEWAESSER = 'Isar'
        """

        features = parse_text_feature_info(response_text)
        parsed = build_parsed_raw_data(features, response_text)

        self.assertEqual(len(features), 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.source_format, "text")
        self.assertEqual(parsed.blocks[0].layer_name, "hwgf_hq100")
        serialized = {field.key: field.value for field in parsed.blocks[0].fields}
        self.assertEqual(serialized["OBJECTID"], "12345")
        self.assertEqual(serialized["FESTSETZUNG"], "ja")

    def test_fallback_excerpt_strips_html_and_css_noise(self):
        html = """
        <html>
          <head>
            <style>body { color: red; }</style>
          </head>
          <body>
            <div>Fallback Hinweis</div>
            <div>Nur Text ohne Tabelle</div>
          </body>
        </html>
        """

        parsed = build_parsed_raw_data([], html)
        excerpt = sanitize_response_excerpt(html)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.blocks[0].title, "Response excerpt")
        self.assertIn("Fallback Hinweis", parsed.blocks[0].fields[0].value)
        self.assertIn("Nur Text ohne Tabelle", excerpt)
        self.assertNotIn("<html", excerpt)
        self.assertNotIn("body {", excerpt)


if __name__ == "__main__":
    unittest.main()
