"""Throwaway in-memory TUI for the Issue 65 candidate-closure audit."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from model import build_review, transition


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def render(state: dict[str, Any], *, clear: bool = True) -> None:
    if clear:
        os.system("cls" if os.name == "nt" else "clear")
    print(f"{BOLD}Issue 65 projected H2/IFMM candidate-closure audit{RESET}")
    print(f"{DIM}{state['question']}{RESET}\n")
    print(f"{BOLD}review_status:{RESET} {state['review_status']}")
    print(
        f"{BOLD}recommended_disposition:{RESET} "
        f"{state['recommended_disposition']}"
    )
    print(
        f"{BOLD}candidate_entry_permitted:{RESET} "
        f"{str(state['candidate_entry_permitted']).lower()}"
    )
    print(
        f"{BOLD}closure:{RESET} {state['frozen_control_count']} frozen controls; "
        f"{state['identity_gap_count']} result-affecting gaps\n"
    )
    print(f"{BOLD}Missing executable identity / authority{RESET}")
    for gap in state["identity_gaps"]:
        print(f"- {gap['id']}: {gap['impact']}")
    print(f"\n{BOLD}Proposed successor slice{RESET}")
    for successor in state["successor_slice"]:
        print(f"{successor['order']}. {successor['title']}")
    if state["review_note"]:
        print(f"\n{BOLD}review_note:{RESET} {state['review_note']}")
    print(
        f"\n{BOLD}[a]{RESET} accept  "
        f"{BOLD}[d]{RESET} adjust  "
        f"{BOLD}[r]{RESET} reject  "
        f"{BOLD}[q]{RESET} quit"
    )


def snapshot(state: dict[str, Any]) -> None:
    print(json.dumps(state, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="print the initial review state as JSON and exit",
    )
    args = parser.parse_args()
    state = build_review()
    if args.snapshot:
        snapshot(state)
        return 0

    while True:
        render(state)
        choice = input("> ").strip().lower()
        if choice == "q":
            return 0
        if choice in {"a", "d", "r"}:
            note = input("review note (optional): ").strip()
            action = {"a": "accept", "d": "adjust", "r": "reject"}[choice]
            state = transition(state, action, note)


if __name__ == "__main__":
    raise SystemExit(main())
