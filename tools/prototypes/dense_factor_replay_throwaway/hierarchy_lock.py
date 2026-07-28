#!/usr/bin/env python3
"""Close and verify the immutable file set of a hierarchy capture.

The C++ capture deliberately writes a raw, hash-free manifest.  This tool is
the separate publication boundary: it rejects stale or unreferenced payloads,
binds every artifact and generator/native input, and emits one canonical
content digest.  It never runs a factor backend or assigns semantic rank.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

PROTOTYPE_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = PROTOTYPE_DIR / "capture"
HIERARCHY_CMAKE = CAPTURE_DIR / "hierarchy" / "CMakeLists.txt"
CAPTURE_SCHEMA = "rapidrbf-canonical-hierarchy-admission-corpus-v3"
LOCK_SCHEMA = "rapidrbf-canonical-hierarchy-corpus-lock-v3"
RAW_MANIFEST_NAME = "hierarchy.manifest.raw.json"
POLATORY_COMMIT = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"

EXPECTED_COUNTS = {
    "workloads": 12,
    "blocks": 204,
    "fine_blocks": 192,
    "coarse_blocks": 12,
    "factor_sources": 216,
    "qtaq_factor_sources": 204,
    "p_top_factor_sources": 12,
    "auxiliary_decomposition_sources": 12,
    "controls": 1,
    "artifacts": 2738,
}

NATIVE_CLOSURE = {
    "lib/intel64/mkl_intel_lp64_dll.lib": "487b430c0a2bcca41dc40abcab8cbc18471701b621efb850136f6d45821f5db4",
    "lib/intel64/mkl_sequential_dll.lib": "3859198460bd0d04a617a7fecb9ceb9c18f7e8b14ebcb439a0eebaca7b9d01b2",
    "lib/intel64/mkl_core_dll.lib": "110c0433d4665f8535174059d9042992cd88e566c7b2b13281fd776a7d46cc02",
    "bin/mkl_core.2.dll": "3e7edb4328abf430b62c7c75e33447042dc8033f0cc75910708fd3bb5f27c792",
    "bin/mkl_sequential.2.dll": "478fda28a98021fb7f95b27b2876cac7346d77c4a491003ba0f50baf17b66fe3",
    "bin/mkl_def.2.dll": "0aff76a9a8c4618c1f467bf08334ec3a93e92ada04b62f31864c8f052bea9745",
    "bin/mkl_avx2.2.dll": "cc85f0c3b1f0f02998a14923037873530645a77039e95a6a3fb90a7d01468d41",
}
NATIVE_COORDINATE = "intel-mkl 2023.0.0#2; Windows x86_64; LP64; sequential"

ITEM_BYTES = {"f64": 8, "i64": 8, "u8": 1}
ENCODINGS = {
    "f64": {"contiguous", "row-major", "lower-triangle-row-major-packed"},
    "i64": {"contiguous"},
    "u8": {"boolean-mask"},
}

REGISTERED_CASE_MULTIPLICITY = {
    "M1/EXP/1K-EXACT": 1,
    "M1/EXP/10K-ASSIGNED": 1,
    "M2/TH3/1K-EXACT": 1,
    "M2/TH3/10K-ASSIGNED": 1,
    "M3/HERMITE/1K-EXACT": 1,
    "M3/HERMITE/10K-ASSIGNED": 1,
    "M4/GEOMETRY/1K-TRUTH-TABLE": 3,
    "M4/GEOMETRY/10K-SELECTED-VALID": 3,
}

M4_POSITIVE_GEOMETRIES = {
    "clustered-near-boundary",
    "near-coincident-nextafter-pairs",
    "nonuniform-boundary",
}

COMMON_BLOCK_ARTIFACTS = {
    "domain_value_indices",
    "domain_gradient_indices",
    "inner_value_mask",
    "inner_gradient_mask",
    "canonical_lagrange_flat_indices",
    "a_lower",
    "p_row_major",
    "q_top_row_major",
    "qtaq_lower",
    "rhs_full",
    "rhs_reduced",
    "reference_gamma",
    "reference_lambda",
}
COARSE_ONLY_ARTIFACTS = {"p_top_row_major", "reference_c"}
WORKLOAD_ARTIFACTS = {
    "value_points",
    "gradient_points",
    "observations",
    "model_values",
    "selected_polynomial_indices",
}
CONTROL_ARTIFACTS = {
    "duplicate_coordinate_mutation",
    "mutated_value_points",
}
EXPECTED_ASSERTIONS = {
    "exact-workload-count": "workloads",
    "exact-block-count": "blocks",
    "exact-fine-block-count": "fine_blocks",
    "exact-coarse-block-count": "coarse_blocks",
    "exact-carried-factor-source-count": "factor_sources",
    "one-qtaq-factor-source-per-block": "qtaq_factor_sources",
    "coarse-only-p-top-factor-sources": "p_top_factor_sources",
    "one-workload-global-lagrange-auxiliary-source-per-workload": "auxiliary_decomposition_sources",
    "frozen-literal-factor-sources-excluded": None,
    "m3-blocks-all-canonical-global-row-map": None,
    "one-materialized-rank-invalid-control": "controls",
}


class LockError(RuntimeError):
    """A deterministic capture-integrity failure."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise LockError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LockError(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LockError(f"expected a JSON object at {path}")
    return value


def _safe_member(root: Path, relative: str) -> Path:
    member = PurePosixPath(relative)
    if (
        member.is_absolute()
        or not member.parts
        or any(part in {"", ".", ".."} for part in member.parts)
    ):
        raise LockError(f"unsafe artifact path: {relative!r}")
    target = root.joinpath(*member.parts)
    try:
        target.resolve().relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise LockError(f"artifact escapes corpus root: {relative!r}") from exc
    if target.is_symlink():
        raise LockError(f"artifact must not be a symlink: {relative!r}")
    return target


def _require_exact_counts(manifest: Mapping[str, Any]) -> None:
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise LockError("raw manifest has no counts object")
    for name, expected in EXPECTED_COUNTS.items():
        actual = counts.get(name)
        if actual != expected:
            raise LockError(
                f"raw manifest count {name!r}: expected {expected}, got {actual!r}"
            )
    assertions = manifest.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise LockError("raw manifest has no capture assertions")
    failed = [
        item.get("assertion_id", "<missing>")
        for item in assertions
        if not isinstance(item, dict) or item.get("passed") is not True
    ]
    if failed:
        raise LockError("raw capture assertions failed: " + ", ".join(failed))


def _shape_and_storage(
    artifact_id: str, value: Mapping[str, Any]
) -> tuple[str, str, list[int], int, int]:
    dtype = value.get("dtype")
    encoding = value.get("encoding")
    shape = value.get("shape")
    stored_elements = value.get("stored_elements")
    declared_bytes = value.get("bytes")
    if dtype not in ITEM_BYTES:
        raise LockError(f"artifact {artifact_id} has unsupported dtype {dtype!r}")
    if encoding not in ENCODINGS[dtype]:
        raise LockError(
            f"artifact {artifact_id} has invalid {dtype} encoding {encoding!r}"
        )
    if (
        not isinstance(shape, list)
        or not shape
        or any(
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 0
            for dimension in shape
        )
    ):
        raise LockError(f"artifact {artifact_id} has invalid shape {shape!r}")
    if encoding in {"row-major", "lower-triangle-row-major-packed"}:
        if len(shape) != 2:
            raise LockError(
                f"artifact {artifact_id} encoding {encoding} requires 2D shape"
            )
    elif len(shape) != 1:
        raise LockError(f"artifact {artifact_id} encoding {encoding} requires 1D shape")
    if encoding == "lower-triangle-row-major-packed":
        if shape[0] != shape[1]:
            raise LockError(
                f"artifact {artifact_id} packed lower triangle must be square"
            )
        expected_elements = shape[0] * (shape[0] + 1) // 2
    else:
        expected_elements = math.prod(shape)
    if (
        isinstance(stored_elements, bool)
        or not isinstance(stored_elements, int)
        or stored_elements != expected_elements
    ):
        raise LockError(
            f"artifact {artifact_id} stored_elements: expected "
            f"{expected_elements}, got {stored_elements!r}"
        )
    expected_bytes = expected_elements * ITEM_BYTES[dtype]
    if (
        isinstance(declared_bytes, bool)
        or not isinstance(declared_bytes, int)
        or declared_bytes != expected_bytes
    ):
        raise LockError(
            f"artifact {artifact_id} bytes: expected {expected_bytes}, "
            f"got {declared_bytes!r}"
        )
    expected_byte_order = "not-applicable" if dtype == "u8" else "little"
    if value.get("byte_order") != expected_byte_order:
        raise LockError(
            f"artifact {artifact_id} has invalid byte_order {value.get('byte_order')!r}"
        )
    return dtype, encoding, shape, expected_elements, expected_bytes


def _artifact_table(
    corpus_root: Path, manifest: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise LockError("raw manifest artifacts must be an array")
    expected_artifact_count = manifest["counts"].get("artifacts")
    if len(artifacts) != expected_artifact_count:
        raise LockError("raw manifest artifact count differs from its artifact array")

    by_id: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    for ordinal, value in enumerate(artifacts):
        if not isinstance(value, dict):
            raise LockError(f"artifact {ordinal} is not an object")
        artifact_id = value.get("artifact_id")
        relative = value.get("path")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise LockError(f"artifact {ordinal} has no stable artifact_id")
        if artifact_id in by_id:
            raise LockError(f"duplicate artifact_id: {artifact_id}")
        if not isinstance(relative, str) or not relative:
            raise LockError(f"artifact {artifact_id} has no path")
        if relative in paths:
            raise LockError(f"two artifact IDs share path {relative!r}")
        owner_kind = value.get("owner_kind")
        owner_id = value.get("owner_id")
        role = value.get("role")
        if owner_kind not in {"workload", "block", "control"}:
            raise LockError(
                f"artifact {artifact_id} has invalid owner_kind {owner_kind!r}"
            )
        if not isinstance(owner_id, str) or not owner_id:
            raise LockError(f"artifact {artifact_id} has no owner_id")
        if not isinstance(role, str) or not role:
            raise LockError(f"artifact {artifact_id} has no role")
        dtype, encoding, shape, stored_elements, declared_bytes = _shape_and_storage(
            artifact_id, value
        )

        path = _safe_member(corpus_root, relative)
        if not path.is_file():
            raise LockError(f"artifact payload is missing: {relative}")
        sha256, actual_bytes = _sha256_file(path)
        if actual_bytes != declared_bytes:
            raise LockError(
                f"artifact {artifact_id} declares {declared_bytes} bytes, "
                f"found {actual_bytes}"
            )
        by_id[artifact_id] = {
            "path": relative,
            "sha256": sha256,
            "bytes": actual_bytes,
            "dtype": dtype,
            "byte_order": value.get("byte_order"),
            "encoding": encoding,
            "shape": shape,
            "stored_elements": stored_elements,
            "role": role,
            "owner_kind": owner_kind,
            "owner_id": owner_id,
        }
        paths.add(relative)
    return by_id, paths


def _array(value: Any, *, context: str, length: int | None = None) -> list[Any]:
    if not isinstance(value, list):
        raise LockError(f"{context} must be an array")
    if length is not None and len(value) != length:
        raise LockError(f"{context}: expected {length} entries, got {len(value)}")
    return value


def _object(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise LockError(f"{context} must be an object")
    return value


def _identifier(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise LockError(f"{context} must be a non-empty string")
    return value


def _integer(value: Any, *, context: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LockError(
            f"{context} must be an integer greater than or equal to {minimum}"
        )
    return value


def _unique_objects(
    values: Any,
    *,
    context: str,
    id_field: str,
    expected_length: int,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for ordinal, raw in enumerate(
        _array(values, context=context, length=expected_length)
    ):
        item = _object(raw, context=f"{context}[{ordinal}]")
        identifier = _identifier(
            item.get(id_field), context=f"{context}[{ordinal}].{id_field}"
        )
        if identifier in result:
            raise LockError(f"duplicate {context} identifier: {identifier}")
        result[identifier] = item
    return result


def _require_artifact(
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_id: Any,
    *,
    owner_kind: str,
    owner_id: str,
    role: str,
    dtype: str,
    encoding: str,
    shape: Sequence[int],
    referenced: set[str],
) -> Mapping[str, Any]:
    identifier = _identifier(
        artifact_id, context=f"{owner_kind} {owner_id} artifact {role}"
    )
    artifact = artifacts.get(identifier)
    if artifact is None:
        raise LockError(
            f"{owner_kind} {owner_id} references missing artifact {identifier}"
        )
    expected = {
        "owner_kind": owner_kind,
        "owner_id": owner_id,
        "role": role,
        "dtype": dtype,
        "encoding": encoding,
        "shape": list(shape),
    }
    actual = {name: artifact.get(name) for name in expected}
    if actual != expected:
        raise LockError(
            f"artifact {identifier} topology differs: expected "
            f"{expected!r}, got {actual!r}"
        )
    if identifier in referenced:
        raise LockError(
            f"artifact {identifier} is owned by more than one manifest role"
        )
    referenced.add(identifier)
    return artifact


def _payload_bytes(corpus_root: Path, artifact: Mapping[str, Any]) -> bytes:
    path = _safe_member(
        corpus_root,
        _identifier(artifact.get("path"), context="artifact payload path"),
    )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise LockError(f"cannot read artifact payload {path}: {exc}") from exc


def _read_i64(corpus_root: Path, artifact: Mapping[str, Any]) -> list[int]:
    payload = _payload_bytes(corpus_root, artifact)
    if len(payload) % 8:
        raise LockError(f"i64 artifact {artifact.get('path')} is truncated")
    return [value[0] for value in struct.iter_unpack("<q", payload)]


def _read_u8(corpus_root: Path, artifact: Mapping[str, Any]) -> list[int]:
    payload = _payload_bytes(corpus_root, artifact)
    values = list(payload)
    if any(value not in {0, 1} for value in values):
        raise LockError(
            f"boolean mask {artifact.get('path')} contains values other than 0/1"
        )
    return values


def _read_f64_bits(
    corpus_root: Path,
    artifact: Mapping[str, Any],
    *,
    require_finite: bool = True,
) -> list[int]:
    payload = _payload_bytes(corpus_root, artifact)
    if len(payload) % 8:
        raise LockError(f"f64 artifact {artifact.get('path')} is truncated")
    if require_finite:
        for (value,) in struct.iter_unpack("<d", payload):
            if not math.isfinite(value):
                raise LockError(
                    f"f64 artifact {artifact.get('path')} contains non-finite data"
                )
    return [value[0] for value in struct.iter_unpack("<Q", payload)]


def _check_top_level_contract(manifest: Mapping[str, Any]) -> None:
    expected_identity = {
        "generator": "m1-m4-1k-10k-complete-hierarchy-canonical-row-map-v3",
        "compiler": "clang-19.1.5",
        "build_mode": "Release",
        "floating_point_mode": "clang-cl-fp-precise-fast-math-disabled",
        "eigen_version": "3.5.0",
        "polatory_commit": POLATORY_COMMIT,
    }
    for name, expected in expected_identity.items():
        if manifest.get(name) != expected:
            raise LockError(
                f"capture {name}: expected {expected!r}, got {manifest.get(name)!r}"
            )
    if manifest.get("binary_contract") != {
        "double_bytes": 8,
        "iec559": True,
        "little_endian": True,
    }:
        raise LockError("capture binary contract is not little-endian binary64")
    policy = _object(manifest.get("hierarchy_policy"), context="hierarchy_policy")
    expected_policy = {
        "fine_to_coarse_ratio": 10,
        "requested_coarsest_points": 2048,
        "effective_10k_coarse_points": 2047,
        "domain_max_leaf_scalar_order": 1024,
        "registered_levels": [1, 2],
    }
    for name, expected in expected_policy.items():
        if policy.get(name) != expected:
            raise LockError(
                f"hierarchy_policy.{name}: expected {expected!r}, "
                f"got {policy.get(name)!r}"
            )
    bindings = _object(
        policy.get("expression_bindings"),
        context="hierarchy_policy.expression_bindings",
    )
    if bindings != {
        "level": 1,
        "n_levels": 2,
        "kFineToCoarseRatio": 10,
        "kNCoarsestPoints": 2048,
    }:
        raise LockError("frozen coarse expression bindings changed")
    expression = policy.get("effective_expression")
    if (
        not isinstance(expression, str)
        or "Index(pow(" not in expression
        or "(level - 1)" not in expression
    ):
        raise LockError("frozen effective coarse expression is not bound")
    overlap = _object(
        policy.get("domain_overlap_quota"),
        context="hierarchy_policy.domain_overlap_quota",
    )
    if overlap.get("hex") != "0x1p-1" or overlap.get("decimal") != 0.5:
        raise LockError("domain overlap quota is not exact binary64 0.5")
    assembly = _object(manifest.get("assembly"), context="assembly")
    row_map = assembly.get("row_channel_map")
    if (
        not isinstance(row_map, str)
        or "source_value_rows + 3*global_gradient_index + component" not in row_map
    ):
        raise LockError("capture does not bind the canonical global row map")
    profile = _object(manifest.get("inventory_profile"), context="inventory_profile")
    if profile.get("profile_id") != "canonical-m1-m4-1k-10k-v3":
        raise LockError("unexpected inventory profile identifier")
    if profile.get("expected") != EXPECTED_COUNTS:
        raise LockError("inventory profile does not match locked expectations")
    exclusions = _array(manifest.get("exclusions"), context="exclusions", length=3)
    exclusion_ids = {
        _identifier(
            _object(value, context=f"exclusions[{ordinal}]").get("record_id"),
            context=f"exclusions[{ordinal}].record_id",
        )
        for ordinal, value in enumerate(exclusions)
    }
    if exclusion_ids != {
        "M3-HERMITE-COMPOSITE-max-order-fine-frozen-literal",
        "M3-HERMITE-COMPOSITE-level0-coarse-frozen-literal",
        ("polatory::polynomial::UnisolventPointSet<3>::100-random-trial-full-pivot-lu"),
    }:
        raise LockError("required frozen-literal/generator exclusions changed")
    lineage = _object(manifest.get("lineage"), context="lineage")
    m4_selection = _object(
        lineage.get("m4_positive_selection"),
        context="lineage.m4_positive_selection",
    )
    if m4_selection.get("near_coincident_recipe") != {
        "row_pairs": [[4, 5], [6, 7], [8, 9]],
        "centers_hex": ["0x1p-2", "0x1p-1", "0x1.8p-1"],
        "separation_axes": ["x", "y", "z"],
        "half_separation_hex": "0x1p-13",
        "endpoint_expression": "outward nextafter(center +/- 2^-13)",
        "minimum_total_separation_hex": "0x1p-12",
    }:
        raise LockError("M4 near-coincident fixture recipe changed")


def _validate_workloads(
    corpus_root: Path,
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    referenced: set[str],
) -> tuple[
    dict[str, Mapping[str, Any]],
    dict[str, list[int]],
]:
    workloads = _unique_objects(
        manifest.get("workloads"),
        context="workloads",
        id_field="workload_id",
        expected_length=EXPECTED_COUNTS["workloads"],
    )
    cases: dict[str, int] = {}
    fixtures: set[str] = set()
    m4_by_case: dict[str, set[str]] = {}
    polynomial_indices: dict[str, list[int]] = {}
    for workload_id, workload in workloads.items():
        case_id = _identifier(workload.get("case_id"), context=f"{workload_id}.case_id")
        scale_id = workload.get("scale_id")
        if scale_id not in {"1k", "10k"}:
            raise LockError(f"{workload_id} has invalid scale_id {scale_id!r}")
        cases[case_id] = cases.get(case_id, 0) + 1
        fixture_id = _identifier(
            workload.get("fixture_id"), context=f"{workload_id}.fixture_id"
        )
        if fixture_id in fixtures:
            raise LockError(f"duplicate workload fixture_id: {fixture_id}")
        fixtures.add(fixture_id)
        if case_id.startswith("M4/"):
            geometry_id = _identifier(
                workload.get("geometry_id"),
                context=f"{workload_id}.geometry_id",
            )
            m4_by_case.setdefault(case_id, set()).add(geometry_id)

        value_rows = _integer(
            workload.get("value_rows"), context=f"{workload_id}.value_rows"
        )
        gradient_points = _integer(
            workload.get("gradient_points"),
            context=f"{workload_id}.gradient_points",
        )
        scalar_order = _integer(
            workload.get("scalar_order"),
            context=f"{workload_id}.scalar_order",
            minimum=1,
        )
        if scalar_order != value_rows + 3 * gradient_points:
            raise LockError(f"{workload_id} scalar row count is inconsistent")
        degree = _integer(
            workload.get("resolved_polynomial_degree"),
            context=f"{workload_id}.resolved_polynomial_degree",
        )
        if degree not in {0, 1}:
            raise LockError(f"{workload_id} has unsupported polynomial degree")
        polynomial_order = _integer(
            workload.get("polynomial_order"),
            context=f"{workload_id}.polynomial_order",
            minimum=1,
        )
        if polynomial_order != (1 if degree == 0 else 4):
            raise LockError(f"{workload_id} polynomial order is inconsistent")
        requested = _object(
            workload.get("requested_polynomial_degree"),
            context=f"{workload_id}.requested_polynomial_degree",
        )
        if workload_id.startswith("M1-"):
            if requested != {"mode": "explicit", "value": 0}:
                raise LockError(f"{workload_id} must request explicit degree 0")
        elif requested.get("mode") != "minimum-required":
            raise LockError(f"{workload_id} must request the minimum-required degree")

        hierarchy = _object(
            workload.get("hierarchy"), context=f"{workload_id}.hierarchy"
        )
        expected_hierarchy = (
            {"levels": 1, "blocks": 1, "fine_blocks": 0, "coarse_blocks": 1}
            if scale_id == "1k"
            else {
                "levels": 2,
                "blocks": 33,
                "fine_blocks": 32,
                "coarse_blocks": 1,
            }
        )
        if hierarchy != expected_hierarchy:
            raise LockError(f"{workload_id} hierarchy differs from the frozen topology")

        refs = _object(workload.get("artifacts"), context=f"{workload_id}.artifacts")
        if set(refs) != WORKLOAD_ARTIFACTS - {"model_values"}:
            raise LockError(f"{workload_id} workload artifact roles changed")
        value_artifact = _require_artifact(
            artifacts,
            refs.get("value_points"),
            owner_kind="workload",
            owner_id=workload_id,
            role="value_points",
            dtype="f64",
            encoding="row-major",
            shape=[value_rows, 3],
            referenced=referenced,
        )
        gradient_artifact = _require_artifact(
            artifacts,
            refs.get("gradient_points"),
            owner_kind="workload",
            owner_id=workload_id,
            role="gradient_points",
            dtype="f64",
            encoding="row-major",
            shape=[gradient_points, 3],
            referenced=referenced,
        )
        observations_artifact = _require_artifact(
            artifacts,
            refs.get("observations"),
            owner_kind="workload",
            owner_id=workload_id,
            role="observations",
            dtype="f64",
            encoding="contiguous",
            shape=[scalar_order],
            referenced=referenced,
        )
        selected_artifact = _require_artifact(
            artifacts,
            refs.get("selected_polynomial_indices"),
            owner_kind="workload",
            owner_id=workload_id,
            role="selected_polynomial_indices",
            dtype="i64",
            encoding="contiguous",
            shape=[polynomial_order],
            referenced=referenced,
        )
        model = _object(workload.get("model"), context=f"{workload_id}.model")
        model_artifact_id = _identifier(
            model.get("exact_values_artifact"),
            context=f"{workload_id}.model artifact",
        )
        model_descriptor = artifacts.get(model_artifact_id)
        if model_descriptor is None:
            raise LockError(
                f"{workload_id} references missing model artifact {model_artifact_id}"
            )
        model_shape = model_descriptor.get("shape")
        if (
            not isinstance(model_shape, list)
            or len(model_shape) != 1
            or not isinstance(model_shape[0], int)
        ):
            raise LockError(f"{workload_id} model artifact shape is invalid")
        model_artifact = _require_artifact(
            artifacts,
            model_artifact_id,
            owner_kind="workload",
            owner_id=workload_id,
            role="model_values",
            dtype="f64",
            encoding="contiguous",
            shape=[model_shape[0]],
            referenced=referenced,
        )
        for artifact in (
            value_artifact,
            gradient_artifact,
            observations_artifact,
            model_artifact,
        ):
            _read_f64_bits(corpus_root, artifact)
        indices = _read_i64(corpus_root, selected_artifact)
        if (
            len(indices) != polynomial_order
            or len(set(indices)) != len(indices)
            or any(index < 0 or index >= value_rows for index in indices)
        ):
            raise LockError(f"{workload_id} selected polynomial indices are malformed")
        polynomial_indices[workload_id] = indices

    if cases != REGISTERED_CASE_MULTIPLICITY:
        raise LockError(f"registered case multiplicity differs: {cases!r}")
    expected_m4_cases = {
        case_id for case_id in REGISTERED_CASE_MULTIPLICITY if case_id.startswith("M4/")
    }
    if set(m4_by_case) != expected_m4_cases or any(
        geometries != M4_POSITIVE_GEOMETRIES for geometries in m4_by_case.values()
    ):
        raise LockError("M4 positive geometry triplets are incomplete")
    return workloads, polynomial_indices


def _validate_blocks(
    corpus_root: Path,
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    workloads: Mapping[str, Mapping[str, Any]],
    polynomial_indices: Mapping[str, list[int]],
    referenced: set[str],
) -> dict[str, Mapping[str, Any]]:
    blocks = _unique_objects(
        manifest.get("blocks"),
        context="blocks",
        id_field="block_id",
        expected_length=EXPECTED_COUNTS["blocks"],
    )
    by_workload: dict[str, list[Mapping[str, Any]]] = {
        workload_id: [] for workload_id in workloads
    }
    fine_inner_values: dict[str, list[int]] = {}
    fine_inner_gradients: dict[str, list[int]] = {}
    for workload_id, workload in workloads.items():
        if workload.get("scale_id") == "10k":
            fine_inner_values[workload_id] = [
                0
                for _ in range(
                    _integer(
                        workload.get("value_rows"),
                        context=f"{workload_id}.value_rows",
                    )
                )
            ]
            fine_inner_gradients[workload_id] = [
                0
                for _ in range(
                    _integer(
                        workload.get("gradient_points"),
                        context=f"{workload_id}.gradient_points",
                    )
                )
            ]

    for block_id, block in blocks.items():
        workload_id = _identifier(
            block.get("workload_id"), context=f"{block_id}.workload_id"
        )
        workload = workloads.get(workload_id)
        if workload is None:
            raise LockError(f"{block_id} names unknown workload {workload_id}")
        by_workload[workload_id].append(block)
        role = block.get("role")
        if role not in {"fine", "coarse"}:
            raise LockError(f"{block_id} has invalid role {role!r}")
        level = _integer(block.get("level"), context=f"{block_id}.level")
        ordinal = _integer(block.get("ordinal"), context=f"{block_id}.ordinal")
        if role == "fine" and (level != 1 or ordinal >= 32):
            raise LockError(f"{block_id} has invalid fine level/ordinal")
        if role == "coarse" and (level != 0 or ordinal != 0):
            raise LockError(f"{block_id} has invalid coarse level/ordinal")
        source_value_rows = _integer(
            block.get("source_value_rows"),
            context=f"{block_id}.source_value_rows",
        )
        source_gradient_points = _integer(
            block.get("source_gradient_points"),
            context=f"{block_id}.source_gradient_points",
        )
        if source_value_rows != workload.get(
            "value_rows"
        ) or source_gradient_points != workload.get("gradient_points"):
            raise LockError(f"{block_id} source dimensions changed")
        value_rows = _integer(block.get("value_rows"), context=f"{block_id}.value_rows")
        gradient_points = _integer(
            block.get("gradient_points"),
            context=f"{block_id}.gradient_points",
        )
        inner_value_rows = _integer(
            block.get("inner_value_rows"),
            context=f"{block_id}.inner_value_rows",
        )
        inner_gradient_points = _integer(
            block.get("inner_gradient_points"),
            context=f"{block_id}.inner_gradient_points",
        )
        if inner_value_rows > value_rows or inner_gradient_points > gradient_points:
            raise LockError(f"{block_id} inner rows exceed domain rows")
        scalar_order = _integer(
            block.get("scalar_order"),
            context=f"{block_id}.scalar_order",
            minimum=1,
        )
        polynomial_order = _integer(
            block.get("polynomial_order"),
            context=f"{block_id}.polynomial_order",
            minimum=1,
        )
        reduced_order = _integer(
            block.get("reduced_order"),
            context=f"{block_id}.reduced_order",
            minimum=1,
        )
        if scalar_order != value_rows + 3 * gradient_points:
            raise LockError(f"{block_id} scalar order is inconsistent")
        if polynomial_order != workload.get("polynomial_order"):
            raise LockError(f"{block_id} polynomial order drifted")
        if reduced_order != scalar_order - polynomial_order:
            raise LockError(f"{block_id} reduced order is inconsistent")
        if block.get("row_channel_map") != "canonical-global-value-offset-v1":
            raise LockError(f"{block_id} does not claim the canonical row map")

        refs = _object(block.get("artifacts"), context=f"{block_id}.artifacts")
        expected_roles = (
            COMMON_BLOCK_ARTIFACTS | COARSE_ONLY_ARTIFACTS
            if role == "coarse"
            else COMMON_BLOCK_ARTIFACTS
        )
        if set(refs) != expected_roles:
            raise LockError(
                f"{block_id} artifact roles differ: "
                f"expected {sorted(expected_roles)!r}, got {sorted(refs)!r}"
            )
        specifications = {
            "domain_value_indices": ("i64", "contiguous", [value_rows]),
            "domain_gradient_indices": ("i64", "contiguous", [gradient_points]),
            "inner_value_mask": ("u8", "boolean-mask", [value_rows]),
            "inner_gradient_mask": ("u8", "boolean-mask", [gradient_points]),
            "canonical_lagrange_flat_indices": ("i64", "contiguous", [scalar_order]),
            "a_lower": (
                "f64",
                "lower-triangle-row-major-packed",
                [scalar_order, scalar_order],
            ),
            "p_row_major": ("f64", "row-major", [scalar_order, polynomial_order]),
            "q_top_row_major": ("f64", "row-major", [polynomial_order, reduced_order]),
            "qtaq_lower": (
                "f64",
                "lower-triangle-row-major-packed",
                [reduced_order, reduced_order],
            ),
            "rhs_full": ("f64", "contiguous", [scalar_order]),
            "rhs_reduced": ("f64", "contiguous", [reduced_order]),
            "reference_gamma": ("f64", "contiguous", [reduced_order]),
            "reference_lambda": ("f64", "contiguous", [scalar_order]),
            "p_top_row_major": (
                "f64",
                "row-major",
                [polynomial_order, polynomial_order],
            ),
            "reference_c": ("f64", "contiguous", [polynomial_order]),
        }
        block_artifacts: dict[str, Mapping[str, Any]] = {}
        for artifact_role in expected_roles:
            dtype, encoding, shape = specifications[artifact_role]
            block_artifacts[artifact_role] = _require_artifact(
                artifacts,
                refs.get(artifact_role),
                owner_kind="block",
                owner_id=block_id,
                role=artifact_role,
                dtype=dtype,
                encoding=encoding,
                shape=shape,
                referenced=referenced,
            )
        domain_values = _read_i64(corpus_root, block_artifacts["domain_value_indices"])
        domain_gradients = _read_i64(
            corpus_root, block_artifacts["domain_gradient_indices"]
        )
        value_mask = _read_u8(corpus_root, block_artifacts["inner_value_mask"])
        gradient_mask = _read_u8(corpus_root, block_artifacts["inner_gradient_mask"])
        flat = _read_i64(
            corpus_root,
            block_artifacts["canonical_lagrange_flat_indices"],
        )
        if len(set(domain_values)) != len(domain_values) or any(
            index < 0 or index >= source_value_rows for index in domain_values
        ):
            raise LockError(f"{block_id} domain value indices are malformed")
        if len(set(domain_gradients)) != len(domain_gradients) or any(
            index < 0 or index >= source_gradient_points for index in domain_gradients
        ):
            raise LockError(f"{block_id} domain gradient indices are malformed")
        if domain_values[:polynomial_order] != polynomial_indices[workload_id]:
            raise LockError(f"{block_id} does not place polynomial anchors first")
        expected_flat = domain_values + [
            source_value_rows + 3 * gradient_index + component
            for gradient_index in domain_gradients
            for component in range(3)
        ]
        if flat != expected_flat:
            raise LockError(
                f"{block_id} canonical global Lagrange row map is malformed"
            )
        if sum(value_mask) != inner_value_rows:
            raise LockError(f"{block_id} inner value count differs from mask")
        if sum(gradient_mask) != inner_gradient_points:
            raise LockError(f"{block_id} inner gradient count differs from mask")
        if role == "coarse":
            if (
                inner_value_rows != value_rows
                or inner_gradient_points != gradient_points
                or any(value != 1 for value in value_mask)
                or any(value != 1 for value in gradient_mask)
            ):
                raise LockError(f"{block_id} coarse domain is not wholly inner")
        else:
            for local_index, is_inner in enumerate(value_mask):
                if is_inner:
                    fine_inner_values[workload_id][domain_values[local_index]] += 1
            for local_index, is_inner in enumerate(gradient_mask):
                if is_inner:
                    fine_inner_gradients[workload_id][
                        domain_gradients[local_index]
                    ] += 1
        for artifact_role in (
            "rhs_full",
            "rhs_reduced",
            "reference_gamma",
            "reference_lambda",
            *(("reference_c",) if role == "coarse" else ()),
        ):
            _read_f64_bits(corpus_root, block_artifacts[artifact_role])

    fine_count = 0
    coarse_count = 0
    for workload_id, workload_blocks in by_workload.items():
        scale_id = workloads[workload_id].get("scale_id")
        fine = [block for block in workload_blocks if block.get("role") == "fine"]
        coarse = [block for block in workload_blocks if block.get("role") == "coarse"]
        expected_fine = 0 if scale_id == "1k" else 32
        if (
            len(fine) != expected_fine
            or len(coarse) != 1
            or {block.get("ordinal") for block in fine} != set(range(expected_fine))
        ):
            raise LockError(f"{workload_id} block topology is incomplete")
        if scale_id == "10k":
            if any(count != 1 for count in fine_inner_values[workload_id]):
                raise LockError(
                    f"{workload_id} fine inner value ownership is not a partition"
                )
            if any(count != 1 for count in fine_inner_gradients[workload_id]):
                raise LockError(
                    f"{workload_id} fine inner gradient ownership is not a partition"
                )
        fine_count += len(fine)
        coarse_count += len(coarse)
    if (
        fine_count != EXPECTED_COUNTS["fine_blocks"]
        or coarse_count != EXPECTED_COUNTS["coarse_blocks"]
    ):
        raise LockError("independently reconstructed block counts differ")
    return blocks


def _validate_factor_sources(
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    workloads: Mapping[str, Mapping[str, Any]],
    blocks: Mapping[str, Mapping[str, Any]],
) -> None:
    sources = _unique_objects(
        manifest.get("factor_sources"),
        context="factor_sources",
        id_field="factor_source_id",
        expected_length=EXPECTED_COUNTS["factor_sources"],
    )
    by_block: dict[str, dict[str, Mapping[str, Any]]] = {
        block_id: {} for block_id in blocks
    }
    for source_id, source in sources.items():
        if "frozen-literal" in source_id:
            raise LockError("frozen-literal M3 source entered carried factors")
        block_id = _identifier(source.get("block_id"), context=f"{source_id}.block_id")
        block = blocks.get(block_id)
        if block is None:
            raise LockError(f"{source_id} names unknown block {block_id}")
        workload_id = source.get("workload_id")
        if workload_id != block.get("workload_id"):
            raise LockError(f"{source_id} workload/block lineage differs")
        matrix_role = source.get("matrix_role")
        if matrix_role not in {"qtaq", "p_top"}:
            raise LockError(f"{source_id} has invalid matrix role")
        if matrix_role in by_block[block_id]:
            raise LockError(f"{block_id} has duplicate {matrix_role} source")
        by_block[block_id][matrix_role] = source
        block_refs = _object(block.get("artifacts"), context=f"{block_id}.artifacts")
        expected_artifact = block_refs.get(
            "qtaq_lower" if matrix_role == "qtaq" else "p_top_row_major"
        )
        if source.get("matrix_artifact") != expected_artifact:
            raise LockError(f"{source_id} matrix artifact is not block-owned")
        if expected_artifact not in artifacts:
            raise LockError(f"{source_id} matrix artifact is missing")
        expected_rank = (
            block.get("reduced_order")
            if matrix_role == "qtaq"
            else block.get("polynomial_order")
        )
        if source.get("expected_rank") != expected_rank:
            raise LockError(f"{source_id} expected rank is inconsistent")
        if matrix_role == "p_top" and block.get("role") != "coarse":
            raise LockError(f"fine block {block_id} carries P_top")
        if (
            source.get("semantic_admission")
            != "certificate-required-before-backend-selection"
        ):
            raise LockError(f"{source_id} bypasses semantic admission")

    qtaq = 0
    p_top = 0
    for block_id, block_sources in by_block.items():
        expected_roles = (
            {"qtaq", "p_top"} if blocks[block_id].get("role") == "coarse" else {"qtaq"}
        )
        if set(block_sources) != expected_roles:
            raise LockError(f"{block_id} carried factor inventory is incomplete")
        qtaq += 1
        p_top += int("p_top" in block_sources)
    if (
        qtaq != EXPECTED_COUNTS["qtaq_factor_sources"]
        or p_top != EXPECTED_COUNTS["p_top_factor_sources"]
    ):
        raise LockError("independently reconstructed factor counts differ")

    auxiliary = _unique_objects(
        manifest.get("auxiliary_decomposition_sources"),
        context="auxiliary_decomposition_sources",
        id_field="source_id",
        expected_length=EXPECTED_COUNTS["auxiliary_decomposition_sources"],
    )
    auxiliary_by_workload: dict[str, Mapping[str, Any]] = {}
    for source_id, source in auxiliary.items():
        workload_id = _identifier(
            source.get("workload_id"), context=f"{source_id}.workload_id"
        )
        workload = workloads.get(workload_id)
        if workload is None or workload_id in auxiliary_by_workload:
            raise LockError(f"{source_id} auxiliary workload lineage differs")
        auxiliary_by_workload[workload_id] = source
        coarse = next(
            (
                block
                for block in blocks.values()
                if block.get("workload_id") == workload_id
                and block.get("role") == "coarse"
            ),
            None,
        )
        if coarse is None:
            raise LockError(f"{source_id} has no workload coarse block")
        coarse_refs = _object(
            coarse.get("artifacts"),
            context=f"{coarse.get('block_id')}.artifacts",
        )
        if source.get("matrix_artifact") != coarse_refs.get("p_top_row_major"):
            raise LockError(f"{source_id} does not alias coarse P_top")
        if source.get("expected_rank") != workload.get("polynomial_order"):
            raise LockError(f"{source_id} auxiliary rank differs")
        if (
            source.get("classification") != "non-carried-generator-auxiliary"
            or source.get("issue_38_handoff") is not False
        ):
            raise LockError(f"{source_id} auxiliary classification changed")
    if set(auxiliary_by_workload) != set(workloads):
        raise LockError("one auxiliary source per workload was not materialized")


def _validate_negative_control(
    corpus_root: Path,
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    workloads: Mapping[str, Mapping[str, Any]],
    referenced: set[str],
) -> None:
    controls = _array(
        manifest.get("controls"),
        context="controls",
        length=EXPECTED_COUNTS["controls"],
    )
    control = _object(controls[0], context="controls[0]")
    control_id = _identifier(
        control.get("control_id"), context="controls[0].control_id"
    )
    if control_id != "M4-GEOMETRY-1K-RANK-INVALID-DUPLICATE":
        raise LockError("unexpected materialized rank-invalid control ID")
    if control.get("control_kind") != "rank-invalid-negative":
        raise LockError("materialized control is not rank-invalid")
    if (
        control.get("expected_disposition") != "RankDeficient"
        or control.get("admission_phase") != "pre-backend"
        or control.get("backend_calls") != 0
        or any(
            control.get(name) != 0
            for name in (
                "workload_count_contribution",
                "block_count_contribution",
                "factor_source_count_contribution",
            )
        )
    ):
        raise LockError("rank-invalid control disposition/count boundary changed")
    base = _object(control.get("base_fixture"), context=f"{control_id}.base")
    workload_id = _identifier(
        base.get("workload_id"), context=f"{control_id}.base.workload_id"
    )
    workload = workloads.get(workload_id)
    if (
        workload is None
        or workload_id != "M4-GEOMETRY-NONUNIFORM-1K"
        or base.get("fixture_id") != workload.get("fixture_id")
    ):
        raise LockError("rank-invalid control base fixture is not M4 1k")
    workload_refs = _object(
        workload.get("artifacts"), context=f"{workload_id}.artifacts"
    )
    if base.get("coordinate_artifact") != workload_refs.get("value_points"):
        raise LockError("rank-invalid control base coordinate is not hash-bound")
    mutation = _object(control.get("mutation"), context=f"{control_id}.mutation")
    destination = _integer(
        mutation.get("destination_row"),
        context=f"{control_id}.destination_row",
    )
    source = _integer(mutation.get("source_row"), context=f"{control_id}.source_row")
    value_rows = _integer(
        workload.get("value_rows"), context=f"{workload_id}.value_rows"
    )
    if destination == source or destination >= value_rows or source >= value_rows:
        raise LockError("rank-invalid control duplicate rows are invalid")
    selected_artifact_id = _identifier(
        workload_refs.get("selected_polynomial_indices"),
        context=f"{workload_id}.selected_polynomial_indices",
    )
    selected_indices = _read_i64(corpus_root, artifacts[selected_artifact_id])
    if destination in selected_indices or source in selected_indices:
        raise LockError("rank-invalid duplicate rows must both be nullspace-tail rows")
    recipe_artifact = _require_artifact(
        artifacts,
        mutation.get("recipe_artifact"),
        owner_kind="control",
        owner_id=control_id,
        role="duplicate_coordinate_mutation",
        dtype="i64",
        encoding="contiguous",
        shape=[2],
        referenced=referenced,
    )
    mutated_artifact = _require_artifact(
        artifacts,
        mutation.get("mutated_coordinate_artifact"),
        owner_kind="control",
        owner_id=control_id,
        role="mutated_value_points",
        dtype="f64",
        encoding="row-major",
        shape=[value_rows, 3],
        referenced=referenced,
    )
    if _read_i64(corpus_root, recipe_artifact) != [destination, source]:
        raise LockError("rank-invalid mutation recipe payload differs")
    base_artifact_id = _identifier(
        base.get("coordinate_artifact"),
        context=f"{control_id}.base.coordinate_artifact",
    )
    base_bits = _read_f64_bits(corpus_root, artifacts[base_artifact_id])
    mutated_bits = _read_f64_bits(corpus_root, mutated_artifact)
    if len(base_bits) != len(mutated_bits):
        raise LockError("rank-invalid coordinate payload shape differs")
    expected_bits = list(base_bits)
    expected_bits[3 * destination : 3 * destination + 3] = base_bits[
        3 * source : 3 * source + 3
    ]
    if mutated_bits != expected_bits:
        raise LockError("rank-invalid payload is not the declared single-row duplicate")
    if (
        base_bits[3 * destination : 3 * destination + 3]
        == base_bits[3 * source : 3 * source + 3]
    ):
        raise LockError("rank-invalid base rows were already duplicates")


def _validate_assertions(manifest: Mapping[str, Any]) -> None:
    assertions = _unique_objects(
        manifest.get("assertions"),
        context="assertions",
        id_field="assertion_id",
        expected_length=len(EXPECTED_ASSERTIONS),
    )
    if set(assertions) != set(EXPECTED_ASSERTIONS):
        raise LockError("capture assertion vocabulary changed")
    for assertion_id, count_name in EXPECTED_ASSERTIONS.items():
        assertion = assertions[assertion_id]
        expected = 0 if count_name is None else EXPECTED_COUNTS[count_name]
        if assertion != {
            "assertion_id": assertion_id,
            "expected": expected,
            "actual": expected,
            "passed": True,
        }:
            raise LockError(
                f"capture assertion {assertion_id} is not independently true"
            )


def _validate_manifest_topology(
    corpus_root: Path,
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> None:
    _check_top_level_contract(manifest)
    referenced: set[str] = set()
    workloads, polynomial_indices = _validate_workloads(
        corpus_root, manifest, artifacts, referenced
    )
    blocks = _validate_blocks(
        corpus_root,
        manifest,
        artifacts,
        workloads,
        polynomial_indices,
        referenced,
    )
    _validate_factor_sources(manifest, artifacts, workloads, blocks)
    _validate_negative_control(corpus_root, manifest, artifacts, workloads, referenced)
    _validate_assertions(manifest)
    if referenced != set(artifacts):
        missing = sorted(set(artifacts) - referenced)
        extra = sorted(referenced - set(artifacts))
        raise LockError(
            "artifact ownership/reference closure differs: "
            f"unreferenced={missing!r}, unknown={extra!r}"
        )


def _actual_files(root: Path) -> set[str]:
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise LockError(f"capture contains a symlink: {path}")
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    return files


def _source_entry(path: Path) -> dict[str, Any]:
    sha256, size = _sha256_file(path)
    return {"sha256": sha256, "bytes": size}


def _verify_polatory(polatory_source: Path) -> None:
    try:
        head = subprocess.run(
            ["git", "-C", str(polatory_source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            [
                "git",
                "-C",
                str(polatory_source),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LockError(f"cannot verify frozen Polatory checkout: {exc}") from exc
    if head != POLATORY_COMMIT:
        raise LockError(
            f"Polatory must be {POLATORY_COMMIT}, found {head or '<empty>'}"
        )
    if status:
        raise LockError("Polatory checkout has tracked modifications")


def _native_closure(polatory_source: Path) -> dict[str, dict[str, Any]]:
    native_root = polatory_source / "build" / "vcpkg_installed" / "x64-windows"
    result: dict[str, dict[str, Any]] = {}
    for relative, expected_sha256 in NATIVE_CLOSURE.items():
        path = native_root.joinpath(*PurePosixPath(relative).parts)
        actual_sha256, size = _sha256_file(path)
        if actual_sha256 != expected_sha256:
            raise LockError(
                f"native closure hash mismatch for {relative}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        result[relative] = {"sha256": actual_sha256, "bytes": size}
    return result


def _expected_lock_body(
    corpus_root: Path,
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    capture_executable: Path,
    polatory_source: Path,
) -> dict[str, Any]:
    raw_path = corpus_root / RAW_MANIFEST_NAME
    _verify_polatory(polatory_source)
    if not capture_executable.is_file():
        raise LockError(f"capture executable is missing: {capture_executable}")
    raw_sha256, raw_bytes = _sha256_file(raw_path)
    return {
        "schema": LOCK_SCHEMA,
        "hash_algorithm": "sha256",
        "capture_schema": CAPTURE_SCHEMA,
        "raw_manifest": {
            "path": RAW_MANIFEST_NAME,
            "sha256": raw_sha256,
            "bytes": raw_bytes,
        },
        "counts": dict(manifest["counts"]),
        "artifacts": dict(artifacts),
        "source_closure": {
            "capture/hierarchy_capture.cpp": _source_entry(
                CAPTURE_DIR / "hierarchy_capture.cpp"
            ),
            "capture/hierarchy/CMakeLists.txt": _source_entry(HIERARCHY_CMAKE),
            "hierarchy_lock.py": _source_entry(PROTOTYPE_DIR / "hierarchy_lock.py"),
            "capture_executable": _source_entry(capture_executable),
        },
        "polatory": {
            "commit": POLATORY_COMMIT,
            "tracked_tree_clean": True,
        },
        "native_closure": {
            "coordinate": NATIVE_COORDINATE,
            "files": _native_closure(polatory_source),
        },
    }


def _require_expected_lock(
    lock: Mapping[str, Any], expected_body: Mapping[str, Any]
) -> None:
    digest = lock.get("corpus_sha256")
    if not isinstance(digest, str):
        raise LockError("lock has no corpus_sha256")
    body = {key: value for key, value in lock.items() if key != "corpus_sha256"}
    if _sha256_bytes(_canonical_bytes(body)) != digest:
        raise LockError("lock body does not reproduce corpus_sha256")
    if body != expected_body:
        keys = sorted(
            key
            for key in set(body) | set(expected_body)
            if body.get(key) != expected_body.get(key)
        )
        raise LockError(
            "lock body differs from independently reconstructed canonical body: "
            + ", ".join(keys)
        )


def lock_capture(
    corpus_root: Path,
    capture_executable: Path,
    polatory_source: Path,
) -> dict[str, Any]:
    corpus_root = corpus_root.resolve()
    raw_path = corpus_root / RAW_MANIFEST_NAME
    lock_path = corpus_root / "manifest.lock.json"
    if lock_path.exists():
        raise LockError(f"refusing to replace existing lock: {lock_path}")
    manifest = _load_object(raw_path)
    if manifest.get("schema") != CAPTURE_SCHEMA:
        raise LockError(
            f"expected capture schema {CAPTURE_SCHEMA!r}, "
            f"found {manifest.get('schema')!r}"
        )
    if manifest.get("polatory_commit") != POLATORY_COMMIT:
        raise LockError("raw manifest does not bind the frozen Polatory commit")
    _require_exact_counts(manifest)
    artifacts, payload_paths = _artifact_table(corpus_root, manifest)
    _validate_manifest_topology(corpus_root, manifest, artifacts)

    actual = _actual_files(corpus_root)
    expected = {RAW_MANIFEST_NAME, *payload_paths}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unreferenced " + ", ".join(extra))
        raise LockError("capture file-set mismatch: " + "; ".join(details))

    body = _expected_lock_body(
        corpus_root,
        manifest,
        artifacts,
        capture_executable,
        polatory_source,
    )
    lock = {**body, "corpus_sha256": _sha256_bytes(_canonical_bytes(body))}
    encoded = (
        json.dumps(
            lock,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    try:
        with lock_path.open("xb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise LockError(f"cannot publish {lock_path}: {exc}") from exc
    return lock


def verify_capture_lock(
    corpus_root: Path,
    capture_executable: Path,
    polatory_source: Path,
) -> dict[str, Any]:
    corpus_root = corpus_root.resolve()
    lock_path = corpus_root / "manifest.lock.json"
    lock = _load_object(lock_path)

    manifest = _load_object(corpus_root / RAW_MANIFEST_NAME)
    if manifest.get("schema") != CAPTURE_SCHEMA:
        raise LockError("locked raw manifest schema changed")
    _require_exact_counts(manifest)
    artifacts, payload_paths = _artifact_table(corpus_root, manifest)
    _validate_manifest_topology(corpus_root, manifest, artifacts)
    if artifacts != lock.get("artifacts"):
        raise LockError("locked artifact table differs from current payloads")

    expected_files = {RAW_MANIFEST_NAME, "manifest.lock.json", *payload_paths}
    actual_files = _actual_files(corpus_root)
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unreferenced " + ", ".join(extra))
        raise LockError("locked file-set mismatch: " + "; ".join(details))

    expected_body = _expected_lock_body(
        corpus_root,
        manifest,
        artifacts,
        capture_executable,
        polatory_source,
    )
    _require_expected_lock(lock, expected_body)
    return lock


def run_malformed_controls(
    corpus_root: Path,
    capture_executable: Path,
    polatory_source: Path,
) -> dict[str, Any]:
    """Prove that representative self-consistent lies cannot be locked."""
    corpus_root = corpus_root.resolve()
    manifest = _load_object(corpus_root / RAW_MANIFEST_NAME)
    _require_exact_counts(manifest)
    artifacts, _ = _artifact_table(corpus_root, manifest)
    _validate_manifest_topology(corpus_root, manifest, artifacts)

    controls: list[tuple[str, Any]] = []

    def topology_control(name: str, mutate: Any) -> None:
        candidate = copy.deepcopy(manifest)
        mutate(candidate)
        try:
            _require_exact_counts(candidate)
            _validate_manifest_topology(corpus_root, candidate, artifacts)
        except LockError:
            controls.append((name, "rejected"))
            return
        raise LockError(f"malformed lock control was accepted: {name}")

    def shape_control(candidate: dict[str, Any]) -> None:
        candidate["artifacts"][0]["stored_elements"] += 1
        _shape_and_storage(
            candidate["artifacts"][0]["artifact_id"],
            candidate["artifacts"][0],
        )

    candidate = copy.deepcopy(manifest)
    try:
        shape_control(candidate)
    except LockError:
        controls.append(("artifact-storage-mismatch", "rejected"))
    else:
        raise LockError(
            "malformed lock control was accepted: artifact-storage-mismatch"
        )

    topology_control(
        "self-declared-count-lie",
        lambda value: value["counts"].__setitem__("blocks", 203),
    )
    topology_control(
        "inventory-profile-lie",
        lambda value: value["inventory_profile"]["expected"].__setitem__(
            "workloads", 11
        ),
    )
    topology_control(
        "workload-artifact-roles-missing",
        lambda value: value["workloads"][0].__setitem__("artifacts", {}),
    )
    topology_control(
        "block-artifact-owner-alias",
        lambda value: value["blocks"][0]["artifacts"].__setitem__(
            "domain_value_indices",
            value["blocks"][0]["artifacts"]["domain_gradient_indices"],
        ),
    )
    fine_ordinal = next(
        index
        for index, block in enumerate(manifest["blocks"])
        if block["role"] == "fine"
    )
    coarse_ordinal = next(
        index
        for index, block in enumerate(manifest["blocks"])
        if block["role"] == "coarse"
    )
    topology_control(
        "fine-block-smuggled-p-top",
        lambda value: value["blocks"][fine_ordinal]["artifacts"].__setitem__(
            "p_top_row_major",
            value["blocks"][coarse_ordinal]["artifacts"]["p_top_row_major"],
        ),
    )
    m3_ordinal = next(
        index
        for index, block in enumerate(manifest["blocks"])
        if block["workload_id"].startswith("M3-")
    )
    topology_control(
        "m3-local-row-map-claim",
        lambda value: value["blocks"][m3_ordinal].__setitem__(
            "row_channel_map", "local-mu-gradient-offset"
        ),
    )
    topology_control(
        "factor-matrix-reference-drift",
        lambda value: value["factor_sources"][0].__setitem__(
            "matrix_artifact",
            value["workloads"][0]["artifacts"]["observations"],
        ),
    )
    topology_control(
        "auxiliary-promoted-to-handoff",
        lambda value: value["auxiliary_decomposition_sources"][0].__setitem__(
            "issue_38_handoff", True
        ),
    )
    topology_control(
        "negative-control-backend-call",
        lambda value: value["controls"][0].__setitem__("backend_calls", 1),
    )
    topology_control(
        "capture-assertion-lie",
        lambda value: value["assertions"][0].__setitem__("passed", False),
    )

    expected_body = _expected_lock_body(
        corpus_root,
        manifest,
        artifacts,
        capture_executable,
        polatory_source,
    )

    def lock_body_control(name: str, mutate: Any) -> None:
        body = copy.deepcopy(expected_body)
        mutate(body)
        candidate = {
            **body,
            "corpus_sha256": _sha256_bytes(_canonical_bytes(body)),
        }
        try:
            _require_expected_lock(candidate, expected_body)
        except LockError:
            controls.append((name, "rejected"))
            return
        raise LockError(f"self-consistent lock-body control was accepted: {name}")

    lock_body_control(
        "lock-count-self-hash-lie",
        lambda value: value["counts"].__setitem__("blocks", 203),
    )
    lock_body_control(
        "lock-polatory-self-hash-lie",
        lambda value: value["polatory"].__setitem__("commit", "0" * 40),
    )
    lock_body_control(
        "lock-native-coordinate-self-hash-lie",
        lambda value: value["native_closure"].__setitem__("coordinate", "drifted"),
    )
    lock_body_control(
        "lock-hash-algorithm-self-hash-lie",
        lambda value: value.__setitem__("hash_algorithm", "sha512"),
    )
    return {
        "schema": "rapidrbf-hierarchy-lock-malformed-controls-v1",
        "status": "PASS",
        "canonical_corpus_sha256": _sha256_bytes(_canonical_bytes(expected_body)),
        "raw_manifest": expected_body["raw_manifest"],
        "source_closure": expected_body["source_closure"],
        "controls": [
            {"control_id": name, "disposition": disposition}
            for name, disposition in controls
        ],
        "backend_calls": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument("--capture-exe", type=Path, required=True)
    parser.add_argument(
        "--polatory-source",
        type=Path,
        default=Path(os.environ.get("RAPIDRBF_POLATORY_SOURCE", "D:/CODE/polatory")),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify an existing lock instead of creating one",
    )
    parser.add_argument(
        "--self-test-controls",
        action="store_true",
        help="run malformed-manifest rejection controls without locking",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the self-test control report to this path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.verify and args.self_test_controls:
            raise LockError("--verify and --self-test-controls are exclusive")
        if args.output is not None and not args.self_test_controls:
            raise LockError("--output is valid only with --self-test-controls")
        if args.self_test_controls:
            report = run_malformed_controls(
                args.corpus_root,
                args.capture_exe.resolve(),
                args.polatory_source.resolve(),
            )
            encoded = (
                json.dumps(
                    report,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            )
            if args.output is None:
                print(encoded, end="")
            else:
                try:
                    args.output.write_text(encoded, encoding="utf-8")
                except OSError as exc:
                    raise LockError(
                        f"cannot write control report {args.output}: {exc}"
                    ) from exc
            return 0
        action = verify_capture_lock if args.verify else lock_capture
        lock = action(
            args.corpus_root,
            args.capture_exe.resolve(),
            args.polatory_source.resolve(),
        )
    except LockError as exc:
        print(f"hierarchy lock failed: {exc}", file=sys.stderr)
        return 1
    print(lock["corpus_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
