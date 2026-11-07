"""Console entry point for an inspect-first, user-driven Rewards assistant."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from selenium.common.exceptions import WebDriverException

from .browser import (
    create_driver,
    discover_cards,
    get_streak,
    open_card_for_user,
    return_to_dashboard,
    wait_for_cards,
    wait_for_page,
)
from .core import Card, CardStatus, REWARDS_URL

LOG = logging.getLogger("pyrewards")


def positive_int(raw: str) -> int:
    number = int(raw)
    if number < 1:
        raise argparse.ArgumentTypeError("Timeout must be at least 1 second")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Microsoft Rewards activities and optionally open them for manual completion."
    )
    parser.add_argument("--browser", choices=("edge", "chrome"), default="edge")
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path.home() / ".pyrewards" / "browser-profile",
        help="Dedicated persistent browser profile. Do not point at an open personal profile.",
    )
    parser.add_argument("--timeout", type=positive_int, default=15)
    parser.add_argument("--interactive", action="store_true", help="Prompt before opening each activity.")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("runs") / "latest.json",
        help="Where to save the status report (no account identifiers or URLs).",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def show_cards(cards: list[Card]) -> None:
    section = None
    for card in cards:
        if section != card.section:
            section = card.section
            print(f"\n{section}")
        print(f"  [{card.status.value:9}] {card.title}" + (f" (+{card.points_offer} offered)" if card.points_offer is not None else ""))
        if card.description:
            print(f"             {card.description}")
    counts = Counter(card.status.value for card in cards)
    print(
        f"\nTotal: {len(cards)} | completed: {counts['completed']} | "
        f"available: {counts['available']} | unknown: {counts['unknown']} | redeem: {counts['redeem']}"
    )


def save_report(path: Path, started: str, browser: str, initial: list[Card],
                final: list[Card], streak_before: int | None,
                streak_after: int | None, manually_opened: int) -> None:
    data = {
        "started_at": started,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "browser": browser,
        "streak_before": streak_before,
        "streak_after": streak_after,
        "opened_for_manual_completion": manually_opened,
        "before": [card.report_entry() for card in initial],
        "after": [card.report_entry() for card in final],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport saved to {path}")


def run(args: argparse.Namespace) -> int:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    driver = None
    try:
        driver = create_driver(args.browser, args.profile_dir)
        driver.get(REWARDS_URL)
        wait_for_page(driver, args.timeout)
        wait_for_cards(driver, args.timeout)
        initial = discover_cards(driver)
        if not initial and sys.stdin.isatty():
            print("No activity cards detected. If prompted, sign in manually in the browser.")
            input("After the Rewards dashboard loads, press Enter to inspect again...")
            driver.get(REWARDS_URL)
            wait_for_page(driver, args.timeout)
            wait_for_cards(driver, args.timeout)
            initial = discover_cards(driver)
        if not initial:
            LOG.error("No supported cards found. You may be signed out or the dashboard markup may have changed.")
            return 2

        streak_before = get_streak(driver)
        print("Initial dashboard snapshot")
        show_cards(initial)
        opened = 0

        if args.interactive:
            for card in initial:
                if card.status in (CardStatus.COMPLETED, CardStatus.REDEEM) or not card.can_open:
                    continue
                answer = input(f"\n{card.title}\n[o]pen / [s]kip / [q]uit: ").strip().lower()
                if answer == "q":
                    break
                if answer != "o":
                    continue
                # Keep the starting tabs so even a failed click can be cleaned up.
                previous_handles = set(driver.window_handles)
                try:
                    open_card_for_user(driver, card, args.timeout)
                    opened += 1
                    input("Complete the activity yourself in the browser, then press Enter...")
                except (LookupError, WebDriverException) as exc:
                    LOG.warning("Could not open %s: %s", card.title, exc)
                finally:
                    return_to_dashboard(driver, previous_handles, args.timeout)

        final = discover_cards(driver)
        streak_after = get_streak(driver)
        print("\nFinal dashboard snapshot")
        show_cards(final)
        if streak_before is not None or streak_after is not None:
            print(f"Streak: {streak_before if streak_before is not None else '?'} -> "
                  f"{streak_after if streak_after is not None else '?'}")
        save_report(args.report, started, args.browser, initial, final,
                    streak_before, streak_after, opened)
        return 0
    except (OSError, WebDriverException, RuntimeError) as exc:
        LOG.error("Browser run failed: %s", exc)
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                LOG.warning("Unable to close the browser cleanly.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")
    try:
        return run(args)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped by user.")
        return 130
