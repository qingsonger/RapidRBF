"""Pure Issue 57 evidence-path diagnosis and replacement-plan review model."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
FIXED_EVIDENCE = ROOT / "fixed-evidence.v1.json"
PLAN = ROOT / "replacement-execution-plan.v1.json"
VIEWS = ("diagnosis", "first-invalidity", "topology", "replacement", "scope")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixed_evidence() -> dict[str, Any]:
    return load_json(FIXED_EVIDENCE)


def load_plan() -> dict[str, Any]:
    return load_json(PLAN)


def diagnose(fixed: dict[str, Any]) -> dict[str, Any]:
    lanes = fixed["lanes"]
    producer = fixed["producer_verifier_identity"]["producer_name"]
    verifier = fixed["producer_verifier_identity"]["verifier_name"]
    names = {lane["identity_name"] for lane in lanes.values()}
    lane_gate_complete = all(
        lane["journal_status"] == "PASS"
        and lane["completed_check_count"] == 277
        and lane["identity_name"] == producer
        for lane in lanes.values()
    )
    matched = sorted(
        artifact["name"]
        for artifact in fixed["artifacts"]
        if fnmatch.fnmatchcase(
            artifact["name"], fixed["artifact_selector"]["faulty_pattern"]
        )
    )
    matched_kinds = sorted(
        artifact["kind"]
        for artifact in fixed["artifacts"]
        if artifact["name"] in matched
    )
    root = fixed["accepted_root_bound_aggregate"]
    return {
        "producer_verifier_contract_drift": (
            lane_gate_complete and names == {producer} and producer != verifier
        ),
        "artifact_kind_selection_alias": matched_kinds
        == [
            "lane-preflight",
            "lane-preflight",
            "lane-preflight",
            "lane-preflight",
            "preflight-release",
        ],
        "matched_artifacts": matched,
        "accepted_root_bound_gate_intact": (
            root["status"] == "ROOT_BOUND_FOUR_LANE_ZERO_ENTRY_PREFLIGHT_PASS"
            and root["inherited_ready_gated_check_count"] == 1108
            and root["root_bound_check_count"] == 100
        ),
        "candidate_owned_failure": False,
        "candidate_entry_count": fixed["final_cohort"]["candidate_entry_count"],
        "candidate_observation_count": fixed["final_cohort"][
            "candidate_observation_count"
        ],
        "first_invalidity": fixed["producer_verifier_identity"]["first_failure"],
        "final_duplicate_root_bound_cohorts": fixed["artifact_selector"][
            "resulting_root_bound_preflight_cohort_count"
        ],
    }


def validate_replacement(plan: dict[str, Any]) -> dict[str, Any]:
    contract = plan["replacement_contract"]
    authority = contract["authority_check"]
    artifacts = contract["artifact_identity"]
    lane_names = set(artifacts["lane_preflight_names"].values())
    target_names = set(artifacts["target_names"].values())
    singleton_names = {
        artifacts["preflight_release_name"],
        artifacts["reference_name"],
        artifacts["cohort_name"],
    }
    all_names = lane_names | target_names | singleton_names
    inventory = contract["output_inventory"]
    before = inventory["before_candidate_entry"]
    return {
        "single_authority_definition": authority["single_definition"]
        == "preflight_journal.AUTHORITY_CHECK_NAME",
        "producer_and_verifier_share_authority": (
            "imports and records the single definition"
            in authority["producer_rule"]
            and "verifies the same definition" in authority["verifier_rule"]
        ),
        "exact_artifact_names_unique": len(all_names)
        == len(lane_names) + len(target_names) + len(singleton_names),
        "patterns_forbidden": "Patterns" in artifacts["download_rule"],
        "recursive_singleton_discovery_forbidden": (
            "recursive basename discovery is forbidden"
            in contract["filesystem_topology"]["discovery_rule"]
        ),
        "zero_entry_inventory_complete": (
            before["lane_artifacts"] == 4
            and before["ready_gated_checks"] == 1108
            and before["root_bound_checks"] == 100
            and before["root_bound_preflight_cohorts"] == 1
            and before["candidate_entry_unlocks"] == 1
            and before["candidate_entries"] == 0
            and before["candidate_observations"] == 0
        ),
        "one_attempt_noncompensating": (
            plan["fresh_execution"]["attempt_count"] == 1
            and not plan["fresh_execution"]["automatic_retry_permitted"]
            and not plan["fresh_execution"]["workflow_rerun_permitted"]
            and not plan["fresh_execution"]["partial_retry_permitted"]
            and not plan["fresh_execution"]["replacement_retry_permitted"]
            and not plan["fresh_execution"]["attempt_mixing_permitted"]
        ),
        "controller_gate_unchanged": (
            plan["fixed_authority"][
                "accepted_root_bound_controller_binding_sha256"
            ]
            == "1370ecd1ee86ca569d53b5f474dc861879ae252c34544599d5fb2c2e84ca0409"
        ),
    }


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


def view_data(
    state: dict[str, Any], fixed: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    view = state["view"]
    if view == "diagnosis":
        return {
            "proposed_disposition": plan["proposed_disposition"],
            "diagnosis": diagnose(fixed),
            "decision_text": plan["diagnosis"],
        }
    if view == "first-invalidity":
        return {
            "producer_verifier_identity": fixed["producer_verifier_identity"],
            "lanes": fixed["lanes"],
            "accepted_root_bound_aggregate": fixed[
                "accepted_root_bound_aggregate"
            ],
        }
    if view == "topology":
        return {
            "issue_56_selector": fixed["artifact_selector"],
            "issue_56_final_cohort": fixed["final_cohort"],
            "replacement_artifact_identity": plan["replacement_contract"][
                "artifact_identity"
            ],
            "replacement_filesystem_topology": plan["replacement_contract"][
                "filesystem_topology"
            ],
        }
    if view == "replacement":
        return {
            "validation": validate_replacement(plan),
            "replacement_contract": plan["replacement_contract"],
            "fresh_execution": plan["fresh_execution"],
        }
    return {
        "review_state": plan["review_state"],
        "fixed_authority": plan["fixed_authority"],
        "unchanged_gates": plan["unchanged_gates"],
        "forbidden_here": plan["forbidden_here"],
    }
