"""Exercise the throwaway ScalFMM3 C ABI against the frozen Windows build.

This is evidence collection, not a production acceptance test.  In particular,
the direct comparison emitted by the shim is a diagnostic and is deliberately
not promoted to a sound kernel-approximation certificate.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Iterable


POLATORY_REVISION = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"
SCALFMM_REVISION = "0be3d74f17adb28adec7004f712f693ac8ee9901"

ABI_V1 = 1
OK_CERTIFIED = 0
OK_UNCERTIFIED_EVIDENCE = 1
ABI_MISMATCH = 100
INVALID_REQUEST = 101
RESOURCE_EXHAUSTED = 104
CANCELLED = 105
CERTIFICATE_UNAVAILABLE = 107
BUSY = 109
INTERNAL_FAILURE = 110

WEIGHTS_VARY = 1
TARGETS_VARY = 2
A = 1
F = 2
FT = 3
H = 4
SELF = 1
CROSS = 2
GAUSSIAN_PROBE_ONLY = 1

ROUTE_LEGACY_DIRECT = 1
ROUTE_SCALFMM = 2
CERTIFICATE_NONE = 0
CERTIFICATE_FULL_DIRECT_DIAGNOSTIC = 1

RUN_ALLOW_UNCERTIFIED_EVIDENCE = 1 << 0
RUN_FULL_DIRECT_DIAGNOSTIC = 1 << 1
RUN_FORCE_EXCEPTION_FOR_PROBE = 1 << 31

REPORT_INPUTS_COPIED = 1 << 0
REPORT_OUTPUT_STAGED = 1 << 1
REPORT_RESOURCE_ACCOUNTING_PARTIAL = 1 << 2
REPORT_THREAD_ACCOUNTING_PARTIAL = 1 << 3
REPORT_CANCELLATION_QUANTUM_UNBOUNDED = 1 << 4
REPORT_WEIGHT_SENSITIVE_CONFIG_UNCERTIFIED = 1 << 5

UNBOUNDED_QUANTUM = (1 << 64) - 1
UNKNOWN_U32 = (1 << 32) - 1
SENTINEL = -9.87654321012345e299

ACTION_NAMES = {A: "A", F: "F", FT: "FT", H: "H"}
GEOMETRY_NAMES = {SELF: "self", CROSS: "cross"}
PLAN_NAMES = {WEIGHTS_VARY: "weights-vary", TARGETS_VARY: "targets-vary"}
ROUTE_NAMES = {
    0: "unset",
    ROUTE_LEGACY_DIRECT: "legacy-direct",
    ROUTE_SCALFMM: "scalfmm",
}
STATUS_NAMES = {
    OK_CERTIFIED: "OK_CERTIFIED",
    OK_UNCERTIFIED_EVIDENCE: "OK_UNCERTIFIED_EVIDENCE",
    ABI_MISMATCH: "ABI_MISMATCH",
    INVALID_REQUEST: "INVALID_REQUEST",
    RESOURCE_EXHAUSTED: "RESOURCE_EXHAUSTED",
    CANCELLED: "CANCELLED",
    CERTIFICATE_UNAVAILABLE: "CERTIFICATE_UNAVAILABLE",
    BUSY: "BUSY",
    INTERNAL_FAILURE: "INTERNAL_FAILURE",
}


class ErrorV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("stage", ctypes.c_uint32),
        ("detail", ctypes.c_uint32),
        ("offending_index", ctypes.c_uint64),
        ("incident_id", ctypes.c_uint64),
        ("message", ctypes.c_char * 192),
    ]


class ResourceGrantV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("persistent_bytes", ctypes.c_uint64),
        ("transient_bytes", ctypes.c_uint64),
        ("max_threads", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


DoublePointer = ctypes.POINTER(ctypes.c_double)


class PlanDescV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("plan_kind", ctypes.c_uint32),
        ("action", ctypes.c_uint32),
        ("geometry", ctypes.c_uint32),
        ("dimension", ctypes.c_uint32),
        ("kernel", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
        ("kernel_parameters", DoublePointer),
        ("kernel_parameter_count", ctypes.c_uint64),
        ("fixed_sources", DoublePointer),
        ("source_count", ctypes.c_uint64),
        ("fixed_source_value_count", ctypes.c_uint64),
        ("fixed_targets", DoublePointer),
        ("target_count", ctypes.c_uint64),
        ("fixed_target_value_count", ctypes.c_uint64),
        ("fixed_weights", DoublePointer),
        ("fixed_weight_value_count", ctypes.c_uint64),
        ("bbox_min", ctypes.c_double * 3),
        ("bbox_max", ctypes.c_double * 3),
    ]


class LaneDescV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("grant", ResourceGrantV1),
    ]


class RunDescV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
        ("changing_weights", DoublePointer),
        ("changing_weight_value_count", ctypes.c_uint64),
        ("changing_targets", DoublePointer),
        ("changing_target_count", ctypes.c_uint64),
        ("changing_target_value_count", ctypes.c_uint64),
        ("requested_abs_inf_budget", ctypes.c_double),
    ]


class OutputV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("values", DoublePointer),
        ("value_capacity", ctypes.c_uint64),
        ("value_count", ctypes.c_uint64),
    ]


class ReportV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("route", ctypes.c_uint32),
        ("certificate_kind", ctypes.c_uint32),
        ("configured_threads", ctypes.c_uint32),
        ("effective_threads", ctypes.c_uint32),
        ("maximum_live_threads", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("output_value_count", ctypes.c_uint64),
        ("persistent_bytes_estimate", ctypes.c_uint64),
        ("transient_bytes_estimate", ctypes.c_uint64),
        ("maximum_unpolled_work", ctypes.c_uint64),
        ("diagnostic_abs_inf_error", ctypes.c_double),
        ("backend_revision", ctypes.c_char * 41),
    ]


class ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("page_fault_count", ctypes.c_uint32),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
        ("private_usage", ctypes.c_size_t),
    ]


def initialize_header(value: ctypes.Structure) -> None:
    value.struct_size = ctypes.sizeof(type(value))
    value.abi_version = ABI_V1


def double_array(values: Iterable[float]) -> ctypes.Array[ctypes.c_double] | None:
    materialized = list(values)
    if not materialized:
        return None
    return (ctypes.c_double * len(materialized))(*materialized)


def double_pointer(
    value: ctypes.Array[ctypes.c_double] | None,
) -> DoublePointer | None:
    if value is None:
        return None
    return ctypes.cast(value, DoublePointer)


def decode_char_array(value: Any) -> str:
    return bytes(value).split(b"\0", 1)[0].decode("utf-8", errors="replace")


def finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def source_channels(action: int, dimension: int) -> int:
    return dimension if action in (F, H) else 1


def target_channels(action: int, dimension: int) -> int:
    return dimension if action in (FT, H) else 1


def metric_points(count: int, dimension: int, salt: int) -> list[float]:
    """Deterministic, unique-enough points strictly inside [-1, 1]^Dim."""

    values: list[float] = []
    mod = 104729
    multipliers = (7919, 15401, 31337)
    for row in range(count):
        for column in range(dimension):
            numerator = (
                (row + 1) * multipliers[column]
                + (salt + 11) * (column + 5) * 101
                + row * row * 17
            ) % mod
            values.append(-0.82 + 1.64 * numerator / (mod - 1))
    return values


def deterministic_weights(count: int, salt: int) -> list[float]:
    return [
        math.sin((index + 1) * (0.17 + salt * 0.001))
        + 0.25 * math.cos((index + 3) * 0.11)
        for index in range(count)
    ]


def resource_grant(
    *,
    persistent_bytes: int = 1 << 30,
    transient_bytes: int = 1 << 30,
    max_threads: int = 1,
) -> ResourceGrantV1:
    result = ResourceGrantV1()
    initialize_header(result)
    result.persistent_bytes = persistent_bytes
    result.transient_bytes = transient_bytes
    result.max_threads = max_threads
    result.reserved = 0
    return result


def error_dict(error: ErrorV1) -> dict[str, Any]:
    return {
        "stage": error.stage,
        "detail": error.detail,
        "offending_index": (
            None if error.offending_index == UNBOUNDED_QUANTUM else error.offending_index
        ),
        "incident_id": error.incident_id,
        "message": decode_char_array(error.message),
    }


def report_dict(report: ReportV1) -> dict[str, Any]:
    effective_threads: int | str = report.effective_threads
    if report.effective_threads == UNKNOWN_U32:
        effective_threads = "unknown"
    maximum_live_threads: int | str = report.maximum_live_threads
    if report.maximum_live_threads == UNKNOWN_U32:
        maximum_live_threads = "unknown"
    return {
        "route": ROUTE_NAMES.get(report.route, f"unknown-{report.route}"),
        "certificate_kind": report.certificate_kind,
        "configured_threads": report.configured_threads,
        "effective_threads": effective_threads,
        "maximum_live_threads": maximum_live_threads,
        "flags": report.flags,
        "output_value_count": report.output_value_count,
        "persistent_bytes_estimate": report.persistent_bytes_estimate,
        "transient_bytes_estimate": report.transient_bytes_estimate,
        "maximum_unpolled_work": (
            "unbounded"
            if report.maximum_unpolled_work == UNBOUNDED_QUANTUM
            else report.maximum_unpolled_work
        ),
        "diagnostic_abs_inf_error": finite_or_none(
            report.diagnostic_abs_inf_error
        ),
        "backend_revision": decode_char_array(report.backend_revision),
    }


def bind_library(dll: Path) -> ctypes.CDLL:
    library = ctypes.CDLL(str(dll))
    library.rrsf_plan_create_v1.argtypes = [
        ctypes.POINTER(PlanDescV1),
        ctypes.POINTER(ResourceGrantV1),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ErrorV1),
    ]
    library.rrsf_plan_create_v1.restype = ctypes.c_uint32
    library.rrsf_lane_open_v1.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(LaneDescV1),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ErrorV1),
    ]
    library.rrsf_lane_open_v1.restype = ctypes.c_uint32
    library.rrsf_lane_run_v1.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(RunDescV1),
        ctypes.POINTER(OutputV1),
        ctypes.POINTER(ReportV1),
        ctypes.POINTER(ErrorV1),
    ]
    library.rrsf_lane_run_v1.restype = ctypes.c_uint32
    library.rrsf_lane_request_cancel_v1.argtypes = [ctypes.c_void_p]
    library.rrsf_lane_request_cancel_v1.restype = None
    library.rrsf_lane_destroy_v1.argtypes = [ctypes.c_void_p]
    library.rrsf_lane_destroy_v1.restype = None
    library.rrsf_plan_destroy_v1.argtypes = [ctypes.c_void_p]
    library.rrsf_plan_destroy_v1.restype = None
    return library


def build_plan_descriptor(
    *,
    plan_kind: int,
    action: int,
    geometry: int,
    dimension: int,
    sources: list[float],
    targets: list[float] | None = None,
    fixed_weights: list[float] | None = None,
) -> tuple[PlanDescV1, dict[str, ctypes.Array[ctypes.c_double] | None]]:
    if len(sources) % dimension:
        raise ValueError("source values do not divide by dimension")
    target_values = targets or []
    weight_values = fixed_weights or []
    buffers = {
        "kernel": double_array([1.0, 0.55]),
        "sources": double_array(sources),
        "targets": double_array(target_values),
        "weights": double_array(weight_values),
    }
    descriptor = PlanDescV1()
    initialize_header(descriptor)
    descriptor.plan_kind = plan_kind
    descriptor.action = action
    descriptor.geometry = geometry
    descriptor.dimension = dimension
    descriptor.kernel = GAUSSIAN_PROBE_ONLY
    descriptor.reserved = 0
    descriptor.kernel_parameters = double_pointer(buffers["kernel"])
    descriptor.kernel_parameter_count = 2
    descriptor.fixed_sources = double_pointer(buffers["sources"])
    descriptor.source_count = len(sources) // dimension
    descriptor.fixed_source_value_count = len(sources)
    descriptor.fixed_targets = double_pointer(buffers["targets"])
    descriptor.target_count = len(target_values) // dimension
    descriptor.fixed_target_value_count = len(target_values)
    descriptor.fixed_weights = double_pointer(buffers["weights"])
    descriptor.fixed_weight_value_count = len(weight_values)
    descriptor.bbox_min[:] = [-1.0, -1.0, -1.0]
    descriptor.bbox_max[:] = [1.0, 1.0, 1.0]
    return descriptor, buffers


class NativePlan:
    def __init__(
        self,
        library: ctypes.CDLL,
        handle: ctypes.c_void_p,
        *,
        plan_kind: int,
        action: int,
        geometry: int,
        dimension: int,
        source_count: int,
        target_count: int,
        buffers: dict[str, ctypes.Array[ctypes.c_double] | None],
    ) -> None:
        self.library = library
        self.handle = handle
        self.plan_kind = plan_kind
        self.action = action
        self.geometry = geometry
        self.dimension = dimension
        self.source_count = source_count
        self.target_count = target_count
        self.buffers = buffers

    def open_lane(
        self,
        *,
        transient_bytes: int = 1 << 30,
        max_threads: int = 1,
    ) -> "NativeLane":
        descriptor = LaneDescV1()
        initialize_header(descriptor)
        descriptor.grant = resource_grant(
            persistent_bytes=1 << 30,
            transient_bytes=transient_bytes,
            max_threads=max_threads,
        )
        output_handle = ctypes.c_void_p()
        error = ErrorV1()
        initialize_header(error)
        status = self.library.rrsf_lane_open_v1(
            self.handle,
            ctypes.byref(descriptor),
            ctypes.byref(output_handle),
            ctypes.byref(error),
        )
        if status != OK_CERTIFIED:
            raise RuntimeError(
                f"rrsf_lane_open_v1 returned {status}: {error_dict(error)}"
            )
        return NativeLane(self, output_handle)

    def close(self) -> None:
        if self.handle:
            self.library.rrsf_plan_destroy_v1(self.handle)
            self.handle = ctypes.c_void_p()


class NativeLane:
    def __init__(self, plan: NativePlan, handle: ctypes.c_void_p) -> None:
        self.plan = plan
        self.library = plan.library
        self.handle = handle

    def request_cancel(self) -> None:
        self.library.rrsf_lane_request_cancel_v1(self.handle)

    def run(
        self,
        *,
        changing_weights: list[float] | None = None,
        changing_targets: list[float] | None = None,
        flags: int = RUN_ALLOW_UNCERTIFIED_EVIDENCE,
        requested_budget: float = 1e-6,
        weight_count_override: int | None = None,
        target_count_override: int | None = None,
        target_value_count_override: int | None = None,
        output_capacity_override: int | None = None,
    ) -> dict[str, Any]:
        weights = changing_weights or []
        targets = changing_targets or []
        weight_buffer = double_array(weights)
        target_buffer = double_array(targets)

        descriptor = RunDescV1()
        initialize_header(descriptor)
        descriptor.flags = flags
        descriptor.reserved = 0
        descriptor.changing_weights = double_pointer(weight_buffer)
        descriptor.changing_weight_value_count = (
            len(weights)
            if weight_count_override is None
            else weight_count_override
        )
        descriptor.changing_targets = double_pointer(target_buffer)
        inferred_target_count = (
            len(targets) // self.plan.dimension if targets else 0
        )
        descriptor.changing_target_count = (
            inferred_target_count
            if target_count_override is None
            else target_count_override
        )
        descriptor.changing_target_value_count = (
            len(targets)
            if target_value_count_override is None
            else target_value_count_override
        )
        descriptor.requested_abs_inf_budget = requested_budget

        if self.plan.plan_kind == WEIGHTS_VARY:
            expected_output_count = (
                self.plan.target_count
                * target_channels(self.plan.action, self.plan.dimension)
            )
        else:
            expected_output_count = (
                descriptor.changing_target_count
                * target_channels(self.plan.action, self.plan.dimension)
            )
        output_capacity = (
            expected_output_count
            if output_capacity_override is None
            else output_capacity_override
        )
        output_buffer = (
            (ctypes.c_double * output_capacity)(*[SENTINEL] * output_capacity)
            if output_capacity
            else None
        )
        output = OutputV1()
        initialize_header(output)
        output.values = double_pointer(output_buffer)
        output.value_capacity = output_capacity
        output.value_count = 77

        report = ReportV1()
        initialize_header(report)
        error = ErrorV1()
        initialize_header(error)
        status = self.library.rrsf_lane_run_v1(
            self.handle,
            ctypes.byref(descriptor),
            ctypes.byref(output),
            ctypes.byref(report),
            ctypes.byref(error),
        )
        raw_output = (
            [output_buffer[index] for index in range(output_capacity)]
            if output_buffer is not None
            else []
        )
        published = raw_output[: output.value_count]
        return {
            "status": int(status),
            "status_name": STATUS_NAMES.get(int(status), f"STATUS_{status}"),
            "requested_abs_inf_budget": requested_budget,
            "value_count": int(output.value_count),
            "published_values": published,
            "output_checksum": (
                math.fsum((index + 1) * value for index, value in enumerate(published))
                if published
                else 0.0
            ),
            "sentinel_preserved": all(value == SENTINEL for value in raw_output),
            "report": report_dict(report),
            "error": error_dict(error),
        }

    def close(self) -> None:
        if self.handle:
            self.library.rrsf_lane_destroy_v1(self.handle)
            self.handle = ctypes.c_void_p()


def create_plan(
    library: ctypes.CDLL,
    *,
    plan_kind: int,
    action: int,
    geometry: int,
    dimension: int,
    sources: list[float],
    targets: list[float] | None = None,
    fixed_weights: list[float] | None = None,
    persistent_bytes: int = 1 << 30,
) -> NativePlan:
    descriptor, buffers = build_plan_descriptor(
        plan_kind=plan_kind,
        action=action,
        geometry=geometry,
        dimension=dimension,
        sources=sources,
        targets=targets,
        fixed_weights=fixed_weights,
    )
    grant = resource_grant(persistent_bytes=persistent_bytes)
    handle = ctypes.c_void_p()
    error = ErrorV1()
    initialize_header(error)
    status = library.rrsf_plan_create_v1(
        ctypes.byref(descriptor),
        ctypes.byref(grant),
        ctypes.byref(handle),
        ctypes.byref(error),
    )
    if status != OK_CERTIFIED:
        raise RuntimeError(
            f"rrsf_plan_create_v1 returned {status}: {error_dict(error)}"
        )
    return NativePlan(
        library,
        handle,
        plan_kind=plan_kind,
        action=action,
        geometry=geometry,
        dimension=dimension,
        source_count=descriptor.source_count,
        target_count=descriptor.target_count,
        buffers=buffers,
    )


def raw_plan_status(
    library: ctypes.CDLL,
    descriptor: PlanDescV1,
    grant: ResourceGrantV1,
) -> tuple[int, dict[str, Any]]:
    handle = ctypes.c_void_p()
    error = ErrorV1()
    initialize_header(error)
    status = int(
        library.rrsf_plan_create_v1(
            ctypes.byref(descriptor),
            ctypes.byref(grant),
            ctypes.byref(handle),
            ctypes.byref(error),
        )
    )
    if handle:
        library.rrsf_plan_destroy_v1(handle)
    return status, error_dict(error)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def binary_file_observation(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.exists():
        return {"path": str(resolved), "exists": False}
    return {
        "path": str(resolved),
        "exists": True,
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256(resolved),
    }


def git_revision(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def dumpbin_inventory(
    dll: Path, dumpbin: Path | None
) -> dict[str, Any]:
    if dumpbin is None or not dumpbin.exists():
        return {
            "available": False,
            "dependencies": [],
            "exports": [],
        }
    dependencies_text = subprocess.run(
        [str(dumpbin), "/DEPENDENTS", str(dll)],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    exports_text = subprocess.run(
        [str(dumpbin), "/EXPORTS", str(dll)],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    dependencies = sorted(
        {
            line.strip()
            for line in dependencies_text.splitlines()
            if re.fullmatch(r"[A-Za-z0-9_.-]+\.dll", line.strip(), re.IGNORECASE)
        },
        key=str.lower,
    )
    exports = sorted(
        set(re.findall(r"\brrsf_[a-z0-9_]+_v1\b", exports_text))
    )
    return {
        "available": True,
        "tool": str(dumpbin),
        "dependencies": dependencies,
        "exports": exports,
    }


def process_memory() -> dict[str, int]:
    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCountersEx),
        ctypes.c_uint32,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    process = kernel32.GetCurrentProcess()
    ok = psapi.GetProcessMemoryInfo(
        process, ctypes.byref(counters), counters.cb
    )
    if not ok:
        raise ctypes.WinError()
    return {
        "private_bytes": int(counters.private_usage),
        "working_set_bytes": int(counters.working_set_size),
    }


def max_abs_difference(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return math.inf
    return max((abs(a - b) for a, b in zip(left, right)), default=0.0)


def observed_case(result: dict[str, Any]) -> dict[str, Any]:
    diagnostic = result["report"]["diagnostic_abs_inf_error"]
    requested_budget = result["requested_abs_inf_budget"]
    return {
        "status": result["status_name"],
        "requested_abs_inf_budget": requested_budget,
        "value_count": result["value_count"],
        "output_checksum": result["output_checksum"],
        "route": result["report"]["route"],
        "certificate_kind": result["report"]["certificate_kind"],
        "diagnostic_abs_inf_error": diagnostic,
        "diagnostic_exceeds_requested_budget": (
            diagnostic is not None and diagnostic > requested_budget
        ),
        "configured_threads": result["report"]["configured_threads"],
        "effective_threads": result["report"]["effective_threads"],
        "maximum_live_threads": result["report"]["maximum_live_threads"],
        "report_flags": result["report"]["flags"],
        "backend_revision": result["report"]["backend_revision"],
    }


def exercise_probe(
    library: ctypes.CDLL,
    *,
    polatory_root: Path,
    dll: Path,
    dumpbin: Path | None,
    fmm_size: int,
    repeats: int,
) -> tuple[dict[str, Any], bool]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    inventory = dumpbin_inventory(dll, dumpbin)
    triplet = (
        polatory_root / "build" / "vcpkg_installed" / "x64-windows"
    )
    linked_binary_inputs = {
        "polatory_static_library": binary_file_observation(
            polatory_root / "build" / "src" / "polatory.lib"
        ),
        "llvm_openmp_import_library": binary_file_observation(
            Path(
                r"C:\Program Files\Microsoft Visual Studio\2022\Community"
                r"\VC\Tools\MSVC\14.44.35207\lib\x64\libomp.lib"
            )
        ),
        "mkl_intel_lp64_import_library": binary_file_observation(
            triplet / "lib" / "intel64" / "mkl_intel_lp64_dll.lib"
        ),
        "mkl_sequential_import_library": binary_file_observation(
            triplet / "lib" / "intel64" / "mkl_sequential_dll.lib"
        ),
        "mkl_core_import_library": binary_file_observation(
            triplet / "lib" / "intel64" / "mkl_core_dll.lib"
        ),
        "llvm_openmp_runtime": binary_file_observation(
            polatory_root / "build" / "cli" / "libomp140.x86_64.dll"
        ),
        "mkl_sequential_runtime": binary_file_observation(
            polatory_root / "build" / "cli" / "mkl_sequential.2.dll"
        ),
        "mkl_core_runtime": binary_file_observation(
            polatory_root / "build" / "cli" / "mkl_core.2.dll"
        ),
    }
    check(
        "linked-binary-inputs-are-content-identified",
        all(item["exists"] for item in linked_binary_inputs.values()),
        linked_binary_inputs,
    )
    c_smoke = dll.parent / "rapidrbf_scalfmm_c_smoke.exe"
    c_smoke_result: dict[str, Any] = binary_file_observation(c_smoke)
    if c_smoke.exists():
        smoke_environment = os.environ.copy()
        smoke_environment["PATH"] = os.pathsep.join(
            [
                str(dll.parent),
                str(polatory_root / "build" / "cli"),
                str(triplet / "bin"),
                smoke_environment.get("PATH", ""),
            ]
        )
        completed = subprocess.run(
            [str(c_smoke)],
            capture_output=True,
            text=True,
            errors="replace",
            env=smoke_environment,
        )
        c_smoke_result["returncode"] = completed.returncode
        c_smoke_result["stdout"] = completed.stdout
        c_smoke_result["stderr"] = completed.stderr
    check(
        "header-compiles-and-c-caller-crosses-versioned-abi",
        c_smoke_result.get("returncode") == 0,
        c_smoke_result,
    )
    inventory["c_header_smoke"] = c_smoke_result
    expected_exports = {
        "rrsf_plan_create_v1",
        "rrsf_lane_open_v1",
        "rrsf_lane_run_v1",
        "rrsf_lane_request_cancel_v1",
        "rrsf_lane_destroy_v1",
        "rrsf_plan_destroy_v1",
    }
    check(
        "six-versioned-c-exports",
        set(inventory["exports"]) == expected_exports,
        inventory["exports"],
    )

    base_sources = metric_points(6, 2, 1)
    base_targets = metric_points(5, 2, 2)
    descriptor, descriptor_buffers = build_plan_descriptor(
        plan_kind=WEIGHTS_VARY,
        action=A,
        geometry=CROSS,
        dimension=2,
        sources=base_sources,
        targets=base_targets,
    )
    descriptor.struct_size -= 1
    status, error = raw_plan_status(
        library, descriptor, resource_grant()
    )
    check(
        "abi-size-mismatch-is-stable",
        status == ABI_MISMATCH,
        {"status": STATUS_NAMES.get(status), "error": error},
    )
    descriptor.struct_size += 1
    invalid_error = ErrorV1()
    untouched_handle = ctypes.c_void_p()
    status = int(
        library.rrsf_plan_create_v1(
            ctypes.byref(descriptor),
            ctypes.byref(resource_grant()),
            ctypes.byref(untouched_handle),
            ctypes.byref(invalid_error),
        )
    )
    check(
        "invalid-error-layout-is-not-written",
        (
            status == ABI_MISMATCH
            and invalid_error.struct_size == 0
            and not untouched_handle
        ),
        {
            "status": STATUS_NAMES.get(status),
            "error_struct_size_after_call": invalid_error.struct_size,
            "out_plan_is_null": not bool(untouched_handle),
        },
    )
    status, error = raw_plan_status(
        library, descriptor, resource_grant(persistent_bytes=0)
    )
    check(
        "persistent-grant-is-admitted-before-plan-copy",
        status == RESOURCE_EXHAUSTED,
        {"status": STATUS_NAMES.get(status), "error": error},
    )
    # Keep descriptor buffers alive through both raw calls.
    _ = descriptor_buffers

    lifecycle: dict[str, Any] = {}
    plan = create_plan(
        library,
        plan_kind=WEIGHTS_VARY,
        action=A,
        geometry=CROSS,
        dimension=2,
        sources=base_sources,
        targets=base_targets,
    )
    baseline_plan: NativePlan | None = None
    lane: NativeLane | None = None
    baseline_lane: NativeLane | None = None
    exception_lane: NativeLane | None = None
    replacement_lane: NativeLane | None = None
    try:
        copied_sources = plan.buffers["sources"]
        assert copied_sources is not None
        copied_sources[0] = 0.97
        weights = deterministic_weights(6, 4)
        lane = plan.open_lane()
        copied_run = lane.run(
            changing_weights=weights,
            flags=(
                RUN_ALLOW_UNCERTIFIED_EVIDENCE
                | RUN_FULL_DIRECT_DIAGNOSTIC
            ),
        )
        baseline_plan = create_plan(
            library,
            plan_kind=WEIGHTS_VARY,
            action=A,
            geometry=CROSS,
            dimension=2,
            sources=base_sources,
            targets=base_targets,
        )
        baseline_lane = baseline_plan.open_lane()
        baseline_run = baseline_lane.run(
            changing_weights=weights,
            flags=(
                RUN_ALLOW_UNCERTIFIED_EVIDENCE
                | RUN_FULL_DIRECT_DIAGNOSTIC
            ),
        )
        copy_difference = max_abs_difference(
            copied_run["published_values"], baseline_run["published_values"]
        )
        lifecycle["plan_input_copy"] = {
            "mutated_caller_source_after_prepare": True,
            "max_abs_difference_from_fresh_original_plan": copy_difference,
            "report_flags": copied_run["report"]["flags"],
        }
        check(
            "fixed-inputs-are-owned-copies",
            (
                copied_run["status"] == OK_UNCERTIFIED_EVIDENCE
                and baseline_run["status"] == OK_UNCERTIFIED_EVIDENCE
                and copy_difference <= 1e-13
                and copied_run["report"]["flags"] & REPORT_INPUTS_COPIED
            ),
            lifecycle["plan_input_copy"],
        )

        invalid_length = lane.run(
            changing_weights=weights,
            weight_count_override=len(weights) - 1,
            flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
        )
        lifecycle["invalid_length"] = {
            "status": invalid_length["status_name"],
            "output_sentinel_preserved": invalid_length["sentinel_preserved"],
            "error": invalid_length["error"],
        }
        check(
            "invalid-length-does-not-publish",
            (
                invalid_length["status"] == INVALID_REQUEST
                and invalid_length["value_count"] == 0
                and invalid_length["sentinel_preserved"]
            ),
            lifecycle["invalid_length"],
        )

        no_certificate = lane.run(
            changing_weights=weights,
            flags=RUN_FULL_DIRECT_DIAGNOSTIC,
        )
        lifecycle["certificate_gate"] = {
            "status": no_certificate["status_name"],
            "output_sentinel_preserved": no_certificate["sentinel_preserved"],
            "diagnostic_kind": no_certificate["report"]["certificate_kind"],
            "diagnostic_abs_inf_error": no_certificate["report"][
                "diagnostic_abs_inf_error"
            ],
        }
        check(
            "diagnostic-is-not-promoted-to-certificate",
            (
                no_certificate["status"] == CERTIFICATE_UNAVAILABLE
                and no_certificate["value_count"] == 0
                and no_certificate["sentinel_preserved"]
                and no_certificate["report"]["certificate_kind"]
                == CERTIFICATE_FULL_DIRECT_DIAGNOSTIC
            ),
            lifecycle["certificate_gate"],
        )

        lane.request_cancel()
        cancelled = lane.run(
            changing_weights=weights,
            flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
        )
        lifecycle["pre_cancel"] = {
            "status": cancelled["status_name"],
            "output_sentinel_preserved": cancelled["sentinel_preserved"],
        }
        check(
            "pre-cancel-does-not-publish",
            (
                cancelled["status"] == CANCELLED
                and cancelled["value_count"] == 0
                and cancelled["sentinel_preserved"]
            ),
            lifecycle["pre_cancel"],
        )

        recovered = lane.run(
            changing_weights=weights,
            flags=(
                RUN_ALLOW_UNCERTIFIED_EVIDENCE
                | RUN_FULL_DIRECT_DIAGNOSTIC
            ),
        )
        lifecycle["recovery"] = observed_case(recovered)
        check(
            "lane-reusable-after-validation-certificate-and-cancel-failures",
            recovered["status"] == OK_UNCERTIFIED_EVIDENCE,
            lifecycle["recovery"],
        )

        openmp = ctypes.CDLL(
            str(polatory_root / "build" / "cli" / "libomp140.x86_64.dll")
        )
        openmp.omp_get_dynamic.argtypes = []
        openmp.omp_get_dynamic.restype = ctypes.c_int
        openmp.omp_set_dynamic.argtypes = [ctypes.c_int]
        openmp.omp_set_dynamic.restype = None
        openmp.omp_get_max_threads.argtypes = []
        openmp.omp_get_max_threads.restype = ctypes.c_int
        openmp.omp_set_num_threads.argtypes = [ctypes.c_int]
        openmp.omp_set_num_threads.restype = None
        original_dynamic = openmp.omp_get_dynamic()
        original_max_threads = openmp.omp_get_max_threads()
        try:
            openmp.omp_set_dynamic(1)
            openmp.omp_set_num_threads(3)
            configured_before = {
                "dynamic": openmp.omp_get_dynamic(),
                "max_threads": openmp.omp_get_max_threads(),
            }
            settings_run = lane.run(
                changing_weights=weights,
                flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
            )
            configured_after = {
                "dynamic": openmp.omp_get_dynamic(),
                "max_threads": openmp.omp_get_max_threads(),
            }
        finally:
            openmp.omp_set_dynamic(original_dynamic)
            openmp.omp_set_num_threads(original_max_threads)
        lifecycle["openmp_settings"] = {
            "before": configured_before,
            "after": configured_after,
            "run_status": settings_run["status_name"],
        }
        check(
            "caller-openmp-settings-are-restored",
            (
                settings_run["status"] == OK_UNCERTIFIED_EVIDENCE
                and configured_before == configured_after
            ),
            lifecycle["openmp_settings"],
        )

        exception_lane = plan.open_lane()
        forced_exception = exception_lane.run(
            changing_weights=weights,
            flags=(
                RUN_ALLOW_UNCERTIFIED_EVIDENCE
                | RUN_FORCE_EXCEPTION_FOR_PROBE
            ),
        )
        poisoned_followup = exception_lane.run(
            changing_weights=weights,
            flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
        )
        replacement_lane = plan.open_lane()
        replacement_run = replacement_lane.run(
            changing_weights=weights,
            flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
        )
        lifecycle["forced_exception"] = {
            "forced_status": forced_exception["status_name"],
            "forced_values_sentinel_preserved": forced_exception[
                "sentinel_preserved"
            ],
            "poisoned_followup_status": poisoned_followup["status_name"],
            "replacement_lane_status": replacement_run["status_name"],
        }
        check(
            "forced-exception-is-contained-and-poisons-only-that-lane",
            (
                forced_exception["status"] == INTERNAL_FAILURE
                and forced_exception["value_count"] == 0
                and forced_exception["sentinel_preserved"]
                and poisoned_followup["status"] == INTERNAL_FAILURE
                and replacement_run["status"] == OK_UNCERTIFIED_EVIDENCE
            ),
            lifecycle["forced_exception"],
        )
    finally:
        if replacement_lane is not None:
            replacement_lane.close()
        if exception_lane is not None:
            exception_lane.close()
        if baseline_lane is not None:
            baseline_lane.close()
        if baseline_plan is not None:
            baseline_plan.close()
        if lane is not None:
            lane.close()
        plan.close()

    operator_matrix: list[dict[str, Any]] = []
    for dimension in (1, 2, 3):
        for action in (A, F, FT, H):
            for geometry in (SELF, CROSS):
                source_count = 9
                sources = metric_points(source_count, dimension, 10 + action)
                targets = (
                    list(sources)
                    if geometry == SELF
                    else metric_points(7, dimension, 20 + action)
                )
                weights = deterministic_weights(
                    source_count * source_channels(action, dimension),
                    30 + dimension + action,
                )
                plan = create_plan(
                    library,
                    plan_kind=WEIGHTS_VARY,
                    action=action,
                    geometry=geometry,
                    dimension=dimension,
                    sources=sources,
                    targets=targets,
                )
                lane = plan.open_lane()
                try:
                    run = lane.run(
                        changing_weights=weights,
                        flags=(
                            RUN_ALLOW_UNCERTIFIED_EVIDENCE
                            | RUN_FULL_DIRECT_DIAGNOSTIC
                        ),
                    )
                    case = {
                        "dimension": dimension,
                        "action": ACTION_NAMES[action],
                        "geometry": GEOMETRY_NAMES[geometry],
                        **observed_case(run),
                    }
                    operator_matrix.append(case)
                finally:
                    lane.close()
                    plan.close()
    operator_matrix_passed = all(
        case["status"] == "OK_UNCERTIFIED_EVIDENCE"
        and case["route"] == "legacy-direct"
        and case["certificate_kind"] == CERTIFICATE_FULL_DIRECT_DIAGNOSTIC
        and case["diagnostic_abs_inf_error"] is not None
        and case["diagnostic_abs_inf_error"] <= 1e-11
        and case["backend_revision"] == SCALFMM_REVISION
        for case in operator_matrix
    )
    check(
        "operator-mechanics-cover-dimensions-actions-and-geometries",
        operator_matrix_passed and len(operator_matrix) == 24,
        {"case_count": len(operator_matrix), "cases": operator_matrix},
    )

    field_matrix: list[dict[str, Any]] = []
    for dimension in (1, 2, 3):
        for action in (A, F, FT, H):
            source_count = 9
            sources = metric_points(source_count, dimension, 40 + action)
            fixed_weights = deterministic_weights(
                source_count * source_channels(action, dimension),
                50 + dimension + action,
            )
            targets = metric_points(7, dimension, 60 + action)
            plan = create_plan(
                library,
                plan_kind=TARGETS_VARY,
                action=action,
                geometry=CROSS,
                dimension=dimension,
                sources=sources,
                fixed_weights=fixed_weights,
            )
            lane = plan.open_lane()
            try:
                run = lane.run(
                    changing_targets=targets,
                    flags=(
                        RUN_ALLOW_UNCERTIFIED_EVIDENCE
                        | RUN_FULL_DIRECT_DIAGNOSTIC
                    ),
                )
                case = {
                    "dimension": dimension,
                    "action": ACTION_NAMES[action],
                    "geometry": "cross",
                    **observed_case(run),
                }
                field_matrix.append(case)
            finally:
                lane.close()
                plan.close()
    field_matrix_passed = all(
        case["status"] == "OK_UNCERTIFIED_EVIDENCE"
        and case["route"] == "legacy-direct"
        and case["certificate_kind"] == CERTIFICATE_FULL_DIRECT_DIAGNOSTIC
        and case["diagnostic_abs_inf_error"] is not None
        and case["diagnostic_abs_inf_error"] <= 1e-11
        for case in field_matrix
    )
    check(
        "field-mechanics-cover-dimensions-and-actions",
        field_matrix_passed and len(field_matrix) == 12,
        {"case_count": len(field_matrix), "cases": field_matrix},
    )

    large_route_matrix: list[dict[str, Any]] = []
    for dimension in (1, 2, 3):
        for action in (A, F, FT, H):
            for geometry in (SELF, CROSS):
                sources = metric_points(
                    fmm_size, dimension, 100 + 10 * dimension + action
                )
                targets = (
                    list(sources)
                    if geometry == SELF
                    else metric_points(
                        fmm_size, dimension, 200 + 10 * dimension + action
                    )
                )
                weights = deterministic_weights(
                    fmm_size * source_channels(action, dimension),
                    300 + 10 * dimension + action,
                )
                plan = create_plan(
                    library,
                    plan_kind=WEIGHTS_VARY,
                    action=action,
                    geometry=geometry,
                    dimension=dimension,
                    sources=sources,
                    targets=targets,
                )
                lane = plan.open_lane(max_threads=2)
                try:
                    run = lane.run(
                        changing_weights=weights,
                        flags=(
                            RUN_ALLOW_UNCERTIFIED_EVIDENCE
                            | RUN_FULL_DIRECT_DIAGNOSTIC
                        ),
                    )
                    large_route_matrix.append(
                        {
                            "workflow": PLAN_NAMES[WEIGHTS_VARY],
                            "dimension": dimension,
                            "action": ACTION_NAMES[action],
                            "geometry": GEOMETRY_NAMES[geometry],
                            **observed_case(run),
                        }
                    )
                finally:
                    lane.close()
                    plan.close()

            sources = metric_points(
                fmm_size, dimension, 400 + 10 * dimension + action
            )
            fixed_weights = deterministic_weights(
                fmm_size * source_channels(action, dimension),
                500 + 10 * dimension + action,
            )
            targets = metric_points(
                fmm_size, dimension, 600 + 10 * dimension + action
            )
            plan = create_plan(
                library,
                plan_kind=TARGETS_VARY,
                action=action,
                geometry=CROSS,
                dimension=dimension,
                sources=sources,
                fixed_weights=fixed_weights,
            )
            lane = plan.open_lane(max_threads=2)
            try:
                run = lane.run(
                    changing_targets=targets,
                    flags=(
                        RUN_ALLOW_UNCERTIFIED_EVIDENCE
                        | RUN_FULL_DIRECT_DIAGNOSTIC
                    ),
                )
                large_route_matrix.append(
                    {
                        "workflow": PLAN_NAMES[TARGETS_VARY],
                        "dimension": dimension,
                        "action": ACTION_NAMES[action],
                        "geometry": "cross",
                        **observed_case(run),
                    }
                )
            finally:
                lane.close()
                plan.close()

    large_route_matrix_passed = all(
        case["status"] == "OK_UNCERTIFIED_EVIDENCE"
        and case["route"] == "scalfmm"
        and case["certificate_kind"] == CERTIFICATE_FULL_DIRECT_DIAGNOSTIC
        and case["diagnostic_abs_inf_error"] is not None
        and case["backend_revision"] == SCALFMM_REVISION
        for case in large_route_matrix
    )
    check(
        "scalfmm-route-mechanics-cover-both-workflows-all-actions-and-dimensions",
        large_route_matrix_passed and len(large_route_matrix) == 36,
        {"case_count": len(large_route_matrix), "cases": large_route_matrix},
    )

    empty_plan = create_plan(
        library,
        plan_kind=TARGETS_VARY,
        action=H,
        geometry=CROSS,
        dimension=3,
        sources=metric_points(5, 3, 70),
        fixed_weights=deterministic_weights(15, 71),
    )
    empty_lane = empty_plan.open_lane()
    try:
        out_of_bbox = empty_lane.run(
            changing_targets=[1.25, 0.0, 0.0],
            flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
        )
        empty_run = empty_lane.run(
            changing_targets=[],
            flags=(
                RUN_ALLOW_UNCERTIFIED_EVIDENCE
                | RUN_FULL_DIRECT_DIAGNOSTIC
            ),
        )
    finally:
        empty_lane.close()
        empty_plan.close()
    check(
        "out-of-bbox-target-is-rejected-without-publication",
        (
            out_of_bbox["status"] == INVALID_REQUEST
            and out_of_bbox["value_count"] == 0
            and out_of_bbox["sentinel_preserved"]
        ),
        {
            "status": out_of_bbox["status_name"],
            "output_sentinel_preserved": out_of_bbox["sentinel_preserved"],
            "error": out_of_bbox["error"],
        },
    )
    check(
        "empty-field-target-batch-is-valid",
        (
            empty_run["status"] == OK_UNCERTIFIED_EVIDENCE
            and empty_run["value_count"] == 0
            and empty_run["report"]["diagnostic_abs_inf_error"] == 0.0
        ),
        observed_case(empty_run),
    )

    fmm_sources = metric_points(fmm_size, 2, 80)
    fmm_targets = metric_points(fmm_size, 2, 81)
    fmm_weights = deterministic_weights(fmm_size, 82)
    fmm_plan = create_plan(
        library,
        plan_kind=WEIGHTS_VARY,
        action=A,
        geometry=CROSS,
        dimension=2,
        sources=fmm_sources,
        targets=fmm_targets,
    )
    fmm_lane = fmm_plan.open_lane(max_threads=2)
    fmm_observation: dict[str, Any] = {}
    try:
        first = fmm_lane.run(
            changing_weights=fmm_weights,
            flags=(
                RUN_ALLOW_UNCERTIFIED_EVIDENCE
                | RUN_FULL_DIRECT_DIAGNOSTIC
            ),
        )
        fmm_observation["first_run"] = observed_case(first)
        check(
            "actual-scalfmm-route-executes",
            (
                first["status"] == OK_UNCERTIFIED_EVIDENCE
                and first["report"]["route"] == "scalfmm"
                and first["report"]["diagnostic_abs_inf_error"] is not None
                and first["report"]["maximum_unpolled_work"] == "unbounded"
            ),
            fmm_observation["first_run"],
        )

        memory_samples: list[dict[str, int]] = []
        repeat_statuses: list[str] = []
        for _index in range(repeats):
            repeated = fmm_lane.run(
                changing_weights=fmm_weights,
                flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
            )
            repeat_statuses.append(repeated["status_name"])
            del repeated
            gc.collect()
            memory_samples.append(process_memory())
        private_values = [sample["private_bytes"] for sample in memory_samples]
        private_span = max(private_values) - min(private_values)
        private_delta = private_values[-1] - private_values[0]
        fmm_observation["repeated_evaluation_memory"] = {
            "iterations": repeats,
            "statuses": repeat_statuses,
            "samples": memory_samples,
            "private_span_bytes": private_span,
            "last_minus_first_private_bytes": private_delta,
            "probe_only_bound_bytes": 128 << 20,
            "note": (
                "Process-wide short-run observation; this is not the "
                "1k->10k->100k or million-scale acceptance evidence."
            ),
        }
        check(
            "short-run-memory-sample-is-bounded",
            (
                all(status == "OK_UNCERTIFIED_EVIDENCE" for status in repeat_statuses)
                and private_span <= 128 << 20
            ),
            fmm_observation["repeated_evaluation_memory"],
        )

        concurrent: list[dict[str, Any] | None] = [None, None]
        barrier = threading.Barrier(2)

        def concurrent_call(slot: int) -> None:
            barrier.wait()
            concurrent[slot] = fmm_lane.run(
                changing_weights=fmm_weights,
                flags=RUN_ALLOW_UNCERTIFIED_EVIDENCE,
            )

        worker = threading.Thread(target=concurrent_call, args=(0,))
        worker.start()
        concurrent_call(1)
        worker.join()
        concurrent_statuses = sorted(
            result["status"] for result in concurrent if result is not None
        )
        fmm_observation["exclusive_lane"] = {
            "statuses": [
                STATUS_NAMES.get(status, f"STATUS_{status}")
                for status in concurrent_statuses
            ]
        }
        check(
            "concurrent-lane-call-is-rejected",
            concurrent_statuses == [OK_UNCERTIFIED_EVIDENCE, BUSY],
            fmm_observation["exclusive_lane"],
        )
    finally:
        fmm_lane.close()
        fmm_plan.close()

    required_flags = (
        REPORT_INPUTS_COPIED
        | REPORT_OUTPUT_STAGED
        | REPORT_RESOURCE_ACCOUNTING_PARTIAL
        | REPORT_THREAD_ACCOUNTING_PARTIAL
        | REPORT_CANCELLATION_QUANTUM_UNBOUNDED
        | REPORT_WEIGHT_SENSITIVE_CONFIG_UNCERTIFIED
    )
    first_flags = fmm_observation["first_run"]["report_flags"]
    check(
        "report-does-not-hide-known-operational-gaps",
        (
            first_flags & required_flags == required_flags
            and fmm_observation["first_run"]["effective_threads"] == "unknown"
            and fmm_observation["first_run"]["maximum_live_threads"]
            == "unknown"
            and fmm_observation["first_run"]["configured_threads"] == 2
        ),
        {
            "flags": first_flags,
            "required_flags": required_flags,
            "configured_threads": fmm_observation["first_run"][
                "configured_threads"
            ],
            "effective_threads": fmm_observation["first_run"][
                "effective_threads"
            ],
            "maximum_live_threads": fmm_observation["first_run"][
                "maximum_live_threads"
            ],
        },
    )

    polatory_revision = git_revision(polatory_root)
    scalfmm_root = (
        polatory_root / "build" / "scalfmm" / "src" / "scalfmm"
    )
    scalfmm_revision = git_revision(scalfmm_root)
    check(
        "frozen-source-revisions",
        (
            polatory_revision == POLATORY_REVISION
            and scalfmm_revision == SCALFMM_REVISION
        ),
        {
            "polatory": polatory_revision,
            "scalfmm": scalfmm_revision,
        },
    )

    all_passed = all(item["passed"] for item in checks)
    result = {
        "schema": "rapidrbf-scalfmm3-abi-observation/v1",
        "question": (
            "Can a versioned caller-first C shim mechanically contain the "
            "frozen Polatory/ScalFMM evaluator, and which observed gaps still "
            "disqualify it from large-workload Auto?"
        ),
        "classification": "COLLECTED, UNJUDGED",
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "frozen_inputs": {
            "polatory_revision": polatory_revision,
            "scalfmm_revision": scalfmm_revision,
            "dll": str(dll),
            "dll_sha256": sha256(dll),
            "dll_hash_role": (
                "Per-build identity; the current linker is not configured for "
                "reproducible PE output, so this hash may change on relink."
            ),
            "linked_binary_inputs": linked_binary_inputs,
            "provenance_limit": (
                "Hashes identify the reused local artifacts but do not prove "
                "that polatory.lib was built from the observed checkout heads."
            ),
        },
        "binary_inventory": inventory,
        "checks": checks,
        "observations": {
            "lifecycle_and_publication": lifecycle,
            "operator_matrix": operator_matrix,
            "field_matrix": field_matrix,
            "scalfmm_route_matrix": large_route_matrix,
            "empty_target_batch": observed_case(empty_run),
            "scalfmm_route": fmm_observation,
        },
        "observed_or_source_inspected_gaps": {
            "sound_complete_batch_call_certificate_available": False,
            "finite_in_flight_cancellation_quantum_available": False,
            "native_allocation_and_thread_grants_fully_enforced": False,
            "prepared_tree_and_multipole_reuse_observed": False,
            "accepted_scale_memory_evidence_collected": False,
            "tier_one_runtime_and_license_closure_collected": False,
        },
        "limits": [
            "Only the Gaussian family was compiled into this throwaway shim.",
            "Direct comparisons are diagnostics, not sound certificates.",
            "Short-run RSS/private-byte observations are not scale qualification.",
            "The probe uses an existing local Windows build, not a clean host.",
            "The embedded backend revision is a shim declaration, not binary provenance.",
            "No exception originating inside an OpenMP worker was exercised.",
            "License inventory is engineering evidence, not legal advice.",
        ],
        "all_mechanical_checks_passed": all_passed,
    }
    return result, all_passed


def main() -> int:
    parser = argparse.ArgumentParser()
    probe_root = Path(__file__).resolve().parent
    parser.add_argument(
        "--dll",
        type=Path,
        default=probe_root / "build-vs" / "rapidrbf_scalfmm_probe.dll",
    )
    parser.add_argument(
        "--polatory-root",
        type=Path,
        default=Path(r"D:\CODE\polatory"),
    )
    parser.add_argument(
        "--dumpbin",
        type=Path,
        default=Path(
            r"C:\Program Files\Microsoft Visual Studio\2022\Community"
            r"\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe"
        ),
    )
    parser.add_argument("--fmm-size", type=int, default=1024)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if os.name != "nt":
        raise SystemExit("this observed probe targets the frozen Windows build")
    if args.fmm_size < 1024:
        raise SystemExit("--fmm-size must be at least 1024 to enter ScalFMM")
    if args.repeats < 3:
        raise SystemExit("--repeats must be at least 3")

    dll = args.dll.resolve()
    polatory_root = args.polatory_root.resolve()
    if not dll.exists():
        raise SystemExit(f"probe DLL does not exist: {dll}")

    dll_search_dirs = [
        dll.parent,
        polatory_root / "build" / "cli",
        polatory_root / "build" / "vcpkg_installed" / "x64-windows" / "bin",
    ]
    directory_handles = [
        os.add_dll_directory(str(path))
        for path in dll_search_dirs
        if path.exists()
    ]
    try:
        library = bind_library(dll)
        result, passed = exercise_probe(
            library,
            polatory_root=polatory_root,
            dll=dll,
            dumpbin=args.dumpbin.resolve() if args.dumpbin else None,
            fmm_size=args.fmm_size,
            repeats=args.repeats,
        )
    finally:
        for handle in directory_handles:
            handle.close()

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
