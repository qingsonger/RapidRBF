#!/usr/bin/env python3
"""Build the executable oracle index from the reviewed compatibility items."""

from __future__ import annotations

import json
import pathlib
from typing import Any


THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OMP_THREAD_LIMIT": "1",
    "MKL_NUM_THREADS": "1",
    "MKL_DYNAMIC": "FALSE",
    "MKL_CBWR": "COMPATIBLE",
}
LEGACY_LAYOUT = {
    "os": "windows",
    "architecture": "x86_64",
    "byte_order": "little",
    "size_t_bytes": 8,
    "eigen_index_bytes": 8,
    "matrix_storage": "Eigen dynamic row-major raw storage",
}


def workflow_argv(scenario_id: str) -> list[str]:
    return [
        "${PYTHON}",
        "${REPO}/tools/polatory_oracle/workflows.py",
        scenario_id,
        "--repo-root",
        "${REPO}",
        "--polatory-root",
        "${POLATORY_ROOT}",
        "--work",
        "${WORK}",
    ]


def scenario(
    scenario_id: str,
    *,
    role: str,
    surface: str,
    timeout: int,
    covers: list[str] | None = None,
    relates_to: list[str] | None = None,
    authority: str = "canonical",
    argv: list[str] | None = None,
    seed: Any = None,
    seed_policy: str = "No random seed is exposed by the selected operations.",
    legacy: bool = False,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": scenario_id,
        "role": role,
        "authority": authority,
        "surface": surface,
        "argv": argv or workflow_argv(scenario_id),
        "cwd": ".",
        "env": THREAD_ENV,
        "timeout_seconds": timeout,
        "configured_threads": {
            "OMP_NUM_THREADS": 1,
            "OMP_THREAD_LIMIT": 1,
            "MKL_NUM_THREADS": 1,
        },
        "seed": seed,
        "seed_policy": seed_policy,
        "expected": {
            "terminal_status": "exited",
            "exit_code": 0,
        },
        "outputs": [
            {
                "path": "evidence.json",
                "required": True,
                "replay_compare": True,
            },
            {
                "path": "resources.json",
                "required": True,
                "replay_compare": False,
            },
        ],
        "stdout_replay_compare": True,
        "stderr_replay_compare": True,
        "coverage_authority": "scenario_role_and_manifest_mapping",
        "normative_fields": [
            "scenario structure",
            "terminal status and exit category",
            "raw evidence bytes selected by the downstream operation contract",
        ],
        "non_normative_fields": [
            "wall time",
            "working-set and private-byte samples",
            "thread scheduling",
            "exact solver or optimizer trajectory",
            "exact text formatting unless a downstream contract selects a semantic field",
        ],
        "notes": notes or [],
    }
    if role == "accepted_surface":
        result["covers"] = covers or []
    else:
        result["relates_to"] = relates_to or []
    if legacy:
        result["legacy_layout"] = LEGACY_LAYOUT
    return result


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    compatibility_path = (
        repo_root / "oracle" / "manifests" / "compatibility-items.json"
    )
    output_path = repo_root / "oracle" / "manifests" / "oracle-index.json"
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    accepted_coverage: dict[str, list[str]] = {}
    for item in compatibility["items"]:
        for scenario_id in item.get("scenario_ids", []):
            accepted_coverage.setdefault(scenario_id, []).append(item["id"])

    accepted_specs = [
        ("build-identity", "build_environment", 120),
        ("cpp-probe", "instrumented_cpp_diagnostic", 120),
        ("cli-command-contracts", "public_cli", 180),
        ("cli-fit-evaluate", "public_cli", 300),
        ("fit-modes", "public_cli", 300),
        ("cli-kriging", "public_cli", 300),
        ("cli-point-cloud", "public_cli", 180),
        ("cli-geometry", "public_cli", 300),
        ("scale-input-ladder", "benchmark_workload", 600),
        ("legacy-matrix", "legacy_artifact", 600),
        ("python-interface-inventory", "python_source_inventory", 120),
    ]
    scenarios: list[dict[str, Any]] = []
    for scenario_id, surface, timeout in accepted_specs:
        kwargs: dict[str, Any] = {}
        if scenario_id == "cpp-probe":
            kwargs["argv"] = [
                *workflow_argv(scenario_id),
                "--probe",
                "${PROBE}",
            ]
            kwargs["notes"] = [
                "The probe output labels itself diagnostic evidence.",
                "Only the machine-readable valid-input selector in evidence.json feeds accepted-surface decisions; replay of the complete stream detects evidence drift but does not promote diagnostic bytes to compatibility truth.",
            ]
        elif scenario_id == "scale-input-ladder":
            kwargs["seed"] = {"training_points": 0, "prediction_points": 1}
            kwargs["seed_policy"] = (
                "The frozen upstream generator receives literal seeds 0 and 1; "
                "content hashes, not seed identity alone, define each corpus."
            )
            kwargs["notes"] = [
                "This scenario freezes the workload ladder and a 1k executable anchor.",
                "It does not claim that the deferred million-scale fit/evaluation release gate passes.",
            ]
        elif scenario_id == "legacy-matrix":
            kwargs["legacy"] = True
            kwargs["notes"] = [
                "Only valid Model and Interpolant artifacts are migration inputs.",
                "VariogramSet files are differential-only evidence and RapidRBF never writes the native format.",
            ]
        elif scenario_id == "python-interface-inventory":
            kwargs["notes"] = [
                "This accepted item is the source-bound workflow and logical array-shape prerequisite, not an executable Python-extension behavior oracle or exact signature/import-name contract.",
                "Runtime buildability and workflow execution remain unestablished; build failures are held in a separate research-only scenario.",
            ]
        scenarios.append(
            scenario(
                scenario_id,
                role="accepted_surface",
                surface=surface,
                timeout=timeout,
                covers=accepted_coverage.get(scenario_id, []),
                **kwargs,
            )
        )

    scenarios.extend(
        [
            scenario(
                "unit-smoke",
                role="provenance_only",
                surface="upstream_unit_tests",
                timeout=360,
                relates_to=[
                    "stable.numerical-convergence-outcomes",
                    "internal.backend-identities",
                ],
                notes=[
                    "A selected source-suite smoke run is retained as provenance; it does not establish a RapidRBF acceptance threshold."
                ],
            ),
            scenario(
                "legacy-corruption",
                role="research_only",
                surface="legacy_artifact",
                timeout=180,
                relates_to=[
                    "legacy.model-interpolant",
                    "change.invalid-unsafe-inputs",
                ],
                legacy=True,
                notes=[
                    "Malformed artifacts are bounded diagnostic inputs, not accepted Polatory behavior.",
                    "The unbounded-allocation case is hashed but never loaded.",
                ],
            ),
            scenario(
                "defect-inequality-active-set",
                role="research_only",
                surface="public_cli",
                timeout=300,
                relates_to=[
                    "stable.fit-modes",
                    "change.invalid-unsafe-inputs",
                ],
                notes=[
                    "Suspected defect on valid input; reproduction does not adjudicate compatibility."
                ],
            ),
            scenario(
                "defect-zero-rhs",
                role="research_only",
                surface="public_cli",
                timeout=300,
                relates_to=[
                    "stable.numerical-convergence-outcomes",
                    "change.invalid-unsafe-inputs",
                ],
                notes=[
                    "The suspected internal NaN basis is not exposed by the observed public early-return outcome."
                ],
            ),
            scenario(
                "defect-normal-score-small-inputs",
                role="research_only",
                surface="public_cli",
                timeout=180,
                relates_to=[
                    "stable.kriging-variogram",
                    "change.invalid-unsafe-inputs",
                ],
            ),
            scenario(
                "defect-multi-radius-normals",
                role="research_only",
                surface="public_cli",
                timeout=180,
                relates_to=[
                    "stable.point-cloud-sdf",
                    "change.invalid-unsafe-inputs",
                ],
            ),
            scenario(
                "defect-pathological-sdf",
                role="research_only",
                surface="public_cli",
                timeout=180,
                relates_to=[
                    "stable.point-cloud-sdf",
                    "change.invalid-unsafe-inputs",
                ],
            ),
            scenario(
                "python-build",
                role="research_only",
                authority="instrumented",
                surface="python_build_reproduction",
                timeout=120,
                relates_to=["migration.python"],
                notes=[
                    "The frozen build failures are environment-specific diagnostic observations and do not cover the accepted Python migration surface.",
                    "The static SdfDataGenerator mismatch was not reached dynamically.",
                ],
            ),
        ]
    )

    actual_accepted = {
        scenario_value["id"]
        for scenario_value in scenarios
        if scenario_value["role"] == "accepted_surface"
    }
    if actual_accepted != set(accepted_coverage):
        raise RuntimeError(
            "accepted scenario definitions differ from compatibility coverage: "
            f"defined={sorted(actual_accepted)}, "
            f"declared={sorted(accepted_coverage)}"
        )
    index = {
        "schema_version": "1.0.0",
        "id": "polatory-4a30beb-windows-x86_64-behavior-oracle",
        "source_issue": "https://github.com/qingsonger/RapidRBF/issues/6",
        "compatibility_manifest_issue": "https://github.com/qingsonger/RapidRBF/issues/5",
        "polatory": {
            "repository": "https://github.com/polatory/polatory.git",
            "commit": "4a30beb08053fb339ce899e255be4b6d3f74aa0c",
            "cli_sha256": "95cd325f727e6f56d1656feb52672a37a5fc655132a232cbb6976f031ffccfe9",
            "binary_distribution": "not_redistributed",
        },
        "interpretation": {
            "accepted_surface": "May cover required manifest items through its declared selector or accepted inventory; the role does not promote every captured byte to compatibility truth.",
            "research_only": "Preserves suspected defects or unsafe legacy observations and can never satisfy required compatibility coverage.",
            "provenance_only": "Preserves build or test context and can never satisfy required compatibility coverage.",
            "role_enforcement_scope": "Scenario roles and covers/relates_to mappings govern coverage authority. Full-stream replay is an evidence-integrity and drift check; downstream contracts select accepted semantic fields.",
            "numeric_tolerance_applied": False,
        },
        "compatibility_items": compatibility["items"],
        "scenarios": scenarios,
    }
    output_path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
