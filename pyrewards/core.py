"""Pure parsing and reporting helpers, independent of Selenium."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable
from urllib.parse import urlsplit


REWARDS_URL = "https://rewards.microsoft.com/"

# Microsoft's dashboard uses both legacy mee-card components and newer React
# tiles. Keep the selectors centralized so new markup can be added safely.
MODERN_CARD_TITLE_SELECTOR = "p.text-globalBody2Strong"
SECTION_SELECTORS = {
    "Daily set": (
        "mee-rewards-daily-set-section mee-card",
        "mee-rewards-daily-set-section [class*='card']",
    ),
    "More activities": (
        "#more-activities mee-card",
        "mee-rewards-more-activities-section mee-card",
    ),
    "Reward tiles": (
        "div.p-paddingCardBodyDefaultOutside",
    ),
}


class CardStatus(str, Enum):
    COMPLETED = "completed"
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    REDEEM = "redeem"


@dataclass(frozen=True)
class Card:
    section: str
    index: int
    title: str
    status: CardStatus
    href: str = field(default="", repr=False)
    # New React tiles may use a clickable wrapper or onclick handler without
    # an <a href>. None retains legacy inference from href for older callers.
    clickable: bool | None = None
    description: str = ""
    points_offer: int | None = None

    @property
    def can_open(self) -> bool:
        return bool(self.href) if self.clickable is None else self.clickable

    def report_entry(self) -> dict[str, str | bool | int | None]:
        """Never write activity URLs, which may contain session parameters."""
        return {
            "section": self.section,
            "title": self.title,
            "description": self.description,
            "points_offer": self.points_offer,
            "status": self.status.value,
            "clickable": self.can_open,
        }


def classify_status(classes: Iterable[str], aria_label: str = "") -> CardStatus:
    """Be conservative: an offered +10 points is not proof of collection."""
    tokens = set(re.split(r"\s+", " ".join(classes).lower().strip()))
    if any(
        "skypecirclecheck" in token
        or token in {"completed", "is-complete", "checkmarkcircle", "icon-check"}
        for token in tokens
    ):
        return CardStatus.COMPLETED
    label = aria_label.lower()
    if any(phrase in label for phrase in ("already completed", "you've completed", "completed today")):
        return CardStatus.COMPLETED
    if any("addmedium" in token or token in {"available", "is-available"} for token in tokens):
        return CardStatus.AVAILABLE
    return CardStatus.UNKNOWN


def is_redeem_card(title: str, aria_label: str = "", href: str = "") -> bool:
    text = f"{title} {aria_label}".lower()
    path = urlsplit(href).path.lower()
    return "redeem now" in text or path.startswith("/redeem")


def offered_points(raw: str) -> int | None:
    """Extract a promotional +N badge, never interpreted as earned points."""
    match = re.fullmatch(r"\s*\+\s*(\d{1,5})\s*", raw)
    return int(match.group(1)) if match else None


def extract_streak(aria_label: str | None) -> int | None:
    if not aria_label:
        return None
    before = re.search(r"(\d[\d,]*)\s*,?\s*current day streak", aria_label, re.I)
    after = re.search(r"current day streak\s*[:,]?\s*(\d[\d,]*)", aria_label, re.I)
    match = before or after
    return int(match.group(1).replace(",", "")) if match else None
