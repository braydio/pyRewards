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


class BatchOpeningTests(unittest.TestCase):
    def test_skip_four_open_three_selects_positions_five_to_seven(self):
        from pyrewards.cli import select_cards

        cards = [
            Card("Reward tiles", i, f"Card #{i + 1}", CardStatus.UNKNOWN,
                 clickable=True)
            for i in range(10)
        ]
        self.assertEqual(
            [(position, card.title) for position, card in select_cards(cards, 4, 3)],
            [(5, "Card #5"), (6, "Card #6"), (7, "Card #7")],
        )
        self.assertEqual(len(select_cards(cards, 9, 3)), 1)
        self.assertEqual(select_cards(cards, 11, 3), [])

    def test_new_options_and_invalid_combinations(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from pyrewards.cli import parse_args

        args = parse_args(["--skip", "4", "--open", "3", "--run-quizzes"])
        self.assertEqual((args.skip, args.open_count), (4, 3))
        self.assertTrue(args.run_quizzes)
        for invalid in (
            ["--skip", "4"], ["--skip", "-1", "--open", "3"],
            ["--skip", "4", "--open", "-1"], ["--open", "3", "--interactive"],
            ["--open", "0"], ["--run-quizzes"],
        ):
            with self.subTest(invalid=invalid):
                with redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit):
                        parse_args(invalid)

    def test_batch_opens_exact_card_positions_without_substitution(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import Mock, patch, call
        from pyrewards.cli import parse_args, run

        cards = [
            Card("Reward tiles", i, f"Card #{i + 1}", CardStatus.UNKNOWN,
                 clickable=True)
            for i in range(9)
        ]
        # Position #6 is completed: do not use card #8 as a replacement.
        cards[5] = Card("Reward tiles", 5, "Card #6",
                        CardStatus.COMPLETED, clickable=True)

        driver = Mock()
        driver.current_window_handle = "dashboard"
        with tempfile.TemporaryDirectory() as temp:
            args = parse_args(["--skip", "4", "--open", "3",
                               "--report", str(Path(temp) / "batch.json")])
            with patch("pyrewards.cli.create_driver", return_value=driver), \
                 patch("pyrewards.cli.wait_for_page"), \
                 patch("pyrewards.cli.wait_for_cards", return_value=True), \
                 patch("pyrewards.cli.get_streak", return_value=None), \
                 patch("pyrewards.cli.discover_cards", return_value=cards), \
                 patch("pyrewards.cli.open_card_in_own_tab") as opener, \
                 patch("pyrewards.cli.sys.stdin.isatty", return_value=True), \
                 patch("builtins.input", return_value="") as prompt, \
                 redirect_stdout(StringIO()):
                self.assertEqual(run(args), 0)

            self.assertEqual(opener.call_count, 2)
            self.assertEqual([c.args[1].title for c in opener.call_args_list],
                             ["Card #5", "Card #7"])
            self.assertEqual(prompt.call_count, 1)
            result = json.loads(Path(args.report).read_text(encoding="utf-8"))
            self.assertEqual(result["selection"], {"skip": 4, "open": 3})
            self.assertEqual([x["position"] for x in result["open_results"]], [5, 6, 7])
            self.assertEqual([x["status"] for x in result["open_results"]],
                             ["opened", "skipped_completed_or_redeem", "opened"])
            driver.quit.assert_called_once()

    def test_batch_mode_without_terminal_does_not_instantly_close_new_tabs(self):
        from unittest.mock import Mock, patch
        from pyrewards.cli import parse_args, run

        driver = Mock()
        driver.current_window_handle = "dashboard"
        args = parse_args(["--open", "1"])
        cards = [Card("Reward tiles", 0, "Card #1", CardStatus.UNKNOWN,
                      clickable=True)]
        with patch("pyrewards.cli.create_driver", return_value=driver), \
             patch("pyrewards.cli.wait_for_page"), \
             patch("pyrewards.cli.wait_for_cards", return_value=True), \
             patch("pyrewards.cli.discover_cards", return_value=cards), \
             patch("pyrewards.cli.get_streak", return_value=None), \
             patch("pyrewards.cli.sys.stdin.isatty", return_value=False), \
             patch("pyrewards.cli.open_card_in_own_tab") as opener:
            self.assertEqual(run(args), 2)
            opener.assert_not_called()
            driver.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
