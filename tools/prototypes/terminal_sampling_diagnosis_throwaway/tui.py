"""THROWAWAY interactive state viewer for the Issue 54 decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIAGNOSIS = json.loads((ROOT / "diagnosis.v1.json").read_text(encoding="utf-8"))
TRACES = json.loads(
    (ROOT / "captured-terminal-traces.v1.json").read_text(encoding="utf-8")
)


def show_summary() -> None:
    print(json.dumps({
        "disposition": DIAGNOSIS["disposition"],
        "cause": DIAGNOSIS["cause"],
        "captured_evidence": DIAGNOSIS["captured_evidence"],
        "native_probe": DIAGNOSIS["native_probe"],
    }, indent=2))


def show_traces() -> None:
    print(json.dumps(TRACES["traces"], indent=2))


def show_boundary() -> None:
    print(json.dumps(DIAGNOSIS["diagnostic_boundary"], indent=2))


def show_wayfinder() -> None:
    print(json.dumps(DIAGNOSIS["wayfinder"], indent=2))


ACTIONS = {
    "summary": show_summary,
    "traces": show_traces,
    "boundary": show_boundary,
    "wayfinder": show_wayfinder,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--script",
        help="comma-separated actions for unattended review",
    )
    args = parser.parse_args()
    if args.script:
        for action in args.script.split(","):
            print(f"\n=== action: {action} ===")
            ACTIONS[action]()
        return 0

    print("Issue 54 terminal-sampling diagnosis (THROWAWAY)")
    print("Actions: summary, traces, boundary, wayfinder, quit")
    show_summary()
    while True:
        action = input("> ").strip().lower()
        if action in {"quit", "q", "exit"}:
            return 0
        if action not in ACTIONS:
            print("unknown action")
            continue
        ACTIONS[action]()


if __name__ == "__main__":
    raise SystemExit(main())
