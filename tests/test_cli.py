import tempfile
import unittest
from pathlib import Path

from pyrewards.core import Card, CardStatus


class ReportTests(unittest.TestCase):
    def test_saved_report_contains_status_not_urls(self):
        # cli depends on Selenium, which is installed as the single runtime dependency.
        from pyrewards.cli import save_report

        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "nested" / "result.json"
            cards = [Card("Daily set", 0, "Daily quiz", CardStatus.AVAILABLE,
                          "https://example.com/?session=top-secret")]
            save_report(destination, "2026-01-01T12:00:00", "edge", cards, cards, None, None, 0)
            report = destination.read_text(encoding="utf-8")
            self.assertIn('"available"', report)
            self.assertNotIn("top-secret", report)
            self.assertTrue(destination.exists())


if __name__ == "__main__":
    unittest.main()
