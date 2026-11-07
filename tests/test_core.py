import unittest

from pyrewards.core import (
    Card,
    CardStatus,
    classify_status,
    extract_streak,
    is_redeem_card,
    offered_points,
)


class CardParsingTests(unittest.TestCase):
    def test_classifies_known_completed_icon(self):
        self.assertEqual(classify_status(["icon SkypeCircleCheck"]), CardStatus.COMPLETED)

    def test_classifies_known_available_icon(self):
        self.assertEqual(classify_status(["icon AddMedium"]), CardStatus.AVAILABLE)

    def test_unknown_is_not_assumed_completed(self):
        self.assertEqual(classify_status(["card"], "Complete 3 searches"), CardStatus.UNKNOWN)

    def test_completed_aria_label(self):
        self.assertEqual(classify_status([], "You've completed this activity"), CardStatus.COMPLETED)

    def test_redeem_is_separate_from_earning(self):
        self.assertTrue(is_redeem_card("Redeem now"))
        self.assertTrue(is_redeem_card("Gift cards", href="https://rewards.microsoft.com/redeem"))
        self.assertFalse(is_redeem_card("Daily quiz", href="https://www.bing.com/"))

    def test_offered_points_are_not_earnings(self):
        self.assertEqual(offered_points("+10"), 10)
        self.assertEqual(offered_points("+ 10"), 10)
        self.assertIsNone(offered_points("10 points earned"))

    def test_href_less_react_card_is_clickable(self):
        card = Card("Reward tiles", 0, "Rome Mild Roman Historic",
                    CardStatus.UNKNOWN, clickable=True,
                    description="Historic walks in pleasant temps", points_offer=10)
        report = card.report_entry()
        self.assertTrue(card.can_open)
        self.assertEqual(report["points_offer"], 10)
        self.assertEqual(report["description"], "Historic walks in pleasant temps")

    def test_streak_text(self):
        self.assertEqual(extract_streak("1,234, Current day streak"), 1234)
        self.assertEqual(extract_streak("Current day streak: 17"), 17)
        self.assertIsNone(extract_streak("Next goal in 5 days"))
        self.assertIsNone(extract_streak(None))

    def test_report_does_not_leak_activity_link(self):
        card = Card("Daily set", 0, "Quiz", CardStatus.UNKNOWN,
                    "https://example.com/?secret=private")
        self.assertNotIn("secret", str(card.report_entry()))
        self.assertTrue(card.report_entry()["clickable"])


if __name__ == "__main__":
    unittest.main()
