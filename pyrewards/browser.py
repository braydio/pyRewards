"""Selenium browser support. The user, not the script, completes activities."""

from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .core import (
    Card,
    CardStatus,
    MODERN_CARD_TITLE_SELECTOR,
    REWARDS_URL,
    SECTION_SELECTORS,
    classify_status,
    extract_streak,
    is_redeem_card,
    offered_points,
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


def _section_elements(driver, section: str):
    for selector in SECTION_SELECTORS[section]:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if section == "Reward tiles":
            # Ignore decorative cards without a Rewards activity title and
            # avoid double-counting a tile nested in a legacy mee-card.
            elements = [
                element for element in elements
                if element.find_elements(By.CSS_SELECTOR, MODERN_CARD_TITLE_SELECTOR)
                and not element.find_elements(By.XPATH, "ancestor::mee-card")
            ]
        if elements:
            return elements
    return []


def wait_for_cards(driver, timeout: int) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: any(_section_elements(d, section) for section in SECTION_SELECTORS)
        )
        return True
    except TimeoutException:
        return False


def _title_and_description(element, section: str) -> tuple[str, str]:
    if section == "Reward tiles":
        titles = element.find_elements(By.CSS_SELECTOR, MODERN_CARD_TITLE_SELECTOR)
        subtitles = element.find_elements(
            By.CSS_SELECTOR, "p.text-fgCtrlNeutralSecondaryRest"
        )
        title = titles[0].text.strip() if titles else ""
        description = subtitles[0].text.strip() if subtitles else ""
        return title[:160], description[:300]

    lines = [line.strip() for line in element.text.splitlines() if line.strip()]
    return (lines[0] if lines else "")[:160], ""


def _click_target(element):
    # The provided React markup contains only a DIV and paragraphs. Its actual
    # clickable link/button commonly wraps the body, not the other way around.
    ancestors = element.find_elements(
        By.XPATH,
        "./ancestor::*[(self::a and @href) or self::button or @role='button' or @tabindex='0'][1]",
    )
    if ancestors:
        return ancestors[0]

    descendants = element.find_elements(
        By.CSS_SELECTOR, "a[href], button, [role='button']"
    )
    if descendants:
        return descendants[0]

    # For React cards with event handlers on a generic DIV, a normal Selenium
    # click on the card body bubbles to its parent. No JavaScript injection.
    return element


def _card_from_element(element, section: str, index: int) -> Card | None:
    title, description = _title_and_description(element, section)
    target = _click_target(element)
    href = target.get_attribute("href") or ""
    label = (target.get_attribute("aria-label") or
             element.get_attribute("aria-label") or "")

    if not title:
        title = label.strip()[:160]
    if not title:
        return None

    classes = [element.get_attribute("class") or ""]
    # Only inspect completion icons, not generic 'checked' text elsewhere.
    icons = element.find_elements(
        By.CSS_SELECTOR,
        "mee-rewards-points [class], [class*='SkypeCircleCheck'], "
        "[class*='AddMedium'], [class*='CheckmarkCircle']",
    )
    classes.extend(icon.get_attribute("class") or "" for icon in icons)

    point_badges = element.find_elements(
        By.CSS_SELECTOR, "p.text-statusInformativeTintFg"
    )
    points = offered_points(point_badges[0].text) if point_badges else None
    state = (
        CardStatus.REDEEM if is_redeem_card(title, label, href)
        else classify_status(classes, label)
    )
    return Card(
        section, index, title, state, href, True, description, points
    )


def discover_cards(driver) -> list[Card]:
    found: list[Card] = []
    for section in SECTION_SELECTORS:
        for index, element in enumerate(_section_elements(driver, section)):
            card = _card_from_element(element, section, index)
            if card is not None:
                found.append(card)
    return found


def get_streak(driver) -> int | None:
    streaks = driver.find_elements(By.CSS_SELECTOR, "mee-rewards-streak")
    return extract_streak(streaks[0].get_attribute("aria-label")) if streaks else None


def open_card_for_user(driver, card: Card, timeout: int):
    """Open an activity only after its explicit interactive prompt.

    Finds the same card by title again, so dashboard reordering between
    activities does not cause the script to click a different item.
    """
    elements = _section_elements(driver, card.section)
    matches = [
        element for element in elements
        if _title_and_description(element, card.section)[0] == card.title
    ]
    if len(matches) != 1:
        raise LookupError(
            f"Cannot uniquely identify {card.title!r} on the refreshed dashboard. "
            "Inspect the dashboard again."
        )
    target = _click_target(matches[0])
    actual_href = target.get_attribute("href") or ""
    if card.href and actual_href != card.href:
        raise LookupError("Card link changed since discovery. Refusing to open a different link.")

    before_handles = set(driver.window_handles)
    before_url = driver.current_url
    target.click()
    try:
        WebDriverWait(driver, min(timeout, 4)).until(
            lambda d: bool(set(d.window_handles) - before_handles)
            or d.current_url != before_url
        )
    except TimeoutException:
        # Some activities use a React modal instead of navigating.
        pass
    new_handles = [h for h in driver.window_handles if h not in before_handles]
    if new_handles:
        driver.switch_to.window(new_handles[-1])
    return before_handles


def open_card_in_own_tab(driver, card: Card, timeout: int,
                         dashboard_handle: str) -> str:
    """Open a card in an independent tab, preserving every prior activity tab.

    A fresh dashboard tab is used as a launcher so both JS-driven navigation
    and cards that open a second tab work. For the latter, discard only the
    temporary launcher and retain the new activity tab. Any failed attempt
    closes only tabs created for that attempt.
    """
    driver.switch_to.window(dashboard_handle)
    existing = set(driver.window_handles)
    driver.switch_to.new_window("tab")
    launcher = driver.current_window_handle
    try:
        driver.get(REWARDS_URL)
        wait_for_page(driver, timeout)
        if not wait_for_cards(driver, timeout):
            raise LookupError("No activity cards were loaded in the new tab.")

        open_card_for_user(driver, card, timeout)
        destination = driver.current_window_handle

        if destination != launcher:
            driver.switch_to.window(launcher)
            driver.close()
            driver.switch_to.window(destination)
        return destination
    except Exception:
        for handle in list(driver.window_handles):
            if handle not in existing:
                try:
                    driver.switch_to.window(handle)
                    driver.close()
                except WebDriverException:
                    pass
        try:
            driver.switch_to.window(dashboard_handle)
        except WebDriverException:
            pass
        raise


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
