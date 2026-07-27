"""One-screen terminal shell for the throwaway ScalFMM3 C-ABI decision lab."""

from __future__ import annotations

import argparse
import os
import textwrap

from model import LabState, assess, selection_summary, transition


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
WIDTH = 112


def styled(text: str, style: str, color: bool) -> str:
    if not color:
        return text
    return f"{style}{text}{RESET}"


def wrapped(label: str, value: str) -> list[str]:
    prefix = f"{label}: "
    return textwrap.wrap(
        value,
        width=WIDTH,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix),
        break_long_words=False,
        break_on_hyphens=False,
    )


def render(state: LabState, color: bool = False) -> str:
    assessment = assess(state)
    lines: list[str] = []

    lines.append(styled("SCALFMM3 NARROW C-ABI DECISION LAB -- THROWAWAY", BOLD, color))
    lines.extend(
        wrapped(
            "QUESTION",
            "Can the pinned engine be contained behind a caller-first narrow C ABI, "
            "and what observed failure bars large-workload Auto?",
        )
    )
    lines.append(
        styled(
            "Rule: source lineage, observed probe evidence, missing evidence, and counterfactuals stay distinct.",
            DIM,
            color,
        )
    )
    lines.append("")
    lines.append(styled("SELECTION", BOLD, color))
    lines.extend(wrapped("Case", selection_summary(state)))
    lines.extend(wrapped("Workflow", state.workflow.detail))
    lines.extend(wrapped("Term", state.term.detail))
    lines.extend(wrapped("Anisotropy", f"{state.anisotropy.detail}; the C ABI sees metric coordinates only"))
    lines.extend(wrapped("Run focus", state.run_case.detail))
    lines.append("")
    lines.append(styled("CALLER-FIRST SEAM", BOLD, color))
    lines.extend(
        wrapped(
            "Rust owns",
            "anisotropy transforms, multi-term/split composition, certification, direct fallback, and public errors",
        )
    )
    lines.extend(wrapped("C plan", assessment.c_plan))
    lines.extend(wrapped("C lane", assessment.c_lane))
    lines.append(
        "C run: checked layouts + stable status + staged values; boundary throw contained, worker throw unexercised"
    )
    lines.append("")
    lines.append(styled("EVIDENCE LEDGER", BOLD, color))
    for label, finding in assessment.evidence_ledger:
        lines.extend(wrapped(label, finding))
    lines.append("")
    lines.append(styled("SIX AUTO PROMOTION GATES", BOLD, color))
    lines.append(f"{'#':<2} {'gate':<25} {'status':<8} finding")
    for index, gate in enumerate(assessment.gates, start=1):
        lines.append(
            f"{index:<2} {gate.name[:25]:<25} {gate.status:<8} {gate.finding}"
        )
    lines.extend(wrapped("FIRST DISQUALIFIER", assessment.first_disqualifier))
    lines.append("")
    lines.append(styled("VERDICT", BOLD, color))
    lines.extend(
        wrapped(
            "Scenario profile",
            f"{state.evidence.label} -- {state.evidence.detail}",
        )
    )
    lines.extend(wrapped("Prototype recommendation", assessment.verdict))
    lines.extend(wrapped("Why", assessment.reason))
    lines.append("")
    lines.append(
        styled(
            "[w] workflow  [a] action  [d] dimension  [g] geometry  [k] term  [x] anisotropy",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[r] run case  [e] scenario profile  [0] reset  [q] quit",
            DIM,
            color,
        )
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the throwaway ScalFMM3 narrow C-ABI decision lab."
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="print the initial frame once instead of entering the interaction loop",
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
