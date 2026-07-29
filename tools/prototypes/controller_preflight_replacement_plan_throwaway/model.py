"""Pure review state for the Issue 52 replacement-plan prototype."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "replacement-execution-plan.v1.json"
VIEWS = ("diagnosis", "boundary", "execution", "scope")


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def initial_state(view: str = "diagnosis") -> dict[str, Any]:
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
    if view == "diagnosis":
        return {
            "decision": plan["decision"],
            "adjudication": plan["diagnosis"]["adjudication"],
            "root_cause": plan["diagnosis"]["root_cause"],
            "platform_findings": plan["diagnosis"]["platform_findings"],
        }
    if view == "boundary":
        return plan["controller_evidence_boundary"]
    if view == "execution":
        return {
            "inherited_immutable_scope": plan["inherited_immutable_scope"],
            "replacement_execution_plan": plan["replacement_execution_plan"],
            "validation": plan["boundary_validation"],
        }
    return {
        "forbidden_here": plan["forbidden_here"],
        "predecessor": plan["predecessor"],
    }
