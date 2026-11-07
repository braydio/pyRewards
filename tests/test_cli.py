import json
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


class QuizCLIOptionsTests(unittest.TestCase):
    def test_quiz_mode_requires_interactive_opt_in(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from pyrewards.cli import parse_args

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--run-quizzes"])

    def test_quiz_mode_configuration(self):
        from pyrewards.cli import parse_args

        args = parse_args([
            "--interactive", "--run-quizzes",
            "--max-quiz-questions", "8", "--quiz-pause", "1.2",
        ])
        self.assertTrue(args.run_quizzes)
        self.assertEqual(args.max_quiz_questions, 8)
        self.assertEqual(args.quiz_pause, 1.2)

    def test_run_report_includes_quiz_progress(self):
        from pyrewards.cli import save_report

        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "latest.json"
            progress = [{
                "card": "Supersonic quiz",
                "status": "completed",
                "reason": "Visible quiz completion marker detected.",
                "questions_advanced": 3,
                "attempted_options": 7,
                "events": [{"event": "answer_attempt", "question": 1,
                            "option": "rqAnswerOption0", "progressed": False}],
            }]
            save_report(destination, "2026-01-01T12:00:00", "edge",
                        [], [], None, None, 1, progress)
            report = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(report["quiz_runs"], progress)
            self.assertNotIn("url", report["quiz_runs"][0])


if __name__ == "__main__":
    unittest.main()
