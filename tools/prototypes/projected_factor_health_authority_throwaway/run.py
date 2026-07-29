"""One-command runner for the issue-46 authority and plan prototype."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from model import derive_adversarial_cards, derive_boundary_cards


ROOT = Path(__file__).resolve().parent
DIAGNOSIS = ROOT.parent / "projected_source_health_diagnosis_throwaway"
DIAGNOSIS_PLAN = DIAGNOSIS / "diagnosis-plan.v1.json"
DIAGNOSIS_EVIDENCE = DIAGNOSIS / "evidence" / "diagnosis-evidence.json"
AUTHORITY_PROFILE = ROOT / "authority-profile.v1.json"
REQUALIFICATION_PLAN = ROOT / "requalification-plan.v1.json"
EVIDENCE_DIR = ROOT / "evidence"
EVIDENCE_JSON = EVIDENCE_DIR / "authority-evidence.json"
SUMMARY_MD = EVIDENCE_DIR / "observed-results.md"
REPRODUCTION_JSON = EVIDENCE_DIR / "reproduction.json"

EXPECTED_DIAGNOSIS_PLAN_SHA256 = (
    "fb36f808157131c203dd8209450bde9f4a440ec0ca5f52cf0511b0e53bcd3001"
)
EXPECTED_DIAGNOSIS_EVIDENCE_SHA256 = (
    "b5dbe24ace553df3d390673feef5cad1912bdc8130d97875739f13e8512587d2"
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def has_forbidden_authority_input(authority: dict[str, Any]) -> bool:
    frozen_inputs = authority["frozen_inputs"]
    independence = authority["independence"]
    forbidden_top_level = {
        "candidate_binding",
        "candidate_factor",
        "candidate_solution",
        "candidate_observation",
    }
    return bool(forbidden_top_level.intersection(authority)) or any(
        key.startswith("candidate_")
        for key in frozen_inputs
        if key != "candidate_value"
    ) or "candidate binding" not in " ".join(
        independence["forbidden_reference_inputs"]
    )


def boundary_payload(card: Any) -> dict[str, Any]:
    value = asdict(card)
    value["workload"] = value.pop("workload")
    return value


def summary_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# Observed results — projected-factor solution-health repair",
        "",
        f"Disposition: `{evidence['disposition']}`",
        "",
        "This is a boundary prototype and frozen requalification plan, not a "
        "216-source candidate judgment.",
        "",
        "## Frozen identities",
        "",
        f"- Replacement authority: `{evidence['authority_profile_sha256']}`.",
        f"- Requalification plan: `{evidence['requalification_plan_sha256']}`.",
        f"- Accepted issue-45 evidence: `{EXPECTED_DIAGNOSIS_EVIDENCE_SHA256}`.",
        "",
        "## Boundary witnesses",
        "",
        "| Ordinal | Workload | Old | Repaired | Candidate/reference interval | Threshold |",
        "| ---: | --- | --- | --- | ---: | ---: |",
    ]
    for card in evidence["boundaries"]:
        distance = card["candidate_distance"]
        lines.append(
            f"| {card['ordinal']} | `{card['workload']}` | `{card['old_status']}` "
            f"| `{card['new_status']}` | "
            f"`[{distance['lower']:.6e}, {distance['upper']:.6e}]` | "
            f"`{card['threshold']:.6e}` |"
        )
    lines.extend(
        [
            "",
            "Ordinal 72 changes from old `FAIL` to repaired `PASS`: its candidate "
            "solution is inside the unchanged threshold around the frozen-`(A,b)` "
            "reference. Ordinals 69 and 150 remain `FAIL`, demonstrating that the "
            "repair is not a blanket accommodation for the candidate. The projected "
            "passing control remains `PASS`.",
            "",
            "## Adversarial guards",
            "",
        ]
    )
    for card in evidence["adversarial"]:
        mark = "PASS" if card["status"] == card["expected"] else "FAIL"
        lines.append(
            f"- `{mark}` — **{card['case_id']}**: `{card['status']}`. "
            f"{card['explanation']}"
        )
    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            "The declared vector remains only the frozen RHS-construction input and a "
            "diagnostic. The exact binary64 system is authoritative. A directed-rounding "
            "reference certificate owns oracle uncertainty; overlap is "
            "`INDETERMINATE`, never a pass. The full cohort remains unexecuted and "
            "unjudged.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    require(DIAGNOSIS_PLAN.is_file(), "accepted issue-45 diagnosis plan is missing")
    require(
        sha256_file(DIAGNOSIS_PLAN) == EXPECTED_DIAGNOSIS_PLAN_SHA256,
        "accepted issue-45 diagnosis plan differs",
    )
    require(
        DIAGNOSIS_EVIDENCE.is_file(),
        "accepted issue-45 diagnosis evidence is missing",
    )
    require(
        sha256_file(DIAGNOSIS_EVIDENCE) == EXPECTED_DIAGNOSIS_EVIDENCE_SHA256,
        "accepted issue-45 diagnosis evidence differs",
    )

    authority = json.loads(AUTHORITY_PROFILE.read_text(encoding="utf-8"))
    plan = json.loads(REQUALIFICATION_PLAN.read_text(encoding="utf-8"))
    authority_sha256 = sha256_file(AUTHORITY_PROFILE)
    require(
        plan["authorities"]["replacement_solution_health"]["sha256"]
        == authority_sha256,
        "requalification plan does not bind the exact authority profile",
    )
    require(
        not has_forbidden_authority_input(authority),
        "authority profile contains a forbidden candidate input",
    )
    require(
        plan["numeric_judgment"]["solution_relative_inf_max"] == "256*n*2^-53",
        "requalification threshold differs",
    )
    require(
        plan["cohort"]["logical_factor_sources"] == 216
        and plan["cohort"]["targets"] == 4
        and plan["cohort"]["profiles_per_target"] == 3,
        "requalification cohort shape differs",
    )

    diagnosis_evidence = json.loads(
        DIAGNOSIS_EVIDENCE.read_text(encoding="utf-8")
    )
    boundaries = derive_boundary_cards(diagnosis_evidence)
    adversarial = derive_adversarial_cards(boundaries)
    by_ordinal = {card.ordinal: card for card in boundaries}

    closure = {
        "frozen_issue_45_evidence_verified": True,
        "authority_excludes_candidate_inputs": not has_forbidden_authority_input(
            authority
        ),
        "unchanged_threshold_bound": (
            plan["numeric_judgment"]["solution_relative_inf_max"]
            == "256*n*2^-53"
        ),
        "passing_control_preserved": by_ordinal[0].new_status == "PASS",
        "nearest_declared_vector_false_failure_repaired": (
            by_ordinal[72].old_status == "FAIL"
            and by_ordinal[72].new_status == "PASS"
        ),
        "candidate_not_blanket_accommodated": (
            by_ordinal[69].new_status == "FAIL"
            and by_ordinal[150].new_status == "FAIL"
        ),
        "all_adversarial_guards_close": all(
            card.status == card.expected for card in adversarial
        ),
        "full_cohort_remains_unexecuted": (
            not plan["scope"]["executes_or_prejudges_cohort"]
        ),
    }
    disposition = (
        "REPLACEMENT_HEALTH_AUTHORITY_AND_PLAN_FROZEN"
        if all(closure.values())
        else "AUTHORITY_REPAIR_NOT_YET_CERTIFIABLE"
    )
    evidence = {
        "schema": "RapidRBF/ProjectedFactorHealthAuthorityEvidence/v1",
        "disposition": disposition,
        "authority_profile_sha256": authority_sha256,
        "requalification_plan_sha256": sha256_file(REQUALIFICATION_PLAN),
        "accepted_diagnosis": {
            "plan_sha256": EXPECTED_DIAGNOSIS_PLAN_SHA256,
            "evidence_sha256": EXPECTED_DIAGNOSIS_EVIDENCE_SHA256,
            "disposition": diagnosis_evidence["disposition"],
        },
        "boundaries": [boundary_payload(card) for card in boundaries],
        "adversarial": [asdict(card) for card in adversarial],
        "closure": closure,
        "scope": {
            "full_requalification_executed": False,
            "candidate_or_corpus_admitted": False,
            "mechanism_panel_run": False,
            "factor_storage_selected": False,
            "entered_100k_rung": False,
        },
    }
    reproduction = {
        "schema": "RapidRBF/ProjectedFactorHealthAuthorityReproduction/v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "authority_profile_sha256": authority_sha256,
        "requalification_plan_sha256": sha256_file(REQUALIFICATION_PLAN),
        "diagnosis_plan_sha256": sha256_file(DIAGNOSIS_PLAN),
        "diagnosis_evidence_sha256": sha256_file(DIAGNOSIS_EVIDENCE),
        "evidence_sha256": sha256_bytes(canonical_json(evidence)),
        "command": (
            "python tools/prototypes/"
            "projected_factor_health_authority_throwaway/run.py"
        ),
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_JSON.write_bytes(canonical_json(evidence))
    SUMMARY_MD.write_text(summary_markdown(evidence), encoding="utf-8")
    REPRODUCTION_JSON.write_bytes(canonical_json(reproduction))
    print(
        json.dumps(
            {
                "disposition": disposition,
                "authority_profile_sha256": authority_sha256,
                "requalification_plan_sha256": sha256_file(
                    REQUALIFICATION_PLAN
                ),
                "boundary_statuses": {
                    str(card.ordinal): card.new_status for card in boundaries
                },
                "evidence": str(EVIDENCE_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise SystemExit(f"authority prototype failed: {error}") from error
