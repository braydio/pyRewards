"""Deterministic tests for the original filled-circle quiz workflow."""

import unittest
from unittest.mock import patch

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pyrewards.quiz import run_quiz


class Element:
    def __init__(self, *, identifier="", text="", callback=None):
        self.identifier = identifier
        self.text = text
        self.callback = callback
        self.click_count = 0

    def get_attribute(self, name):
        return self.identifier if name == "id" else None

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def click(self):
        self.click_count += 1
        if self.callback:
            self.callback()


class Switch:
    def __init__(self, driver):
        self.driver = driver

    def default_content(self):
        self.driver.in_frame = False

    def frame(self, frame):
        self.driver.in_frame = True


class FakeQuizDriver:
    def __init__(self, *, questions=2, correct=1, stall=False,
                 quiz=True, iframe=False, no_header=False):
        self.quiz = quiz
        self.iframe = iframe
        self.in_frame = False
        self.switch_to = Switch(self)
        self.started = False
        self.complete = False
        self.questions = questions
        self.correct = correct
        self.progress = 0
        self.stall = stall
        self.no_header = no_header
        self.attempts = []

    def find_elements(self, by, selector):
        assert by == By.CSS_SELECTOR
        if selector == "iframe":
            return [Element()] if self.iframe else []
        if not self.quiz or (self.iframe and not self.in_frame):
            return []
        if selector == "#rqStartQuiz":
            return [] if self.started else [Element(callback=self.start)]
        if selector == "#quizCompleteContainer":
            return [Element()] if self.complete else []
        if selector == "#rqHeaderCredits":
            return [Element()] if self.started and not self.no_header else []
        if selector == "#rqHeaderCredits span.filledCircle":
            return [Element() for _ in range(self.progress)]
        if selector == "[id^='rqAnswerOption']":
            return [
                Element(identifier=f"rqAnswerOption{i}",
                        callback=lambda i=i: self.answer(i))
                for i in range(3)
            ] if self.started and not self.complete else []
        return []

    def start(self):
        self.started = True

    def answer(self, index):
        self.attempts.append(index)
        if not self.stall and index == self.correct:
            self.progress += 1
            if self.progress == self.questions:
                self.complete = True


class InstantWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, check):
        result = check(self.driver)
        if not result:
            raise TimeoutException()
        return result


@patch("pyrewards.quiz.WebDriverWait", InstantWait)
class QuizTests(unittest.TestCase):
    def test_start_wrong_choice_then_advance_until_complete(self):
        driver = FakeQuizDriver(questions=2)
        result = run_quiz(driver, "Supersonic quiz", pause=0)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.questions_advanced, 2)
        self.assertEqual(result.attempted_options, 4)
        self.assertEqual(driver.attempts, [0, 1, 0, 1])
        self.assertEqual(len([e for e in result.events if e["event"] == "answer_attempt"]), 4)

    def test_no_quiz_does_not_click_anything(self):
        driver = FakeQuizDriver(quiz=False)
        result = run_quiz(driver, "Search activity", pause=0)
        self.assertEqual(result.status, "not_quiz")
        self.assertEqual(driver.attempts, [])

    def test_no_progress_stops_instead_of_looping(self):
        driver = FakeQuizDriver(stall=True)
        result = run_quiz(driver, "Supersonic quiz", pause=0)
        self.assertEqual(result.status, "stalled")
        self.assertEqual(driver.attempts, [0, 1, 2])

    def test_missing_progress_stops_without_trying_answers(self):
        driver = FakeQuizDriver(no_header=True)
        result = run_quiz(driver, "Supersonic quiz", pause=0)
        self.assertEqual(result.status, "unsupported")
        self.assertEqual(driver.attempts, [])

    def test_max_questions_is_enforced(self):
        driver = FakeQuizDriver(questions=100)
        result = run_quiz(driver, "Supersonic quiz", pause=0, max_questions=2)
        self.assertEqual(result.status, "limit_reached")
        self.assertEqual(result.questions_advanced, 2)
        self.assertEqual(driver.progress, 2)

    def test_quiz_inside_single_iframe(self):
        driver = FakeQuizDriver(questions=1, iframe=True)
        result = run_quiz(driver, "Supersonic quiz", pause=0)
        self.assertEqual(result.status, "completed")
        self.assertFalse(driver.in_frame)

    def test_completed_quiz_requires_a_completion_marker(self):
        driver = FakeQuizDriver(questions=100, stall=True)
        driver.complete = True
        result = run_quiz(driver, "Already done", pause=0)
        self.assertEqual(result.status, "completed")
        self.assertEqual(driver.attempts, [])


if __name__ == "__main__":
    unittest.main()
