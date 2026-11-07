"""Pure parsing and reporting helpers, independent of Selenium."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable
from urllib.parse import urlsplit


REWARDS_URL = "https://rewards.microsoft.com/"

# The first selector with results wins for each section. Kept in one place
# because Microsoft's dashboard markup can change independently of the code.
SECTION_SELECTORS = {
    "Daily set": (
        "mee-rewards-daily-set-section mee-card",
        "mee-rewards-daily-set-section [class*='card']",
    ),
    "More activities": (
        "#more-activities mee-card",
        "mee-rewards-more-activities-section mee-card",
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

    def report_entry(self) -> dict[str, str | bool]:
        """Never write activity URLs, which may contain session parameters."""
        return {
            "section": self.section,
            "title": self.title,
            "status": self.status.value,
            "clickable": bool(self.href),
        }


def classify_status(classes: Iterable[str], aria_label: str = "") -> CardStatus:
    """Be conservative: unrecognized icons are UNKNOWN, not completed."""
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


def extract_streak(aria_label: str | None) -> int | None:
    if not aria_label:
        return None
    before = re.search(r"(\d[\d,]*)\s*,?\s*current day streak", aria_label, re.I)
    after = re.search(r"current day streak\s*[:,]?\s*(\d[\d,]*)", aria_label, re.I)
    match = before or after
    return int(match.group(1).replace(",", "")) if match else None
