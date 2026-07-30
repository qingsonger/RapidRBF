"""Interactive shell for the Issue 59 throwaway dispatch state model."""

from __future__ import annotations

import json
import os

from model import State, reduce, render_state


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def render(state: State) -> None:
    clear()
    print(f"{BOLD}Issue 59 zero-run dispatch prototype{RESET}")
    print(
        f"{DIM}Question: which trigger gate suppressed Issue 58, and does the "
        f"replacement stay locked on zero, duplicate, or rerun identity?{RESET}\n"
    )
    print(json.dumps(render_state(state), indent=2, sort_keys=True))
    print(
        "\n"
        f"{BOLD}[u]{RESET} {DIM}observe unique new-object push{RESET}  "
        f"{BOLD}[p]{RESET} {DIM}observe ref-only path suppression{RESET}  "
        f"{BOLD}[n]{RESET} {DIM}observe no ref-only push event{RESET}\n"
        f"{BOLD}[i]{RESET} {DIM}inject invalid probe matrix{RESET}  "
        f"{BOLD}[o]{RESET} {DIM}observe one valid replacement run{RESET}  "
        f"{BOLD}[d]{RESET} {DIM}observe duplicate replacement runs{RESET}\n"
        f"{BOLD}[r]{RESET} {DIM}observe rerun attempt{RESET}  "
        f"{BOLD}[x]{RESET} {DIM}reset{RESET}  "
        f"{BOLD}[q]{RESET} {DIM}quit{RESET}"
    )


def main() -> None:
    state = State()
    actions = {
        "u": "unique",
        "p": "ref-path",
        "n": "ref-none",
        "i": "ref-invalid",
        "o": "replacement-valid",
        "d": "replacement-duplicate",
        "r": "replacement-rerun",
        "x": "reset",
    }
    while True:
        render(state)
        key = input("\n> ").strip().lower()
        if key == "q":
            return
        if key in actions:
            state = reduce(state, actions[key])


if __name__ == "__main__":
    main()
