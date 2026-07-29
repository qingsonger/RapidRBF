"""Atomic Issue 53 controller-preflight journal and verifier."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Callable


JOURNAL_NAME = "controller-preflight-journal.json"
CHECKS_DIRECTORY = "controller-preflight-checks"
EXPECTED_CHECKS = 277
EXPECTED_GROUP_COUNTS = {
    "identity": 1,
    "pure-state-trace": 8,
    "global-check": 7,
    "helper-build": 1,
    "native-helper-observation": 4,
    "fast-exit-observation": 256,
}
EXPECTED_NAMES_BY_GROUP = {
    "identity": {"issue53-authority-and-controller-binding"},
    "pure-state-trace": {
        "pure-state-exit_before_entry",
        "pure-state-issue49_esrch_exit",
        "pure-state-other_sampling_error",
        "pure-state-over_grant",
        "pure-state-terminal_first_esrch_exit",
        "pure-state-timeout_after_entry",
        "pure-state-unpaired_esrch",
        "pure-state-zero_successful_samples",
    },
    "global-check": {
        "pure_state_traces",
        "one_thread_detected",
        "grant_plus_one_detected",
        "fast_exit_closure",
        "unpaired_esrch_invalid",
        "other_sampling_error_invalid",
        "helper_scratch_removed",
    },
    "helper-build": {"native-helper-build"},
    "native-helper-observation": {
        "one-thread",
        "grant-plus-one",
        "fault-unpaired-esrch",
        "fault-non-esrch",
    },
    "fast-exit-observation": {
        f"fast-exit-{index:03d}" for index in range(256)
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(
        path,
        (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)
            + "\n"
        ).encode("utf-8"),
    )


def stream_record(data: bytes) -> dict[str, Any]:
    return {
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "base64": base64.b64encode(data).decode("ascii"),
    }


class PreflightJournal:
    """Persist each check before it can contribute to a global PASS."""

    def __init__(
        self,
        *,
        output: Path,
        lane_id: str,
        target: str,
        replacement_plan_sha256: str,
        lane_witness: Path,
    ) -> None:
        self.output = output
        self.checks = output / CHECKS_DIRECTORY
        self.checks.mkdir(parents=True)
        self.entries: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {
            "schema": "RapidRBF/ReadyGatedControllerPreflightJournal/v1",
            "issue": 53,
            "boundary": "Controller preflight readiness",
            "lane_id": lane_id,
            "target": target,
            "replacement_execution_plan_sha256": replacement_plan_sha256,
            "lane_witness": {
                "file": str(lane_witness),
                "bytes": lane_witness.stat().st_size,
                "sha256": sha256_file(lane_witness),
            },
            "scope": {
                "candidate_built_for_byte_identity": False,
                "candidate_executed": False,
                "candidate_entries": 0,
                "backend_entries": 0,
                "factor_or_solve_calls": 0,
                "candidate_observations": 0,
            },
            "completed_check_count": 0,
            "checks": self.entries,
            "collection_status": "IN_PROGRESS",
            "status": None,
        }
        self.persist()

    def mark_candidate_built(self) -> None:
        self.state["scope"]["candidate_built_for_byte_identity"] = True
        self.persist()

    def persist(self) -> None:
        atomic_json(self.output / JOURNAL_NAME, self.state)

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
            "schema": "RapidRBF/ReadyGatedControllerPreflightCheck/v1",
            "ordinal": ordinal,
            "lane_id": self.state["lane_id"],
            "target": self.state["target"],
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
            "file": f"{CHECKS_DIRECTORY}/{path.name}",
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
                    "lane_id": self.state["lane_id"],
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
        except Exception as error:  # noqa: BLE001 - evidence must survive failure
            self.record(
                name=name,
                group=group,
                passed=False,
                detail={
                    "exception_type": type(error).__name__,
                    "exception": str(error),
                    "traceback": traceback.format_exc(),
                },
            )
            return None

    def finalize(self, *, status: str) -> dict[str, Any]:
        self.state["collection_status"] = "COMPLETE"
        self.state["status"] = status
        self.persist()
        journal = self.output / JOURNAL_NAME
        atomic_bytes(
            journal.with_name(journal.name + ".sha256"),
            f"{sha256_file(journal)}  {journal.name}\n".encode("ascii"),
        )
        return {
            "file": journal.name,
            "bytes": journal.stat().st_size,
            "sha256": sha256_file(journal),
            "sidecar": journal.name + ".sha256",
            "completed_check_count": len(self.entries),
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _verify_stream(value: dict[str, Any], label: str) -> None:
    try:
        raw = base64.b64decode(value["base64"], validate=True)
    except Exception as error:  # noqa: BLE001 - normalize malformed evidence
        raise RuntimeError(f"{label} base64 differs: {error}") from error
    _require(len(raw) == value["bytes"], f"{label} byte count differs")
    _require(sha256_bytes(raw) == value["sha256"], f"{label} digest differs")


def verify_preflight_journal(
    root: Path,
    *,
    lane_id: str,
    target: str,
    replacement_plan_sha256: str,
) -> dict[str, Any]:
    journal_path = root / JOURNAL_NAME
    _require(journal_path.is_file(), f"{lane_id} journal is absent")
    sidecar = journal_path.with_name(journal_path.name + ".sha256")
    _require(
        sidecar.is_file()
        and sidecar.read_text(encoding="ascii").strip()
        == f"{sha256_file(journal_path)}  {journal_path.name}",
        f"{lane_id} journal sidecar differs",
    )
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    _require(
        journal["schema"]
        == "RapidRBF/ReadyGatedControllerPreflightJournal/v1"
        and journal["issue"] == 53
        and journal["boundary"] == "Controller preflight readiness"
        and journal["lane_id"] == lane_id
        and journal["target"] == target
        and journal["replacement_execution_plan_sha256"]
        == replacement_plan_sha256
        and journal["collection_status"] == "COMPLETE"
        and journal["status"] == "PASS",
        f"{lane_id} journal identity or status differs",
    )
    scope = journal["scope"]
    _require(
        scope["candidate_built_for_byte_identity"]
        and not scope["candidate_executed"]
        and scope["candidate_entries"] == 0
        and scope["backend_entries"] == 0
        and scope["factor_or_solve_calls"] == 0
        and scope["candidate_observations"] == 0,
        f"{lane_id} journal scope differs",
    )
    entries = journal["checks"]
    _require(
        journal["completed_check_count"] == EXPECTED_CHECKS
        and len(entries) == EXPECTED_CHECKS,
        f"{lane_id} journal must close {EXPECTED_CHECKS} checks",
    )
    _require(
        [entry["ordinal"] for entry in entries] == list(range(EXPECTED_CHECKS)),
        f"{lane_id} journal ordinals differ",
    )
    _require(
        all(entry["status"] == "PASS" for entry in entries),
        f"{lane_id} journal contains a failed check",
    )
    _require(
        dict(Counter(entry["group"] for entry in entries))
        == EXPECTED_GROUP_COUNTS,
        f"{lane_id} journal group inventory differs",
    )
    for group, expected_names in EXPECTED_NAMES_BY_GROUP.items():
        actual_names = {
            entry["name"] for entry in entries if entry["group"] == group
        }
        _require(
            actual_names == expected_names,
            f"{lane_id} journal {group} names differ",
        )
    referenced = {journal_path, sidecar}
    for entry in entries:
        path = root / entry["file"]
        _require(
            path.is_file()
            and path.stat().st_size == entry["bytes"]
            and sha256_file(path) == entry["sha256"],
            f"{lane_id} check {entry['ordinal']} differs",
        )
        record = json.loads(path.read_text(encoding="utf-8"))
        _require(
            record["schema"]
            == "RapidRBF/ReadyGatedControllerPreflightCheck/v1"
            and record["ordinal"] == entry["ordinal"]
            and record["name"] == entry["name"]
            and record["group"] == entry["group"]
            and record["status"] == entry["status"]
            and record["lane_id"] == lane_id
            and record["target"] == target,
            f"{lane_id} check {entry['ordinal']} identity differs",
        )
        if entry["group"] in {
            "native-helper-observation",
            "fast-exit-observation",
        }:
            streams = record["detail"]["diagnostic_streams"]
            _verify_stream(streams["stdout"], f"{lane_id}/{entry['name']} stdout")
            _verify_stream(streams["stderr"], f"{lane_id}/{entry['name']} stderr")
        referenced.add(path)
    return {
        "file": journal_path.name,
        "bytes": journal_path.stat().st_size,
        "sha256": sha256_file(journal_path),
        "sidecar": sidecar.name,
        "completed_check_count": EXPECTED_CHECKS,
        "referenced_paths": referenced,
    }
