"""Pure decision-state derivation for the Issue 32 throwaway review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_result(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _key(run: dict[str, Any]) -> tuple[str, str, int]:
    return run["workload_id"], run["topology"], run["window"]


def build_review(
    panel: dict[str, Any], audit: dict[str, Any]
) -> dict[str, Any]:
    panel_runs = panel["runs"]
    audit_runs = audit["runs"]
    robust = {
        _key(run): run
        for run in audit_runs
        if run["orthogonalization"] == "robust-mgs-dgks"
    }
    parity = {
        _key(run): run
        for run in audit_runs
        if run["orthogonalization"] == "parity-one-pass-cgs"
    }
    pair_rows: list[dict[str, Any]] = []
    for key in sorted(robust):
        left = robust[key]
        right = parity[key]
        pair_rows.append(
            {
                "workload": key[0],
                "topology": key[1],
                "window": key[2],
                "robust_status": left["status"],
                "parity_status": right["status"],
                "robust_iterations": left["iterations"],
                "parity_iterations": right["iterations"],
                "robust_direct_pass": left["direct_certificate"]["pass"],
                "parity_direct_pass": right["direct_certificate"]["pass"],
                "direct_value_delta": abs(
                    left["direct_certificate"]["value_residual"]
                    - right["direct_certificate"]["value_residual"]
                ),
                "direct_gradient_delta": abs(
                    left["direct_certificate"]["gradient_residual"]
                    - right["direct_certificate"]["gradient_residual"]
                ),
            }
        )

    m3 = sorted(
        (
            run
            for run in panel_runs
            if run["workload_id"] == "M3-HERMITE-10K"
        ),
        key=lambda run: (
            run["bound_certificate"]["gradient_residual"],
            run["bound_certificate"]["value_residual"],
        ),
    )
    return {
        "disposition": panel["prototype_disposition"],
        "run_count": len(panel_runs),
        "workload_count": len({run["workload_id"] for run in panel_runs}),
        "factor_evidence": panel["run_scoped_factor_evidence"],
        "peak_working_set_bytes": max(
            run["process_peak_working_set_bytes"] for run in panel_runs
        ),
        "scores": panel["configuration_scores"],
        "orthogonalization_pairs": pair_rows,
        "m3_best": m3[0],
        "all_pair_iterations_equal": all(
            row["robust_iterations"] == row["parity_iterations"]
            for row in pair_rows
        ),
        "all_pair_outcomes_equal": all(
            row["robust_status"] == row["parity_status"]
            and row["robust_direct_pass"] == row["parity_direct_pass"]
            for row in pair_rows
        ),
        "recommended_decision": (
            "Accept the finding: the current candidate family has no global "
            "winner; route a mixed-gradient mechanism gap before Issue 34."
        ),
    }
