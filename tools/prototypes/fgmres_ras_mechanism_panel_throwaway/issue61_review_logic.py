"""Pure decision-state logic for the Issue 61 throwaway review."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _run(result: dict[str, Any]) -> dict[str, Any]:
    runs = result.get("runs", [])
    if len(runs) != 1:
        raise ValueError("each Issue 61 probe must contain exactly one run")
    return runs[0]


def _residuals(result: dict[str, Any]) -> dict[str, float | int | str]:
    run = _run(result)
    certificate = run["bound_certificate"]
    return {
        "topology": run["topology"],
        "iterations": run["iterations"],
        "value": certificate["value_residual"],
        "gradient": certificate["gradient_residual"],
        "cpd": certificate["cpd_eta"],
        "seconds": run["elapsed_seconds"],
    }


def build_review(
    mechanism_audit: dict[str, Any],
    baseline_one: dict[str, Any],
    scaled_full: dict[str, Any],
    reversed_eight: dict[str, Any],
    coarse_one: dict[str, Any],
    coarse_eight: dict[str, Any],
    coarse_cycle: dict[str, Any],
) -> dict[str, Any]:
    baseline = _residuals(baseline_one)
    scaled = _residuals(scaled_full)
    reversed_probe = _residuals(reversed_eight)
    enriched_one = _residuals(coarse_one)
    enriched_eight = _residuals(coarse_eight)
    enriched_cycle = _residuals(coarse_cycle)
    mapping = mechanism_audit["canonical_mapping"]
    operator = mechanism_audit["operator_max_abs"]

    mapping_closed = (
        mapping["fine_value_inner_ownership_min"] == 1
        and mapping["fine_value_inner_ownership_max"] == 1
        and mapping["fine_gradient_point_inner_ownership_min"] == 1
        and mapping["fine_gradient_point_inner_ownership_max"] == 1
        and mapping["maximum_local_matrix_absolute_difference"] < 1e-13
    )
    scale_only_rejected = (
        scaled["gradient"] > baseline["gradient"] * 0.5
        and scaled["iterations"] == 100
    )
    reorder_only_rejected = (
        reversed_probe["value"] > baseline["value"]
        and reversed_probe["gradient"] > 1.0
    )
    coarse_signal = {
        "one_step_value_improvement": baseline["value"] / enriched_one["value"],
        "one_step_gradient_improvement": (
            baseline["gradient"] / enriched_one["gradient"]
        ),
        "cycle_value_improvement": baseline["value"] / enriched_cycle["value"],
        "cycle_gradient_improvement": (
            baseline["gradient"] / enriched_cycle["gradient"]
        ),
    }
    coarse_supported = (
        coarse_signal["one_step_value_improvement"] > 5.0
        and coarse_signal["one_step_gradient_improvement"] > 5.0
        and enriched_cycle["value"] < enriched_eight["value"]
        and enriched_cycle["gradient"] < enriched_eight["gradient"]
    )

    return {
        "review_status": "PENDING_HUMAN_RATIFICATION",
        "review_note": "",
        "mapping_closed": mapping_closed,
        "mapping": mapping,
        "operator": operator,
        "gradient_to_value_block_max_ratio": (
            operator["gradient_gradient"] / operator["value_value"]
        ),
        "scale_only_rejected": scale_only_rejected,
        "reorder_only_rejected": reorder_only_rejected,
        "coarse_supported": coarse_supported,
        "probes": {
            "baseline_one": baseline,
            "scaled_full": scaled,
            "reversed_eight": reversed_probe,
            "coarse_one": enriched_one,
            "coarse_eight": enriched_eight,
            "coarse_cycle": enriched_cycle,
        },
        "coarse_signal": coarse_signal,
        "recommended_decision": (
            "Freeze exactly one 4096-target enriched-coarse experiment with "
            "the accepted coarse-fine-coarse composition, robust MGS/DGKS, "
            "m=64, 100 iterations, 240 internal operator actions, complete "
            "direct actions/certificates, and distinct current/coarse4096 "
            "controls across the registered 1k/10k M1-M4 panel."
        ),
    }


def transition(
    state: dict[str, Any], action: str, note: str = ""
) -> dict[str, Any]:
    result = deepcopy(state)
    if action == "accept":
        result["review_status"] = "ACCEPT_COARSE4096_EXPERIMENT"
        result["review_note"] = note
    elif action == "adjust":
        result["review_status"] = "ADJUST_EXPERIMENT"
        result["review_note"] = note
    elif action == "reject":
        result["review_status"] = "REJECT_DIAGNOSIS"
        result["review_note"] = note
    else:
        raise ValueError(f"unknown review action: {action}")
    return result
