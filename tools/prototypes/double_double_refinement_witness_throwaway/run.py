"""Controller for the frozen Issue 49 double-double witness gate."""

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
CONTRACT = ROOT / "execution-contract.v1.json"
WITNESS_PLAN = (
    ROOT.parent
    / "repaired_projected_solve_diagnosis_throwaway"
    / "next-experiment-plan.v1.json"
)
AUTHORITY = (
    ROOT.parent
    / "projected_factor_health_authority_throwaway"
    / "authority-profile.v1.json"
)
REQUALIFICATION_PLAN = (
    ROOT.parent
    / "projected_factor_health_authority_throwaway"
    / "requalification-plan.v1.json"
)

WITNESS_PLAN_SHA256 = (
    "7018a1a33d601076ff17b6824068ada146039fa57aab5b1cf71793cbe6d13d60"
)
ISSUE41_PLAN_SHA256 = (
    "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce"
)
REFERENCE_SHA256 = (
    "6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a"
)
AUTHORITY_SHA256 = (
    "c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6"
)
REQUALIFICATION_PLAN_SHA256 = (
    "3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829"
)
BINDING_SHA256 = (
    "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
)
TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}
PROFILES = (
    {"workers": 1, "maximum_live_threads": 12},
    {"workers": 2, "maximum_live_threads": 12},
    {"workers": 8, "maximum_live_threads": 16},
)
SOURCE_BINDING_PATHS = {
    "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.toml": (
        ROOT / "Cargo.toml"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.lock": (
        ROOT / "Cargo.lock"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/src/main.rs": (
        ROOT / "src/main.rs"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/run.py": (
        ROOT / "run.py"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/verify_cohort.py": (
        ROOT / "verify_cohort.py"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/execution-contract.v1.json": (
        ROOT / "execution-contract.v1.json"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/factor-qualification-plan.v1.json": (
        ROOT / "factor-qualification-plan.v1.json"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/transport-manifest.v1.json": (
        ROOT / "transport-manifest.v1.json"
    ),
    ".github/workflows/double-double-refinement-witness.yml": (
        REPOSITORY / ".github/workflows/double-double-refinement-witness.yml"
    ),
}
SUPPORTED = "REFINEMENT_ROUTE_SUPPORTED_FOR_FULL_CORPUS_PLAN"
REJECTED = "REFINEMENT_ROUTE_REJECTED_DIAGNOSTIC_ONLY"
INVALID = "INVALID_UNJUDGED"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 3600,
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


def git_value(*arguments: str) -> str:
    return run(["git", *arguments], cwd=REPOSITORY, timeout=60).stdout.strip()


def verify_static_authority() -> dict[str, Any]:
    require(sha256_file(WITNESS_PLAN) == WITNESS_PLAN_SHA256, "witness plan differs")
    require(sha256_file(PLAN) == ISSUE41_PLAN_SHA256, "issue-41 plan differs")
    require(sha256_file(AUTHORITY) == AUTHORITY_SHA256, "authority differs")
    require(
        sha256_file(REQUALIFICATION_PLAN) == REQUALIFICATION_PLAN_SHA256,
        "requalification plan differs",
    )
    verifier = run([sys.executable, "verify_binding.py"], cwd=CANDIDATE)
    manifest = json.loads(
        (CANDIDATE / "binding-manifest.v1.json").read_text(encoding="utf-8")
    )
    require(manifest["binding_sha256"] == BINDING_SHA256, "candidate binding differs")
    witness = json.loads(WITNESS_PLAN.read_text(encoding="utf-8"))
    issue_41 = json.loads(PLAN.read_text(encoding="utf-8"))
    require(
        sha256_file(LANES / "lane-contract.v1.json")
        == issue_41["authority"]["lane_contract"]["sha256"],
        "lane contract differs",
    )
    require(
        [item["ordinal"] for item in witness["witness_corpus"]]
        == [0, 36, 69, 72, 106, 150],
        "witness inventory differs",
    )
    return {
        "witness_plan_sha256": WITNESS_PLAN_SHA256,
        "issue_41_plan_sha256": ISSUE41_PLAN_SHA256,
        "authority_profile_sha256": AUTHORITY_SHA256,
        "requalification_plan_sha256": REQUALIFICATION_PLAN_SHA256,
        "candidate_binding_sha256": BINDING_SHA256,
        "binding_verifier_stdout": verifier.stdout.strip(),
    }


def source_binding() -> dict[str, Any]:
    files = {
        relative: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for relative, path in SOURCE_BINDING_PATHS.items()
    }
    value = {
        "schema": "RapidRBF/DoubleDoubleRefinementWitnessSourceBinding/v1",
        "rust_toolchain": "1.85.0",
        "cargo_features": "default",
        "panic_profile": "unwind",
        "candidate_binding_sha256": BINDING_SHA256,
        "witness_plan_sha256": WITNESS_PLAN_SHA256,
        "accepted_issue45_refinement_source": json.loads(
            WITNESS_PLAN.read_text(encoding="utf-8")
        )["authorities"]["accepted_issue45_refinement_source"],
        "files": files,
    }
    value["binding_sha256"] = canonical_sha256(value)
    return value


def native_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return (
        ROOT
        / "target"
        / "release"
        / f"rapidrbf-double-double-refinement-witness-throwaway{suffix}"
    )


def build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["CARGO_INCREMENTAL"] = "0"
    environment["RUSTUP_TOOLCHAIN"] = "1.85.0"
    return environment


def run_preflight(lane_id: str, target: str, output: Path) -> None:
    require(lane_id in TARGETS and TARGETS[lane_id] == target, "target identity differs")
    require(not output.exists(), f"preflight output must be absent: {output}")
    authority = verify_static_authority()
    environment = build_environment()
    environment["RAPIDRBF_LANE_ID"] = lane_id
    environment["RAPIDRBF_TARGET"] = target
    build = run(
        ["cargo", "build", "--release", "--locked"],
        cwd=ROOT,
        env=environment,
        timeout=3600,
    )
    executable = native_executable()
    require(executable.is_file(), "native executable missing")
    output.mkdir(parents=True)
    binary_path = output / "binary-preflight.json"
    run(
        [str(executable), "--identity-preflight", str(binary_path)],
        cwd=ROOT,
        env=environment,
        timeout=60,
    )
    binary = json.loads(binary_path.read_text(encoding="utf-8"))
    require(
        binary["status"] == "PASS"
        and binary["backend_entries"] == 0
        and binary["factor_or_solve_calls"] == 0
        and binary["candidate_observations"] == 0
        and binary["qd"]["double_double_bytes"] == 16
        and binary["lane_id"] == lane_id
        and binary["target"] == target,
        "zero-factor-call binary preflight failed",
    )
    binding = source_binding()
    evidence = {
        "schema": "RapidRBF/DoubleDoubleRefinementWitnessTargetPreflight/v1",
        "status": "PASS",
        "lane_id": lane_id,
        "target": target,
        "authority": authority,
        "source_binding": binding,
        "binary_preflight": binary,
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
        "git_sha": git_value("rev-parse", "HEAD"),
    }
    path = output / "preflight-observation.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    (output / "preflight-observation.json.sha256").write_text(
        f"{sha256_file(path)}  preflight-observation.json\n"
    )


def verify_preflight_cohort(root: Path) -> dict[str, Any]:
    paths = sorted(root.rglob("preflight-observation.json"))
    require(len(paths) == 4, f"expected four preflights, found {len(paths)}")
    observations = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    by_lane = {item["lane_id"]: item for item in observations}
    require(set(by_lane) == set(TARGETS), "preflight lane set differs")
    bindings = {item["source_binding"]["binding_sha256"] for item in observations}
    commits = {item["git_sha"] for item in observations}
    require(len(bindings) == 1 and len(commits) == 1, "preflight cohort mixed bindings")
    for lane_id, target in TARGETS.items():
        item = by_lane[lane_id]
        require(
            item["status"] == "PASS"
            and item["target"] == target
            and item["binary_preflight"]["backend_entries"] == 0,
            f"preflight {lane_id} failed",
        )
    local = source_binding()
    require(
        next(iter(bindings)) == local["binding_sha256"],
        "executing source differs from preflight binding",
    )
    return {
        "status": "PASS",
        "binding_sha256": local["binding_sha256"],
        "git_sha": next(iter(commits)),
        "lanes": {
            lane: {
                "target": item["target"],
                "preflight_sha256": sha256_file(
                    next(
                        path
                        for path in paths
                        if json.loads(path.read_text(encoding="utf-8"))["lane_id"]
                        == lane
                    )
                ),
            }
            for lane, item in sorted(by_lane.items())
        },
    }


def verify_reference(path: Path) -> dict[str, Any]:
    require(path.is_file() and sha256_file(path) == REFERENCE_SHA256, "reference differs")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(
        manifest["schema"] == "RapidRBF/ProjectedFactorReferenceManifest/v1"
        and manifest["disposition"] == "CERTIFIED_REFERENCE"
        and manifest["certified_references"] == 537
        and manifest["indeterminate_references"] == 0
        and not manifest["candidate_inputs_observed"],
        "reference completeness or independence differs",
    )
    return {
        "schema": manifest["schema"],
        "sha256": REFERENCE_SHA256,
        "certified_references": 537,
        "candidate_inputs_observed": False,
    }


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
    asset = manifest["asset"]
    require(
        bundle.stat().st_size == asset["bytes"]
        and sha256_file(bundle) == asset["sha256"],
        "transport bundle differs",
    )
    extraction = Path(
        tempfile.mkdtemp(
            prefix="rapidrbf-issue49-input-",
            dir=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())),
        )
    )
    safe_extract(bundle, extraction)
    require(
        (extraction / "factor-qualification-plan.v1.json").read_bytes()
        == PLAN.read_bytes(),
        "transported plan differs",
    )
    return manifest, extraction


def windows_thread_count(pid: int) -> int:
    from ctypes import wintypes

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
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
    if snapshot == ctypes.c_void_p(-1).value:
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


def macos_thread_count(pid: int) -> int:
    class ProcTaskInfo(ctypes.Structure):
        _fields_ = [
            ("pti_virtual_size", ctypes.c_uint64),
            ("pti_resident_size", ctypes.c_uint64),
            ("pti_total_user", ctypes.c_uint64),
            ("pti_total_system", ctypes.c_uint64),
            ("pti_threads_user", ctypes.c_uint64),
            ("pti_threads_system", ctypes.c_uint64),
            ("pti_policy", ctypes.c_int32),
            ("pti_faults", ctypes.c_int32),
            ("pti_pageins", ctypes.c_int32),
            ("pti_cow_faults", ctypes.c_int32),
            ("pti_messages_sent", ctypes.c_int32),
            ("pti_messages_received", ctypes.c_int32),
            ("pti_syscalls_mach", ctypes.c_int32),
            ("pti_syscalls_unix", ctypes.c_int32),
            ("pti_csw", ctypes.c_int32),
            ("pti_threadnum", ctypes.c_int32),
            ("pti_numrunning", ctypes.c_int32),
            ("pti_priority", ctypes.c_int32),
        ]

    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    libproc.proc_pidinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    libproc.proc_pidinfo.restype = ctypes.c_int
    info = ProcTaskInfo()
    observed = libproc.proc_pidinfo(
        pid, 4, 0, ctypes.byref(info), ctypes.sizeof(info)
    )
    if observed != ctypes.sizeof(info):
        raise OSError(ctypes.get_errno(), "proc_pidinfo")
    return int(info.pti_threadnum)


def process_thread_count(pid: int) -> int:
    if sys.platform == "win32":
        return windows_thread_count(pid)
    if sys.platform == "darwin":
        return macos_thread_count(pid)
    return len(list(Path(f"/proc/{pid}/task").iterdir()))


def run_observed(
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
    started = time.monotonic()
    samples = 0
    maximum = 0
    errors: list[str] = []
    timed_out = False
    while process.poll() is None:
        try:
            maximum = max(maximum, process_thread_count(process.pid))
            samples += 1
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(str(error))
        if time.monotonic() - started > timeout:
            process.kill()
            timed_out = True
            break
        time.sleep(0.002)
    stdout, stderr = process.communicate()
    return (
        subprocess.CompletedProcess(command, process.returncode, stdout, stderr),
        {
            "method": "native external process-thread sampling at 2ms cadence",
            "samples": samples,
            "maximum_live_threads": maximum,
            "sampling_errors": errors,
            "timed_out": timed_out,
            "timeout_seconds": timeout,
        },
    )


def execute_target(args: argparse.Namespace) -> None:
    require(
        args.lane_id in TARGETS and TARGETS[args.lane_id] == args.target,
        "target identity differs",
    )
    require(not args.output.exists(), f"output must be absent: {args.output}")
    authority = verify_static_authority()
    preflights = verify_preflight_cohort(args.preflight_root)
    reference = verify_reference(args.reference_manifest)
    transport, extraction = verify_transport(args.bundle)
    environment = build_environment()
    try:
        lane = json.loads(args.lane_witness.read_text(encoding="utf-8"))
        require(
            lane["qualification"] == "PASS"
            and lane["lane"]["lane_id"] == args.lane_id
            and lane["lane"]["target"] == args.target,
            "lane witness differs",
        )
        build = run(
            ["cargo", "build", "--release", "--locked"],
            cwd=ROOT,
            env=environment,
            timeout=3600,
        )
        executable = native_executable()
        args.output.mkdir(parents=True)
        observations: list[dict[str, Any]] = []
        for profile in PROFILES:
            workers = profile["workers"]
            output = args.output / f"candidate-{workers}-workers.json"
            entry = args.output / f"candidate-{workers}-workers-entry.json"
            baseline = entry.with_suffix(".baseline.json")
            scratch = Path(
                tempfile.gettempdir(),
                f"rapidrbf-issue49-{args.lane_id}-{workers}-{os.getpid()}",
            )
            require(
                not output.exists()
                and not entry.exists()
                and not baseline.exists()
                and not scratch.exists(),
                "candidate paths are not fresh",
            )
            command = [
                str(executable),
                "--plan",
                str(PLAN),
                "--bundle-root",
                str(extraction),
                "--reference-manifest",
                str(args.reference_manifest),
                "--lane-id",
                args.lane_id,
                "--target",
                args.target,
                "--workers",
                str(workers),
                "--maximum-live-threads",
                str(profile["maximum_live_threads"]),
                "--entry-marker",
                str(entry),
                "--scratch",
                str(scratch),
                "--output",
                str(output),
            ]
            completed, threads = run_observed(
                command, cwd=ROOT, env=environment, timeout=7200
            )
            threads["maximum_live_threads_grant"] = profile["maximum_live_threads"]
            threads["pass"] = (
                not threads["timed_out"]
                and not threads["sampling_errors"]
                and threads["samples"] > 0
                and threads["maximum_live_threads"]
                <= profile["maximum_live_threads"]
            )
            if completed.returncode != 0:
                disposition = REJECTED if entry.is_file() else INVALID
                observations.append(
                    {
                        "workers": workers,
                        "disposition": disposition,
                        "baseline_file": baseline.name if baseline.is_file() else None,
                        "baseline_sha256": (
                            sha256_file(baseline) if baseline.is_file() else None
                        ),
                        "candidate_entry_file": entry.name if entry.is_file() else None,
                        "candidate_entry_sha256": (
                            sha256_file(entry) if entry.is_file() else None
                        ),
                        "candidate_file": None,
                        "failure": {
                            "classification": (
                                "candidate-owned-after-entry"
                                if entry.is_file()
                                else "pre-entry-baseline-or-controller-invalidity"
                            ),
                            "returncode": completed.returncode,
                            "timed_out": threads["timed_out"],
                        },
                        "controller_threads": threads,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                )
                continue
            candidate = json.loads(output.read_text(encoding="utf-8"))
            require(
                candidate["schema"]
                == "RapidRBF/DoubleDoubleRefinementWitnessLaneObservation/v1"
                and candidate["lane_id"] == args.lane_id
                and candidate["target"] == args.target
                and candidate["lane"]["configured_workers"] == workers
                and candidate["disposition"] in {SUPPORTED, REJECTED},
                "candidate observation identity differs",
            )
            observations.append(
                {
                    "workers": workers,
                    "disposition": candidate["disposition"],
                    "baseline_file": baseline.name,
                    "baseline_sha256": sha256_file(baseline),
                    "candidate_entry_file": entry.name,
                    "candidate_entry_sha256": sha256_file(entry),
                    "candidate_file": output.name,
                    "candidate_sha256": sha256_file(output),
                    "failure": None,
                    "controller_threads": threads,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        if any(item["disposition"] == INVALID for item in observations):
            disposition = INVALID
        elif all(
            item["disposition"] == SUPPORTED and item["controller_threads"]["pass"]
            for item in observations
        ):
            disposition = SUPPORTED
        else:
            disposition = REJECTED
        evidence = {
            "schema": "RapidRBF/DoubleDoubleRefinementWitnessTargetEvidence/v1",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "lane_id": args.lane_id,
            "target": args.target,
            "disposition": disposition,
            "authority": authority,
            "preflight_cohort": preflights,
            "reference_manifest": reference,
            "transport": transport,
            "lane_witness": lane,
            "profiles": observations,
            "native_executable": {
                "bytes": executable.stat().st_size,
                "sha256": sha256_file(executable),
            },
            "build": {
                "stdout": build.stdout,
                "stderr": build.stderr,
                "rustc": run(
                    ["rustc", "-vV"], cwd=ROOT, env=environment
                ).stdout.strip(),
                "cargo": run(
                    ["cargo", "-V"], cwd=ROOT, env=environment
                ).stdout.strip(),
            },
            "source_binding": source_binding(),
            "git_sha": git_value("rev-parse", "HEAD"),
            "github": {
                "repository": os.environ.get("GITHUB_REPOSITORY"),
                "sha": os.environ.get("GITHUB_SHA"),
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            },
        }
        path = args.output / "target-observation.json"
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        (args.output / "target-observation.json.sha256").write_text(
            f"{sha256_file(path)}  target-observation.json\n"
        )
    finally:
        shutil.rmtree(extraction, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--lane-witness", type=Path)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--preflight-root", type=Path)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if not args.preflight_only:
        require(
            all(
                value is not None
                for value in (
                    args.bundle,
                    args.lane_witness,
                    args.reference_manifest,
                    args.preflight_root,
                )
            ),
            "execution requires bundle, lane witness, reference, and preflight root",
        )
        args.bundle = args.bundle.resolve()
        args.lane_witness = args.lane_witness.resolve()
        args.reference_manifest = args.reference_manifest.resolve()
        args.preflight_root = args.preflight_root.resolve()
    return args


if __name__ == "__main__":
    try:
        parsed = parse_args()
        if parsed.preflight_only:
            run_preflight(
                parsed.lane_id, parsed.target, parsed.output
            )
        else:
            execute_target(parsed)
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TimeoutError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        raise SystemExit(f"double-double witness controller failed: {error}") from error
