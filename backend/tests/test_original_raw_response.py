import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geo"))

from parsers import make_original_raw_response_preview  # noqa: E402


class OriginalRawResponseTests(unittest.TestCase):
    def test_original_raw_response_is_not_clipped(self):
        raw_response = (
            "<html><body>"
            + "".join(f"<div>Zeile {index:04d}</div>" for index in range(250))
            + "</body></html>"
        )

        preview = make_original_raw_response_preview(raw_response)

        self.assertEqual(preview, raw_response)
        self.assertTrue(preview.endswith("</body></html>"))
        self.assertNotIn("...", preview[-10:])


if __name__ == "__main__":
    unittest.main()
