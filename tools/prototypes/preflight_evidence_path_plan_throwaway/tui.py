"""Tiny in-memory TUI for reviewing the Issue 57 diagnosis and plan."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from model import (
    VIEWS,
    initial_state,
    load_fixed_evidence,
    load_plan,
    reduce,
    view_data,
)


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def render(
    state: dict[str, Any],
    fixed: dict[str, Any],
    plan: dict[str, Any],
    *,
    ansi: bool,
) -> str:
    bold = BOLD if ansi else ""
    dim = DIM if ansi else ""
    reset = RESET if ansi else ""
    data = json.dumps(
        view_data(state, fixed, plan),
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    )
    return "\n".join(
        (
            f"{bold}Issue 57 preflight evidence-path plan{reset}",
            f"{dim}view {state['index'] + 1}/{len(VIEWS)}: {state['view']}{reset}",
            "",
            data,
            "",
            f"{bold}[n]{reset} next  {bold}[p]{reset} previous  "
            f"{bold}[q]{reset} quit",
        )
    )


def snapshot(selection: str) -> None:
    fixed = load_fixed_evidence()
    plan = load_plan()
    views = VIEWS if selection == "all" else (selection,)
    for index, view in enumerate(views):
        if index:
            print("\n" + "=" * 78 + "\n")
        print(render(initial_state(view), fixed, plan, ansi=False))


def interactive() -> None:
    fixed = load_fixed_evidence()
    plan = load_plan()
    state = initial_state()
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(render(state, fixed, plan, ansi=True))
        command = input("> ").strip().lower()
        if command == "q":
            return
        if command == "n":
            state = reduce(state, "next")
        elif command == "p":
            state = reduce(state, "previous")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", choices=("all", *VIEWS))
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.snapshot:
        snapshot(arguments.snapshot)
    else:
        interactive()
