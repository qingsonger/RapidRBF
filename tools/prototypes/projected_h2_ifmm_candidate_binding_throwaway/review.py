"""Throwaway in-memory TUI for the Issue 66 source-closure review."""

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
    print(f"{BOLD}Issue 66 projected H2/IFMM source-closure review{RESET}")
    print(f"{DIM}{state['question']}{RESET}\n")
    print(f"{BOLD}review_status:{RESET} {state['review_status']}")
    print(
        f"{BOLD}recommended_disposition:{RESET} "
        f"{state['recommended_disposition']}"
    )
    print(f"{BOLD}authority_defect:{RESET} {state['authority_defect']}")
    print(
        f"{BOLD}candidate_entry_permitted:{RESET} "
        f"{str(state['candidate_entry_permitted']).lower()}"
    )
    observations = state["candidate_observations"]
    print(
        f"{BOLD}candidate_observations:{RESET} "
        f"setup={observations['factor_setup']} "
        f"apply={observations['factor_apply']} "
        f"solve={observations['solve']}"
    )
    print(
        f"{BOLD}closure:{RESET} {state['blocking_requirement_count']}/"
        f"{state['requirement_count']} requirements block source closure\n"
    )
    print(f"{BOLD}Requirement audit{RESET}")
    for requirement in state["requirements"]:
        print(
            f"- {requirement['id']} [{requirement['state']}]: "
            f"{requirement['finding']}"
        )
    print(f"\n{BOLD}Interpretation{RESET}")
    for item in state["interpretation"]:
        print(f"- {item}")
    print(f"\n{BOLD}Proposed next frontier{RESET}")
    for successor in state["proposed_frontier"]:
        print(f"{successor['order']}. {successor['title']} ({successor['type']})")
        print(f"   {successor['question']}")
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
