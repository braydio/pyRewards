import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


class BrowserSelectionTests(unittest.TestCase):
    def test_cli_accepts_chromium(self):
        from pyrewards.cli import parse_args

        args = parse_args(["--browser", "chromium", "--interactive"])
        self.assertEqual(args.browser, "chromium")
        self.assertTrue(args.interactive)

    def test_chromium_uses_system_binary(self):
        from pyrewards.browser import create_driver

        with tempfile.TemporaryDirectory() as temp:
            with patch("pyrewards.browser.shutil.which", return_value="/usr/bin/chromium"), (
                patch("pyrewards.browser.webdriver.Chrome") as launch
            ):
                create_driver("chromium", Path(temp) / "profile")
                launch.assert_called_once()
                options = launch.call_args.kwargs["options"]
                self.assertEqual(options.binary_location, "/usr/bin/chromium")

    def test_chromium_missing_browser_has_clear_error(self):
        from pyrewards.browser import create_driver

        with tempfile.TemporaryDirectory() as temp:
            with patch("pyrewards.browser.shutil.which", return_value=None), (
                patch("pyrewards.browser.webdriver.Chrome") as launch
            ):
                with self.assertRaisesRegex(FileNotFoundError, "sudo pacman"):
                    create_driver("chromium", Path(temp) / "profile")
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
