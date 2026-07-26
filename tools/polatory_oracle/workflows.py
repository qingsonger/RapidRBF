#!/usr/bin/env python3
"""Run grouped frozen-Polatory observations and emit byte-preserving evidence.

This adapter exists only to make multi-command public workflows replayable.
It does not apply numerical tolerances or decide whether Polatory is correct.
Each child invocation is recorded with logical paths, raw stdout/stderr bytes,
declared output bytes or hashes, and separate non-normative resource samples.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
from typing import Any, Iterable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from oracle import sample_process  # noqa: E402


SCHEMA_VERSION = "1.0.0"
POLATORY_COMMIT = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"
POLATORY_CLI_SHA256 = (
    "95cd325f727e6f56d1656feb52672a37a5fc655132a232cbb6976f031ffccfe9"
)
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OMP_THREAD_LIMIT": "1",
    "MKL_NUM_THREADS": "1",
    "MKL_DYNAMIC": "FALSE",
    "MKL_CBWR": "COMPATIBLE",
}
FAMILIES = (
    "bh2",
    "bh3",
    "th2",
    "th3",
    "cub",
    "exp",
    "gau",
    "gc3",
    "gc5",
    "gc7",
    "gc9",
    "sph",
    "sp3",
    "sp5",
    "sp7",
    "sp9",
)
COMMANDS = (
    "create-model",
    "fit",
    "evaluate",
    "extract-model",
    "show-model",
    "variogram",
    "show-variogram",
    "fit-model-to-variogram",
    "cross-validate",
    "estimate-normals",
    "normals-to-sdf",
    "surface-25d",
    "isosurface",
    "unique",
)
VALUE_FIXTURE = {1: "values-1d.csv", 2: "values-2d.csv", 3: "values-3d.csv"}
GRAD_FIXTURE = {
    1: "gradients-1d.csv",
    2: "gradients-2d.csv",
    3: "gradients-3d.csv",
}
EVAL_FIXTURE = {
    1: "evaluation-points-1d.csv",
    2: "evaluation-points-2d.csv",
    3: "evaluation-points-3d.csv",
}
ANISOTROPY = {
    1: ("1.5",),
    2: ("1", "0.25", "0", "1"),
    3: ("1", "0.2", "0", "0", "1", "0.1", "0", "0", "1"),
}


class WorkflowError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def stream_record(data: bytes) -> dict[str, Any]:
    return {
        "encoding": "base64",
        "size": len(data),
        "sha256": sha256_bytes(data),
        "bytes_base64": base64.b64encode(data).decode("ascii"),
    }


def logical_arg(
    value: str,
    *,
    repo_root: pathlib.Path,
    polatory_root: pathlib.Path,
    work: pathlib.Path,
) -> str:
    candidate = pathlib.Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        exact = {
            (polatory_root / "build" / "cli" / "polatory.exe").resolve(): "${POLATORY_CLI}",
            (polatory_root / "build" / "test" / "Unittest.exe").resolve(): "${POLATORY_TESTS}",
            (polatory_root / "build" / "benchmark" / "points.exe").resolve(): "${POLATORY_POINTS}",
            (polatory_root / "build" / "benchmark" / "predict.exe").resolve(): "${POLATORY_PREDICT}",
        }
        if resolved in exact:
            return exact[resolved]
        for root, token in (
            (work.resolve(), "${WORK}"),
            (repo_root.resolve(), "${REPO}"),
            (polatory_root.resolve(), "${POLATORY_ROOT}"),
        ):
            try:
                suffix = resolved.relative_to(root).as_posix()
            except ValueError:
                continue
            return token if not suffix else f"{token}/{suffix}"
    return value.replace("\\", "/")


def verify_frozen_source(polatory_root: pathlib.Path) -> pathlib.Path:
    commit = subprocess.check_output(
        ["git", "-C", str(polatory_root), "rev-parse", "HEAD"],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()
    if commit != POLATORY_COMMIT:
        raise WorkflowError(f"unexpected Polatory revision: {commit}")
    tracked = subprocess.check_output(
        [
            "git",
            "-C",
            str(polatory_root),
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()
    if tracked:
        raise WorkflowError("Polatory has tracked modifications")
    cli = polatory_root / "build" / "cli" / "polatory.exe"
    if not cli.is_file():
        raise WorkflowError(f"missing frozen CLI: {cli}")
    actual = sha256_file(cli)
    if actual != POLATORY_CLI_SHA256:
        raise WorkflowError(f"unexpected polatory.exe SHA-256: {actual}")
    return cli


class Recorder:
    def __init__(
        self,
        *,
        scenario_id: str,
        repo_root: pathlib.Path,
        polatory_root: pathlib.Path,
        work: pathlib.Path,
    ) -> None:
        self.scenario_id = scenario_id
        self.repo_root = repo_root.resolve()
        self.polatory_root = polatory_root.resolve()
        self.work = work.resolve()
        self.cli = verify_frozen_source(self.polatory_root)
        self.runs: list[dict[str, Any]] = []
        self.resources: list[dict[str, Any]] = []

    def child(
        self,
        run_id: str,
        argv: list[str],
        *,
        outputs: Iterable[tuple[pathlib.Path, str, bool]] = (),
        timeout_seconds: float = 120.0,
        expected_exit_codes: set[int] | None = None,
    ) -> dict[str, Any]:
        if any(run["id"] == run_id for run in self.runs):
            raise WorkflowError(f"duplicate run id: {run_id}")
        environment = dict(os.environ)
        environment.update(THREAD_ENV)
        environment.update(
            {
                "TEMP": str(self.work),
                "TMP": str(self.work),
                "TMPDIR": str(self.work),
            }
        )
        started = time.monotonic()
        process = subprocess.Popen(
            argv,
            cwd=self.work,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        samples: list[dict[str, Any]] = []
        terminal_status = "exited"
        stdout = b""
        stderr = b""
        try:
            while True:
                elapsed = time.monotonic() - started
                samples.append({"elapsed_seconds": elapsed, **sample_process(process.pid)})
                remaining = timeout_seconds - elapsed
                if remaining <= 0:
                    terminal_status = "timeout"
                    process.kill()
                    stdout, stderr = process.communicate()
                    break
                try:
                    stdout, stderr = process.communicate(timeout=min(0.05, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        elapsed = time.monotonic() - started
        exit_code = process.returncode if terminal_status == "exited" else None
        output_records: list[dict[str, Any]] = []
        for path, role, embed in outputs:
            resolved = path.resolve()
            try:
                logical_path = resolved.relative_to(self.work).as_posix()
            except ValueError as error:
                raise WorkflowError(f"output escapes work root: {resolved}") from error
            if not resolved.is_file():
                output_records.append(
                    {"path": f"${{WORK}}/{logical_path}", "role": role, "present": False}
                )
                continue
            data = resolved.read_bytes()
            record = {
                "path": f"${{WORK}}/{logical_path}",
                "role": role,
                "present": True,
                "size": len(data),
                "sha256": sha256_bytes(data),
            }
            if embed:
                record.update(
                    {
                        "encoding": "base64",
                        "bytes_base64": base64.b64encode(data).decode("ascii"),
                    }
                )
            output_records.append(record)
        run = {
            "id": run_id,
            "argv": [
                logical_arg(
                    arg,
                    repo_root=self.repo_root,
                    polatory_root=self.polatory_root,
                    work=self.work,
                )
                for arg in argv
            ],
            "cwd": "${WORK}",
            "environment": {
                **THREAD_ENV,
                "TEMP": "${WORK}",
                "TMP": "${WORK}",
                "TMPDIR": "${WORK}",
            },
            "configured_threads": 1,
            "terminal_status": terminal_status,
            "exit_code": exit_code,
            "timeout_seconds": timeout_seconds,
            "stdout": stream_record(stdout),
            "stderr": stream_record(stderr),
            "outputs": output_records,
        }
        self.runs.append(run)
        self.resources.append(
            {
                "id": run_id,
                "monotonic_wall_seconds": elapsed,
                "sampling_interval_seconds": 0.05,
                "resource_scope": "direct_child_process_only",
                "peak_working_set_bytes": max(
                    (
                        sample["working_set_bytes"]
                        for sample in samples
                        if sample["working_set_bytes"] is not None
                    ),
                    default=None,
                ),
                "peak_private_bytes": max(
                    (
                        sample["private_bytes"]
                        for sample in samples
                        if sample["private_bytes"] is not None
                    ),
                    default=None,
                ),
                "maximum_observed_thread_count": max(
                    (
                        sample["thread_count"]
                        for sample in samples
                        if sample["thread_count"] is not None
                    ),
                    default=None,
                ),
                "samples": samples,
            }
        )
        if expected_exit_codes is not None and exit_code not in expected_exit_codes:
            raise WorkflowError(
                f"{run_id} expected exit {sorted(expected_exit_codes)}, "
                f"got status={terminal_status} exit={exit_code}"
            )
        return run

    def polatory(
        self,
        run_id: str,
        args: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.child(run_id, [str(self.cli), *args], **kwargs)

    def finish(self, *, observations: dict[str, Any] | None = None) -> None:
        evidence = {
            "schema_version": SCHEMA_VERSION,
            "kind": "frozen_polatory_workflow_observation",
            "scenario_id": self.scenario_id,
            "authority": "diagnostic_baseline_not_mathematical_truth",
            "numeric_tolerance_applied": False,
            "polatory_commit": POLATORY_COMMIT,
            "polatory_cli": {
                "sha256": POLATORY_CLI_SHA256,
                "distribution": "not_redistributed",
            },
            "configured_thread_environment": THREAD_ENV,
            "runs": self.runs,
            "observations": observations or {},
        }
        resources = {
            "schema_version": SCHEMA_VERSION,
            "kind": "non_normative_resource_samples",
            "scenario_id": self.scenario_id,
            "runs": self.resources,
        }
        write_json(self.work / "evidence.json", evidence)
        write_json(self.work / "resources.json", resources)
        print(
            json.dumps(
                {"scenario_id": self.scenario_id, "run_count": len(self.runs)},
                sort_keys=True,
            )
        )


def fixture(recorder: Recorder, name: str) -> pathlib.Path:
    path = recorder.repo_root / "oracle" / "fixtures" / "source" / name
    if not path.is_file():
        raise WorkflowError(f"missing fixture: {path}")
    return path


def run_build_identity(recorder: Recorder) -> dict[str, Any]:
    binaries = {
        "polatory_cli": recorder.cli,
        "polatory_tests": recorder.polatory_root / "build" / "test" / "Unittest.exe",
        "benchmark_points": recorder.polatory_root / "build" / "benchmark" / "points.exe",
        "benchmark_predict": recorder.polatory_root / "build" / "benchmark" / "predict.exe",
    }
    commands = {
        "cmake": ["cmake", "--version"],
        "ninja": ["ninja", "--version"],
        "python": [sys.executable, "--version"],
        "clang_cl": [
            str(
                pathlib.Path(
                    r"C:\Program Files\Microsoft Visual Studio\2022\Community"
                    r"\VC\Tools\Llvm\x64\bin\clang-cl.exe"
                )
            ),
            "--version",
        ],
    }
    observations: dict[str, Any] = {
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture()[0],
            "logical_processor_count": os.cpu_count(),
            "python_implementation": platform.python_implementation(),
        },
        "binaries": {},
        "build_configuration": {},
        "dependency_revisions": {},
    }
    for name, path in binaries.items():
        if not path.is_file():
            raise WorkflowError(f"missing build artifact: {path}")
        observations["binaries"][name] = {
            "path": logical_arg(
                str(path),
                repo_root=recorder.repo_root,
                polatory_root=recorder.polatory_root,
                work=recorder.work,
            ),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
            "distribution": "not_redistributed",
        }
    for name, argv in commands.items():
        recorder.child(
            f"version-{name}",
            argv,
            timeout_seconds=30,
            expected_exit_codes={0},
        )
    for name, path in (
        ("vcpkg_gitlink", recorder.polatory_root / "vcpkg"),
        ("scalfmm_checkout", recorder.polatory_root / "build" / "scalfmm" / "src" / "scalfmm"),
    ):
        if path.exists():
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                shell=False,
            )
            observations["dependency_revisions"][name] = {
                "terminal_status": "exited",
                "exit_code": result.returncode,
                "stdout": stream_record(result.stdout),
                "stderr": stream_record(result.stderr),
            }
    cache_path = recorder.polatory_root / "build" / "CMakeCache.txt"
    ninja_path = recorder.polatory_root / "build" / "build.ninja"
    if not cache_path.is_file() or not ninja_path.is_file():
        raise WorkflowError("frozen build lacks CMakeCache.txt or build.ninja")
    selected_cache_keys = {
        "BUILD_BENCHMARKS",
        "BUILD_CLI",
        "BUILD_EXAMPLES",
        "BUILD_PYTHON_BINDINGS",
        "BUILD_TESTS",
        "CMAKE_BUILD_TYPE",
        "CMAKE_CXX_COMPILER",
        "CMAKE_CXX_FLAGS",
        "CMAKE_CXX_FLAGS_RELEASE",
        "CMAKE_GENERATOR",
        "CMAKE_TOOLCHAIN_FILE",
        "MKL_DIR",
        "OpenMP_CXX_FLAGS",
        "OpenMP_CXX_LIB_NAMES",
        "OpenMP_CXX_SPEC_DATE",
        "VCPKG_INSTALLED_DIR",
        "VCPKG_TARGET_TRIPLET",
    }
    selected_cache: dict[str, dict[str, str]] = {}
    for line in cache_path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line:
            continue
        key_and_type, value = line.split("=", 1)
        if ":" not in key_and_type:
            continue
        key, value_type = key_and_type.split(":", 1)
        if key in selected_cache_keys:
            selected_cache[key] = {
                "type": value_type,
                "value": logical_arg(
                    value,
                    repo_root=recorder.repo_root,
                    polatory_root=recorder.polatory_root,
                    work=recorder.work,
                ),
            }
    ninja_text = ninja_path.read_text(encoding="utf-8", errors="replace")
    observations["build_configuration"] = {
        "cmake_cache": {
            "path": "${POLATORY_ROOT}/build/CMakeCache.txt",
            "size": cache_path.stat().st_size,
            "sha256": sha256_file(cache_path),
            "selected_entries": selected_cache,
        },
        "build_ninja": {
            "path": "${POLATORY_ROOT}/build/build.ninja",
            "size": ninja_path.stat().st_size,
            "sha256": sha256_file(ninja_path),
        },
        "detected_linkage": {
            "mkl_interface": "lp64",
            "mkl_threading": "sequential",
            "mkl_dynamic": "mkl_sequential_dll.lib" in ninja_text,
            "openmp_runtime": (
                "LLVM libomp" if "libomp.lib" in ninja_text else "not detected"
            ),
        },
    }
    return observations


def run_cpp_probe(recorder: Recorder, probe: pathlib.Path) -> dict[str, Any]:
    if not probe.is_file():
        raise WorkflowError(f"missing source probe executable: {probe}")
    output = recorder.child(
        "instrumented-source-probe",
        [str(probe.resolve())],
        timeout_seconds=120,
        expected_exit_codes={0},
    )
    raw = base64.b64decode(output["stdout"]["bytes_base64"])
    records = [json.loads(line) for line in raw.splitlines()]
    if len(records) != 401 or records[0].get("kind") != "manifest":
        raise WorkflowError("source probe did not produce the frozen 401-record schema")
    if records[-1].get("kind") != "summary" or records[-1].get("status") != "completed":
        raise WorkflowError("source probe lacks its completed summary")
    accepted_anisotropy_observations = [
        "identity",
        "positive_diagonal",
        "shear",
        "ill_conditioned_positive_determinant",
    ]
    observed_anisotropy = {
        record.get("observation")
        for record in records
        if record.get("kind") == "anisotropy_observation"
    }
    missing_anisotropy = (
        set(accepted_anisotropy_observations) - observed_anisotropy
    )
    if missing_anisotropy:
        raise WorkflowError(
            "source probe lacks accepted anisotropy observations: "
            f"{sorted(missing_anisotropy)}"
        )
    research_kinds = {
        "model_error_observation",
        "model_mutation_observation",
        "rbf_construction_observation",
    }
    research_records = sum(record.get("kind") in research_kinds for record in records)
    mixed_anisotropy = sum(
        record.get("kind") == "anisotropy_observation"
        and record.get("observation")
        in {
            "singular",
            "reflection",
            "nonfinite_nan",
            "nonfinite_positive_infinity",
            "nonfinite_negative_infinity",
        }
        for record in records
    )
    return {
        "record_count": len(records),
        "stdout_sha256": output["stdout"]["sha256"],
        "accepted_surface_selector": {
            "schema_version": "1.0.0",
            "included_whole_record_kinds": [
                "rbf_metadata",
                "model_observation",
                "monomial_basis_observation",
                "direct_operator_dense_observation",
            ],
            "rbf_evaluation_field_policy": "returned_finite_fields_only",
            "anisotropy_observations": accepted_anisotropy_observations,
            "note": (
                "Returned non-finite fields, unsupported coincident derivatives, "
                "invalid construction/mutation, and invalid anisotropy remain "
                "diagnostic evidence only."
            ),
        },
        "research_only_record_count_lower_bound": research_records + mixed_anisotropy,
    }


def run_cli_command_contracts(recorder: Recorder) -> dict[str, Any]:
    recorder.polatory(
        "global-help",
        ["--help"],
        timeout_seconds=30,
        expected_exit_codes={0},
    )
    for command in COMMANDS:
        recorder.polatory(
            f"help-{command}",
            [command, "--help"],
            timeout_seconds=30,
            expected_exit_codes={0},
        )
    malformed_out = recorder.work / "malformed-output.csv"
    recorder.polatory(
        "partial-number-parsing",
        [
            "unique",
            "--in",
            str(fixture(recorder, "malformed-numbers.csv")),
            "--dim",
            "1",
            "--out",
            str(malformed_out),
        ],
        outputs=[(malformed_out, "logical_table", True)],
        expected_exit_codes={0},
    )
    conflict_out = recorder.work / "conflict.csv"
    recorder.polatory(
        "mutually-exclusive-normal-search",
        [
            "estimate-normals",
            "--in",
            str(fixture(recorder, "point-cloud-plane.csv")),
            "--k",
            "4",
            "--radius",
            "2",
            "--out",
            str(conflict_out),
        ],
        outputs=[(conflict_out, "logical_table", True)],
        expected_exit_codes={1},
    )
    return {
        "command_count": len(COMMANDS),
        "partial_number_behavior": "captured_for_intentional_change_not_candidate_truth",
        "conflict_behavior": "exit_category_observation",
    }


def run_cli_fit_evaluate(recorder: Recorder) -> dict[str, Any]:
    for dim in (1, 2, 3):
        model = recorder.work / f"dim{dim}.model"
        interpolant = recorder.work / f"dim{dim}.interpolant"
        evaluation = recorder.work / f"dim{dim}-evaluation.csv"
        extracted = recorder.work / f"dim{dim}-extracted.model"
        recorder.polatory(
            f"create-model-dim{dim}",
            [
                "create-model",
                "--dim",
                str(dim),
                "--rbf",
                "th3",
                "1",
                "0.25",
                "aniso",
                *ANISOTROPY[dim],
                "--nug",
                "0.01",
                "--deg",
                "1",
                "--out",
                str(model),
            ],
            outputs=[(model, "legacy_model_intermediate", True)],
            expected_exit_codes={0},
        )
        recorder.polatory(
            f"fit-hermite-dim{dim}",
            [
                "fit",
                "--in",
                str(fixture(recorder, VALUE_FIXTURE[dim])),
                "--grad-in",
                str(fixture(recorder, GRAD_FIXTURE[dim])),
                "--dim",
                str(dim),
                "--model",
                str(model),
                "--tol",
                "1e-8",
                "--grad-tol",
                "1e-8",
                "--out",
                str(interpolant),
            ],
            outputs=[(interpolant, "legacy_interpolant_intermediate", True)],
            expected_exit_codes={0},
        )
        recorder.polatory(
            f"evaluate-value-gradient-dim{dim}",
            [
                "evaluate",
                "--in",
                str(interpolant),
                "--points",
                str(fixture(recorder, EVAL_FIXTURE[dim])),
                "--dim",
                str(dim),
                "--grads",
                "--out",
                str(evaluation),
            ],
            outputs=[(evaluation, "logical_table", True)],
            expected_exit_codes={0},
        )
        recorder.polatory(
            f"extract-model-dim{dim}",
            [
                "extract-model",
                "--in",
                str(interpolant),
                "--dim",
                str(dim),
                "--out",
                str(extracted),
            ],
            outputs=[(extracted, "legacy_model_intermediate", True)],
            expected_exit_codes={0},
        )
        recorder.polatory(
            f"show-model-dim{dim}",
            ["show-model", "--in", str(extracted), "--dim", str(dim)],
            # Polatory persists polyharmonic models but its textual
            # description path is covariance-only.
            expected_exit_codes={1},
        )
    return {
        "dimensions": [1, 2, 3],
        "constraint_layout": "mixed_value_full_gradient",
        "evaluation_layout": "coordinates_value_full_gradient",
    }


def run_fit_modes(recorder: Recorder) -> dict[str, Any]:
    ordinary = recorder.work / "ordinary.interpolant"
    reduced = recorder.work / "incremental.interpolant"
    inequality = recorder.work / "inequality.interpolant"
    common = [
        "--in",
        str(fixture(recorder, "values-1d.csv")),
        "--dim",
        "1",
        "--rbf",
        "th3",
        "1",
        "0.25",
        "--deg",
        "1",
        "--tol",
        "1e-8",
    ]
    recorder.polatory(
        "ordinary-fit",
        ["fit", *common, "--out", str(ordinary)],
        outputs=[(ordinary, "legacy_interpolant_intermediate", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "incremental-fit",
        ["fit", *common, "--reduce", "--out", str(reduced)],
        outputs=[(reduced, "legacy_interpolant_intermediate", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "inequality-fit",
        [
            "fit",
            "--in",
            str(fixture(recorder, "inequality-simple-1d.csv")),
            "--dim",
            "1",
            "--rbf",
            "gau",
            "1",
            "5",
            "--deg",
            "1",
            "--tol",
            "1e-8",
            "--ineq",
            "--out",
            str(inequality),
        ],
        outputs=[(inequality, "legacy_interpolant_intermediate", True)],
        expected_exit_codes={0},
    )
    return {
        "accepted_modes": ["ordinary", "incremental", "inequality"],
        "warm_start": "not_claimed_as_required_stable_capability",
    }


def run_cli_kriging(recorder: Recorder) -> dict[str, Any]:
    variogram_1d = recorder.work / "variogram-1d.bin"
    recorder.polatory(
        "variogram-1d",
        [
            "variogram",
            "--in",
            str(fixture(recorder, "values-1d.csv")),
            "--dim",
            "1",
            "--lag-dist",
            "0.5",
            "--num-lags",
            "4",
            "--out",
            str(variogram_1d),
        ],
        outputs=[(variogram_1d, "differential_only_variogram_set", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "show-variogram-1d",
        ["show-variogram", "--in", str(variogram_1d), "--dim", "1"],
        expected_exit_codes={0},
    )
    for weight in range(6):
        fitted = recorder.work / f"variogram-model-w{weight}.model"
        recorder.polatory(
            f"fit-model-to-variogram-weight-{weight}",
            [
                "fit-model-to-variogram",
                "--in",
                str(variogram_1d),
                "--dim",
                "1",
                "--rbf",
                "exp",
                "1",
                "5",
                "--weights",
                str(weight),
                "--num-trials",
                "1",
                "--out",
                str(fitted),
            ],
            outputs=[(fitted, "legacy_model_intermediate", True)],
            expected_exit_codes={0},
        )
    cross_validation = recorder.work / "cross-validation.csv"
    recorder.polatory(
        "cross-validate",
        [
            "cross-validate",
            "--in",
            str(fixture(recorder, "cross-validation-1d.csv")),
            "--dim",
            "1",
            "--rbf",
            "exp",
            "1",
            "5",
            "--deg",
            "1",
            "--tol",
            "1e-6",
            "--out",
            str(cross_validation),
        ],
        outputs=[(cross_validation, "logical_table", True)],
        expected_exit_codes={0},
    )
    normal_score = recorder.work / "normal-score-ties.variogram"
    recorder.polatory(
        "normal-score-ties",
        [
            "variogram",
            "--in",
            str(fixture(recorder, "normal-score-ties.csv")),
            "--dim",
            "1",
            "--normal-score",
            "--lag-dist",
            "1",
            "--num-lags",
            "4",
            "--out",
            str(normal_score),
        ],
        outputs=[(normal_score, "differential_only_variogram_set", True)],
        expected_exit_codes={0},
    )
    variogram_2d = recorder.work / "variogram-2d-aniso.bin"
    recorder.polatory(
        "variogram-2d-detrended-anisotropic",
        [
            "variogram",
            "--in",
            str(fixture(recorder, "values-2d.csv")),
            "--dim",
            "2",
            "--detrend",
            "1",
            "--aniso",
            "--lag-dist",
            "0.5",
            "--num-lags",
            "4",
            "--out",
            str(variogram_2d),
        ],
        outputs=[(variogram_2d, "differential_only_variogram_set", True)],
        expected_exit_codes={0},
    )
    return {
        "weight_schemes": list(range(6)),
        "variogram_set_import_scope": "differential_only_not_migration_input",
    }


def run_cli_point_cloud(recorder: Recorder) -> dict[str, Any]:
    unique = recorder.work / "unique.csv"
    normals = recorder.work / "normals.csv"
    sdf = recorder.work / "sdf.csv"
    recorder.polatory(
        "unique-distance-filter",
        [
            "unique",
            "--in",
            str(fixture(recorder, "unique-2d.csv")),
            "--dim",
            "2",
            "--dist",
            "1e-6",
            "--out",
            str(unique),
        ],
        outputs=[(unique, "logical_table", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "estimate-normals-knn",
        [
            "estimate-normals",
            "--in",
            str(fixture(recorder, "point-cloud-plane.csv")),
            "--k",
            "4",
            "--threshold",
            "1",
            "--direction",
            "0",
            "0",
            "1",
            "--out",
            str(normals),
        ],
        outputs=[(normals, "logical_table", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "normals-to-sdf",
        [
            "normals-to-sdf",
            "--in",
            str(normals),
            "--offset",
            "0.25",
            "--ratio",
            "1",
            "--out",
            str(sdf),
        ],
        outputs=[(sdf, "logical_table", True)],
        expected_exit_codes={0},
    )
    return {
        "normal_orientation": "toward_direction_positive_z",
        "sdf_ratio": 1.0,
        "random_selection": "disabled_by_ratio_1",
    }


def run_cli_geometry(recorder: Recorder) -> dict[str, Any]:
    surface_interpolant = recorder.work / "surface-25d.interpolant"
    surface_obj = recorder.work / "surface-25d.obj"
    recorder.polatory(
        "fit-surface-25d-field",
        [
            "fit",
            "--in",
            str(fixture(recorder, "values-2d.csv")),
            "--dim",
            "2",
            "--rbf",
            "th3",
            "1",
            "0.25",
            "--deg",
            "1",
            "--tol",
            "1e-8",
            "--out",
            str(surface_interpolant),
        ],
        outputs=[(surface_interpolant, "legacy_interpolant_intermediate", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "surface-25d",
        [
            "surface-25d",
            "--in",
            str(surface_interpolant),
            "--bbox",
            "-1.5",
            "-1.5",
            "-3",
            "1.5",
            "1.5",
            "5",
            "--res",
            "0.5",
            "--out",
            str(surface_obj),
        ],
        outputs=[(surface_obj, "raw_obj_noncontractual_numbering", True)],
        expected_exit_codes={0},
    )
    sdf = recorder.work / "geometry-sdf.csv"
    implicit = recorder.work / "geometry-implicit.interpolant"
    iso_obj = recorder.work / "isosurface.obj"
    recorder.polatory(
        "geometry-normals-to-sdf",
        [
            "normals-to-sdf",
            "--in",
            str(fixture(recorder, "normals-plane.csv")),
            "--offset",
            "0.5",
            "--ratio",
            "1",
            "--out",
            str(sdf),
        ],
        outputs=[(sdf, "logical_table", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "fit-isosurface-field",
        [
            "fit",
            "--in",
            str(sdf),
            "--dim",
            "3",
            "--rbf",
            "th3",
            "1",
            "0.25",
            "--deg",
            "1",
            "--tol",
            "1e-8",
            "--out",
            str(implicit),
        ],
        outputs=[(implicit, "legacy_interpolant_intermediate", True)],
        expected_exit_codes={0},
    )
    recorder.polatory(
        "isosurface-seeded-snapped",
        [
            "isosurface",
            "--in",
            str(implicit),
            "--seeds",
            str(fixture(recorder, "isosurface-seeds.csv")),
            "--snap",
            str(fixture(recorder, "isosurface-snap.csv")),
            "--bbox",
            "-1.5",
            "-1.5",
            "-1",
            "1.5",
            "1.5",
            "1",
            "--res",
            "0.5",
            "--isoval",
            "0",
            "--out",
            str(iso_obj),
        ],
        outputs=[(iso_obj, "raw_obj_noncontractual_numbering", True)],
        timeout_seconds=180,
        expected_exit_codes={0},
    )
    return {
        "surface_25d": obj_summary(surface_obj),
        "isosurface": obj_summary(iso_obj),
        "exact_vertex_face_numbering_is_contractual": False,
    }


def obj_summary(path: pathlib.Path) -> dict[str, Any]:
    vertices: list[tuple[float, float, float]] = []
    face_count = 0
    sentinel_rows = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            fields = line.split()
            if len(fields) >= 4:
                vertex = (float(fields[1]), float(fields[2]), float(fields[3]))
                vertices.append(vertex)
                if not all(value == value for value in vertex):
                    sentinel_rows += 1
        elif line.startswith("f "):
            face_count += 1
    bbox = None
    finite = [
        vertex
        for vertex in vertices
        if all(value == value and abs(value) != float("inf") for value in vertex)
    ]
    if finite:
        bbox = {
            "min": [min(row[axis] for row in finite) for axis in range(3)],
            "max": [max(row[axis] for row in finite) for axis in range(3)],
        }
    return {
        "vertex_count": len(vertices),
        "face_count": face_count,
        "nonfinite_sentinel_vertex_count": sentinel_rows,
        "bbox": bbox,
    }


def run_unit_smoke(recorder: Recorder) -> dict[str, Any]:
    tests = recorder.polatory_root / "build" / "test" / "Unittest.exe"
    selected = (
        "rbf_evaluator.trivial:rbf_operator.trivial:KrylovTest.gmres:"
        "variogram_calculator.serialization:normal_estimator.knn:"
        "sdf_data_generator.trivial:isosurface.generate_plane"
    )
    recorder.child(
        "selected-upstream-unit-smoke",
        [
            str(tests),
            f"--gtest_filter={selected}",
            "--gtest_color=no",
            "--gtest_print_time=0",
            "--gtest_random_seed=1",
        ],
        timeout_seconds=300,
        expected_exit_codes={0},
    )
    return {
        "filter": selected,
        "role": "provenance_only_not_an_acceptance_threshold",
    }


def verify_fixture_checksums(root: pathlib.Path) -> dict[str, Any]:
    checksum_path = root / "checksums.sha256"
    if not checksum_path.is_file():
        raise WorkflowError(f"missing checksum manifest: {checksum_path}")
    expected_paths: set[str] = set()
    for number, line in enumerate(
        checksum_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as error:
            raise WorkflowError(f"bad checksum row {number}") from error
        if relative in expected_paths:
            raise WorkflowError(f"duplicate checksum path: {relative}")
        expected_paths.add(relative)
        path = root.joinpath(*pathlib.PurePosixPath(relative).parts)
        if not path.is_file() or sha256_file(path) != digest:
            raise WorkflowError(f"legacy fixture checksum mismatch: {relative}")
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if actual_paths != expected_paths:
        raise WorkflowError("legacy fixture checksum manifest is not a closed file set")
    return {
        "file_count_excluding_checksum_manifest": len(expected_paths),
        "total_bytes_excluding_checksum_manifest": sum(
            (root / pathlib.PurePosixPath(relative)).stat().st_size
            for relative in expected_paths
        ),
        "checksums_sha256": sha256_file(checksum_path),
    }


def run_legacy_matrix(recorder: Recorder) -> dict[str, Any]:
    root = (
        recorder.repo_root
        / "oracle"
        / "fixtures"
        / "legacy"
        / "windows-x86_64-polatory-4a30beb"
    )
    integrity = verify_fixture_checksums(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    accepted_artifacts = [
        artifact
        for artifact in manifest["artifacts"]
        if artifact["role"] in {"model", "interpolant"}
    ]
    for artifact in accepted_artifacts:
        path = root.joinpath(*pathlib.PurePosixPath(artifact["path"]).parts)
        dim = int(artifact["dimension"])
        if artifact["role"] == "model":
            covariance = artifact["family"] not in {"bh2", "bh3", "th2", "th3"}
            recorder.polatory(
                f"load-{artifact['path'].replace('/', '-')}",
                ["show-model", "--in", str(path), "--dim", str(dim)],
                expected_exit_codes={0} if covariance else {1},
            )
        elif artifact["role"] == "interpolant":
            output = recorder.work / (
                artifact["path"].replace("/", "-") + ".evaluation.csv"
            )
            recorder.polatory(
                f"load-{artifact['path'].replace('/', '-')}",
                [
                    "evaluate",
                    "--in",
                    str(path),
                    "--points",
                    str(fixture(recorder, EVAL_FIXTURE[dim])),
                    "--dim",
                    str(dim),
                    "--grads",
                    "--out",
                    str(output),
                ],
                outputs=[(output, "logical_table", True)],
                expected_exit_codes={0},
            )
    return {
        **integrity,
        "artifact_count": len(accepted_artifacts),
        "coverage": manifest["coverage"],
        "platform_layout": manifest["platform_layout"],
        "variogram_set_role": "differential_only_not_import_input",
    }


def run_legacy_corruption(recorder: Recorder) -> dict[str, Any]:
    root = (
        recorder.repo_root
        / "oracle"
        / "fixtures"
        / "legacy"
        / "windows-x86_64-polatory-4a30beb"
    )
    verify_fixture_checksums(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    skipped: list[dict[str, Any]] = []
    for case in manifest["corruption_cases"]:
        path = root.joinpath(*pathlib.PurePosixPath(case["path"]).parts)
        if case.get("replay_policy", "").startswith("do_not_load"):
            skipped.append(
                {
                    "path": case["path"],
                    "reason": case.get("reason", "bounded safety policy"),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
            continue
        if "interpolant" in path.name:
            output = recorder.work / f"{path.stem}.csv"
            recorder.polatory(
                f"corruption-{path.stem}",
                [
                    "evaluate",
                    "--in",
                    str(path),
                    "--points",
                    str(fixture(recorder, "evaluation-points-1d.csv")),
                    "--dim",
                    "1",
                    "--out",
                    str(output),
                ],
                outputs=[(output, "incidental_invalid_input_output", True)],
                timeout_seconds=10,
            )
        else:
            recorder.polatory(
                f"corruption-{path.stem}",
                ["show-model", "--in", str(path), "--dim", "1"],
                timeout_seconds=10,
            )
    return {
        "role": "research_only_not_candidate_truth",
        "skipped_unbounded_cases": skipped,
    }


def run_defect_inequality(recorder: Recorder) -> dict[str, Any]:
    output = recorder.work / "kostov.interpolant"
    recorder.polatory(
        "kostov-active-set-reproducer",
        [
            "fit",
            "--in",
            str(fixture(recorder, "inequality-kostov-1d.csv")),
            "--dim",
            "1",
            "--rbf",
            "gau",
            "1",
            "5",
            "--deg",
            "0",
            "--tol",
            "1e-8",
            "--ineq",
            "--out",
            str(output),
        ],
        outputs=[(output, "research_only_interpolant", True)],
        timeout_seconds=120,
        expected_exit_codes={0},
    )
    return {
        "role": "research_only",
        "adjudication": "pending",
        "candidate_defect": "inequality_active_set_indexing",
    }


def write_zero_rhs(path: pathlib.Path, count: int = 1024) -> None:
    rows = []
    for index in range(count):
        x = (index % 32) / 31
        y = ((index // 32) % 32) / 31
        rows.append(f"{x:.17g},{y:.17g},0\n")
    path.write_text("".join(rows), encoding="ascii", newline="\n")


def run_defect_zero_rhs(recorder: Recorder) -> dict[str, Any]:
    values = recorder.work / "zero-rhs-1024.csv"
    output = recorder.work / "zero-rhs.interpolant"
    write_zero_rhs(values)
    recorder.polatory(
        "zero-rhs-fit",
        [
            "fit",
            "--in",
            str(values),
            "--dim",
            "2",
            "--rbf",
            "gau",
            "1",
            "1",
            "--deg",
            "0",
            "--tol",
            "1e-8",
            "--out",
            str(output),
        ],
        outputs=[
            (values, "generated_reproducer_input", True),
            (output, "research_only_interpolant", True),
        ],
        timeout_seconds=180,
        expected_exit_codes={0},
    )
    return {
        "role": "research_only",
        "adjudication": "pending",
        "candidate_defect": "zero_rhs_gmres_nan_basis",
        "public_cli_observation": (
            "The public fit can return before the suspected internal basis state "
            "is externally visible."
        ),
    }


def run_defect_normal_score(recorder: Recorder) -> dict[str, Any]:
    for name in ("normal-score-singleton.csv", "normal-score-empty.csv"):
        output = recorder.work / f"{pathlib.Path(name).stem}.variogram"
        expected = {0} if "singleton" in name else {1}
        recorder.polatory(
            pathlib.Path(name).stem,
            [
                "variogram",
                "--in",
                str(fixture(recorder, name)),
                "--dim",
                "1",
                "--normal-score",
                "--lag-dist",
                "1",
                "--num-lags",
                "2",
                "--out",
                str(output),
            ],
            outputs=[(output, "research_only_variogram", True)],
            expected_exit_codes=expected,
        )
    return {
        "role": "research_only",
        "adjudication": "pending",
        "candidate_defect": "normal_score_empty_or_singleton",
    }


def run_defect_multi_radius(recorder: Recorder) -> dict[str, Any]:
    output = recorder.work / "multi-radius.csv"
    recorder.polatory(
        "multi-radius-underpopulation",
        [
            "estimate-normals",
            "--in",
            str(fixture(recorder, "multi-radius-underpopulation.csv")),
            "--radius",
            "0.25",
            "2",
            "--threshold",
            "1",
            "--direction",
            "0",
            "0",
            "1",
            "--out",
            str(output),
        ],
        outputs=[(output, "research_only_logical_table", True)],
        expected_exit_codes={0},
    )
    return {
        "role": "research_only",
        "adjudication": "pending",
        "candidate_defect": "multi_radius_underpopulation",
    }


def run_defect_pathological_sdf(recorder: Recorder) -> dict[str, Any]:
    output = recorder.work / "pathological-sdf.csv"
    recorder.polatory(
        "duplicate-normal-points",
        [
            "normals-to-sdf",
            "--in",
            str(fixture(recorder, "pathological-sdf-duplicates.csv")),
            "--offset",
            "0.5",
            "--ratio",
            "1",
            "--out",
            str(output),
        ],
        outputs=[(output, "research_only_logical_table", True)],
        timeout_seconds=10,
        expected_exit_codes={1},
    )
    return {
        "role": "research_only",
        "adjudication": "pending",
        "candidate_defect": "pathological_sdf_adjustment",
    }


def run_python_inventory(recorder: Recorder) -> dict[str, Any]:
    path = recorder.repo_root / "oracle" / "manifests" / "python-surface.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    upstream = manifest.get("frozen_upstream", {})
    if upstream.get("commit") != POLATORY_COMMIT:
        raise WorkflowError("Python surface manifest is not bound to frozen Polatory")
    for source in upstream["source_files"]:
        target = recorder.polatory_root.joinpath(
            *pathlib.PurePosixPath(source["path"]).parts
        )
        if not target.is_file() or sha256_file(target) != source["sha256"]:
            raise WorkflowError(f"Python source inventory mismatch: {source['path']}")
    return {
        "manifest_path": "${REPO}/oracle/manifests/python-surface.json",
        "manifest_size": path.stat().st_size,
        "manifest_sha256": sha256_file(path),
        "workflow_count": len(manifest["workflows"]),
        "role": "accepted_surface_inventory",
        "acceptance_kind": "source_bound_workflow_and_shape_prerequisite",
        "runtime_buildability": "not_established_by_this_scenario",
        "runtime_workflow_execution": "not_established_by_this_scenario",
    }


def run_python_build_evidence(recorder: Recorder) -> dict[str, Any]:
    root = (
        recorder.repo_root
        / "oracle"
        / "fixtures"
        / "python-build"
        / "windows-x86_64-polatory-4a30beb"
    )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for stream in manifest["evidence_files"]:
        path = root.joinpath(*pathlib.PurePosixPath(stream["path"]).parts)
        if (
            not path.is_file()
            or path.stat().st_size != stream["bytes"]
            or sha256_file(path) != stream["sha256"]
        ):
            raise WorkflowError(f"Python build evidence mismatch: {stream['path']}")
    return {
        "manifest_path": (
            "${REPO}/oracle/fixtures/python-build/"
            "windows-x86_64-polatory-4a30beb/manifest.json"
        ),
        "manifest_size": (root / "manifest.json").stat().st_size,
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "run_count": len(manifest["runs"]),
        "role": "research_only_buildability_evidence",
        "adjudication": "pending",
    }


def run_scale_ladder(recorder: Recorder) -> dict[str, Any]:
    points_exe = recorder.polatory_root / "build" / "benchmark" / "points.exe"
    predict_exe = recorder.polatory_root / "build" / "benchmark" / "predict.exe"
    ladder: list[dict[str, Any]] = []
    files: dict[tuple[int, int], pathlib.Path] = {}
    for size in (1_000, 10_000, 100_000, 1_000_000):
        for seed, role in ((0, "training_points"), (1, "prediction_points")):
            output = recorder.work / f"points-{size}-seed-{seed}.csv"
            files[(size, seed)] = output
            run = recorder.child(
                f"generate-{role}-{size}",
                [str(points_exe), str(size), str(seed), str(output)],
                outputs=[(output, role, size == 1_000)],
                timeout_seconds=180,
                expected_exit_codes={0},
            )
            artifact = run["outputs"][0]
            row_count = sum(1 for _ in output.open("rb"))
            ladder.append(
                {
                    "requested_rows": size,
                    "actual_rows": row_count,
                    "seed": seed,
                    "role": role,
                    "size": artifact["size"],
                    "sha256": artifact["sha256"],
                    "bytes_embedded_in_evidence": size == 1_000,
                }
            )
    train = files[(1_000, 0)]
    predict = files[(1_000, 1)]
    values = recorder.work / "scale-1000-values.csv"
    with train.open("r", encoding="utf-8") as source, values.open(
        "w", encoding="ascii", newline="\n"
    ) as target:
        for line in source:
            x, y, z = (
                float(value) for value in line.replace(",", " ").split()[:3]
            )
            target.write(f"{x + 2.0 * y - 0.5 * z:.17g}\n")
    prediction = recorder.work / "scale-1000-predictions.csv"
    recorder.child(
        "lower-rung-fit-evaluate-1000x1000",
        [str(predict_exe), str(train), str(values), str(predict), str(prediction)],
        outputs=[
            (values, "deterministic_analytic_values", True),
            (prediction, "raw_numerical_output", True),
        ],
        timeout_seconds=300,
        expected_exit_codes={0},
    )
    return {
        "upstream_workload": {
            "dimensions": 3,
            "rbf": "exp",
            "rbf_parameters": [1.0, 0.02],
            "polynomial_degree": 0,
            "fit_tolerance": 0.0001,
            "training_seed": 0,
            "prediction_seed": 1,
        },
        "ladder": ladder,
        "million_rung_execution": (
            "point corpus identity frozen; full fit/evaluation intentionally deferred "
            "until lower-rung resource bounds and the measurement harness exist"
        ),
        "lower_rung_execution": "1000 training x 1000 prediction",
        "release_gate_satisfied": False,
    }


SCENARIOS = {
    "build-identity": lambda recorder, _args: run_build_identity(recorder),
    "cpp-probe": lambda recorder, args: run_cpp_probe(recorder, args.probe.resolve()),
    "cli-command-contracts": lambda recorder, _args: run_cli_command_contracts(recorder),
    "cli-fit-evaluate": lambda recorder, _args: run_cli_fit_evaluate(recorder),
    "fit-modes": lambda recorder, _args: run_fit_modes(recorder),
    "cli-kriging": lambda recorder, _args: run_cli_kriging(recorder),
    "cli-point-cloud": lambda recorder, _args: run_cli_point_cloud(recorder),
    "cli-geometry": lambda recorder, _args: run_cli_geometry(recorder),
    "unit-smoke": lambda recorder, _args: run_unit_smoke(recorder),
    "scale-input-ladder": lambda recorder, _args: run_scale_ladder(recorder),
    "legacy-matrix": lambda recorder, _args: run_legacy_matrix(recorder),
    "legacy-corruption": lambda recorder, _args: run_legacy_corruption(recorder),
    "defect-inequality-active-set": lambda recorder, _args: run_defect_inequality(
        recorder
    ),
    "defect-zero-rhs": lambda recorder, _args: run_defect_zero_rhs(recorder),
    "defect-normal-score-small-inputs": lambda recorder, _args: run_defect_normal_score(
        recorder
    ),
    "defect-multi-radius-normals": lambda recorder, _args: run_defect_multi_radius(
        recorder
    ),
    "defect-pathological-sdf": lambda recorder, _args: run_defect_pathological_sdf(
        recorder
    ),
    "python-interface-inventory": lambda recorder, _args: run_python_inventory(recorder),
    "python-build": lambda recorder, _args: run_python_build_evidence(recorder),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--repo-root", type=pathlib.Path, required=True)
    parser.add_argument("--polatory-root", type=pathlib.Path, required=True)
    parser.add_argument("--work", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--probe", type=pathlib.Path)
    args = parser.parse_args()
    if args.scenario == "cpp-probe" and args.probe is None:
        parser.error("--probe is required for cpp-probe")
    try:
        recorder = Recorder(
            scenario_id=args.scenario,
            repo_root=args.repo_root,
            polatory_root=args.polatory_root,
            work=args.work,
        )
        observations = SCENARIOS[args.scenario](recorder, args)
        recorder.finish(observations=observations)
    except (
        WorkflowError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
