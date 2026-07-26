#!/usr/bin/env python3
"""Materialize the small Windows x86_64 Polatory legacy-artifact fixture matrix.

This is a current-baseline adapter, not a general differential harness.  It
refuses any source revision or executable other than the frozen Polatory
snapshot and never overwrites an existing fixture directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import struct
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Any


POLATORY_COMMIT = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"
POLATORY_CLI_SHA256 = "95cd325f727e6f56d1656feb52672a37a5fc655132a232cbb6976f031ffccfe9"
SCHEMA_VERSION = "1.0.0"
THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OMP_THREAD_LIMIT": "1",
    "MKL_NUM_THREADS": "1",
    "MKL_DYNAMIC": "FALSE",
    "MKL_CBWR": "COMPATIBLE",
}
FAMILIES = {
    "bh2": ["1", "0.25"],
    "bh3": ["1", "0.25"],
    "th2": ["1", "0.25"],
    "th3": ["1", "0.25"],
    "cub": ["1", "5"],
    "exp": ["1", "5"],
    "gau": ["1", "5"],
    "gc3": ["1", "5"],
    "gc5": ["1", "5"],
    "gc7": ["1", "5"],
    "gc9": ["1", "5"],
    "sph": ["1", "5"],
    "sp3": ["1", "5"],
    "sp5": ["1", "5"],
    "sp7": ["1", "5"],
    "sp9": ["1", "5"],
}
ANISOTROPY = {
    1: ["1.5"],
    2: ["1", "0.25", "0", "1"],
    3: ["1", "0.2", "0", "0", "1", "0.1", "0", "0", "1"],
}
VALUE_FIXTURE = {
    1: "values-1d.csv",
    2: "values-2d.csv",
    3: "values-3d-quadratic.csv",
}
GRADIENT_FIXTURE = {
    1: "gradients-1d.csv",
    2: "gradients-2d.csv",
    3: "gradients-3d.csv",
}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(root: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.STDOUT, text=True
    ).strip()


def verify_frozen_source(polatory_root: pathlib.Path, cli: pathlib.Path) -> None:
    actual_commit = git_output(polatory_root, "rev-parse", "HEAD")
    if actual_commit != POLATORY_COMMIT:
        raise RuntimeError(
            f"Polatory HEAD is {actual_commit}; expected frozen {POLATORY_COMMIT}"
        )
    tracked = git_output(polatory_root, "status", "--porcelain", "--untracked-files=no")
    if tracked:
        raise RuntimeError("Polatory has tracked modifications; refusing to label artifacts frozen")
    actual_cli_hash = sha256_file(cli)
    if actual_cli_hash != POLATORY_CLI_SHA256:
        raise RuntimeError(
            f"polatory.exe SHA-256 is {actual_cli_hash}; expected {POLATORY_CLI_SHA256}"
        )


def logical_arg(
    value: str, repo_root: pathlib.Path, polatory_root: pathlib.Path, staging: pathlib.Path
) -> str:
    candidate = pathlib.Path(value)
    if value == str((polatory_root / "build" / "cli" / "polatory.exe").resolve()):
        return "${POLATORY_CLI}"
    if candidate.is_absolute():
        resolved = candidate.resolve()
        for root, token in (
            (staging.resolve(), "${WORK}"),
            (repo_root.resolve(), "${REPO}"),
            (polatory_root.resolve(), "${POLATORY_ROOT}"),
        ):
            try:
                suffix = resolved.relative_to(root).as_posix()
            except ValueError:
                continue
            return token if not suffix else f"{token}/{suffix}"
    return value.replace("\\", "/")


def run_cli(
    *,
    cli: pathlib.Path,
    args: list[str],
    run_id: str,
    staging: pathlib.Path,
    repo_root: pathlib.Path,
    polatory_root: pathlib.Path,
    scratch: pathlib.Path,
    records: list[dict[str, Any]],
    timeout_seconds: float = 60.0,
) -> None:
    logs = staging / "generation-logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path = logs / f"{run_id}.stdout.bin"
    stderr_path = logs / f"{run_id}.stderr.bin"
    argv = [str(cli.resolve()), *args]
    env = os.environ.copy()
    env.update(THREAD_ENV)
    env.update({"TEMP": str(scratch), "TMP": str(scratch)})
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=scratch,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        status = "exited"
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        status = "timeout"
        exit_code = None
        stdout = error.stdout or b""
        stderr = error.stderr or b""
    elapsed = time.monotonic() - started
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    record = {
        "id": run_id,
        "argv": [
            logical_arg(arg, repo_root, polatory_root, staging) for arg in argv
        ],
        "cwd": "${SCRATCH}",
        "environment": {**THREAD_ENV, "TEMP": "${SCRATCH}", "TMP": "${SCRATCH}"},
        "configured_threads": 1,
        "effective_threads": None,
        "seed": None,
        "seed_policy": "No seed is exposed by this CLI operation.",
        "timeout_seconds": timeout_seconds,
        "terminal_status": status,
        "exit_code": exit_code,
        "elapsed_seconds_diagnostic": elapsed,
        "stdout": {
            "path": stdout_path.resolve().relative_to(staging.resolve()).as_posix(),
            "size": len(stdout),
            "sha256": hashlib.sha256(stdout).hexdigest(),
        },
        "stderr": {
            "path": stderr_path.resolve().relative_to(staging.resolve()).as_posix(),
            "size": len(stderr),
            "sha256": hashlib.sha256(stderr).hexdigest(),
        },
    }
    records.append(record)
    if status != "exited" or exit_code != 0:
        raise RuntimeError(
            f"{run_id} failed: status={status}, exit={exit_code}, "
            f"stderr={stderr.decode('utf-8', 'backslashreplace')}"
        )


def record_file(path: pathlib.Path, staging: pathlib.Path, role: str, **metadata: Any) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(staging.resolve()).as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "role": role,
        **metadata,
    }


def write_corruptions(
    staging: pathlib.Path, artifacts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    corrupt_root = staging / "corruptions"
    corrupt_root.mkdir(parents=True, exist_ok=True)
    source_model = staging / "dim1" / "gau.model"
    source_interpolant = staging / "dim1" / "gau.interpolant"
    model_bytes = source_model.read_bytes()
    interpolant_bytes = source_interpolant.read_bytes()
    cases: list[dict[str, Any]] = []

    def add(name: str, payload: bytes, source: pathlib.Path, hazard: str) -> None:
        target = corrupt_root / name
        target.write_bytes(payload)
        item = record_file(
            target,
            staging,
            "malformed_legacy_artifact",
            source=source.resolve().relative_to(staging.resolve()).as_posix(),
            hazard=hazard,
            replay_policy=(
                "do_not_load_without_process_memory_and_timeout_limits"
                if hazard == "unbounded_allocation_request"
                else "bounded_subprocess_only"
            ),
        )
        artifacts.append(item)
        cases.append(item)

    add("model-empty.bin", b"", source_model, "truncated")
    add("model-truncated-1.bin", model_bytes[:1], source_model, "truncated")
    add(
        "model-truncated-half.bin",
        model_bytes[: len(model_bytes) // 2],
        source_model,
        "truncated",
    )
    add("model-truncated-last.bin", model_bytes[:-1], source_model, "truncated")
    add("model-trailing.bin", model_bytes + b"RAPIDRBF_TRAILING", source_model, "trailing_bytes")
    add(
        "model-huge-rbf-count.bin",
        struct.pack("<Q", 1 << 31),
        source_model,
        "unbounded_allocation_request",
    )
    add(
        "model-nonfinite-nugget.bin",
        model_bytes[:-8] + struct.pack("<Q", 0x7FF8000000000001),
        source_model,
        "nonfinite_model_state",
    )
    add(
        "model-negative-nugget.bin",
        model_bytes[:-8] + struct.pack("<d", -1.0),
        source_model,
        "invalid_model_state",
    )
    add(
        "interpolant-truncated-last.bin",
        interpolant_bytes[:-1],
        source_interpolant,
        "truncated",
    )
    add(
        "interpolant-trailing.bin",
        interpolant_bytes + b"RAPIDRBF_TRAILING",
        source_interpolant,
        "trailing_bytes",
    )
    return cases


def write_checksums(root: pathlib.Path) -> None:
    checksum_path = root / "checksums.sha256"
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p != checksum_path):
        rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n")
    checksum_path.write_text("".join(rows), encoding="utf-8", newline="\n")


def materialize(
    repo_root: pathlib.Path,
    polatory_root: pathlib.Path,
    output: pathlib.Path,
) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    if staging.exists():
        raise RuntimeError(f"unexpected staging collision: {staging}")
    staging.mkdir()
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="rapidrbf-legacy-materialize-"))
    cli = polatory_root / "build" / "cli" / "polatory.exe"
    verify_frozen_source(polatory_root, cli)
    source_fixtures = repo_root / "oracle" / "fixtures" / "source"
    records: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    try:
        for dim in (1, 2, 3):
            dim_root = staging / f"dim{dim}"
            dim_root.mkdir()
            values = source_fixtures / VALUE_FIXTURE[dim]
            for family, params in FAMILIES.items():
                model = dim_root / f"{family}.model"
                interpolant = dim_root / f"{family}.interpolant"
                model_args = [
                    "create-model",
                    "--dim",
                    str(dim),
                    "--rbf",
                    family,
                    *params,
                    "aniso",
                    *ANISOTROPY[dim],
                    "--nug",
                    "0.01",
                    "--out",
                    str(model),
                ]
                run_cli(
                    cli=cli,
                    args=model_args,
                    run_id=f"legacy-model-dim{dim}-{family}",
                    staging=staging,
                    repo_root=repo_root,
                    polatory_root=polatory_root,
                    scratch=scratch,
                    records=records,
                )
                fit_args = [
                    "fit",
                    "--in",
                    str(values),
                    "--dim",
                    str(dim),
                    "--model",
                    str(model),
                    "--tol",
                    "1e-8",
                    "--out",
                    str(interpolant),
                ]
                run_cli(
                    cli=cli,
                    args=fit_args,
                    run_id=f"legacy-interpolant-dim{dim}-{family}",
                    staging=staging,
                    repo_root=repo_root,
                    polatory_root=polatory_root,
                    scratch=scratch,
                    records=records,
                )
                artifacts.append(
                    record_file(
                        model,
                        staging,
                        "model",
                        dimension=dim,
                        family=family,
                        fitted=None,
                    )
                )
                artifacts.append(
                    record_file(
                        interpolant,
                        staging,
                        "interpolant",
                        dimension=dim,
                        family=family,
                        fitted=True,
                        observation_layout="values_only",
                    )
                )

            composite_model = dim_root / "composite.model"
            composite_interpolant = dim_root / "composite.interpolant"
            run_cli(
                cli=cli,
                args=[
                    "create-model",
                    "--dim",
                    str(dim),
                    "--rbf",
                    "gau",
                    "1",
                    "5",
                    "aniso",
                    *ANISOTROPY[dim],
                    "exp",
                    "0.5",
                    "2",
                    "aniso",
                    *ANISOTROPY[dim],
                    "--nug",
                    "0.125",
                    "--deg",
                    "0",
                    "--out",
                    str(composite_model),
                ],
                run_id=f"legacy-model-dim{dim}-composite",
                staging=staging,
                repo_root=repo_root,
                polatory_root=polatory_root,
                scratch=scratch,
                records=records,
            )
            run_cli(
                cli=cli,
                args=[
                    "fit",
                    "--in",
                    str(values),
                    "--dim",
                    str(dim),
                    "--model",
                    str(composite_model),
                    "--tol",
                    "1e-8",
                    "--out",
                    str(composite_interpolant),
                ],
                run_id=f"legacy-interpolant-dim{dim}-composite",
                staging=staging,
                repo_root=repo_root,
                polatory_root=polatory_root,
                scratch=scratch,
                records=records,
            )
            artifacts.append(
                record_file(
                    composite_model,
                    staging,
                    "model",
                    dimension=dim,
                    family="composite:gau+exp",
                    fitted=None,
                )
            )
            artifacts.append(
                record_file(
                    composite_interpolant,
                    staging,
                    "interpolant",
                    dimension=dim,
                    family="composite:gau+exp",
                    fitted=True,
                    observation_layout="values_only",
                )
            )

            hermite = dim_root / "th3-hermite.interpolant"
            run_cli(
                cli=cli,
                args=[
                    "fit",
                    "--in",
                    str(source_fixtures / VALUE_FIXTURE[dim]),
                    "--grad-in",
                    str(source_fixtures / GRADIENT_FIXTURE[dim]),
                    "--dim",
                    str(dim),
                    "--rbf",
                    "th3",
                    "1",
                    "0.25",
                    "aniso",
                    *ANISOTROPY[dim],
                    "--deg",
                    "1",
                    "--tol",
                    "1e-8",
                    "--grad-tol",
                    "1e-8",
                    "--out",
                    str(hermite),
                ],
                run_id=f"legacy-interpolant-dim{dim}-th3-hermite",
                staging=staging,
                repo_root=repo_root,
                polatory_root=polatory_root,
                scratch=scratch,
                records=records,
            )
            artifacts.append(
                record_file(
                    hermite,
                    staging,
                    "interpolant",
                    dimension=dim,
                    family="th3",
                    fitted=True,
                    observation_layout="mixed_value_full_gradient",
                )
            )

            variogram = dim_root / "variogram.differential-only"
            variogram_args = [
                "variogram",
                "--in",
                str(values),
                "--dim",
                str(dim),
                "--lag-dist",
                "0.5",
                "--num-lags",
                "4",
            ]
            if dim > 1:
                variogram_args.append("--aniso")
            variogram_args.extend(["--out", str(variogram)])
            run_cli(
                cli=cli,
                args=variogram_args,
                run_id=f"legacy-variogram-dim{dim}-differential-only",
                staging=staging,
                repo_root=repo_root,
                polatory_root=polatory_root,
                scratch=scratch,
                records=records,
            )
            artifacts.append(
                record_file(
                    variogram,
                    staging,
                    "variogram_set",
                    dimension=dim,
                    import_scope="differential_only_not_accepted_for_import",
                )
            )

        corruptions = write_corruptions(staging, artifacts)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "id": "polatory-4a30beb-windows-x86_64-legacy-matrix",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "authority": "canonical",
            "polatory_commit": POLATORY_COMMIT,
            "polatory_cli": {
                "size": cli.stat().st_size,
                "sha256": sha256_file(cli),
                "distribution": "not_redistributed",
            },
            "platform_layout": {
                "os": "windows",
                "architecture": "x86_64",
                "byte_order": "little",
                "double": {"format": "IEEE-754 binary64", "bytes": 8},
                "size_t_bytes": struct.calcsize("P"),
                "eigen_index_bytes": 8,
                "bool_bytes": struct.calcsize("?"),
                "matrix_storage": "Eigen dynamic row-major raw storage",
                "format_properties": [
                    "no magic",
                    "no version",
                    "implicit object kind",
                    "implicit dimension",
                    "no checksum",
                    "no length limit",
                    "trailing bytes unchecked",
                ],
            },
            "coverage": {
                "dimensions": [1, 2, 3],
                "families": list(FAMILIES),
                "model_variants": ["per_family", "composite", "nugget", "anisotropy"],
                "interpolant_variants": ["values_only", "mixed_value_full_gradient"],
                "variogram_import_scope": "differential_only",
            },
            "runs": records,
            "artifacts": artifacts,
            "corruption_cases": corruptions,
            "known_gap": (
                "Unfitted Interpolant artifacts are not constructible through the frozen CLI; "
                "the downstream import-boundary decision must decide whether to add a "
                "source-linked diagnostic writer."
            ),
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        write_checksums(staging)
        os.replace(staging, output)
    except BaseException:
        # Preserve the exact staging path for forensic inspection; never delete
        # a partially generated evidence directory implicitly.
        raise
    finally:
        scratch_resolved = scratch.resolve()
        temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
        if (
            scratch_resolved.parent == temp_root
            and scratch_resolved.name.startswith("rapidrbf-legacy-materialize-")
        ):
            shutil.rmtree(scratch_resolved, ignore_errors=True)
        else:
            raise RuntimeError(f"refusing to remove unexpected scratch path {scratch_resolved}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--polatory-root",
        type=pathlib.Path,
        default=pathlib.Path(r"D:\CODE\polatory"),
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path(
            "oracle/fixtures/legacy/windows-x86_64-polatory-4a30beb"
        ),
    )
    args = parser.parse_args()
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    output = args.output
    if not output.is_absolute():
        output = repo_root / output
    materialize(repo_root, args.polatory_root.resolve(), output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
