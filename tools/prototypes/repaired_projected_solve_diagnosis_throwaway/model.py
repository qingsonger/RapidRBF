"""In-memory decision model for the issue-48 throwaway prototype."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SUBSET_PATH = ROOT / "inputs" / "issue47-witness-subset.v1.json"
PLAN_PATH = ROOT / "next-experiment-plan.v1.json"
EXPECTED_ORDINALS = (0, 36, 69, 72, 106, 150)
FAMILIES = ("operational", "constraint", "dynamic-range")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    subset = json.loads(SUBSET_PATH.read_text(encoding="utf-8"))
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    validate_inputs(subset, plan)
    return subset, plan


def validate_inputs(subset: dict[str, Any], plan: dict[str, Any]) -> None:
    claimed = subset["payload_sha256"]
    unhashed = {key: value for key, value in subset.items() if key != "payload_sha256"}
    if canonical_sha256(unhashed) != claimed:
        raise ValueError("committed witness subset payload SHA-256 differs")
    if subset["cohort"]["disposition"] != "NOT_ADMITTED_DIAGNOSTIC_ONLY":
        raise ValueError("unexpected issue-47 disposition")
    if subset["cohort"]["certified_references"] != 537:
        raise ValueError("issue-47 certified-reference count differs")
    if subset["cohort"]["indeterminate_references"] != 0:
        raise ValueError("issue-47 contains an indeterminate reference")
    if subset["cohort"]["candidate_inputs_observed_by_reference"]:
        raise ValueError("candidate-independent reference observed candidate inputs")
    subset_ordinals = tuple(item["ordinal"] for item in subset["witnesses"])
    plan_ordinals = tuple(item["ordinal"] for item in plan["witness_corpus"])
    if subset_ordinals != EXPECTED_ORDINALS or plan_ordinals != EXPECTED_ORDINALS:
        raise ValueError("witness ordinal set or order differs")
    subset_by_ordinal = {item["ordinal"]: item for item in subset["witnesses"]}
    for planned in plan["witness_corpus"]:
        observed = subset_by_ordinal[planned["ordinal"]]
        metadata = observed["metadata"]
        if planned["factor_source_id"] != metadata["factor_source_id"]:
            raise ValueError("planned factor-source identity differs")
        if planned["source_sha256"] != metadata["sha256"]:
            raise ValueError("planned source SHA-256 differs")
        if planned["dimension"] != metadata["dimension"]:
            raise ValueError("planned source dimension differs")
        if planned["expected_rank"] != metadata["expected_rank"]:
            raise ValueError("planned exact-rank authority differs")
        reference_rhs = {
            item["family"]: item["rhs_sha256"]
            for item in observed["reference_entry"]["rhs"]
        }
        if planned["rhs_sha256"] != reference_rhs:
            raise ValueError("planned RHS identity differs")
    authorities = plan["authorities"]
    if (
        authorities["issue47_reference_manifest_sha256"]
        != subset["cohort"]["reference_manifest_sha256"]
    ):
        raise ValueError("planned reference manifest identity differs")
    if (
        authorities["unchanged_candidate_binding_sha256"]
        != subset["cohort"]["candidate_binding_sha256"]
    ):
        raise ValueError("planned candidate binding identity differs")


def family_summary(witness: dict[str, Any], family: str) -> dict[str, Any]:
    judgments = [
        next(
            item
            for item in observation["solution_judgments"]
            if item["family"] == family
        )
        for observation in witness["lane_observations"]
    ]
    reload_judgments = [
        next(
            item
            for item in observation["reload_solution_judgments"]
            if item["family"] == family
        )
        for observation in witness["lane_observations"]
    ]
    return {
        "family": family,
        "pre_pack_statuses": sorted({item["status"] for item in judgments}),
        "post_reload_statuses": sorted(
            {item["status"] for item in reload_judgments}
        ),
        "minimum_threshold_ratio_lower": min(
            item["threshold_ratio_lower"] for item in judgments
        ),
        "maximum_threshold_ratio_upper": max(
            item["threshold_ratio_upper"] for item in judgments
        ),
        "minimum_relative_distance_lower": min(
            item["relative_distance_lower"] for item in judgments
        ),
        "maximum_relative_distance_upper": max(
            item["relative_distance_upper"] for item in judgments
        ),
    }


def route_summary(witness: dict[str, Any]) -> dict[str, Any] | None:
    comparison = witness.get("accepted_issue45_route_comparison")
    if comparison is None:
        return None
    threshold = comparison["solution_threshold"]
    routes = {}
    for name, route in comparison["routes"].items():
        history = route["refinement_correction_relative_inf_history"]
        first_correction = history[0]
        later_correction_upper_sum = sum(history[1:])
        raw_to_refined_lower_bound = max(
            0.0, first_correction - later_correction_upper_sum
        )
        routes[name] = {
            "first_refinement_correction_relative_inf": first_correction,
            "first_correction_to_threshold_ratio": first_correction / threshold,
            "later_correction_upper_sum": later_correction_upper_sum,
            "raw_to_refined_lower_bound": raw_to_refined_lower_bound,
            "raw_to_refined_lower_bound_to_threshold_ratio": (
                raw_to_refined_lower_bound / threshold
            ),
            "refinement_steps": route["refinement_steps"],
            "double_double_refined_backward_error": route[
                "double_double_refined_maximum_backward_error"
            ],
        }
    return {
        "directional_forward_amplification": comparison[
            "directional_forward_amplification"
        ],
        "lblt_full_pivot_lu_relative_agreement": comparison[
            "lblt_full_pivot_lu_relative_agreement"
        ],
        "solution_threshold": threshold,
        "routes": routes,
    }


def analyze() -> dict[str, Any]:
    subset, plan = load_inputs()
    witnesses = []
    current_failures_per_lane = 0
    all_status_vectors_invariant = True
    all_factor_health_side_gates_pass = True

    for witness in subset["witnesses"]:
        families = [
            family_summary(witness, family) for family in FAMILIES
        ]
        lane_count = len(witness["lane_observations"])
        failing_families = [
            item["family"]
            for item in families
            if item["pre_pack_statuses"] == ["FAIL"]
        ]
        current_failures_per_lane += len(failing_families)
        max_backward_ratio = max(
            observation["maximum_backward_error"]
            / observation["backward_threshold"]
            for observation in witness["lane_observations"]
        )
        max_reconstruction_ratio = max(
            observation["reconstruction_relative_inf"]
            / observation["reconstruction_threshold"]
            for observation in witness["lane_observations"]
        )
        side_gates_pass = (
            max_backward_ratio < 1.0
            and max_reconstruction_ratio < 1.0
            and all(
                observation["pre_post_solutions_bit_exact"]
                for observation in witness["lane_observations"]
            )
        )
        all_status_vectors_invariant &= witness[
            "status_vector_identical_across_all_12_observations"
        ]
        all_factor_health_side_gates_pass &= side_gates_pass
        witnesses.append(
            {
                "ordinal": witness["ordinal"],
                "category": witness["category"],
                "factor_source_id": witness["metadata"]["factor_source_id"],
                "workload_id": witness["metadata"]["workload_id"],
                "dimension": witness["metadata"]["dimension"],
                "expected_rank": witness["metadata"]["expected_rank"],
                "factorization": witness["metadata"]["factorization"],
                "lane_observations": lane_count,
                "status_vector_invariant": witness[
                    "status_vector_identical_across_all_12_observations"
                ],
                "failing_families": failing_families,
                "maximum_backward_gate_fraction": max_backward_ratio,
                "maximum_reconstruction_gate_fraction": (
                    max_reconstruction_ratio
                ),
                "pre_post_bit_exact": all(
                    observation["pre_post_solutions_bit_exact"]
                    for observation in witness["lane_observations"]
                ),
                "families": families,
                "accepted_route_comparison": route_summary(witness),
            }
        )

    current_failures = (
        current_failures_per_lane
        * plan["execution_matrix"]["target_profile_observations"]
        * 2
    )
    ordinal106 = next(item for item in witnesses if item["ordinal"] == 106)
    ordinal69 = next(item for item in witnesses if item["ordinal"] == 69)
    ordinal150 = next(item for item in witnesses if item["ordinal"] == 150)

    raw_alternatives_fail_extremes = True
    for witness in (ordinal69, ordinal150):
        comparison = witness["accepted_route_comparison"]
        assert comparison is not None
        for route_name in (
            "full_pivot_lu",
            "symmetric_max_equilibrated_lblt",
        ):
            raw_alternatives_fail_extremes &= (
                comparison["routes"][route_name][
                    "raw_to_refined_lower_bound_to_threshold_ratio"
                ]
                > 1.0
            )

    result = {
        "schema": "RapidRBF/RepairedProjectedSolveDiagnosis/v1",
        "disposition": "NEXT_DENSE_FACTOR_EXPERIMENT_FROZEN",
        "input_identities": {
            "witness_subset_payload_sha256": subset["payload_sha256"],
            "next_experiment_plan_file_sha256": file_sha256(PLAN_PATH),
            "issue47_archive_sha256": subset["derivation"][
                "issue47_archive_sha256"
            ],
            "issue47_reference_manifest_sha256": subset["cohort"][
                "reference_manifest_sha256"
            ],
            "unchanged_candidate_binding_sha256": subset["cohort"][
                "candidate_binding_sha256"
            ],
        },
        "feedback_loop": {
            "command": (
                "python tools/prototypes/"
                "repaired_projected_solve_diagnosis_throwaway/run.py "
                "--require-current-candidate-admitted"
            ),
            "expected_exit_code": 1,
            "selected_witnesses": len(witnesses),
            "target_profile_observations": plan["execution_matrix"][
                "target_profile_observations"
            ],
            "pre_and_post_reference_solution_failures": current_failures,
            "exact_symptom": (
                "candidate-owned frozen-system forward-solution FAIL while "
                "reconstruction, reduced backward error, and pre/post "
                "bit-exactness pass"
            ),
        },
        "proven_mechanism": {
            "statement": (
                "The unchanged binary64 projected-B Bunch-Kaufman route is "
                "backward stable and reconstructs its frozen matrix, but its "
                "forward solve error is amplified beyond the frozen "
                "candidate-independent threshold along particular RHS "
                "directions. Problem conditioning is necessary context, not "
                "a sufficient per-factor verdict: ordinal 106 uses one "
                "full-rank factor and fails only the operational RHS."
            ),
            "all_12_observations_share_status_vectors": (
                all_status_vectors_invariant
            ),
            "all_selected_side_gates_pass": (
                all_factor_health_side_gates_pass
            ),
            "ordinal_106_failing_families": ordinal106["failing_families"],
            "raw_full_pivot_and_equilibration_fail_extremes": (
                raw_alternatives_fail_extremes
            ),
            "accepted_issue45_refinement_routes_converge": True,
        },
        "hypotheses": [
            {
                "rank": 1,
                "name": (
                    "condition- and RHS-amplified binary64 forward error; "
                    "owned double-double refinement closes it"
                ),
                "status": "SUPPORTED_ROUTE_WITH_TWO_UNTESTED_BOUNDARIES",
                "prediction": (
                    "The selected refined route passes all 18 certified "
                    "witness RHS on every target/profile while retaining the "
                    "unchanged factor identity and side gates."
                ),
                "remaining_uncertainty": (
                    "Accepted route-comparison evidence covers ordinals "
                    "0/69/72/150, but not the M2 1k boundary 36 or the "
                    "partial-family exception 106, nor the new resource and "
                    "mid-refinement cancellation boundary."
                ),
            },
            {
                "rank": 2,
                "name": "pivot or factorization choice alone",
                "status": "FALSIFIED_AS_SOLE_MECHANISM",
                "prediction": (
                    "Raw full-pivot LU would place the 69 and 150 correction "
                    "inside the unchanged threshold."
                ),
                "observation": (
                    "The first correction minus the sum of every later "
                    "correction remains above the threshold on both accepted "
                    "extremes."
                ),
            },
            {
                "rank": 3,
                "name": "symmetric max equilibration alone",
                "status": "FALSIFIED_AS_SOLE_MECHANISM",
                "prediction": (
                    "Raw equilibrated Bunch-Kaufman would place the 69 and "
                    "150 correction inside the unchanged threshold."
                ),
                "observation": (
                    "The first correction minus the sum of every later "
                    "correction remains above the threshold on both accepted "
                    "extremes."
                ),
            },
            {
                "rank": 4,
                "name": "rank or frozen-system authority defect",
                "status": "FALSIFIED_ON_THE_SELECTED_BOUNDARY",
                "prediction": (
                    "Independent routes or the directed-rounding references "
                    "would fail to establish unique full-rank solutions."
                ),
                "observation": (
                    "All six plans assert exact full rank; issue 47 certifies "
                    "537/537 references with zero INDETERMINATE, and accepted "
                    "issue-45 independent routes agree far below the gate."
                ),
            },
            {
                "rank": 5,
                "name": "platform, threads, serialization, or publication",
                "status": "FALSIFIED",
                "prediction": (
                    "The source/family failure vector or pre/post solution "
                    "bits would change across targets, profiles, or reload."
                ),
                "observation": (
                    "All twelve observations share the same vector and every "
                    "selected pre/post solution is bit exact within its lane."
                ),
            },
        ],
        "witnesses": witnesses,
        "next_experiment": {
            "name": plan["selected_candidate_boundary"]["name"],
            "plan_schema": plan["schema"],
            "plan_file_sha256": file_sha256(PLAN_PATH),
            "sources": len(plan["witness_corpus"]),
            "rhs_families": plan["execution_matrix"][
                "rhs_families_per_source"
            ],
            "target_profile_observations": plan["execution_matrix"][
                "target_profile_observations"
            ],
            "candidate_source_observations": plan["execution_matrix"][
                "candidate_source_observations"
            ],
            "dispositions": list(plan["dispositions"]),
        },
        "scope": plan["scope"],
    }
    return result
