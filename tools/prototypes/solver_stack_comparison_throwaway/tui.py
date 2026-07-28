"""Thin interactive shell for the throwaway solver-stack decision lab."""

from __future__ import annotations

import argparse
import os
import textwrap

from model import GIB, MIB, LabState, assess, compare_axis, transition


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
WIDTH = 132


def styled(text: str, style: str, color: bool) -> str:
    if not color:
        return text
    return f"{style}{text}{RESET}"


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


def bytes_text(value: int | None) -> str:
    if value is None:
        return "UNMATERIALIZED"
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= GIB:
        return f"{sign}{absolute / GIB:.2f} GiB"
    return f"{sign}{absolute / MIB:.1f} MiB"


def clipped(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[: max(0, length - 3)] + "..."


def render_axis(state: LabState) -> list[str]:
    lines = [f"  {'choice':38} {'derived state':27} axis-specific evidence/risk"]
    for row in compare_axis(state):
        marker = ">" if row.selected else " "
        lines.append(
            f"{marker} {clipped(row.label, 38):38} "
            f"{clipped(row.status, 27):27} {clipped(row.reason, 49)}"
        )
    return lines


def selected_axis_detail(state: LabState) -> str:
    if state.axis == "dense":
        if not state.preconditioner.factor_store_required:
            return f"N/A for {state.preconditioner.label}."
        return (
            f"audited coordinate={state.dense.audited_coordinate}; {state.dense.v1_scope}; "
            f"{state.dense.evidence}"
        )
    if state.axis == "krylov":
        return (
            f"audited coordinate={state.krylov.audited_coordinate}; {state.krylov.v1_scope}; "
            f"{state.krylov.evidence}"
        )
    if state.axis == "restart window":
        if state.krylov.fixed_window is not None:
            return (
                f"{state.krylov.label} fixes its comparison window/cap at "
                f"{state.effective_window}."
            )
        return (
            f"Selected restart m={state.effective_window}; only V/Z bytes are "
            "arithmetically known until the complete solver workspace is materialized."
        )
    if state.axis == "memory grant":
        ledger = assess(state).plan.resource
        return (
            f"Selected total grant={state.grant_gib} GiB; known subtotal="
            f"{bytes_text(ledger.known_subtotal_bytes)}; headroom after known="
            f"{bytes_text(ledger.headroom_after_known_bytes)}; "
            f"{len(ledger.unknown_reservations)} byte categories remain unmaterialized."
        )
    if state.axis == "factor cap":
        if not state.preconditioner.factor_store_required:
            return (
                f"N/A: {state.preconditioner.label} owns no RapidRBF factor store or cap."
            )
        if state.factor_store.reservation_mode != "selected-cap":
            return f"N/A: {state.factor_store.label} does not consume the cap."
        return (
            f"Selected cap={state.factor_cap_gib:g} GiB; it reserves resident factors "
            "or the recompute pool, not dense workspace or scratch-disk capacity."
        )
    if state.axis == "orthogonalization":
        return f"{state.orthogonalization.description} {state.orthogonalization.risk}"
    if state.axis == "factor algorithm":
        if not state.preconditioner.factor_store_required:
            return f"N/A for {state.preconditioner.label}."
        return f"{state.factor_algorithm.description} {state.factor_algorithm.evidence}"
    if state.axis == "preconditioner":
        return f"{state.preconditioner.v1_scope}; {state.preconditioner.evidence}"
    if state.axis == "factor store":
        if not state.preconditioner.factor_store_required:
            return f"N/A for {state.preconditioner.label}."
        return f"{state.factor_store.temporary_io} {state.factor_store.evidence}"
    if state.axis == "observation":
        return state.observation.risk
    if state.axis == "threads":
        return state.threads.risk
    if state.axis == "thread lane":
        return f"{state.thread_lane.requirement} {state.thread_lane.risk}"
    if state.axis == "budgets":
        return state.budgets.risk
    if state.axis == "execution lane":
        return (
        f"{state.execution_lane.lifecycle} {state.execution_lane.affinity_cache} "
        f"{state.execution_lane.risk}"
        )
    return f"Unknown comparison axis {state.axis!r}."


def render(state: LabState, color: bool) -> str:
    result = assess(state)
    plan = result.plan
    ledger = plan.resource
    evidence_kind = "WHAT-IF" if state.evidence.hypothetical else "CURRENT"
    if not plan.factor_store_applicable:
        factor_store = "N/A for selected preconditioner"
    elif state.factor_store.reservation_mode == "selected-cap":
        factor_store = (
            f"{state.factor_store.label}; explicit resident/recompute cap="
            f"{state.factor_cap_gib:g} GiB; {state.factor_store.temporary_io}"
        )
    else:
        factor_store = f"{state.factor_store.label}; {state.factor_store.temporary_io}"
    factor_algorithm = (
        state.factor_algorithm.label
        if plan.factor_algorithm_applicable
        else "N/A for selected preconditioner"
    )
    dense_substrate = (
        f"{state.dense.label} [audited {state.dense.audited_coordinate}]"
        if plan.dense_applicable
        else "N/A for selected preconditioner"
    )
    unknowns = "; ".join(ledger.unknown_reservations)
    assumptions = " ".join(ledger.assumptions)
    lines: list[str] = []

    lines.append(styled("RAPIDRBF SOLVER-STACK SOLVE-PLAN LAB - THROWAWAY", BOLD, color))
    lines.append(
        styled(
            "Prototype cases are not acceptance IDs; WHAT-IF evidence is never an observation.",
            DIM,
            color,
        )
    )
    lines.append("")
    lines.append(styled("PROTOTYPE WORKLOAD CASE", BOLD, color))
    lines.append(
        f"{state.workload.prototype_id}  case={state.workload.case_id}  [{state.workload.stage}]"
    )
    lines.extend(wrapped("Accepted seed", state.workload.accepted_seed))
    lines.extend(wrapped("Purpose", state.workload.description))
    lines.extend(wrapped("Operator", state.workload.operator_route))
    lines.extend(wrapped("Authority", state.workload.baseline_authority))
    lines.extend(wrapped("Equation count", state.workload.unknowns_note))
    lines.append("")
    lines.append(styled("INVARIANT-CHECKED SOLVE PLAN", BOLD, color))
    lines.extend(
        wrapped(
            "Dense/factors",
            f"{dense_substrate}; factor algorithm={factor_algorithm}",
        )
    )
    lines.extend(
        wrapped(
            "Krylov",
            f"{state.krylov.label} [audited {state.krylov.audited_coordinate}]; "
            f"window/cap={ledger.krylov_window}; "
            f"{state.orthogonalization.label}",
        )
    )
    lines.extend(wrapped("Preconditioner", f"{state.preconditioner.label}; {state.preconditioner.topology}"))
    lines.extend(wrapped("Factor store", factor_store))
    lines.extend(wrapped("Algebraic observation", f"{state.observation.label}; {state.observation.schedule}"))
    lines.extend(wrapped("Terminal authority", plan.terminal_authority))
    lines.extend(
        wrapped(
            "Threads/budgets",
            f"{state.threads.label}; lane={state.thread_lane.label}; {state.budgets.label}",
        )
    )
    lines.extend(
        wrapped(
            "Execution lane",
            f"{state.platform}; {state.execution_lane.label}; "
            f"{state.execution_lane.lifecycle} {state.execution_lane.affinity_cache}",
        )
    )
    lines.extend(wrapped("Stable terminal states", ", ".join(plan.termination_states)))
    lines.append("")
    lines.append(styled("ONE SHARED RESOURCE LEDGER - PARTIAL UNTIL EVERY CATEGORY IS MATERIALIZED", BOLD, color))
    lines.append(
        f"Grant={state.grant_gib} GiB  V/Z={bytes_text(ledger.basis_bytes)}  "
        f"coefficients={bytes_text(ledger.coefficient_bytes)}  "
        f"factor reservation={bytes_text(ledger.factor_reservation_bytes)}"
    )
    lines.append(
        f"Known subtotal={bytes_text(ledger.known_subtotal_bytes)}  "
        f"headroom after known={bytes_text(ledger.headroom_after_known_bytes)}  "
        f"unknown categories={len(ledger.unknown_reservations)}"
    )
    lines.extend(wrapped("Unknown reservations", unknowns))
    lines.extend(wrapped("Assumptions", assumptions))
    lines.append("")
    lines.append(
        styled(
            f"EVIDENCE - {evidence_kind} - plan-shape fingerprint {plan.plan_shape_id}",
            BOLD,
            color,
        )
    )
    lines.extend(
        wrapped(
            "Immutable binding requirements",
            " | ".join(plan.binding_requirements),
        )
    )
    lines.extend(wrapped(state.evidence.label, state.evidence.description))
    lines.append(styled(f"DERIVED: {result.status}", BOLD, color))
    lines.extend(wrapped("Conclusion", result.conclusion))
    if plan.invariant_gaps:
        lines.extend(wrapped("Plan gaps", "; ".join(plan.invariant_gaps)))
    if result.evidence_gaps:
        lines.extend(wrapped("Evidence gaps", "; ".join(result.evidence_gaps)))
    if plan.warnings:
        lines.extend(wrapped("Warnings", "; ".join(plan.warnings)))
    lines.extend(wrapped("Next probes", " | ".join(result.probes[:2])))
    lines.append("")
    lines.append(styled(f"COMPARE AXIS - {state.axis.upper()} (other selections held fixed)", BOLD, color))
    lines.extend(render_axis(state))
    lines.extend(wrapped("Selected-axis detail", selected_axis_detail(state)))
    lines.append("")
    lines.extend(wrapped("Notice", state.notice))
    lines.append(
        styled(
            "[s] case  [d] dense  [l] factor algorithm  [k] Krylov  [a] orthogonalization  [m] window",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[p] preconditioner  [f] factor store  [c] factor cap  [o] observation  [t] ownership  [n] thread lane",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[b] budgets  [x] lifecycle/cache lane  [y] platform  [g] grant  [e] evidence  [v] axis  [r] reset  [q] quit",
            DIM,
            color,
        )
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the throwaway RapidRBF solver-stack solve-plan lab."
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
