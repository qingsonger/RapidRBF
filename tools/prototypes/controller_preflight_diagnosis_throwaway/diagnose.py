"""THROWAWAY diagnostic journal for the Issue 52 controller-only question."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
ISSUE51_ROOT = ROOT.parent / "double_double_refinement_witness_throwaway"
sys.path.insert(0, str(ISSUE51_ROOT))
import run as issue51  # noqa: E402


ISSUE51_COMMIT = "53e9d28aa78a3bbe2cbb486a1ef35f1a3aad5387"
ISSUE51_CONTROLLER_BINDING = (
    "e8bec9e0dda182727315f328d693f0b420d15c8059cdc09f05072655420aac8d"
)
ISSUE51_SOURCE_BINDING = (
    "954ff5dbc200309ed807cdd52af97dc782c757b56be2678fe35e3a171cd0af11"
)
ISSUE51_CANDIDATE_BINDING = (
    "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
)
ISSUE51_ACCEPTED_REFERENCE = (
    "6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a"
)
ISSUE51_CONTROLLER_PLAN = (
    "347cd33670d4f53c3d0b439fcc01085081f019324fdf23f107d2b5e32b4ceea4"
)
TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    data = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(path.name + ".partial")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


class Journal:
    def __init__(
        self,
        *,
        output: Path,
        lane_id: str,
        target: str,
        lane_witness: Path,
    ) -> None:
        self.output = output
        self.checks = output / "checks"
        self.checks.mkdir(parents=True)
        self.lane_id = lane_id
        self.target = target
        self.entries: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {
            "schema": "RapidRBF/ControllerPreflightDiagnosticJournal/v1",
            "issue": 52,
            "question": (
                "Which exact Issue 51 controller-only checks fail on each "
                "frozen lane?"
            ),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "lane_id": lane_id,
            "target": target,
            "issue51_commit": ISSUE51_COMMIT,
            "issue51_controller_binding_sha256": ISSUE51_CONTROLLER_BINDING,
            "issue51_source_binding_sha256": ISSUE51_SOURCE_BINDING,
            "candidate_binding_sha256": ISSUE51_CANDIDATE_BINDING,
            "accepted_reference_sha256": ISSUE51_ACCEPTED_REFERENCE,
            "controller_plan_sha256": ISSUE51_CONTROLLER_PLAN,
            "candidate_built": False,
            "candidate_executed": False,
            "backend_entries": 0,
            "factor_or_solve_calls": 0,
            "candidate_observations": 0,
            "lane_witness": {
                "path": str(lane_witness),
                "bytes": lane_witness.stat().st_size,
                "sha256": sha256_file(lane_witness),
            },
            "completed_check_count": 0,
            "checks": self.entries,
            "collection_status": "IN_PROGRESS",
        }
        self.persist()

    def persist(self) -> None:
        atomic_json(self.output / "diagnostic-journal.json", self.state)

    @staticmethod
    def detail_summary(detail: Any) -> dict[str, Any]:
        if not isinstance(detail, dict):
            return {}
        result: dict[str, Any] = {}
        for name in (
            "classification",
            "maximum_live_threads",
            "maximum_live_threads_grant",
            "successful_samples",
            "benign_terminal_races",
            "invalidity",
        ):
            if name in detail:
                result[name] = detail[name]
        process = detail.get("process_result")
        if isinstance(process, dict):
            result["process_result"] = {
                name: process.get(name)
                for name in (
                    "returncode",
                    "signal",
                    "process_tree_empty_after_reap",
                )
            }
        return result

    def record(
        self,
        *,
        name: str,
        group: str,
        passed: bool,
        detail: Any,
    ) -> dict[str, Any]:
        ordinal = len(self.entries)
        safe_name = name.replace("/", "-").replace(":", "-")
        path = self.checks / f"{ordinal:03d}-{safe_name}.json"
        record = {
            "schema": "RapidRBF/ControllerPreflightDiagnosticCheck/v1",
            "ordinal": ordinal,
            "lane_id": self.lane_id,
            "target": self.target,
            "name": name,
            "group": group,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
        atomic_json(path, record)
        entry = {
            "ordinal": ordinal,
            "name": name,
            "group": group,
            "status": record["status"],
            "file": f"checks/{path.name}",
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "summary": self.detail_summary(detail),
        }
        self.entries.append(entry)
        self.state["completed_check_count"] = len(self.entries)
        self.persist()
        print(
            json.dumps(
                {
                    "lane_id": self.lane_id,
                    "ordinal": ordinal,
                    "name": name,
                    "status": record["status"],
                    "summary": entry["summary"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return entry

    def capture(
        self,
        *,
        name: str,
        group: str,
        action: Callable[[], Any],
        predicate: Callable[[Any], bool],
    ) -> Any | None:
        try:
            detail = action()
            self.record(
                name=name,
                group=group,
                passed=bool(predicate(detail)),
                detail=detail,
            )
            return detail
        except Exception as error:  # diagnostic closure must survive a check
            self.record(
                name=name,
                group=group,
                passed=False,
                detail={
                    "exception_type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
            )
            return None


def verify_lane(lane_id: str, target: str, lane_witness_path: Path) -> dict[str, Any]:
    require(lane_id in TARGETS and TARGETS[lane_id] == target, "target differs")
    witness = json.loads(lane_witness_path.read_text(encoding="utf-8"))
    require(
        witness["qualification"] == "PASS"
        and witness["lane"]["lane_id"] == lane_id
        and witness["lane"]["target"] == target,
        "lane witness differs",
    )
    return witness


def diagnose(
    *,
    lane_id: str,
    target: str,
    lane_witness_path: Path,
    output: Path,
) -> None:
    require(not output.exists(), f"output must be absent: {output}")
    witness = verify_lane(lane_id, target, lane_witness_path)
    output.mkdir(parents=True)
    journal = Journal(
        output=output,
        lane_id=lane_id,
        target=target,
        lane_witness=lane_witness_path,
    )

    authority = journal.capture(
        name="issue51-authority-and-controller-binding",
        group="identity",
        action=lambda: {
            "authority": issue51.verify_static_authority(),
            "controller_binding": issue51.controller_binding(),
        },
        predicate=lambda value: (
            value["authority"]["candidate_binding_sha256"]
            == ISSUE51_CANDIDATE_BINDING
            and value["authority"]["controller_plan_sha256"]
            == ISSUE51_CONTROLLER_PLAN
            and value["controller_binding"]["controller_binding_sha256"]
            == ISSUE51_CONTROLLER_BINDING
        ),
    )

    model = issue51.load_controller_model()
    trace_results: dict[str, Any] = {}
    for name, scenario in model.scenario_catalog().items():
        def drive(scenario: dict[str, Any] = scenario) -> dict[str, Any]:
            state = model.initial_state(scenario["grant"])
            for action in scenario["actions"]:
                state = model.reduce(state, action)
            return {
                "expected": scenario["expected"],
                "observed": state["verdict"],
                "history": state["history"],
            }

        result = journal.capture(
            name=f"pure-state-{name}",
            group="pure_state_traces",
            action=drive,
            predicate=lambda value: value["observed"] == value["expected"],
        )
        trace_results[name] = result
    pure_state_pass = all(
        result is not None and result["observed"] == result["expected"]
        for result in trace_results.values()
    )
    journal.record(
        name="pure_state_traces",
        group="original-global-check",
        passed=pure_state_pass,
        detail={"scenario_count": len(trace_results)},
    )

    environment = issue51.build_environment()
    environment["RAPIDRBF_LANE_ID"] = lane_id
    environment["RAPIDRBF_TARGET"] = target
    scratch = Path(tempfile.mkdtemp(prefix="rapidrbf-issue52-controller-diagnosis-"))
    helper_executable = scratch / (
        "controller-helper.exe" if sys.platform == "win32" else "controller-helper"
    )
    observations: dict[str, Any] = {}
    fast_exits: list[Any | None] = []
    try:
        def build_helper() -> dict[str, Any]:
            completed = issue51.run(
                [
                    "rustc",
                    str(issue51.CONTROLLER_HELPER),
                    "-C",
                    "opt-level=0",
                    "-o",
                    str(helper_executable),
                ],
                cwd=issue51.ROOT,
                env=environment,
                timeout=300,
            )
            return {
                "source_sha256": issue51.sha256_file(
                    issue51.CONTROLLER_HELPER
                ),
                "executable_sha256": issue51.sha256_file(helper_executable),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }

        helper_build = journal.capture(
            name="native-helper-build",
            group="native-helper",
            action=build_helper,
            predicate=lambda value: (
                helper_executable.is_file()
                and value["source_sha256"]
                == "6bac891f15f3a023a59eaa95be3393ebdf7fbd866ccda68fa993debde29f6302"
            ),
        )
        if helper_build is not None and helper_executable.is_file():
            def observe(name: str, threads: int, require_sample: bool, fault: str | None = None) -> Any:
                return issue51.helper_observation(
                    scratch,
                    helper_executable=helper_executable,
                    name=name,
                    threads=threads,
                    grant=12,
                    environment=environment,
                    require_sample=require_sample,
                    fault_mode=fault,
                )

            observations["one_thread"] = journal.capture(
                name="one-thread",
                group="native-helper-observation",
                action=lambda: observe("one-thread", 1, True),
                predicate=lambda value: (
                    value["classification"] == "PASS"
                    and 1 <= value["maximum_live_threads"] <= 12
                ),
            )
            observations["grant_plus_one"] = journal.capture(
                name="grant-plus-one",
                group="native-helper-observation",
                action=lambda: observe("grant-plus-one", 13, True),
                predicate=lambda value: (
                    value["classification"] == "VALID_CANDIDATE_OWNED_NONPASS"
                    and value["maximum_live_threads"] >= 13
                ),
            )
            for index in range(256):
                name = f"fast-exit-{index:03d}"
                fast_exits.append(
                    journal.capture(
                        name=name,
                        group="fast-exit-observation",
                        action=lambda name=name: observe(name, 1, False),
                        predicate=lambda value: (
                            value["classification"] == "PASS"
                            and value["process_result"][
                                "process_tree_empty_after_reap"
                            ]
                        ),
                    )
                )
            observations["unpaired_esrch"] = journal.capture(
                name="fault-unpaired-esrch",
                group="native-helper-observation",
                action=lambda: observe(
                    "fault-unpaired-esrch", 1, False, "unpaired-esrch"
                ),
                predicate=lambda value: (
                    value["classification"] == "INVALID_CONTROLLER_EVIDENCE"
                ),
            )
            observations["other_error"] = journal.capture(
                name="fault-non-esrch",
                group="native-helper-observation",
                action=lambda: observe(
                    "fault-non-esrch", 1, False, "non-esrch"
                ),
                predicate=lambda value: (
                    value["classification"] == "INVALID_CONTROLLER_EVIDENCE"
                ),
            )
        else:
            journal.record(
                name="native-helper-observations",
                group="native-helper",
                passed=False,
                detail={"error": "helper build did not close"},
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    one_thread = observations.get("one_thread")
    over_grant = observations.get("grant_plus_one")
    unpaired = observations.get("unpaired_esrch")
    other = observations.get("other_error")
    global_checks = {
        "pure_state_traces": pure_state_pass,
        "one_thread_detected": (
            one_thread is not None
            and one_thread["classification"] == "PASS"
            and 1 <= one_thread["maximum_live_threads"] <= 12
        ),
        "grant_plus_one_detected": (
            over_grant is not None
            and over_grant["classification"] == "VALID_CANDIDATE_OWNED_NONPASS"
            and over_grant["maximum_live_threads"] >= 13
        ),
        "fast_exit_closure": (
            len(fast_exits) == 256
            and all(
                value is not None
                and value["classification"] == "PASS"
                and value["process_result"]["process_tree_empty_after_reap"]
                for value in fast_exits
            )
        ),
        "unpaired_esrch_invalid": (
            unpaired is not None
            and unpaired["classification"] == "INVALID_CONTROLLER_EVIDENCE"
        ),
        "other_sampling_error_invalid": (
            other is not None
            and other["classification"] == "INVALID_CONTROLLER_EVIDENCE"
        ),
        "helper_scratch_removed": not scratch.exists(),
    }
    for name, passed in global_checks.items():
        if name == "pure_state_traces":
            continue
        journal.record(
            name=name,
            group="original-global-check",
            passed=passed,
            detail={"original_issue51_check": name},
        )

    failed_observations = [
        {
            "name": entry["name"],
            "group": entry["group"],
            "summary": entry["summary"],
            "file": entry["file"],
            "sha256": entry["sha256"],
        }
        for entry in journal.entries
        if entry["status"] == "FAIL"
        and entry["group"]
        in {"pure_state_traces", "native-helper", "native-helper-observation", "fast-exit-observation"}
    ]
    summary = {
        "schema": "RapidRBF/ControllerPreflightDiagnosticSummary/v1",
        "issue": 52,
        "lane_id": lane_id,
        "target": target,
        "collection_status": "COMPLETE",
        "original_controller_status": (
            "PASS" if all(global_checks.values()) else "FAIL"
        ),
        "global_checks": global_checks,
        "failed_global_checks": [
            name for name, passed in global_checks.items() if not passed
        ],
        "failed_observations": failed_observations,
        "completed_check_count": len(journal.entries),
        "journal": {
            "file": "diagnostic-journal.json",
            "bytes": (output / "diagnostic-journal.json").stat().st_size,
            "sha256_before_completion": sha256_file(
                output / "diagnostic-journal.json"
            ),
        },
        "identity": {
            "issue51_commit": ISSUE51_COMMIT,
            "issue51_controller_binding_sha256": ISSUE51_CONTROLLER_BINDING,
            "issue51_source_binding_sha256": ISSUE51_SOURCE_BINDING,
            "candidate_binding_sha256": ISSUE51_CANDIDATE_BINDING,
            "accepted_reference_sha256": ISSUE51_ACCEPTED_REFERENCE,
            "controller_plan_sha256": ISSUE51_CONTROLLER_PLAN,
            "authority_check_recorded": authority is not None,
            "lane_witness_sha256": sha256_file(lane_witness_path),
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPOSITORY,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
        },
        "scope": {
            "candidate_built": False,
            "candidate_executed": False,
            "backend_entries": 0,
            "factor_or_solve_calls": 0,
            "candidate_observations": 0,
        },
        "lane_witness": witness,
    }
    atomic_json(output / "diagnostic-summary.json", summary)
    journal.state["collection_status"] = "COMPLETE"
    journal.state["original_controller_status"] = summary[
        "original_controller_status"
    ]
    journal.state["failed_global_checks"] = summary["failed_global_checks"]
    journal.state["summary"] = {
        "file": "diagnostic-summary.json",
        "bytes": (output / "diagnostic-summary.json").stat().st_size,
        "sha256": sha256_file(output / "diagnostic-summary.json"),
    }
    journal.persist()
    (output / "diagnostic-journal.json.sha256").write_text(
        f"{sha256_file(output / 'diagnostic-journal.json')}  "
        "diagnostic-journal.json\n",
        encoding="ascii",
    )
    (output / "diagnostic-summary.json.sha256").write_text(
        f"{sha256_file(output / 'diagnostic-summary.json')}  "
        "diagnostic-summary.json\n",
        encoding="ascii",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-id", required=True, choices=sorted(TARGETS))
    parser.add_argument("--target", required=True)
    parser.add_argument("--lane-witness", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.lane_witness = args.lane_witness.resolve()
    args.output = args.output.resolve()
    return args


if __name__ == "__main__":
    parsed = parse_args()
    diagnose(
        lane_id=parsed.lane_id,
        target=parsed.target,
        lane_witness_path=parsed.lane_witness,
        output=parsed.output,
    )
