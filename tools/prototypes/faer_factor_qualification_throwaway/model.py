"""Pure state/decision logic for the throwaway faer qualification lab.

Question: can the bound Windows std+linalg direct in-process stock-faer
0.24.4 path satisfy every gate required to publish run-scoped
``ValidatedFactor`` and externally certified ``Solved`` corrections for the
complete canonical 1k/10k mechanism-panel factor corpus?

This module owns no terminal or filesystem I/O.  The TUI is a thin adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Iterable, Mapping


class GateStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"
    NOT_REACHED = "NOT_REACHED"


class Disposition(StrEnum):
    QUALIFIED_PACKED = "QUALIFIED_PACKED"
    QUALIFIED_RUN_SCOPED_RECOMPUTE = "QUALIFIED_RUN_SCOPED_RECOMPUTE"
    NOT_ADMITTED_DIAGNOSTIC_ONLY = "NOT_ADMITTED_DIAGNOSTIC_ONLY"


@dataclass(frozen=True)
class Gate:
    gate_id: str
    title: str
    status: GateStatus
    authority: str
    reason: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class LabState:
    gates: tuple[Gate, ...]
    selected_gate: int = 0
    view: str = "decision"
    reload_count: int = 0


REQUIRED_GATE_IDS = (
    "semantic_corpus",
    "factor_health_profile",
    "owned_representation",
    "external_certificate",
    "exact_transient_accounting",
    "caller_permit_lease",
    "bounded_cancellation",
    "lane_closure",
    "atomic_controls",
    "durable_pack_reload",
)

RECOMPUTE_ONLY_GAP = "durable_pack_reload"
VIEWS = ("decision", "evidence", "profile")


def decide(gates: Iterable[Gate]) -> Disposition:
    """Return one of the three profile-authorized outcomes.

    Recompute is deliberately narrow: it is available only if every required
    gate except durable pack/reload passes.  A PARTIAL or NOT_REACHED gate is
    not silently treated as success.
    """

    gate_list = tuple(gates)
    gate_ids = [gate.gate_id for gate in gate_list]
    duplicate_ids = sorted(
        gate_id for gate_id in set(gate_ids) if gate_ids.count(gate_id) > 1
    )
    if duplicate_ids:
        raise ValueError(f"gate topology has duplicate ids: {duplicate_ids}")

    by_id = {gate.gate_id: gate for gate in gate_list}
    if set(by_id) != set(REQUIRED_GATE_IDS):
        missing = sorted(set(REQUIRED_GATE_IDS) - set(by_id))
        extra = sorted(set(by_id) - set(REQUIRED_GATE_IDS))
        raise ValueError(f"gate topology drifted; missing={missing}, extra={extra}")

    nonpassing = {
        gate_id
        for gate_id in REQUIRED_GATE_IDS
        if by_id[gate_id].status is not GateStatus.PASS
    }
    if not nonpassing:
        return Disposition.QUALIFIED_PACKED
    if nonpassing == {RECOMPUTE_ONLY_GAP}:
        return Disposition.QUALIFIED_RUN_SCOPED_RECOMPUTE
    return Disposition.NOT_ADMITTED_DIAGNOSTIC_ONLY


def gates_from_summary(summary: Mapping[str, Any]) -> tuple[Gate, ...]:
    gates = tuple(
        Gate(
            gate_id=item["gate_id"],
            title=item["title"],
            status=GateStatus(item["status"]),
            authority=item["authority"],
            reason=item["reason"],
            evidence=tuple(item.get("evidence", ())),
        )
        for item in summary["gates"]
    )
    observed = Disposition(summary["disposition"])
    computed = decide(gates)
    if observed is not computed:
        raise ValueError(
            f"summary disposition {observed} disagrees with reducer {computed}"
        )
    return gates


def initial_state(summary: Mapping[str, Any]) -> LabState:
    return LabState(gates=gates_from_summary(summary))


def reduce_state(state: LabState, action: str) -> LabState:
    if action == "next_gate":
        return replace(
            state, selected_gate=(state.selected_gate + 1) % len(state.gates)
        )
    if action == "previous_gate":
        return replace(
            state, selected_gate=(state.selected_gate - 1) % len(state.gates)
        )
    if action == "next_view":
        current = VIEWS.index(state.view)
        return replace(state, view=VIEWS[(current + 1) % len(VIEWS)])
    if action == "reloaded":
        return replace(state, reload_count=state.reload_count + 1)
    if action == "noop":
        return state
    raise ValueError(f"unknown action {action!r}")
