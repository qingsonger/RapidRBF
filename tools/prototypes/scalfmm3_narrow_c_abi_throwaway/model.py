"""Pure state model for the throwaway ScalFMM3 C-ABI decision lab.

Question: can the pinned ScalFMM3 engine be contained behind a caller-first,
versioned narrow C ABI, and what observed boundary failure disqualifies it from
large-workload Auto?

This module is deterministic and performs no I/O. ``tui.py`` owns interaction
and rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    detail: str


WORKFLOWS = (
    Choice(
        "operator",
        "PreparedOperator",
        "fixed source+target geometry; each exclusive lane accepts new weights",
    ),
    Choice(
        "field",
        "PreparedField",
        "fixed sources+weights; each exclusive lane accepts a target batch",
    ),
)

ACTIONS = (
    Choice("a", "A", "declared A input/output layout"),
    Choice("f", "F", "declared F input/output layout"),
    Choice("ft", "F^T", "declared F^T input/output layout"),
    Choice("h", "H", "declared H input/output layout"),
)

DIMENSIONS = (1, 2, 3)

GEOMETRIES = (
    Choice("self", "self", "source and target coordinates are logically identical"),
    Choice("cross", "cross", "source and target coordinates are independent"),
)

TERMS = (
    Choice(
        "gaussian",
        "Gaussian",
        "the only term whose actual mechanics are exercised by this probe",
    ),
    Choice(
        "required-smooth",
        "required smooth family",
        "source lineage exists, but this probe does not execute family closure",
    ),
    Choice(
        "split-tail",
        "split smooth tail",
        "Rust decomposes the kernel; the ABI receives one smooth isotropic term",
    ),
)

ANISOTROPIES = (
    Choice("identity", "identity", "Rust passes canonical coordinates"),
    Choice("diagonal", "positive diagonal", "Rust transforms to metric coordinates"),
    Choice("shear", "validated shear", "Rust transforms to metric coordinates"),
)

RUN_CASES = (
    Choice(
        "valid",
        "valid run",
        "checked inputs, staged result, then synchronous copy under exclusive caller access",
    ),
    Choice(
        "repeat",
        "repeated run",
        "8 actual FMM repeats stayed within a 128 MiB probe-only span; not scale qualification",
    ),
    Choice(
        "bad-length",
        "bad length",
        "stable status; values unchanged; value_count zero; lane reusable",
    ),
    Choice(
        "pre-cancel",
        "pre-cancel",
        "cancel before work; values unchanged; value_count zero",
    ),
    Choice("tiny-grant", "tiny grant", "reject an insufficient declared resource grant"),
    Choice(
        "concurrent",
        "concurrent lane use",
        "one observed overlap returned BUSY; this does not prove hard isolation",
    ),
)

EVIDENCE_PROFILES = (
    Choice(
        "frozen-pass-through",
        "frozen mutable-evaluator pass-through",
        "inherits Polatory behavior without an owned narrow boundary",
    ),
    Choice(
        "retained-lane",
        "retained-lane narrow shim",
        "caller-first plan/lane prototype with Gaussian-only observed mechanics",
    ),
    Choice(
        "worker-process",
        "worker-process containment",
        "hypothetical hard containment around the same uncertified engine",
    ),
    Choice(
        "counterfactual",
        "all gates passed",
        "counterfactual evidence profile, not a present observation",
    ),
)


@dataclass(frozen=True)
class LabState:
    workflow_index: int = 0
    action_index: int = 0
    dimension_index: int = 2
    geometry_index: int = 1
    term_index: int = 0
    anisotropy_index: int = 0
    run_case_index: int = 0
    evidence_index: int = 1

    @property
    def workflow(self) -> Choice:
        return WORKFLOWS[self.workflow_index]

    @property
    def action(self) -> Choice:
        return ACTIONS[self.action_index]

    @property
    def dimension(self) -> int:
        return DIMENSIONS[self.dimension_index]

    @property
    def geometry(self) -> Choice:
        return GEOMETRIES[self.geometry_index]

    @property
    def term(self) -> Choice:
        return TERMS[self.term_index]

    @property
    def anisotropy(self) -> Choice:
        return ANISOTROPIES[self.anisotropy_index]

    @property
    def run_case(self) -> Choice:
        return RUN_CASES[self.run_case_index]

    @property
    def evidence(self) -> Choice:
        return EVIDENCE_PROFILES[self.evidence_index]


@dataclass(frozen=True)
class Gate:
    name: str
    status: str
    finding: str


@dataclass(frozen=True)
class Assessment:
    verdict: str
    reason: str
    c_plan: str
    c_lane: str
    evidence_ledger: tuple[tuple[str, str], ...]
    gates: tuple[Gate, ...]
    first_disqualifier: str


def _cycle(value: int, size: int) -> int:
    return (value + 1) % size


def transition(state: LabState, command: str) -> LabState:
    """Return a new state for one documented TUI command."""

    command = command.strip().lower()
    if command == "w":
        return replace(
            state, workflow_index=_cycle(state.workflow_index, len(WORKFLOWS))
        )
    if command == "a":
        return replace(state, action_index=_cycle(state.action_index, len(ACTIONS)))
    if command == "d":
        return replace(
            state, dimension_index=_cycle(state.dimension_index, len(DIMENSIONS))
        )
    if command == "g":
        return replace(
            state, geometry_index=_cycle(state.geometry_index, len(GEOMETRIES))
        )
    if command == "k":
        return replace(state, term_index=_cycle(state.term_index, len(TERMS)))
    if command == "x":
        return replace(
            state,
            anisotropy_index=_cycle(
                state.anisotropy_index, len(ANISOTROPIES)
            ),
        )
    if command == "r":
        return replace(
            state, run_case_index=_cycle(state.run_case_index, len(RUN_CASES))
        )
    if command == "e":
        return replace(
            state,
            evidence_index=_cycle(state.evidence_index, len(EVIDENCE_PROFILES)),
        )
    if command == "0":
        return LabState()
    return state


def _verdict(profile: str) -> tuple[str, str]:
    if profile == "frozen-pass-through":
        return (
            "AUTO-INELIGIBLE",
            "mutable native state, failures, and resources are not owned by a narrow boundary",
        )
    if profile == "retained-lane":
        return (
            "FORCED-PROTOTYPE-ONLY",
            "the caller-first seam is plausible, but observed evidence cannot certify success",
        )
    if profile == "worker-process":
        return (
            "FORCED-PROTOTYPE-ONLY",
            "process isolation can bound failure blast radius; it cannot create a certificate",
        )
    return (
        "COUNTERFACTUAL AUTO-ELIGIBLE",
        "only if every gate is passed for the exact call and release platform",
    )


def _gates(profile: str) -> tuple[Gate, ...]:
    if profile == "counterfactual":
        return (
            Gate("semantic/action closure", "PASS*", "all families x 1D-3D x A/F/F^T/H"),
            Gate("sound call certificate", "PASS*", "complete-batch conservative bound"),
            Gate("owned prepared reuse", "PASS*", "bounded immutable plan + exclusive lane"),
            Gate("cancel/resources", "PASS*", "finite quantum and enforced per-call grant"),
            Gate("scale/repeat stability", "PASS*", "differential, stress, and high-water evidence"),
            Gate("tier-one closure", "PASS*", "self-contained runtime and license inventory"),
        )

    reuse = "FAIL" if profile == "frozen-pass-through" else "PARTIAL"
    control = "HYPOTHESIS" if profile == "worker-process" else "FAIL"
    return (
        Gate("semantic/action closure", "PARTIAL", "source lineage; Gaussian mechanics only"),
        Gate("sound call certificate", "FAIL", "sampling/direct diagnostic is not proof"),
        Gate("owned prepared reuse", reuse, "lane shape probed; bounds not established"),
        Gate(
            "cancel/resources",
            control,
            (
                "worker isolation is unbuilt and cannot create a certificate"
                if profile == "worker-process"
                else "no finite in-flight quantum or full thread lease"
            ),
        ),
        Gate("scale/repeat stability", "MISSING", "no accepted large/repeated evidence"),
        Gate("tier-one closure", "MISSING", "runtime and license closure incomplete"),
    )


def assess(state: LabState) -> Assessment:
    """Assess the selected evidence profile without promoting hypotheses to facts."""

    profile = state.evidence.key
    verdict, reason = _verdict(profile)
    gates = _gates(profile)
    invalid_combination = (
        state.workflow.key == "field" and state.geometry.key == "self"
    )

    if state.workflow.key == "operator":
        c_plan = (
            "copy fixed source+target metric coordinates; bind one dimension, "
            "action, geometry, and isotropic term"
        )
        c_lane = "own mutable native evaluator; each run supplies weights"
    else:
        if state.geometry.key == "self":
            c_plan = (
                "invalid prototype combination: a changing-target field plan "
                "cannot promise fixed self geometry"
            )
            c_lane = "reject before native execution; select cross geometry"
        else:
            c_plan = (
                "copy fixed source metric coordinates+weights; bind one dimension, "
                "action, and isotropic term"
            )
            c_lane = "own mutable native evaluator; each run supplies target coordinates"

    selected_observation = (
        "Gaussian adapter mechanics only"
        if state.term.key == "gaussian"
        else "no executed mechanics for this term selection"
    )
    ledger = (
        (
            "SOURCE",
            "pinned fork exposes 1D-3D A/F/F^T/H lineage, mutable setters, sampled accuracy",
        ),
        (
            "OBSERVED",
            f"{selected_observation}; Gaussian-only matrices have 36 direct-route and 36 actual FMM-route cases",
        ),
        (
            "MISSING",
            "sound certificate, finite cancellation, enforced resources, scale, release closure",
        ),
        (
            "COUNTERFACTUAL",
            "worker isolation or six passed gates are hypotheses until separately measured",
        ),
    )

    first_disqualifier = (
        "none in the counterfactual profile"
        if profile == "counterfactual"
        else "sound complete-batch certificate unavailable (first observed hard Auto failure)"
    )
    if invalid_combination:
        verdict = "INVALID SELECTION"
        reason = (
            "PreparedField changes targets, so this prototype cannot bind fixed "
            "self geometry"
        )
        gates = (
            Gate(
                "semantic/action closure",
                "INVALID",
                "changing-target field and fixed self geometry contradict",
            ),
            *gates[1:],
        )
        first_disqualifier = "invalid workflow/geometry combination"
    return Assessment(
        verdict=verdict,
        reason=reason,
        c_plan=c_plan,
        c_lane=c_lane,
        evidence_ledger=ledger,
        gates=gates,
        first_disqualifier=first_disqualifier,
    )


def selection_summary(state: LabState) -> str:
    """Explain what the current controls ask the probe to exercise."""

    return (
        f"{state.workflow.label}; {state.action.label}/{state.dimension}D/"
        f"{state.geometry.label}; {state.term.label}; {state.anisotropy.label}; "
        f"{state.run_case.label}"
    )
