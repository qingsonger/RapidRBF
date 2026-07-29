"""Tiny interactive reviewer for the repaired solution-health authority."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from model import load_dashboard, render_dashboard


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" / "authority-evidence.json"


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def interactive() -> int:
    dashboard = load_dashboard(EVIDENCE)
    ordinals = [card.ordinal for card in dashboard.boundaries]
    selected = 0
    view = "boundary"
    while True:
        clear()
        ordinal = ordinals[selected] if view == "boundary" else None
        print(render_dashboard(dashboard, view=view, selected=ordinal))
        print()
        print(
            "[n] next boundary  [p] previous boundary  "
            "[v] toggle boundary/adversarial  [a] all  [q] quit"
        )
        command = input("> ").strip().lower()
        if command == "q":
            return 0
        if command == "n":
            selected = (selected + 1) % len(ordinals)
            view = "boundary"
        elif command == "p":
            selected = (selected - 1) % len(ordinals)
            view = "boundary"
        elif command == "v":
            view = "adversarial" if view == "boundary" else "boundary"
        elif command == "a":
            view = "all"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    dashboard = load_dashboard(EVIDENCE)
    if args.snapshot:
        print(render_dashboard(dashboard))
        return 0
    return interactive()


if __name__ == "__main__":
    raise SystemExit(main())
