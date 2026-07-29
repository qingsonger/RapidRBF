"""Verify one non-compensating, same-attempt four-lane issue-44 cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


FEASIBLE = "FEASIBLE_FOR_216_FACTOR_QUALIFICATION"
REJECTED = "EVIDENCE_BACKED_REJECTED"
UNJUDGED = "UNJUDGED_EVIDENCE_MISSING"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_lane(evidence: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    candidate = evidence.get("candidate", {})
    lane = evidence.get("lane_witness", {})
    if lane.get("qualification") != "PASS":
        reasons.append("lane witness is not qualified")
    if candidate.get("lane_id") != evidence.get("lane_id"):
        reasons.append("candidate lane id differs")
    if candidate.get("target") != evidence.get("target"):
        reasons.append("candidate target differs")
    if evidence.get("disposition") != candidate.get("disposition"):
        reasons.append("wrapper and candidate dispositions differ")
    if evidence.get("temporary_storage", {}).get("candidate_scratch_before") != []:
        reasons.append("candidate scratch was not initially empty")
    if evidence.get("temporary_storage", {}).get("candidate_scratch_after") != []:
        reasons.append("candidate wrote temporary storage")
    if not evidence.get("temporary_storage", {}).get(
        "scratch_removed_after_observation"
    ):
        reasons.append("candidate scratch cleanup did not close")
    if evidence.get("disposition") not in {FEASIBLE, REJECTED, UNJUDGED}:
        reasons.append("forbidden lane disposition")
    return not reasons, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract_bytes = args.contract.read_bytes()
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest()
    contract = json.loads(contract_bytes)
    required = contract["judgment"]["required_lanes"]
    paths = sorted(args.evidence_root.rglob("lane-observation.json"))
    records: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for path in paths:
        evidence = json.loads(path.read_text(encoding="utf-8"))
        lane_id = evidence.get("lane_id")
        if lane_id in records:
            problems.append(f"duplicate lane evidence for {lane_id}")
            continue
        if lane_id not in required:
            problems.append(f"unexpected lane evidence for {lane_id}")
            continue
        valid, reasons = check_lane(evidence)
        if not valid:
            problems.extend(f"{lane_id}: {reason}" for reason in reasons)
        if evidence.get("execution_contract", {}).get("sha256") != contract_sha256:
            problems.append(f"{lane_id}: execution contract differs")
        records[lane_id] = {"path": path, "evidence": evidence}

    missing = [lane_id for lane_id in required if lane_id not in records]
    problems.extend(f"missing lane evidence for {lane_id}" for lane_id in missing)
    cohort_keys = {
        (
            item["evidence"].get("github", {}).get("run_id"),
            item["evidence"].get("github", {}).get("run_attempt"),
            item["evidence"].get("github", {}).get("sha"),
            item["evidence"].get("execution_contract", {}).get("sha256"),
        )
        for item in records.values()
    }
    if len(cohort_keys) != 1:
        problems.append("lane evidence does not share one run/attempt/sha/contract key")

    dispositions = {
        lane_id: records[lane_id]["evidence"]["disposition"]
        for lane_id in required
        if lane_id in records
    }
    if problems or len(records) != len(required) or UNJUDGED in dispositions.values():
        disposition = UNJUDGED
    elif all(value == FEASIBLE for value in dispositions.values()):
        disposition = FEASIBLE
    elif any(value == REJECTED for value in dispositions.values()):
        disposition = REJECTED
    else:
        disposition = UNJUDGED
        problems.append("complete cohort has an unrecognized disposition combination")

    args.output.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema": "rapidrbf-instrumented-faer-feasibility-cohort-v1",
        "execution_contract": {
            "contract_id": contract["contract_id"],
            "sha256": contract_sha256,
        },
        "required_lanes": required,
        "lane_dispositions": dispositions,
        "cohort_keys": [list(key) for key in sorted(cohort_keys, key=str)],
        "problems": problems,
        "disposition": disposition,
        "lane_evidence": {
            lane_id: {
                "sha256": sha256_file(records[lane_id]["path"]),
                "target": records[lane_id]["evidence"]["target"],
                "native_executable": records[lane_id]["evidence"][
                    "native_executable"
                ],
                "candidate": records[lane_id]["evidence"]["candidate"],
            }
            for lane_id in required
            if lane_id in records
        },
    }
    summary_path = args.output / "cohort-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "cohort-summary.json.sha256").write_text(
        f"{sha256_file(summary_path)}  cohort-summary.json\n", encoding="utf-8"
    )
    lines = [
        "# Instrumented faer two-factor feasibility cohort",
        "",
        f"Disposition: `{disposition}`",
        "",
        "| Lane | Target | Disposition |",
        "| --- | --- | --- |",
    ]
    for lane_id in required:
        if lane_id in records:
            evidence = records[lane_id]["evidence"]
            lines.append(
                f"| `{lane_id}` | `{evidence['target']}` | "
                f"`{evidence['disposition']}` |"
            )
        else:
            lines.append(f"| `{lane_id}` | missing | `{UNJUDGED}` |")
    if problems:
        lines.extend(["", "## Problems", ""])
        lines.extend(f"- {problem}" for problem in problems)
    lines.extend(
        [
            "",
            "This gate does not replay the 216-factor corpus, adopt faer, compare "
            "solver mechanisms, choose persistent storage, or enter the 100k rung.",
            "",
        ]
    )
    (args.output / "cohort-summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(disposition)
    return 1 if disposition == UNJUDGED else 0


if __name__ == "__main__":
    raise SystemExit(main())
