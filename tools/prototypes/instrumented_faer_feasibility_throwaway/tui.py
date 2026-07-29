"""Thin terminal shell for the instrumented-faer feasibility state model."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from textwrap import wrap

from model import (
    LabState,
    View,
    gate_matrix,
    new_state,
    reduce_state,
    selected_gate,
    target_matrix,
)


HERE = Path(__file__).resolve().parent
SUMMARY_PATH = HERE / "evidence" / "observed-summary.json"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
CLEAR = "\x1b[2J\x1b[H"


def load_summary() -> dict:
    value = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("observed summary root must be an object")
    return value


def compact(text: str, width: int = 96) -> list[str]:
    return wrap(text, width=width, replace_whitespace=False) or [""]


def summary_lines(state: LabState) -> list[str]:
    summary = state.summary
    gate = selected_gate(state)
    lines = [
        f"{BOLD}Disposition{RESET}: {summary['disposition']}",
        f"{BOLD}Candidate backend calls{RESET}: {summary['backend_calls']}",
        f"{BOLD}Published factors / corrections{RESET}: "
        f"{summary['published_validated_factors']} / "
        f"{summary['published_solved_corrections']}",
        f"{BOLD}Profile projection{RESET}: {summary['profile']['sha256']}",
        f"{BOLD}Stock source closure{RESET}: "
        f"{summary['source_audit']['source_closure_sha256']}",
        f"{BOLD}Candidate binding{RESET}: {summary['binding']['state']}",
        "",
        f"{BOLD}Selected gate [{state.gate_index + 1}/{len(summary['gates'])}]{RESET}",
        f"{gate['title']} - {gate['status']}",
    ]
    lines.extend(compact(gate["reason"]))
    lines.append("")
    lines.append(f"{DIM}Authority: {gate['authority']}{RESET}")
    if gate["evidence"]:
        lines.append(f"{DIM}Evidence: {', '.join(gate['evidence'])}{RESET}")
    return lines


def source_lines(state: LabState) -> list[str]:
    audit = state.summary["source_audit"]
    facts = audit["stock_facts"]
    lines = [
        f"{BOLD}Exact stock source{RESET}",
        f"closure: {audit['source_closure_sha256']}",
        f"audited source set: {audit['audited_source_set_sha256']}",
        "",
        f"{BOLD}Observed stock facts{RESET}",
    ]
    for name, value in facts.items():
        lines.append(f"{name}: {value}")
    lines.extend(["", f"{BOLD}Required fork surface{RESET}"])
    for item in state.summary["binding"]["required_source_changes"]:
        lines.append(f"- {item['path']}")
        for responsibility in item["responsibilities"]:
            lines.extend(f"    {line}" for line in compact(responsibility, 88))
    return lines


def evidence_lines(state: LabState) -> list[str]:
    lines = [
        f"{BOLD}Non-compensating target matrix{RESET}",
        "",
    ]
    for row in target_matrix(state):
        target, build, run, allocation, n_minus_one, cancel, latency = row
        lines.extend(
            [
                f"{BOLD}{target}{RESET}",
                f"  build={build}; factor={run}; allocation={allocation}",
                f"  N-1={n_minus_one}; cancel={cancel}; host-latency={latency}",
            ]
        )
    lines.extend(
        [
            "",
            f"{BOLD}Disposition precedence{RESET}",
            "FEASIBLE requires every gate and every target witness to PASS.",
            "REJECTED requires a reproducible observed failure of a frozen executable control.",
            "Anything missing or not reached is UNJUDGED; unknown is never rejection.",
        ]
    )
    return lines


def frame(state: LabState) -> str:
    if state.view is View.SUMMARY:
        body = summary_lines(state)
    elif state.view is View.SOURCE:
        body = source_lines(state)
    else:
        body = evidence_lines(state)
    header = [
        f"{BOLD}THROWAWAY - instrumented faer feasibility{RESET}",
        f"{DIM}view={state.view.value}; reloads={state.reload_count}{RESET}",
        "",
    ]
    footer = [
        "",
        f"{BOLD}[j]{RESET} next gate  {BOLD}[k]{RESET} previous gate  "
        f"{BOLD}[v]{RESET} view  {BOLD}[r]{RESET} reload  {BOLD}[q]{RESET} quit",
    ]
    return "\n".join(header + body + footer)


def read_key() -> str:
    if os.name == "nt":
        import msvcrt

        return msvcrt.getwch()

    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def print_matrix(state: LabState) -> None:
    print("GATES")
    for gate_id, status, reason in gate_matrix(state):
        print(f"{gate_id}\t{status}\t{reason}")
    print("\nTARGETS")
    for row in target_matrix(state):
        print("\t".join(row))
    print(f"\nDISPOSITION\t{state.summary['disposition']}")


def interactive(state: LabState) -> None:
    while True:
        print(CLEAR + frame(state), end="", flush=True)
        key = read_key().lower()
        if key == "q":
            print()
            return
        if key == "j":
            state = reduce_state(state, "next_gate")
        elif key == "k":
            state = reduce_state(state, "previous_gate")
        elif key == "v":
            state = reduce_state(state, "next_view")
        elif key == "r":
            state = reduce_state(
                state,
                "reload",
                reloaded_summary=load_summary(),
            )
        else:
            state = reduce_state(state, "noop")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()
    state = new_state(load_summary())
    if args.matrix:
        print_matrix(state)
    elif args.snapshot:
        print(frame(state))
    else:
        interactive(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
