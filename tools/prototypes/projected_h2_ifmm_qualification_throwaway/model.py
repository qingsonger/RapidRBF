"""Pure review-state logic for the Issue 65 candidate-closure audit.

Question: can the projected H2/IFMM candidate in Issues 64 and 65 be executed
and judged without making observation-affecting implementation choices?
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


FROZEN_CONTROLS = [
    {
        "id": "projected_operator",
        "status": "FROZEN",
        "value": "factor canonical B = Q^T A Q; recover through P_top",
    },
    {
        "id": "factor_family",
        "status": "FROZEN",
        "value": "symmetric strong-admissibility H2/IFMM-style approximate LDLT",
    },
    {
        "id": "leaf_limit",
        "status": "FROZEN",
        "value": "at most 64 signed-zero-normalized coordinate groups",
    },
    {
        "id": "approximation_gate",
        "status": "FROZEN",
        "value": "relative spectral truncation 2^-30; rank at most 256",
    },
    {
        "id": "solve_authority",
        "status": "FROZEN",
        "value": "right-FGMRES m=64, <=100 iterations, external 2^-24 certificate",
    },
    {
        "id": "fail_closed_rules",
        "status": "FROZEN",
        "value": "reject pivot/rank/cap failures; no hidden regularization or rebuild",
    },
]


IDENTITY_GAPS = [
    {
        "id": "projected_basis_binding",
        "status": "MISSING",
        "impact": (
            "No content-addressed global Q/P_top construction, reduced-coordinate "
            "permutation, or anchor/tie ordering is bound."
        ),
    },
    {
        "id": "coordinate_group_order",
        "status": "MISSING",
        "impact": (
            "Signed-zero normalization is named, but coordinate equality, merged "
            "value/gradient ownership, total ordering, and tie rules are not."
        ),
    },
    {
        "id": "cluster_tree",
        "status": "MISSING",
        "impact": (
            "Leaf capacity is fixed, but split axis, split point, degenerate "
            "geometry handling, child order, and tree serialization are not."
        ),
    },
    {
        "id": "admissibility_predicate",
        "status": "MISSING",
        "impact": (
            "eta=1 is fixed, but the diameter/distance formula, anisotropy metric, "
            "component composition, equality branch, and compact-support partition "
            "are not."
        ),
    },
    {
        "id": "nested_basis_construction",
        "status": "MISSING",
        "impact": (
            "Nested bases and deterministic SVD qualification are required without "
            "a sampling matrix, SVD implementation, sign/tie convention, transfer "
            "construction, or rounding identity."
        ),
    },
    {
        "id": "elimination_and_pivots",
        "status": "MISSING",
        "impact": (
            "LDLT is named without an elimination order, supernode/block policy, "
            "pivot interpretation, symmetry restoration rule, or arithmetic binding."
        ),
    },
    {
        "id": "fill_in_recompression",
        "status": "MISSING",
        "impact": (
            "Fill-ins must be recompressed, but aggregation order, update ownership, "
            "recompression schedule, and rank-cap failure point are unspecified."
        ),
    },
    {
        "id": "source_build_lane_binding",
        "status": "MISSING",
        "impact": (
            "No candidate source digest, dependency lock, compiler/runtime identity, "
            "or four-target build binding exists."
        ),
    },
    {
        "id": "candidate_evidence_authority",
        "status": "MISSING",
        "impact": (
            "No append-only candidate evidence schema, independent verifier, "
            "attempt cardinality, or pre-entry invalidity boundary is bound."
        ),
    },
    {
        "id": "structural_100k_fixtures",
        "status": "MISSING",
        "impact": (
            "The three 100k shapes are named, but no content-addressed materialized "
            "geometry/identity manifests are bound for setup-only execution."
        ),
    },
]


SUCCESSOR_SLICE = [
    {
        "order": 1,
        "title": (
            "Freeze and materialize the exact projected H2/IFMM candidate "
            "and qualification authority"
        ),
        "boundary": (
            "Bind source, construction semantics, fixtures, builds, controller, "
            "schema, and independent verification; execute zero candidate coordinates."
        ),
    },
    {
        "order": 2,
        "title": (
            "Execute the source-bound projected H2/IFMM complete-panel "
            "and 100k structural qualification"
        ),
        "boundary": (
            "Run exactly the immutable binding; make no implementation, threshold, "
            "tree, rank, retry, or evidence-policy choice after candidate entry."
        ),
    },
]


def build_review() -> dict[str, Any]:
    gaps = deepcopy(IDENTITY_GAPS)
    return {
        "question": (
            "Is the Issue 65 candidate closed enough for reproducible, "
            "non-observation-driven scientific qualification?"
        ),
        "review_status": "PENDING_HUMAN_RATIFICATION",
        "review_note": "",
        "frozen_control_count": len(FROZEN_CONTROLS),
        "identity_gap_count": len(gaps),
        "candidate_entry_permitted": False,
        "recommended_disposition": "INVALID_UNJUDGED",
        "reason": (
            "Result-affecting candidate identity and evidence-authority choices "
            "remain open; any run would qualify an implementer's choices rather "
            "than the single live-ratified candidate."
        ),
        "frozen_controls": deepcopy(FROZEN_CONTROLS),
        "identity_gaps": gaps,
        "successor_slice": deepcopy(SUCCESSOR_SLICE),
        "non_claims": [
            "No H2/IFMM numerical or resource result has been observed.",
            "No factor route, implementation, dependency, or storage policy is rejected.",
            "No accepted threshold or authority is weakened or reinterpreted.",
        ],
    }


def transition(
    state: dict[str, Any], action: str, note: str = ""
) -> dict[str, Any]:
    result = deepcopy(state)
    if action == "accept":
        result["review_status"] = "ACCEPT_INVALID_UNJUDGED_AND_SUCCESSOR_SPLIT"
    elif action == "adjust":
        result["review_status"] = "REQUEST_CLOSURE_AUDIT_ADJUSTMENT"
    elif action == "reject":
        result["review_status"] = "REJECT_CLOSURE_DEFECT_FINDING"
    else:
        raise ValueError(f"unknown review action: {action}")
    result["review_note"] = note
    return result
