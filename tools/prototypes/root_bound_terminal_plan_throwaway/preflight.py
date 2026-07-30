"""Issue 55 four-lane, zero-candidate-entry controller-plan preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from model import (
    BENIGN,
    evaluate_scenarios,
    classify_adapter_failure,
)


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
WITNESS = ROOT.parent / "double_double_refinement_witness_throwaway"
sys.path.insert(0, str(WITNESS))

from controller_observer import observe_process  # noqa: E402


TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}
CONTROLLER_BINDING_PATHS = (
    "tools/prototypes/double_double_refinement_witness_throwaway/controller_observer.py",
    "tools/prototypes/root_bound_terminal_plan_throwaway/model.py",
    "tools/prototypes/root_bound_terminal_plan_throwaway/preflight.py",
)
SOURCE_BINDING_PATHS = (
    *CONTROLLER_BINDING_PATHS,
    "tools/prototypes/controller_preflight_diagnosis_throwaway/diagnose.py",
    "tools/prototypes/double_double_refinement_witness_throwaway/controller_helper.rs",
    "tools/prototypes/root_bound_terminal_plan_throwaway/aggregate.py",
    "tools/prototypes/root_bound_terminal_plan_throwaway/fresh-cohort-plan.v1.json",
    ".github/workflows/freeze-root-bound-terminal-plan.yml",
)
EXPECTED_INHERITED_CHECKS = 277
CANDIDATE_BINDING = (
    "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
)
WITNESS_PLAN = (
    "7018a1a33d601076ff17b6824068ada146039fa57aab5b1cf71793cbe6d13d60"
)
ACCEPTED_REFERENCE = (
    "6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a"
)
HELPER = """
import pathlib
import sys
import time

release = pathlib.Path(sys.argv[1])
deadline = time.monotonic() + 5.0
while not release.exists():
    if time.monotonic() >= deadline:
        raise SystemExit(91)
    time.sleep(0.001)
"""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def atomic_json(path: Path, value: Any) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def binding(paths: tuple[str, ...]) -> dict[str, Any]:
    files = []
    for name in paths:
        path = REPOSITORY / name
        require(path.is_file(), f"binding path is absent: {name}")
        files.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": sha256_bytes(payload), "files": files}


def git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def load_inherited(path: Path, lane_id: str, target: str) -> dict[str, Any]:
    summary_path = path / "diagnostic-summary.json"
    sidecar = summary_path.with_suffix(summary_path.suffix + ".sha256")
    journal_path = path / "diagnostic-journal.json"
    journal_sidecar = journal_path.with_suffix(journal_path.suffix + ".sha256")
    require(summary_path.is_file(), "inherited summary is absent")
    require(journal_path.is_file(), "inherited journal is absent")
    require(sidecar.is_file(), "inherited summary sidecar is absent")
    require(journal_sidecar.is_file(), "inherited journal sidecar is absent")
    require(
        sidecar.read_text(encoding="ascii").split()[0] == sha256_file(summary_path),
        "inherited summary sidecar differs",
    )
    require(
        journal_sidecar.read_text(encoding="ascii").split()[0]
        == sha256_file(journal_path),
        "inherited journal sidecar differs",
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    require(
        summary["lane_id"] == lane_id
        and summary["target"] == target
        and summary["boundary"] == "ready-gated"
        and summary["collection_status"] == "COMPLETE"
        and summary["original_controller_status"] == "PASS"
        and summary["completed_check_count"] == EXPECTED_INHERITED_CHECKS
        and not summary["failed_global_checks"],
        "inherited ready-gated controller preflight differs",
    )
    require(
        summary["scope"]
        == {
            "candidate_built": False,
            "candidate_executed": False,
            "backend_entries": 0,
            "factor_or_solve_calls": 0,
            "candidate_observations": 0,
        },
        "inherited preflight is not zero-entry",
    )
    return {
        "summary": {
            "file": summary_path.name,
            "bytes": summary_path.stat().st_size,
            "sha256": sha256_file(summary_path),
        },
        "journal": {
            "file": journal_path.name,
            "bytes": journal_path.stat().st_size,
            "sha256": sha256_file(journal_path),
        },
        "completed_check_count": summary["completed_check_count"],
        "observed_controller_binding_sha256": summary["identity"][
            "observed_controller_binding_sha256"
        ],
    }


def structured_record(observation: dict[str, Any]) -> dict[str, Any]:
    events = observation["event_log"]
    error = next(event for event in events if event["kind"] == "sample_error")
    terminal = next(
        (event for event in events if event["kind"] == "terminal_observed"),
        None,
    )
    reap = next((event for event in events if event["kind"] == "reaped"), None)
    last_ns = events[-1]["monotonic_ns"] if events else 0
    raw = error["raw_adapter_result"]
    return {
        "schema": "RapidRBF/RootBoundAdapterFailure/v1",
        "adapter": raw["adapter"],
        "errno": raw["errno"],
        "error_name": raw["error_name"],
        "phase": raw["phase"],
        "subject_pid": raw["subject_pid"],
        "root_pid": observation["diagnostic_pid"],
        "invocation_nonce": observation["invocation_nonce"],
        "sample_started_ns": error["sample_started_ns"],
        "sample_finished_ns": error["sample_finished_ns"],
        "terminal": (
            {
                "owner": terminal["owner"],
                "invocation_nonce": terminal["invocation_nonce"],
                "observed_ns": terminal["monotonic_ns"],
                "returncode": terminal["returncode"],
            }
            if terminal is not None
            else None
        ),
        "reap": (
            {
                "owner": reap["owner"],
                "invocation_nonce": reap["invocation_nonce"],
                "observed_ns": reap["monotonic_ns"],
            }
            if reap is not None
            else None
        ),
        "process_tree_cleanup": {
            "invocation_nonce": observation["invocation_nonce"],
            "observed_ns": last_ns + 1,
            "complete": observation["process_result"][
                "process_tree_empty_after_reap"
            ],
        },
        "prior_reconciliations": 0,
        "incomplete_sample_effect": {
            "successful_sample_delta": observation["successful_samples"],
            "sample_error_delta": 0,
            "maximum_live_threads_delta": observation["maximum_live_threads"],
        },
    }


def native_reproduction() -> dict[str, Any]:
    if sys.platform == "win32":
        return {
            "status": "NOT_APPLICABLE",
            "reason": (
                "Issue 53 native terminal invalidities were Linux "
                "group-membership and macOS BSD-identity losses"
            ),
            "candidate_entry_count": 0,
            "backend_entry_count": 0,
            "factor_call_count": 0,
            "solve_call_count": 0,
        }
    with tempfile.TemporaryDirectory(prefix="rapidrbf-issue55-native-") as scratch:
        release = Path(scratch) / "release"
        fired = False

        def cross_terminal() -> None:
            nonlocal fired
            if fired:
                return
            fired = True
            release.write_text("release\n", encoding="utf-8")
            time.sleep(0.250 if sys.platform == "darwin" else 0.050)

        before = cross_terminal if sys.platform.startswith("linux") else None
        after = (lambda _pids: cross_terminal()) if sys.platform == "darwin" else None
        completed, observation = observe_process(
            [sys.executable, "-c", HELPER, str(release)],
            cwd=ROOT,
            env=dict(os.environ),
            timeout_seconds=3.0,
            maximum_live_threads=12,
            candidate_entry=None,
            candidate_output=None,
            require_candidate_entry=False,
            require_successful_sample=False,
            invocation_kind="issue55-root-bound-native-inventory",
            terminal_policy="root-bound",
            before_group_snapshot=before,
            after_group_snapshot=after,
        )
    record = structured_record(observation)
    classification = classify_adapter_failure(record)
    expected_adapter = (
        "linux-proc-process-tree"
        if sys.platform.startswith("linux")
        else "macos-proc-process-tree"
    )
    expected_phase = (
        "group-membership" if sys.platform.startswith("linux") else "bsd-identity"
    )
    passed = (
        completed.returncode == 0
        and observation["classification"] == "PASS"
        and observation["benign_terminal_races"] == 1
        and classification == BENIGN
        and record["adapter"] == expected_adapter
        and record["phase"] == expected_phase
        and record["subject_pid"] == record["root_pid"]
        and record["process_tree_cleanup"]["complete"]
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "adapter": record["adapter"],
        "phase": record["phase"],
        "classification": classification,
        "record": record,
        "observer": {
            "classification": observation["classification"],
            "returncode": completed.returncode,
            "benign_terminal_races": observation["benign_terminal_races"],
            "successful_samples": observation["successful_samples"],
            "maximum_live_threads": observation["maximum_live_threads"],
            "process_tree_empty_after_reap": observation["process_result"][
                "process_tree_empty_after_reap"
            ],
        },
        "candidate_entry_count": 0,
        "backend_entry_count": 0,
        "factor_call_count": 0,
        "solve_call_count": 0,
    }


def main(
    *,
    lane_id: str,
    target: str,
    lane_witness_path: Path,
    inherited_path: Path,
    output: Path,
) -> None:
    require(lane_id in TARGETS and TARGETS[lane_id] == target, "lane differs")
    require(not output.exists(), f"output must be absent: {output}")
    witness = json.loads(lane_witness_path.read_text(encoding="utf-8"))
    require(
        witness["qualification"] == "PASS"
        and witness["lane"]["lane_id"] == lane_id
        and witness["lane"]["target"] == target,
        "lane witness differs",
    )
    inherited = load_inherited(inherited_path, lane_id, target)
    controls = evaluate_scenarios()
    control_checks = {
        **{
            f"adapter:{name}": result["passed"]
            for name, result in controls["adapter_failure_controls"].items()
        },
        **{
            f"process:{name}": result["passed"]
            for name, result in controls["process_result_controls"].items()
        },
    }
    native = native_reproduction()
    native_pass = native["status"] in {"PASS", "NOT_APPLICABLE"}
    controller = binding(CONTROLLER_BINDING_PATHS)
    source = binding(SOURCE_BINDING_PATHS)
    checks = [
        {
            "ordinal": index,
            "name": name,
            "status": "PASS" if passed else "FAIL",
        }
        for index, (name, passed) in enumerate(
            [
                ("inherited-ready-gated-277", True),
                *control_checks.items(),
                ("native-inventory-reproduction", native_pass),
                ("zero-candidate-entry", True),
                ("process-tree-cleanup", native.get("record", {}).get(
                    "process_tree_cleanup", {"complete": True}
                ).get("complete", True)),
            ]
        )
    ]
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    scope = {
        "candidate_built": False,
        "candidate_executed": False,
        "candidate_entries": 0,
        "backend_entries": 0,
        "factor_calls": 0,
        "solve_calls": 0,
        "candidate_observations": 0,
    }
    output.mkdir(parents=True)
    journal = {
        "schema": "RapidRBF/RootBoundZeroEntryPreflightJournal/v1",
        "issue": 55,
        "lane_id": lane_id,
        "target": target,
        "status": status,
        "checks": checks,
        "completed_check_count": len(checks),
        "inherited_completed_check_count": inherited["completed_check_count"],
        "controls": controls,
        "native_reproduction": native,
        "scope": scope,
    }
    journal_path = output / "root-bound-preflight-journal.json"
    atomic_json(journal_path, journal)
    journal_sidecar = journal_path.with_suffix(journal_path.suffix + ".sha256")
    journal_sidecar.write_text(
        f"{sha256_file(journal_path)}  {journal_path.name}\n",
        encoding="ascii",
    )
    summary = {
        "schema": "RapidRBF/RootBoundZeroEntryPreflightSummary/v1",
        "issue": 55,
        "lane_id": lane_id,
        "target": target,
        "status": status,
        "git_commit": git_value("rev-parse", "HEAD"),
        "github": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "workflow_sha": os.environ.get("GITHUB_SHA"),
        },
        "identities": {
            "controller_binding_sha256": controller["sha256"],
            "source_binding_sha256": source["sha256"],
            "workflow_sha256": sha256_file(
                REPOSITORY
                / ".github/workflows/freeze-root-bound-terminal-plan.yml"
            ),
            "candidate_binding_sha256": CANDIDATE_BINDING,
            "witness_plan_sha256": WITNESS_PLAN,
            "accepted_reference_sha256": ACCEPTED_REFERENCE,
            "lane_witness_sha256": sha256_file(lane_witness_path),
        },
        "inherited": inherited,
        "root_bound_completed_check_count": len(checks),
        "failed_checks": [
            item["name"] for item in checks if item["status"] != "PASS"
        ],
        "native_reproduction": {
            key: value
            for key, value in native.items()
            if key not in {"record"}
        },
        "scope": scope,
        "journal": {
            "file": journal_path.name,
            "bytes": journal_path.stat().st_size,
            "sha256": sha256_file(journal_path),
            "sidecar": journal_sidecar.name,
        },
        "lane_witness": witness,
    }
    summary_path = output / "root-bound-preflight-summary.json"
    atomic_json(summary_path, summary)
    summary_path.with_suffix(summary_path.suffix + ".sha256").write_text(
        f"{sha256_file(summary_path)}  {summary_path.name}\n",
        encoding="ascii",
    )
    require(status == "PASS", "root-bound zero-entry preflight failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-id", required=True, choices=sorted(TARGETS))
    parser.add_argument("--target", required=True)
    parser.add_argument("--lane-witness", required=True, type=Path)
    parser.add_argument("--inherited", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.lane_witness = args.lane_witness.resolve()
    args.inherited = args.inherited.resolve()
    args.output = args.output.resolve()
    return args


if __name__ == "__main__":
    parsed = parse_args()
    main(
        lane_id=parsed.lane_id,
        target=parsed.target,
        lane_witness_path=parsed.lane_witness,
        inherited_path=parsed.inherited,
        output=parsed.output,
    )
