#!/usr/bin/env python3
"""Write or verify the exact issue-42 instrumented faer candidate binding."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "binding-manifest.v1.json"
PATCH_SET = ROOT / "patch-set.v1.json"

PROFILE_SHA256 = (
    "00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3"
)
PLAN_SHA256 = (
    "5b288e33d13464ae79948b1afcb2d76d0d08f9c81b27010ad51d4906cfc66892"
)
STOCK_SOURCE_SHA256 = (
    "530103a7c8f62e8cf225045d39410b9d36e67d11f5acf6793f403bb0fc1a9fb9"
)
GENERATED = {
    "vendor/private-gemm-x86-0.1.20/generated/x86_64/asm.rs": (
        97_960,
        "4842a0cb51436aa092317caff49f4663c9504a8cb4c8691b4dc580ad57edbd34",
    ),
    "vendor/private-gemm-x86-0.1.20/generated/x86_64/asm.s": (
        8_592_955,
        "eb7bad48175bf2a074cf9f2cc98e62e2cda27e08d0aba1266bf192ebd1141988",
    ),
}
CRATES = (
    "faer-0.24.4",
    "private-gemm-x86-0.1.20",
    "dyn-stack-0.13.2",
)
REQUIRED_PATCH_PATHS = {
    "dyn-stack-0.13.2/Cargo.toml",
    "dyn-stack-0.13.2/Cargo.toml.orig",
    "dyn-stack-0.13.2/src/lib.rs",
    "faer-0.24.4/Cargo.toml",
    "faer-0.24.4/Cargo.toml.orig",
    "faer-0.24.4/src/linalg/cholesky/bunch_kaufman/factor.rs",
    "faer-0.24.4/src/linalg/cholesky/bunch_kaufman/solve.rs",
    "faer-0.24.4/src/linalg/lu/full_pivoting/factor.rs",
    "faer-0.24.4/src/linalg/lu/full_pivoting/solve.rs",
    "faer-0.24.4/src/linalg/matmul/internal/mod.rs",
    "faer-0.24.4/src/linalg/matmul/mod.rs",
    "faer-0.24.4/src/linalg/matmul/triangular.rs",
    "faer-0.24.4/src/linalg/triangular_solve.rs",
    "private-gemm-x86-0.1.20/Cargo.toml",
    "private-gemm-x86-0.1.20/Cargo.toml.orig",
    "private-gemm-x86-0.1.20/build.rs",
    "private-gemm-x86-0.1.20/generated/x86_64/asm.rs",
    "private-gemm-x86-0.1.20/generated/x86_64/asm.s",
    "private-gemm-x86-0.1.20/src/lib.rs",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_record(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }


def closure(root: Path) -> dict[str, Any]:
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    total = 0
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        total += len(data)
        digest.update(len(relative).to_bytes(8, "little"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "little"))
        digest.update(hashlib.sha256(data).digest())
    return {"files": len(files), "bytes": total, "sha256": digest.hexdigest()}


def binding_files() -> list[Path]:
    return sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and path != MANIFEST
            and "target" not in path.relative_to(ROOT).parts
            and "evidence" not in path.relative_to(ROOT).parts
            and "__pycache__" not in path.relative_to(ROOT).parts
        ),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def write_patch_set(registry_root: Path) -> None:
    changes: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for crate in CRATES:
        stock = registry_root / crate
        bound = ROOT / "vendor" / crate
        require(stock.is_dir(), f"missing stock crate {stock}")
        stock_files = {
            path.relative_to(stock).as_posix(): path
            for path in stock.rglob("*")
            if path.is_file()
        }
        bound_files = {
            path.relative_to(bound).as_posix(): path
            for path in bound.rglob("*")
            if path.is_file()
        }
        for relative in sorted(set(stock_files) | set(bound_files)):
            stock_path = stock_files.get(relative)
            bound_path = bound_files.get(relative)
            stock_data = stock_path.read_bytes() if stock_path else None
            bound_data = bound_path.read_bytes() if bound_path else None
            if stock_data == bound_data:
                continue
            record = {"path": f"{crate}/{relative}"}
            if stock_data is None:
                record["change"] = "added"
                record["stock_sha256"] = None
                record["stock_bytes"] = 0
            elif bound_data is None:
                record["change"] = "removed"
                record["stock_sha256"] = sha256(stock_data)
                record["stock_bytes"] = len(stock_data)
                removed.append(record)
                continue
            else:
                record["change"] = "modified"
                record["stock_sha256"] = sha256(stock_data)
                record["stock_bytes"] = len(stock_data)
            record["bound_sha256"] = sha256(bound_data)
            record["bound_bytes"] = len(bound_data)
            changes.append(record)

    document = {
        "schema": "rapidrbf-instrumented-faer-patch-set-v1",
        "upstream_source_closure_sha256": STOCK_SOURCE_SHA256,
        "rule": (
            "Every changed or added byte is named by stock and bound SHA-256; "
            "all other vendored bytes are covered by the binding content closure."
        ),
        "changes": changes,
        "removed": removed,
    }
    require(not removed, "the narrow fork may not delete stock source files")
    found = {item["path"] for item in changes}
    require(
        REQUIRED_PATCH_PATHS <= found,
        f"required patch paths missing: {sorted(REQUIRED_PATCH_PATHS - found)}",
    )
    PATCH_SET.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_inputs() -> None:
    profile = read_json(ROOT / "inputs/factor-health-profile.projected.json")
    plan = read_json(ROOT / "inputs/two-factor-plan.v1.json")
    upstream = read_json(ROOT / "inputs/upstream-source-closure.v1.json")
    require(sha256(canonical_bytes(profile)) == PROFILE_SHA256, "profile changed")
    require(sha256(canonical_bytes(plan)) == PLAN_SHA256, "two-factor plan changed")
    require(
        upstream["combined_sha256"] == STOCK_SOURCE_SHA256,
        "stock source identity changed",
    )
    require(
        [target["target"] for target in plan["targets"]]
        == [
            "x86_64-pc-windows-msvc",
            "x86_64-unknown-linux-gnu",
            "aarch64-apple-darwin",
            "x86_64-apple-darwin",
        ],
        "tier-one target order changed",
    )


def verify_generated_sources() -> None:
    for relative, (expected_bytes, expected_sha) in GENERATED.items():
        data = (ROOT / relative).read_bytes()
        require(len(data) == expected_bytes, f"{relative} byte count changed")
        require(sha256(data) == expected_sha, f"{relative} hash changed")
    build = (
        ROOT / "vendor/private-gemm-x86-0.1.20/build.rs"
    ).read_text(encoding="utf-8")
    require(
        'env::var_os("RAPIDRBF_REGENERATE_PRIVATE_GEMM").is_none()' in build
        and 'join("generated/x86_64")' in build,
        "private-gemm build no longer defaults to the frozen generated bytes",
    )


def verify_patch_set() -> None:
    patch = read_json(PATCH_SET)
    require(
        patch["upstream_source_closure_sha256"] == STOCK_SOURCE_SHA256,
        "patch ancestry changed",
    )
    require(not patch["removed"], "patch set contains a removed stock file")
    found = {item["path"] for item in patch["changes"]}
    require(
        REQUIRED_PATCH_PATHS <= found,
        f"required patch paths missing: {sorted(REQUIRED_PATCH_PATHS - found)}",
    )
    for item in patch["changes"]:
        bound = ROOT / "vendor" / item["path"]
        data = bound.read_bytes()
        require(len(data) == item["bound_bytes"], f"{item['path']} bytes changed")
        require(
            sha256(data) == item["bound_sha256"],
            f"{item['path']} patch bytes changed",
        )


def require_fragments(path: str, fragments: Iterable[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [fragment for fragment in fragments if fragment not in text]
    require(not missing, f"{path} missing binding fragments: {missing}")


def verify_control_surfaces() -> None:
    gemm_path = "vendor/private-gemm-x86-0.1.20/src/lib.rs"
    gemm = (ROOT / gemm_path).read_text(encoding="utf-8")
    require("thread_local!" not in gemm, "private-gemm regained unowned TLS state")
    require_fragments(
        gemm_path,
        (
            "pub fn workspace_layout",
            "struct OwnedWorkspace",
            "rapidrbf_faer_control::reserve_transient",
            "rapidrbf_faer_control::backend_entry",
            "EventKind::Packing",
            "EventKind::MacroKernel",
            "workspace: *mut u8",
            "workspace_len: usize",
        ),
    )
    required = {
        "vendor/dyn-stack-0.13.2/src/lib.rs": ("stack_carve",),
        "vendor/faer-0.24.4/src/linalg/cholesky/bunch_kaufman/factor.rs": (
            "EventKind::Pivot",
            "EventKind::Panel",
        ),
        "vendor/faer-0.24.4/src/linalg/cholesky/bunch_kaufman/solve.rs": (
            "EventKind::Solve",
        ),
        "vendor/faer-0.24.4/src/linalg/lu/full_pivoting/factor.rs": (
            "EventKind::Pivot",
        ),
        "vendor/faer-0.24.4/src/linalg/lu/full_pivoting/solve.rs": (
            "EventKind::Solve",
        ),
        "vendor/faer-0.24.4/src/linalg/matmul/mod.rs": (
            "EventKind::MacroKernel",
        ),
        "vendor/faer-0.24.4/src/linalg/triangular_solve.rs": (
            "EventKind::Solve",
        ),
        "crates/rapidrbf-instrumented-factor/src/lib.rs": (
            "pub fn plan",
            "pub fn preflight",
            "pub fn checkpoint_bounds",
            "pub fn execute<T>",
            "pub struct ExecutionLease",
            "pub struct ExecutionMetrics",
            "pub struct CancellationToken",
            'parallelism: "Par::Seq"',
            'temporary_storage: "denied-for-two-factor-feasibility"',
        ),
    }
    for path, fragments in required.items():
        require_fragments(path, fragments)


def expected_manifest() -> dict[str, Any]:
    entries = [file_record(path, ROOT) for path in binding_files()]
    digest = sha256(canonical_bytes(entries))
    crate_closures = {
        crate: closure(ROOT / "vendor" / crate) for crate in CRATES
    }
    return {
        "schema": "rapidrbf-instrumented-faer-candidate-binding-v1",
        "binding_id": (
            "RapidRBF/InstrumentedFaerCandidateExecutionBinding/v1/" + digest
        ),
        "binding_sha256": digest,
        "state": "MATERIALIZED_NO_FACTOR_OBSERVATION",
        "content_algorithm": "sha256-of-canonical-file-record-array-v1",
        "manifest_is_part_of_content_hash": False,
        "content_files": len(entries),
        "content_bytes": sum(item["bytes"] for item in entries),
        "content": entries,
        "frozen_inputs": {
            "factor_health_profile_sha256": PROFILE_SHA256,
            "two_factor_plan_sha256": PLAN_SHA256,
            "stock_source_closure_sha256": STOCK_SOURCE_SHA256,
            "patch_set_sha256": sha256(PATCH_SET.read_bytes()),
            "cargo_lock_sha256": sha256((ROOT / "Cargo.lock").read_bytes()),
        },
        "source_closures": crate_closures,
        "upstream": {
            "faer": "0.24.4",
            "private-gemm-x86": "0.1.20",
            "dyn-stack": "0.13.2",
        },
        "features": {
            "faer": ["std", "linalg"],
            "dyn-stack": ["alloc", "core-error", "std"],
            "private-gemm-x86": ["std"],
            "default_features": False,
        },
        "execution_seam": {
            "public_type": "CandidateExecutionBinding",
            "faer_types_cross_public_seam": False,
            "parallelism": "Par::Seq",
            "outer_compute_permits": 1,
            "temporary_storage": "denied",
            "cancellation_transport": "typed unwind caught inside seam",
            "receipt_type": "ExecutionMetrics",
        },
        "generated_sources": {
            path: {"bytes": size, "sha256": digest}
            for path, (size, digest) in GENERATED.items()
        },
        "tier_one_targets": [
            "x86_64-pc-windows-msvc",
            "x86_64-unknown-linux-gnu",
            "aarch64-apple-darwin",
            "x86_64-apple-darwin",
        ],
        "reproducible_build": {
            "rust_toolchain": "1.85.0",
            "command": (
                "cargo +1.85.0 test --locked "
                "-p rapidrbf-faer-control "
                "-p rapidrbf-instrumented-factor"
            ),
            "private_gemm_generator_refresh_env": (
                "RAPIDRBF_REGENERATE_PRIVATE_GEMM"
            ),
        },
        "observation_boundary": {
            "backend_calls": 0,
            "two_factor_plan_executed": False,
            "factor_publications": 0,
            "solve_publications": 0,
            "qualification_disposition": None,
        },
    }


def verify_manifest(write: bool) -> dict[str, Any]:
    expected = expected_manifest()
    if write:
        MANIFEST.write_text(
            json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    observed = read_json(MANIFEST)
    require(observed == expected, "binding manifest does not match exact bytes")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument(
        "--write-patch-set",
        type=Path,
        metavar="CARGO_REGISTRY_SOURCE_ROOT",
        help="refresh patch ancestry from the exact unpacked stock crates",
    )
    args = parser.parse_args()
    if args.write_patch_set:
        write_patch_set(args.write_patch_set.resolve())
    require(PATCH_SET.is_file(), "patch-set.v1.json is missing")
    verify_inputs()
    verify_generated_sources()
    verify_patch_set()
    verify_control_surfaces()
    manifest = verify_manifest(args.write_manifest)
    print(
        json.dumps(
            {
                "binding_id": manifest["binding_id"],
                "binding_sha256": manifest["binding_sha256"],
                "content_files": manifest["content_files"],
                "content_bytes": manifest["content_bytes"],
                "backend_calls": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
