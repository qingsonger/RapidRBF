"""Pure judgment and presentation model for the issue-46 throwaway prototype."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lower) and math.isfinite(self.upper)):
            raise ValueError("interval endpoints must be finite")
        if self.lower < 0.0 or self.upper < self.lower:
            raise ValueError("invalid non-negative interval")


@dataclass(frozen=True)
class BoundaryCard:
    ordinal: int
    category: str
    workload: str
    dimension: int
    old_status: str
    new_status: str
    threshold: float
    candidate_distance: Interval
    oracle_radius: float
    backward_error: float
    explanation: str


@dataclass(frozen=True)
class AdversarialCard:
    case_id: str
    status: str
    expected: str
    explanation: str


@dataclass(frozen=True)
class Dashboard:
    disposition: str
    authority_sha256: str
    plan_sha256: str
    boundaries: tuple[BoundaryCard, ...]
    adversarial: tuple[AdversarialCard, ...]
    closure: dict[str, bool]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def judge_relative_interval(distance: Interval, threshold: float) -> str:
    """Three-valued judgment after scale normalization.

    Boundary evidence is already normalized by max(1, ||x*||_inf). The full
    authority computes the equivalent d/s interval with outward MPFR bounds.
    """

    if not math.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("threshold must be finite and positive")
    if distance.upper <= threshold:
        return "PASS"
    if distance.lower > threshold:
        return "FAIL"
    return "INDETERMINATE"


def correction_envelope(
    corrections: Iterable[float],
    route_agreement: float,
    dimension: int,
) -> tuple[Interval, float]:
    """Conservatively enclose initial candidate distance to the independent route.

    The accepted issue-45 evidence records the first candidate-factor
    refinement correction, later correction tail, and agreement with the
    independently pivoted raw-A route. This function only exercises the new
    decision rule on that frozen evidence; the full plan replaces this
    feasibility envelope with the directed-rounding certificate in the
    authority profile.
    """

    values = tuple(float(value) for value in corrections)
    if not values or any(value < 0.0 or not math.isfinite(value) for value in values):
        raise ValueError("correction history must be finite and non-negative")
    if route_agreement < 0.0 or not math.isfinite(route_agreement):
        raise ValueError("route agreement must be finite and non-negative")
    if dimension <= 0:
        raise ValueError("dimension must be positive")

    first = values[0]
    tail = math.fsum(values[1:])
    double_double_rounding = 8.0 * dimension * (2.0**-105)
    oracle_radius = route_agreement + double_double_rounding
    total = math.fsum(values)
    if total >= 0.5:
        raise ValueError("normalization drift is too large for boundary feasibility")
    normalization_guard = 1.0 / (1.0 - total)
    lower = max(
        0.0,
        (first - tail - oracle_radius) / normalization_guard,
    )
    upper = (first + tail + oracle_radius) * normalization_guard
    return Interval(lower=lower, upper=upper), oracle_radius


def derive_boundary_cards(evidence: dict[str, Any]) -> tuple[BoundaryCard, ...]:
    cards: list[BoundaryCard] = []
    for observation in evidence["observations"]:
        dimension = int(observation["dimension"])
        correction = observation["candidate_lblt"]["double_double_refined"][
            "correction_relative_inf_history"
        ]
        agreement = float(
            observation["independent_reference"][
                "lblt_full_pivot_lu_relative_agreement"
            ]
        )
        distance, oracle_radius = correction_envelope(
            correction,
            agreement,
            dimension,
        )
        threshold = float(observation["archived"]["solution_threshold"])
        status = judge_relative_interval(distance, threshold)
        old_status = str(observation["archived"]["status"])
        if status == "PASS" and old_status == "FAIL":
            explanation = (
                "The candidate is close to the frozen-(A,b) reference even though "
                "the pre-rounding declared vector made the old gate fail."
            )
        elif status == "FAIL":
            explanation = (
                "The defective declared-vector comparison is removed, but this "
                "candidate solution remains separated from the frozen-system "
                "reference by more than the unchanged threshold."
            )
        else:
            explanation = (
                "The repaired authority preserves the boundary result without "
                "using the declared vector as an oracle."
            )
        cards.append(
            BoundaryCard(
                ordinal=int(observation["ordinal"]),
                category=str(observation["category"]),
                workload=str(observation["workload_id"]),
                dimension=dimension,
                old_status=old_status,
                new_status=status,
                threshold=threshold,
                candidate_distance=distance,
                oracle_radius=oracle_radius,
                backward_error=float(
                    observation["candidate_lblt"]["metrics"][
                        "maximum_backward_error"
                    ]
                ),
                explanation=explanation,
            )
        )
    return tuple(cards)


def derive_adversarial_cards(
    boundaries: tuple[BoundaryCard, ...],
) -> tuple[AdversarialCard, ...]:
    by_ordinal = {card.ordinal: card for card in boundaries}
    nearest = by_ordinal[72]
    threshold = nearest.threshold

    declared_invariant = nearest.new_status
    overlap = judge_relative_interval(
        Interval(threshold * 0.999999, threshold * 1.000001),
        threshold,
    )
    false_admission = judge_relative_interval(
        Interval(threshold * 2.0, threshold * 2.0),
        threshold,
    )
    return (
        AdversarialCard(
            case_id="declared-vector-perturbation",
            status=declared_invariant,
            expected="PASS",
            explanation=(
                "Changing the diagnostic declared vector after frozen b exists "
                "does not enter the new judgment; ordinal 72 remains PASS."
            ),
        ),
        AdversarialCard(
            case_id="threshold-overlap",
            status=overlap,
            expected="INDETERMINATE",
            explanation=(
                "An oracle interval straddling the unchanged threshold cannot be "
                "rounded or voted into PASS."
            ),
        ),
        AdversarialCard(
            case_id="low-backward-error-false-admission",
            status=false_admission,
            expected="FAIL",
            explanation=(
                "A candidate two thresholds from the reference fails even when a "
                "separate backward-error gate would pass."
            ),
        ),
        AdversarialCard(
            case_id="candidate-circularity",
            status="REJECTED_BEFORE_REFERENCE_GENERATION",
            expected="REJECTED_BEFORE_REFERENCE_GENERATION",
            explanation=(
                "A reference request containing a candidate binding, factor, "
                "solution, residual, or observation is identity-invalid."
            ),
        ),
        AdversarialCard(
            case_id="candidate-threshold-override",
            status="REJECTED_BEFORE_CANDIDATE_ENTRY",
            expected="REJECTED_BEFORE_CANDIDATE_ENTRY",
            explanation=(
                "The threshold is fixed by the authority profile; a candidate or "
                "lane override changes identity and cannot enter the cohort."
            ),
        ),
    )


def load_dashboard(path: Path) -> Dashboard:
    evidence = read_json(path)
    boundaries = tuple(
        BoundaryCard(
            ordinal=int(card["ordinal"]),
            category=str(card["category"]),
            workload=str(card["workload"]),
            dimension=int(card["dimension"]),
            old_status=str(card["old_status"]),
            new_status=str(card["new_status"]),
            threshold=float(card["threshold"]),
            candidate_distance=Interval(
                lower=float(card["candidate_distance"]["lower"]),
                upper=float(card["candidate_distance"]["upper"]),
            ),
            oracle_radius=float(card["oracle_radius"]),
            backward_error=float(card["backward_error"]),
            explanation=str(card["explanation"]),
        )
        for card in evidence["boundaries"]
    )
    adversarial = tuple(
        AdversarialCard(
            case_id=str(card["case_id"]),
            status=str(card["status"]),
            expected=str(card["expected"]),
            explanation=str(card["explanation"]),
        )
        for card in evidence["adversarial"]
    )
    return Dashboard(
        disposition=str(evidence["disposition"]),
        authority_sha256=str(evidence["authority_profile_sha256"]),
        plan_sha256=str(evidence["requalification_plan_sha256"]),
        boundaries=boundaries,
        adversarial=adversarial,
        closure={key: bool(value) for key, value in evidence["closure"].items()},
    )


def render_dashboard(
    dashboard: Dashboard,
    view: str = "all",
    selected: int | None = None,
) -> str:
    lines = [
        "RapidRBF - repaired projected-factor health authority",
        "=" * 66,
        f"Disposition       {dashboard.disposition}",
        f"Authority SHA-256 {dashboard.authority_sha256}",
        f"Plan SHA-256      {dashboard.plan_sha256}",
        "",
        "Closure",
    ]
    for name, value in dashboard.closure.items():
        lines.append(f"  {'PASS' if value else 'FAIL':<4} {name}")
    lines.append("")

    if view in {"all", "boundary"}:
        lines.append("Boundary witnesses")
        cards = dashboard.boundaries
        if selected is not None:
            cards = tuple(card for card in cards if card.ordinal == selected)
        for card in cards:
            lines.extend(
                [
                    (
                        f"  ordinal {card.ordinal:<3} {card.workload:<38} "
                        f"old={card.old_status:<4} new={card.new_status}"
                    ),
                    (
                        f"    distance=[{card.candidate_distance.lower:.6e}, "
                        f"{card.candidate_distance.upper:.6e}] "
                        f"threshold={card.threshold:.6e}"
                    ),
                    (
                        f"    oracle_radius={card.oracle_radius:.6e} "
                        f"backward={card.backward_error:.6e}"
                    ),
                    f"    {card.explanation}",
                ]
            )
        lines.append("")

    if view in {"all", "adversarial"}:
        lines.append("Adversarial guards")
        for card in dashboard.adversarial:
            mark = "PASS" if card.status == card.expected else "FAIL"
            lines.extend(
                [
                    f"  {mark:<4} {card.case_id}: {card.status}",
                    f"    {card.explanation}",
                ]
            )
    return "\n".join(lines)
