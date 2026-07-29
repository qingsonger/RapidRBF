"""Tiny dependency-free terminal browser for the archived qualification cohort."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from model import load_dashboard, render_dashboard


ROOT = Path(__file__).resolve().parent


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT / "evidence",
        help="directory containing the unpacked target and cohort artifacts",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="print one complete frame and exit",
    )
    args = parser.parse_args()
    dashboard = load_dashboard(args.evidence)
    if args.snapshot:
        print(render_dashboard(dashboard))
        return 0

    selected: str | None = None
    while True:
        clear_screen()
        print(render_dashboard(dashboard, selected))
        print()
        print("[a] all targets  [1-4] target detail  [q] quit")
        command = input("> ").strip().lower()
        if command == "q":
            return 0
        if command == "a":
            selected = None
            continue
        if command in {"1", "2", "3", "4"}:
            selected = dashboard.targets[int(command) - 1].lane_id


if __name__ == "__main__":
    raise SystemExit(main())
