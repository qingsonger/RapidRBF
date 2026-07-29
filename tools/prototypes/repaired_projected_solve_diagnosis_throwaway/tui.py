#!/usr/bin/env python3
"""Tiny in-memory terminal reviewer for the issue-48 decision."""

from __future__ import annotations

import argparse
import json
from typing import Any

from model import PLAN_PATH, analyze


SECTIONS = (
    "summary",
    "witnesses",
    "hypotheses",
    "experiment",
    "scope",
)


def render(state: dict[str, Any], result: dict[str, Any], plan: dict[str, Any]) -> str:
    section = state["section"]
    lines = [
        "=== ISSUE 48 THROWAWAY REVIEWER ===",
        f"section: {section}",
        f"review proposal (memory only): {state['review_proposal']}",
        f"disposition: {result['disposition']}",
        "",
    ]
    if section == "summary":
        mechanism = result["proven_mechanism"]
        lines.extend(
            [
                result["proven_mechanism"]["statement"],
                "",
                "Closure:",
                f"- 12-lane vectors identical: "
                f"{mechanism['all_12_observations_share_status_vectors']}",
                f"- reconstruction/backward/bit-exact side gates pass: "
                f"{mechanism['all_selected_side_gates_pass']}",
                f"- ordinal 106 failing families: "
                f"{mechanism['ordinal_106_failing_families']}",
                f"- raw LU/equilibration fail accepted extremes: "
                f"{mechanism['raw_full_pivot_and_equilibration_fail_extremes']}",
                f"- selected pre/post red coordinates: "
                f"{result['feedback_loop']['pre_and_post_reference_solution_failures']}",
            ]
        )
    elif section == "witnesses":
        for witness in result["witnesses"]:
            family_state = ", ".join(
                f"{family['family']}="
                f"{'/'.join(family['pre_pack_statuses'])}"
                f"@{family['minimum_threshold_ratio_lower']:.4g}x"
                for family in witness["families"]
            )
            lines.extend(
                [
                    f"- ordinal {witness['ordinal']} | {witness['category']}",
                    f"  {witness['workload_id']} n/rank="
                    f"{witness['dimension']}/{witness['expected_rank']}",
                    f"  {family_state}",
                    f"  backward gate fraction <= "
                    f"{witness['maximum_backward_gate_fraction']:.4g}; "
                    f"reconstruction <= "
                    f"{witness['maximum_reconstruction_gate_fraction']:.4g}",
                ]
            )
    elif section == "hypotheses":
        for hypothesis in result["hypotheses"]:
            lines.extend(
                [
                    f"{hypothesis['rank']}. {hypothesis['name']}",
                    f"   status: {hypothesis['status']}",
                    f"   prediction: {hypothesis['prediction']}",
                    f"   evidence: "
                    f"{hypothesis.get('observation', hypothesis.get('remaining_uncertainty'))}",
                ]
            )
    elif section == "experiment":
        boundary = plan["selected_candidate_boundary"]
        matrix = plan["execution_matrix"]
        lines.extend(
            [
                f"Candidate: {boundary['name']}",
                f"Factor: {boundary['factorization']}",
                f"Residual: {boundary['residual']}",
                f"Correction: {boundary['correction']}",
                f"Terminal rounding: {boundary['terminal_rounding']}",
                f"Maximum refinement steps: "
                f"{boundary['maximum_refinement_steps']}",
                f"Materialization: {boundary['materialization_rule']}",
                "",
                f"Matrix: {matrix['logical_sources_per_observation']} sources x "
                f"{matrix['rhs_families_per_source']} RHS x "
                f"{matrix['target_profile_observations']} target/profiles",
                "Dispositions:",
            ]
        )
        for name, meaning in plan["dispositions"].items():
            lines.append(f"- {name}: {meaning}")
    elif section == "scope":
        lines.append("Scope flags:")
        for name, value in result["scope"].items():
            lines.append(f"- {name}: {value}")
        lines.extend(
            [
                "",
                "Live review choices:",
                "- accept: record NEXT_DENSE_FACTOR_EXPERIMENT_FROZEN",
                "- adjust: identify an exact witness, control, or plan change",
                "- reject: identify the unsupported mechanism or route choice",
            ]
        )
    lines.extend(
        [
            "",
            "Actions: [n]ext [p]revious [a]ccept proposal "
            "[j]adjust proposal [r]eject proposal [q]uit",
        ]
    )
    return "\n".join(lines)


def snapshot(result: dict[str, Any], plan: dict[str, Any]) -> str:
    parts = []
    for section in SECTIONS:
        parts.append(
            render(
                {"section": section, "review_proposal": "PENDING"},
                result,
                plan,
            )
        )
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    result = analyze()
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if args.snapshot:
        print(snapshot(result, plan))
        return 0

    state = {"section": SECTIONS[0], "review_proposal": "PENDING"}
    while True:
        print("\033[2J\033[H", end="")
        print(render(state, result, plan))
        action = input("> ").strip().lower()
        if action == "q":
            return 0
        if action == "n":
            index = (SECTIONS.index(state["section"]) + 1) % len(SECTIONS)
            state["section"] = SECTIONS[index]
        elif action == "p":
            index = (SECTIONS.index(state["section"]) - 1) % len(SECTIONS)
            state["section"] = SECTIONS[index]
        elif action == "a":
            state["review_proposal"] = "ACCEPT (not recorded)"
        elif action == "j":
            state["review_proposal"] = "ADJUST (not recorded)"
        elif action == "r":
            state["review_proposal"] = "REJECT (not recorded)"


if __name__ == "__main__":
    raise SystemExit(main())
