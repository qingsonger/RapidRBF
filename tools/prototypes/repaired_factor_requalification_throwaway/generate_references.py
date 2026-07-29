"""Materialize the issue-47 target-independent reference manifest.

This is the only reference-phase entrypoint. It verifies every frozen input,
extracts the immutable issue-41 transport safely, hashes the complete
reference-generator closure, and invokes the MPFR-directed generator before
any candidate executable is built or entered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / "reference"
PROTOTYPES = ROOT.parent
ISSUE41 = PROTOTYPES / "instrumented_faer_corpus_qualification_throwaway"
AUTHORITY = PROTOTYPES / "projected_factor_health_authority_throwaway"
ISSUE41_PLAN = ISSUE41 / "factor-qualification-plan.v1.json"
AUTHORITY_PROFILE = AUTHORITY / "authority-profile.v1.json"
REQUALIFICATION_PLAN = AUTHORITY / "requalification-plan.v1.json"

EXPECTED = {
    "bundle_bytes": 452_947_159,
    "bundle_sha256": "a3b6417e61a604ee568d7bb5fed0416ce5c726f0e529ca1f998a7bdb272e207a",
    "issue41_plan_sha256": "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce",
    "authority_sha256": "c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6",
    "requalification_plan_sha256": "3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829",
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


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
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


def safe_extract(bundle: Path, destination: Path) -> None:
    with zipfile.ZipFile(bundle) as archive:
        for member in archive.infolist():
            relative = Path(member.filename)
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and "\\" not in member.filename,
                f"unsafe bundle member {member.filename!r}",
            )
        archive.extractall(destination)


def generator_closure() -> tuple[str, list[dict[str, Any]]]:
    paths = (
        ROOT / "generate_references.py",
        REFERENCE / "Cargo.toml",
        REFERENCE / "Cargo.lock",
        REFERENCE / "src" / "main.rs",
    )
    digest = hashlib.sha256()
    files: list[dict[str, Any]] = []
    for path in paths:
        require(path.is_file(), f"missing generator closure file {path}")
        relative = path.relative_to(ROOT).as_posix()
        payload = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "little"))
        digest.update(payload)
        files.append(
            {
                "path": relative,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return digest.hexdigest(), files


def executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    target_root = Path(os.environ.get("CARGO_TARGET_DIR", REFERENCE / "target"))
    return (
        target_root
        / "release"
        / f"rapidrbf-repaired-factor-reference-throwaway{suffix}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-limit", type=int)
    args = parser.parse_args()
    args.bundle = args.bundle.resolve()
    args.output = args.output.resolve()
    require(not args.output.exists(), f"output must be absent: {args.output}")
    require(
        args.bundle.stat().st_size == EXPECTED["bundle_bytes"]
        and sha256_file(args.bundle) == EXPECTED["bundle_sha256"],
        "issue-41 bundle identity differs",
    )
    for path, expected in (
        (ISSUE41_PLAN, EXPECTED["issue41_plan_sha256"]),
        (AUTHORITY_PROFILE, EXPECTED["authority_sha256"]),
        (REQUALIFICATION_PLAN, EXPECTED["requalification_plan_sha256"]),
    ):
        require(sha256_file(path) == expected, f"{path.name} identity differs")

    closure_sha256, closure_files = generator_closure()
    environment = os.environ.copy()
    environment["CARGO_INCREMENTAL"] = "0"
    environment["RUSTUP_TOOLCHAIN"] = "1.85.0"
    build = run(
        ["cargo", "build", "--release", "--locked"],
        cwd=REFERENCE,
        env=environment,
        timeout=7200,
    )
    binary = executable()
    require(binary.is_file(), f"missing generator executable {binary}")

    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    extraction = Path(
        tempfile.mkdtemp(prefix="rapidrbf-issue47-reference-", dir=runner_temp)
    )
    try:
        safe_extract(args.bundle, extraction)
        require(
            (extraction / "factor-qualification-plan.v1.json").read_bytes()
            == ISSUE41_PLAN.read_bytes(),
            "transported issue-41 plan differs",
        )
        command = [
            str(binary),
            "--issue-41-plan",
            str(ISSUE41_PLAN),
            "--authority-profile",
            str(AUTHORITY_PROFILE),
            "--requalification-plan",
            str(REQUALIFICATION_PLAN),
            "--bundle-root",
            str(extraction),
            "--generator-closure-sha256",
            closure_sha256,
            "--output",
            str(args.output),
        ]
        if args.source_limit is not None:
            command.extend(["--source-limit", str(args.source_limit)])
        generated = run(command, cwd=REFERENCE, env=environment, timeout=18_000)
    finally:
        shutil.rmtree(extraction, ignore_errors=True)

    manifest = json.loads(args.output.read_text(encoding="utf-8"))
    allowed = {
        "CERTIFIED_REFERENCE",
        "CERTIFIED_REFERENCE_DIAGNOSTIC_SUBSET",
        "REFERENCE_SET_INCOMPLETE_UNJUDGED",
    }
    require(
        manifest["schema"] == "RapidRBF/ProjectedFactorReferenceManifest/v1"
        and manifest["disposition"] in allowed
        and manifest["generator"]["closure_sha256"] == closure_sha256
        and not manifest["candidate_inputs_observed"],
        "reference manifest identity or independence differs",
    )
    manifest_sha256 = sha256_file(args.output)
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    sidecar.write_text(
        f"{manifest_sha256}  {args.output.name}\n",
        encoding="utf-8",
    )
    reproduction = args.output.with_name("reference-reproduction.json")
    reproduction.write_text(
        json.dumps(
            {
                "schema": "RapidRBF/ProjectedFactorReferenceReproduction/v1",
                "manifest_sha256": manifest_sha256,
                "manifest_disposition": manifest["disposition"],
                "generator_closure_sha256": closure_sha256,
                "generator_closure_files": closure_files,
                "generator_executable": {
                    "bytes": binary.stat().st_size,
                    "sha256": sha256_file(binary),
                },
                "build_stdout": build.stdout.strip(),
                "build_stderr": build.stderr.strip(),
                "generator_stdout": generated.stdout.strip(),
                "generator_stderr": generated.stderr.strip(),
                "rustc": run(
                    ["rustc", "-vV"], cwd=REFERENCE, env=environment, timeout=60
                ).stdout.strip(),
                "cargo": run(
                    ["cargo", "-V"], cwd=REFERENCE, env=environment, timeout=60
                ).stdout.strip(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "disposition": manifest["disposition"],
                "manifest": str(args.output),
                "manifest_sha256": manifest_sha256,
                "generator_closure_sha256": closure_sha256,
                "unique_matrix_payloads": manifest["unique_matrix_payloads"],
                "certified_references": manifest["certified_references"],
                "indeterminate_references": manifest["indeterminate_references"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        KeyError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        raise SystemExit(f"reference phase failed: {error}") from error
