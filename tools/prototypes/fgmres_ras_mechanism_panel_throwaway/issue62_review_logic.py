"""Pure review-state logic for the Issue 62 throwaway cohort."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_review(evidence: dict[str, Any]) -> dict[str, Any]:
    runs = evidence["runs"]
    if (
        evidence["schema"] != "RapidRBF/Coarse4096MechanismPanel/v1"
        or len(runs) != 18
    ):
        raise ValueError("Issue 62 evidence shape differs")

    one_k = [run for run in runs if run["scale_id"] == "1k"]
    current = [
        run
        for run in runs
        if run["scale_id"] == "10k"
        and run["enriched_coarse_target"] == 0
    ]
    candidate = [
        run
        for run in runs
        if run["scale_id"] == "10k"
        and run["enriched_coarse_target"] == 4096
    ]
    if len(one_k) != 6 or len(current) != 6 or len(candidate) != 6:
        raise ValueError("Issue 62 cohort partition differs")

    by_workload_current = {run["workload_id"]: run for run in current}
    by_workload_candidate = {run["workload_id"]: run for run in candidate}
    m3_current = by_workload_current["M3-HERMITE-10K"]
    m3_candidate = by_workload_candidate["M3-HERMITE-10K"]
    current_controls_match = all(
        run["direct_certificate"]["pass"]
        == (run["workload_id"] != "M3-HERMITE-10K")
        for run in current
    )
    factor = evidence["run_scoped_factor_evidence"]
    maximum_peak = max(run["process_peak_working_set_bytes"] for run in runs)
    maximum_actions = max(run["actions"]["preconditioner_internal"] for run in runs)
    unique_run_ids = len({run["run_identity_sha256"] for run in runs})

    return {
        "review_status": "PENDING_HUMAN_RATIFICATION",
        "review_note": "",
        "recorded_disposition": evidence["prototype_disposition"],
        "recommended_decision": "COARSE4096_REJECTED_DIAGNOSTIC_ONLY",
        "cohort": {
            "runs": len(runs),
            "one_k_identity_controls": len(one_k),
            "current_10k_controls": len(current),
            "coarse4096_10k_candidates": len(candidate),
            "current_controls_match": current_controls_match,
            "one_k_all_pass": all(
                run["direct_certificate"]["pass"] for run in one_k
            ),
            "candidate_passes": sum(
                run["direct_certificate"]["pass"] for run in candidate
            ),
            "candidate_failures": sum(
                not run["direct_certificate"]["pass"] for run in candidate
            ),
            "unique_run_ids": unique_run_ids,
        },
        "factor_reference": {
            "generated_factor_sources": factor[
                "generated_enriched_factor_sources"
            ],
            "reference_rhs_passes": factor[
                "generated_enriched_reference_rhs_passes"
            ],
            "maximum_q_upper": factor[
                "maximum_generated_reference_q_upper"
            ],
            "maximum_relative_radius": factor[
                "maximum_generated_reference_relative_radius"
            ],
        },
        "resources": {
            "maximum_peak_bytes": maximum_peak,
            "peak_limit_bytes": evidence["frozen_profile"][
                "process_peak_working_set_limit_bytes"
            ],
            "maximum_preconditioner_actions": maximum_actions,
            "preconditioner_action_limit": evidence["frozen_profile"][
                "maximum_preconditioner_operator_actions"
            ],
        },
        "m3": {
            "current": m3_current["direct_certificate"],
            "candidate": m3_candidate["direct_certificate"],
            "value_improvement": (
                m3_current["direct_certificate"]["value_residual"]
                / m3_candidate["direct_certificate"]["value_residual"]
            ),
            "gradient_improvement": (
                m3_current["direct_certificate"]["gradient_residual"]
                / m3_candidate["direct_certificate"]["gradient_residual"]
            ),
            "iterations": m3_candidate["iterations"],
            "preconditioner_actions": m3_candidate["actions"][
                "preconditioner_internal"
            ],
        },
        "candidate_rows": [
            {
                "workload_id": run["workload_id"],
                "pass": run["direct_certificate"]["pass"],
                "iterations": run["iterations"],
                "value": run["direct_certificate"]["value_residual"],
                "gradient": run["direct_certificate"]["gradient_residual"],
                "cpd": run["direct_certificate"]["cpd_eta"],
            }
            for run in candidate
        ],
    }


def transition(
    state: dict[str, Any], action: str, note: str = ""
) -> dict[str, Any]:
    result = deepcopy(state)
    if action == "accept":
        result["review_status"] = (
            "ACCEPT_COARSE4096_REJECTED_DIAGNOSTIC_ONLY"
        )
    elif action == "adjust":
        result["review_status"] = "REQUEST_ISSUE62_ADJUSTMENT"
    elif action == "reject":
        result["review_status"] = "REJECT_ISSUE62_DISPOSITION"
    else:
        raise ValueError(f"unknown review action: {action}")
    result["review_note"] = note
    return result
