"""Thin interactive shell for the throwaway kifmm adaptation decision lab."""

from __future__ import annotations

import argparse
import os
import textwrap

from model import (
    KIFMM_REVISION,
    LabState,
    anisotropy_label,
    assess,
    transform_detail,
    transition,
)


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
WIDTH = 116


def styled(text: str, style: str, color: bool) -> str:
    if not color:
        return text
    return f"{style}{text}{RESET}"


def clipped(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: width - 3] + "..."


def wrapped(label: str, value: str, width: int = WIDTH) -> list[str]:
    prefix = f"{label}: "
    return textwrap.wrap(
        value,
        width=width,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix),
        break_long_words=False,
        break_on_hyphens=False,
    )


def render(state: LabState, color: bool) -> str:
    result = assess(state)
    lines: list[str] = []

    lines.append(
        styled("RAPIDRBF KIFMM COMPONENT/PORTABILITY LAB -- THROWAWAY", BOLD, color)
    )
    lines.append(
        styled(
            "SOURCE STRUCTURE + MAPPING IDENTITY ARE NOT KIFMM EXECUTION, A "
            "SOUND CERTIFICATE, OR AUTO PROMOTION.",
            DIM,
            color,
        )
    )
    if result.hypothetical:
        lines.append(
            styled(
                "***** COUNTERFACTUAL ONLY -- NO OBSERVED PROMOTION CLAIM *****",
                BOLD,
                color,
            )
        )
    lines.append("")

    lines.append(styled("FROZEN INPUT / SELECTED CASE", BOLD, color))
    lines.append(
        f"kifmm: {KIFMM_REVISION[:7]}  |  Route: {state.evidence.label}"
    )
    lines.append(
        f"Action: {state.action.label} ({state.action.channels})  |  "
        f"Dimension: {state.dimension}D"
    )
    lines.append(
        f"Form: {state.kernel_form.label}  |  "
        f"Anisotropy: {anisotropy_label(state)}"
    )
    lines.append(
        f"Prepared shape: {state.lifetime.label} -- {state.lifetime.contract}"
    )
    lines.extend(wrapped("Canonical", state.action.canonical))
    lines.extend(wrapped("Transform", transform_detail(state)))
    lines.extend(wrapped("Profile", state.evidence.description))
    lines.append("")

    lines.append(styled("ADAPTATION ROUTE", BOLD, color))
    lines.extend(wrapped("Route", result.route))
    lines.append("")

    lines.append(styled("FROZEN SOURCE / PROBE LEDGER", BOLD, color))
    for item in result.ledger:
        detail_width = WIDTH - 39
        lines.append(
            f"{item.status:17} {item.label:20} "
            f"{clipped(item.detail, detail_width)}"
        )
    lines.append("")

    lines.append(styled("AUTO PROMOTION GATES", BOLD, color))
    for gate in result.gates:
        detail_width = WIDTH - 43
        lines.append(
            f"{gate.status:17} {gate.label:22} "
            f"{clipped(gate.detail, detail_width)}"
        )
    lines.append("")

    lines.append(styled(f"VERDICT -- {result.verdict}", BOLD, color))
    lines.extend(wrapped("First disqualifier", result.first_disqualifier))
    lines.extend(wrapped("Conclusion", result.conclusion))
    lines.extend(wrapped("Notice", state.notice))
    lines.append("")
    lines.append(
        styled(
            "[a] action  [d] dimension  [f] family/form  [x] anisotropy",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[u] prepared shape  [e] decision route  [r] reset  [q] quit",
            DIM,
            color,
        )
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the throwaway RapidRBF kifmm adaptation lab."
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
