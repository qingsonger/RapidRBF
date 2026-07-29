"""Judge one frozen repaired-factor four-target requalification cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ADMITTED = "ADMITTED_FOR_MECHANISM_PANEL"
NOT_ADMITTED = "NOT_ADMITTED_DIAGNOSTIC_ONLY"
INVALID = "INVALID_UNJUDGED"
AUTHORITY_SHA256 = (
    "c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6"
)
REQUALIFICATION_PLAN_SHA256 = (
    "3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829"
)
ISSUE_41_PLAN_SHA256 = (
    "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce"
)
BINDING_SHA256 = (
    "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
)
PROFILE_SHA256 = (
    "00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3"
)
REQUIRED_PROFILES = {1: 12, 2: 12, 8: 16}
RHS_FAMILIES = [
    "operational",
    "constraint",
    "dynamic-range",
]
ALLOWED_JUDGMENTS = {"PASS", "FAIL", "INDETERMINATE"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def invalid_if(condition: bool, invalid: list[str], message: str) -> None:
    if condition:
        invalid.append(message)


def coordinate(
    *,
    lane_id: str,
    target: str,
    workers: int,
    gate: str,
    status: str = "FAIL",
    source: dict[str, Any] | None = None,
    stage: str | None = None,
    rhs_family: str | None = None,
    observed: Any = None,
    limit: Any = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "lane_id": lane_id,
        "target": target,
        "workers": workers,
        "gate": gate,
        "status": status,
    }
    if source is not None:
        item.update(
            {
                "ordinal": source.get("ordinal"),
                "factor_source_id": source.get("factor_source_id"),
                "workload_id": source.get("workload_id"),
                "block_id": source.get("block_id"),
                "role": source.get("role"),
            }
        )
    if stage is not None:
        item["stage"] = stage
    if rhs_family is not None:
        item["rhs_family"] = rhs_family
    if observed is not None:
        item["observed"] = observed
    if limit is not None:
        item["limit"] = limit
    return item


def check_judgments(
    judgments: Any,
    *,
    lane_id: str,
    target: str,
    workers: int,
    source: dict[str, Any],
    stage: str,
    invalid: list[str],
    failures: list[dict[str, Any]],
) -> None:
    prefix = f"{lane_id}/{workers}/source-{source.get('ordinal')}/{stage}"
    if not isinstance(judgments, list) or len(judgments) != 3:
        invalid.append(f"{prefix}: repaired reference judgment closure differs")
        return
    families = [item.get("family") for item in judgments]
    if families != RHS_FAMILIES:
        invalid.append(f"{prefix}: repaired RHS family order differs")
        return
    for judgment in judgments:
        status = judgment.get("status")
        if status not in ALLOWED_JUDGMENTS:
            invalid.append(
                f"{prefix}/{judgment.get('family')}: forbidden judgment {status!r}"
            )
            continue
        if not isinstance(judgment.get("rhs_sha256"), str):
            invalid.append(
                f"{prefix}/{judgment.get('family')}: missing RHS identity"
            )
            continue
        if status != "PASS":
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=target,
                    workers=workers,
                    source=source,
                    gate="reference-solution",
                    stage=stage,
                    rhs_family=judgment["family"],
                    status=status,
                    observed={
                        "distance_lower_exact_hex": judgment.get(
                            "distance_lower_exact_hex"
                        ),
                        "distance_upper_exact_hex": judgment.get(
                            "distance_upper_exact_hex"
                        ),
                        "non_finite_candidate": judgment.get(
                            "non_finite_candidate"
                        ),
                    },
                    limit={
                        "scale_lower_mpfr_hex": judgment.get(
                            "scale_lower_mpfr_hex"
                        ),
                        "scale_upper_mpfr_hex": judgment.get(
                            "scale_upper_mpfr_hex"
                        ),
                        "solution_threshold_mpfr_hex": judgment.get(
                            "solution_threshold_mpfr_hex"
                        ),
                        "pass_limit_exact_hex": judgment.get(
                            "pass_limit_exact_hex"
                        ),
                        "fail_limit_exact_hex": judgment.get(
                            "fail_limit_exact_hex"
                        ),
                    },
                )
            )


def check_candidate(
    candidate: dict[str, Any],
    *,
    lane_id: str,
    target: str,
    workers: int,
    maximum_live_threads: int,
    reference_sha256: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    prefix = f"{lane_id}/{workers}"
    invalid: list[str] = []
    failures: list[dict[str, Any]] = []
    invalid_if(
        candidate.get("schema")
        != "RapidRBF/RepairedProjectedFactorRequalificationLaneObservation/v1",
        invalid,
        f"{prefix}: candidate schema differs",
    )
    invalid_if(
        candidate.get("lane_id") != lane_id or candidate.get("target") != target,
        invalid,
        f"{prefix}: candidate lane or target identity differs",
    )
    invalid_if(
        candidate.get("diagnostic_subset") is not False,
        invalid,
        f"{prefix}: diagnostic subset entered the full cohort",
    )
    invalid_if(
        candidate.get("disposition") not in {ADMITTED, NOT_ADMITTED},
        invalid,
        f"{prefix}: candidate disposition is forbidden",
    )
    reference = candidate.get("reference_manifest", {})
    invalid_if(
        reference.get("sha256") != reference_sha256
        or reference.get("authority_profile_sha256") != AUTHORITY_SHA256
        or reference.get("requalification_plan_sha256")
        != REQUALIFICATION_PLAN_SHA256
        or reference.get("candidate_inputs_observed") is not False,
        invalid,
        f"{prefix}: candidate reference identity or independence differs",
    )
    binding = candidate.get("candidate_binding", {})
    invalid_if(
        binding.get("binding_sha256") != BINDING_SHA256
        or binding.get("profile_sha256") != PROFILE_SHA256
        or binding.get("parallelism") != "Par::Seq",
        invalid,
        f"{prefix}: candidate binding identity differs",
    )
    invalid_if(
        candidate.get("plan", {}).get("file_sha256") != ISSUE_41_PLAN_SHA256,
        invalid,
        f"{prefix}: issue-41 plan identity differs",
    )
    lane = candidate.get("lane", {})
    invalid_if(
        lane.get("configured_workers") != workers
        or lane.get("maximum_live_threads_grant") != maximum_live_threads
        or lane.get("backend_parallelism") != "Par::Seq"
        or lane.get("nested_automatic_pool") is not False,
        invalid,
        f"{prefix}: lane controller identity differs",
    )
    effective_workers = lane.get("effective_worker_high_water")
    if (
        not isinstance(effective_workers, int)
        or effective_workers <= 0
        or effective_workers > workers
    ):
        failures.append(
            coordinate(
                lane_id=lane_id,
                target=target,
                workers=workers,
                gate="effective-worker-high-water",
                observed=effective_workers,
                limit=workers,
            )
        )

    sources = candidate.get("factor_sources")
    if not isinstance(sources, list):
        invalid.append(f"{prefix}: factor source observations are absent")
        sources = []
    ordinals = [source.get("ordinal") for source in sources]
    if ordinals != list(range(216)):
        failures.append(
            coordinate(
                lane_id=lane_id,
                target=target,
                workers=workers,
                gate="logical-source-closure",
                observed=ordinals,
                limit=list(range(216)),
            )
        )
    counts = candidate.get("counts", {})
    passed = sum(source.get("status") == "PASS" for source in sources)
    failed = sum(source.get("status") != "PASS" for source in sources)
    invalid_if(
        counts.get("planned_factor_sources") != 216
        or counts.get("observed_factor_sources") != len(sources)
        or counts.get("passed_factor_sources") != passed
        or counts.get("failed_factor_sources") != failed,
        invalid,
        f"{prefix}: source counts are internally inconsistent",
    )
    for count_gate, expected in (
        ("qualified_factor_access_publications", 216),
        ("solved_correction_publications", 216),
        ("run_recompute_budget_initial", 216),
        ("run_recompute_budget_consumed", 0),
        ("run_scoped_recompute_recipes", 0),
    ):
        if counts.get(count_gate) != expected:
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=target,
                    workers=workers,
                    gate=count_gate.replace("_", "-"),
                    observed=counts.get(count_gate),
                    limit=expected,
                )
            )

    for source in sources:
        ordinal = source.get("ordinal")
        if not isinstance(ordinal, int):
            invalid.append(f"{prefix}: source without integer ordinal")
            continue
        for metric, threshold, gate in (
            (
                "reconstruction_relative_inf",
                "reconstruction_threshold",
                "factor-reconstruction",
            ),
            ("maximum_backward_error", "backward_threshold", "backward-error"),
        ):
            observed = source.get(metric)
            limit = source.get(threshold)
            if (
                not isinstance(observed, (int, float))
                or not isinstance(limit, (int, float))
            ):
                invalid.append(f"{prefix}/source-{ordinal}: {gate} fields differ")
            elif observed > limit:
                failures.append(
                    coordinate(
                        lane_id=lane_id,
                        target=target,
                        workers=workers,
                        source=source,
                        gate=gate,
                        observed=observed,
                        limit=limit,
                    )
                )
        check_judgments(
            source.get("solution_judgments"),
            lane_id=lane_id,
            target=target,
            workers=workers,
            source=source,
            stage="pre-pack",
            invalid=invalid,
            failures=failures,
        )
        check_judgments(
            source.get("reload_solution_judgments"),
            lane_id=lane_id,
            target=target,
            workers=workers,
            source=source,
            stage="post-reload",
            invalid=invalid,
            failures=failures,
        )
        if source.get("pre_post_solutions_bit_exact") is not True:
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=target,
                    workers=workers,
                    source=source,
                    gate="pre-post-solution-bits",
                    observed=source.get("pre_post_solutions_bit_exact"),
                    limit=True,
                )
            )
        pack = source.get("pack", {})
        if (
            pack.get("positive_reload") is not True
            or pack.get("removed_after_reload") is not True
        ):
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=target,
                    workers=workers,
                    source=source,
                    gate="durable-private-pack-reload",
                    observed={
                        "positive_reload": pack.get("positive_reload"),
                        "removed_after_reload": pack.get("removed_after_reload"),
                    },
                    limit={
                        "positive_reload": True,
                        "removed_after_reload": True,
                    },
                )
            )
        n_minus_one = source.get("n_minus_one", {})
        if (
            n_minus_one.get("status") != "PASS"
            or n_minus_one.get("operation_called") is not False
            or n_minus_one.get("metrics", {}).get("backend_entries") != 0
        ):
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=target,
                    workers=workers,
                    source=source,
                    gate="n-minus-one-transient-denial",
                    observed=n_minus_one,
                    limit="PASS before operation/backend entry",
                )
            )
        for metrics_name in ("execution_metrics", "reload_metrics"):
            metrics = source.get(metrics_name, {})
            if (
                metrics.get("transient_residue_bytes") != 0
                or metrics.get("outer_compute_permits_live") != 0
            ):
                failures.append(
                    coordinate(
                        lane_id=lane_id,
                        target=target,
                        workers=workers,
                        source=source,
                        stage=metrics_name.replace("_metrics", ""),
                        gate="resource-residue",
                        observed={
                            "transient_residue_bytes": metrics.get(
                                "transient_residue_bytes"
                            ),
                            "outer_compute_permits_live": metrics.get(
                                "outer_compute_permits_live"
                            ),
                        },
                        limit={
                            "transient_residue_bytes": 0,
                            "outer_compute_permits_live": 0,
                        },
                    )
                )

    controls = candidate.get("controls", {})
    cancellation = controls.get("cancellation", {})
    negative = controls.get("negative_reload", {})
    controls_pass = (
        controls.get("exact_n_minus_one_observations") == 216
        and cancellation.get("status") == "PASS"
        and cancellation.get("mid_factor", {}).get("cancelled") is True
        and cancellation.get("mid_factor", {}).get("backend_entered") is True
        and cancellation.get("mid_factor", {}).get("prior_factor_preserved")
        is True
        and cancellation.get("mid_factor", {}).get("failed_publications") == 0
        and cancellation.get("mid_solve", {}).get("cancelled") is True
        and cancellation.get("mid_solve", {}).get("backend_entered") is True
        and cancellation.get("mid_solve", {}).get(
            "prior_solved_correction_preserved"
        )
        is True
        and cancellation.get("mid_solve", {}).get("failed_publications") == 0
        and negative.get("status") == "PASS"
        and negative.get("backend_entries") == 0
        and all(
            negative.get(name) is True
            for name in (
                "truncated_pack",
                "corrupt_pack",
                "wrong_source",
                "wrong_profile",
                "metadata_mismatch",
            )
        )
    )
    if not controls_pass:
        failures.append(
            coordinate(
                lane_id=lane_id,
                target=target,
                workers=workers,
                gate="negative-and-cancellation-controls",
                observed=controls,
                limit="all frozen controls PASS",
            )
        )
    scratch = candidate.get("scratch", {})
    if (
        scratch.get("cleanup_pass") is not True
        or scratch.get("live_residue_bytes") != 0
        or scratch.get("residue_files") != []
    ):
        failures.append(
            coordinate(
                lane_id=lane_id,
                target=target,
                workers=workers,
                gate="scratch-cleanup",
                observed=scratch,
                limit={
                    "cleanup_pass": True,
                    "live_residue_bytes": 0,
                    "residue_files": [],
                },
            )
        )
    if candidate.get("disposition") == NOT_ADMITTED and not failures:
        failures.append(
            coordinate(
                lane_id=lane_id,
                target=target,
                workers=workers,
                gate="candidate-disposition-without-specific-gate",
                observed=NOT_ADMITTED,
                limit=ADMITTED,
            )
        )
    if candidate.get("disposition") == ADMITTED and failures:
        invalid.append(f"{prefix}: admitted disposition contradicts failed gates")
    return invalid, failures


def check_target(
    path: Path,
    evidence: dict[str, Any],
    *,
    contract_sha256: str,
    expected_target: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    lane_id = evidence.get("lane_id", path.parent.name)
    invalid: list[str] = []
    failures: list[dict[str, Any]] = []
    invalid_if(
        evidence.get("schema")
        != "RapidRBF/RepairedProjectedFactorTargetEvidence/v1",
        invalid,
        f"{lane_id}: target evidence schema differs",
    )
    invalid_if(
        evidence.get("target") != expected_target,
        invalid,
        f"{lane_id}: native target differs",
    )
    invalid_if(
        evidence.get("disposition") not in {ADMITTED, NOT_ADMITTED},
        invalid,
        f"{lane_id}: target disposition is forbidden",
    )
    invalid_if(
        evidence.get("execution_contract", {}).get("sha256") != contract_sha256,
        invalid,
        f"{lane_id}: execution contract differs",
    )
    authority = evidence.get("authority", {})
    invalid_if(
        authority.get("repaired_authority_sha256") != AUTHORITY_SHA256
        or authority.get("requalification_plan_sha256")
        != REQUALIFICATION_PLAN_SHA256
        or authority.get("plan_file_sha256") != ISSUE_41_PLAN_SHA256
        or authority.get("binding_sha256") != BINDING_SHA256,
        invalid,
        f"{lane_id}: frozen authority identity differs",
    )
    reference = evidence.get("reference_manifest", {})
    invalid_if(
        reference.get("schema") != "RapidRBF/ProjectedFactorReferenceManifest/v1"
        or reference.get("disposition") != "CERTIFIED_REFERENCE"
        or reference.get("candidate_inputs_observed") is not False
        or reference.get("unique_matrix_payloads") != 179
        or reference.get("certified_references") != 537,
        invalid,
        f"{lane_id}: certified reference identity differs",
    )
    reference_sha256 = reference.get("sha256")
    invalid_if(
        not isinstance(reference_sha256, str),
        invalid,
        f"{lane_id}: reference manifest sha256 is absent",
    )
    lane_witness = evidence.get("lane_witness", {})
    invalid_if(
        lane_witness.get("qualification") != "PASS"
        or lane_witness.get("lane", {}).get("lane_id") != lane_id
        or lane_witness.get("lane", {}).get("target") != expected_target,
        invalid,
        f"{lane_id}: lane witness differs",
    )
    observations = evidence.get("lane_observations", [])
    invalid_if(
        not isinstance(observations, list)
        or len(observations) != len(REQUIRED_PROFILES)
        or {item.get("workers") for item in observations}
        != set(REQUIRED_PROFILES),
        invalid,
        f"{lane_id}: required lane profile closure differs",
    )
    if not isinstance(observations, list):
        observations = []
    for observation in observations:
        workers = observation.get("workers")
        if workers not in REQUIRED_PROFILES:
            continue
        maximum_live_threads = REQUIRED_PROFILES[workers]
        entry_name = observation.get("candidate_entry_file")
        entry_path = path.parent / entry_name if isinstance(entry_name, str) else None
        if (
            entry_path is None
            or not entry_path.is_file()
            or sha256_file(entry_path)
            != observation.get("candidate_entry_file_sha256")
        ):
            invalid.append(
                f"{lane_id}/{workers}: candidate-entry marker identity differs"
            )
            continue
        try:
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            invalid.append(
                f"{lane_id}/{workers}: candidate-entry marker unreadable: {error}"
            )
            continue
        if (
            entry.get("schema")
            != "RapidRBF/RepairedProjectedFactorCandidateEntry/v1"
            or entry.get("lane_id") != lane_id
            or entry.get("target") != expected_target
            or entry.get("workers") != workers
            or entry.get("maximum_live_threads") != maximum_live_threads
            or entry.get("candidate_binding_sha256") != BINDING_SHA256
            or entry.get("authority_profile_sha256") != AUTHORITY_SHA256
            or entry.get("requalification_plan_sha256")
            != REQUALIFICATION_PLAN_SHA256
            or entry.get("issue_41_plan_sha256") != ISSUE_41_PLAN_SHA256
            or entry.get("reference_manifest_sha256") != reference_sha256
        ):
            invalid.append(
                f"{lane_id}/{workers}: candidate-entry marker fields differ"
            )
            continue
        candidate_failure = observation.get("candidate_failure")
        if candidate_failure is not None:
            if (
                candidate_failure.get("classification")
                != "candidate-owned-after-entry"
                or candidate_failure.get("gate")
                not in {"candidate-crash", "candidate-timeout"}
                or observation.get("candidate_disposition") != NOT_ADMITTED
                or observation.get("candidate_file") is not None
                or observation.get("candidate_file_sha256") is not None
            ):
                invalid.append(
                    f"{lane_id}/{workers}: candidate failure record differs"
                )
                continue
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=expected_target,
                    workers=workers,
                    gate=candidate_failure["gate"],
                    observed={
                        "returncode": candidate_failure.get("returncode"),
                        "scratch_residue_files": candidate_failure.get(
                            "scratch_residue_files"
                        ),
                    },
                    limit="candidate completes and emits a lane observation",
                )
            )
            thread = observation.get("controller_threads", {})
            if thread.get("sampling_errors") != []:
                invalid.append(
                    f"{lane_id}/{workers}: external thread sampling failed"
                )
            elif (
                thread.get("maximum_live_threads_grant")
                != maximum_live_threads
                or thread.get(
                    "maximum_live_threads", maximum_live_threads + 1
                )
                > maximum_live_threads
            ):
                failures.append(
                    coordinate(
                        lane_id=lane_id,
                        target=expected_target,
                        workers=workers,
                        gate="external-live-thread-high-water",
                        observed=thread,
                        limit=maximum_live_threads,
                    )
                )
            continue
        candidate_path = path.parent / observation.get("candidate_file", "")
        if not candidate_path.is_file():
            invalid.append(f"{lane_id}/{workers}: candidate observation is absent")
            continue
        if sha256_file(candidate_path) != observation.get("candidate_file_sha256"):
            invalid.append(f"{lane_id}/{workers}: candidate file identity differs")
            continue
        try:
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            invalid.append(f"{lane_id}/{workers}: candidate JSON unreadable: {error}")
            continue
        candidate_invalid, candidate_failures = check_candidate(
            candidate,
            lane_id=lane_id,
            target=expected_target,
            workers=workers,
            maximum_live_threads=maximum_live_threads,
            reference_sha256=reference_sha256,
        )
        invalid.extend(candidate_invalid)
        failures.extend(candidate_failures)
        thread = observation.get("controller_threads", {})
        if (
            thread.get("pass") is not True
            or thread.get("samples", 0) <= 0
            or thread.get("sampling_errors") != []
            or thread.get("maximum_live_threads_grant") != maximum_live_threads
            or thread.get("maximum_live_threads", maximum_live_threads + 1)
            > maximum_live_threads
        ):
            failures.append(
                coordinate(
                    lane_id=lane_id,
                    target=expected_target,
                    workers=workers,
                    gate="external-live-thread-high-water",
                    observed=thread,
                    limit=maximum_live_threads,
                )
            )
    if evidence.get("disposition") == ADMITTED and failures:
        invalid.append(f"{lane_id}: admitted target disposition contradicts failures")
    return invalid, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract_bytes = args.contract.read_bytes()
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest()
    contract = json.loads(contract_bytes)
    plan_path = args.contract.parent / "factor-qualification-plan.v1.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    required = {target["lane_id"]: target["target"] for target in plan["targets"]}
    invalid: list[str] = []
    failures: list[dict[str, Any]] = []
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(args.evidence_root.rglob("target-observation.json")):
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            invalid.append(f"{path}: target JSON unreadable: {error}")
            continue
        lane_id = evidence.get("lane_id")
        if lane_id not in required:
            invalid.append(f"unexpected target evidence for {lane_id}")
            continue
        if lane_id in records:
            invalid.append(f"duplicate target evidence for {lane_id}")
            continue
        records[lane_id] = (path, evidence)
        target_invalid, target_failures = check_target(
            path,
            evidence,
            contract_sha256=contract_sha256,
            expected_target=required[lane_id],
        )
        invalid.extend(target_invalid)
        failures.extend(target_failures)

    for lane_id in required:
        if lane_id not in records:
            invalid.append(f"missing target evidence for {lane_id}")

    cohort_keys = {
        (
            evidence.get("github", {}).get("run_id"),
            evidence.get("github", {}).get("run_attempt"),
            evidence.get("github", {}).get("sha"),
            evidence.get("authority", {}).get("requalification_plan_sha256"),
            evidence.get("reference_manifest", {}).get("sha256"),
        )
        for _, evidence in records.values()
    }
    if len(cohort_keys) != 1 or any(None in key for key in cohort_keys):
        invalid.append(
            "target evidence does not share one populated "
            "run/attempt/sha/requalification-plan/reference key"
        )
    transport_ids = {
        (
            evidence.get("transport", {}).get("asset", {}).get("sha256"),
            evidence.get("transport", {}).get("asset", {}).get("bytes"),
        )
        for _, evidence in records.values()
    }
    if len(transport_ids) != 1 or any(None in key for key in transport_ids):
        invalid.append("target evidence does not share one populated transport asset")

    dispositions = {
        lane_id: evidence.get("disposition")
        for lane_id, (_, evidence) in records.items()
    }
    if invalid:
        disposition = INVALID
    elif failures:
        disposition = NOT_ADMITTED
    else:
        disposition = ADMITTED

    args.output.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema": "RapidRBF/RepairedProjectedFactorRequalificationCohort/v1",
        "execution_contract": {
            "contract_id": contract["contract_id"],
            "sha256": contract_sha256,
        },
        "frozen_authority": {
            "authority_profile_sha256": AUTHORITY_SHA256,
            "requalification_plan_sha256": REQUALIFICATION_PLAN_SHA256,
            "issue_41_plan_sha256": ISSUE_41_PLAN_SHA256,
            "candidate_binding_sha256": BINDING_SHA256,
        },
        "factor_qualification_plan": {
            "plan_id": plan["plan_id"],
            "sha256": sha256_file(plan_path),
        },
        "required_targets": required,
        "target_dispositions": dispositions,
        "cohort_keys": [list(key) for key in sorted(cohort_keys, key=str)],
        "transport_ids": [list(key) for key in sorted(transport_ids, key=str)],
        "invalidity_reasons": invalid,
        "nonpassing_coordinates": failures,
        "disposition": disposition,
        "target_evidence": {
            lane_id: {
                "sha256": sha256_file(records[lane_id][0]),
                "target": records[lane_id][1].get("target"),
                "native_executable": records[lane_id][1].get(
                    "native_executable"
                ),
                "lane_profiles": [
                    {
                        "workers": item.get("workers"),
                        "candidate_file_sha256": item.get(
                            "candidate_file_sha256"
                        ),
                        "controller_threads": item.get("controller_threads"),
                    }
                    for item in records[lane_id][1].get("lane_observations", [])
                ],
            }
            for lane_id in required
            if lane_id in records
        },
    }
    summary_path = args.output / "cohort-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output / "cohort-summary.json.sha256").write_text(
        f"{sha256_file(summary_path)}  cohort-summary.json\n",
        encoding="utf-8",
    )
    lines = [
        "# Repaired projected-factor full-corpus requalification",
        "",
        f"Disposition: `{disposition}`",
        "",
        "| Target lane | Native target | Disposition | Profiles |",
        "| --- | --- | --- | --- |",
    ]
    for lane_id, target in required.items():
        if lane_id in records:
            evidence = records[lane_id][1]
            profiles = ", ".join(
                f"{item.get('workers')}/{item.get('maximum_live_threads')}"
                for item in evidence.get("lane_observations", [])
            )
            lines.append(
                f"| `{lane_id}` | `{target}` | "
                f"`{evidence.get('disposition')}` | `{profiles}` |"
            )
        else:
            lines.append(f"| `{lane_id}` | `{target}` | `{INVALID}` | missing |")
    if invalid:
        lines.extend(["", "## Invalidity reasons", ""])
        lines.extend(f"- {reason}" for reason in invalid)
    if failures:
        lines.extend(["", "## Exact nonpassing coordinates", ""])
        lines.extend(
            f"- `{json.dumps(item, sort_keys=True, separators=(',', ':'))}`"
            for item in failures
        )
    lines.extend(
        [
            "",
            "This requalification does not adopt faer, rank mechanisms, choose a "
            "persistent factor store, change the frozen authority, or enter the "
            "100k rung.",
            "",
        ]
    )
    (args.output / "cohort-summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    print(disposition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
