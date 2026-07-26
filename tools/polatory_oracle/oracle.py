#!/usr/bin/env python3
"""Capture, verify, and replay immutable Polatory behavior observations.

This module deliberately does not compare floating-point values against a
tolerance.  It preserves raw evidence for the later differential-harness and
numerical-contract decisions. Canonical performance and differential
comparison belong to RapidRBF Issue #15, not this evidence collector.
"""

from __future__ import annotations

import argparse
import ctypes
import difflib
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA_VERSION = "1.0.0"
ALLOWED_APPLICABILITY = {"required", "not_applicable", "must_not_compare"}
ALLOWED_TERMINAL = {"exited", "timeout"}
ALLOWED_AUTHORITY = {"canonical", "instrumented"}
ALLOWED_ROLE = {"accepted_surface", "research_only", "provenance_only"}
THREAD_ENVIRONMENT = {
    "BLIS_NUM_THREADS",
    "MKL_DYNAMIC",
    "MKL_NUM_THREADS",
    "OMP_DYNAMIC",
    "OMP_NUM_THREADS",
    "OMP_PLACES",
    "OMP_PROC_BIND",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "RAYON_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
}
TEMP_ENVIRONMENT = {"TEMP", "TMP", "TMPDIR"}
INHERITED_ENVIRONMENT = {
    "COMSPEC",
    "NUMBER_OF_PROCESSORS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "WINDIR",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class OracleError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OracleError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OracleError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise OracleError(f"{path} must contain one JSON object")
    return value


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_relative(value: str, field: str) -> pathlib.PurePosixPath:
    if not isinstance(value, str) or not value:
        raise OracleError(f"{field} must be a non-empty string")
    if "\\" in value:
        raise OracleError(f"{field} must use forward slashes: {value!r}")
    windows = pathlib.PureWindowsPath(value)
    if windows.drive or windows.root:
        raise OracleError(f"{field} must be bundle-relative: {value!r}")
    candidate = pathlib.PurePosixPath(value)
    if candidate.is_absolute() or candidate.anchor:
        raise OracleError(f"{field} must be bundle-relative: {value!r}")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise OracleError(f"{field} contains an unsafe segment: {value!r}")
    return candidate


def safe_cwd(value: Any, field: str) -> pathlib.PurePosixPath | None:
    if value is None or value == ".":
        return None
    return safe_relative(value, field)


def resolve_under(root: pathlib.Path, relative: str, field: str) -> pathlib.Path:
    pure = safe_relative(relative, field)
    root_resolved = root.resolve()
    target = root.joinpath(*pure.parts)
    resolved = target.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as error:
        raise OracleError(f"{field} escapes {root_resolved}: {relative!r}") from error
    return resolved


def ensure_unique(values: Iterable[str], field: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise OracleError(f"duplicate {field}: {value}")
        seen.add(value)


def validate_index(index: dict[str, Any]) -> None:
    if index.get("schema_version") != SCHEMA_VERSION:
        raise OracleError(
            f"unsupported index schema_version {index.get('schema_version')!r}"
        )
    items = index.get("compatibility_items")
    scenarios = index.get("scenarios")
    if not isinstance(items, list) or not isinstance(scenarios, list):
        raise OracleError("index requires compatibility_items[] and scenarios[]")
    item_ids: list[str] = []
    scenario_ids: list[str] = []
    item_by_id: dict[str, dict[str, Any]] = {}
    scenario_by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"]
        ):
            raise OracleError("every compatibility item requires a string id")
        item_id = item["id"]
        item_ids.append(item_id)
        item_by_id[item_id] = item
        applicability = item.get("oracle_applicability")
        if applicability not in ALLOWED_APPLICABILITY:
            raise OracleError(
                f"compatibility item {item_id} has invalid oracle_applicability"
            )
        declared = item.get("scenario_ids", [])
        if not isinstance(declared, list) or not all(
            isinstance(value, str) and value for value in declared
        ):
            raise OracleError(f"compatibility item {item_id}.scenario_ids must be strings")
        ensure_unique(declared, f"{item_id}.scenario_ids")
        if applicability != "required" and declared:
            raise OracleError(
                f"{item_id} is {applicability} and must not claim oracle scenarios"
            )
        if applicability in {"not_applicable", "must_not_compare"} and not item.get(
            "reason"
        ):
            raise OracleError(f"{item_id} requires a reason")
    ensure_unique(item_ids, "compatibility item id")
    for scenario in scenarios:
        if (
            not isinstance(scenario, dict)
            or not isinstance(scenario.get("id"), str)
            or not scenario["id"]
        ):
            raise OracleError("every scenario requires a string id")
        scenario_id = scenario["id"]
        scenario_path = safe_relative(scenario_id, f"scenario {scenario_id}.id")
        if len(scenario_path.parts) != 1:
            raise OracleError(f"scenario {scenario_id}.id must be one path-safe segment")
        scenario_ids.append(scenario_id)
        scenario_by_id[scenario_id] = scenario
        authority = scenario.get("authority")
        role = scenario.get("role")
        if authority not in ALLOWED_AUTHORITY:
            raise OracleError(f"scenario {scenario_id} has invalid authority {authority!r}")
        if role not in ALLOWED_ROLE:
            raise OracleError(f"scenario {scenario_id} has invalid role {role!r}")
        if role == "accepted_surface" and authority != "canonical":
            raise OracleError(
                f"accepted_surface scenario {scenario_id} must have canonical authority"
            )
        argv = scenario.get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(value, str) and value for value in argv
        ):
            raise OracleError(f"scenario {scenario_id}.argv must be non-empty strings")
        covers = scenario.get("covers", [])
        relates_to = scenario.get("relates_to", [])
        for field_name, references in (("covers", covers), ("relates_to", relates_to)):
            if not isinstance(references, list) or not all(
                isinstance(value, str) and value for value in references
            ):
                raise OracleError(
                    f"scenario {scenario_id}.{field_name} must contain strings"
                )
            ensure_unique(references, f"scenario {scenario_id}.{field_name}")
            unknown = set(references) - set(item_by_id)
            if unknown:
                raise OracleError(
                    f"scenario {scenario_id}.{field_name} references unknown "
                    f"compatibility items {sorted(unknown)}"
                )
        if role == "accepted_surface":
            if not covers or relates_to:
                raise OracleError(
                    f"accepted_surface scenario {scenario_id} requires covers and "
                    "must not use relates_to"
                )
            for item_id in covers:
                if item_by_id[item_id]["oracle_applicability"] != "required":
                    raise OracleError(
                        f"scenario {scenario_id} must not cover {item_id}, which is "
                        f"{item_by_id[item_id]['oracle_applicability']}"
                    )
        elif covers or not relates_to:
            raise OracleError(
                f"{role} scenario {scenario_id} requires relates_to and must not use covers"
            )
        env = scenario.get("env", {})
        if not isinstance(env, dict) or not all(
            isinstance(key, str) and isinstance(value, (str, type(None)))
            for key, value in env.items()
        ):
            raise OracleError(f"scenario {scenario_id}.env must map strings to strings/null")
        folded_env: set[str] = set()
        for key, value in env.items():
            folded = key.upper()
            if not key or "=" in key or "\x00" in key or (
                isinstance(value, str) and "\x00" in value
            ):
                raise OracleError(f"scenario {scenario_id}.env contains an invalid entry")
            if folded in folded_env:
                raise OracleError(
                    f"scenario {scenario_id}.env duplicates {key!r} case-insensitively"
                )
            if folded in TEMP_ENVIRONMENT:
                raise OracleError(
                    f"scenario {scenario_id}.env must not override isolated {folded}"
                )
            folded_env.add(folded)
        safe_cwd(scenario.get("cwd", "."), f"scenario {scenario_id}.cwd")
        timeout = scenario.get("timeout_seconds", 60)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise OracleError(f"scenario {scenario_id}.timeout_seconds must be positive")
        expected = scenario.get("expected")
        if not isinstance(expected, dict) or expected.get("terminal_status") not in ALLOWED_TERMINAL:
            raise OracleError(f"scenario {scenario_id} has invalid expected terminal status")
        if (
            expected.get("terminal_status") == "exited"
            and not isinstance(expected.get("exit_code"), int)
        ):
            raise OracleError(f"scenario {scenario_id} requires expected.exit_code")
        outputs = scenario.get("outputs", [])
        if not isinstance(outputs, list):
            raise OracleError(f"scenario {scenario_id}.outputs must be a list")
        output_paths: list[str] = []
        for output in outputs:
            if not isinstance(output, dict):
                raise OracleError(f"scenario {scenario_id} output must be an object")
            path = output.get("path")
            safe_relative(path, f"scenario {scenario_id} output.path")
            output_paths.append(path)
            if not isinstance(output.get("required", True), bool) or not isinstance(
                output.get("replay_compare", True), bool
            ):
                raise OracleError(
                    f"scenario {scenario_id} output flags must be booleans"
                )
        ensure_unique(output_paths, f"scenario {scenario_id} output path")
        for replay_field in (
            "replay_compare",
            "stdout_replay_compare",
            "stderr_replay_compare",
        ):
            if not isinstance(scenario.get(replay_field, True), bool):
                raise OracleError(f"scenario {scenario_id}.{replay_field} must be boolean")
        configured_threads = scenario.get("configured_threads")
        if configured_threads is not None and not isinstance(configured_threads, dict):
            raise OracleError(
                f"scenario {scenario_id}.configured_threads must be an object"
            )
        if scenario.get("surface") == "legacy_artifact":
            layout = scenario.get("legacy_layout")
            required_layout_fields = {
                "os",
                "architecture",
                "byte_order",
                "size_t_bytes",
                "eigen_index_bytes",
                "matrix_storage",
            }
            if not isinstance(layout, dict) or not required_layout_fields.issubset(layout):
                raise OracleError(
                    f"scenario {scenario_id} legacy_layout requires "
                    f"{sorted(required_layout_fields)}"
                )
    ensure_unique(scenario_ids, "scenario id")
    for item_id, item in item_by_id.items():
        declared = set(item.get("scenario_ids", []))
        observed = {
            scenario_id
            for scenario_id, scenario in scenario_by_id.items()
            if scenario.get("role") == "accepted_surface"
            and item_id in scenario.get("covers", [])
        }
        if item["oracle_applicability"] == "required":
            if not declared:
                raise OracleError(f"required compatibility item {item_id} has no scenarios")
            unknown = declared - set(scenario_by_id)
            if unknown:
                raise OracleError(
                    f"compatibility item {item_id} references unknown scenarios {sorted(unknown)}"
                )
            if declared != observed:
                raise OracleError(
                    f"compatibility item {item_id} and scenario covers disagree: "
                    f"declared={sorted(declared)}, observed={sorted(observed)}"
                )


def parse_vars(values: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {"PYTHON": sys.executable}
    for value in values:
        if "=" not in value:
            raise OracleError(f"--var must be NAME=VALUE, got {value!r}")
        name, resolved = value.split("=", 1)
        if not name or not resolved:
            raise OracleError(f"--var must be NAME=VALUE, got {value!r}")
        variables[name] = resolved
    return variables


def expand(value: str, variables: dict[str, str]) -> str:
    result = value
    for name, replacement in variables.items():
        result = result.replace("${" + name + "}", replacement)
    if "${" in result:
        raise OracleError(f"unresolved placeholder in {value!r}")
    return result


def logicalize(value: str, variables: dict[str, str]) -> str:
    """Replace resolved run-specific paths with stable logical placeholders."""
    result = value
    candidates = sorted(
        (
            (resolved, "${" + name + "}")
            for name, resolved in variables.items()
            if resolved
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for resolved, placeholder in candidates:
        result = result.replace(resolved, placeholder)
        alternate = resolved.replace("\\", "/")
        if alternate != resolved:
            result = result.replace(alternate, placeholder)
    return result


def _windows_sample(pid: int) -> dict[str, int | None]:
    if os.name != "nt":
        return {
            "working_set_bytes": None,
            "peak_working_set_bytes": None,
            "private_bytes": None,
            "peak_pagefile_bytes": None,
            "thread_count": None,
        }

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010
    TH32CS_SNAPTHREAD = 0x00000004
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class THREADENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("cntUsage", ctypes.c_ulong),
            ("th32ThreadID", ctypes.c_ulong),
            ("th32OwnerProcessID", ctypes.c_ulong),
            ("tpBasePri", ctypes.c_long),
            ("tpDeltaPri", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Thread32First.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(THREADENTRY32),
    ]
    kernel32.Thread32First.restype = ctypes.c_int
    kernel32.Thread32Next.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(THREADENTRY32),
    ]
    kernel32.Thread32Next.restype = ctypes.c_int

    thread_count: int | None = None
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot and snapshot != INVALID_HANDLE_VALUE:
        try:
            entry = THREADENTRY32()
            entry.dwSize = ctypes.sizeof(entry)
            count = 0
            ok = kernel32.Thread32First(snapshot, ctypes.byref(entry))
            while ok:
                if entry.th32OwnerProcessID == pid:
                    count += 1
                ok = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
            thread_count = count
        finally:
            kernel32.CloseHandle(snapshot)

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
    )
    if not handle:
        return {
            "working_set_bytes": None,
            "peak_working_set_bytes": None,
            "private_bytes": None,
            "peak_pagefile_bytes": None,
            "thread_count": thread_count,
        }
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), ctypes.sizeof(counters)
        )
        if not ok:
            return {
                "working_set_bytes": None,
                "peak_working_set_bytes": None,
                "private_bytes": None,
                "peak_pagefile_bytes": None,
                "thread_count": thread_count,
            }
        return {
            "working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
            "private_bytes": int(counters.PrivateUsage),
            "peak_pagefile_bytes": int(counters.PeakPagefileUsage),
            "thread_count": thread_count,
        }
    finally:
        kernel32.CloseHandle(handle)


def sample_process(pid: int) -> dict[str, int | None]:
    if os.name == "nt":
        return _windows_sample(pid)
    status = pathlib.Path(f"/proc/{pid}/status")
    working_set: int | None = None
    threads: int | None = None
    try:
        for line in status.read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                working_set = int(line.split()[1]) * 1024
            elif line.startswith("Threads:"):
                threads = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return {
        "working_set_bytes": working_set,
        "peak_working_set_bytes": None,
        "private_bytes": None,
        "peak_pagefile_bytes": None,
        "thread_count": threads,
    }


class _WindowsJob:
    """Best-effort process-tree ownership for timeout cleanup on Windows."""

    def __init__(self, handle: int) -> None:
        self.handle = handle

    @classmethod
    def assign(cls, process: subprocess.Popen[bytes]) -> "_WindowsJob | None":
        if os.name != "nt":
            return None

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_ulong),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_ulong),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_ulong),
                ("SchedulingClass", ctypes.c_ulong),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return None
        information = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        information.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        configured = kernel32.SetInformationJobObject(
            handle,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(information),
            ctypes.sizeof(information),
        )
        process_handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
        assigned = configured and kernel32.AssignProcessToJobObject(
            handle, process_handle
        )
        if not assigned:
            kernel32.CloseHandle(handle)
            return None
        return cls(handle)

    def terminate(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateJobObject.restype = ctypes.c_int
        kernel32.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if self.handle:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_int
            kernel32.CloseHandle(self.handle)
            self.handle = 0


def terminate_process_tree(
    process: subprocess.Popen[bytes], job: _WindowsJob | None
) -> None:
    if job is not None:
        job.terminate()
    elif os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()


def run_scenario(
    scenario: dict[str, Any],
    run_root: pathlib.Path,
    repo_root: pathlib.Path,
    variables: dict[str, str],
) -> dict[str, Any]:
    scenario_id = scenario["id"]
    run_dir = resolve_under(run_root, scenario_id, "scenario id")
    run_dir.mkdir(parents=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"rapidrbf-oracle-{scenario_id}-"))
    try:
        cwd_pure = safe_cwd(scenario.get("cwd", "."), f"scenario {scenario_id}.cwd")
        if cwd_pure is None:
            process_cwd = work.resolve()
            configured_cwd = "."
            effective_cwd = "${WORK}"
        else:
            configured_cwd = cwd_pure.as_posix()
            process_cwd = resolve_under(work, configured_cwd, f"scenario {scenario_id}.cwd")
            process_cwd.mkdir(parents=True, exist_ok=False)
            effective_cwd = f"${{WORK}}/{configured_cwd}"
        expanded_vars = {
            **variables,
            "REPO": str(repo_root.resolve()),
            "WORK": str(work.resolve()),
            "CWD": str(process_cwd),
        }
        argv = [expand(value, expanded_vars) for value in scenario["argv"]]

        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in INHERITED_ENVIRONMENT
        }

        def remove_environment_key(name: str) -> None:
            for existing in list(environment):
                if existing.upper() == name.upper():
                    environment.pop(existing)

        configured_environment: dict[str, str | None] = {}
        for key, value in scenario.get("env", {}).items():
            configured_environment[key] = value
            remove_environment_key(key)
            if value is not None:
                environment[key] = expand(value, expanded_vars)
        for key in TEMP_ENVIRONMENT:
            remove_environment_key(key)
            environment[key] = str(work.resolve())
        effective_environment = {
            key: ("${WORK}" if value == str(work.resolve()) else value)
            for key, value in sorted(environment.items(), key=lambda item: item[0].upper())
        }
        configured_threads = scenario.get("configured_threads")
        if configured_threads is None:
            configured_threads = {
                key: effective_environment[key]
                for key in effective_environment
                if key.upper() in THREAD_ENVIRONMENT
            }

        timeout = float(scenario.get("timeout_seconds", 60))
        started_utc = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        process = subprocess.Popen(
            argv,
            cwd=process_cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=os.name != "nt",
        )
        job = _WindowsJob.assign(process)
        samples: list[dict[str, Any]] = []
        stdout = b""
        stderr = b""
        terminal = "exited"
        try:
            while True:
                elapsed = time.monotonic() - started
                sample = {"elapsed_seconds": elapsed, **sample_process(process.pid)}
                samples.append(sample)
                remaining = timeout - elapsed
                if remaining <= 0:
                    terminal = "timeout"
                    terminate_process_tree(process, job)
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired as error:
                        if process.poll() is None:
                            process.kill()
                        stdout = error.output or b""
                        stderr = error.stderr or b""
                    break
                try:
                    stdout, stderr = process.communicate(timeout=min(0.05, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                terminate_process_tree(process, job)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if job is not None:
                job.close()

        elapsed = time.monotonic() - started
        exit_code = process.returncode if terminal == "exited" else None
        stdout_path = run_dir / "stdout.txt"
        stderr_path = run_dir / "stderr.txt"
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        samples_path = run_dir / "process-samples.jsonl"
        samples_path.write_text(
            "".join(json.dumps(sample, sort_keys=True) + "\n" for sample in samples),
            encoding="utf-8",
            newline="\n",
        )
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir()
        output_records: list[dict[str, Any]] = []
        for output in scenario.get("outputs", []):
            relative = str(safe_relative(output["path"], f"{scenario_id} output.path"))
            source = resolve_under(process_cwd, relative, f"{scenario_id} output.path")
            required = output.get("required", True)
            replay_compare = output.get("replay_compare", True)
            if not source.is_file():
                if required:
                    raise OracleError(f"scenario {scenario_id} did not create {relative}")
                output_records.append(
                    {
                        "path": relative,
                        "capture_path": f"outputs/{relative}",
                        "present": False,
                        "required": False,
                        "replay_compare": replay_compare,
                    }
                )
                continue
            target = resolve_under(outputs_dir, relative, f"{scenario_id} output.path")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            output_records.append(
                {
                    "path": relative,
                    "capture_path": f"outputs/{relative}",
                    "present": True,
                    "required": required,
                    "replay_compare": replay_compare,
                    "size": target.stat().st_size,
                    "sha256": sha256_file(target),
                }
            )

        def maximum_sample(field: str) -> int | None:
            return max(
                (
                    sample[field]
                    for sample in samples
                    if sample.get(field) is not None
                ),
                default=None,
            )

        max_working_set = maximum_sample("working_set_bytes")
        max_peak_working_set = maximum_sample("peak_working_set_bytes")
        max_private = maximum_sample("private_bytes")
        max_peak_pagefile = maximum_sample("peak_pagefile_bytes")
        max_threads = maximum_sample("thread_count")
        metrics = {
            "schema_version": SCHEMA_VERSION,
            "monotonic_wall_seconds": elapsed,
            "peak_working_set_bytes": max_working_set,
            "platform_peak_working_set_bytes": max_peak_working_set,
            "peak_private_bytes": max_private,
            "platform_peak_pagefile_bytes": max_peak_pagefile,
            "configured_threads": configured_threads,
            "maximum_observed_thread_count": max_threads,
            "sampling_interval_seconds": 0.05,
            "resource_scope": "direct_process_only",
        }
        metrics_path = run_dir / "metrics.json"
        write_json(metrics_path, metrics)
        expected = scenario["expected"]
        record = {
            "schema_version": SCHEMA_VERSION,
            "id": scenario_id,
            "authority": scenario["authority"],
            "role": scenario["role"],
            "surface": scenario.get("surface"),
            "covers": scenario.get("covers", []),
            "relates_to": scenario.get("relates_to", []),
            "configured_argv": scenario["argv"],
            "argv": [logicalize(value, expanded_vars) for value in argv],
            "configured_working_directory": configured_cwd,
            "working_directory": effective_cwd,
            "configured_environment": configured_environment,
            "environment": effective_environment,
            "seed": scenario.get("seed"),
            "seed_policy": scenario.get("seed_policy"),
            "configured_threads": configured_threads,
            "effective_threads": max_threads,
            "timeout_seconds": timeout,
            "expected": expected,
            "started_at": started_utc,
            "terminal_status": terminal,
            "exit_code": exit_code,
            "replay_compare": scenario.get("replay_compare", True),
            "stdout": {
                "path": "stdout.txt",
                "size": len(stdout),
                "sha256": sha256_bytes(stdout),
                "replay_compare": scenario.get("stdout_replay_compare", True),
            },
            "stderr": {
                "path": "stderr.txt",
                "size": len(stderr),
                "sha256": sha256_bytes(stderr),
                "replay_compare": scenario.get("stderr_replay_compare", True),
            },
            "process_samples": {
                "path": "process-samples.jsonl",
                "size": samples_path.stat().st_size,
                "sha256": sha256_file(samples_path),
            },
            "metrics": {
                "path": "metrics.json",
                "size": metrics_path.stat().st_size,
                "sha256": sha256_file(metrics_path),
            },
            "outputs": output_records,
            "legacy_layout": scenario.get("legacy_layout"),
            "normative_fields": scenario.get("normative_fields", []),
            "non_normative_fields": scenario.get("non_normative_fields", []),
        }
        write_json(run_dir / "run.json", record)
        write_checksums(run_dir)
        if terminal != expected["terminal_status"]:
            raise OracleError(
                f"scenario {scenario_id}: expected "
                f"{expected['terminal_status']}, got {terminal}"
            )
        if terminal == "exited" and exit_code != expected["exit_code"]:
            raise OracleError(
                f"scenario {scenario_id}: expected exit "
                f"{expected['exit_code']}, got {exit_code}"
            )
        return record
    finally:
        if work.exists():
            safe_remove_temp(work, f"rapidrbf-oracle-{scenario_id}-")


def write_checksums(root: pathlib.Path) -> None:
    checksum_path = root / "checksums.sha256"
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p != checksum_path):
        rows.append(
            f"{sha256_file(path)}  {path.stat().st_size}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    checksum_path.write_text("".join(rows), encoding="utf-8", newline="\n")


def safe_remove_temp(path: pathlib.Path, required_prefix: str) -> None:
    resolved = path.resolve()
    temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    if resolved.parent != temp_root or not resolved.name.startswith(required_prefix):
        raise OracleError(f"refusing to remove unexpected temporary path {resolved}")
    shutil.rmtree(resolved)


def capture(
    index_path: pathlib.Path,
    output: pathlib.Path,
    repo_root: pathlib.Path,
    variables: dict[str, str],
) -> pathlib.Path:
    index = load_json(index_path)
    validate_index(index)
    index_sha256 = sha256_file(index_path)
    index_size = index_path.stat().st_size
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError as error:
        raise OracleError(f"refusing to overwrite existing bundle {output}") from error
    runs_root = output / "runs"
    runs_root.mkdir()
    run_records: list[dict[str, Any]] = []
    try:
        for scenario in index["scenarios"]:
            run_records.append(
                run_scenario(scenario, runs_root, repo_root.resolve(), variables)
            )
        bundle = {
            "schema_version": SCHEMA_VERSION,
            "id": index.get("id", output.name),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "index": {
                "sha256": index_sha256,
                "size": index_size,
                "source": index_path.name,
            },
            "runs": [
                {
                    "id": record["id"],
                    "path": f"runs/{record['id']}/run.json",
                    "size": (runs_root / record["id"] / "run.json").stat().st_size,
                    "sha256": sha256_file(runs_root / record["id"] / "run.json"),
                }
                for record in run_records
            ],
        }
        if (
            sha256_file(index_path) != index_sha256
            or index_path.stat().st_size != index_size
        ):
            raise OracleError("index changed while capture was running")
        write_json(output / "bundle.json", bundle)
        write_checksums(output)
        return output
    except BaseException:
        # An incomplete output remains diagnostic and cannot pass verify.
        raise


def verify_checksums(root: pathlib.Path) -> None:
    checksum_path = root / "checksums.sha256"
    if checksum_path.is_symlink() or not checksum_path.is_file():
        raise OracleError(f"missing {checksum_path}")
    listed: set[str] = set()
    for number, line in enumerate(
        checksum_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            expected, size_text, relative = line.split("  ", 2)
        except ValueError as error:
            raise OracleError(f"malformed checksum line {checksum_path}:{number}") from error
        if not SHA256_RE.fullmatch(expected):
            raise OracleError(f"malformed digest at {checksum_path}:{number}")
        try:
            expected_size = int(size_text)
        except ValueError as error:
            raise OracleError(f"malformed size at {checksum_path}:{number}") from error
        if expected_size < 0:
            raise OracleError(f"negative size at {checksum_path}:{number}")
        if relative in listed:
            raise OracleError(f"duplicate checksum path {relative!r} in {checksum_path}")
        listed.add(relative)
        target = resolve_under(root, relative, f"checksum path {checksum_path}:{number}")
        if target.is_symlink() or not target.is_file():
            raise OracleError(f"checksum target is missing: {target}")
        actual_size = target.stat().st_size
        if actual_size != expected_size:
            raise OracleError(
                f"size mismatch for {target}: {actual_size} != {expected_size}"
            )
        actual = sha256_file(target)
        if actual != expected:
            raise OracleError(f"checksum mismatch for {target}: {actual} != {expected}")
    actual_files: set[str] = set()
    for target in root.rglob("*"):
        if target.is_symlink():
            raise OracleError(f"bundle contains a symbolic link: {target}")
        if target.is_file() and target != checksum_path:
            actual_files.add(target.relative_to(root).as_posix())
    if listed != actual_files:
        raise OracleError(
            f"checksum closure mismatch in {root}: "
            f"missing={sorted(actual_files - listed)}, "
            f"unknown={sorted(listed - actual_files)}"
        )


def verify_file_descriptor(
    root: pathlib.Path, descriptor: Any, field: str
) -> pathlib.Path:
    if not isinstance(descriptor, dict):
        raise OracleError(f"{field} must be an object")
    path = resolve_under(root, descriptor.get("path"), f"{field}.path")
    expected_sha = descriptor.get("sha256")
    expected_size = descriptor.get("size")
    if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
        raise OracleError(f"{field}.sha256 must be a lowercase SHA-256")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise OracleError(f"{field}.size must be a non-negative integer")
    if path.is_symlink() or not path.is_file():
        raise OracleError(f"{field} target is missing or not a regular file: {path}")
    if path.stat().st_size != expected_size:
        raise OracleError(f"{field} size mismatch for {path}")
    if sha256_file(path) != expected_sha:
        raise OracleError(f"{field} SHA-256 mismatch for {path}")
    return path


def verify_run_record(
    scenario: dict[str, Any], run_dir: pathlib.Path, record: dict[str, Any]
) -> None:
    scenario_id = scenario["id"]
    expected_structure = {
        "id": scenario_id,
        "authority": scenario["authority"],
        "role": scenario["role"],
        "surface": scenario.get("surface"),
        "covers": scenario.get("covers", []),
        "relates_to": scenario.get("relates_to", []),
        "configured_argv": scenario["argv"],
        "configured_working_directory": scenario.get("cwd") or ".",
        "configured_environment": scenario.get("env", {}),
        "seed": scenario.get("seed"),
        "seed_policy": scenario.get("seed_policy"),
        "timeout_seconds": float(scenario.get("timeout_seconds", 60)),
        "expected": scenario["expected"],
        "replay_compare": scenario.get("replay_compare", True),
        "legacy_layout": scenario.get("legacy_layout"),
        "normative_fields": scenario.get("normative_fields", []),
        "non_normative_fields": scenario.get("non_normative_fields", []),
    }
    if record.get("schema_version") != SCHEMA_VERSION:
        raise OracleError(f"run {scenario_id} schema version mismatch")
    for field, expected in expected_structure.items():
        if record.get(field) != expected:
            raise OracleError(
                f"run {scenario_id}.{field} differs from index: "
                f"{record.get(field)!r} != {expected!r}"
            )
    expected = scenario["expected"]
    if record.get("terminal_status") != expected["terminal_status"]:
        raise OracleError(f"run {scenario_id} terminal status violates expectation")
    if (
        expected["terminal_status"] == "exited"
        and record.get("exit_code") != expected["exit_code"]
    ):
        raise OracleError(f"run {scenario_id} exit code violates expectation")
    if expected["terminal_status"] == "timeout" and record.get("exit_code") is not None:
        raise OracleError(f"run {scenario_id} timeout must not claim an exit code")
    expected_descriptor_paths = {
        "stdout": "stdout.txt",
        "stderr": "stderr.txt",
        "process_samples": "process-samples.jsonl",
        "metrics": "metrics.json",
    }
    for name in ("stdout", "stderr", "process_samples", "metrics"):
        descriptor = record.get(name)
        if (
            not isinstance(descriptor, dict)
            or descriptor.get("path") != expected_descriptor_paths[name]
        ):
            raise OracleError(f"run {scenario_id}.{name} path is invalid")
        verify_file_descriptor(run_dir, record.get(name), f"run {scenario_id}.{name}")
    if record["stdout"].get("replay_compare") != scenario.get(
        "stdout_replay_compare", True
    ) or record["stderr"].get("replay_compare") != scenario.get(
        "stderr_replay_compare", True
    ):
        raise OracleError(f"run {scenario_id} stream replay policy differs from index")
    expected_outputs = scenario.get("outputs", [])
    actual_outputs = record.get("outputs")
    if not isinstance(actual_outputs, list) or len(actual_outputs) != len(expected_outputs):
        raise OracleError(f"run {scenario_id} output list differs from index")
    for number, (declared, captured) in enumerate(
        zip(expected_outputs, actual_outputs, strict=True)
    ):
        if not isinstance(captured, dict):
            raise OracleError(f"run {scenario_id} output {number} is invalid")
        path = declared["path"]
        required = declared.get("required", True)
        replay_compare = declared.get("replay_compare", True)
        structural = {
            "path": path,
            "capture_path": f"outputs/{path}",
            "required": required,
            "replay_compare": replay_compare,
        }
        for field, value in structural.items():
            if captured.get(field) != value:
                raise OracleError(
                    f"run {scenario_id} output {number}.{field} differs from index"
                )
        if required and captured.get("present") is not True:
            raise OracleError(f"run {scenario_id} required output {path} is absent")
        if captured.get("present"):
            verify_file_descriptor(
                run_dir,
                {
                    "path": captured.get("capture_path"),
                    "size": captured.get("size"),
                    "sha256": captured.get("sha256"),
                },
                f"run {scenario_id} output {path}",
            )
        else:
            target = resolve_under(
                run_dir, captured["capture_path"], f"run {scenario_id} output {path}"
            )
            if target.exists() or target.is_symlink():
                raise OracleError(
                    f"run {scenario_id} absent output {path} has captured bytes"
                )


def verify(index_path: pathlib.Path, bundle_root: pathlib.Path | None = None) -> None:
    index = load_json(index_path)
    validate_index(index)
    if bundle_root is None:
        return
    bundle_root = bundle_root.resolve()
    bundle_path = bundle_root / "bundle.json"
    if bundle_path.is_symlink():
        raise OracleError("bundle.json must not be a symbolic link")
    bundle = load_json(bundle_path)
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise OracleError("bundle schema version mismatch")
    index_descriptor = bundle.get("index")
    if not isinstance(index_descriptor, dict):
        raise OracleError("bundle index descriptor is missing")
    if (
        index_descriptor.get("sha256") != sha256_file(index_path)
        or index_descriptor.get("size") != index_path.stat().st_size
    ):
        raise OracleError("bundle was captured from a different index")
    expected_ids = [scenario["id"] for scenario in index["scenarios"]]
    run_descriptors = bundle.get("runs", [])
    if not isinstance(run_descriptors, list):
        raise OracleError("bundle.runs must be a list")
    actual_ids = [
        record.get("id") if isinstance(record, dict) else None
        for record in run_descriptors
    ]
    if actual_ids != expected_ids:
        raise OracleError(
            f"bundle scenario order differs: expected {expected_ids}, got {actual_ids}"
        )
    for scenario, descriptor in zip(index["scenarios"], run_descriptors, strict=True):
        expected_path = f"runs/{scenario['id']}/run.json"
        if descriptor.get("path") != expected_path:
            raise OracleError(f"bundle run path differs for {scenario['id']}")
        run_json = verify_file_descriptor(
            bundle_root, descriptor, f"bundle run {scenario['id']}"
        )
        run_dir = run_json.parent
        record = load_json(run_json)
        verify_run_record(scenario, run_dir, record)
        verify_checksums(run_dir)
    verify_checksums(bundle_root)


def structural_signature(record: dict[str, Any]) -> dict[str, Any] | None:
    if not record.get("replay_compare", True):
        return None
    return {
        field: record.get(field)
        for field in (
            "authority",
            "role",
            "surface",
            "covers",
            "relates_to",
            "configured_argv",
            "argv",
            "configured_working_directory",
            "working_directory",
            "configured_environment",
            "environment",
            "seed",
            "seed_policy",
            "configured_threads",
            "timeout_seconds",
            "expected",
            "terminal_status",
            "exit_code",
            "legacy_layout",
            "normative_fields",
            "non_normative_fields",
        )
    } | {
        "outputs": [
            {
                "path": output.get("path"),
                "present": output.get("present"),
                "required": output.get("required"),
            }
            for output in record.get("outputs", [])
            if output.get("replay_compare", True)
        ]
    }


def byte_difference(blessed: bytes, replayed: bytes) -> dict[str, Any]:
    common = min(len(blessed), len(replayed))
    first = next(
        (offset for offset in range(common) if blessed[offset] != replayed[offset]),
        common,
    )
    result: dict[str, Any] = {
        "blessed_size": len(blessed),
        "replayed_size": len(replayed),
        "blessed_sha256": sha256_bytes(blessed),
        "replayed_sha256": sha256_bytes(replayed),
        "first_difference_offset": first,
        "blessed_context_hex": blessed[first : first + 32].hex(),
        "replayed_context_hex": replayed[first : first + 32].hex(),
    }
    if len(blessed) > 64 * 1024 or len(replayed) > 64 * 1024:
        return result
    try:
        before_text = blessed.decode("utf-8")
        after_text = replayed.decode("utf-8")
    except UnicodeDecodeError:
        return result
    result["unified_diff"] = "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile="blessed",
            tofile="replayed",
        )
    )
    return result


def replay(
    index_path: pathlib.Path,
    blessed: pathlib.Path,
    repo_root: pathlib.Path,
    variables: dict[str, str],
    diff_out: pathlib.Path | None,
) -> list[dict[str, Any]]:
    verify(index_path, blessed)
    replay_parent = pathlib.Path(
        tempfile.mkdtemp(prefix="rapidrbf-oracle-replay-")
    )
    replay_root = replay_parent / "bundle"
    try:
        capture(index_path, replay_root, repo_root, variables)
        verify(index_path, replay_root)
        index = load_json(index_path)
        differences: list[dict[str, Any]] = []
        for scenario in index["scenarios"]:
            scenario_id = scenario["id"]
            before_dir = blessed / "runs" / scenario_id
            after_dir = replay_root / "runs" / scenario_id
            before = load_json(before_dir / "run.json")
            after = load_json(after_dir / "run.json")
            before_structure = structural_signature(before)
            after_structure = structural_signature(after)
            if before_structure != after_structure:
                differences.append(
                    {
                        "scenario_id": scenario_id,
                        "kind": "structure",
                        "blessed": before_structure,
                        "replayed": after_structure,
                    }
                )
            for stream in ("stdout", "stderr"):
                before_descriptor = before[stream]
                after_descriptor = after[stream]
                if not before_descriptor.get("replay_compare", True):
                    continue
                before_bytes = resolve_under(
                    before_dir, before_descriptor["path"], f"{scenario_id}.{stream}"
                ).read_bytes()
                after_bytes = resolve_under(
                    after_dir, after_descriptor["path"], f"{scenario_id}.{stream}"
                ).read_bytes()
                if before_bytes != after_bytes:
                    differences.append(
                        {
                            "scenario_id": scenario_id,
                            "kind": "bytes",
                            "field": stream,
                            **byte_difference(before_bytes, after_bytes),
                        }
                    )
            for before_output, after_output in zip(
                before.get("outputs", []), after.get("outputs", []), strict=True
            ):
                if not before_output.get("replay_compare", True):
                    continue
                if not before_output.get("present") or not after_output.get("present"):
                    continue
                before_bytes = resolve_under(
                    before_dir,
                    before_output["capture_path"],
                    f"{scenario_id} output",
                ).read_bytes()
                after_bytes = resolve_under(
                    after_dir,
                    after_output["capture_path"],
                    f"{scenario_id} output",
                ).read_bytes()
                if before_bytes != after_bytes:
                    differences.append(
                        {
                            "scenario_id": scenario_id,
                            "kind": "bytes",
                            "field": f"outputs/{before_output['path']}",
                            **byte_difference(before_bytes, after_bytes),
                        }
                    )
        report = {
            "schema_version": SCHEMA_VERSION,
            "kind": "exact_replay_difference_evidence",
            "numeric_tolerance_applied": False,
            "differences": differences,
        }
        if diff_out is not None:
            if diff_out.exists() or diff_out.is_symlink():
                raise OracleError(f"refusing to overwrite diff evidence {diff_out}")
            diff_out.parent.mkdir(parents=True, exist_ok=True)
            write_json(diff_out, report)
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
        return differences
    finally:
        if replay_parent.exists():
            safe_remove_temp(replay_parent, "rapidrbf-oracle-replay-")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--index", type=pathlib.Path, required=True)
    capture_parser.add_argument("--out", type=pathlib.Path, required=True)
    capture_parser.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    capture_parser.add_argument("--var", action="append", default=[])

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--index", type=pathlib.Path, required=True)
    verify_parser.add_argument("--bundle", type=pathlib.Path)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--index", type=pathlib.Path, required=True)
    replay_parser.add_argument("--bundle", type=pathlib.Path, required=True)
    replay_parser.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    replay_parser.add_argument("--var", action="append", default=[])
    replay_parser.add_argument("--diff-out", type=pathlib.Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture(
                args.index.resolve(),
                args.out,
                args.repo_root.resolve(),
                parse_vars(args.var),
            )
            print(result)
        elif args.command == "verify":
            verify(
                args.index.resolve(),
                args.bundle.resolve() if args.bundle is not None else None,
            )
            print("ok")
        else:
            differences = replay(
                args.index.resolve(),
                args.bundle.resolve(),
                args.repo_root.resolve(),
                parse_vars(args.var),
                args.diff_out,
            )
            return 1 if differences else 0
    except (OracleError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
