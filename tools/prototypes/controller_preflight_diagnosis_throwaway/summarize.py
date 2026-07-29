"""Aggregate four immutable Issue 52 controller-only diagnostic journals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main(root: Path, output: Path) -> None:
    require(not output.exists(), f"output must be absent: {output}")
    paths = sorted(root.rglob("diagnostic-summary.json"))
    require(len(paths) == 4, f"expected four summaries, found {len(paths)}")
    observations = [
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in paths
    ]
    by_lane = {value["lane_id"]: (path, value) for path, value in observations}
    require(set(by_lane) == set(TARGETS), "diagnostic lane set differs")
    for lane_id, target in TARGETS.items():
        path, value = by_lane[lane_id]
        require(
            value["collection_status"] == "COMPLETE"
            and value["target"] == target
            and value["scope"]
            == {
                "candidate_built": False,
                "candidate_executed": False,
                "backend_entries": 0,
                "factor_or_solve_calls": 0,
                "candidate_observations": 0,
            },
            f"diagnostic scope differs for {lane_id}",
        )
        sidecar = path.with_suffix(path.suffix + ".sha256")
        require(sidecar.is_file(), f"summary sidecar absent for {lane_id}")
        require(
            sidecar.read_text(encoding="ascii").split()[0] == sha256_file(path),
            f"summary sidecar differs for {lane_id}",
        )

    identities = {
        (
            value["identity"]["issue51_commit"],
            value["identity"]["issue51_controller_binding_sha256"],
            value["identity"]["issue51_source_binding_sha256"],
            value["identity"]["candidate_binding_sha256"],
            value["identity"]["accepted_reference_sha256"],
            value["identity"]["controller_plan_sha256"],
            value["identity"]["git_commit"],
        )
        for _, value in observations
    }
    require(len(identities) == 1, "diagnostic cohort mixed identities")
    lane_records: dict[str, Any] = {}
    for lane_id in TARGETS:
        path, value = by_lane[lane_id]
        lane_records[lane_id] = {
            "target": value["target"],
            "original_controller_status": value["original_controller_status"],
            "global_checks": value["global_checks"],
            "failed_global_checks": value["failed_global_checks"],
            "failed_observations": value["failed_observations"],
            "completed_check_count": value["completed_check_count"],
            "summary": {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            },
            "lane_witness_sha256": value["identity"]["lane_witness_sha256"],
        }

    cohort = {
        "schema": "RapidRBF/ControllerPreflightDiagnosticCohort/v1",
        "issue": 52,
        "collection_status": "COMPLETE",
        "question_status": (
            "FAILURES_REPRODUCED"
            if all(
                lane_records[lane]["original_controller_status"] == "FAIL"
                for lane in ("windows-x86_64", "macos-arm64", "macos-x86_64")
            )
            and lane_records["linux-x86_64-glibc"]["original_controller_status"]
            == "PASS"
            else "OBSERVED_PATTERN_DIFFERS"
        ),
        "identity": {
            "issue51_commit": next(iter(identities))[0],
            "issue51_controller_binding_sha256": next(iter(identities))[1],
            "issue51_source_binding_sha256": next(iter(identities))[2],
            "candidate_binding_sha256": next(iter(identities))[3],
            "accepted_reference_sha256": next(iter(identities))[4],
            "controller_plan_sha256": next(iter(identities))[5],
            "diagnostic_git_commit": next(iter(identities))[6],
        },
        "scope": {
            "candidate_built": False,
            "candidate_executed": False,
            "backend_entries": 0,
            "factor_or_solve_calls": 0,
            "candidate_observations": 0,
        },
        "lanes": lane_records,
    }
    output.mkdir(parents=True)
    cohort_path = output / "diagnostic-cohort.json"
    cohort_path.write_text(
        json.dumps(cohort, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Controller-only diagnostic cohort",
        "",
        f"- Collection: `{cohort['collection_status']}`",
        f"- Pattern: `{cohort['question_status']}`",
        "- Candidate built/executed: `false` / `false`",
        "",
        "## Exact lane results",
        "",
    ]
    for lane_id, record in lane_records.items():
        failures = (
            ", ".join(f"`{item}`" for item in record["failed_global_checks"])
            or "none"
        )
        lines.append(
            f"- **{lane_id}**: `{record['original_controller_status']}`; "
            f"failed global checks: {failures}"
        )
        for failure in record["failed_observations"]:
            lines.append(
                f"  - `{failure['name']}`: "
                f"`{json.dumps(failure['summary'], sort_keys=True)}`"
            )
    (output / "diagnostic-cohort.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    (output / "diagnostic-cohort.json.sha256").write_text(
        f"{sha256_file(cohort_path)}  diagnostic-cohort.json\n",
        encoding="ascii",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.evidence_root = args.evidence_root.resolve()
    args.output = args.output.resolve()
    return args


if __name__ == "__main__":
    parsed = parse_args()
    main(parsed.evidence_root, parsed.output)
