"""THROWAWAY prototype of the Issue 50 controller state machine.

The question is whether one external observer can preserve hard thread
evidence while treating only a reconciled macOS proc_pidinfo ESRCH as a
normal terminal race. The reducer is pure; I/O belongs in the TUI or in the
future execution-ticket controller.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


RECONCILIATION_WINDOW_MS = 1_000


def initial_state(grant: int = 12) -> dict[str, Any]:
    return {
        "phase": "NOT_STARTED",
        "process_token": None,
        "pid_diagnostic": None,
        "grant": grant,
        "candidate_entry": False,
        "successful_samples": 0,
        "maximum_live_threads": 0,
        "last_process_inventory": [],
        "benign_terminal_races": 0,
        "pending_absence": None,
        "terminal": None,
        "timed_out": False,
        "invalidity": [],
        "verdict": "PENDING",
        "history": [],
    }


def _record(state: dict[str, Any], action: dict[str, Any]) -> None:
    state["history"].append(deepcopy(action))


def _invalidate(state: dict[str, Any], reason: str) -> None:
    state["phase"] = "INVALID"
    state["invalidity"].append(reason)
    state["verdict"] = "INVALID_CONTROLLER_EVIDENCE"


def _same_process(state: dict[str, Any], action: dict[str, Any]) -> bool:
    return action.get("process_token") == state["process_token"]


def _accept_terminal_race(state: dict[str, Any]) -> None:
    state["benign_terminal_races"] += 1
    state["pending_absence"] = None


def _finalize(state: dict[str, Any]) -> None:
    if state["invalidity"]:
        state["verdict"] = "INVALID_CONTROLLER_EVIDENCE"
    elif not state["candidate_entry"]:
        _invalidate(state, "process terminated before the frozen candidate-entry marker")
    elif state["successful_samples"] == 0:
        _invalidate(state, "no successful live-process thread sample")
    elif state["maximum_live_threads"] > state["grant"]:
        state["verdict"] = "VALID_CANDIDATE_OWNED_THREAD_FAILURE"
    elif state["timed_out"]:
        state["verdict"] = "VALID_CANDIDATE_OWNED_PROCESS_FAILURE"
    else:
        state["verdict"] = "VALID_THREAD_EVIDENCE_PASS"


def reduce(state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    """Return a new controller state after one serialized observer event."""

    next_state = deepcopy(state)
    kind = action["type"]
    _record(next_state, action)

    if next_state["phase"] == "INVALID":
        return next_state

    if kind == "launch":
        if next_state["phase"] != "NOT_STARTED":
            _invalidate(next_state, "launch outside NOT_STARTED")
        else:
            next_state["phase"] = "LIVE"
            next_state["process_token"] = action["process_token"]
            next_state["pid_diagnostic"] = action["pid"]
        return next_state

    if not _same_process(next_state, action):
        _invalidate(next_state, "event does not belong to the launched process handle")
        return next_state

    if kind == "candidate_entry":
        if next_state["phase"] != "LIVE":
            _invalidate(next_state, "candidate entry outside LIVE")
        elif next_state["candidate_entry"]:
            _invalidate(next_state, "duplicate candidate-entry marker")
        else:
            next_state["candidate_entry"] = True
        return next_state

    if kind == "sample_ok":
        if next_state["phase"] != "LIVE":
            _invalidate(next_state, "successful sample outside LIVE")
        elif not isinstance(action.get("threads"), int) or action["threads"] < 1:
            _invalidate(
                next_state,
                "successful process-tree sample did not report a positive count",
            )
        else:
            inventory = action.get("processes")
            identities = [
                item.get("process_identity")
                for item in inventory
                if isinstance(item, dict)
            ] if isinstance(inventory, list) else []
            inventory_valid = (
                isinstance(inventory, list)
                and bool(inventory)
                and len(identities) == len(inventory)
                and len(set(identities)) == len(identities)
                and state["process_token"] in identities
                and all(
                    isinstance(item.get("threads"), int) and item["threads"] >= 1
                    for item in inventory
                )
                and sum(item["threads"] for item in inventory) == action["threads"]
            )
            if not inventory_valid:
                _invalidate(
                    next_state,
                    "process-tree inventory is incomplete, duplicated, or inconsistent",
                )
                return next_state
            next_state["successful_samples"] += 1
            next_state["maximum_live_threads"] = max(
                next_state["maximum_live_threads"], action["threads"]
            )
            next_state["last_process_inventory"] = deepcopy(inventory)
        return next_state

    if kind == "sample_error":
        eligible_esrch = (
            action.get("adapter") == "macos-proc_pidinfo"
            and action.get("errno") == 3
            and action.get("error_name") == "ESRCH"
        )
        if not eligible_esrch:
            _invalidate(next_state, "sampling error is not the one eligible ESRCH case")
            return next_state

        sample_started_ms = action["sample_started_ms"]
        sample_finished_ms = action["sample_finished_ms"]
        if next_state["phase"] == "LIVE":
            next_state["phase"] = "RECONCILING_PROCESS_ABSENT"
            next_state["pending_absence"] = {
                "sample_started_ms": sample_started_ms,
                "sample_finished_ms": sample_finished_ms,
                "reconcile_by_ms": sample_finished_ms + RECONCILIATION_WINDOW_MS,
                "raw_error": "[Errno 3] proc_pidinfo",
            }
        elif next_state["phase"] == "TERMINAL_OBSERVED":
            terminal_ms = next_state["terminal"]["observed_ms"]
            if sample_started_ms <= terminal_ms <= sample_finished_ms:
                _accept_terminal_race(next_state)
            else:
                _invalidate(
                    next_state,
                    "ESRCH sample was not in flight across the terminal observation",
                )
        else:
            _invalidate(next_state, "ESRCH outside a live-to-terminal sampling race")
        return next_state

    if kind == "terminal_observed":
        if next_state["phase"] == "LIVE":
            next_state["phase"] = "TERMINAL_OBSERVED"
        elif next_state["phase"] == "RECONCILING_PROCESS_ABSENT":
            pending = next_state["pending_absence"]
            if action["observed_ms"] > pending["reconcile_by_ms"]:
                _invalidate(next_state, "ESRCH was not reconciled within 1000 ms")
                return next_state
            if pending["sample_started_ms"] > action["observed_ms"]:
                _invalidate(next_state, "ESRCH sample began after terminal observation")
                return next_state
            _accept_terminal_race(next_state)
            next_state["phase"] = "TERMINAL_OBSERVED"
        else:
            _invalidate(next_state, "terminal event outside LIVE or reconciliation")
            return next_state
        next_state["terminal"] = {
            "observed_ms": action["observed_ms"],
            "returncode": action["returncode"],
            "source": "sole-waiter",
        }
        return next_state

    if kind == "reconciliation_expired":
        if next_state["phase"] != "RECONCILING_PROCESS_ABSENT":
            _invalidate(next_state, "reconciliation expiry without pending ESRCH")
        else:
            _invalidate(next_state, "ESRCH was not paired to the same child terminal event")
        return next_state

    if kind == "timeout":
        if next_state["phase"] not in {"LIVE", "RECONCILING_PROCESS_ABSENT"}:
            _invalidate(next_state, "timeout outside a live process")
        else:
            next_state["timed_out"] = True
            next_state["pending_absence"] = None
            next_state["phase"] = "TERMINAL_OBSERVED"
            next_state["terminal"] = {
                "observed_ms": action["observed_ms"],
                "returncode": action["returncode"],
                "source": "controller-timeout-kill-and-wait",
            }
        return next_state

    if kind == "reap":
        if next_state["phase"] != "TERMINAL_OBSERVED":
            _invalidate(next_state, "reap before a terminal result")
        elif action["returncode"] != next_state["terminal"]["returncode"]:
            _invalidate(next_state, "reaped result differs from the waiter result")
        else:
            next_state["phase"] = "REAPED"
            _finalize(next_state)
        return next_state

    _invalidate(next_state, f"unknown action: {kind}")
    return next_state


def scenario_catalog() -> dict[str, dict[str, Any]]:
    token = "invocation-7f2c"

    def event(kind: str, **values: Any) -> dict[str, Any]:
        return {"type": kind, "process_token": token, **values}

    launch = event("launch", pid=4312)
    entry = event("candidate_entry")
    def sample(threads: int) -> dict[str, Any]:
        return event(
            "sample_ok",
            threads=threads,
            processes=[{"process_identity": token, "threads": threads}],
        )

    sample_2 = sample(2)

    return {
        "issue49_esrch_exit": {
            "description": "The Issue 49 race becomes valid terminal closure.",
            "grant": 12,
            "expected": "VALID_THREAD_EVIDENCE_PASS",
            "actions": [
                launch,
                entry,
                sample_2,
                sample(3),
                event(
                    "sample_error",
                    adapter="macos-proc_pidinfo",
                    errno=3,
                    error_name="ESRCH",
                    sample_started_ms=200,
                    sample_finished_ms=202,
                ),
                event("terminal_observed", observed_ms=206, returncode=0),
                event("reap", returncode=0),
            ],
        },
        "terminal_first_esrch_exit": {
            "description": "Waiter wins the race while one sample is already in flight.",
            "grant": 12,
            "expected": "VALID_THREAD_EVIDENCE_PASS",
            "actions": [
                launch,
                entry,
                sample_2,
                event("terminal_observed", observed_ms=200, returncode=0),
                event(
                    "sample_error",
                    adapter="macos-proc_pidinfo",
                    errno=3,
                    error_name="ESRCH",
                    sample_started_ms=199,
                    sample_finished_ms=201,
                ),
                event("reap", returncode=0),
            ],
        },
        "unpaired_esrch": {
            "description": "ESRCH without the same-handle terminal event invalidates evidence.",
            "grant": 12,
            "expected": "INVALID_CONTROLLER_EVIDENCE",
            "actions": [
                launch,
                entry,
                sample_2,
                event(
                    "sample_error",
                    adapter="macos-proc_pidinfo",
                    errno=3,
                    error_name="ESRCH",
                    sample_started_ms=200,
                    sample_finished_ms=202,
                ),
                event("reconciliation_expired", observed_ms=1203),
            ],
        },
        "other_sampling_error": {
            "description": "EPERM and every non-eligible error remain invalid.",
            "grant": 12,
            "expected": "INVALID_CONTROLLER_EVIDENCE",
            "actions": [
                launch,
                entry,
                sample_2,
                event(
                    "sample_error",
                    adapter="macos-proc_pidinfo",
                    errno=1,
                    error_name="EPERM",
                    sample_started_ms=200,
                    sample_finished_ms=202,
                ),
            ],
        },
        "over_grant": {
            "description": "A valid observation above the grant is candidate-owned failure.",
            "grant": 12,
            "expected": "VALID_CANDIDATE_OWNED_THREAD_FAILURE",
            "actions": [
                launch,
                entry,
                sample_2,
                sample(13),
                event("terminal_observed", observed_ms=500, returncode=0),
                event("reap", returncode=0),
            ],
        },
        "timeout_after_entry": {
            "description": "A timeout after entry is a valid candidate-owned process failure.",
            "grant": 12,
            "expected": "VALID_CANDIDATE_OWNED_PROCESS_FAILURE",
            "actions": [
                launch,
                entry,
                sample_2,
                event("timeout", observed_ms=7_200_000, returncode=-9),
                event("reap", returncode=-9),
            ],
        },
        "exit_before_entry": {
            "description": "No candidate-entry marker means the coordinate is invalid.",
            "grant": 12,
            "expected": "INVALID_CONTROLLER_EVIDENCE",
            "actions": [
                launch,
                sample_2,
                event("terminal_observed", observed_ms=20, returncode=2),
                event("reap", returncode=2),
            ],
        },
        "zero_successful_samples": {
            "description": "A terminal result cannot replace live thread evidence.",
            "grant": 12,
            "expected": "INVALID_CONTROLLER_EVIDENCE",
            "actions": [
                launch,
                entry,
                event("terminal_observed", observed_ms=20, returncode=0),
                event("reap", returncode=0),
            ],
        },
    }
