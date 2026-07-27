"""Thin interactive shell for the throwaway backend candidate evidence lab."""

from __future__ import annotations

import argparse
import os
import textwrap

from model import (
    CANDIDATES,
    LabState,
    assess,
    assessments,
    recommendation,
    required_probe_groups,
    transition,
)


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"


def styled(text: str, style: str, color: bool) -> str:
    if not color:
        return text
    return f"{style}{text}{RESET}"


def wrapped(label: str, value: str, width: int = 96) -> list[str]:
    prefix = f"{label}: "
    subsequent = " " * len(prefix)
    return textwrap.wrap(
        value,
        width=width,
        initial_indent=prefix,
        subsequent_indent=subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def render(state: LabState, color: bool) -> str:
    scenario = state.scenario
    focus = assess(state.candidate, state)
    rows = assessments(state)
    lines: list[str] = []

    lines.append(styled("RAPIDRBF BACKEND EVIDENCE LAB -- THROWAWAY", BOLD, color))
    lines.append(
        styled(
            "Contract fit is not promotion evidence. WHAT-IF views are counterfactual.",
            DIM,
            color,
        )
    )
    lines.append("")
    lines.append(styled("CURRENT STATE", BOLD, color))
    lines.extend(wrapped("Scenario", scenario.label))
    lines.extend(wrapped("Purpose", scenario.description))
    lines.append(f"Kernel family / form: {state.kernel.label} / {state.kernel.form}")
    lines.append(f"Action / dimension: {state.action} / {state.dimension}D")
    lines.append(f"Anisotropy: {state.anisotropy.label}")
    lines.append(f"Geometry / reuse: {scenario.geometry} / {scenario.reuse}")
    lines.append(f"Scale / platform: {scenario.scale} / {state.platform}")
    lines.extend(wrapped("Evidence view", state.evidence.label))
    lines.extend(wrapped("Evidence rule", state.evidence.description))
    lines.append(styled("EVIDENCE LEDGER", BOLD, color))
    lines.extend(
        wrapped(
            "M",
            "Frozen Polatory 1k x 1k lower-rung direct anchor only: "
            "0.268579 s, 19,058,688 peak private bytes, 25,174,016 peak "
            "working-set bytes. Diagnostic, not a candidate FMM comparison.",
        )
    )
    lines.extend(
        wrapped(
            "I",
            "Accepted contracts plus frozen Polatory/ScalFMM source and Windows "
            "oracle lineage.",
        )
    )
    lines.extend(
        wrapped(
            "?",
            "No RapidRBF direct, neighbor, Ferreus, kifmm, C-ABI, or composed "
            "candidate execution has been measured.",
        )
    )
    lines.append("")
    lines.append(styled("ROUTE CONCLUSION", BOLD, color))
    lines.extend(wrapped("Decision", recommendation(state)))
    lines.append("")
    lines.append(styled("CANDIDATE STATUS", BOLD, color))
    lines.append(f"{'candidate':24} {'route fit':34} use")
    lines.append("-" * 96)
    for row in rows:
        marker = ">" if row.candidate.key == state.candidate.key else " "
        lines.append(
            f"{marker} {row.candidate.label[:22]:22} "
            f"{row.route_fit[:32]:32} {row.use}"
        )
    lines.append("")
    lines.append(styled(f"FOCUS -- {focus.candidate.label}", BOLD, color))
    lines.extend(wrapped("Role", focus.candidate.role))
    lines.extend(wrapped("Evidence", focus.evidence))
    for label, value in focus.candidate.comparison:
        lines.extend(wrapped(label, value))
    lines.append(styled("Blockers", BOLD, color))
    if focus.blockers:
        lines.extend(f"- {item}" for item in focus.blockers)
    else:
        lines.append("- none in this evidence view")
    lines.append("")
    lines.append(styled("REQUIRED PROBE GROUPS", BOLD, color))
    lines.extend(f"- {item}" for item in required_probe_groups(state))
    lines.append("")
    lines.append(
        styled(
            "[n] scenario  [f] family  [a] action  [x] anisotropy  [d] dimension",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[p] platform  [e] evidence view  [c] candidate  [r] reset  [q] quit",
            DIM,
            color,
        )
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the throwaway RapidRBF backend evidence lab."
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="print the initial frame once instead of starting the interaction loop",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    color = not args.snapshot and "NO_COLOR" not in os.environ
    state = LabState()

    if args.snapshot:
        print(render(state, color=False))
        return 0

    while True:
        print("\x1b[2J\x1b[H", end="")
        print(render(state, color=color))
        try:
            command = input("\ncommand> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if command == "q":
            return 0
        state = transition(state, command)


if __name__ == "__main__":
    raise SystemExit(main())
