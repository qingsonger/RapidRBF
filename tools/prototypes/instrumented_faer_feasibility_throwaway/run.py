"""Reproducible evidence runner for the instrumented-faer feasibility prototype.

The runner verifies frozen stock-source facts and produces an evidence state.
It intentionally refuses to manufacture an exact fork identity or target
witness when those artifacts do not exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
INPUTS = HERE / "inputs"

EXPECTED_COMBINED_PROFILE_SHA256 = (
    "55398d3e7156d7af09bbcb47aa320506f08f2a8c720f80506a1df3648e5f2124"
)
EXPECTED_CRATE_CLOSURES = {
    "faer-0.24.4": {
        "files": 179,
        "bytes": 9208583,
        "sha256": "6788513332d8385fe5b01e104aa407b9302ea2d126d7dc60386a512b0e957d61",
    },
    "private-gemm-x86-0.1.20": {
        "files": 13,
        "bytes": 262197,
        "sha256": "fbfb14de2dabc443a292be45bc763725d19482fa73ed324b050dd72c5716bcd2",
    },
    "dyn-stack-0.13.2": {
        "files": 15,
        "bytes": 107768,
        "sha256": "f0e0c3c60c4aa59b8cd24d671e1860ac89c6e8163f728282a05cfa1e3158d608",
    },
}
EXPECTED_COMBINED_SOURCE_CLOSURE = (
    "530103a7c8f62e8cf225045d39410b9d36e67d11f5acf6793f403bb0fc1a9fb9"
)
PROJECTED_KEYS = (
    "authority",
    "factor_health",
    "owned_representation",
    "publication",
    "resource_contract",
    "cancellation_contract",
    "thread_contract",
    "allowed_outcomes",
    "recompute_exception",
)


class Status(StrEnum):
    PASS = "PASS"
    MISSING = "EVIDENCE_MISSING"
    NOT_REACHED = "NOT_REACHED"
    REJECTED = "EVIDENCE_BACKED_REJECTED"


class Disposition(StrEnum):
    FEASIBLE = "FEASIBLE_FOR_216_FACTOR_QUALIFICATION"
    REJECTED = "EVIDENCE_BACKED_REJECTED"
    UNJUDGED = "UNJUDGED_EVIDENCE_MISSING"


@dataclass(frozen=True)
class Gate:
    gate_id: str
    title: str
    status: Status
    authority: str
    reason: str
    evidence: tuple[str, ...]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_combined_profile(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    digest = sha256_bytes(data)
    require(
        digest == EXPECTED_COMBINED_PROFILE_SHA256,
        "combined profile bytes differ from the accepted direct-faer evidence: "
        f"expected {EXPECTED_COMBINED_PROFILE_SHA256}, found {digest}",
    )
    profile = json.loads(data)
    require(
        tuple(key for key in PROJECTED_KEYS if key not in profile) == (),
        "combined profile is missing a projected rule field",
    )
    require(
        profile.get("candidate", {}).get("execution_boundary")
        == "direct-in-process-stock-crate",
        "the projection input is not the accepted mixed direct-faer profile",
    )
    return profile, digest


def project_profile(
    profile: dict[str, Any], origin_sha256: str
) -> tuple[dict[str, Any], str]:
    projected: dict[str, Any] = {
        "schema": "rapidrbf-factor-health-profile-projection-v1",
        "profile_id": profile["profile_id"],
        "projection": {
            "algorithm": "ordered-allowlist-from-accepted-mixed-profile-v1",
            "origin_sha256": origin_sha256,
            "included_top_level_fields": list(PROJECTED_KEYS),
            "excluded_top_level_fields": ["schema", "candidate"],
        },
    }
    for key in PROJECTED_KEYS:
        projected[key] = profile[key]
    digest = sha256_bytes(canonical_bytes(projected))
    return projected, digest


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
    expected = EXPECTED_CRATE_CLOSURES.get(root.name)
    require(expected is not None, f"unexpected crate root {root.name}")
    require(
        observed == expected,
        f"{root.name} source closure mismatch: expected {expected}, found {observed}",
    )
    return observed


def combined_crate_closure_hash(
    closures: dict[str, dict[str, Any]]
) -> str:
    return sha256_bytes(canonical_bytes(closures))


def require_source(
    root: Path,
    namespace: str,
    relative: str,
    required_fragments: Iterable[str],
) -> dict[str, Any]:
    path = root / relative
    data = path.read_bytes()
    text = data.decode("utf-8")
    fragments = tuple(required_fragments)
    missing = [fragment for fragment in fragments if fragment not in text]
    require(not missing, f"{namespace}/{relative} is missing {missing}")
    return {
        "path": f"{namespace}/{relative}",
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "required_fragments": list(fragments),
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


def audit_sources(registry_root: Path) -> dict[str, Any]:
    roots = {
        "faer-0.24.4": registry_root / "faer-0.24.4",
        "private-gemm-x86-0.1.20": registry_root
        / "private-gemm-x86-0.1.20",
        "dyn-stack-0.13.2": registry_root / "dyn-stack-0.13.2",
    }
    for root in roots.values():
        require(root.is_dir(), f"missing exact crate source {root.name}")

    closures = {name: crate_closure(root) for name, root in roots.items()}
    combined = combined_crate_closure_hash(closures)
    require(
        combined == EXPECTED_COMBINED_SOURCE_CLOSURE,
        "combined source closure changed: "
        f"expected {EXPECTED_COMBINED_SOURCE_CLOSURE}, found {combined}",
    )

    faer = roots["faer-0.24.4"]
    gemm = roots["private-gemm-x86-0.1.20"]
    stack = roots["dyn-stack-0.13.2"]
    findings = [
        require_source(
            faer,
            "faer-0.24.4",
            "src/linalg/matmul/internal/mod.rs",
            (
                "pub fn spicy_matmul_scratch",
                "return StackReq::EMPTY;",
                "private_gemm_x86::gemm(",
            ),
        ),
        require_source(
            faer,
            "faer-0.24.4",
            "src/linalg/cholesky/bunch_kaufman/factor.rs",
            (
                "fn lblt_blocked_step",
                "fn lblt_blocked",
                "fn lblt_unblocked",
                "pub fn cholesky_in_place",
            ),
        ),
        require_source(
            faer,
            "faer-0.24.4",
            "src/linalg/cholesky/bunch_kaufman/solve.rs",
            ("pub fn solve_in_place_scratch", "pub fn solve_in_place"),
        ),
        require_source(
            faer,
            "faer-0.24.4",
            "src/linalg/lu/full_pivoting/factor.rs",
            (
                "pub fn lu_in_place_scratch",
                "pub fn lu_in_place",
                "collect::<alloc::vec::Vec<_>>()",
            ),
        ),
        require_source(
            faer,
            "faer-0.24.4",
            "src/linalg/lu/full_pivoting/solve.rs",
            ("pub fn solve_in_place_scratch", "pub fn solve_in_place"),
        ),
        require_source(
            faer,
            "faer-0.24.4",
            "src/linalg/triangular_solve.rs",
            (
                "fn solve_unit_lower_triangular_in_place_imp",
                "fn solve_upper_triangular_in_place_imp",
            ),
        ),
        require_source(
            gemm,
            "private-gemm-x86-0.1.20",
            "src/lib.rs",
            (
                "pub unsafe fn gemm(",
                "thread_local!",
                "static MEM: RefCell<Vec",
                "Vec::with_capacity(lhs_size + rhs_size)",
                "mem.reserve_exact(lhs_size + rhs_size)",
            ),
        ),
        require_source(
            stack,
            "dyn-stack-0.13.2",
            "src/lib.rs",
            (
                "pub struct MemStack",
                "pub fn make_with<T>",
                "unsafe impl alloc::Allocator for Bump",
            ),
        ),
        require_source(
            stack,
            "dyn-stack-0.13.2",
            "src/mem.rs",
            (
                "pub fn try_new_in",
                "impl<A: Allocator> Drop for MemBuffer<A>",
                "impl<A: Allocator> Drop for PodBuffer<A>",
            ),
        ),
    ]

    cancellation_pattern = re.compile(
        r"\b(cancel|cancellation|cancelled|checkpoint|poll)\b",
        re.IGNORECASE,
    )
    selected_factor_files = (
        faer / "src/linalg/cholesky/bunch_kaufman/factor.rs",
        faer / "src/linalg/cholesky/bunch_kaufman/solve.rs",
        faer / "src/linalg/lu/full_pivoting/factor.rs",
        faer / "src/linalg/lu/full_pivoting/solve.rs",
        faer / "src/linalg/triangular_solve.rs",
        faer / "src/linalg/matmul/internal/mod.rs",
        gemm / "src/lib.rs",
    )
    cancellation_matches = [
        path.name
        for path in selected_factor_files
        if cancellation_pattern.search(path.read_text(encoding="utf-8"))
    ]
    require(
        not cancellation_matches,
        "stock selected source unexpectedly gained cancellation vocabulary: "
        + ", ".join(cancellation_matches),
    )

    return {
        "crate_closure_algorithm": (
            "sha256-length-prefixed-path-byte-length-file-sha256-v1"
        ),
        "source_closure_algorithm": (
            "sha256-of-canonical-json-over-full-crate-closures-v1"
        ),
        "source_closure_sha256": combined,
        "crate_closures": closures,
        "audited_source_set_sha256": source_set_hash(findings),
        "audited_files": [finding["path"] for finding in findings],
        "stock_facts": {
            "x86_spicy_scratch_declares_zero_bytes": True,
            "x86_private_gemm_owns_persistent_tls_vec": True,
            "x86_private_gemm_has_reentrant_vec_fallback": True,
            "bunch_kaufman_accepts_caller_memstack": True,
            "full_pivot_seq_path_uses_caller_memstack": True,
            "full_pivot_parallel_path_has_unowned_vec": True,
            "dyn_stack_has_fallible_allocator_entry": True,
            "selected_factor_and_solve_paths_have_cancellation_vocabulary": False,
        },
    }


def target_witnesses(plan: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for target in plan["targets"]:
        records.append(
            {
                **target,
                "candidate_build": Status.MISSING,
                "two_factor_execution": Status.NOT_REACHED,
                "allocation_trace": Status.NOT_REACHED,
                "n_minus_one_control": Status.NOT_REACHED,
                "cancellation_work_unit_bound": Status.NOT_REACHED,
                "qualified_host_ack_latency": Status.MISSING,
                "prior_state_and_cleanup": Status.NOT_REACHED,
                "reason": (
                    "No exact candidate binding exists; target execution and "
                    "qualified-host observation would otherwise be candidate-free."
                ),
            }
        )
    return records


def build_gates(
    profile_digest: str,
    source_audit: dict[str, Any],
    binding: dict[str, Any],
    witnesses: list[dict[str, Any]],
) -> list[Gate]:
    source_digest = source_audit["source_closure_sha256"]
    target_names = tuple(record["target"] for record in witnesses)
    return [
        Gate(
            "mechanical_profile_projection",
            "Mechanical candidate-independent profile projection",
            Status.PASS,
            "accepted mixed direct-faer profile",
            "The allowlisted rule fields are canonicalized and hashed before any candidate observation.",
            (profile_digest,),
        ),
        Gate(
            "stock_source_closure",
            "Exact stock faer/private-gemm/dyn-stack source closure",
            Status.PASS,
            "captured direct-faer source identities",
            "All complete crate closures and the selected source surfaces match the accepted direct-faer evidence.",
            (source_digest, source_audit["audited_source_set_sha256"]),
        ),
        Gate(
            "exact_candidate_binding",
            "Exact hash-bound narrow fork",
            Status.MISSING,
            "CandidateExecutionBinding",
            "The binding deliberately contains no fork commit, patch-set digest, per-target source digest, or executable identity.",
            (binding["state"],),
        ),
        Gate(
            "two_factor_execution",
            "Maximum projected-B and coarse-P_top execution",
            Status.NOT_REACHED,
            "immutable two-factor plan",
            "Candidate execution cannot begin before one exact binding freezes the implementation being observed.",
            (
                "block:M3-HERMITE-10K-level-0-coarse-000:qtaq_lower",
                "block:M2-TH3-1K-level-0-coarse-000:p_top_row_major",
            ),
        ),
        Gate(
            "allocation_closure",
            "ExecutionLease allocation and temporary-storage closure",
            Status.NOT_REACHED,
            "caller-owned exact grant",
            "Stock x86 private-gemm still retains a TLS Vec and declares zero scratch; no fork exists to route it or the selected dyn-stack paths through a lease.",
            (source_digest,),
        ),
        Gate(
            "n_minus_one",
            "Deterministic exact N-minus-one denial",
            Status.NOT_REACHED,
            "two-factor exact resource schedule",
            "There is no candidate preflight calculation to challenge with N-1 before permit acquisition, allocation, and backend entry.",
            (),
        ),
        Gate(
            "bounded_cancellation",
            "Bounded pivot, panel, packing, macro-kernel, and solve cancellation",
            Status.NOT_REACHED,
            "fork checkpoint manifest plus executable controls",
            "The selected stock paths contain no cancellation vocabulary; no fallible checkpoint implementation or maximum unpolled work-unit record exists.",
            (source_audit["audited_source_set_sha256"],),
        ),
        Gate(
            "target_closure",
            "Four tier-one target and qualified-host witnesses",
            Status.MISSING,
            "non-compensating target matrix",
            "Every target lacks a bound candidate build and qualified-host acknowledgment-latency witness.",
            target_names,
        ),
        Gate(
            "atomicity_cleanup",
            "Prior-state preservation, zero publication, and cleanup",
            Status.NOT_REACHED,
            "transactional factor/solve publication",
            "No executable factor or solve attempt exists from which to observe cancellation, cleanup, and prior-state reuse.",
            (),
        ),
    ]


def choose_disposition(
    gates: list[Gate], witnesses: list[dict[str, Any]]
) -> Disposition:
    if any(gate.status is Status.REJECTED for gate in gates):
        return Disposition.REJECTED
    if all(gate.status is Status.PASS for gate in gates) and all(
        all(
            record[field] is Status.PASS
            for field in (
                "candidate_build",
                "two_factor_execution",
                "allocation_trace",
                "n_minus_one_control",
                "cancellation_work_unit_bound",
                "qualified_host_ack_latency",
                "prior_state_and_cleanup",
            )
        )
        for record in witnesses
    ):
        return Disposition.FEASIBLE
    return Disposition.UNJUDGED


def report(summary: dict[str, Any]) -> str:
    lines = [
        "# Instrumented in-process faer feasibility probe",
        "",
        "## Disposition",
        "",
        f"**`{summary['disposition']}`.**",
        "",
        summary["disposition_reason"],
        "",
        "## Frozen identities",
        "",
        f"- Projected FactorHealthProfile: `{summary['profile']['sha256']}`.",
        f"- Stock source closure: `{summary['source_audit']['source_closure_sha256']}`.",
        f"- Two-factor plan: `{summary['plan']['sha256']}`.",
        f"- Candidate binding: `{summary['binding']['state']}`.",
        "",
        "## Gates",
        "",
        "| Gate | State | Reason |",
        "| --- | --- | --- |",
    ]
    for gate in summary["gates"]:
        escaped_reason = gate["reason"].replace("|", "\\|")
        lines.append(
            f"| {gate['title']} | `{gate['status']}` | "
            f"{escaped_reason} |"
        )
    lines.extend(
        [
            "",
            "## Target witnesses",
            "",
            "| Target | Build | Factor run | Allocation | N-1 | Cancellation | Host latency |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for target in summary["targets"]:
        lines.append(
            f"| `{target['target']}` | `{target['candidate_build']}` | "
            f"`{target['two_factor_execution']}` | `{target['allocation_trace']}` | "
            f"`{target['n_minus_one_control']}` | "
            f"`{target['cancellation_work_unit_bound']}` | "
            f"`{target['qualified_host_ack_latency']}` |"
        )
    lines.extend(
        [
            "",
            "## What the source audit establishes",
            "",
            "- The accepted rule set can be projected mechanically without carrying the rejected direct candidate identity forward.",
            "- The low-level Bunch-Kaufman and full-pivot paths accept caller-provided matrices, permutations, and dyn-stack scratch.",
            "- The selected x86 matmul path still declares zero scratch while private-gemm owns a persistent TLS `Vec` plus a reentrant `Vec` fallback.",
            "- The selected stock factor, matmul, and solve paths expose no cancellation checkpoint vocabulary.",
            "",
            "## Evidence still required",
            "",
            "- one immutable fork/patch-set identity shared by all target bindings;",
            "- executable allocation traces showing every selected byte charged to one `ExecutionLease` and zero temporary-storage use;",
            "- exact N and N-1 controls before permit acquisition and backend entry;",
            "- measured maximum unpolled pivot, panel, packing, macro-kernel, and solve work units;",
            "- cancellation, prior-state reuse, zero-publication, and cleanup controls on both factors; and",
            "- build identities plus qualified-host acknowledgment-latency evidence on all four tier-one targets.",
            "",
            "Missing evidence is not an evidence-backed rejection. The mechanism-panel qualification remains blocked.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    require(not args.output.exists(), "output path must not already exist")

    combined, combined_digest = verify_combined_profile(
        INPUTS / "combined-factor-health-profile.v1.json"
    )
    projected, projected_digest = project_profile(combined, combined_digest)
    plan_path = INPUTS / "probe-plan.v1.json"
    plan = read_json(plan_path)
    plan_digest = sha256_bytes(canonical_bytes(plan))
    binding = read_json(INPUTS / "fork-binding.v1.json")
    require(
        binding["state"] == "MISSING_EXACT_FORK"
        and binding["binding_id"] is None
        and binding["binding_sha256"] is None,
        "this captured runner only models the preregistered missing-fork state",
    )
    source_audit = audit_sources(args.registry_root)
    witnesses = target_witnesses(plan)
    gates = build_gates(projected_digest, source_audit, binding, witnesses)
    disposition = choose_disposition(gates, witnesses)
    require(
        disposition is Disposition.UNJUDGED,
        "captured missing-fork evidence must remain unjudged",
    )

    summary = {
        "schema": "rapidrbf-instrumented-faer-feasibility-evidence-v1",
        "question": (
            "Can one exact hash-bound instrumented in-process faer fork close "
            "allocation and cancellation on two factors and four targets?"
        ),
        "disposition": disposition,
        "disposition_reason": (
            "The candidate-independent profile and exact stock source facts "
            "are frozen, but no exact fork, executable two-factor control, or "
            "qualified-host target witness exists. The current evidence "
            "therefore supports neither feasibility nor rejection."
        ),
        "profile": {
            "origin_sha256": combined_digest,
            "sha256": projected_digest,
            "projection_algorithm": projected["projection"]["algorithm"],
        },
        "plan": {
            "sha256": plan_digest,
            "factor_count": len(plan["factors"]),
            "target_count": len(plan["targets"]),
            "factors": plan["factors"],
        },
        "binding": binding,
        "source_audit": source_audit,
        "gates": [asdict(gate) for gate in gates],
        "targets": witnesses,
        "backend_calls": 0,
        "published_validated_factors": 0,
        "published_solved_corrections": 0,
        "candidate_observations_used_to_set_profile": False,
    }

    args.output.mkdir(parents=True)
    (args.output / "factor-health-profile.projected.json").write_bytes(
        canonical_bytes(projected) + b"\n"
    )
    (args.output / "observed-summary.json").write_bytes(
        json.dumps(summary, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    (args.output / "observed-results.md").write_text(
        report(summary),
        encoding="utf-8",
        newline="\n",
    )
    print(args.output / "observed-summary.json")
    print(args.output / "observed-results.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
