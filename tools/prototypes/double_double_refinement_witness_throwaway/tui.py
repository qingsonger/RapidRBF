"""Tiny terminal reviewer for the immutable Issue 58 cohort summary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from model import ReviewState, from_summary, reduce


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def render(state: ReviewState) -> str:
    lines = [
        f"{BOLD}Root-bound refinement witness cohort review{RESET}",
        "",
        f"{BOLD}Disposition:{RESET} {state.disposition}",
        f"{BOLD}Source binding:{RESET} {state.source_binding_sha256}",
        f"{BOLD}Controller binding:{RESET} {state.controller_binding_sha256}",
        f"{BOLD}Zero-entry preflights:{RESET} {state.preflight_count}/4",
        f"{BOLD}Target/profile observations:{RESET} {state.target_profile_count}/12",
        f"{BOLD}Witness source observations:{RESET} {state.witness_source_observations}/72",
        f"{BOLD}Invalidity reasons:{RESET} {len(state.invalidity_reasons)}",
        f"{BOLD}Nonpassing coordinates:{RESET} {len(state.nonpassing_coordinates)}",
        f"{BOLD}Human reaction:{RESET} {state.human_reaction}",
        "",
        f"{BOLD}Scope{RESET}",
    ]
    lines.extend(f"  {name}: {value}" for name, value in state.scope)
    if state.invalidity_reasons:
        lines.extend(["", f"{BOLD}Invalidity{RESET}"])
        lines.extend(f"  - {reason}" for reason in state.invalidity_reasons)
    if state.nonpassing_coordinates:
        item = state.nonpassing_coordinates[state.cursor]
        lines.extend(
            [
                "",
                f"{BOLD}Coordinate {state.cursor + 1}/{len(state.nonpassing_coordinates)}{RESET}",
                json.dumps(item, indent=2, sort_keys=True)
                if state.detail
                else str(item.get("gate", item)),
            ]
        )
    lines.extend(
        [
            "",
            f"{DIM}[n] next  [p] previous  [d] detail  [a] accept  "
            f"[j] adjust  [r] reject  [q] quit{RESET}",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    state = from_summary(json.loads(args.summary.read_text(encoding="utf-8")))
    if args.snapshot:
        print(render(state))
        return 0
    actions = {
        "n": "next",
        "p": "previous",
        "d": "toggle-detail",
        "a": "ACCEPT",
        "j": "ADJUST",
        "r": "REJECT",
    }
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(render(state))
        key = input("> ").strip().lower()
        if key == "q":
            return 0
        state = reduce(state, actions.get(key, key))


if __name__ == "__main__":
    raise SystemExit(main())
