"""Interactive terminal reviewer for a captured issue-47 cohort judgment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from model import ReviewState, from_summary, reduce


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
CLEAR = "\x1b[2J\x1b[H"


def render(state: ReviewState) -> None:
    print(CLEAR, end="")
    print(f"{BOLD}Repaired factor requalification — live review{RESET}")
    print(f"{DIM}Throwaway prototype; review state is in memory only.{RESET}\n")
    print(f"{BOLD}official disposition:{RESET} {state.disposition}")
    print(f"{BOLD}human reaction:{RESET}       {state.human_reaction}")
    print(
        f"{BOLD}cohort key:{RESET}           "
        f"{json.dumps(state.cohort_key, separators=(',', ':'))}"
    )
    print(f"{BOLD}invalidity reasons:{RESET}   {len(state.invalidity_reasons)}")
    for reason in state.invalidity_reasons:
        print(f"  - {reason}")
    print(f"{BOLD}nonpassing coordinates:{RESET} {len(state.nonpassing_coordinates)}")
    if state.nonpassing_coordinates:
        current = state.nonpassing_coordinates[state.cursor]
        print(
            f"{BOLD}coordinate:{RESET} "
            f"{state.cursor + 1}/{len(state.nonpassing_coordinates)}"
        )
        if state.detail:
            print(json.dumps(current, indent=2, sort_keys=True))
        else:
            print(
                json.dumps(
                    {
                        key: current.get(key)
                        for key in (
                            "lane_id",
                            "target",
                            "workers",
                            "ordinal",
                            "rhs_family",
                            "stage",
                            "gate",
                            "status",
                        )
                        if key in current
                    },
                    sort_keys=True,
                )
            )
    print(f"\n{BOLD}targets{RESET}")
    for lane, disposition in state.target_dispositions:
        print(f"  {lane}: {disposition}")
    print(
        "\n"
        f"{BOLD}[n]{RESET} {DIM}next coordinate{RESET}  "
        f"{BOLD}[p]{RESET} {DIM}previous{RESET}  "
        f"{BOLD}[d]{RESET} {DIM}toggle detail{RESET}\n"
        f"{BOLD}[a]{RESET} {DIM}accept{RESET}  "
        f"{BOLD}[j]{RESET} {DIM}request adjustment{RESET}  "
        f"{BOLD}[r]{RESET} {DIM}reject{RESET}  "
        f"{BOLD}[u]{RESET} {DIM}clear reaction{RESET}  "
        f"{BOLD}[q]{RESET} {DIM}quit{RESET}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    state = from_summary(json.loads(args.summary.read_text(encoding="utf-8")))
    actions = {
        "n": "next",
        "p": "previous",
        "d": "toggle-detail",
        "a": "ACCEPT",
        "j": "ADJUST",
        "r": "REJECT",
        "u": "UNREVIEWED",
    }
    while True:
        render(state)
        key = input("> ").strip().lower()[:1]
        if key == "q":
            break
        state = reduce(state, actions.get(key, ""))
    print(CLEAR, end="")
    print(
        f"{BOLD}Final in-memory reaction:{RESET} {state.human_reaction}\n"
        f"{DIM}Post that reaction on the Wayfinder ticket; nothing was written."
        f"{RESET}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
