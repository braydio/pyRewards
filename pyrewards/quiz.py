"""Bounded Selenium quiz navigation, modeled on pyRewards' 2024 quiz functions.

This deliberately supports *observed* Microsoft Rewards quiz markers only.
Unknown pages, search tasks, and verification challenges are never clicked.
No external answer service, credential extraction, or blind DOM-wide clicking.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

LOG = logging.getLogger("pyrewards.quiz")
START = "#rqStartQuiz"
HEADER = "#rqHeaderCredits"
FILLED = "#rqHeaderCredits span.filledCircle"
COMPLETE = "#quizCompleteContainer"
ANSWERS = "[id^='rqAnswerOption']"
QUESTION_TEXT = (
    "#rqQuestionText",
    "#rqQuestion",
    ".rqQuestion",
    "[data-testid='quiz-question']",
)
MAX_OPTIONS = 8
MAX_FRAMES = 8


@dataclass
class QuizRun:
    """Only non-sensitive information is retained in activity reports."""

    card: str
    status: str = "not_quiz"
    reason: str = ""
    questions_advanced: int = 0
    attempted_options: int = 0
    events: list[dict[str, object]] = field(default_factory=list)

    def event(self, kind: str, **details: object) -> None:
        entry = {"event": kind, **details}
        self.events.append(entry)
        LOG.info("%s: %s %s", self.card, kind, details)


def _visible(driver, selector: str):
    """Find visible elements without relying on stale cached WebElements."""
    try:
        return [
            element for element in driver.find_elements(By.CSS_SELECTOR, selector)
            if element.is_displayed()
        ]
    except StaleElementReferenceException:
        return []


def _quiz_marker_present(driver) -> bool:
    return any(_visible(driver, marker) for marker in (START, HEADER, COMPLETE, ANSWERS))


def _locate_quiz_context(driver) -> bool:
    """Select main document or one iframe containing the known quiz controls."""
    driver.switch_to.default_content()
    if _quiz_marker_present(driver):
        return True

    for frame in driver.find_elements(By.CSS_SELECTOR, "iframe")[:MAX_FRAMES]:
        try:
            driver.switch_to.frame(frame)
            if _quiz_marker_present(driver):
                return True
        except (WebDriverException, StaleElementReferenceException):
            pass
        driver.switch_to.default_content()
    return False


def _complete(driver) -> bool:
    return bool(_visible(driver, COMPLETE))


def _progress(driver) -> int | None:
    """Return the original 'filled circles' counter or None if unsupported."""
    if not _visible(driver, HEADER):
        return None
    return len(_visible(driver, FILLED))


def _question_text(driver) -> str:
    for selector in QUESTION_TEXT:
        elements = _visible(driver, selector)
        if elements:
            text = elements[0].text.strip()
            if text:
                return text[:200]
    return ""


def _signature(driver) -> tuple[int | None, str]:
    return _progress(driver), _question_text(driver)


def _answers(driver) -> list[tuple[str, object]]:
    """Only explicitly named Rewards answer elements, in numbered order."""
    found = []
    for element in _visible(driver, ANSWERS):
        if not element.is_enabled():
            continue
        identifier = element.get_attribute("id") or ""
        if not re.fullmatch(r"rqAnswerOption\d+", identifier):
            continue
        found.append((identifier, element))
    found.sort(key=lambda pair: int(pair[0].removeprefix("rqAnswerOption")))
    return found[:MAX_OPTIONS]


def _click(driver, element) -> None:
    """Click normally; one scroll-and-retry for an intercepted click."""
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        element.click()


def _changed(driver, prior: tuple[int | None, str]) -> bool:
    if _complete(driver):
        return True
    now = _signature(driver)
    if now[0] is not None and prior[0] is not None and now[0] > prior[0]:
        return True
    return bool(now[1] and prior[1] and now[1] != prior[1])


def _wait_for_change(driver, prior: tuple[int | None, str], timeout: float) -> bool:
    try:
        WebDriverWait(driver, timeout).until(lambda d: _changed(d, prior))
        return True
    except TimeoutException:
        return False


def run_quiz(
    driver,
    card_title: str,
    *,
    discovery_timeout: float = 6,
    step_timeout: float = 2.5,
    max_questions: int = 20,
    pause: float = 0.7,
) -> QuizRun:
    """Run a known, visible Rewards quiz from the *already opened* activity tab.

    Only called after the user explicitly opts in to running that activity.
    Reports 'completed' exclusively when the visible completion marker exists.
    """
    if discovery_timeout <= 0 or step_timeout <= 0:
        raise ValueError("Quiz timeouts must be positive")
    if max_questions < 1 or pause < 0:
        raise ValueError("Invalid maximum questions or pause")

    result = QuizRun(card=card_title)
    try:
        try:
            WebDriverWait(driver, discovery_timeout).until(_locate_quiz_context)
        except TimeoutException:
            result.reason = "No recognized quiz controls were found after opening the activity."
            result.event("not_quiz")
            return result

        if _complete(driver):
            result.status = "completed"
            result.reason = "Quiz already shows its completion marker."
            result.event("already_complete")
            return result

        starts = _visible(driver, START)
        if starts:
            result.event("start")
            _click(driver, starts[0])
            try:
                WebDriverWait(driver, discovery_timeout).until(
                    lambda d: _complete(d) or bool(_answers(d))
                )
            except TimeoutException:
                result.status = "unsupported"
                result.reason = "Quiz start did not reveal recognizable answer options."
                result.event("unsupported", stage="start")
                return result

        if _complete(driver):
            result.status = "completed"
            result.reason = "Quiz displayed its completion marker."
            result.event("complete")
            return result

        result.status = "running"
        seen_signatures: set[tuple[int | None, str]] = set()
        for question in range(1, max_questions + 1):
            if _complete(driver):
                result.status = "completed"
                result.reason = "Visible quiz completion marker detected."
                result.event("complete")
                return result

            before = _signature(driver)
            if before == (None, ""):
                result.status = "unsupported"
                result.reason = "Could not observe question progress or text."
                result.event("unsupported", stage="progress")
                return result
            if before in seen_signatures:
                result.status = "stalled"
                result.reason = "The same quiz question reappeared without progress."
                result.event("stalled", question=question)
                return result
            seen_signatures.add(before)

            options = _answers(driver)
            if not options:
                result.status = "unsupported"
                result.reason = "No visible enabled rqAnswerOption controls."
                result.event("unsupported", stage="options", question=question)
                return result

            result.event(
                "question",
                number=question,
                initial_progress=before[0],
                available_options=len(options),
            )
            advanced = False
            option_ids = [identifier for identifier, _ in options]
            for option_id in option_ids:
                # The UI may re-render after an incorrect choice. Always locate
                # the answer again rather than clicking a stale WebElement.
                current = dict(_answers(driver))
                option = current.get(option_id)
                if option is None:
                    result.event("option_disappeared", question=question, option=option_id)
                    continue

                if pause:
                    time.sleep(pause)
                try:
                    _click(driver, option)
                except WebDriverException as exc:
                    result.event("click_failed", question=question, option=option_id,
                                 error=type(exc).__name__)
                    continue
                result.attempted_options += 1
                changed = _wait_for_change(driver, before, step_timeout)
                result.event(
                    "answer_attempt",
                    question=question,
                    option=option_id,
                    progressed=changed,
                    progress_after=_progress(driver),
                )
                if _complete(driver):
                    result.status = "completed"
                    result.reason = "Visible quiz completion marker detected."
                    result.questions_advanced += 1
                    result.event("complete")
                    return result
                if changed:
                    result.questions_advanced += 1
                    advanced = True
                    break

            if not advanced:
                result.status = "stalled"
                result.reason = "Tried available choices without observable advancement."
                result.event("stalled", question=question)
                return result

        result.status = "limit_reached"
        result.reason = f"Stopped after the configured maximum of {max_questions} questions."
        result.event("limit_reached", max_questions=max_questions)
        return result

    except WebDriverException as exc:
        result.status = "error"
        result.reason = f"Browser error: {type(exc).__name__}"
        result.event("error", type=type(exc).__name__)
        return result
    finally:
        # Leave the driver in a normal document context for tab cleanup.
        try:
            driver.switch_to.default_content()
        except WebDriverException:
            LOG.warning("Could not restore top-level frame after quiz.")
