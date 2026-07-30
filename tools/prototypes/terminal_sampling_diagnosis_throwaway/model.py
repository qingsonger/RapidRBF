"""THROWAWAY state model for Issue 54 terminal-sampling diagnosis."""

from __future__ import annotations

from typing import Any


RECONCILIATION_NS = 1_000_000_000


def legacy_classification(trace: dict[str, Any]) -> str:
    """Replay the exact Issue 53 eligibility rule."""
    error = trace["error"]
    eligible = (
        error["adapter"] == "macos-proc_pidinfo"
        and error["errno"] == 3
        and error["error_name"] == "ESRCH"
        and error["root_taskinfo"]
    )
    if not eligible:
        return "INVALID_CONTROLLER_EVIDENCE"
    if not _terminal_closes(trace):
        return "INVALID_CONTROLLER_EVIDENCE"
    return "BENIGN_TERMINAL_RACE"


def diagnostic_boundary_classification(trace: dict[str, Any]) -> str:
    """Classify only facts a successor diagnostic must capture explicitly."""
    error = trace["error"]
    if error["errno"] != 3 or error["error_name"] != "ESRCH":
        return "INVALID_CONTROLLER_EVIDENCE"
    if error.get("subject_pid") is None:
        return "UNJUDGED_MISSING_ROOT_BINDING"
    if error["subject_pid"] != trace["root_pid"]:
        return "INCOMPLETE_NONROOT_SAMPLE"
    if not _terminal_closes(trace):
        return "INVALID_CONTROLLER_EVIDENCE"
    return "BENIGN_ROOT_TERMINAL_CLOSURE"


def _terminal_closes(trace: dict[str, Any]) -> bool:
    terminal_ns = trace.get("terminal_ns")
    return (
        trace.get("same_handle_terminal") is True
        and isinstance(terminal_ns, int)
        and terminal_ns >= trace["sample_started_ns"]
        and terminal_ns <= trace["error_finished_ns"] + RECONCILIATION_NS
    )
