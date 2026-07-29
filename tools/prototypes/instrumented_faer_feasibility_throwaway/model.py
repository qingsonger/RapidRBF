"""Pure state model for the instrumented-faer feasibility prototype.

Question: does the captured evidence support feasibility, rejection, or an
unjudged result for the exact two-factor/four-target source-feasibility gate?

This module performs no I/O. ``tui.py`` owns loading, terminal input, and
rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any


class View(StrEnum):
    SUMMARY = "summary"
    SOURCE = "source"
    EVIDENCE = "evidence"


@dataclass(frozen=True)
class LabState:
    summary: dict[str, Any]
    gate_index: int = 0
    view: View = View.SUMMARY
    reload_count: int = 0


VIEWS = tuple(View)


def new_state(summary: dict[str, Any]) -> LabState:
    if not summary.get("gates"):
        raise ValueError("evidence summary has no gates")
    return LabState(summary=summary)


def selected_gate(state: LabState) -> dict[str, Any]:
    gates = state.summary["gates"]
    return gates[state.gate_index % len(gates)]


def reduce_state(
    state: LabState,
    action: str,
    *,
    reloaded_summary: dict[str, Any] | None = None,
) -> LabState:
    if action == "next_gate":
        return replace(
            state,
            gate_index=(state.gate_index + 1) % len(state.summary["gates"]),
        )
    if action == "previous_gate":
        return replace(
            state,
            gate_index=(state.gate_index - 1) % len(state.summary["gates"]),
        )
    if action == "next_view":
        index = VIEWS.index(state.view)
        return replace(state, view=VIEWS[(index + 1) % len(VIEWS)])
    if action == "reload":
        if reloaded_summary is None:
            raise ValueError("reload requires a new immutable summary")
        gate_index = min(state.gate_index, len(reloaded_summary["gates"]) - 1)
        return replace(
            state,
            summary=reloaded_summary,
            gate_index=gate_index,
            reload_count=state.reload_count + 1,
        )
    if action == "noop":
        return state
    raise ValueError(f"unknown action {action!r}")


def target_matrix(state: LabState) -> tuple[tuple[str, ...], ...]:
    rows = []
    for target in state.summary["targets"]:
        rows.append(
            (
                target["target"],
                target["candidate_build"],
                target["two_factor_execution"],
                target["allocation_trace"],
                target["n_minus_one_control"],
                target["cancellation_work_unit_bound"],
                target["qualified_host_ack_latency"],
            )
        )
    return tuple(rows)


def gate_matrix(state: LabState) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (gate["gate_id"], gate["status"], gate["reason"])
        for gate in state.summary["gates"]
    )
