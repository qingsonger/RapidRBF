"""Pure review-state logic for the Issue 63 stagnation diagnosis."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


FIT_THRESHOLD = 2.0**-24


def build_review(
    accepted: dict[str, Any], full_window: dict[str, Any]
) -> dict[str, Any]:
    accepted_m3 = [
        run
        for run in accepted["runs"]
        if run["workload_id"] == "M3-HERMITE-10K"
        and run["enriched_coarse_target"] == 4096
    ]
    full_window_runs = full_window["runs"]
    if len(accepted_m3) != 1 or len(full_window_runs) != 1:
        raise ValueError("Issue 63 evidence shape differs")
    m64 = accepted_m3[0]
    m100 = full_window_runs[0]
    if (
        m64["window"] != 64
        or m100["window"] != 100
        or m100["workload_id"] != "M3-HERMITE-10K"
        or m100["enriched_coarse_target"] != 4096
    ):
        raise ValueError("Issue 63 diagnostic binding differs")

    c64 = m64["direct_certificate"]
    c100 = m100["bound_certificate"]
    return {
        "review_status": "PENDING_HUMAN_RATIFICATION",
        "review_note": "",
        "recommended_decision": "SAME_HIERARCHY_RAS_FAMILY_EXHAUSTED_FOR_V1",
        "accepted_m64": {
            "iterations": m64["iterations"],
            "preconditioner_actions": m64["actions"][
                "preconditioner_internal"
            ],
            "value": c64["value_residual"],
            "gradient": c64["gradient_residual"],
        },
        "full_window_m100": {
            "iterations": m100["iterations"],
            "preconditioner_actions": m100["actions"][
                "preconditioner_internal"
            ],
            "value": c100["value_residual"],
            "gradient": c100["gradient_residual"],
            "cpd": c100["cpd_eta"],
            "orthogonality_defect": m100["maximum_orthogonality_defect"],
            "peak_bytes": m100["process_peak_working_set_bytes"],
            "basis_bytes": m100["basis_bytes"],
            "run_identity": m100["run_identity_sha256"],
        },
        "comparison": {
            "value_improvement": (
                c64["value_residual"] / c100["value_residual"]
            ),
            "gradient_improvement": (
                c64["gradient_residual"] / c100["gradient_residual"]
            ),
            "value_threshold_multiple": c100["value_residual"]
            / FIT_THRESHOLD,
            "gradient_threshold_multiple": c100["gradient_residual"]
            / FIT_THRESHOLD,
        },
        "closed_hypotheses": [
            "qualified factor or complete-direct authority defect",
            "fine/coarse composition or residual-transfer order",
            "scaling-only or orthogonalization defect",
            "m=64 restart truncation",
        ],
        "surviving_mechanism": (
            "same-hierarchy geometric coarse content lacks the coupled "
            "global M3 slow modes"
        ),
    }


def transition(
    state: dict[str, Any], action: str, note: str = ""
) -> dict[str, Any]:
    result = deepcopy(state)
    if action == "accept":
        result["review_status"] = (
            "ACCEPT_SAME_HIERARCHY_RAS_FAMILY_EXHAUSTED_FOR_V1"
        )
    elif action == "adjust":
        result["review_status"] = "REQUEST_ISSUE63_ADJUSTMENT"
    elif action == "reject":
        result["review_status"] = "REJECT_ISSUE63_DISPOSITION"
    else:
        raise ValueError(f"unknown review action: {action}")
    result["review_note"] = note
    return result
