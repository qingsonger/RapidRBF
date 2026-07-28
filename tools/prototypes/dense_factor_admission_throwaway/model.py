"""Pure fail-closed state model for the throwaway dense-factor admission audit."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any


BUNDLE_SCHEMA = "rapidrbf-factor-admission-bundle-v1"
OUTPUT_SCHEMA = "rapidrbf-factor-admission-disposition-v1"
EXPECTED_CORPUS_SHA256 = (
    "ac282ee95062b4463d2e0a0c0ca83da454660e0e5048fa79ea3a07da280ef26e"
)
EXPECTED_MANIFEST_SHA256 = (
    "b488d8fa726872cf17cfe4f1bb48e08c44de1a1ecf2370a2d08fb59eb7384cbc"
)
EXPECTED_LINEAGE = {
    "wayfinder_ticket": "Admit the canonical dense-factor corpus for mechanism-panel use",
    "dense_replay_commit": "b00160b318d2d1faf27ef6f305960ccadd3061eb",
    "m3_diagnosis_commit": "5be79c562b848d3f8bc020784d6ac9b2d0551fcf",
    "polatory_commit": "4a30beb08053fb339ce899e255be4b6d3f74aa0c",
}
EXPECTED_CANONICAL_RECORDS = {
    "M1-EXP-LOCAL-max-order-fine-canonical",
    "M1-EXP-LOCAL-level0-coarse-canonical",
    "M2-TH3-CPD-max-order-fine-canonical",
    "M2-TH3-CPD-level0-coarse-canonical",
    "M3-HERMITE-COMPOSITE-max-order-fine-canonical",
    "M3-HERMITE-COMPOSITE-level0-coarse-canonical",
    "M4-GEOMETRY-FAILURE-max-order-fine-canonical",
    "M4-GEOMETRY-FAILURE-level0-coarse-canonical",
}
EXPECTED_EXCLUDED_RECORDS = {
    "M3-HERMITE-COMPOSITE-max-order-fine-frozen-literal",
    "M3-HERMITE-COMPOSITE-level0-coarse-frozen-literal",
}
REQUIRED_GATE_IDS = (
    "semantic_rank_certificates",
    "factor_health_profile",
    "independent_evaluator_and_publication",
    "resource_and_thread_lease",
    "atomic_factor_pack_reload_reuse",
)
EXPECTED_PREREQUISITE_STATES = {
    "corpus_identity": "PASS",
    "canonical_m3_representation": "PASS",
    "panel_hierarchy_coverage": "EVIDENCE_MISSING",
}
EXPECTED_GATE_STATES = {
    "semantic_rank_certificates": "EVIDENCE_MISSING",
    "factor_health_profile": "EVIDENCE_MISSING",
    "independent_evaluator_and_publication": "EVIDENCE_MISSING",
    "resource_and_thread_lease": "EVIDENCE_MISSING",
    "atomic_factor_pack_reload_reuse": "PARTIAL",
}
EXPECTED_ALLOWED_DIAGNOSTICS = {
    "hash-verified canonical matrices and right-hand sides may be force-replayed in fresh private workers",
    "pivots, factor reconstruction, reduced/full residual diagnostics, trajectories, work, and failure observations may be collected",
    "nalgebra and exact Windows oneMKL may run only as sidecar diagnostic comparators",
    "identity/no-factor execution may run only as the registered M1-M4 1k diagnostic ablation",
}
EXPECTED_FORBIDDEN_USES = {
    "using either frozen-literal M3 record as a factor input or expected semantic result",
    "publishing or caching a ValidatedFactor or certified correction",
    "declaring Converged, selecting rank/restart/preconditioner settings, or advancing a mechanism survivor",
    "naming faer, nalgebra, or oneMKL as an adopted production factor backend",
    "using representative-block observations as 1k/10k hierarchy, 100k storage, or release evidence",
}
PERSISTENCE_ONLY_GAP = "PERSISTENCE_ONLY_GAP"
PASS = "PASS"
NON_PASS_STATES = {
    "EVIDENCE_MISSING",
    "PARTIAL",
    "REJECTED",
    "INDETERMINATE",
    PERSISTENCE_ONLY_GAP,
}
UNSAFE_REPLAY_STATES = {"REJECTED", "INDETERMINATE"}


def load_bundle(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid admission bundle JSON: {error}") from error
    validate_bundle(bundle)
    return bundle, digest


def validate_bundle(bundle: dict[str, Any]) -> None:
    errors: list[str] = []
    expected_top_level = {
        "schema",
        "authority",
        "lineage",
        "corpus",
        "scope",
        "prerequisites",
        "gates",
        "backend_roles",
        "diagnostic_contract",
        "successor_questions",
    }
    if set(bundle) != expected_top_level:
        errors.append("bundle fields differ from the negative-disposition schema")
    if bundle.get("schema") != BUNDLE_SCHEMA:
        errors.append(f"schema must be {BUNDLE_SCHEMA}")
    if bundle.get("authority") != "negative-disposition-only":
        errors.append("authority must be negative-disposition-only")
    if bundle.get("lineage") != EXPECTED_LINEAGE:
        errors.append("lineage differs from the immutable upstream decisions")

    corpus = bundle.get("corpus", {})
    if corpus.get("sha256") != EXPECTED_CORPUS_SHA256:
        errors.append("corpus digest differs from the locked Stage 0 corpus")
    if corpus.get("raw_manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        errors.append("raw manifest digest differs from the locked Stage 0 corpus")
    if corpus.get("schema") != "rapidrbf-dense-factor-corpus-v1":
        errors.append("corpus schema differs from rapidrbf-dense-factor-corpus-v1")
    if corpus.get("lock_schema") != "rapidrbf-dense-factor-corpus-lock-v2":
        errors.append("corpus lock schema differs from the immutable v2 lock")
    if corpus.get("verified_file_count") != 191:
        errors.append("verified file count differs from the locked corpus")
    if corpus.get("referenced_payload_count") != 190:
        errors.append("payload count differs from the locked corpus")
    canonical = set(corpus.get("canonical_record_ids", []))
    excluded = set(corpus.get("excluded_defect_fixture_ids", []))
    if canonical != EXPECTED_CANONICAL_RECORDS:
        errors.append("canonical record set is not the locked eight-record set")
    if excluded != EXPECTED_EXCLUDED_RECORDS:
        errors.append("excluded record set is not the two frozen-literal M3 fixtures")
    if canonical & excluded:
        errors.append("canonical and excluded record sets overlap")

    scope = bundle.get("scope", {})
    if scope.get("captured_scale") != "10k-derived":
        errors.append("scope must remain 10k-derived")
    if scope.get("coverage") != "representative local/coarse blocks only":
        errors.append("scope must remain representative-block-only")

    prerequisite_list = bundle.get("prerequisites", [])
    prerequisites = {
        item.get("id"): item for item in prerequisite_list
    }
    if (
        len(prerequisite_list) != len(EXPECTED_PREREQUISITE_STATES)
        or set(prerequisites) != set(EXPECTED_PREREQUISITE_STATES)
    ):
        errors.append("prerequisite set differs from the fixed disposition")
    for prerequisite_id, expected_state in EXPECTED_PREREQUISITE_STATES.items():
        if prerequisites.get(prerequisite_id, {}).get("state") != expected_state:
            errors.append(
                f"{prerequisite_id} must remain {expected_state} in this bundle"
            )

    gate_list = bundle.get("gates", [])
    gates = {item.get("id"): item for item in gate_list}
    if len(gate_list) != len(REQUIRED_GATE_IDS) or set(gates) != set(REQUIRED_GATE_IDS):
        errors.append("gate set differs from the five ticket gates")
    for gate_id, gate in gates.items():
        state = gate.get("state")
        if state != PASS and state not in NON_PASS_STATES:
            errors.append(f"{gate_id} has unsupported state {state!r}")
        expected_state = EXPECTED_GATE_STATES.get(gate_id)
        if state != expected_state:
            errors.append(f"{gate_id} must remain {expected_state} in this bundle")

    roles = bundle.get("backend_roles", {})
    if roles.get("qualification_candidate") != "faer 0.24.4":
        errors.append("faer 0.24.4 must remain the sole qualification candidate")
    if set(roles.get("diagnostic_comparators", [])) != {
        "nalgebra 0.35.0",
        "oneMKL 2023.0.0#2 Windows LP64 sequential",
    }:
        errors.append("diagnostic comparator set differs from the locked decision")
    if roles.get("production_selection") is not None:
        errors.append("negative disposition cannot carry a production selection")

    contract = bundle.get("diagnostic_contract", {})
    allowed = contract.get("allowed", [])
    forbidden = contract.get("forbidden", [])
    if (
        len(allowed) != len(EXPECTED_ALLOWED_DIAGNOSTICS)
        or set(allowed) != EXPECTED_ALLOWED_DIAGNOSTICS
    ):
        errors.append("diagnostic allowlist differs from the fail-closed contract")
    if (
        len(forbidden) != len(EXPECTED_FORBIDDEN_USES)
        or set(forbidden) != EXPECTED_FORBIDDEN_USES
    ):
        errors.append("forbidden-use list differs from the fail-closed contract")
    if contract.get("bounded_factor_free_fallback") != {
        "name": "identity/no-factor",
        "scope": "registered M1-M4 1k diagnostics only",
        "authority": "DIAGNOSTIC_ONLY",
        "production_factor_implication": False,
    }:
        errors.append("factor-free fallback differs from the locked diagnostic ablation")
    bounded_recompute = contract.get("bounded_recompute_fallback", {})
    if bounded_recompute.get("state") != "NOT_AVAILABLE":
        errors.append("bounded recompute must remain unavailable in this bundle")

    if errors:
        raise ValueError("; ".join(errors))


def evaluate_bundle(bundle: dict[str, Any], bundle_sha256: str) -> dict[str, Any]:
    validate_bundle(bundle)
    prerequisites = {item["id"]: item for item in bundle["prerequisites"]}
    gates = {item["id"]: item for item in bundle["gates"]}

    missing_prerequisites = [
        item
        for item in bundle["prerequisites"]
        if item["state"] != PASS
    ]
    unclosed_gates = [
        gates[gate_id]
        for gate_id in REQUIRED_GATE_IDS
        if gates[gate_id]["state"] != PASS
    ]

    identity_bound = prerequisites["corpus_identity"]["state"] == PASS
    canonical_bound = (
        prerequisites["canonical_m3_representation"]["state"] == PASS
    )
    hierarchy_complete = prerequisites["panel_hierarchy_coverage"]["state"] == PASS
    all_gates_closed = not unclosed_gates

    admitted = (
        bundle["authority"] == "positive-admission"
        and identity_bound
        and canonical_bound
        and hierarchy_complete
        and all_gates_closed
    )
    unsafe_replay_states = {
        item["state"]
        for item in [*bundle["prerequisites"], *bundle["gates"]]
        if item["state"] in UNSAFE_REPLAY_STATES
    }
    bounded_recompute_ready = (
        identity_bound
        and canonical_bound
        and hierarchy_complete
        and all(
            gates[gate_id]["state"] == PASS
            for gate_id in (
                "semantic_rank_certificates",
                "factor_health_profile",
                "independent_evaluator_and_publication",
                "resource_and_thread_lease",
            )
        )
        and gates["atomic_factor_pack_reload_reuse"]["state"]
        == PERSISTENCE_ONLY_GAP
        and bundle["diagnostic_contract"]["bounded_recompute_fallback"]["state"]
        == "AVAILABLE_RUN_SCOPED"
    )
    diagnostic_only_ready = (
        identity_bound
        and canonical_bound
        and not unsafe_replay_states
    )

    if admitted:
        admission_disposition = "ADMITTED"
        mechanism_input_authority = "AUTHORITATIVE"
        downstream_decision_authority = "ENABLED"
        evidence_state = "JUDGED"
    elif diagnostic_only_ready:
        admission_disposition = "NOT_ADMITTED"
        mechanism_input_authority = "DIAGNOSTIC_ONLY"
        downstream_decision_authority = "BLOCKED"
        evidence_state = "EVIDENCE_MISSING"
    else:
        admission_disposition = (
            "REJECTED"
            if "REJECTED" in unsafe_replay_states
            else "INDETERMINATE"
            if "INDETERMINATE" in unsafe_replay_states
            else "REJECTED"
        )
        mechanism_input_authority = "NONE"
        downstream_decision_authority = "BLOCKED"
        evidence_state = admission_disposition

    reasons = [
        item["effect"]
        for item in missing_prerequisites
    ] + [
        item["effect"]
        for item in unclosed_gates
    ]

    return {
        "schema": OUTPUT_SCHEMA,
        "bundle": {
            "schema": bundle["schema"],
            "sha256": bundle_sha256,
            "authority": bundle["authority"],
        },
        "lineage": deepcopy(bundle["lineage"]),
        "corpus": deepcopy(bundle["corpus"]),
        "scope": deepcopy(bundle["scope"]),
        "attempt_evidence_state": "COLLECTED, UNJUDGED",
        "evidence_state": evidence_state,
        "prerequisites": deepcopy(bundle["prerequisites"]),
        "gates": deepcopy(bundle["gates"]),
        "gate_summary": {
            "required_gate_count": len(REQUIRED_GATE_IDS),
            "closed_gate_count": len(REQUIRED_GATE_IDS) - len(unclosed_gates),
            "unclosed_gate_count": len(unclosed_gates),
            "unclosed_gate_ids": [item["id"] for item in unclosed_gates],
            "missing_prerequisite_ids": [
                item["id"] for item in missing_prerequisites
            ],
        },
        "backend_roles": deepcopy(bundle["backend_roles"]),
        "disposition": {
            "admission_disposition": admission_disposition,
            "mechanism_input_authority": mechanism_input_authority,
            "downstream_decision_authority": downstream_decision_authority,
            "bounded_recompute_fallback_ready": bounded_recompute_ready,
            "reasons": reasons,
        },
        "diagnostic_contract": (
            deepcopy(bundle["diagnostic_contract"])
            if diagnostic_only_ready
            else {
                "allowed": [],
                "forbidden": deepcopy(bundle["diagnostic_contract"]["forbidden"]),
                "bounded_factor_free_fallback": {
                    "state": "NOT_AVAILABLE",
                    "reason": "explicit rejection or indeterminacy removes diagnostic input authority",
                },
                "bounded_recompute_fallback": {
                    "state": "NOT_AVAILABLE",
                    "reason": "explicit rejection or indeterminacy removes diagnostic input authority",
                },
            }
        ),
        "successor_questions": deepcopy(bundle["successor_questions"]),
    }


def render_snapshot(path: Path) -> dict[str, Any]:
    bundle, digest = load_bundle(path)
    return evaluate_bundle(bundle, digest)


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"
