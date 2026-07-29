"""Throwaway terminal shell for the Issue 50 controller state machine."""

from __future__ import annotations

import argparse
import json
import os

from model import initial_state, reduce, scenario_catalog


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def run_scenario(name: str) -> dict:
    scenario = scenario_catalog()[name]
    state = initial_state(scenario["grant"])
    for action in scenario["actions"]:
        state = reduce(state, action)
    return {
        "scenario": name,
        "description": scenario["description"],
        "expected": scenario["expected"],
        "observed": state["verdict"],
        "matches": state["verdict"] == scenario["expected"],
        "state": state,
    }


def snapshot(selection: str) -> None:
    names = list(scenario_catalog())
    if selection != "all":
        names = [selection]
    print(json.dumps([run_scenario(name) for name in names], indent=2))


def render(name: str, index: int, state: dict) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    scenario = scenario_catalog()[name]
    print(f"{BOLD}Issue 50 controller-evidence prototype{RESET}")
    print(f"{DIM}{scenario['description']}{RESET}\n")
    print(f"{BOLD}scenario{RESET}: {name}")
    print(f"{BOLD}step{RESET}: {index}/{len(scenario['actions'])}")
    print(json.dumps(state, indent=2))
    print(
        f"\n{BOLD}[n]{RESET} next event  "
        f"{BOLD}[r]{RESET} reset  "
        f"{BOLD}[s]{RESET} next scenario  "
        f"{BOLD}[q]{RESET} quit"
    )


def interactive() -> None:
    names = list(scenario_catalog())
    scenario_index = 0
    action_index = 0
    state = initial_state(scenario_catalog()[names[scenario_index]]["grant"])
    while True:
        name = names[scenario_index]
        render(name, action_index, state)
        command = input("> ").strip().lower()
        if command == "q":
            return
        if command == "r":
            action_index = 0
            state = initial_state(scenario_catalog()[name]["grant"])
        elif command == "s":
            scenario_index = (scenario_index + 1) % len(names)
            action_index = 0
            name = names[scenario_index]
            state = initial_state(scenario_catalog()[name]["grant"])
        elif command in {"", "n"}:
            actions = scenario_catalog()[name]["actions"]
            if action_index < len(actions):
                state = reduce(state, actions[action_index])
                action_index += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot",
        choices=["all", *scenario_catalog().keys()],
        help="render one or all complete scenarios and exit",
    )
    args = parser.parse_args()
    if args.snapshot:
        snapshot(args.snapshot)
    else:
        interactive()


if __name__ == "__main__":
    main()
