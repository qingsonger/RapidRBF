"""Capture a qualified native GitHub-hosted lane witness.

This preflight never imports or executes the instrumented faer candidate.  It
proves only that the named hosted lane is real, native, auditable, and capable
of compiling and executing a Rust binary on the required target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


def run_command(command: Sequence[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return {
            "command": list(command),
            "returncode": None,
            "stdout": "",
            "stderr": str(error),
        }
    return {
        "command": list(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def parse_rust_host(rustc_verbose: dict[str, Any]) -> str | None:
    for line in rustc_verbose["stdout"].splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    return None


def native_rust_features() -> tuple[list[str], dict[str, Any]]:
    result = run_command(["rustc", "--print", "cfg", "-C", "target-cpu=native"])
    features = sorted(
        match.group(1)
        for line in result["stdout"].splitlines()
        if (match := re.fullmatch(r'target_feature="([^"]+)"', line.strip()))
    )
    return features, result


def os_identity() -> dict[str, Any]:
    system = platform.system()
    common = {
        "platform_system": system,
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "platform_machine": platform.machine(),
        "uname": list(platform.uname()),
    }
    if system == "Windows":
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_OperatingSystem | "
                "Select-Object Caption,Version,BuildNumber | "
                "ConvertTo-Json -Compress"
            ),
        ]
        common["platform_detail"] = run_command(command)
    elif system == "Linux":
        release: dict[str, str] = {}
        os_release = Path("/etc/os-release")
        if os_release.exists():
            for line in os_release.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    release[key] = value.strip().strip('"')
        common["os_release"] = release
        common["glibc"] = run_command(["getconf", "GNU_LIBC_VERSION"])
        common["platform_detail"] = run_command(["uname", "-a"])
    elif system == "Darwin":
        common["platform_detail"] = run_command(["sw_vers"])
    return common


def cpu_identity() -> dict[str, Any]:
    system = platform.system()
    identity: dict[str, Any] = {
        "logical_cpu_count": os.cpu_count(),
        "python_processor": platform.processor(),
    }
    if system == "Windows":
        identity["platform_detail"] = run_command(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Processor | "
                    "Select-Object Name,Manufacturer,NumberOfCores,"
                    "NumberOfLogicalProcessors | ConvertTo-Json -Compress"
                ),
            ]
        )
    elif system == "Linux":
        identity["platform_detail"] = run_command(["lscpu", "--json"])
    elif system == "Darwin":
        identity["brand"] = run_command(["sysctl", "-n", "machdep.cpu.brand_string"])
        identity["physical_cpu_count"] = run_command(
            ["sysctl", "-n", "hw.physicalcpu"]
        )
        identity["logical_cpu_count_command"] = run_command(
            ["sysctl", "-n", "hw.logicalcpu"]
        )
    return identity


def resource_identity(runner_temp: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(runner_temp)
    identity: dict[str, Any] = {
        "runner_temp_disk": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    }
    system = platform.system()
    if system == "Windows":
        identity["memory"] = run_command(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_OperatingSystem | "
                    "Select-Object TotalVisibleMemorySize,FreePhysicalMemory | "
                    "ConvertTo-Json -Compress"
                ),
            ]
        )
    elif system == "Linux":
        selected: dict[str, str] = {}
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition(":")
                if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                    selected[key] = value.strip()
        identity["memory"] = selected
    elif system == "Darwin":
        identity["memory_bytes"] = run_command(["sysctl", "-n", "hw.memsize"])
        identity["vm_stat"] = run_command(["vm_stat"])
    return identity


def executable_identity(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if data.startswith(b"MZ") and len(data) >= 0x40:
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe_offset : pe_offset + 4] == b"PE\0\0":
            return {
                "format": "pe",
                "machine": struct.unpack_from("<H", data, pe_offset + 4)[0],
            }
    if data.startswith(b"\x7fELF") and len(data) >= 20:
        endian = "<" if data[5] == 1 else ">"
        return {
            "format": "elf",
            "machine": struct.unpack_from(f"{endian}H", data, 18)[0],
        }
    if data.startswith(b"\xcf\xfa\xed\xfe") and len(data) >= 8:
        return {
            "format": "mach-o",
            "machine": struct.unpack_from("<I", data, 4)[0],
        }
    if data.startswith(b"\xfe\xed\xfa\xcf") and len(data) >= 8:
        return {
            "format": "mach-o",
            "machine": struct.unpack_from(">I", data, 4)[0],
        }
    return {"format": "unknown", "machine": None}


def compile_and_run_native_smoke(
    runner_temp: Path, lane: dict[str, Any]
) -> tuple[dict[str, Any], bool, str]:
    smoke_root = Path(tempfile.mkdtemp(prefix="rapidrbf-native-smoke-", dir=runner_temp))
    try:
        source = smoke_root / "smoke.rs"
        executable = smoke_root / (
            "rapidrbf-native-smoke.exe"
            if platform.system() == "Windows"
            else "rapidrbf-native-smoke"
        )
        source.write_text(
            (
                'fn main() { println!("{}:{}", '
                "std::env::consts::OS, std::env::consts::ARCH); }\n"
            ),
            encoding="utf-8",
        )
        compile_result = run_command(
            ["rustc", str(source), "-C", "opt-level=0", "-o", str(executable)]
        )
        execute_result = (
            run_command([str(executable)])
            if compile_result["returncode"] == 0
            else {
                "command": ["<native-smoke>"],
                "returncode": None,
                "stdout": "",
                "stderr": "compile failed",
            }
        )
        executable_header = (
            executable_identity(executable)
            if compile_result["returncode"] == 0 and executable.exists()
            else {"format": "missing", "machine": None}
        )
        expected = f'{lane["rust_std_os"]}:{lane["rust_std_arch"]}'
        passed = (
            compile_result["returncode"] == 0
            and execute_result["returncode"] == 0
            and execute_result["stdout"] == expected
            and executable_header["format"] == lane["executable_format"]
            and executable_header["machine"] == lane["executable_machine"]
        )
        detail = (
            f"native executable returned {execute_result['stdout']!r}; "
            f"expected {expected!r}; header={executable_header!r}"
        )
        return (
            {
                "compile_returncode": compile_result["returncode"],
                "compile_stderr": compile_result["stderr"],
                "execute_returncode": execute_result["returncode"],
                "execute_stdout": execute_result["stdout"],
                "execute_stderr": execute_result["stderr"],
                "executable_header": executable_header,
            },
            passed,
            detail,
        )
    finally:
        shutil.rmtree(smoke_root, ignore_errors=True)


def scratch_roundtrip(runner_temp: Path) -> tuple[bool, str]:
    scratch = Path(tempfile.mkdtemp(prefix="rapidrbf-scratch-", dir=runner_temp))
    marker = scratch / "roundtrip.bin"
    payload = b"RapidRBF isolated lane scratch\n"
    marker.write_bytes(payload)
    observed = marker.read_bytes()
    shutil.rmtree(scratch)
    passed = observed == payload and not scratch.exists()
    return passed, "write/read/delete completed below RUNNER_TEMP"


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract_bytes = args.contract.read_bytes()
    contract = json.loads(contract_bytes)
    lanes = {lane["lane_id"]: lane for lane in contract["lanes"]}
    if args.lane not in lanes:
        raise SystemExit(f"unknown lane {args.lane!r}")
    lane = lanes[args.lane]

    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    runner_temp_raw = os.environ.get("RUNNER_TEMP", "")
    runner_temp = Path(runner_temp_raw) if runner_temp_raw else output

    rustc_verbose = run_command(["rustc", "-vV"])
    cargo_version = run_command(["cargo", "-V"])
    rustup_toolchain = run_command(["rustup", "show", "active-toolchain"])
    native_features, native_feature_command = native_rust_features()
    rust_host = parse_rust_host(rustc_verbose)

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "github_actions",
        os.environ.get("GITHUB_ACTIONS") == "true",
        f'GITHUB_ACTIONS={os.environ.get("GITHUB_ACTIONS")!r}',
    )
    add_check(
        checks,
        "github_hosted_runner",
        os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
        f'RUNNER_ENVIRONMENT={os.environ.get("RUNNER_ENVIRONMENT")!r}',
    )
    add_check(
        checks,
        "runner_os",
        os.environ.get("RUNNER_OS") == lane["runner_os"],
        f'RUNNER_OS={os.environ.get("RUNNER_OS")!r}; expected={lane["runner_os"]!r}',
    )
    add_check(
        checks,
        "runner_arch",
        os.environ.get("RUNNER_ARCH") == lane["runner_arch"],
        (
            f'RUNNER_ARCH={os.environ.get("RUNNER_ARCH")!r}; '
            f'expected={lane["runner_arch"]!r}'
        ),
    )
    add_check(
        checks,
        "native_machine",
        platform.machine() in lane["native_machine"],
        (
            f"platform.machine()={platform.machine()!r}; "
            f"accepted={lane['native_machine']!r}"
        ),
    )
    add_check(
        checks,
        "native_rust_host",
        rust_host == lane["target"],
        f"rustc host={rust_host!r}; required target={lane['target']!r}",
    )
    missing_features = sorted(set(lane["required_cpu_features"]) - set(native_features))
    add_check(
        checks,
        "required_cpu_features",
        not missing_features,
        (
            f"required={lane['required_cpu_features']!r}; "
            f"missing={missing_features!r}"
        ),
    )
    image_os = os.environ.get("ImageOS")
    image_version = os.environ.get("ImageVersion")
    add_check(
        checks,
        "runner_image_identity",
        bool(image_os and image_version),
        f"ImageOS={image_os!r}; ImageVersion={image_version!r}",
    )
    add_check(
        checks,
        "runner_temp",
        bool(runner_temp_raw and runner_temp.is_dir()),
        "RUNNER_TEMP is present and resolves to a directory",
    )

    glibc = None
    if lane.get("libc") == "glibc":
        glibc_result = run_command(["getconf", "GNU_LIBC_VERSION"])
        glibc = glibc_result["stdout"]
        add_check(
            checks,
            "glibc",
            glibc_result["returncode"] == 0 and glibc.startswith("glibc "),
            f"getconf GNU_LIBC_VERSION={glibc!r}",
        )

    smoke, smoke_passed, smoke_detail = compile_and_run_native_smoke(
        runner_temp, lane
    )
    add_check(checks, "native_rust_compile_and_execute", smoke_passed, smoke_detail)
    scratch_passed, scratch_detail = scratch_roundtrip(runner_temp)
    add_check(checks, "isolated_scratch_roundtrip", scratch_passed, scratch_detail)

    qualification = (
        "PASS" if all(check["status"] == "PASS" for check in checks) else "UNQUALIFIED"
    )
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    server_url = os.environ.get("GITHUB_SERVER_URL")
    witness = {
        "schema": "rapidrbf-instrumented-faer-lane-witness-v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "qualification": qualification,
        "lane": lane,
        "contract": {
            "contract_id": contract["contract_id"],
            "sha256": hashlib.sha256(contract_bytes).hexdigest(),
        },
        "github": {
            "repository": repository,
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
            "run_id": run_id,
            "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "run_url": (
                f"{server_url}/{repository}/actions/runs/{run_id}"
                if server_url and repository and run_id
                else None
            ),
            "job": os.environ.get("GITHUB_JOB"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_environment": os.environ.get("RUNNER_ENVIRONMENT"),
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
            "image_os": image_os,
            "image_version": image_version,
        },
        "host": {
            "os": os_identity(),
            "cpu": cpu_identity(),
            "resources": resource_identity(runner_temp),
            "native_rust_features": native_features,
            "glibc": glibc,
        },
        "toolchain": {
            "python": sys.version,
            "rustc_verbose": rustc_verbose,
            "cargo_version": cargo_version,
            "rustup_active_toolchain": rustup_toolchain,
            "native_feature_command": native_feature_command,
            "git_version": run_command(["git", "--version"]),
            "cmake_version": run_command(["cmake", "--version"]),
            "clang_version": run_command(["clang", "--version"]),
        },
        "native_smoke": smoke,
        "checks": checks,
        "candidate": {
            "binding_loaded": False,
            "backend_calls": 0,
            "factor_publications": 0,
            "disposition": "NOT_IN_SCOPE_FOR_LANE_PREFLIGHT",
        },
    }

    witness_path = output / "lane-identity.json"
    witness_path.write_text(
        json.dumps(witness, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    witness_sha = sha256_file(witness_path)
    (output / "lane-identity.json.sha256").write_text(
        f"{witness_sha}  lane-identity.json\n", encoding="utf-8"
    )
    print(f"{args.lane}: {qualification}")
    print(f"lane-identity sha256: {witness_sha}")
    return 0 if qualification == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
