#!/usr/bin/env python3
"""Derive the issue-48 witness subset from immutable accepted evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "inputs" / "issue47-witness-subset.v1.json"
ISSUE47_ARCHIVE_SHA256 = (
    "b38870fedb17886c105d9162ac79ed81661a4a1f8428d6a80f627ddaf37e96a1"
)
ISSUE47_REFERENCE_SHA256 = (
    "6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a"
)
ISSUE41_PLAN_SHA256 = (
    "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce"
)
ISSUE45_EVIDENCE_SHA256 = (
    "b5dbe24ace553df3d390673feef5cad1912bdc8130d97875739f13e8512587d2"
)
SELECTED_ORDINALS = (0, 36, 69, 72, 106, 150)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(payload)


def find_zip_member(archive: zipfile.ZipFile, suffix: str, contains: str = "") -> str:
    matches = [
        name
        for name in archive.namelist()
        if name.endswith(suffix) and contains in name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one archive member ending {suffix!r} "
            f"and containing {contains!r}; found {matches}"
        )
    return matches[0]


def read_zip_json(archive: zipfile.ZipFile, member: str) -> tuple[Any, bytes]:
    payload = archive.read(member)
    return json.loads(payload), payload


def mpfr_hex_to_float(text: str) -> float:
    """Parse MPFR base-16 scientific notation such as 1.f@-9."""

    sign = -1.0 if text.startswith("-") else 1.0
    unsigned = text.lstrip("+-")
    if "@" in unsigned:
        significand, exponent16 = unsigned.split("@", 1)
        exponent2 = 4 * int(exponent16)
    else:
        significand = unsigned
        exponent2 = 0
    return sign * float.fromhex(f"0x{significand}p{exponent2}")


def dyadic_to_float(text: str) -> float:
    """Parse exact integer-times-power-of-two notation such as abcp-256."""

    mantissa_hex, exponent2 = text.split("p", 1)
    mantissa = int(mantissa_hex, 16)
    if mantissa == 0:
        return 0.0
    bits = mantissa.bit_length()
    shift = max(0, bits - 53)
    top = mantissa >> shift
    return math.ldexp(float(top), int(exponent2) + shift)


def compact_judgment(judgment: dict[str, Any]) -> dict[str, Any]:
    distance_lower = dyadic_to_float(judgment["distance_lower_exact_hex"])
    distance_upper = dyadic_to_float(judgment["distance_upper_exact_hex"])
    pass_limit = dyadic_to_float(judgment["pass_limit_exact_hex"])
    fail_limit = dyadic_to_float(judgment["fail_limit_exact_hex"])
    scale_lower = mpfr_hex_to_float(judgment["scale_lower_mpfr_hex"])
    scale_upper = mpfr_hex_to_float(judgment["scale_upper_mpfr_hex"])
    return {
        "family": judgment["family"],
        "status": judgment["status"],
        "rhs_sha256": judgment["rhs_sha256"],
        "relative_distance_lower": distance_lower / scale_upper,
        "relative_distance_upper": distance_upper / scale_lower,
        "threshold_ratio_lower": distance_lower / fail_limit,
        "threshold_ratio_upper": distance_upper / pass_limit,
        "non_finite_candidate": judgment["non_finite_candidate"],
    }


def compact_reference(rhs: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": rhs["family"],
        "rhs_sha256": rhs["rhs_sha256"],
        "status": rhs["status"],
        "precision_bits": rhs["precision_bits"],
        "q_upper": mpfr_hex_to_float(rhs["q_upper_hex"]),
        "rho_upper": mpfr_hex_to_float(rhs["rho_upper_hex"]),
        "relative_radius_upper": mpfr_hex_to_float(
            rhs["relative_radius_upper_hex"]
        ),
        "solution_threshold": mpfr_hex_to_float(rhs["solution_threshold_hex"]),
        "reference_quality_limit": mpfr_hex_to_float(
            rhs["reference_quality_limit_hex"]
        ),
        "center_sha256": rhs["center_sha256"],
        "refinement_correction_relative_inf": rhs[
            "refinement_correction_relative_inf"
        ],
    }


def compact_candidate_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "ordinal": source["ordinal"],
        "factor_source_id": source["factor_source_id"],
        "workload_id": source["workload_id"],
        "block_id": source["block_id"],
        "dimension": source["dimension"],
        "role": source["role"],
        "source_sha256": source["source_sha256"],
        "status": source["status"],
        "factor_fingerprint": source["factor_fingerprint"],
        "reconstruction_relative_inf": source["reconstruction_relative_inf"],
        "reconstruction_threshold": source["reconstruction_threshold"],
        "maximum_backward_error": source["maximum_backward_error"],
        "backward_threshold": source["backward_threshold"],
        "maximum_declared_solution_relative_inf_diagnostic": source[
            "maximum_declared_solution_relative_inf_diagnostic"
        ],
        "unchanged_solution_threshold": source["unchanged_solution_threshold"],
        "pre_post_solutions_bit_exact": source[
            "pre_post_solutions_bit_exact"
        ],
        "solution_judgments": [
            compact_judgment(item) for item in source["solution_judgments"]
        ],
        "reload_solution_judgments": [
            compact_judgment(item)
            for item in source["reload_solution_judgments"]
        ],
    }


def compact_issue45_observation(observation: dict[str, Any]) -> dict[str, Any]:
    routes: dict[str, Any] = {}
    for key in (
        "candidate_lblt",
        "full_pivot_lu",
        "symmetric_max_equilibrated_lblt",
    ):
        route = observation[key]
        routes[key] = {
            "raw_maximum_declared_solution_relative_inf": route["metrics"][
                "maximum_declared_solution_relative_inf"
            ],
            "raw_maximum_backward_error": route["metrics"][
                "maximum_backward_error"
            ],
            "double_double_refined_maximum_declared_solution_relative_inf": route[
                "double_double_refined"
            ]["maximum_declared_solution_relative_inf"],
            "double_double_refined_maximum_backward_error": route[
                "double_double_refined"
            ]["maximum_backward_error"],
            "refinement_steps": route["double_double_refined"]["steps"],
            "refinement_correction_relative_inf_history": route[
                "double_double_refined"
            ]["correction_relative_inf_history"],
        }
    return {
        "ordinal": observation["ordinal"],
        "category": observation["category"],
        "solution_threshold": observation["archived"]["solution_threshold"],
        "directional_forward_amplification": observation["frozen_rhs"][
            "directional_forward_amplification"
        ],
        "lblt_full_pivot_lu_relative_agreement": observation[
            "independent_reference"
        ]["lblt_full_pivot_lu_relative_agreement"],
        "routes": routes,
    }


def load_json(path: Path, expected_sha256: str, label: str) -> Any:
    observed = sha256_file(path)
    if observed != expected_sha256:
        raise RuntimeError(
            f"{label} SHA-256 mismatch: expected {expected_sha256}, got {observed}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("issue47_archive", type=Path)
    parser.add_argument("issue41_plan", type=Path)
    parser.add_argument("issue45_evidence", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    archive_sha256 = sha256_file(args.issue47_archive)
    if archive_sha256 != ISSUE47_ARCHIVE_SHA256:
        raise RuntimeError(
            "issue-47 archive SHA-256 mismatch: "
            f"expected {ISSUE47_ARCHIVE_SHA256}, got {archive_sha256}"
        )
    plan = load_json(args.issue41_plan, ISSUE41_PLAN_SHA256, "issue-41 plan")
    issue45 = load_json(
        args.issue45_evidence, ISSUE45_EVIDENCE_SHA256, "issue-45 evidence"
    )

    with zipfile.ZipFile(args.issue47_archive) as archive:
        cohort_member = find_zip_member(archive, "cohort-summary.json")
        reference_member = find_zip_member(
            archive, "reference-manifest.v1.json"
        )
        candidate_members = sorted(
            name
            for name in archive.namelist()
            if "/qualification/candidate-" in name
            and name.endswith("-workers.json")
        )
        if len(candidate_members) != 12:
            raise RuntimeError(
                f"expected 12 candidate observations; found {len(candidate_members)}"
            )
        cohort, cohort_payload = read_zip_json(archive, cohort_member)
        reference, reference_payload = read_zip_json(archive, reference_member)
        if sha256_bytes(reference_payload) != ISSUE47_REFERENCE_SHA256:
            raise RuntimeError("issue-47 reference manifest identity mismatch")
        candidates = [
            read_zip_json(archive, member)[0] for member in candidate_members
        ]

    if cohort["disposition"] != "NOT_ADMITTED_DIAGNOSTIC_ONLY":
        raise RuntimeError("unexpected issue-47 disposition")
    if reference["certified_references"] != 537:
        raise RuntimeError("unexpected certified-reference count")
    if reference["indeterminate_references"] != 0:
        raise RuntimeError("issue-47 reference contains INDETERMINATE entries")

    plan_sources = {item["ordinal"]: item for item in plan["factor_sources"]}
    observations: dict[int, list[dict[str, Any]]] = {
        ordinal: [] for ordinal in SELECTED_ORDINALS
    }
    lanes: list[dict[str, Any]] = []
    for candidate in candidates:
        lane = {
            "lane_id": candidate["lane_id"],
            "target": candidate["target"],
            "workers": candidate["lane"]["configured_workers"],
            "candidate_file_disposition": candidate["disposition"],
        }
        lanes.append(lane)
        sources = {item["ordinal"]: item for item in candidate["factor_sources"]}
        for ordinal in SELECTED_ORDINALS:
            compact = compact_candidate_source(sources[ordinal])
            compact["lane"] = lane
            observations[ordinal].append(compact)

    reference_by_source = {
        entry["source_sha256"]: entry for entry in reference["entries"]
    }
    issue45_by_ordinal = {
        item["ordinal"]: item for item in issue45["observations"]
    }

    witnesses: list[dict[str, Any]] = []
    for ordinal in SELECTED_ORDINALS:
        metadata = plan_sources[ordinal]
        lane_observations = observations[ordinal]
        status_vectors = {
            (
                item["status"],
                tuple(
                    judgment["status"]
                    for judgment in item["solution_judgments"]
                ),
                tuple(
                    judgment["status"]
                    for judgment in item["reload_solution_judgments"]
                ),
            )
            for item in lane_observations
        }
        reference_entry = reference_by_source[metadata["sha256"]]
        witness: dict[str, Any] = {
            "ordinal": ordinal,
            "category": {
                0: "passing projected control",
                36: "M2-TH3 1k failure boundary",
                69: "M2-TH3 smallest-dimension failed and duplicate-source boundary",
                72: "repaired M3-HERMITE 1k pass and rank/pivot boundary",
                106: "M3-HERMITE partial-RHS-family exception",
                150: "M4-GEOMETRY worst frozen-system failure boundary",
            }[ordinal],
            "metadata": {
                key: metadata[key]
                for key in (
                    "factor_source_id",
                    "workload_id",
                    "block_id",
                    "dimension",
                    "expected_rank",
                    "factorization",
                    "role",
                    "sha256",
                    "bytes",
                )
            },
            "reference_entry": {
                "first_ordinal": reference_entry["first_ordinal"],
                "logical_factor_source_ids": reference_entry[
                    "logical_factor_source_ids"
                ],
                "source_sha256": reference_entry["source_sha256"],
                "rhs": [
                    compact_reference(rhs) for rhs in reference_entry["rhs"]
                ],
            },
            "lane_observations": lane_observations,
            "status_vector_identical_across_all_12_observations": (
                len(status_vectors) == 1
            ),
        }
        if ordinal in issue45_by_ordinal:
            witness["accepted_issue45_route_comparison"] = (
                compact_issue45_observation(issue45_by_ordinal[ordinal])
            )
        witnesses.append(witness)

    subset = {
        "schema": "RapidRBF/RepairedProjectedSolveDiagnosisWitnessSubset/v1",
        "derivation": {
            "issue47_archive_sha256": archive_sha256,
            "issue47_cohort_summary_sha256": sha256_bytes(cohort_payload),
            "issue47_reference_manifest_sha256": sha256_bytes(
                reference_payload
            ),
            "issue41_plan_sha256": ISSUE41_PLAN_SHA256,
            "issue45_evidence_sha256": ISSUE45_EVIDENCE_SHA256,
            "selected_ordinals": list(SELECTED_ORDINALS),
            "full_cohort_rerun": False,
            "full_cohort_mutated": False,
        },
        "cohort": {
            "disposition": cohort["disposition"],
            "required_targets": cohort["required_targets"],
            "nonpassing_coordinates": len(cohort["nonpassing_coordinates"]),
            "candidate_binding_sha256": cohort["frozen_authority"][
                "candidate_binding_sha256"
            ],
            "reference_manifest_sha256": ISSUE47_REFERENCE_SHA256,
            "certified_references": reference["certified_references"],
            "indeterminate_references": reference[
                "indeterminate_references"
            ],
            "candidate_inputs_observed_by_reference": reference[
                "candidate_inputs_observed"
            ],
            "lanes": lanes,
        },
        "witnesses": witnesses,
    }
    subset["payload_sha256"] = canonical_sha256(subset)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(subset, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "payload_sha256": subset["payload_sha256"],
                "witnesses": len(witnesses),
                "lane_observations": sum(
                    len(witness["lane_observations"])
                    for witness in witnesses
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"prepare failed: {error}", file=sys.stderr)
        raise
