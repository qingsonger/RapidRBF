"""Run one frozen issue-44 observation on one already-qualified native lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
CANDIDATE = ROOT.parent / "instrumented_faer_candidate_binding_throwaway"
LANES = ROOT.parent / "instrumented_faer_lane_provisioning_throwaway"
CONTRACT = ROOT / "execution-contract.v1.json"
INPUT_MANIFEST = ROOT / "inputs" / "input-manifest.v1.json"
ALLOWED_DISPOSITIONS = {
    "FEASIBLE_FOR_216_FACTOR_QUALIFICATION",
    "EVIDENCE_BACKED_REJECTED",
    "UNJUDGED_EVIDENCE_MISSING",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int = 900,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {list(command)!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def require_hash(path: Path, expected: str) -> None:
    observed = sha256_file(path)
    if observed != expected:
        raise RuntimeError(f"{path} sha256={observed}; expected={expected}")


def load_inputs() -> tuple[dict[str, Any], dict[str, Path]]:
    manifest = json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
    paths: dict[str, Path] = {}
    for artifact in manifest["artifacts"]:
        path = INPUT_MANIFEST.parent / artifact["file"]
        if path.stat().st_size != artifact["bytes"]:
            raise RuntimeError(
                f"{path} bytes={path.stat().st_size}; expected={artifact['bytes']}"
            )
        require_hash(path, artifact["sha256"])
        paths[artifact["role"]] = path
    if set(paths) != {"projected_b", "coarse_p_top"}:
        raise RuntimeError("input manifest does not name exactly the two frozen roles")
    return manifest, paths


def verify_authority(contract: dict[str, Any]) -> dict[str, Any]:
    authority = contract["authority"]
    require_hash(
        CANDIDATE / "binding-manifest.v1.json",
        authority["candidate_manifest_file_sha256"],
    )
    require_hash(
        CANDIDATE / "inputs" / "factor-health-profile.projected.json",
        authority["factor_health_profile_file_sha256"],
    )
    require_hash(
        CANDIDATE / "inputs" / "two-factor-plan.v1.json",
        authority["two_factor_plan_file_sha256"],
    )
    require_hash(
        CANDIDATE / "checkpoint-metadata.v1.json",
        authority["checkpoint_metadata_file_sha256"],
    )
    require_hash(
        LANES / "lane-contract.v1.json",
        authority["lane_contract_sha256"],
    )
    verifier = run([sys.executable, "verify_binding.py"], cwd=CANDIDATE)
    manifest = json.loads(
        (CANDIDATE / "binding-manifest.v1.json").read_text(encoding="utf-8")
    )
    if manifest["binding_sha256"] != authority["candidate_binding_sha256"]:
        raise RuntimeError("candidate binding identity differs from execution contract")
    return {
        "binding_verifier_stdout": verifier.stdout.strip(),
        "binding_manifest_sha256": sha256_file(
            CANDIDATE / "binding-manifest.v1.json"
        ),
        "binding_sha256": manifest["binding_sha256"],
    }


def native_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return (
        ROOT
        / "target"
        / "release"
        / f"rapidrbf-instrumented-faer-feasibility-gate-throwaway{suffix}"
    )


def git_value(*args: str) -> str:
    return run(["git", *args], cwd=REPOSITORY, timeout=60).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--lane-witness", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract_bytes = CONTRACT.read_bytes()
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest()
    contract = json.loads(contract_bytes)
    input_manifest, input_paths = load_inputs()
    authority = verify_authority(contract)

    lane_witness = json.loads(args.lane_witness.read_text(encoding="utf-8"))
    if lane_witness["qualification"] != "PASS":
        raise RuntimeError("candidate execution requires a qualified lane witness")
    if lane_witness["lane"]["lane_id"] != args.lane_id:
        raise RuntimeError("lane witness id differs from requested lane")
    if lane_witness["lane"]["target"] != args.target:
        raise RuntimeError("lane witness target differs from requested target")
    if (
        lane_witness["contract"]["sha256"]
        != contract["authority"]["lane_contract_sha256"]
    ):
        raise RuntimeError("lane witness uses a different lane contract")

    environment = os.environ.copy()
    environment["CARGO_INCREMENTAL"] = "0"
    environment["RUSTUP_TOOLCHAIN"] = contract["execution"]["rust_toolchain"]
    build = run(
        ["cargo", "build", "--release", "--locked"],
        cwd=ROOT,
        env=environment,
        timeout=1800,
    )
    executable = native_executable()
    if not executable.is_file():
        raise RuntimeError(f"missing native executable {executable}")

    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    candidate_scratch = Path(
        tempfile.mkdtemp(prefix=f"rapidrbf-issue44-{args.lane_id}-", dir=runner_temp)
    )
    try:
        before = sorted(path.relative_to(candidate_scratch).as_posix() for path in candidate_scratch.rglob("*"))
        observed = run(
            [
                str(executable),
                "--projected-b",
                str(input_paths["projected_b"]),
                "--coarse-p-top",
                str(input_paths["coarse_p_top"]),
                "--lane-id",
                args.lane_id,
                "--target",
                args.target,
            ],
            cwd=ROOT,
            env=environment,
            timeout=1800,
        )
        after = sorted(path.relative_to(candidate_scratch).as_posix() for path in candidate_scratch.rglob("*"))
    finally:
        shutil.rmtree(candidate_scratch, ignore_errors=True)

    try:
        candidate = json.loads(observed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"candidate emitted malformed JSON: {error}\n{observed.stdout}"
        ) from error
    if candidate.get("schema") != "rapidrbf-instrumented-faer-lane-observation-v1":
        raise RuntimeError("candidate observation schema differs")
    if candidate.get("lane_id") != args.lane_id or candidate.get("target") != args.target:
        raise RuntimeError("candidate observation lane identity differs")
    if candidate.get("disposition") not in ALLOWED_DISPOSITIONS:
        raise RuntimeError("candidate emitted a forbidden disposition")
    if before or after:
        raise RuntimeError(
            f"candidate temporary-storage root changed: before={before}, after={after}"
        )

    args.output.mkdir(parents=True, exist_ok=False)
    head_sha = git_value("rev-parse", "HEAD")
    source_files = [
        "Cargo.toml",
        "Cargo.lock",
        "src/main.rs",
        "run.py",
        "execution-contract.v1.json",
        "inputs/input-manifest.v1.json",
    ]
    evidence = {
        "schema": "rapidrbf-instrumented-faer-qualified-lane-evidence-v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "lane_id": args.lane_id,
        "target": args.target,
        "disposition": candidate["disposition"],
        "execution_contract": {
            "contract_id": contract["contract_id"],
            "sha256": contract_sha256,
            "git_sha": head_sha,
        },
        "authority_verification": authority,
        "input_manifest": {
            "sha256": sha256_file(INPUT_MANIFEST),
            "canonical_hierarchy": input_manifest["canonical_hierarchy"],
            "artifacts": input_manifest["artifacts"],
        },
        "native_executable": {
            "path_role": "target/release native issue-44 runner",
            "bytes": executable.stat().st_size,
            "sha256": sha256_file(executable),
        },
        "source_identity": {
            relative: {
                "bytes": (ROOT / relative).stat().st_size,
                "sha256": sha256_file(ROOT / relative),
            }
            for relative in source_files
        },
        "build": {
            "command": ["cargo", "build", "--release", "--locked"],
            "stdout": build.stdout.strip(),
            "stderr": build.stderr.strip(),
            "rustc": run(["rustc", "-vV"], cwd=ROOT, env=environment).stdout.strip(),
            "cargo": run(["cargo", "-V"], cwd=ROOT, env=environment).stdout.strip(),
        },
        "lane_witness": lane_witness,
        "candidate": candidate,
        "temporary_storage": {
            "policy": "denied",
            "candidate_scratch_before": before,
            "candidate_scratch_after": after,
            "scratch_removed_after_observation": not candidate_scratch.exists(),
        },
        "github": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "job": os.environ.get("GITHUB_JOB"),
        },
        "retry": {
            "candidate_observation_started": True,
            "silent_retry_permitted": False,
        },
    }
    evidence_path = args.output / "lane-observation.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence_sha = sha256_file(evidence_path)
    (args.output / "lane-observation.json.sha256").write_text(
        f"{evidence_sha}  lane-observation.json\n", encoding="utf-8"
    )
    print(f"{args.lane_id}: {candidate['disposition']}")
    print(f"lane-observation sha256: {evidence_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
