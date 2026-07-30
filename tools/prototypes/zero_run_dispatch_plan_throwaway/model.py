"""Pure throwaway state model for the Issue 59 dispatch decision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum


class Diagnosis(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    EMPTY_PATH_DIFF_PROVEN = "EMPTY_PATH_DIFF_PROVEN"
    REF_ONLY_PUSH_EVENT_ABSENT = "REF_ONLY_PUSH_EVENT_ABSENT"
    INVALID_OR_DIFFERENT_MECHANISM = "INVALID_OR_DIFFERENT_MECHANISM"


class CandidateGate(str, Enum):
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"


@dataclass(frozen=True)
class ProbeObservation:
    branch_only_runs: int | None = None
    path_gated_runs: int | None = None


@dataclass(frozen=True)
class ReplacementObservation:
    matching_runs: int | None = None
    current_run_matches: bool = False
    run_attempt: int | None = None
    event_identity_valid: bool = False
    preflight_release_valid: bool = False


@dataclass(frozen=True)
class State:
    actions_enabled: bool = True
    workflow_active: bool = True
    new_object: ProbeObservation = ProbeObservation()
    ref_only: ProbeObservation = ProbeObservation()
    replacement: ReplacementObservation = ReplacementObservation()


def diagnose(state: State) -> Diagnosis:
    values = (
        state.new_object.branch_only_runs,
        state.new_object.path_gated_runs,
        state.ref_only.branch_only_runs,
        state.ref_only.path_gated_runs,
    )
    if any(value is None for value in values):
        return Diagnosis.UNOBSERVED
    if not state.actions_enabled or not state.workflow_active:
        return Diagnosis.INVALID_OR_DIFFERENT_MECHANISM
    if values == (1, 1, 1, 0):
        return Diagnosis.EMPTY_PATH_DIFF_PROVEN
    if values == (1, 1, 0, 0):
        return Diagnosis.REF_ONLY_PUSH_EVENT_ABSENT
    return Diagnosis.INVALID_OR_DIFFERENT_MECHANISM


def candidate_gate(state: State) -> CandidateGate:
    observation = state.replacement
    if (
        observation.matching_runs == 1
        and observation.current_run_matches
        and observation.run_attempt == 1
        and observation.event_identity_valid
        and observation.preflight_release_valid
    ):
        return CandidateGate.UNLOCKED
    return CandidateGate.LOCKED


def reduce(state: State, action: str) -> State:
    if action == "unique":
        return replace(
            state,
            new_object=ProbeObservation(branch_only_runs=1, path_gated_runs=1),
        )
    if action == "ref-path":
        return replace(
            state,
            ref_only=ProbeObservation(branch_only_runs=1, path_gated_runs=0),
        )
    if action == "ref-none":
        return replace(
            state,
            ref_only=ProbeObservation(branch_only_runs=0, path_gated_runs=0),
        )
    if action == "ref-invalid":
        return replace(
            state,
            ref_only=ProbeObservation(branch_only_runs=0, path_gated_runs=1),
        )
    if action == "replacement-valid":
        return replace(
            state,
            replacement=ReplacementObservation(
                matching_runs=1,
                current_run_matches=True,
                run_attempt=1,
                event_identity_valid=True,
                preflight_release_valid=True,
            ),
        )
    if action == "replacement-duplicate":
        return replace(
            state,
            replacement=ReplacementObservation(
                matching_runs=2,
                current_run_matches=True,
                run_attempt=1,
                event_identity_valid=True,
                preflight_release_valid=True,
            ),
        )
    if action == "replacement-rerun":
        return replace(
            state,
            replacement=ReplacementObservation(
                matching_runs=1,
                current_run_matches=True,
                run_attempt=2,
                event_identity_valid=True,
                preflight_release_valid=True,
            ),
        )
    if action == "reset":
        return State()
    raise ValueError(f"unknown action: {action}")


def render_state(state: State) -> dict[str, object]:
    return {
        **asdict(state),
        "diagnosis": diagnose(state).value,
        "candidate_gate": candidate_gate(state).value,
    }
