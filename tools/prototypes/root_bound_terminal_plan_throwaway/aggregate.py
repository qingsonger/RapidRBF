"""Verify and aggregate the four Issue 55 zero-entry lane artifacts."""

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
ZERO_SCOPE = {
    "candidate_built": False,
    "candidate_executed": False,
    "candidate_entries": 0,
    "backend_entries": 0,
    "factor_calls": 0,
    "solve_calls": 0,
    "candidate_observations": 0,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_lane(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    sidecar = path.with_suffix(path.suffix + ".sha256")
    require(sidecar.is_file(), f"summary sidecar absent: {path}")
    require(
        sidecar.read_text(encoding="ascii").split()[0] == sha256_file(path),
        f"summary sidecar differs: {path}",
    )
    journal = path.parent / value["journal"]["file"]
    journal_sidecar = path.parent / value["journal"]["sidecar"]
    require(journal.is_file(), f"journal absent: {journal}")
    require(journal_sidecar.is_file(), f"journal sidecar absent: {journal}")
    require(
        journal.stat().st_size == value["journal"]["bytes"]
        and sha256_file(journal) == value["journal"]["sha256"]
        and journal_sidecar.read_text(encoding="ascii").split()[0]
        == value["journal"]["sha256"],
        f"journal identity differs: {journal}",
    )
    return value


def main(root: Path, output: Path) -> None:
    require(not output.exists(), f"output must be absent: {output}")
    paths = sorted(root.rglob("root-bound-preflight-summary.json"))
    require(len(paths) == 4, f"expected four summaries, found {len(paths)}")
    lanes = {value["lane_id"]: (path, value) for path in paths if (value := load_lane(path))}
    require(set(lanes) == set(TARGETS), "lane set differs")

    identity_rows = set()
    lane_records: dict[str, Any] = {}
    for lane_id, target in TARGETS.items():
        path, value = lanes[lane_id]
        require(
            value["schema"] == "RapidRBF/RootBoundZeroEntryPreflightSummary/v1"
            and value["issue"] == 55
            and value["target"] == target
            and value["status"] == "PASS"
            and not value["failed_checks"]
            and value["inherited"]["completed_check_count"] == 277
            and value["scope"] == ZERO_SCOPE,
            f"lane status/scope differs: {lane_id}",
        )
        require(
            value["github"]["run_attempt"] in {None, "1"},
            f"workflow rerun is forbidden: {lane_id}",
        )
        native = value["native_reproduction"]
        expected_native = (
            "NOT_APPLICABLE" if lane_id == "windows-x86_64" else "PASS"
        )
        require(
            native["status"] == expected_native,
            f"native reproduction differs: {lane_id}",
        )
        if lane_id == "linux-x86_64-glibc":
            require(
                native["adapter"] == "linux-proc-process-tree"
                and native["phase"] == "group-membership",
                "Linux native coordinate differs",
            )
        if lane_id.startswith("macos-"):
            require(
                native["adapter"] == "macos-proc-process-tree"
                and native["phase"] == "bsd-identity",
                f"macOS native coordinate differs: {lane_id}",
            )
        identity_rows.add(
            (
                value["git_commit"],
                value["github"]["run_id"],
                value["github"]["run_attempt"],
                value["github"]["workflow_sha"],
                value["identities"]["controller_binding_sha256"],
                value["identities"]["source_binding_sha256"],
                value["identities"]["workflow_sha256"],
                value["identities"]["candidate_binding_sha256"],
                value["identities"]["witness_plan_sha256"],
                value["identities"]["accepted_reference_sha256"],
            )
        )
        lane_records[lane_id] = {
            "target": target,
            "status": value["status"],
            "inherited_completed_check_count": value["inherited"][
                "completed_check_count"
            ],
            "root_bound_completed_check_count": value[
                "root_bound_completed_check_count"
            ],
            "native_reproduction": native,
            "summary": {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            },
            "journal": value["journal"],
            "lane_witness_sha256": value["identities"][
                "lane_witness_sha256"
            ],
        }
    require(len(identity_rows) == 1, "four-lane cohort mixed identities")
    identity = next(iter(identity_rows))
    aggregation_identity = sha256_json(
        {
            "identity": identity,
            "lanes": {
                name: lane_records[name]["summary"]["sha256"]
                for name in sorted(lane_records)
            },
        }
    )
    cohort = {
        "schema": "RapidRBF/RootBoundZeroEntryPreflightCohort/v1",
        "issue": 55,
        "status": "ROOT_BOUND_FOUR_LANE_ZERO_ENTRY_PREFLIGHT_PASS",
        "disposition_supported_for_hitl": "ROOT_BOUND_FRESH_COHORT_PLAN_FROZEN",
        "identity": {
            "git_commit": identity[0],
            "run_id": identity[1],
            "run_attempt": identity[2],
            "workflow_sha": identity[3],
            "controller_binding_sha256": identity[4],
            "source_binding_sha256": identity[5],
            "workflow_sha256": identity[6],
            "candidate_binding_sha256": identity[7],
            "witness_plan_sha256": identity[8],
            "accepted_reference_sha256": identity[9],
            "aggregation_sha256": aggregation_identity,
        },
        "scope": ZERO_SCOPE,
        "inherited_ready_gated_check_count": 4 * 277,
        "root_bound_check_count": sum(
            record["root_bound_completed_check_count"]
            for record in lane_records.values()
        ),
        "required_native_reproductions": {
            "linux-proc-process-tree/group-membership": "PASS",
            "macos-arm64/macos-proc-process-tree/bsd-identity": "PASS",
            "macos-x86_64/macos-proc-process-tree/bsd-identity": "PASS",
            "windows-x86_64": "NOT_APPLICABLE_WITH_POLICY_CONTROLS_PASS",
        },
        "lanes": lane_records,
        "non_reuse": {
            "issue_53_observations_used": 0,
            "issue_54_diagnostic_observations_used_as_candidate_counts": 0,
            "issue_55_observations_are_candidate_counts": false,
        },
    }
    output.mkdir(parents=True)
    cohort_path = output / "root-bound-preflight-cohort.json"
    cohort_path.write_text(
        json.dumps(cohort, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cohort_path.with_suffix(cohort_path.suffix + ".sha256").write_text(
        f"{sha256_file(cohort_path)}  {cohort_path.name}\n",
        encoding="ascii",
    )
    lines = [
        "# Issue 55 root-bound zero-entry preflight",
        "",
        f"- Status: `{cohort['status']}`",
        f"- Provisional disposition: `{cohort['disposition_supported_for_hitl']}`",
        f"- Commit: `{cohort['identity']['git_commit']}`",
        f"- Controller binding: `{cohort['identity']['controller_binding_sha256']}`",
        f"- Aggregation: `{cohort['identity']['aggregation_sha256']}`",
        "- Candidate built/executed/entered/observed: `false/false/0/0`",
        "",
        "## Lanes",
        "",
    ]
    for lane_id, record in lane_records.items():
        native = record["native_reproduction"]
        coordinate = (
            f"{native.get('adapter')}/{native.get('phase')}"
            if native["status"] == "PASS"
            else native["status"]
        )
        lines.append(
            f"- **{lane_id}**: inherited `{record['inherited_completed_check_count']}`; "
            f"root-bound `{record['root_bound_completed_check_count']}`; "
            f"native `{coordinate}`"
        )
    (output / "root-bound-preflight-cohort.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
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
