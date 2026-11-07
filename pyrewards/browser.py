"""Selenium browser support. The user, not the script, completes activities."""

from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .core import (
    Card,
    CardStatus,
    REWARDS_URL,
    SECTION_SELECTORS,
    classify_status,
    extract_streak,
    is_redeem_card,
)


def create_driver(browser: str, profile_dir: Path):
    profile_dir = profile_dir.expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    if browser == "edge":
        options = webdriver.EdgeOptions()
        factory = webdriver.Edge
    elif browser == "chrome":
        options = webdriver.ChromeOptions()
        factory = webdriver.Chrome
    else:
        raise ValueError(f"Unsupported browser: {browser}")
    # A dedicated persistent profile avoids touching an already-running
    # personal browser profile. Selenium Manager resolves the driver.
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--start-maximized")
    return factory(options=options)


def wait_for_page(driver, timeout: int) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def wait_for_cards(driver, timeout: int) -> bool:
    selectors = tuple(s for group in SECTION_SELECTORS.values() for s in group)
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: any(d.find_elements(By.CSS_SELECTOR, s) for s in selectors)
        )
        return True
    except TimeoutException:
        return False


def _section_elements(driver, section: str):
    for selector in SECTION_SELECTORS[section]:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            return elements
    return []


def discover_cards(driver) -> list[Card]:
    found: list[Card] = []
    for section in SECTION_SELECTORS:
        for index, element in enumerate(_section_elements(driver, section)):
            anchors = element.find_elements(By.CSS_SELECTOR, "a[href]")
            anchor = anchors[0] if anchors else None
            href = anchor.get_attribute("href") or "" if anchor else ""
            label = (anchor.get_attribute("aria-label") or "") if anchor else ""
            lines = [line.strip() for line in element.text.splitlines() if line.strip()]
            title = (lines[0] if lines else label or f"Untitled card {index + 1}")[:160]
            classes = [element.get_attribute("class") or ""]
            icon_elements = element.find_elements(
                By.CSS_SELECTOR,
                "mee-rewards-points [class], [class*='SkypeCircleCheck'], [class*='AddMedium']",
            )
            classes.extend(icon.get_attribute("class") or "" for icon in icon_elements)
            state = (
                CardStatus.REDEEM
                if is_redeem_card(title, label, href)
                else classify_status(classes, label)
            )
            found.append(Card(section, index, title, state, href))
    return found


def get_streak(driver) -> int | None:
    streaks = driver.find_elements(By.CSS_SELECTOR, "mee-rewards-streak")
    return extract_streak(streaks[0].get_attribute("aria-label")) if streaks else None


def open_card_for_user(driver, card: Card, timeout: int):
    """Only called after a user chooses 'open' for this particular card.

    Returns the window handles that existed before clicking; restoration only
    closes newly created handles, never tabs already open in the session.
    """
    elements = _section_elements(driver, card.section)
    if card.index >= len(elements):
        raise LookupError("Card moved or disappeared. Inspect the dashboard again.")
    anchors = elements[card.index].find_elements(By.CSS_SELECTOR, "a[href]")
    if not anchors:
        raise LookupError("This card has no clickable link.")
    anchor = anchors[0]
    if (anchor.get_attribute("href") or "") != card.href:
        raise LookupError("Card changed since discovery. Refusing to open a different link.")

    before_handles = set(driver.window_handles)
    before_url = driver.current_url
    anchor.click()
    try:
        WebDriverWait(driver, min(timeout, 4)).until(
            lambda d: bool(set(d.window_handles) - before_handles)
            or d.current_url != before_url
        )
    except TimeoutException:
        # Some cards open an in-place dialog rather than navigating.
        pass
    new_handles = [h for h in driver.window_handles if h not in before_handles]
    if new_handles:
        driver.switch_to.window(new_handles[-1])
    return before_handles


def return_to_dashboard(driver, previous_handles: set[str], timeout: int) -> None:
    for handle in list(driver.window_handles):
        if handle not in previous_handles:
            driver.switch_to.window(handle)
            driver.close()
    remaining = driver.window_handles
    if not remaining:
        raise RuntimeError("All browser tabs were closed.")
    original = next((h for h in remaining if h in previous_handles), remaining[0])
    driver.switch_to.window(original)
    if driver.current_url != REWARDS_URL:
        driver.get(REWARDS_URL)
    else:
        driver.refresh()
    wait_for_page(driver, timeout)
    wait_for_cards(driver, timeout)
