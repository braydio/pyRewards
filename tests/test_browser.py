"""Mocked Selenium regression tests for the supplied React Rewards markup."""

import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from pyrewards.browser import discover_cards, open_card_for_user
from pyrewards.core import CardStatus, REWARDS_URL


class ReactCardTests(unittest.TestCase):
    def setUp(self):
        self.title = Mock(text="Rome Mild Roman Historic")
        self.subtitle = Mock(text="Historic walks in pleasant temps")
        self.badge = Mock(text="+10")
        self.card = Mock(text="Rome Mild Roman Historic\nHistoric walks in pleasant temps\n+10")
        self.card.get_attribute.side_effect = lambda attribute: (
            "flex grow flex-col p-paddingCardBodyDefaultOutside gap-2"
            if attribute == "class" else ""
        )

        def card_descendants(by, selector):
            if (by, selector) == (By.CSS_SELECTOR, "p.text-globalBody2Strong"):
                return [self.title]
            if (by, selector) == (By.CSS_SELECTOR, "p.text-fgCtrlNeutralSecondaryRest"):
                return [self.subtitle]
            if (by, selector) == (By.CSS_SELECTOR, "p.text-statusInformativeTintFg"):
                return [self.badge]
            return []
        self.card.find_elements.side_effect = card_descendants

        self.driver = Mock(current_url=REWARDS_URL, window_handles=["dashboard"])
        self.driver.find_elements.side_effect = lambda by, selector: (
            [self.card] if (by, selector) ==
            (By.CSS_SELECTOR, "div.p-paddingCardBodyDefaultOutside") else []
        )

    def test_discovers_card_from_supplied_classes_without_anchor(self):
        cards = discover_cards(self.driver)
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card.title, "Rome Mild Roman Historic")
        self.assertEqual(card.description, "Historic walks in pleasant temps")
        self.assertEqual(card.points_offer, 10)
        self.assertEqual(card.status, CardStatus.UNKNOWN)
        self.assertTrue(card.can_open)
        self.assertEqual(card.href, "")

    def test_clicks_body_when_no_anchor_or_button(self):
        card = discover_cards(self.driver)[0]
        with patch("pyrewards.browser.WebDriverWait") as wait:
            wait.return_value.until.side_effect = TimeoutException()
            handles = open_card_for_user(self.driver, card, timeout=2)
        self.card.click.assert_called_once()
        self.assertEqual(handles, {"dashboard"})

    def test_clicks_outer_wrapper_when_it_is_a_button(self):
        wrapper = Mock()
        wrapper.get_attribute.side_effect = lambda attribute: (
            "" if attribute in ("href", "aria-label") else None
        )
        original = self.card.find_elements.side_effect

        def with_wrapper(by, selector):
            if by == By.XPATH and selector.startswith("./ancestor::"):
                return [wrapper]
            return original(by, selector)

        self.card.find_elements.side_effect = with_wrapper
        card = discover_cards(self.driver)[0]
        with patch("pyrewards.browser.WebDriverWait") as wait:
            wait.return_value.until.side_effect = TimeoutException()
            open_card_for_user(self.driver, card, timeout=2)
        wrapper.click.assert_called_once()
        self.card.click.assert_not_called()

    def test_refuses_ambiguous_identical_titles(self):
        card = discover_cards(self.driver)[0]
        self.driver.find_elements.side_effect = lambda by, selector: (
            [self.card, self.card]
            if (by, selector) == (By.CSS_SELECTOR, "div.p-paddingCardBodyDefaultOutside")
            else []
        )
        with self.assertRaisesRegex(LookupError, "Cannot uniquely identify"):
            open_card_for_user(self.driver, card, timeout=2)
        self.card.click.assert_not_called()


class TabSwitcher:
    def __init__(self, driver):
        self.driver = driver

    def window(self, handle):
        if handle not in self.driver.window_handles:
            raise ValueError("Unknown window")
        self.driver.current_window_handle = handle

    def new_window(self, kind):
        assert kind == "tab"
        handle = f"tab-{self.driver.next_tab}"
        self.driver.next_tab += 1
        self.driver.window_handles.append(handle)
        self.driver.current_window_handle = handle


class FakeWindowDriver:
    def __init__(self):
        self.window_handles = ["dashboard", "older-activity"]
        self.current_window_handle = "dashboard"
        self.switch_to = TabSwitcher(self)
        self.next_tab = 1
        self.visited = []

    def get(self, url):
        self.visited.append((self.current_window_handle, url))

    def close(self):
        self.window_handles.remove(self.current_window_handle)
        self.current_window_handle = self.window_handles[-1]


class SeparateTabTests(unittest.TestCase):
    def setUp(self):
        from pyrewards.core import Card
        self.driver = FakeWindowDriver()
        self.card = Card("Reward tiles", 4, "Card #5", CardStatus.UNKNOWN,
                         clickable=True)

    def test_same_tab_navigation_keeps_own_activity_tab(self):
        from pyrewards.browser import open_card_in_own_tab

        with patch("pyrewards.browser.wait_for_cards", return_value=True), \
             patch("pyrewards.browser.wait_for_page"), \
             patch("pyrewards.browser.open_card_for_user") as open_card:
            tab = open_card_in_own_tab(self.driver, self.card, 3, "dashboard")

        self.assertEqual(tab, "tab-1")
        self.assertEqual(self.driver.window_handles,
                         ["dashboard", "older-activity", "tab-1"])
        self.assertEqual(self.driver.visited[0][0], "tab-1")
        open_card.assert_called_once()

    def test_popup_click_discards_launcher_but_keeps_activity_tab(self):
        from pyrewards.browser import open_card_in_own_tab

        def popup(driver, card, timeout):
            driver.window_handles.append("quiz-popup")
            driver.current_window_handle = "quiz-popup"

        with patch("pyrewards.browser.wait_for_cards", return_value=True), \
             patch("pyrewards.browser.wait_for_page"), \
             patch("pyrewards.browser.open_card_for_user", side_effect=popup):
            tab = open_card_in_own_tab(self.driver, self.card, 3, "dashboard")

        self.assertEqual(tab, "quiz-popup")
        self.assertEqual(self.driver.window_handles,
                         ["dashboard", "older-activity", "quiz-popup"])
        self.assertEqual(self.driver.current_window_handle, "quiz-popup")

    def test_failed_click_cleans_only_attempt_tabs(self):
        from pyrewards.browser import open_card_in_own_tab

        with patch("pyrewards.browser.wait_for_cards", return_value=True), \
             patch("pyrewards.browser.wait_for_page"), \
             patch("pyrewards.browser.open_card_for_user",
                   side_effect=LookupError("Card moved")):
            with self.assertRaisesRegex(LookupError, "Card moved"):
                open_card_in_own_tab(self.driver, self.card, 3, "dashboard")

        self.assertEqual(self.driver.window_handles,
                         ["dashboard", "older-activity"])
        self.assertEqual(self.driver.current_window_handle, "dashboard")


if __name__ == "__main__":
    unittest.main()
