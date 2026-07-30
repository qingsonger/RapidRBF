"""Verify the sole immutable non-compensating Issue 56 root-bound cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from preflight_journal import verify_preflight_journal


TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}
WORKERS = (1, 2, 8)
GRANTS = {1: 12, 2: 12, 8: 16}
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


def canonical_sha256(value: Any) -> str:
    data = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def matches(path: Path, expected_bytes: int, expected_sha256: str) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == expected_bytes
        and sha256_file(path) == expected_sha256
    )


def verify_sidecar(path: Path) -> bool:
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        return False
    return sidecar.read_text(encoding="utf-8").strip() == (
        f"{sha256_file(path)}  {path.name}"
    )


def candidate_failures(
    candidate: dict[str, Any], lane: str, workers: int
) -> list[dict[str, Any]]:
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
    rhs_identities: list[str] = []
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
        pre = source["solution_judgments"]
        post = source["reload_solution_judgments"]
        if len(pre) != 3 or len(post) != 3:
            failures.append(
                {
                    "lane": lane,
                    "workers": workers,
                    "ordinal": source["ordinal"],
                    "gate": "rhs-inventory",
                }
            )
            continue
        pre_ids = [item["rhs_sha256"] for item in pre]
        post_ids = [item["rhs_sha256"] for item in post]
        if pre_ids != post_ids:
            failures.append(
                {
                    "lane": lane,
                    "workers": workers,
                    "ordinal": source["ordinal"],
                    "gate": "rhs-pre-post-identity",
                }
            )
        rhs_identities.extend(pre_ids)
    if len(rhs_identities) != 18 or len(set(rhs_identities)) != 18:
        failures.append(
            {
                "lane": lane,
                "workers": workers,
                "gate": "frozen-18-rhs-identity",
            }
        )
    if any(candidate["scope"].values()):
        failures.append({"lane": lane, "workers": workers, "gate": "scope-boundary"})
    return failures


def verify_controller(
    observation: dict[str, Any],
    *,
    lane: str,
    workers: int,
    entry_path: Path | None,
    output_path: Path | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    invalidity: list[str] = []
    failures: list[dict[str, Any]] = []
    if observation.get("schema") != "RapidRBF/ControllerValidProcessObservation/v1":
        return [f"{lane}/{workers} controller schema differs"], failures
    if observation.get("terminal_policy") != "root-bound":
        invalidity.append(f"{lane}/{workers} root-bound policy is absent")
    events = observation.get("event_log", [])
    nonce = observation.get("invocation_nonce")
    if (
        not events
        or [item.get("sequence") for item in events] != list(range(len(events)))
        or any(item.get("invocation_nonce") != nonce for item in events)
        or any(
            events[index]["monotonic_ns"] > events[index + 1]["monotonic_ns"]
            for index in range(len(events) - 1)
        )
    ):
        invalidity.append(f"{lane}/{workers} controller event order differs")
    kinds = [item.get("kind") for item in events]
    if kinds.count("terminal_observed") != 1 or kinds.count("reaped") != 1:
        invalidity.append(f"{lane}/{workers} sole-waiter closure differs")
    if (
        observation.get("successful_samples", 0) < 1
        or observation.get("maximum_live_threads", 0) < 1
    ):
        invalidity.append(f"{lane}/{workers} has no successful live sample")
    for event in events:
        if event.get("kind") != "sample_ok":
            continue
        inventory = event.get("process_inventory", [])
        identities = [item.get("process_identity") for item in inventory]
        if (
            not inventory
            or len(identities) != len(set(identities))
            or sum(item.get("threads", 0) for item in inventory)
            != event.get("summed_live_threads")
            or not any(item.get("is_root") for item in inventory)
        ):
            invalidity.append(
                f"{lane}/{workers} contains an incomplete process-tree sample"
            )
            break
    benign = [
        item for item in events if item.get("kind") == "benign_terminal_race"
    ]
    if len(benign) != observation.get("benign_terminal_races") or len(benign) > 1:
        invalidity.append(f"{lane}/{workers} benign ESRCH count differs")
    records = observation.get("root_bound_adapter_failures", [])
    if len(records) != len(benign):
        invalidity.append(f"{lane}/{workers} root-bound record count differs")
    native_phases = {
        "linux-proc-process-tree": {
            "group-membership",
            "stat",
            "task-inventory",
        },
        "macos-proc-process-tree": {
            "group-membership",
            "bsd-identity",
            "task-info",
        },
        "windows-job-toolhelp-process-tree": {
            "job-membership",
            "process-identity",
            "thread-inventory",
        },
    }
    for envelope in records:
        record = envelope.get("record", {})
        terminal = record.get("terminal") or {}
        reap = record.get("reap") or {}
        cleanup = record.get("process_tree_cleanup") or {}
        if (
            envelope.get("classification")
            != "BENIGN_ROOT_BOUND_TERMINAL_CLOSURE"
            or record.get("schema") != "RapidRBF/RootBoundAdapterFailure/v1"
            or record.get("errno") != 3
            or record.get("error_name") != "ESRCH"
            or record.get("adapter") not in native_phases
            or record.get("phase") not in native_phases.get(record.get("adapter"), set())
            or record.get("subject_pid") != record.get("root_pid")
            or record.get("root_pid") != observation.get("diagnostic_pid")
            or record.get("invocation_nonce") != nonce
            or record.get("sample_finished_ns", -1)
            < record.get("sample_started_ns", 0)
            or terminal.get("owner") != "sole-waiter"
            or terminal.get("invocation_nonce") != nonce
            or terminal.get("observed_ns", -1)
            < record.get("sample_started_ns", 0)
            or terminal.get("observed_ns", 0)
            > record.get("sample_finished_ns", 0) + 1_000_000_000
            or reap.get("owner") != "sole-waiter"
            or reap.get("invocation_nonce") != nonce
            or reap.get("observed_ns", -1) < terminal.get("observed_ns", 0)
            or cleanup.get("invocation_nonce") != nonce
            or cleanup.get("complete") is not True
            or cleanup.get("observed_ns", -1) < reap.get("observed_ns", 0)
            or record.get("prior_reconciliations") != 0
            or record.get("incomplete_sample_effect")
            != {
                "successful_sample_delta": 0,
                "sample_error_delta": 0,
                "maximum_live_threads_delta": 0,
            }
        ):
            invalidity.append(f"{lane}/{workers} root-bound record differs")
    result = observation.get("process_result", {})
    if not result.get("process_tree_empty_after_reap"):
        invalidity.append(f"{lane}/{workers} process tree survived root reap")
    entry_identity = result.get("candidate_entry")
    if (
        entry_path is None
        or entry_identity is None
        or not matches(
            entry_path, entry_identity["bytes"], entry_identity["sha256"]
        )
    ):
        invalidity.append(f"{lane}/{workers} candidate-entry identity differs")
    output_identity = result.get("candidate_output")
    if output_path is None:
        if output_identity is not None:
            invalidity.append(f"{lane}/{workers} absent output has an identity")
    elif (
        output_identity is None
        or not matches(
            output_path, output_identity["bytes"], output_identity["sha256"]
        )
    ):
        invalidity.append(f"{lane}/{workers} candidate-output identity differs")

    classification = observation.get("classification")
    if classification == "INVALID_CONTROLLER_EVIDENCE":
        invalidity.append(f"{lane}/{workers} controller evidence is invalid")
    elif classification == "VALID_CANDIDATE_OWNED_NONPASS":
        failures.append(
            {"lane": lane, "workers": workers, "gate": "controller-owned-process"}
        )
    elif classification != "PASS":
        invalidity.append(f"{lane}/{workers} controller classification is unknown")
    if (
        observation.get("maximum_live_threads", 0) > GRANTS[workers]
        and classification != "VALID_CANDIDATE_OWNED_NONPASS"
    ):
        invalidity.append(f"{lane}/{workers} over-grant attribution differs")
    if (
        observation.get("maximum_live_threads", 0) <= GRANTS[workers]
        and result.get("returncode") == 0
        and not observation.get("timed_out")
        and classification == "VALID_CANDIDATE_OWNED_NONPASS"
    ):
        invalidity.append(f"{lane}/{workers} candidate nonpass lacks a cause")
    return invalidity, failures


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
    referenced: set[Path] = set()
    if (
        contract.get("schema")
        != "RapidRBF/RootBoundDoubleDoubleRefinementWitnessExecutionContract/v1"
        or contract.get("maximum_attempts") != 1
        or contract.get("required_run_attempt") != 1
        or contract.get("replacement_retry_permitted")
        or contract.get("partial_rerun_permitted")
        or contract.get("attempt_mixing_permitted")
    ):
        invalidity.append("Issue 56 execution contract differs")

    reference_paths = sorted(
        args.evidence_root.rglob("reference-manifest.v1.json")
    )
    reference_evidence: dict[str, Any] | None = None
    if len(reference_paths) != 1:
        invalidity.append(
            f"expected one accepted reference, found {len(reference_paths)}"
        )
    elif sha256_file(reference_paths[0]) != contract["reference_manifest_sha256"]:
        invalidity.append("accepted reference differs")
    else:
        reference_path = reference_paths[0]
        reproduction_path = reference_path.with_name(
            "reference-reproduction.json"
        )
        if not verify_sidecar(reference_path):
            invalidity.append("accepted reference sidecar differs")
        try:
            reproduction = json.loads(
                reproduction_path.read_text(encoding="utf-8")
            )
            if (
                reproduction["schema"]
                != "RapidRBF/ProjectedFactorReferenceReproduction/v1"
                or reproduction["manifest_sha256"]
                != contract["reference_manifest_sha256"]
            ):
                invalidity.append("accepted reference reproduction differs")
        except (OSError, KeyError, json.JSONDecodeError) as error:
            invalidity.append(f"accepted reference reproduction is malformed: {error}")
        referenced.update(
            {
                reference_path,
                reference_path.with_name(reference_path.name + ".sha256"),
                reproduction_path,
            }
        )
        reference_evidence = {
            "manifest": {
                "bytes": reference_path.stat().st_size,
                "sha256": sha256_file(reference_path),
            },
            "reproduction": {
                "bytes": (
                    reproduction_path.stat().st_size
                    if reproduction_path.is_file()
                    else None
                ),
                "sha256": (
                    sha256_file(reproduction_path)
                    if reproduction_path.is_file()
                    else None
                ),
            },
        }

    preflight_paths = sorted(
        args.evidence_root.rglob("preflight-observation.json")
    )
    if len(preflight_paths) != 4:
        invalidity.append(
            f"expected four preflight observations, found {len(preflight_paths)}"
        )
    preflights: dict[str, dict[str, Any]] = {}
    preflight_files: dict[str, Path] = {}
    for path in preflight_paths:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            lane = item["lane_id"]
            if lane in preflights or lane not in TARGETS:
                invalidity.append(f"duplicate or unexpected preflight {lane}")
                continue
            if (
                item["schema"]
                != "RapidRBF/RootBoundRefinementWitnessTargetPreflight/v1"
                or item["status"] != "PASS"
                or item["target"] != TARGETS[lane]
                or item["binary_preflight"]["candidate_executed"]
                or item["binary_preflight"]["backend_entries"] != 0
                or item["binary_preflight"]["factor_or_solve_calls"] != 0
                or item["binary_preflight"]["candidate_observations"] != 0
                or item["controller_preflight"]["status"] != "PASS"
            ):
                invalidity.append(f"preflight {lane} contract differs")
            for child_key in ("binary_preflight", "controller_preflight"):
                child = item[child_key]
                child_path = path.parent / child["file"]
                if not matches(child_path, child["bytes"], child["sha256"]):
                    invalidity.append(f"preflight {lane} {child_key} differs")
                referenced.add(child_path)
            journal = verify_preflight_journal(
                path.parent,
                lane_id=lane,
                target=TARGETS[lane],
                replacement_plan_sha256=contract[
                    "root_bound_fresh_cohort_plan_sha256"
                ],
            )
            if {
                name: journal[name]
                for name in (
                    "file",
                    "bytes",
                    "sha256",
                    "sidecar",
                    "completed_check_count",
                )
            } != item["controller_preflight"]["journal"]:
                invalidity.append(f"preflight {lane} journal envelope differs")
            referenced.update(journal["referenced_paths"])
            if not verify_sidecar(path):
                invalidity.append(f"preflight {lane} sidecar differs")
            referenced.update({path, path.with_name(path.name + ".sha256")})
            preflights[lane] = item
            preflight_files[lane] = path
        except (
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            invalidity.append(f"malformed preflight {path}: {error}")
    if set(preflights) != set(TARGETS):
        invalidity.append("complete four-lane preflight set is absent")

    root_bound_release: dict[str, Any] | None = None
    unlock_release: dict[str, Any] | None = None
    root_bound_paths = sorted(
        args.evidence_root.rglob("root-bound-preflight-cohort.json")
    )
    unlock_paths = sorted(
        args.evidence_root.rglob("execution-preflight-unlock.json")
    )
    if len(root_bound_paths) != 1:
        invalidity.append(
            f"expected one root-bound preflight cohort, found {len(root_bound_paths)}"
        )
    else:
        root_path = root_bound_paths[0]
        try:
            root_value = json.loads(root_path.read_text(encoding="utf-8"))
            identity = root_value["identity"]
            if (
                not verify_sidecar(root_path)
                or root_value["schema"]
                != "RapidRBF/RootBoundZeroEntryPreflightCohort/v1"
                or root_value["issue"] != 55
                or root_value["status"]
                != "ROOT_BOUND_FOUR_LANE_ZERO_ENTRY_PREFLIGHT_PASS"
                or root_value["inherited_ready_gated_check_count"] != 1108
                or root_value["root_bound_check_count"] != 100
                or identity["controller_binding_sha256"]
                != contract["accepted_root_bound_controller_binding_sha256"]
                or identity["source_binding_sha256"]
                != contract["root_bound_preflight_source_binding_sha256"]
                or identity["workflow_sha256"]
                != contract["root_bound_preflight_workflow_sha256"]
                or identity["candidate_binding_sha256"]
                != contract["candidate_binding_sha256"]
                or identity["witness_plan_sha256"]
                != contract["witness_plan_sha256"]
                or identity["accepted_reference_sha256"]
                != contract["reference_manifest_sha256"]
                or root_value["non_reuse"]["issue_53_observations_used"] != 0
                or root_value["non_reuse"][
                    "issue_54_diagnostic_observations_used_as_candidate_counts"
                ]
                != 0
                or root_value["non_reuse"][
                    "issue_55_observations_are_candidate_counts"
                ]
                is not False
            ):
                invalidity.append("root-bound preflight release differs")
            referenced.update(
                {root_path, root_path.with_name(root_path.name + ".sha256")}
            )
            markdown = root_path.with_name("root-bound-preflight-cohort.md")
            if markdown.is_file():
                referenced.add(markdown)
            for lane, lane_record in root_value["lanes"].items():
                summaries = [
                    path
                    for path in args.evidence_root.rglob(
                        "root-bound-preflight-summary.json"
                    )
                    if json.loads(path.read_text(encoding="utf-8"))["lane_id"]
                    == lane
                ]
                if len(summaries) != 1:
                    invalidity.append(
                        f"root-bound preflight summary count differs for {lane}"
                    )
                    continue
                summary_path = summaries[0]
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                journal_path = summary_path.parent / summary["journal"]["file"]
                journal_sidecar = (
                    summary_path.parent / summary["journal"]["sidecar"]
                )
                inherited_dir = summary_path.parent.parent / "inherited"
                inherited_summary = (
                    inherited_dir / summary["inherited"]["summary"]["file"]
                )
                inherited_journal = (
                    inherited_dir / summary["inherited"]["journal"]["file"]
                )
                if (
                    lane not in TARGETS
                    or summary["target"] != TARGETS[lane]
                    or not verify_sidecar(summary_path)
                    or summary_path.stat().st_size
                    != lane_record["summary"]["bytes"]
                    or sha256_file(summary_path)
                    != lane_record["summary"]["sha256"]
                    or not matches(
                        journal_path,
                        lane_record["journal"]["bytes"],
                        lane_record["journal"]["sha256"],
                    )
                    or not journal_sidecar.is_file()
                    or journal_sidecar.read_text(encoding="ascii").split()[0]
                    != lane_record["journal"]["sha256"]
                    or not matches(
                        inherited_summary,
                        summary["inherited"]["summary"]["bytes"],
                        summary["inherited"]["summary"]["sha256"],
                    )
                    or not verify_sidecar(inherited_summary)
                    or not matches(
                        inherited_journal,
                        summary["inherited"]["journal"]["bytes"],
                        summary["inherited"]["journal"]["sha256"],
                    )
                    or not verify_sidecar(inherited_journal)
                ):
                    invalidity.append(
                        f"root-bound lane evidence differs for {lane}"
                    )
                referenced.update(
                    {
                        summary_path,
                        summary_path.with_name(summary_path.name + ".sha256"),
                        journal_path,
                        journal_sidecar,
                        inherited_summary,
                        inherited_summary.with_name(
                            inherited_summary.name + ".sha256"
                        ),
                        inherited_journal,
                        inherited_journal.with_name(
                            inherited_journal.name + ".sha256"
                        ),
                    }
                )
            root_bound_release = {
                "file": root_path.name,
                "bytes": root_path.stat().st_size,
                "sha256": sha256_file(root_path),
                "identity": identity,
                "lanes": root_value["lanes"],
                "scope": root_value["scope"],
            }
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            invalidity.append(f"malformed root-bound preflight release: {error}")

    if len(unlock_paths) != 1:
        invalidity.append(
            f"expected one candidate-entry unlock, found {len(unlock_paths)}"
        )
    else:
        unlock_path = unlock_paths[0]
        try:
            unlock = json.loads(unlock_path.read_text(encoding="utf-8"))
            ready_unlock = unlock["ready_gated_preflight"]
            preflight_binding_ids = {
                item["source_binding"]["source_binding_sha256"]
                for item in preflights.values()
            }
            preflight_controller_ids = {
                item["source_binding"]["controller_binding_sha256"]
                for item in preflights.values()
            }
            preflight_commits = {
                item["git_sha"] for item in preflights.values()
            }
            preflight_coordinates = {
                (
                    str(item["lane_witness"]["github"]["run_id"]),
                    str(item["lane_witness"]["github"]["run_attempt"]),
                    str(item["lane_witness"]["github"]["sha"]),
                )
                for item in preflights.values()
            }
            ready_lanes_match = all(
                lane in ready_unlock["lanes"]
                and ready_unlock["lanes"][lane]["preflight_bytes"]
                == preflight_files[lane].stat().st_size
                and ready_unlock["lanes"][lane]["preflight_sha256"]
                == sha256_file(preflight_files[lane])
                for lane in TARGETS
                if lane in preflight_files
            )
            expected_unlock_aggregation = (
                canonical_sha256(
                    {
                        "source_binding_sha256": next(
                            iter(preflight_binding_ids)
                        ),
                        "ready_lanes": {
                            lane: ready_unlock["lanes"][lane][
                                "preflight_sha256"
                            ]
                            for lane in sorted(TARGETS)
                        },
                        "root_bound_cohort_sha256": root_bound_release["sha256"],
                        "root_bound_aggregation_sha256": root_bound_release[
                            "identity"
                        ]["aggregation_sha256"],
                    }
                )
                if len(preflight_binding_ids) == 1
                and root_bound_release is not None
                and all(lane in ready_unlock["lanes"] for lane in TARGETS)
                else None
            )
            if (
                not verify_sidecar(unlock_path)
                or unlock["schema"]
                != "RapidRBF/RootBoundRefinementWitnessExecutionUnlock/v1"
                or unlock["issue"] != 56
                or unlock["status"] != "PASS"
                or unlock["root_bound_fresh_cohort_plan_sha256"]
                != contract["root_bound_fresh_cohort_plan_sha256"]
                or unlock["accepted_root_bound_controller_binding_sha256"]
                != contract["accepted_root_bound_controller_binding_sha256"]
                or root_bound_release is None
                or unlock["root_bound_preflight"] != root_bound_release
                or len(preflight_binding_ids) != 1
                or unlock["execution_source_binding_sha256"]
                != next(iter(preflight_binding_ids))
                or len(preflight_controller_ids) != 1
                or unlock["execution_controller_binding_sha256"]
                != next(iter(preflight_controller_ids))
                or len(preflight_commits) != 1
                or unlock["git_sha"] != next(iter(preflight_commits))
                or len(preflight_coordinates) != 1
                or unlock["workflow_coordinate"]
                != {
                    "run_id": next(iter(preflight_coordinates))[0],
                    "run_attempt": next(iter(preflight_coordinates))[1],
                    "sha": next(iter(preflight_coordinates))[2],
                }
                or not ready_lanes_match
                or unlock["aggregation_sha256"]
                != expected_unlock_aggregation
                or unlock["non_reuse"]
                != {
                    "issue_53_observations_used": 0,
                    "issue_54_diagnostic_observations_used": 0,
                    "issue_55_observations_used_as_candidate_counts": 0,
                }
            ):
                invalidity.append("candidate-entry unlock differs")
            referenced.update(
                {unlock_path, unlock_path.with_name(unlock_path.name + ".sha256")}
            )
            unlock_release = {
                "bytes": unlock_path.stat().st_size,
                "sha256": sha256_file(unlock_path),
                "aggregation_sha256": unlock["aggregation_sha256"],
                "value": unlock,
            }
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            invalidity.append(f"malformed candidate-entry unlock: {error}")

    target_paths = sorted(args.evidence_root.rglob("target-observation.json"))
    if len(target_paths) != 4:
        invalidity.append(
            f"expected four target observations, found {len(target_paths)}"
        )
    targets: dict[str, Any] = {}
    run_coordinates: set[tuple[str, str, str]] = set()
    binding_ids: set[str] = set()
    controller_ids: set[str] = set()
    commits: set[str] = set()
    for path in target_paths:
        try:
            target = json.loads(path.read_text(encoding="utf-8"))
            lane = target["lane_id"]
            if lane in targets:
                invalidity.append(f"duplicate target observation for {lane}")
                continue
            if (
                lane not in TARGETS
                or target["target"] != TARGETS[lane]
                or target["schema"]
                != "RapidRBF/RootBoundRefinementWitnessTargetEvidence/v1"
            ):
                invalidity.append(f"unexpected target identity in {path}")
                continue
            if lane not in preflights:
                invalidity.append(f"target {lane} lacks same-attempt preflight")
            else:
                if (
                    target["lane_equivalence"]
                    != preflights[lane]["lane_equivalence"]
                ):
                    invalidity.append(
                        f"target {lane} lane/toolchain differs from preflight"
                    )
                for preflight_lane, preflight in preflights.items():
                    summary = target["preflight_cohort"]["lanes"][
                        preflight_lane
                    ]
                    preflight_path = preflight_files[preflight_lane]
                    if (
                        summary["preflight_bytes"] != preflight_path.stat().st_size
                        or summary["preflight_sha256"]
                        != sha256_file(preflight_path)
                    ):
                        invalidity.append(
                            f"target {lane} preflight cohort hash differs"
                        )
                        break
                if (
                    root_bound_release is None
                    or target["preflight_cohort"].get("root_bound")
                    != root_bound_release
                ):
                    invalidity.append(
                        f"target {lane} root-bound preflight release differs"
                    )
                expected_unlock = (
                    {
                        key: unlock_release[key]
                        for key in ("bytes", "sha256", "aggregation_sha256")
                    }
                    if unlock_release is not None
                    else None
                )
                if target["preflight_cohort"].get("unlock") != expected_unlock:
                    invalidity.append(
                        f"target {lane} candidate-entry unlock differs"
                    )
            raw_lane = path.parent.parent / "lane" / "lane-identity.json"
            lane_file = target["lane_witness_file"]
            if not matches(
                raw_lane, lane_file["bytes"], lane_file["sha256"]
            ) or not verify_sidecar(raw_lane):
                invalidity.append(f"target {lane} raw lane witness differs")
            referenced.update(
                {raw_lane, raw_lane.with_name(raw_lane.name + ".sha256")}
            )

            profiles = target["profiles"]
            if tuple(item["workers"] for item in profiles) != WORKERS:
                invalidity.append(f"profile inventory differs for {lane}")
                continue
            target_failures: list[dict[str, Any]] = []
            for profile in profiles:
                workers = profile["workers"]
                baseline_path = (
                    path.parent / profile["baseline_file"]
                    if profile.get("baseline_file")
                    else None
                )
                entry_path = (
                    path.parent / profile["candidate_entry_file"]
                    if profile.get("candidate_entry_file")
                    else None
                )
                candidate_path = (
                    path.parent / profile["candidate_file"]
                    if profile.get("candidate_file")
                    else None
                )
                for artifact_path, bytes_key, hash_key, label in (
                    (
                        baseline_path,
                        "baseline_bytes",
                        "baseline_sha256",
                        "baseline",
                    ),
                    (
                        entry_path,
                        "candidate_entry_bytes",
                        "candidate_entry_sha256",
                        "entry",
                    ),
                    (
                        candidate_path,
                        "candidate_bytes",
                        "candidate_sha256",
                        "candidate",
                    ),
                ):
                    if artifact_path is None:
                        continue
                    if not matches(
                        artifact_path,
                        profile[bytes_key],
                        profile[hash_key],
                    ):
                        invalidity.append(
                            f"{lane}/{workers} {label} artifact differs"
                        )
                    referenced.add(artifact_path)
                controller_invalid, controller_failures = verify_controller(
                    profile["controller_observation"],
                    lane=lane,
                    workers=workers,
                    entry_path=entry_path,
                    output_path=candidate_path,
                )
                invalidity.extend(controller_invalid)
                target_failures.extend(controller_failures)
                if candidate_path is None:
                    if profile["disposition"] == INVALID:
                        invalidity.append(
                            f"{lane}/{workers} stopped before valid candidate evidence"
                        )
                    elif profile["disposition"] != REJECTED:
                        invalidity.append(
                            f"{lane}/{workers} absent candidate has wrong disposition"
                        )
                    continue
                candidate = json.loads(
                    candidate_path.read_text(encoding="utf-8")
                )
                if (
                    candidate["schema"]
                    != "RapidRBF/DoubleDoubleRefinementWitnessLaneObservation/v1"
                    or candidate["lane_id"] != lane
                    or candidate["lane"]["configured_workers"] != workers
                ):
                    invalidity.append(
                        f"candidate identity differs for {lane}/{workers}"
                    )
                    continue
                target_failures.extend(
                    candidate_failures(candidate, lane, workers)
                )
            failures.extend(target_failures)
            if not verify_sidecar(path):
                invalidity.append(f"target {lane} sidecar differs")
            referenced.update({path, path.with_name(path.name + ".sha256")})
            targets[lane] = {
                "target": target["target"],
                "disposition": target["disposition"],
                "source_binding_sha256": target["source_binding"][
                    "source_binding_sha256"
                ],
                "controller_binding_sha256": target["source_binding"][
                    "controller_binding_sha256"
                ],
                "git_sha": target["git_sha"],
                "target_observation_bytes": path.stat().st_size,
                "target_observation_sha256": sha256_file(path),
                "failures": len(target_failures),
            }
            binding_ids.add(
                target["source_binding"]["source_binding_sha256"]
            )
            controller_ids.add(
                target["source_binding"]["controller_binding_sha256"]
            )
            commits.add(target["git_sha"])
            run_coordinates.add(
                (
                    str(target["github"]["run_id"]),
                    str(target["github"]["run_attempt"]),
                    str(target["github"]["sha"]),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            invalidity.append(f"malformed target observation {path}: {error}")

    if set(targets) != set(TARGETS):
        invalidity.append("complete four-target set is absent")
    if len(binding_ids) != 1:
        invalidity.append("target source bindings are mixed")
    if len(controller_ids) != 1:
        invalidity.append("target controller bindings are mixed")
    if len(commits) != 1:
        invalidity.append("target commits are mixed")
    if len(run_coordinates) != 1:
        invalidity.append("target workflow attempts are mixed")
    elif next(iter(run_coordinates))[1] != "1":
        invalidity.append("root-bound workflow attempt is not the sole attempt")
    if commits and run_coordinates:
        coordinate_sha = next(iter(run_coordinates))[2]
        if coordinate_sha != next(iter(commits)):
            invalidity.append("workflow SHA differs from materialized commit")
    if unlock_release is not None:
        unlock = unlock_release["value"]
        expected_coordinate = (
            {
                "run_id": next(iter(run_coordinates))[0],
                "run_attempt": next(iter(run_coordinates))[1],
                "sha": next(iter(run_coordinates))[2],
            }
            if len(run_coordinates) == 1
            else None
        )
        if (
            unlock["git_sha"]
            != (next(iter(commits)) if len(commits) == 1 else None)
            or unlock["workflow_coordinate"] != expected_coordinate
            or unlock["execution_source_binding_sha256"]
            != (next(iter(binding_ids)) if len(binding_ids) == 1 else None)
            or unlock["execution_controller_binding_sha256"]
            != (next(iter(controller_ids)) if len(controller_ids) == 1 else None)
            or root_bound_release is None
            or unlock["root_bound_preflight"] != root_bound_release
        ):
            invalidity.append("candidate-entry unlock and target cohort differ")
    if preflights:
        preflight_bindings = {
            item["source_binding"]["source_binding_sha256"]
            for item in preflights.values()
        }
        preflight_controllers = {
            item["source_binding"]["controller_binding_sha256"]
            for item in preflights.values()
        }
        preflight_commits = {item["git_sha"] for item in preflights.values()}
        if preflight_bindings != binding_ids:
            invalidity.append("preflight and target source bindings differ")
        if preflight_controllers != controller_ids:
            invalidity.append("preflight and target controller bindings differ")
        if preflight_commits != commits:
            invalidity.append("preflight and target commits differ")
        preflight_runs = {
            (
                str(item["lane_witness"]["github"]["run_id"]),
                str(item["lane_witness"]["github"]["run_attempt"]),
                str(item["lane_witness"]["github"]["sha"]),
            )
            for item in preflights.values()
        }
        if preflight_runs != run_coordinates:
            invalidity.append("preflight and target workflow attempts differ")

    actual_files = {path for path in args.evidence_root.rglob("*") if path.is_file()}
    unexpected = sorted(actual_files - referenced)
    if unexpected:
        invalidity.append(
            "unexpected or unreferenced evidence: "
            + ", ".join(str(path.relative_to(args.evidence_root)) for path in unexpected)
        )

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
        "schema": "RapidRBF/RootBoundRefinementWitnessCohortSummary/v1",
        "disposition": disposition,
        "contract_sha256": sha256_file(args.contract),
        "contract_id": contract["contract_id"],
        "controller_plan_sha256": contract["controller_plan_sha256"],
        "root_bound_fresh_cohort_plan_sha256": contract[
            "root_bound_fresh_cohort_plan_sha256"
        ],
        "accepted_root_bound_controller_binding_sha256": contract[
            "accepted_root_bound_controller_binding_sha256"
        ],
        "candidate_binding_sha256": contract["candidate_binding_sha256"],
        "source_binding_sha256": (
            next(iter(binding_ids)) if len(binding_ids) == 1 else None
        ),
        "controller_binding_sha256": (
            next(iter(controller_ids)) if len(controller_ids) == 1 else None
        ),
        "git_sha": next(iter(commits)) if len(commits) == 1 else None,
        "workflow_coordinate": (
            {
                "run_id": next(iter(run_coordinates))[0],
                "run_attempt": next(iter(run_coordinates))[1],
                "sha": next(iter(run_coordinates))[2],
            }
            if len(run_coordinates) == 1
            else None
        ),
        "reference_evidence": reference_evidence,
        "preflight_count": len(preflights),
        "root_bound_preflight_release": root_bound_release,
        "candidate_entry_unlock": (
            {
                key: unlock_release[key]
                for key in ("bytes", "sha256", "aggregation_sha256")
            }
            if unlock_release is not None
            else None
        ),
        "target_count": len(targets),
        "target_profile_count": len(targets) * 3,
        "witness_source_observations": len(targets) * 3 * 6,
        "rhs_identity_observations": len(targets) * 3 * 18,
        "pre_pack_solution_judgments": len(targets) * 3 * 6 * 3,
        "post_reload_solution_judgments": len(targets) * 3 * 6 * 3,
        "targets": targets,
        "invalidity_reasons": invalidity,
        "nonpassing_coordinates": failures,
        "integrity": {
            "referenced_files": len(referenced),
            "actual_files": len(actual_files),
            "unexpected_files": len(unexpected),
        },
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
            "maximum_attempts": contract["maximum_attempts"],
            "attempt_mixing_permitted": False,
            "partial_rerun_permitted": False,
            "candidate_owned_failure_retriable": False,
            "replacement_retry_permitted": False,
            "invalidity_returns_to_fresh_wayfinder_ticket": True,
        },
    }
    args.output.mkdir(parents=True)
    output = args.output / "cohort-summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (args.output / "cohort-summary.json.sha256").write_text(
        f"{sha256_file(output)}  cohort-summary.json\n"
    )
    lines = [
        "# Root-bound fresh double-double refinement witness cohort",
        "",
        f"Disposition: `{disposition}`",
        "",
        f"- Preflights: {len(preflights)}/4",
        f"- Targets: {len(targets)}/4",
        f"- Target/profile observations: {len(targets) * 3}/12",
        f"- Witness/RHS observations: {len(targets) * 3 * 18}/216",
        f"- Nonpassing coordinates: {len(failures)}",
        f"- Invalidity reasons: {len(invalidity)}",
        f"- Integrity files: {len(referenced)}/{len(actual_files)}",
        "- Factor route admitted: no",
        (
            "- Separate full-corpus plan supported: yes"
            if disposition == SUPPORTED
            else "- Separate full-corpus plan supported: no"
        ),
    ]
    (args.output / "cohort-summary.md").write_text("\n".join(lines) + "\n")
    print(disposition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
