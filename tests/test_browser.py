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


if __name__ == "__main__":
    unittest.main()
