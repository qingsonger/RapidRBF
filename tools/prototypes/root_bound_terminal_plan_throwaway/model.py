"""Pure Issue 55 root-bound terminal-closure policy prototype."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "fresh-cohort-plan.v1.json"
RECONCILIATION_NS = 1_000_000_000
BENIGN = "BENIGN_ROOT_BOUND_TERMINAL_CLOSURE"
INVALID = "INVALID_CONTROLLER_EVIDENCE"
PASS = "PASS"
CANDIDATE_NONPASS = "VALID_CANDIDATE_OWNED_NONPASS"
VIEWS = ("decision", "record", "controls", "execution", "scope")

NATIVE_PHASES = {
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


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def classify_adapter_failure(record: dict[str, Any]) -> str:
    """Return BENIGN only for a fully evidenced root terminal closure."""
    required = (
        "adapter",
        "errno",
        "phase",
        "subject_pid",
        "root_pid",
        "invocation_nonce",
        "sample_started_ns",
        "sample_finished_ns",
        "terminal",
        "reap",
        "process_tree_cleanup",
        "prior_reconciliations",
        "incomplete_sample_effect",
    )
    if any(record.get(field) is None for field in required):
        return INVALID
    if record["errno"] != 3 or record.get("error_name") != "ESRCH":
        return INVALID
    if record["adapter"] not in NATIVE_PHASES:
        return INVALID
    if record["phase"] not in NATIVE_PHASES[record["adapter"]]:
        return INVALID
    if record["subject_pid"] != record["root_pid"]:
        return INVALID
    if record["sample_finished_ns"] < record["sample_started_ns"]:
        return INVALID

    nonce = record["invocation_nonce"]
    terminal = record["terminal"]
    reap = record["reap"]
    cleanup = record["process_tree_cleanup"]
    if (
        terminal.get("owner") != "sole-waiter"
        or terminal.get("invocation_nonce") != nonce
        or not isinstance(terminal.get("observed_ns"), int)
        or terminal["observed_ns"] < record["sample_started_ns"]
        or terminal["observed_ns"]
        > record["sample_finished_ns"] + RECONCILIATION_NS
    ):
        return INVALID
    if (
        reap.get("owner") != "sole-waiter"
        or reap.get("invocation_nonce") != nonce
        or not isinstance(reap.get("observed_ns"), int)
        or reap["observed_ns"] < terminal["observed_ns"]
    ):
        return INVALID
    if (
        cleanup.get("invocation_nonce") != nonce
        or cleanup.get("complete") is not True
        or not isinstance(cleanup.get("observed_ns"), int)
        or cleanup["observed_ns"] < reap["observed_ns"]
    ):
        return INVALID
    if record["prior_reconciliations"] != 0:
        return INVALID
    if record["incomplete_sample_effect"] != {
        "successful_sample_delta": 0,
        "sample_error_delta": 0,
        "maximum_live_threads_delta": 0,
    }:
        return INVALID
    return BENIGN


def classify_process_result(
    *,
    controller_record_valid: bool,
    returncode: int,
    timed_out: bool,
    maximum_live_threads: int,
    maximum_live_threads_grant: int,
) -> str:
    """Keep candidate-owned failures nonpassing after controller validity."""
    if not controller_record_valid:
        return INVALID
    if (
        returncode != 0
        or timed_out
        or maximum_live_threads > maximum_live_threads_grant
    ):
        return CANDIDATE_NONPASS
    return PASS


def base_record() -> dict[str, Any]:
    """A complete Linux group-membership root-closure witness."""
    nonce = "invocation-0001"
    return {
        "schema": "RapidRBF/RootBoundAdapterFailure/v1",
        "adapter": "linux-proc-process-tree",
        "errno": 3,
        "error_name": "ESRCH",
        "phase": "group-membership",
        "subject_pid": 4100,
        "root_pid": 4100,
        "invocation_nonce": nonce,
        "sample_started_ns": 10_000_000,
        "sample_finished_ns": 12_000_000,
        "terminal": {
            "owner": "sole-waiter",
            "invocation_nonce": nonce,
            "observed_ns": 13_000_000,
            "returncode": 0,
        },
        "reap": {
            "owner": "sole-waiter",
            "invocation_nonce": nonce,
            "observed_ns": 13_100_000,
        },
        "process_tree_cleanup": {
            "invocation_nonce": nonce,
            "observed_ns": 13_200_000,
            "complete": True,
        },
        "prior_reconciliations": 0,
        "incomplete_sample_effect": {
            "successful_sample_delta": 0,
            "sample_error_delta": 0,
            "maximum_live_threads_delta": 0,
        },
    }


def scenario_catalog() -> dict[str, dict[str, Any]]:
    """Deterministic positive and negative policy controls."""
    scenarios: dict[str, dict[str, Any]] = {}

    def add(
        name: str,
        expected: str,
        mutate: Any = None,
    ) -> None:
        record = base_record()
        if mutate is not None:
            mutate(record)
        scenarios[name] = {"record": record, "expected": expected}

    add("linux-group-membership-root-closure", BENIGN)
    add(
        "macos-bsd-identity-root-closure",
        BENIGN,
        lambda value: value.update(
            adapter="macos-proc-process-tree", phase="bsd-identity"
        ),
    )
    add("missing-subject-pid", INVALID, lambda value: value.update(subject_pid=None))
    add("missing-phase", INVALID, lambda value: value.update(phase=None))
    add("non-root-disappearance", INVALID, lambda value: value.update(subject_pid=4101))
    add(
        "non-esrch",
        INVALID,
        lambda value: value.update(errno=1, error_name="EPERM"),
    )
    add(
        "adapter-phase-mismatch",
        INVALID,
        lambda value: value.update(
            adapter="linux-proc-process-tree", phase="bsd-identity"
        ),
    )
    add(
        "wrong-handle",
        INVALID,
        lambda value: value["terminal"].update(invocation_nonce="other-invocation"),
    )
    add(
        "terminal-before-sample",
        INVALID,
        lambda value: value["terminal"].update(observed_ns=9_999_999),
    )
    add(
        "terminal-after-ceiling",
        INVALID,
        lambda value: value["terminal"].update(observed_ns=1_012_000_001),
    )
    add("missing-terminal", INVALID, lambda value: value.update(terminal=None))
    add(
        "missing-reap",
        INVALID,
        lambda value: value.update(reap=None),
    )
    add(
        "wrong-reap-owner",
        INVALID,
        lambda value: value["reap"].update(owner="sampler"),
    )
    add(
        "repeated-reconciliation",
        INVALID,
        lambda value: value.update(prior_reconciliations=1),
    )
    add(
        "incomplete-cleanup",
        INVALID,
        lambda value: value["process_tree_cleanup"].update(complete=False),
    )
    add(
        "incomplete-sample-counted",
        INVALID,
        lambda value: value["incomplete_sample_effect"].update(
            successful_sample_delta=1
        ),
    )
    return scenarios


def evaluate_scenarios() -> dict[str, Any]:
    results = {}
    for name, scenario in scenario_catalog().items():
        observed = classify_adapter_failure(copy.deepcopy(scenario["record"]))
        results[name] = {
            "expected": scenario["expected"],
            "observed": observed,
            "passed": observed == scenario["expected"],
        }
    process_results = {
        "clean": classify_process_result(
            controller_record_valid=True,
            returncode=0,
            timed_out=False,
            maximum_live_threads=12,
            maximum_live_threads_grant=12,
        ),
        "candidate-exit": classify_process_result(
            controller_record_valid=True,
            returncode=7,
            timed_out=False,
            maximum_live_threads=1,
            maximum_live_threads_grant=12,
        ),
        "candidate-timeout": classify_process_result(
            controller_record_valid=True,
            returncode=0,
            timed_out=True,
            maximum_live_threads=1,
            maximum_live_threads_grant=12,
        ),
        "candidate-thread-grant": classify_process_result(
            controller_record_valid=True,
            returncode=0,
            timed_out=False,
            maximum_live_threads=13,
            maximum_live_threads_grant=12,
        ),
        "controller-invalid": classify_process_result(
            controller_record_valid=False,
            returncode=0,
            timed_out=False,
            maximum_live_threads=1,
            maximum_live_threads_grant=12,
        ),
    }
    expected_process = {
        "clean": PASS,
        "candidate-exit": CANDIDATE_NONPASS,
        "candidate-timeout": CANDIDATE_NONPASS,
        "candidate-thread-grant": CANDIDATE_NONPASS,
        "controller-invalid": INVALID,
    }
    return {
        "adapter_failure_controls": results,
        "process_result_controls": {
            name: {
                "expected": expected_process[name],
                "observed": observed,
                "passed": observed == expected_process[name],
            }
            for name, observed in process_results.items()
        },
    }


def initial_state(view: str = "decision") -> dict[str, Any]:
    if view not in VIEWS:
        raise ValueError(f"unknown view: {view}")
    return {"view": view, "views": list(VIEWS), "index": VIEWS.index(view)}


def reduce(state: dict[str, Any], action: str) -> dict[str, Any]:
    index = state["index"]
    if action == "next":
        index = (index + 1) % len(VIEWS)
    elif action == "previous":
        index = (index - 1) % len(VIEWS)
    elif action in VIEWS:
        index = VIEWS.index(action)
    else:
        raise ValueError(f"unknown action: {action}")
    return {"view": VIEWS[index], "views": list(VIEWS), "index": index}


def view_data(state: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    view = state["view"]
    if view == "decision":
        return {
            "disposition": plan["disposition"],
            "question": plan["question"],
            "validation": plan["validation"],
        }
    if view == "record":
        return plan["controller_boundary"]
    if view == "controls":
        return evaluate_scenarios()
    if view == "execution":
        return {
            "inherited_scope": plan["inherited_immutable_scope"],
            "fresh_execution_plan": plan["fresh_execution_plan"],
        }
    return {
        "forbidden_here": plan["forbidden_here"],
        "identity_and_non_reuse": plan["identity_and_non_reuse"],
    }
