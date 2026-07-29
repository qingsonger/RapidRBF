"""Judge one non-compensating four-target instrumented-faer qualification cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ADMITTED = "ADMITTED_FOR_MECHANISM_PANEL"
DIAGNOSTIC = "NOT_ADMITTED_DIAGNOSTIC_ONLY"
REQUIRED_PROFILES = {
    1: 12,
    2: 12,
    8: 16,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def problem_if(
    condition: bool,
    problems: list[str],
    lane_id: str,
    message: str,
) -> None:
    if condition:
        problems.append(f"{lane_id}: {message}")


def check_candidate(
    candidate: dict[str, Any],
    lane_id: str,
    target: str,
    workers: int,
    maximum_live_threads: int,
) -> list[str]:
    problems: list[str] = []
    problem_if(
        candidate.get("schema")
        != "RapidRBF/InstrumentedFaerCorpusQualificationLaneObservation/v1",
        problems,
        lane_id,
        f"{workers}-worker candidate schema differs",
    )
    problem_if(
        candidate.get("lane_id") != lane_id or candidate.get("target") != target,
        problems,
        lane_id,
        f"{workers}-worker candidate target identity differs",
    )
    problem_if(
        candidate.get("disposition") != ADMITTED
        or candidate.get("diagnostic_subset") is not False,
        problems,
        lane_id,
        f"{workers}-worker candidate is not fully admitted",
    )
    lane = candidate.get("lane", {})
    problem_if(
        lane.get("configured_workers") != workers
        or lane.get("maximum_live_threads_grant") != maximum_live_threads
        or lane.get("backend_parallelism") != "Par::Seq"
        or lane.get("nested_automatic_pool") is not False
        or not 0 < lane.get("effective_worker_high_water", 0) <= workers,
        problems,
        lane_id,
        f"{workers}-worker lane accounting differs",
    )
    counts = candidate.get("counts", {})
    problem_if(
        counts.get("planned_factor_sources") != 216
        or counts.get("observed_factor_sources") != 216
        or counts.get("passed_factor_sources") != 216
        or counts.get("failed_factor_sources") != 0
        or counts.get("qualified_factor_access_publications") != 216
        or counts.get("solved_correction_publications") != 216
        or counts.get("run_recompute_budget_initial") != 216
        or counts.get("run_recompute_budget_consumed") != 0
        or counts.get("run_scoped_recompute_recipes") != 0,
        problems,
        lane_id,
        f"{workers}-worker publication counts differ",
    )
    binding = candidate.get("candidate_binding", {})
    problem_if(
        binding.get("binding_sha256")
        != "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
        or binding.get("profile_sha256")
        != "00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3"
        or binding.get("parallelism") != "Par::Seq",
        problems,
        lane_id,
        f"{workers}-worker binding identity differs",
    )
    problem_if(
        candidate.get("plan", {}).get("file_sha256")
        != "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce",
        problems,
        lane_id,
        f"{workers}-worker plan identity differs",
    )
    scratch = candidate.get("scratch", {})
    problem_if(
        scratch.get("cleanup_pass") is not True
        or scratch.get("live_residue_bytes") != 0
        or scratch.get("residue_files") != [],
        problems,
        lane_id,
        f"{workers}-worker scratch cleanup differs",
    )
    controls = candidate.get("controls", {})
    cancellation = controls.get("cancellation", {})
    negative = controls.get("negative_reload", {})
    problem_if(
        controls.get("exact_n_minus_one_observations") != 216
        or cancellation.get("status") != "PASS"
        or cancellation.get("mid_factor", {}).get("cancelled") is not True
        or cancellation.get("mid_factor", {}).get("backend_entered") is not True
        or cancellation.get("mid_factor", {}).get("prior_factor_preserved")
        is not True
        or cancellation.get("mid_factor", {}).get("failed_publications") != 0
        or cancellation.get("mid_solve", {}).get("cancelled") is not True
        or cancellation.get("mid_solve", {}).get("backend_entered") is not True
        or cancellation.get("mid_solve", {}).get(
            "prior_solved_correction_preserved"
        )
        is not True
        or cancellation.get("mid_solve", {}).get("failed_publications") != 0
        or negative.get("status") != "PASS"
        or negative.get("backend_entries") != 0
        or not all(
            negative.get(name) is True
            for name in (
                "truncated_pack",
                "corrupt_pack",
                "wrong_source",
                "wrong_profile",
                "metadata_mismatch",
            )
        ),
        problems,
        lane_id,
        f"{workers}-worker controls differ",
    )
    sources = candidate.get("factor_sources", [])
    problem_if(
        len(sources) != 216
        or [source.get("ordinal") for source in sources] != list(range(216)),
        problems,
        lane_id,
        f"{workers}-worker source closure differs",
    )
    for source in sources:
        ordinal = source.get("ordinal", "?")
        execution = source.get("execution_metrics", {})
        reload_metrics = source.get("reload_metrics", {})
        pack = source.get("pack", {})
        if (
            source.get("status") != "PASS"
            or source.get("n_minus_one", {}).get("status") != "PASS"
            or source.get("n_minus_one", {}).get("operation_called") is not False
            or source.get("n_minus_one", {})
            .get("metrics", {})
            .get("backend_entries")
            != 0
            or pack.get("positive_reload") is not True
            or pack.get("removed_after_reload") is not True
            or source.get("reconstruction_relative_inf", float("inf"))
            > source.get("reconstruction_threshold", float("-inf"))
            or source.get("maximum_backward_error", float("inf"))
            > source.get("backward_threshold", float("-inf"))
            or source.get("maximum_solution_relative_inf", float("inf"))
            > source.get("reload_solution_threshold", float("-inf"))
            or execution.get("transient_residue_bytes") != 0
            or execution.get("outer_compute_permits_live") != 0
            or reload_metrics.get("transient_residue_bytes") != 0
            or reload_metrics.get("outer_compute_permits_live") != 0
        ):
            problems.append(
                f"{lane_id}: {workers}-worker source {ordinal} gate differs"
            )
    return problems


def check_target(
    path: Path,
    evidence: dict[str, Any],
    contract_sha256: str,
    expected_target: str,
) -> list[str]:
    lane_id = evidence.get("lane_id", path.parent.name)
    problems: list[str] = []
    problem_if(
        evidence.get("schema")
        != "RapidRBF/InstrumentedFaerTargetQualificationEvidence/v1",
        problems,
        lane_id,
        "target evidence schema differs",
    )
    problem_if(
        evidence.get("target") != expected_target,
        problems,
        lane_id,
        "native target differs",
    )
    problem_if(
        evidence.get("disposition") != ADMITTED,
        problems,
        lane_id,
        "target is not admitted",
    )
    problem_if(
        evidence.get("execution_contract", {}).get("sha256") != contract_sha256,
        problems,
        lane_id,
        "execution contract differs",
    )
    lane_witness = evidence.get("lane_witness", {})
    problem_if(
        lane_witness.get("qualification") != "PASS"
        or lane_witness.get("lane", {}).get("lane_id") != lane_id
        or lane_witness.get("lane", {}).get("target") != expected_target,
        problems,
        lane_id,
        "lane witness differs",
    )
    observations = evidence.get("lane_observations", [])
    problem_if(
        len(observations) != len(REQUIRED_PROFILES)
        or {item.get("workers") for item in observations}
        != set(REQUIRED_PROFILES),
        problems,
        lane_id,
        "required lane profile closure differs",
    )
    for observation in observations:
        workers = observation.get("workers")
        if workers not in REQUIRED_PROFILES:
            continue
        maximum_live_threads = REQUIRED_PROFILES[workers]
        candidate_path = path.parent / observation.get("candidate_file", "")
        if not candidate_path.is_file():
            problems.append(
                f"{lane_id}: missing {workers}-worker candidate observation"
            )
            continue
        if sha256_file(candidate_path) != observation.get("candidate_file_sha256"):
            problems.append(
                f"{lane_id}: {workers}-worker candidate file identity differs"
            )
            continue
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        problems.extend(
            check_candidate(
                candidate,
                lane_id,
                expected_target,
                workers,
                maximum_live_threads,
            )
        )
        thread = observation.get("controller_threads", {})
        problem_if(
            thread.get("pass") is not True
            or thread.get("samples", 0) <= 0
            or thread.get("sampling_errors") != []
            or thread.get("maximum_live_threads_grant") != maximum_live_threads
            or thread.get("maximum_live_threads", maximum_live_threads + 1)
            > maximum_live_threads,
            problems,
            lane_id,
            f"{workers}-worker external thread observation differs",
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract_bytes = args.contract.read_bytes()
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest()
    contract = json.loads(contract_bytes)
    plan = json.loads(
        (args.contract.parent / "factor-qualification-plan.v1.json").read_text(
            encoding="utf-8"
        )
    )
    required = {
        target["lane_id"]: target["target"] for target in plan["targets"]
    }
    problems: list[str] = []
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(args.evidence_root.rglob("target-observation.json")):
        evidence = json.loads(path.read_text(encoding="utf-8"))
        lane_id = evidence.get("lane_id")
        if lane_id not in required:
            problems.append(f"unexpected target evidence for {lane_id}")
            continue
        if lane_id in records:
            problems.append(f"duplicate target evidence for {lane_id}")
            continue
        records[lane_id] = (path, evidence)
        problems.extend(
            check_target(path, evidence, contract_sha256, required[lane_id])
        )

    for lane_id in required:
        if lane_id not in records:
            problems.append(f"missing target evidence for {lane_id}")

    cohort_keys = {
        (
            evidence.get("github", {}).get("run_id"),
            evidence.get("github", {}).get("run_attempt"),
            evidence.get("github", {}).get("sha"),
            evidence.get("execution_contract", {}).get("sha256"),
        )
        for _, evidence in records.values()
    }
    if len(cohort_keys) != 1 or any(None in key for key in cohort_keys):
        problems.append(
            "target evidence does not share one populated run/attempt/sha/contract key"
        )
    transport_ids = {
        (
            evidence.get("transport", {}).get("asset", {}).get("sha256"),
            evidence.get("transport", {}).get("asset", {}).get("bytes"),
        )
        for _, evidence in records.values()
    }
    if len(transport_ids) != 1:
        problems.append("target evidence does not share one transport asset")

    dispositions = {
        lane_id: evidence["disposition"]
        for lane_id, (_, evidence) in records.items()
    }
    disposition = (
        ADMITTED
        if not problems
        and len(records) == len(required)
        and all(value == ADMITTED for value in dispositions.values())
        else DIAGNOSTIC
    )

    args.output.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema": "RapidRBF/InstrumentedFaerCorpusQualificationCohort/v1",
        "execution_contract": {
            "contract_id": contract["contract_id"],
            "sha256": contract_sha256,
        },
        "factor_qualification_plan": {
            "plan_id": plan["plan_id"],
            "sha256": sha256_file(
                args.contract.parent / "factor-qualification-plan.v1.json"
            ),
        },
        "required_targets": required,
        "target_dispositions": dispositions,
        "cohort_keys": [list(key) for key in sorted(cohort_keys, key=str)],
        "transport_ids": [list(key) for key in sorted(transport_ids, key=str)],
        "problems": problems,
        "disposition": disposition,
        "target_evidence": {
            lane_id: {
                "sha256": sha256_file(records[lane_id][0]),
                "target": records[lane_id][1]["target"],
                "native_executable": records[lane_id][1]["native_executable"],
                "lane_profiles": [
                    {
                        "workers": item["workers"],
                        "candidate_file_sha256": item["candidate_file_sha256"],
                        "controller_threads": item["controller_threads"],
                    }
                    for item in records[lane_id][1]["lane_observations"]
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
        "# Instrumented faer 216-factor qualification cohort",
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
                f"{item['workers']}/{item['maximum_live_threads']}"
                for item in evidence["lane_observations"]
            )
            lines.append(
                f"| `{lane_id}` | `{target}` | "
                f"`{evidence['disposition']}` | `{profiles}` |"
            )
        else:
            lines.append(f"| `{lane_id}` | `{target}` | `{DIAGNOSTIC}` | missing |")
    if problems:
        lines.extend(["", "## Diagnostic reasons", ""])
        lines.extend(f"- {problem}" for problem in problems)
    lines.extend(
        [
            "",
            "This qualification does not adopt faer, rank mechanisms, choose a "
            "persistent factor store, change the factor-health profile, or enter "
            "the 100k rung.",
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
