"""Prepare the immutable, deduplicated issue-41 qualification input.

The script derives every source entry mechanically from the admitted hierarchy
manifest. It never invents factor data and never gives the transport archive
authority beyond the source identities already frozen by issue 37.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
HIERARCHY_EVIDENCE = (
    REPOSITORY
    / "tools"
    / "prototypes"
    / "dense_factor_replay_throwaway"
    / "evidence"
)
RAW_MANIFEST = HIERARCHY_EVIDENCE / "canonical-hierarchy.manifest.raw.json"
LOCK = HIERARCHY_EVIDENCE / "canonical-hierarchy.manifest.lock.json"
CANDIDATE = ROOT.parent / "instrumented_faer_candidate_binding_throwaway"
LANES = ROOT.parent / "instrumented_faer_lane_provisioning_throwaway"

RAW_MANIFEST_SHA256 = (
    "cf5aaa1e3fe6bf51c3f24f13455ac1036e7ec591668c18ec4c86f3243aa07f54"
)
LOCK_SHA256 = "7abd17eabba0cd578fa8989075f9d09d5113a696df48c9643785822dadde5a75"
CORPUS_SHA256 = "38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79"
ADMISSION_REPORT_SHA256 = (
    "bc907929fdf82976f83212ec514a0ccf43c59499a5dda45f9c4d4ef34aa37e90"
)
PHYSICAL_REPORT_SHA256 = (
    "da75d43c66e7405676639c61e11c99686d291ea690b85ed0828233d957b6a769"
)
PROFILE_SHA256 = "00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3"
BINDING_SHA256 = "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
LANE_CONTRACT_SHA256 = (
    "d6edbf73cc9788dfb56eedc58010ce3b091d94014111a6a4b1f1171cc8f7c5a3"
)
PLAN_SCHEMA = "RapidRBF/FactorQualificationPlan/v1"
EXPECTED_COUNTS = {
    "workloads": 12,
    "blocks": 204,
    "factor_sources": 216,
    "qtaq_factor_sources": 204,
    "p_top_factor_sources": 12,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_authority(
    corpus_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha256_file(RAW_MANIFEST) == RAW_MANIFEST_SHA256, "raw manifest drifted")
    require(sha256_file(LOCK) == LOCK_SHA256, "manifest lock drifted")
    require(
        sha256_file(corpus_root / "hierarchy.manifest.raw.json")
        == RAW_MANIFEST_SHA256,
        "reproduced raw manifest differs",
    )
    require(
        sha256_file(corpus_root / "manifest.lock.json") == LOCK_SHA256,
        "reproduced lock differs",
    )
    raw = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    require(
        raw.get("schema") == "rapidrbf-canonical-hierarchy-admission-corpus-v3",
        "raw manifest schema differs",
    )
    require(
        lock.get("schema") == "rapidrbf-canonical-hierarchy-corpus-lock-v3",
        "lock schema differs",
    )
    require(lock.get("corpus_sha256") == CORPUS_SHA256, "corpus digest differs")
    for key, expected in EXPECTED_COUNTS.items():
        require(raw.get("counts", {}).get(key) == expected, f"count {key} differs")
    return raw, lock


def checked_identity(path: Path, expected: str, label: str) -> dict[str, Any]:
    observed = sha256_file(path)
    require(observed == expected, f"{label} drifted: {observed}")
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": observed}


def build_plan(corpus_root: Path) -> dict[str, Any]:
    raw, lock = load_authority(corpus_root)
    artifacts = lock["artifacts"]
    sources: list[dict[str, Any]] = []
    role_counts: dict[str, int] = {}
    for ordinal, source in enumerate(raw["factor_sources"]):
        matrix_role = source["matrix_role"]
        role = {"qtaq": "projected_b", "p_top": "coarse_p_top"}[matrix_role]
        artifact = artifacts[source["matrix_artifact"]]
        path = corpus_root / artifact["path"]
        require(path.is_file(), f"missing source payload {artifact['path']}")
        require(path.stat().st_size == artifact["bytes"], f"byte count differs: {path}")
        require(sha256_file(path) == artifact["sha256"], f"source hash differs: {path}")
        shape = artifact["shape"]
        require(
            isinstance(shape, list)
            and len(shape) == 2
            and shape[0] == shape[1]
            and shape[0] > 0,
            f"source is not square: {source['factor_source_id']}",
        )
        expected_encoding = (
            "lower-triangle-row-major-packed"
            if role == "projected_b"
            else "row-major"
        )
        require(
            artifact["encoding"] == expected_encoding,
            f"source encoding differs: {source['factor_source_id']}",
        )
        role_counts[role] = role_counts.get(role, 0) + 1
        sources.append(
            {
                "ordinal": ordinal,
                "factor_source_id": source["factor_source_id"],
                "block_id": source["block_id"],
                "workload_id": source["workload_id"],
                "role": role,
                "factorization": source["factorization"],
                "expected_rank": source["expected_rank"],
                "artifact_id": source["matrix_artifact"],
                "bundle_path": f"sources/{artifact['sha256']}.f64le",
                "bytes": artifact["bytes"],
                "sha256": artifact["sha256"],
                "dtype": artifact["dtype"],
                "byte_order": artifact["byte_order"],
                "encoding": artifact["encoding"],
                "dimension": shape[0],
                "stored_elements": artifact["stored_elements"],
            }
        )
    require(
        role_counts == {"projected_b": 204, "coarse_p_top": 12},
        f"factor role inventory differs: {role_counts}",
    )

    profile_path = CANDIDATE / "inputs" / "factor-health-profile.projected.json"
    binding_manifest = CANDIDATE / "binding-manifest.v1.json"
    lane_contract = LANES / "lane-contract.v1.json"
    authority = {
        "canonical_hierarchy": {
            "raw_manifest_sha256": RAW_MANIFEST_SHA256,
            "lock_sha256": LOCK_SHA256,
            "corpus_sha256": CORPUS_SHA256,
            "admission_report_sha256": ADMISSION_REPORT_SHA256,
            "physical_report_sha256": PHYSICAL_REPORT_SHA256,
        },
        "factor_health_profile": {
            **checked_identity(
                profile_path,
                "7ed996b6b2bce7e59398385fd152d41b56a7b47b7ddb5126ebff3b5f10152465",
                "factor-health profile",
            ),
            "profile_sha256": PROFILE_SHA256,
        },
        "candidate_binding": {
            **checked_identity(
                binding_manifest,
                "da90b4642e3670e458c5aa5cf3aa61e370a2a944f120f2f07e897ad00a25c822",
                "candidate binding manifest",
            ),
            "binding_sha256": BINDING_SHA256,
        },
        "lane_contract": checked_identity(
            lane_contract, LANE_CONTRACT_SHA256, "lane contract"
        ),
    }
    payload = {
        "schema": PLAN_SCHEMA,
        "question": (
            "Can the exact pinned instrumented faer binding qualify one "
            "QualifiedFactorAccess path for all 216 admitted factor sources "
            "on every tier-one target and registered lane?"
        ),
        "authority": authority,
        "counts": {
            **EXPECTED_COUNTS,
            "targets": 4,
            "lanes_per_target": 3,
            "required_lane_observations": 12,
        },
        "targets": [
            {
                "lane_id": "windows-x86_64",
                "runner": "windows-2025",
                "target": "x86_64-pc-windows-msvc",
            },
            {
                "lane_id": "linux-x86_64-glibc",
                "runner": "ubuntu-24.04",
                "target": "x86_64-unknown-linux-gnu",
            },
            {
                "lane_id": "macos-arm64",
                "runner": "macos-15",
                "target": "aarch64-apple-darwin",
            },
            {
                "lane_id": "macos-x86_64",
                "runner": "macos-15-intel",
                "target": "x86_64-apple-darwin",
            },
        ],
        "lanes": [
            {"workers": 1, "maximum_live_threads": 12},
            {"workers": 2, "maximum_live_threads": 12},
            {"workers": 8, "maximum_live_threads": 16},
        ],
        "rhs_families": [
            {
                "id": "operational",
                "solution": "1 + (row mod 17) / 17",
                "rhs": "matrix_times_declared_solution",
            },
            {
                "id": "constraint",
                "solution": "alternating +1/-1",
                "rhs": "matrix_times_declared_solution",
            },
            {
                "id": "dynamic-range",
                "solution": "sign(row)*2^((row mod 21)-10)",
                "rhs": "matrix_times_declared_solution",
            },
        ],
        "controls": [
            "source-positive-reload",
            "exact-n-minus-one-every-source",
            "truncated-pack",
            "corrupt-pack",
            "wrong-source",
            "wrong-profile",
            "metadata-mismatch",
            "mid-factor-cancellation",
            "mid-solve-cancellation",
            "prior-factor-reuse",
            "prior-solved-correction-reuse",
            "allocation-high-water",
            "thread-lane",
            "scratch-cleanup",
        ],
        "factor_access": {
            "packed_schema": "RapidRBF/PrototypeQualifiedFactorPack/v1",
            "recompute_recipe_schema": "RapidRBF/RunScopedRecomputeRecipe/v1",
            "recompute_budget": 216,
            "recompute_only_if_sole_nonpassing_gate": "durable_pack_reload",
            "retained_source_lease_required": True,
            "eviction_rebuild": False,
            "cross_run_cache": False,
        },
        "judgment": {
            "admitted": "ADMITTED_FOR_MECHANISM_PANEL",
            "not_admitted": "NOT_ADMITTED_DIAGNOSTIC_ONLY",
            "all_targets_lanes_sources_controls_non_compensating": True,
            "candidate_observations_may_not_change_plan": True,
        },
        "factor_sources": sources,
    }
    plan_digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return {
        **payload,
        "plan_id": f"{PLAN_SCHEMA}/{plan_digest}",
        "plan_payload_sha256": plan_digest,
    }


def write_plan(path: Path, plan: dict[str, Any]) -> bytes:
    data = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    encoded = data.encode("utf-8")
    if path.exists():
        require(path.read_bytes() == encoded, f"existing plan differs: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    return encoded


def copy_stream(source: BinaryIO, target: BinaryIO) -> None:
    shutil.copyfileobj(source, target, length=1024 * 1024)


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def write_bundle(
    path: Path,
    corpus_root: Path,
    plan: dict[str, Any],
    plan_bytes: bytes,
) -> dict[str, Any]:
    if path.exists():
        raise FileExistsError(f"bundle output must be absent: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        unique_sources: dict[str, dict[str, Any]] = {}
        for source in plan["factor_sources"]:
            unique_sources.setdefault(source["sha256"], source)
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1,
            allowZip64=True,
        ) as archive:
            archive.writestr(zip_info("factor-qualification-plan.v1.json"), plan_bytes)
            for digest, source in sorted(unique_sources.items()):
                artifact = lock["artifacts"][source["artifact_id"]]
                source_path = corpus_root / artifact["path"]
                require(sha256_file(source_path) == digest, f"source drifted: {source_path}")
                with source_path.open("rb") as input_handle:
                    with archive.open(zip_info(source["bundle_path"]), "w") as output_handle:
                        copy_stream(input_handle, output_handle)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    unique_by_hash = {
        source["sha256"]: source for source in plan["factor_sources"]
    }
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "factor_source_entries": len(plan["factor_sources"]),
        "unique_matrix_payloads": len(unique_by_hash),
        "unique_matrix_bytes": sum(
            source["bytes"] for source in unique_by_hash.values()
        ),
    }


def write_directory(
    path: Path,
    corpus_root: Path,
    plan: dict[str, Any],
    plan_bytes: bytes,
) -> dict[str, Any]:
    if path.exists():
        raise FileExistsError(f"directory output must be absent: {path}")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    path.mkdir(parents=True)
    try:
        (path / "factor-qualification-plan.v1.json").write_bytes(plan_bytes)
        unique_sources = {
            source["sha256"]: source for source in plan["factor_sources"]
        }
        for digest, source in unique_sources.items():
            artifact = lock["artifacts"][source["artifact_id"]]
            source_path = corpus_root / artifact["path"]
            target = path / source["bundle_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source_path, target)
            except OSError:
                shutil.copyfile(source_path, target)
            require(sha256_file(target) == digest, f"directory source drifted: {target}")
    except BaseException:
        shutil.rmtree(path, ignore_errors=True)
        raise
    return {
        "path": str(path),
        "factor_source_entries": len(plan["factor_sources"]),
        "unique_matrix_payloads": len(unique_sources),
        "unique_matrix_bytes": sum(
            source["bytes"] for source in unique_sources.values()
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--bundle-output", type=Path)
    parser.add_argument("--directory-output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    corpus_root = args.corpus_root.resolve()
    plan = build_plan(corpus_root)
    plan_bytes = write_plan(args.plan_output.resolve(), plan)
    result: dict[str, Any] = {
        "plan": {
            "file": args.plan_output.name,
            "bytes": len(plan_bytes),
            "sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "plan_id": plan["plan_id"],
        }
    }
    if args.bundle_output is not None:
        result["bundle"] = write_bundle(
            args.bundle_output.resolve(), corpus_root, plan, plan_bytes
        )
    if args.directory_output is not None:
        result["directory"] = write_directory(
            args.directory_output.resolve(), corpus_root, plan, plan_bytes
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, OSError, ValueError) as error:
        raise SystemExit(f"prepare bundle failed: {error}") from error
