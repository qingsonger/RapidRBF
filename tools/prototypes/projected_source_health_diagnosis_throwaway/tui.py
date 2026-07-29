"""Tiny terminal reviewer for the issue-45 throwaway prototype."""

from __future__ import annotations

import argparse
from pathlib import Path

from model import load_dashboard, render_dashboard


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" / "diagnosis-evidence.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--ordinal", type=int)
    args = parser.parse_args()
    dashboard = load_dashboard(EVIDENCE)
    if args.snapshot or args.ordinal is not None:
        print(render_dashboard(dashboard, args.ordinal))
        return 0

    ordinals = [card.ordinal for card in dashboard.cards]
    selected: int | None = None
    while True:
        print("\x1b[2J\x1b[H", end="")
        print(render_dashboard(dashboard, selected))
        print("Commands: [a]ll  [n]ext  [p]revious  [q]uit")
        command = input("> ").strip().lower()
        if command == "q":
            return 0
        if command == "a":
            selected = None
            continue
        if command in {"n", "p"}:
            if selected is None:
                selected = ordinals[0 if command == "n" else -1]
            else:
                index = ordinals.index(selected)
                delta = 1 if command == "n" else -1
                selected = ordinals[(index + delta) % len(ordinals)]


if __name__ == "__main__":
    raise SystemExit(main())
