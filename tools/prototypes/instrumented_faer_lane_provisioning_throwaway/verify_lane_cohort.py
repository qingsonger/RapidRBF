"""Verify that one run attempt contains four non-compensating lane witnesses."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_checksum(path: Path) -> str | None:
    checksum_path = path.with_name(path.name + ".sha256")
    if not checksum_path.exists():
        return None
    parts = checksum_path.read_text(encoding="utf-8").strip().split()
    return parts[0] if parts else None


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Instrumented faer lane preflight cohort",
        "",
        f"**Qualification:** `{summary['qualification']}`",
        "",
        f"- Cohort ID: `{summary['cohort_id']}`",
        f"- Lane contract: `{summary['contract_sha256']}`",
        f"- GitHub run: `{summary.get('run_id')}` attempt `{summary.get('run_attempt')}`",
        f"- Commit: `{summary.get('github_sha')}`",
        "",
        "| Lane | Qualification | Witness SHA-256 |",
        "| --- | --- | --- |",
    ]
    for lane in summary["lanes"]:
        lines.append(
            f"| `{lane['lane_id']}` | `{lane['qualification']}` | "
            f"`{lane['witness_sha256']}` |"
        )
    if summary["problems"]:
        lines.extend(["", "## Problems", ""])
        lines.extend(f"- {problem}" for problem in summary["problems"])
    lines.extend(
        [
            "",
            "This is lane provisioning evidence only. No candidate binding was loaded,",
            "no backend call occurred, and no feasibility disposition was produced.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract_bytes = args.contract.read_bytes()
    contract = json.loads(contract_bytes)
    contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    expected = {lane["lane_id"] for lane in contract["lanes"]}
    paths = sorted(args.evidence_root.rglob("lane-identity.json"))

    problems: list[str] = []
    witnesses: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in paths:
        witness = json.loads(path.read_text(encoding="utf-8"))
        lane_id = witness.get("lane", {}).get("lane_id")
        if not lane_id:
            problems.append(f"{path}: missing lane_id")
            continue
        if lane_id in witnesses:
            problems.append(f"duplicate witness for {lane_id}")
            continue
        witnesses[lane_id] = (path, witness)

    missing = sorted(expected - set(witnesses))
    extra = sorted(set(witnesses) - expected)
    if missing:
        problems.append(f"missing lanes: {', '.join(missing)}")
    if extra:
        problems.append(f"unexpected lanes: {', '.join(extra)}")

    cohort_fields = ["repository", "sha", "workflow_ref", "run_id", "run_attempt"]
    cohort_values: dict[str, set[str | None]] = {field: set() for field in cohort_fields}
    lane_summaries: list[dict[str, Any]] = []
    cohort_hash_rows: list[str] = []

    for lane_id in sorted(witnesses):
        path, witness = witnesses[lane_id]
        actual_sha = sha256_file(path)
        recorded_sha = read_checksum(path)
        if recorded_sha != actual_sha:
            problems.append(
                f"{lane_id}: checksum mismatch ({recorded_sha!r} != {actual_sha!r})"
            )
        if witness.get("contract", {}).get("sha256") != contract_sha:
            problems.append(f"{lane_id}: lane-contract hash mismatch")
        if witness.get("qualification") != "PASS":
            problems.append(
                f"{lane_id}: qualification is {witness.get('qualification')!r}"
            )
        candidate = witness.get("candidate", {})
        if (
            candidate.get("binding_loaded") is not False
            or candidate.get("backend_calls") != 0
            or candidate.get("factor_publications") != 0
        ):
            problems.append(f"{lane_id}: candidate boundary was crossed in preflight")
        for field in cohort_fields:
            cohort_values[field].add(witness.get("github", {}).get(field))
        cohort_hash_rows.append(f"{lane_id}:{actual_sha}")
        lane_summaries.append(
            {
                "lane_id": lane_id,
                "qualification": witness.get("qualification"),
                "witness_sha256": actual_sha,
                "runner_label": witness.get("lane", {}).get("runner_label"),
                "target": witness.get("lane", {}).get("target"),
                "image_os": witness.get("github", {}).get("image_os"),
                "image_version": witness.get("github", {}).get("image_version"),
            }
        )

    for field, values in cohort_values.items():
        if len(values) != 1 or None in values:
            problems.append(f"cohort field {field} is not one non-null value: {values!r}")

    cohort_material = "\n".join(
        [
            contract_sha,
            *(
                f"{field}={next(iter(values)) if len(values) == 1 else '<mixed>'}"
                for field, values in cohort_values.items()
            ),
            *cohort_hash_rows,
        ]
    )
    cohort_id = hashlib.sha256(cohort_material.encode("utf-8")).hexdigest()

    def one(field: str) -> str | None:
        values = cohort_values[field]
        return next(iter(values)) if len(values) == 1 else None

    summary = {
        "schema": "rapidrbf-instrumented-faer-lane-cohort-v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "qualification": "PASS" if not problems else "UNQUALIFIED",
        "cohort_id": cohort_id,
        "contract_id": contract["contract_id"],
        "contract_sha256": contract_sha,
        "repository": one("repository"),
        "github_sha": one("sha"),
        "workflow_ref": one("workflow_ref"),
        "run_id": one("run_id"),
        "run_attempt": one("run_attempt"),
        "lanes": lane_summaries,
        "problems": problems,
        "candidate": {
            "binding_loaded": False,
            "backend_calls": 0,
            "factor_publications": 0,
            "disposition": "NOT_IN_SCOPE_FOR_LANE_PREFLIGHT",
        },
    }

    args.output.mkdir(parents=True, exist_ok=False)
    summary_path = args.output / "cohort-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "cohort-summary.json.sha256").write_text(
        f"{sha256_file(summary_path)}  cohort-summary.json\n", encoding="utf-8"
    )
    (args.output / "cohort-summary.md").write_text(
        render_markdown(summary), encoding="utf-8"
    )
    print(render_markdown(summary))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
