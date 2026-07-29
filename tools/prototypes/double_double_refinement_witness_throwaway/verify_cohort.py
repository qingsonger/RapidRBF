"""Verify the immutable non-compensating Issue 49 four-target cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}
WORKERS = (1, 2, 8)
ORDINALS = (0, 36, 69, 72, 106, 150)
SUPPORTED = "REFINEMENT_ROUTE_SUPPORTED_FOR_FULL_CORPUS_PLAN"
REJECTED = "REFINEMENT_ROUTE_REJECTED_DIAGNOSTIC_ONLY"
INVALID = "INVALID_UNJUDGED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_failures(candidate: dict[str, Any], lane: str, workers: int) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if candidate["baseline_replay"]["status"] != "PASS":
        failures.append({"lane": lane, "workers": workers, "gate": "baseline-replay"})
    if candidate["controls"]["negative_reload"]["status"] != "PASS":
        failures.append({"lane": lane, "workers": workers, "gate": "negative-reload"})
    if candidate["controls"]["cancellation"]["status"] != "PASS":
        failures.append({"lane": lane, "workers": workers, "gate": "cancellation"})
    if candidate["controls"]["exact_n_minus_one_observations"] != 6:
        failures.append({"lane": lane, "workers": workers, "gate": "n-minus-one"})
    if not candidate["scratch"]["cleanup_pass"]:
        failures.append({"lane": lane, "workers": workers, "gate": "scratch-cleanup"})
    sources = candidate["factor_sources"]
    if tuple(item["ordinal"] for item in sources) != ORDINALS:
        failures.append({"lane": lane, "workers": workers, "gate": "witness-inventory"})
        return failures
    for source in sources:
        if source["status"] != "PASS":
            failures.append(
                {
                    "lane": lane,
                    "workers": workers,
                    "ordinal": source["ordinal"],
                    "factor_source_id": source["factor_source_id"],
                    "gate": "source",
                    "error": source["error"],
                }
            )
        if source["n_minus_one"]["status"] != "PASS":
            failures.append(
                {
                    "lane": lane,
                    "workers": workers,
                    "ordinal": source["ordinal"],
                    "gate": "n-minus-one",
                }
            )
        if source["refinement"]["owned_bytes"] != 168 * source["dimension"]:
            failures.append(
                {
                    "lane": lane,
                    "workers": workers,
                    "ordinal": source["ordinal"],
                    "gate": "owned-refinement-bytes",
                }
            )
        if not source["pre_post_solutions_bit_exact"]:
            failures.append(
                {
                    "lane": lane,
                    "workers": workers,
                    "ordinal": source["ordinal"],
                    "gate": "pre-post-reload-bit-identity",
                }
            )
    if any(candidate["scope"].values()):
        failures.append({"lane": lane, "workers": workers, "gate": "scope-boundary"})
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"output must be absent: {args.output}")
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    invalidity: list[str] = []
    failures: list[dict[str, Any]] = []
    targets: dict[str, Any] = {}
    paths = sorted(args.evidence_root.rglob("target-observation.json"))
    if len(paths) != 4:
        invalidity.append(f"expected four target observations, found {len(paths)}")
    for path in paths:
        try:
            target = json.loads(path.read_text(encoding="utf-8"))
            lane = target["lane_id"]
            if lane in targets:
                invalidity.append(f"duplicate target observation for {lane}")
                continue
            if lane not in TARGETS or target["target"] != TARGETS[lane]:
                invalidity.append(f"unexpected target identity in {path}")
                continue
            profiles = target["profiles"]
            if tuple(item["workers"] for item in profiles) != WORKERS:
                invalidity.append(f"profile inventory differs for {lane}")
                continue
            target_failures: list[dict[str, Any]] = []
            for profile in profiles:
                workers = profile["workers"]
                if not profile["controller_threads"]["pass"]:
                    target_failures.append(
                        {"lane": lane, "workers": workers, "gate": "thread-bound"}
                    )
                candidate_name = profile.get("candidate_file")
                if candidate_name is None:
                    if profile["disposition"] == INVALID:
                        invalidity.append(
                            f"{lane}/{workers} stopped before refined candidate entry"
                        )
                    else:
                        target_failures.append(
                            {
                                "lane": lane,
                                "workers": workers,
                                "gate": "candidate-crash-or-timeout",
                            }
                        )
                    continue
                candidate_path = path.parent / candidate_name
                if (
                    not candidate_path.is_file()
                    or sha256_file(candidate_path) != profile["candidate_sha256"]
                ):
                    invalidity.append(f"candidate evidence differs for {lane}/{workers}")
                    continue
                candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                if (
                    candidate["schema"]
                    != "RapidRBF/DoubleDoubleRefinementWitnessLaneObservation/v1"
                    or candidate["lane_id"] != lane
                    or candidate["lane"]["configured_workers"] != workers
                ):
                    invalidity.append(f"candidate identity differs for {lane}/{workers}")
                    continue
                target_failures.extend(candidate_failures(candidate, lane, workers))
            failures.extend(target_failures)
            targets[lane] = {
                "target": target["target"],
                "disposition": target["disposition"],
                "source_binding_sha256": target["source_binding"]["binding_sha256"],
                "git_sha": target["git_sha"],
                "target_observation_sha256": sha256_file(path),
                "failures": len(target_failures),
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            invalidity.append(f"malformed target observation {path}: {error}")
    if set(targets) != set(TARGETS):
        invalidity.append("complete four-target set is absent")
    binding_ids = {item["source_binding_sha256"] for item in targets.values()}
    commits = {item["git_sha"] for item in targets.values()}
    if len(binding_ids) != 1:
        invalidity.append("target source bindings are mixed")
    if len(commits) != 1:
        invalidity.append("target commits are mixed")

    if invalidity:
        disposition = INVALID
    elif failures:
        disposition = REJECTED
    elif all(item["disposition"] == SUPPORTED for item in targets.values()):
        disposition = SUPPORTED
    else:
        disposition = REJECTED
        failures.append({"gate": "target-disposition-without-coordinate"})

    summary = {
        "schema": "RapidRBF/DoubleDoubleRefinementWitnessCohortSummary/v1",
        "disposition": disposition,
        "contract_sha256": sha256_file(args.contract),
        "contract_id": contract["contract_id"],
        "source_binding_sha256": next(iter(binding_ids)) if len(binding_ids) == 1 else None,
        "git_sha": next(iter(commits)) if len(commits) == 1 else None,
        "target_count": len(targets),
        "target_profile_count": len(targets) * 3,
        "witness_source_observations": len(targets) * 3 * 6,
        "pre_pack_solution_judgments": len(targets) * 3 * 6 * 3,
        "post_reload_solution_judgments": len(targets) * 3 * 6 * 3,
        "targets": targets,
        "invalidity_reasons": invalidity,
        "nonpassing_coordinates": failures,
        "scope": {
            "supports_full_corpus_plan_only": disposition == SUPPORTED,
            "factor_path_admitted": False,
            "faer_or_qd_adopted": False,
            "factor_corpus_admitted": False,
            "mechanism_panel_run": False,
            "persistent_factor_storage_selected": False,
            "entered_100k_rung": False,
            "downstream_solver_comparison_unblocked": False,
        },
        "retry": {
            "attempt_mixing_permitted": False,
            "partial_rerun_permitted": False,
            "candidate_owned_failure_retriable": False,
        },
    }
    args.output.mkdir(parents=True)
    output = args.output / "cohort-summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (args.output / "cohort-summary.json.sha256").write_text(
        f"{sha256_file(output)}  cohort-summary.json\n"
    )
    lines = [
        "# Double-double refinement witness cohort",
        "",
        f"Disposition: `{disposition}`",
        "",
        f"- Targets: {len(targets)}/4",
        f"- Target/profile observations: {len(targets) * 3}/12",
        f"- Nonpassing coordinates: {len(failures)}",
        f"- Invalidity reasons: {len(invalidity)}",
        "- Factor route admitted: no",
        "- Full-corpus qualification authorized by this result: no",
    ]
    (args.output / "cohort-summary.md").write_text("\n".join(lines) + "\n")
    print(disposition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
