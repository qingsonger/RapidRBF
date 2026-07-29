"""Thin terminal adapter for the throwaway factor-execution seam state model."""

from __future__ import annotations

import argparse
import os
import sys

from model import (
    CANDIDATES,
    SCENARIOS,
    Candidate,
    LabState,
    Scenario,
    View,
    current_contract,
    current_frame,
    frames_for,
    reduce_state,
    terminal_matrix,
)


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def style(value: str, code: str, color: bool) -> str:
    return f"{code}{value}{RESET}" if color else value


def clip(value: str, width: int = 88) -> str:
    return value if len(value) <= width else value[: width - 3] + "..."


def render(state: LabState, *, color: bool) -> str:
    contract = current_contract(state)
    frame = current_frame(state)
    frames = frames_for(state.candidate, state.scenario)
    header = [
        style("THROWAWAY - RapidRBF factor-execution seam lab", BOLD, color),
        style(
            "Question: which one v1 seam should advance to 216-factor qualification?",
            DIM,
            color,
        ),
        "",
        f"{style('route', BOLD, color):<25} {contract.title}",
        f"{style('scenario', BOLD, color):<25} {state.scenario.value}",
        f"{style('frame', BOLD, color):<25} {state.frame_index + 1}/{len(frames)}",
        f"{style('verdict', BOLD, color):<25} {contract.verdict}",
        "",
    ]

    if state.view is View.STATE:
        body = [
            style("Complete state", BOLD, color),
            f"phase:          {frame.phase.value}",
            f"permit lease:   {clip(frame.permit_lease)}",
            f"execution:      {clip(frame.execution)}",
            f"private draft:  {clip(frame.private_draft)}",
            f"factor:         {clip(frame.published_state)}",
            f"recipe:         {clip(frame.published_recipe)}",
            f"correction:     {clip(frame.published_correction)}",
            f"resources:      {clip(frame.resource_state)}",
            f"cancellation:   {clip(frame.cancellation_state)}",
            f"worker:         {clip(frame.worker_state)}",
            f"scratch:        {clip(frame.scratch_state)}",
            f"outcome:        {frame.outcome}",
            f"note:           {clip(frame.note)}",
        ]
    elif state.view is View.INTERFACE:
        body = [
            style("Interface and seam", BOLD, color),
            f"module: {contract.module}",
            *contract.interface,
            "",
            f"seam:         {clip(contract.seam)}",
            f"resources:    {clip(contract.resource_authority)}",
            f"cancellation: {clip(contract.cancellation_authority)}",
            f"distribution: {clip(contract.distribution)}",
            "",
            style("Implementation hides", BOLD, color),
            *(f"- {clip(item)}" for item in contract.implementation_hides),
        ]
    else:
        body = [
            style("Trade-offs", BOLD, color),
            style("Strengths", BOLD, color),
            *(f"+ {clip(item)}" for item in contract.strengths),
            style("Risks", BOLD, color),
            *(f"! {clip(item)}" for item in contract.risks),
            "",
            style("Smallest honest next probe", BOLD, color),
            clip(contract.next_probe),
        ]

    footer = [
        "",
        style(
            f"view={state.view.value} - changing route/scenario resets the state",
            DIM,
            color,
        ),
        (
            f"{style('[1/2/3]', BOLD, color)} route  "
            f"{style('[j/k]', BOLD, color)} scenario  "
            f"{style('[space]', BOLD, color)} step  "
            f"{style('[r]', BOLD, color)} reset  "
            f"{style('[v]', BOLD, color)} view  "
            f"{style('[q]', BOLD, color)} quit"
        ),
    ]
    return "\n".join(header + body + footer)


def render_matrix() -> str:
    lines = [
        "route                                   scenario                   last modeled outcome",
        (
            "--------------------------------------  -------------------------  "
            "-------------------------"
        ),
    ]
    for candidate, scenario, outcome in terminal_matrix():
        lines.append(f"{candidate:<38}  {scenario:<25}  {outcome}")
    return "\n".join(lines)


def read_key() -> str:
    if os.name == "nt":
        import msvcrt

        return msvcrt.getwch()

    import termios
    import tty

    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--route",
        choices=[candidate.value for candidate in CANDIDATES],
        default=Candidate.IN_PROCESS.value,
    )
    parser.add_argument(
        "--scenario",
        choices=[scenario.value for scenario in SCENARIOS],
        default=Scenario.NORMAL.value,
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=0,
        help="advance this many state transitions before rendering",
    )
    parser.add_argument(
        "--view",
        choices=[view.value for view in View],
        default=View.STATE.value,
    )
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.steps < 0:
        raise ValueError("--steps must be non-negative")
    if args.matrix:
        print(render_matrix())
        return 0

    state = LabState(
        candidate=Candidate(args.route),
        scenario=Scenario(args.scenario),
        view=View(args.view),
    )
    for _ in range(args.steps):
        state = reduce_state(state, "step")

    if args.snapshot:
        print(render(state, color=False))
        return 0

    while True:
        print("\x1b[2J\x1b[H", end="")
        print(render(state, color=True), flush=True)
        key = read_key().lower()
        if key == "q":
            return 0
        if key == "1":
            state = reduce_state(state, f"candidate:{CANDIDATES[0].value}")
        elif key == "2":
            state = reduce_state(state, f"candidate:{CANDIDATES[1].value}")
        elif key == "3":
            state = reduce_state(state, f"candidate:{CANDIDATES[2].value}")
        elif key == "j":
            state = reduce_state(state, "next_scenario")
        elif key == "k":
            state = reduce_state(state, "previous_scenario")
        elif key in {" ", "\r", "\n"}:
            state = reduce_state(state, "step")
        elif key == "r":
            state = reduce_state(state, "reset")
        elif key == "v":
            state = reduce_state(state, "next_view")
        else:
            state = reduce_state(state, "noop")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"factor-execution seam TUI failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
