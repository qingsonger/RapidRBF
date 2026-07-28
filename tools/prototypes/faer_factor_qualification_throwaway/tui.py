"""Thin terminal adapter for the throwaway faer qualification state model."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from model import LabState, decide, initial_state, reduce_state


BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def load_summary(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "rapidrbf-faer-factor-qualification-lab-v1":
        raise ValueError(f"unsupported summary schema in {path}")
    return value


def style(value: str, code: str, color: bool) -> str:
    return f"{code}{value}{RESET}" if color else value


def clipped(value: str, width: int) -> str:
    return value if len(value) <= width else value[: width - 3] + "..."


def render(
    summary: dict[str, Any],
    state: LabState,
    *,
    color: bool,
) -> str:
    selected = state.gates[state.selected_gate]
    disposition = decide(state.gates).value
    lines = [
        style(
            "THROWAWAY - direct in-process faer 0.24.4 qualification",
            BOLD,
            color,
        ),
        style(
            "Question: can the complete run-scoped path publish authority?",
            DIM,
            color,
        ),
        "",
        f"{style('disposition', BOLD, color):<28} {disposition}",
        f"{style('backend calls', BOLD, color):<28} {summary['backend_calls']}",
        f"{style('validated factors', BOLD, color):<28} "
        f"{summary['published_validated_factors']}",
        f"{style('solved corrections', BOLD, color):<28} "
        f"{summary['published_solved_corrections']}",
        f"{style('recompute eligible', BOLD, color):<28} "
        f"{str(summary['recompute_exception']['eligible']).lower()}",
        "",
        style("Gate state", BOLD, color),
    ]
    for index, gate in enumerate(state.gates):
        marker = ">" if index == state.selected_gate else " "
        lines.append(
            f"{marker} {index + 1:>2}/{len(state.gates)} "
            f"{gate.status.value:<12} {clipped(gate.title, 55)}"
        )

    lines.extend(
        [
            "",
            style(
                f"Selected - {selected.title} [{selected.status.value}]",
                BOLD,
                color,
            ),
        ]
    )
    if state.view == "decision":
        lines.extend(
            [
                f"authority: {selected.authority}",
                f"reason:    {selected.reason}",
                f"preflight: {summary['preflight']['state']} "
                "-> candidate factorization intentionally not entered",
            ]
        )
    elif state.view == "evidence":
        lines.append("evidence:")
        lines.extend(f"  - {item}" for item in selected.evidence)
        lines.append(
            "source closure: "
            + summary["source_audit"]["source_closure_sha256"]
        )
    else:
        profile = summary["profile"]
        candidate = profile["candidate"]
        factor_health = profile["factor_health"]
        recompute = profile["recompute_exception"]
        lanes = ", ".join(
            f"{lane['workers']}/{lane['maximum_live_threads']}"
            for lane in profile["thread_contract"]["lanes"]
        )
        lines.extend(
            [
                f"profile: {profile['profile_id']}",
                f"candidate: {candidate['target']} "
                f"{'+'.join(candidate['features'])} "
                f"{candidate['execution_boundary']}",
                "health:  reconstruction≤"
                f"{factor_health['reconstruction_relative_inf_max']}; "
                f"solve≤{factor_health['reduced_backward_error_max']}",
                "rule:    recompute only when "
                f"{recompute['only_permitted_when_the_sole_nonpassing_gate_is']} "
                "is the sole nonpassing gate",
                f"lanes:   {lanes}; each independently authoritative",
            ]
        )

    lines.extend(
        [
            "",
            style(
                f"view={state.view}  reloads={state.reload_count}",
                DIM,
                color,
            ),
            (
                f"{style('[j/k]', BOLD, color)} gate  "
                f"{style('[v]', BOLD, color)} view  "
                f"{style('[r]', BOLD, color)} reload  "
                f"{style('[q]', BOLD, color)} quit"
            ),
        ]
    )
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
        "--summary",
        type=Path,
        default=Path(__file__).with_name("evidence")
        / "qualification-summary.json",
    )
    parser.add_argument("--snapshot", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary_path = args.summary.resolve()
    summary = load_summary(summary_path)
    state = initial_state(summary)
    if args.snapshot:
        print(render(summary, state, color=False))
        return 0

    while True:
        print("\x1b[2J\x1b[H", end="")
        print(render(summary, state, color=True), flush=True)
        key = read_key().lower()
        if key == "q":
            return 0
        if key == "j":
            state = reduce_state(state, "next_gate")
        elif key == "k":
            state = reduce_state(state, "previous_gate")
        elif key == "v":
            state = reduce_state(state, "next_view")
        elif key == "r":
            selected = state.selected_gate
            view = state.view
            reloads = state.reload_count
            summary = load_summary(summary_path)
            state = initial_state(summary)
            state = replace(
                state,
                selected_gate=selected % len(state.gates),
                view=view,
                reload_count=reloads,
            )
            state = reduce_state(state, "reloaded")
        else:
            state = reduce_state(state, "noop")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"qualification TUI failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
