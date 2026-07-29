"""Run all three issue-41 lanes on one already-qualified native target."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
CANDIDATE = ROOT.parent / "instrumented_faer_candidate_binding_throwaway"
LANES = ROOT.parent / "instrumented_faer_lane_provisioning_throwaway"
PLAN = ROOT / "factor-qualification-plan.v1.json"
TRANSPORT = ROOT / "transport-manifest.v1.json"
EXECUTION_CONTRACT = ROOT / "execution-contract.v1.json"
ALLOWED_DISPOSITIONS = {
    "ADMITTED_FOR_MECHANISM_PANEL",
    "NOT_ADMITTED_DIAGNOSTIC_ONLY",
}
LANE_PROFILES = (
    {"workers": 1, "maximum_live_threads": 12},
    {"workers": 2, "maximum_live_threads": 12},
    {"workers": 8, "maximum_live_threads": 16},
)


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
    timeout: int = 1800,
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_identity(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    require(path.is_file(), f"missing file {path}")
    require(path.stat().st_size == expected_bytes, f"{path} byte count differs")
    require(sha256_file(path) == expected_sha256, f"{path} sha256 differs")


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


def verify_transport(bundle: Path) -> tuple[dict[str, Any], Path]:
    manifest = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    require(
        manifest.get("schema")
        == "RapidRBF/FactorQualificationTransportManifest/v1",
        "transport manifest schema differs",
    )
    asset = manifest["asset"]
    require_identity(bundle, asset["bytes"], asset["sha256"])
    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    extraction = Path(
        tempfile.mkdtemp(prefix="rapidrbf-issue41-input-", dir=runner_temp)
    )
    try:
        safe_extract(bundle, extraction)
        bundled_plan = extraction / "factor-qualification-plan.v1.json"
        require(
            bundled_plan.read_bytes() == PLAN.read_bytes(),
            "transported qualification plan differs from committed plan",
        )
        source_files = list((extraction / "sources").glob("*.f64le"))
        require(
            len(source_files) == manifest["asset"]["unique_matrix_payloads"],
            "transported unique source count differs",
        )
    except BaseException:
        shutil.rmtree(extraction, ignore_errors=True)
        raise
    return manifest, extraction


def verify_authority() -> dict[str, Any]:
    verifier = run([sys.executable, "verify_binding.py"], cwd=CANDIDATE)
    binding_manifest = json.loads(
        (CANDIDATE / "binding-manifest.v1.json").read_text(encoding="utf-8")
    )
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    require(
        binding_manifest["binding_sha256"]
        == plan["authority"]["candidate_binding"]["binding_sha256"],
        "candidate binding differs from qualification plan",
    )
    require(
        sha256_file(LANES / "lane-contract.v1.json")
        == plan["authority"]["lane_contract"]["sha256"],
        "lane contract differs from qualification plan",
    )
    return {
        "binding_verifier_stdout": verifier.stdout.strip(),
        "binding_manifest_file_sha256": sha256_file(
            CANDIDATE / "binding-manifest.v1.json"
        ),
        "binding_sha256": binding_manifest["binding_sha256"],
        "plan_file_sha256": sha256_file(PLAN),
        "plan_id": plan["plan_id"],
    }


def native_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return (
        ROOT
        / "target"
        / "release"
        / f"rapidrbf-instrumented-faer-corpus-qualification-throwaway{suffix}"
    )


def windows_thread_count(pid: int) -> int:
    from ctypes import wintypes

    snapshot_flag = 0x00000004
    invalid_handle = ctypes.c_void_p(-1).value

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Thread32First.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ThreadEntry32),
    ]
    kernel32.Thread32First.restype = wintypes.BOOL
    kernel32.Thread32Next.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ThreadEntry32),
    ]
    kernel32.Thread32Next.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(snapshot_flag, 0)
    if snapshot == invalid_handle:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot")
    entry = ThreadEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    count = 0
    try:
        success = kernel32.Thread32First(snapshot, ctypes.byref(entry))
        while success:
            if entry.th32OwnerProcessID == pid:
                count += 1
            success = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return count


def process_thread_count(pid: int) -> int:
    if sys.platform == "win32":
        return windows_thread_count(pid)
    task_root = Path(f"/proc/{pid}/task")
    if task_root.is_dir():
        return len(list(task_root.iterdir()))
    if sys.platform == "darwin":
        completed = subprocess.run(
            ["ps", "-o", "thcount=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return int(completed.stdout.strip())
    raise RuntimeError(f"no native thread-count route for {sys.platform}")


def run_observed_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    started = time.monotonic_ns()
    samples = 0
    maximum_threads = 0
    sampling_errors: list[str] = []
    while process.poll() is None:
        try:
            maximum_threads = max(maximum_threads, process_thread_count(process.pid))
            samples += 1
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            sampling_errors.append(str(error))
        if (time.monotonic_ns() - started) / 1_000_000_000 > timeout:
            process.kill()
            stdout, stderr = process.communicate()
            raise TimeoutError(
                f"candidate timed out after {timeout}s\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        time.sleep(0.002)
    stdout, stderr = process.communicate()
    completed = subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )
    require(
        completed.returncode == 0,
        f"candidate failed ({completed.returncode})\n"
        f"stdout:\n{stdout}\nstderr:\n{stderr}",
    )
    require(samples > 0 and not sampling_errors, f"thread sampling failed: {sampling_errors}")
    return completed, {
        "method": "native external process-thread sampling at 2ms cadence",
        "samples": samples,
        "maximum_live_threads": maximum_threads,
        "sampling_errors": sampling_errors,
    }


def git_value(*args: str) -> str:
    return run(["git", *args], cwd=REPOSITORY, timeout=60).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--lane-witness", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), f"output must be absent: {args.output}")

    authority = verify_authority()
    transport, extraction = verify_transport(args.bundle.resolve())
    try:
        lane_witness = json.loads(args.lane_witness.read_text(encoding="utf-8"))
        require(lane_witness["qualification"] == "PASS", "lane is not qualified")
        require(
            lane_witness["lane"]["lane_id"] == args.lane_id,
            "lane witness id differs",
        )
        require(
            lane_witness["lane"]["target"] == args.target,
            "lane witness target differs",
        )
        require(
            lane_witness["contract"]["sha256"]
            == authority_plan()["authority"]["lane_contract"]["sha256"],
            "lane witness contract differs",
        )

        environment = os.environ.copy()
        environment["CARGO_INCREMENTAL"] = "0"
        environment["RUSTUP_TOOLCHAIN"] = "1.85.0"
        build = run(
            ["cargo", "build", "--release", "--locked"],
            cwd=ROOT,
            env=environment,
            timeout=3600,
        )
        executable = native_executable()
        require(executable.is_file(), f"missing native executable {executable}")

        runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        args.output.mkdir(parents=True)
        observations: list[dict[str, Any]] = []
        for profile in LANE_PROFILES:
            workers = profile["workers"]
            candidate_output = args.output / f"candidate-{workers}-workers.json"
            candidate_scratch = runner_temp / (
                f"rapidrbf-issue41-{args.lane_id}-{workers}-workers-"
                f"{os.getpid()}"
            )
            require(
                not candidate_output.exists() and not candidate_scratch.exists(),
                "candidate output/scratch must be fresh",
            )
            command = [
                str(executable),
                "--plan",
                str(PLAN),
                "--bundle-root",
                str(extraction),
                "--lane-id",
                args.lane_id,
                "--target",
                args.target,
                "--workers",
                str(workers),
                "--maximum-live-threads",
                str(profile["maximum_live_threads"]),
                "--scratch",
                str(candidate_scratch),
                "--output",
                str(candidate_output),
            ]
            completed, thread_evidence = run_observed_process(
                command,
                cwd=ROOT,
                env=environment,
                timeout=7200,
            )
            candidate = json.loads(candidate_output.read_text(encoding="utf-8"))
            require(
                candidate["schema"]
                == "RapidRBF/InstrumentedFaerCorpusQualificationLaneObservation/v1",
                "candidate schema differs",
            )
            require(
                candidate["lane_id"] == args.lane_id
                and candidate["target"] == args.target
                and candidate["lane"]["configured_workers"] == workers,
                "candidate lane identity differs",
            )
            require(
                candidate["disposition"] in ALLOWED_DISPOSITIONS,
                "candidate disposition is forbidden",
            )
            thread_evidence["maximum_live_threads_grant"] = profile[
                "maximum_live_threads"
            ]
            thread_evidence["pass"] = (
                thread_evidence["maximum_live_threads"]
                <= profile["maximum_live_threads"]
            )
            observations.append(
                {
                    "workers": workers,
                    "maximum_live_threads": profile["maximum_live_threads"],
                    "candidate_file": candidate_output.name,
                    "candidate_file_sha256": sha256_file(candidate_output),
                    "candidate_disposition": candidate["disposition"],
                    "candidate_counts": candidate["counts"],
                    "candidate_controls": candidate["controls"],
                    "candidate_scratch": candidate["scratch"],
                    "controller_threads": thread_evidence,
                    "stdout": completed.stdout.strip(),
                    "stderr": completed.stderr.strip(),
                }
            )

        evidence = {
            "schema": "RapidRBF/InstrumentedFaerTargetQualificationEvidence/v1",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "lane_id": args.lane_id,
            "target": args.target,
            "disposition": (
                "ADMITTED_FOR_MECHANISM_PANEL"
                if all(
                    item["candidate_disposition"] == "ADMITTED_FOR_MECHANISM_PANEL"
                    and item["controller_threads"]["pass"]
                    for item in observations
                )
                else "NOT_ADMITTED_DIAGNOSTIC_ONLY"
            ),
            "authority": authority,
            "execution_contract": {
                "contract_id": json.loads(
                    EXECUTION_CONTRACT.read_text(encoding="utf-8")
                )["contract_id"],
                "sha256": sha256_file(EXECUTION_CONTRACT),
            },
            "transport": transport,
            "lane_witness": lane_witness,
            "native_executable": {
                "bytes": executable.stat().st_size,
                "sha256": sha256_file(executable),
            },
            "build": {
                "command": ["cargo", "build", "--release", "--locked"],
                "stdout": build.stdout.strip(),
                "stderr": build.stderr.strip(),
                "rustc": run(["rustc", "-vV"], cwd=ROOT, env=environment).stdout.strip(),
                "cargo": run(["cargo", "-V"], cwd=ROOT, env=environment).stdout.strip(),
            },
            "lane_observations": observations,
            "github": {
                "repository": os.environ.get("GITHUB_REPOSITORY"),
                "sha": os.environ.get("GITHUB_SHA"),
                "ref": os.environ.get("GITHUB_REF"),
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "workflow": os.environ.get("GITHUB_WORKFLOW"),
                "job": os.environ.get("GITHUB_JOB"),
            },
            "source_identity": {
                relative: {
                    "bytes": (ROOT / relative).stat().st_size,
                    "sha256": sha256_file(ROOT / relative),
                }
                for relative in (
                    "Cargo.toml",
                    "Cargo.lock",
                    "src/main.rs",
                    "run.py",
                    "factor-qualification-plan.v1.json",
                    "transport-manifest.v1.json",
                    "execution-contract.v1.json",
                )
            },
            "git_sha": git_value("rev-parse", "HEAD"),
        }
        evidence_path = args.output / "target-observation.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (args.output / "target-observation.json.sha256").write_text(
            f"{sha256_file(evidence_path)}  target-observation.json\n",
            encoding="utf-8",
        )
        print(f"{args.lane_id}: {evidence['disposition']}")
        print(f"target-observation sha256: {sha256_file(evidence_path)}")
    finally:
        shutil.rmtree(extraction, ignore_errors=True)
    return 0


def authority_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, TimeoutError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit(f"target qualification failed: {error}") from error
