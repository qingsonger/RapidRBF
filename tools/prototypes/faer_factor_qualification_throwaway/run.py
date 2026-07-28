"""THROWAWAY: build the fail-closed faer factor-qualification evidence bundle.

The run deliberately stops before calling a factor backend when the bound
direct in-process stock-faer candidate has not closed the preregistered
whole-call resource and cancellation contracts. A small residual is not
allowed to override that preflight.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from model import Disposition, Gate, GateStatus, decide


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
PROFILE_SHA256 = "55398d3e7156d7af09bbcb47aa320506f08f2a8c720f80506a1df3648e5f2124"
CANDIDATE_MANIFEST_SHA256 = (
    "82dcc349b0734c52f28058ad4b562a73c4938e13e552ebf520a8d67ab5578bc0"
)
CANDIDATE_LOCK_SHA256 = (
    "bd15eedbba33089e0613b5ad7134e627733140f6bcc127cedb5f9eac2bd83915"
)
EXPECTED_CRATE_CLOSURES = {
    "faer-0.24.4": {
        "files": 179,
        "bytes": 9_208_583,
        "sha256": "6788513332d8385fe5b01e104aa407b9302ea2d126d7dc60386a512b0e957d61",
    },
    "private-gemm-x86-0.1.20": {
        "files": 13,
        "bytes": 262_197,
        "sha256": "fbfb14de2dabc443a292be45bc763725d19482fa73ed324b050dd72c5716bcd2",
    },
    "dyn-stack-0.13.2": {
        "files": 15,
        "bytes": 107_768,
        "sha256": "f0e0c3c60c4aa59b8cd24d671e1860ac89c6e8163f728282a05cfa1e3158d608",
    },
}

EXPECTED_COUNTS = {
    "workloads": 12,
    "blocks": 204,
    "factor_sources": 216,
    "qtaq_factor_sources": 204,
    "p_top_factor_sources": 12,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_identity(path: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    data = path.read_bytes()
    actual = sha256_bytes(data)
    if actual != expected_sha256:
        raise ValueError(
            f"{path} identity drifted: expected {expected_sha256}, found {actual}"
        )
    return data, {
        # Evidence bundles must remain portable and must not disclose the
        # workstation-specific location of a reproduced corpus or registry.
        "name": path.name,
        "bytes": len(data),
        "sha256": actual,
    }


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not canonical JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, found {actual!r}")


def validate_authority(
    manifest_path: Path,
    admission_path: Path,
    physical_path: Path,
    profile_path: Path,
    candidate_manifest_path: Path,
    candidate_lock_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_bytes, manifest_identity = read_identity(
        manifest_path, RAW_MANIFEST_SHA256
    )
    lock_path = manifest_path.with_name("manifest.lock.json")
    lock_bytes, lock_identity = read_identity(lock_path, LOCK_SHA256)
    admission_bytes, admission_identity = read_identity(
        admission_path, ADMISSION_REPORT_SHA256
    )
    physical_bytes, physical_identity = read_identity(
        physical_path, PHYSICAL_REPORT_SHA256
    )
    profile_bytes, profile_identity = read_identity(profile_path, PROFILE_SHA256)
    candidate_manifest_bytes, candidate_manifest_identity = read_identity(
        candidate_manifest_path, CANDIDATE_MANIFEST_SHA256
    )
    candidate_lock_bytes, candidate_lock_identity = read_identity(
        candidate_lock_path, CANDIDATE_LOCK_SHA256
    )

    manifest = parse_json(manifest_bytes, "manifest")
    lock = parse_json(lock_bytes, "lock")
    admission = parse_json(admission_bytes, "admission report")
    physical = parse_json(physical_bytes, "physical report")
    profile = parse_json(profile_bytes, "factor health profile")

    require_equal(
        manifest.get("schema"),
        "rapidrbf-canonical-hierarchy-admission-corpus-v3",
        "manifest schema",
    )
    require_equal(
        lock.get("schema"),
        "rapidrbf-canonical-hierarchy-corpus-lock-v3",
        "lock schema",
    )
    require_equal(lock.get("corpus_sha256"), CORPUS_SHA256, "corpus digest")

    counts = manifest.get("counts", {})
    for key, expected in EXPECTED_COUNTS.items():
        require_equal(counts.get(key), expected, f"manifest counts.{key}")
    roles: dict[str, int] = {}
    for source in manifest.get("factor_sources", []):
        role = source.get("matrix_role")
        roles[role] = roles.get(role, 0) + 1
    require_equal(roles, {"qtaq": 204, "p_top": 12}, "factor role inventory")

    require_equal(
        admission.get("schema"),
        "RapidRBF/HierarchyAdmissionReport/v1",
        "admission schema",
    )
    require_equal(admission.get("state"), "Admitted", "admission state")
    require_equal(admission.get("backend_invocations"), 0, "admission backend calls")
    require_equal(admission.get("state_counts"), {"Admitted": 625}, "admission certificates")
    inventory = admission.get("inventory", {})
    for key in ("workloads", "blocks", "factor_sources"):
        expected = EXPECTED_COUNTS[key]
        require_equal(inventory.get(key), expected, f"admission inventory.{key}")

    require_equal(
        physical.get("schema"),
        "rapidrbf-independent-physical-evaluator-v2",
        "physical schema",
    )
    require_equal(physical.get("backend_calls"), 0, "physical backend calls")
    require_equal(physical.get("factor_count"), 204, "physical factor count")
    require_equal(
        physical.get("certified_factor_count"), 204, "physical certified count"
    )
    require_equal(physical.get("rejected_factor_count"), 0, "physical rejected count")
    require_equal(physical.get("admission_claim"), False, "physical admission claim")

    require_equal(
        profile.get("schema"),
        "rapidrbf-factor-health-profile-v1",
        "factor profile schema",
    )
    require_equal(
        profile.get("authority", {}).get("corpus_sha256"),
        CORPUS_SHA256,
        "factor profile corpus",
    )
    candidate = profile.get("candidate", {})
    require_equal(candidate.get("crate"), "faer", "candidate crate")
    require_equal(candidate.get("version"), "0.24.4", "candidate version")
    require_equal(
        candidate.get("cargo_manifest_sha256"),
        CANDIDATE_MANIFEST_SHA256,
        "candidate manifest identity",
    )
    require_equal(
        candidate.get("cargo_lock_sha256"),
        CANDIDATE_LOCK_SHA256,
        "candidate lock identity",
    )
    require_equal(candidate.get("default_features"), False, "candidate defaults")
    require_equal(candidate.get("features"), ["std", "linalg"], "candidate features")
    require_equal(
        candidate.get("target"),
        "x86_64-pc-windows-msvc",
        "candidate target",
    )
    require_equal(
        candidate.get("required_cpu_features"),
        ["avx2", "fma"],
        "candidate CPU features",
    )
    require_equal(
        candidate.get("local_parallelism"),
        "Par::Seq",
        "candidate local parallelism",
    )
    require_equal(
        candidate.get("execution_boundary"),
        "direct-in-process-stock-crate",
        "candidate execution boundary",
    )
    require_equal(
        candidate.get("process_isolated_backend"),
        False,
        "candidate process isolation",
    )
    require_equal(
        candidate.get("allocator_instrumentation"),
        False,
        "candidate allocator instrumentation",
    )

    candidate_manifest_text = candidate_manifest_bytes.decode("utf-8")
    required_manifest_line = (
        'faer = { version = "=0.24.4", default-features = false, '
        'features = ["std", "linalg"] }'
    )
    if required_manifest_line not in candidate_manifest_text:
        raise ValueError("candidate manifest no longer binds faer std+linalg")
    candidate_lock_text = candidate_lock_bytes.decode("utf-8").replace("\r\n", "\n")
    if 'name = "faer"\nversion = "0.24.4"' not in candidate_lock_text:
        raise ValueError("candidate lock no longer binds faer 0.24.4")

    runtime = admission.get("execution", {}).get("runtime", {})
    require_equal(runtime.get("system"), "Windows", "registered runtime system")
    require_equal(runtime.get("machine"), "AMD64", "registered runtime machine")
    found_simd = runtime.get("simd_extensions", {}).get("found", [])
    for feature in ("AVX2", "FMA3"):
        if feature not in found_simd:
            raise ValueError(
                f"registered runtime no longer records required SIMD feature {feature}"
            )

    identities = {
        "manifest": manifest_identity,
        "lock": lock_identity,
        "admission_report": admission_identity,
        "physical_report": physical_identity,
        "factor_health_profile": profile_identity,
        "candidate_manifest": candidate_manifest_identity,
        "candidate_lock": candidate_lock_identity,
    }
    authority = {
        "counts": EXPECTED_COUNTS,
        "factor_roles": roles,
        "semantic_state": "Admitted",
        "rank_and_nullspace_certificates": 625,
        "physical_witnesses": 204,
        "candidate_factor_backend_calls": 0,
        "candidate_build": {
            "target": "x86_64-pc-windows-msvc",
            "features": ["std", "linalg"],
            "default_features": False,
            "registered_cpu_features": ["avx2", "fma"],
            "local_parallelism": "Par::Seq",
            "execution_boundary": "direct-in-process-stock-crate",
        },
    }
    return {"identities": identities, "authority": authority}, profile


def require_source(
    root: Path,
    namespace: str,
    relative: str,
    required_fragments: Iterable[str],
) -> dict[str, Any]:
    path = root / relative
    data = path.read_bytes()
    text = data.decode("utf-8")
    missing = [fragment for fragment in required_fragments if fragment not in text]
    if missing:
        raise ValueError(f"{path} no longer contains required source evidence {missing}")
    normalized = relative.replace("\\", "/")
    return {
        "path": f"{namespace}/{normalized}",
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "required_fragments": list(required_fragments),
    }


def source_set_hash(findings: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for finding in sorted(findings, key=lambda item: item["path"]):
        path = finding["path"].encode("utf-8")
        file_hash = bytes.fromhex(finding["sha256"])
        digest.update(len(path).to_bytes(8, "little"))
        digest.update(path)
        digest.update(len(file_hash).to_bytes(8, "little"))
        digest.update(file_hash)
    return digest.hexdigest()


def crate_closure(root: Path) -> dict[str, Any]:
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        total_bytes += len(data)
        digest.update(len(relative).to_bytes(8, "little"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "little"))
        digest.update(hashlib.sha256(data).digest())
    observed = {
        "files": len(files),
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }
    require_equal(
        observed,
        EXPECTED_CRATE_CLOSURES[root.name],
        f"{root.name} full source closure",
    )
    return observed


def combined_crate_closure_hash(closures: dict[str, dict[str, Any]]) -> str:
    payload = json.dumps(
        closures,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def audit_sources(faer_root: Path) -> dict[str, Any]:
    if faer_root.name != "faer-0.24.4":
        raise ValueError(f"--faer-source must be the pinned faer-0.24.4 root: {faer_root}")
    registry_root = faer_root.parent
    dependency_roots = {
        "private_gemm": registry_root / "private-gemm-x86-0.1.20",
        "dyn_stack": registry_root / "dyn-stack-0.13.2",
    }
    for name, path in dependency_roots.items():
        if not path.is_dir():
            raise ValueError(f"pinned {name} source is missing at {path}")

    roots = {
        faer_root.name: faer_root,
        dependency_roots["private_gemm"].name: dependency_roots["private_gemm"],
        dependency_roots["dyn_stack"].name: dependency_roots["dyn_stack"],
    }
    closures = {name: crate_closure(root) for name, root in roots.items()}

    findings = [
        require_source(
            faer_root,
            faer_root.name,
            "src/linalg/solvers.rs",
            (
                "pub struct Lblt<T>",
                "pub struct FullPivLu<T>",
                "pub fn B_diag(&self)",
                "pub fn B_subdiag(&self)",
                "pub fn P(&self)",
                "pub fn Q(&self)",
                "get_global_parallelism()",
            ),
        ),
        require_source(
            faer_root,
            faer_root.name,
            "src/linalg/lu/partial_pivoting/factor.rs",
            ("pub fn lu_in_place_scratch", "pub fn lu_in_place"),
        ),
        require_source(
            faer_root,
            faer_root.name,
            "src/linalg/lu/full_pivoting/factor.rs",
            (
                "pub fn lu_in_place_scratch",
                "pub fn lu_in_place",
                "collect::<alloc::vec::Vec<_>>()",
            ),
        ),
        require_source(
            faer_root,
            faer_root.name,
            "src/linalg/matmul/internal/mod.rs",
            (
                '#[cfg(all(target_arch = "x86_64", feature = "std"))]',
                'is_x86_feature_detected!("avx2")',
                'is_x86_feature_detected!("fma")',
                "use private_gemm_x86::*",
                "private_gemm_x86::gemm",
            ),
        ),
        require_source(
            faer_root,
            faer_root.name,
            "src/lib.rs",
            (
                "pub enum Par",
                "GLOBAL_PARALLELISM",
                "pub fn disable_global_parallelism()",
                "pub fn set_global_parallelism(par: Par)",
            ),
        ),
        require_source(
            faer_root,
            faer_root.name,
            "Cargo.toml.orig",
            (
                "std = [",
                '"dep:private-gemm-x86"',
                "linalg = []",
            ),
        ),
        require_source(
            dependency_roots["private_gemm"],
            dependency_roots["private_gemm"].name,
            "src/lib.rs",
            (
                "thread_local!",
                "static MEM: RefCell<Vec",
                "Vec::with_capacity(lhs_size + rhs_size)",
                "mem.reserve_exact(lhs_size + rhs_size)",
            ),
        ),
        require_source(
            dependency_roots["dyn_stack"],
            dependency_roots["dyn_stack"].name,
            "src/mem.rs",
            (
                "impl<A: Allocator> Drop for MemBuffer<A>",
                "self.alloc.deallocate",
            ),
        ),
        require_source(
            dependency_roots["dyn_stack"],
            dependency_roots["dyn_stack"].name,
            "src/stack_req.rs",
            (
                "pub const fn size_bytes(&self)",
                "pub fn any_of",
            ),
        ),
    ]

    cancellation_files = list((faer_root / "src/linalg").rglob("*.rs"))
    cancellation_pattern = re.compile(
        r"\b(cancel(?:lation|led)?|deadline|AtomicBool)\b", re.IGNORECASE
    )
    cancellation_matches: list[str] = []
    for path in sorted(cancellation_files):
        text = path.read_text(encoding="utf-8")
        if cancellation_pattern.search(text):
            cancellation_matches.append(path.relative_to(faer_root).as_posix())
    if cancellation_matches:
        raise ValueError(
            "pinned factor/solve source unexpectedly gained cancellation vocabulary: "
            + ", ".join(cancellation_matches)
        )

    return {
        "candidate": {"crate": "faer", "version": "0.24.4"},
        "crate_closure_algorithm": (
            "sha256-length-prefixed-path-byte-length-file-sha256-v1"
        ),
        "source_closure_algorithm": (
            "sha256-of-canonical-json-over-full-crate-closures-v1"
        ),
        "source_closure_sha256": combined_crate_closure_hash(closures),
        "crate_closures": closures,
        "audited_api_set_sha256": source_set_hash(findings),
        "files": findings,
        "facts": {
            "owned_component_getters": True,
            "low_level_explicit_memstack": True,
            "high_level_process_global_parallelism": True,
            "bound_target": "x86_64-pc-windows-msvc",
            "bound_features": ["std", "linalg"],
            "bound_registered_cpu_features": ["avx2", "fma"],
            "bound_execution_boundary": "direct-in-process-stock-crate",
            "bound_local_parallelism": "Par::Seq",
            "unselected_parallel_full_pivot_path_allocates_vec_outside_memstack": (
                True
            ),
            "bound_native_f64_matmul_routes_to_private_gemm": True,
            "private_gemm_persistent_tls_vec": True,
            "dyn_stack_drop_deallocates_without_write_or_residue_evidence": True,
            "factor_and_solve_module_cancellation_matches": cancellation_matches,
        },
    }


def gate_records(source_audit: dict[str, Any], authority: dict[str, Any]) -> list[Gate]:
    source_ref = source_audit["source_closure_sha256"]
    manifest_ref = authority["identities"]["manifest"]["sha256"]
    profile_ref = authority["identities"]["factor_health_profile"]["sha256"]
    return [
        Gate(
            "semantic_corpus",
            "Canonical corpus and semantic authority",
            GateStatus.PASS,
            "upstream rank/nullspace and physical certificates",
            "The complete 12-workload, 204-block, 216-factor inventory is "
            "bound; the backend has no rank authority.",
            (manifest_ref, CORPUS_SHA256, ADMISSION_REPORT_SHA256, PHYSICAL_REPORT_SHA256),
        ),
        Gate(
            "factor_health_profile",
            "Preregistered FactorHealthProfile",
            GateStatus.PASS,
            "candidate-independent profile",
            "Algorithms, health formulae, controls, lanes, and the narrow "
            "recompute exception were frozen before candidate execution.",
            (profile_ref,),
        ),
        Gate(
            "owned_representation",
            "RapidRBF-owned B and P_top representation",
            GateStatus.PARTIAL,
            "public faer component and low-level interfaces",
            "Stock faer exposes enough logical components for an owned "
            "record, but the complete P_top record and all-216-source reload "
            "witness have not been materialized.",
            (source_ref, "Stage-0 QTAQ pack/reload was diagnostic only"),
        ),
        Gate(
            "external_certificate",
            "Externally certified operational and manufactured solves",
            GateStatus.NOT_REACHED,
            "independent value/gradient and CPD evaluator",
            "The current evaluator certifies frozen reference witnesses, not "
            "runtime faer outputs; backend entry is rejected before candidate "
            "publication.",
            (PHYSICAL_REPORT_SHA256,),
        ),
        Gate(
            "exact_transient_accounting",
            "Exact whole-call transient and cleanup accounting",
            GateStatus.BLOCKED,
            "caller-owned resource grant",
            "For the bound Windows std+linalg direct in-process candidate, "
            "native f64 GEMM retains a TLS Vec outside faer's declared "
            "MemStack and the caller's grant; this candidate has neither "
            "allocator instrumentation nor an isolated-worker quota.",
            (source_ref, "private-gemm TLS capacity derives from runtime cache topology"),
        ),
        Gate(
            "caller_permit_lease",
            "Caller-owned permit lease and maximum-live evidence",
            GateStatus.PARTIAL,
            "registered 1/12, 2/12, and 8/16 lanes",
            "Low-level calls accept explicit Par and can be wrapped, but "
            "stock faer supplies no lease or active-worker evidence and the "
            "prototype has not materialized the process-tree lane controller.",
            (source_ref,),
        ),
        Gate(
            "bounded_cancellation",
            "Bounded cancellation with prior-state preservation",
            GateStatus.BLOCKED,
            "operational factor contract",
            "Pinned in-process factor/solve code exposes no cancellation "
            "token or polling hook, and this candidate has no isolated "
            "worker to terminate; boundary checks cannot interrupt an "
            "in-flight O(n^3) kernel.",
            (source_ref, "factor/solve cancellation vocabulary matches: 0"),
        ),
        Gate(
            "lane_closure",
            "Complete 1k/10k resource and thread lanes",
            GateStatus.NOT_REACHED,
            "non-compensating execution lanes",
            "No candidate session may start after the exact-resource and "
            "cancellation preflight fails; no lane may borrow authority from "
            "another.",
            ("1/12", "2/12", "8/16"),
        ),
        Gate(
            "atomic_controls",
            "Atomic corruption, grant, cancellation, and reuse controls",
            GateStatus.PARTIAL,
            "transactional factor and solve publication",
            "Metadata and pack controls are implementable outside faer, but "
            "cancellation, total-grant-minus-one, and all-lane reuse cannot "
            "close while the owning contracts are blocked.",
            (source_ref,),
        ),
        Gate(
            "durable_pack_reload",
            "Durable pack/reload",
            GateStatus.PARTIAL,
            "RapidRBF-owned logical factor format",
            "Logical component packing is feasible, but this is not the sole "
            "gap; the profile therefore forbids the run-scoped recompute "
            "exception.",
            (source_ref,),
        ),
    ]


def markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Direct in-process stock faer 0.24.4 factor qualification",
        "",
        "## Disposition",
        "",
        f"**`{summary['disposition']}`.**",
        "",
        "The canonical corpus and its pre-backend semantic authority are complete, "
        "but the bound Windows std+linalg direct in-process candidate does not "
        "close the preregistered whole-call transient accounting and bounded "
        "in-flight cancellation obligations. "
        "Backend calls therefore remain zero and no `ValidatedFactor` or `Solved` "
        "state is published.",
        "",
        "Durable pack/reload is not the sole gap, so the profile's bounded "
        "run-scoped recompute exception is inapplicable.",
        "",
        "## Bound inputs",
        "",
        f"- Corpus: `{summary['authority']['identities']['lock']['sha256']}` "
        f"(canonical digest `{CORPUS_SHA256}`).",
        f"- Admission report: `{ADMISSION_REPORT_SHA256}`; 625/625 rank/nullspace certificates.",
        f"- Physical report: `{PHYSICAL_REPORT_SHA256}`; 204/204 frozen witnesses.",
        f"- FactorHealthProfile: `{PROFILE_SHA256}`.",
        f"- Candidate Cargo manifest/lock: `{CANDIDATE_MANIFEST_SHA256}` / "
        f"`{CANDIDATE_LOCK_SHA256}`.",
        "- Candidate route: `x86_64-pc-windows-msvc`, `std+linalg`, "
        "registered `AVX2+FMA`, `Par::Seq`, direct in-process.",
        f"- faer source closure: `{summary['source_audit']['source_closure_sha256']}`.",
        "",
        "## Gates",
        "",
        "| Gate | State | Reason |",
        "| --- | --- | --- |",
    ]
    for gate in summary["gates"]:
        reason = gate["reason"].replace("|", "\\|")
        lines.append(f"| {gate['title']} | `{gate['status']}` | {reason} |")
    lines.extend(
        [
            "",
            "## What remains possible",
            "",
            "- Public L/B/permutation and full-pivot L/U/P/Q data are sufficient "
            "to define RapidRBF-owned logical records; raw faer allocations are not a format.",
            "- Low-level calls can accept explicit `Par` and `MemStack`; an outer "
            "controller can add permits, process isolation, and metadata controls.",
            "- A future probe may qualify an instrumented faer fork or an isolated "
            "adapter with an accepted quota allocator and hard-cancellation design.",
            "",
            "Those are follow-up hypotheses, not evidence that this candidate "
            "passed or that every possible RapidRBF-owned faer adapter fails.",
            "",
            "## Deliberate limits",
            "",
            "- No factor backend was called after the preflight rejected the contract.",
            "- No runtime faer witness was passed to the independent physical evaluator.",
            "- No dependency adoption, mechanism comparison, persistent factor-store "
            "policy, 100k run, or production backend selection is claimed.",
            "",
        ]
    )
    return "\n".join(lines)


def fsync_write(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def publish_fresh_directory(output: Path, summary: dict[str, Any]) -> None:
    if output.exists():
        raise FileExistsError(f"fresh output path already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(f"staging path already exists: {staging}")
    staging.mkdir()
    staged_files = (
        staging / "qualification-summary.json",
        staging / "observed-results.md",
    )
    try:
        summary_bytes = (
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        report_bytes = markdown_report(summary).encode("utf-8")
        fsync_write(staged_files[0], summary_bytes)
        fsync_write(staged_files[1], report_bytes)
        os.replace(staging, output)
    except BaseException:
        for path in staged_files:
            path.unlink(missing_ok=True)
        staging.rmdir()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    candidate_replay = (
        Path(__file__).resolve().parent.parent
        / "dense_factor_replay_throwaway"
        / "replay"
    )
    parser.add_argument("--corpus-manifest", required=True, type=Path)
    parser.add_argument("--admission-report", required=True, type=Path)
    parser.add_argument("--physical-report", required=True, type=Path)
    parser.add_argument("--faer-source", required=True, type=Path)
    parser.add_argument(
        "--candidate-manifest",
        type=Path,
        default=candidate_replay / "Cargo.toml",
    )
    parser.add_argument(
        "--candidate-lock",
        type=Path,
        default=candidate_replay / "Cargo.lock",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).with_name("factor-health-profile.v1.json"),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    authority, profile = validate_authority(
        args.corpus_manifest.resolve(),
        args.admission_report.resolve(),
        args.physical_report.resolve(),
        args.profile.resolve(),
        args.candidate_manifest.resolve(),
        args.candidate_lock.resolve(),
    )
    source_audit = audit_sources(args.faer_source.resolve())
    gates = gate_records(source_audit, authority)
    disposition = decide(gates)
    require_equal(
        disposition,
        Disposition.NOT_ADMITTED_DIAGNOSTIC_ONLY,
        "fail-closed disposition",
    )
    summary = {
        "schema": "rapidrbf-faer-factor-qualification-lab-v1",
        "question": (
            "Can the bound Windows std+linalg direct in-process stock-faer "
            "0.24.4 candidate publish run-scoped ValidatedFactor and "
            "externally certified Solved corrections for every canonical "
            "1k/10k mechanism-panel factor while closing all registered gates?"
        ),
        "disposition": disposition.value,
        "backend_calls": 0,
        "published_validated_factors": 0,
        "published_solved_corrections": 0,
        "preflight": {
            "state": "BackendContractUnavailable",
            "reason": (
                "the bound direct in-process candidate lacks whole-call "
                "transient grant authority and bounded in-flight cancellation"
            ),
            "candidate_observations_used_to_set_profile": False,
        },
        "authority": authority,
        "profile": profile,
        "source_audit": source_audit,
        "gates": [
            {
                **asdict(gate),
                "status": gate.status.value,
                "evidence": list(gate.evidence),
            }
            for gate in gates
        ],
        "recompute_exception": {
            "eligible": False,
            "reason": "durable_pack_reload is not the sole nonpassing gate",
        },
        "next_decision": {
            "question": (
                "Should v1 probe an instrumented/isolated faer adapter with "
                "accepted quota and cancellation authority, or reopen the "
                "dense-factor substrate?"
            ),
            "not_part_of_this_ticket": True,
        },
    }
    publish_fresh_directory(args.output.resolve(), summary)
    print(json.dumps(
        {
            "disposition": disposition.value,
            "backend_calls": 0,
            "output": str(args.output.resolve()),
        },
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, OSError, ValueError) as error:
        print(f"qualification lab failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
