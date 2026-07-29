"""One-command runner for the issue-45 throwaway diagnosis."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
ISSUE_41 = ROOT.parent / "instrumented_faer_corpus_qualification_throwaway"
INPUTS = ROOT / "inputs"
EXTRACTED = INPUTS / "extracted"
EVIDENCE = ROOT / "evidence"
TARGET = ROOT / "target"
RAW_FEEDBACK_OUTPUT = INPUTS / "feedback-output.raw.json"
FEEDBACK_OUTPUT = EVIDENCE / "feedback-loop.json"
DIAGNOSIS_OUTPUT = EVIDENCE / "diagnosis-evidence.json"
SUMMARY_OUTPUT = EVIDENCE / "observed-results.md"
REPRODUCTION_OUTPUT = EVIDENCE / "reproduction.json"


def run(
    command: list[str],
    *,
    cwd: Path = REPOSITORY,
    timeout: int = 3600,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def native_executable(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return TARGET / "release" / f"{name}{suffix}"


def clean_output(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def format_scientific(value: float) -> str:
    return f"{value:.6e}"


def render_summary(diagnosis: dict[str, Any]) -> str:
    observations = diagnosis["observations"]
    lines = [
        "# Observed result",
        "",
        "## Disposition",
        "",
        f"`{diagnosis['disposition']}`",
        "",
        "The frozen `pack_reload_solution_relative_inf_max = 256*n*2^-53` "
        "authority is unsound for the issue-41 manufactured-RHS construction. "
        "The issue-41 candidate and factor bytes are not admitted by this result; "
        "the representative subset is not corpus requalification.",
        "",
        "## Tight feedback loop",
        "",
        "The exact issue-41 candidate path was replayed on ordinal 72 alone. "
        "It reproduced the archived factor fingerprint and metrics exactly: "
        "reconstruction and reduced backward error pass, while only the "
        "declared-solution-relative gate fails at 1.184706x its limit.",
        "",
        "## Boundary-complete diagnosis subset",
        "",
        "| Ordinal | Boundary | Frozen status | Gate | Refined frozen-b solution error | LDLT/LU reference agreement | RHS directional amplification |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for observation in observations:
        lines.append(
            "| "
            f"{observation['ordinal']} | "
            f"{observation['category']} | "
            f"`{observation['archived']['status']}` | "
            f"{format_scientific(observation['archived']['solution_threshold'])} | "
            f"{format_scientific(observation['independent_reference']['declared_solution_relative_inf'])} | "
            f"{format_scientific(observation['independent_reference']['lblt_full_pivot_lu_relative_agreement'])} | "
            f"{format_scientific(observation['frozen_rhs']['directional_forward_amplification'])} |"
        )
    lines.extend(
        [
            "",
            "## What the probes separate",
            "",
            "- **Conditioning / authority:** the ordered binary64 `b = fl(Ax)` "
            "has only a small backward perturbation, but the admitted projected "
            "sources amplify it enough that the mathematically correct frozen-b "
            "solution is outside the fixed declared-x gate. The passing M1 control "
            "stays inside the same gate.",
            "- **Candidate-local solve:** exact issue-41 LDLT, symmetric max "
            "equilibration, and independent full-pivot LU converge under "
            "105-bit residual refinement to the same frozen-b solution. None of "
            "the three routes restores the failed declared-x gate.",
            "- **Serialization / reuse:** every selected factor payload and solved "
            "correction is bit-exact across the owned-component byte round-trip.",
            "- **Source / rank authority:** the two independently pivoted refined "
            "routes agree far below the gate and reach roughly 1e-31 normalized "
            "backward error; the evidence does not support reopening exact-rank "
            "or physical-source admission.",
            "",
            "## Decision boundary",
            "",
            "This result proves a defect in the candidate-independent health "
            "authority. It does not replace that authority, requalify the 216 "
            "factors, adopt faer, run the mechanism panel, choose factor storage, "
            "or enter the 100k rung. A fresh decision ticket must define a "
            "candidate-independent reference for the same frozen `(A, b)` system "
            "with explicit oracle uncertainty and then preregister a new full-corpus "
            "qualification plan.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    run([sys.executable, str(ROOT / "prepare.py")], cwd=REPOSITORY, timeout=120)

    environment = os.environ.copy()
    environment["CARGO_INCREMENTAL"] = "0"
    environment["CARGO_TARGET_DIR"] = str(TARGET)
    run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            str(ISSUE_41 / "Cargo.toml"),
        ],
        env=environment,
    )
    run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            str(ROOT / "Cargo.toml"),
        ],
        env=environment,
    )

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    scratch = INPUTS / "feedback-scratch"
    for path in [
        scratch,
        RAW_FEEDBACK_OUTPUT,
        FEEDBACK_OUTPUT,
        DIAGNOSIS_OUTPUT,
        SUMMARY_OUTPUT,
        REPRODUCTION_OUTPUT,
    ]:
        clean_output(path)

    feedback_command = [
        str(
            native_executable(
                "rapidrbf-instrumented-faer-corpus-qualification-throwaway"
            )
        ),
        "--plan",
        str(INPUTS / "feedback-loop-plan.v1.json"),
        "--bundle-root",
        str(EXTRACTED),
        "--lane-id",
        "local-windows-x86_64",
        "--target",
        "x86_64-pc-windows-msvc",
        "--workers",
        "1",
        "--maximum-live-threads",
        "12",
        "--scratch",
        str(scratch),
        "--output",
        str(RAW_FEEDBACK_OUTPUT),
        "--source-limit",
        "1",
    ]
    feedback_process = run(feedback_command, env=environment, timeout=300)
    feedback = json.loads(RAW_FEEDBACK_OUTPUT.read_text(encoding="utf-8"))
    require(feedback["disposition"] == "NOT_ADMITTED_DIAGNOSTIC_ONLY", "loop did not go red")
    require(len(feedback["factor_sources"]) == 1, "feedback source count differs")
    source = feedback["factor_sources"][0]
    require(source["ordinal"] == 72 and source["status"] == "FAIL", "wrong failure")
    require(
        source["factor_fingerprint"]
        == "a70901bee4078889d672c4cf5cc95d91e4da0c79b335e803ff7921a79f5850ee",
        "feedback factor fingerprint differs",
    )
    require(
        source["reconstruction_relative_inf"] <= source["reconstruction_threshold"]
        and source["maximum_backward_error"] <= source["backward_threshold"]
        and source["maximum_solution_relative_inf"]
        > source["reload_solution_threshold"],
        "feedback failure shape differs",
    )
    normalized_feedback = {
        "schema": "RapidRBF/ProjectedSourceHealthFeedbackLoopReplay/v1",
        "source_observation": source,
        "issue_41_output_schema": feedback["schema"],
        "issue_41_disposition": feedback["disposition"],
        "issue_41_lane": {
            "lane_id": feedback["lane_id"],
            "target": feedback["target"],
            "configured_workers": feedback["lane"]["configured_workers"],
            "maximum_live_threads_grant": feedback["lane"][
                "maximum_live_threads_grant"
            ],
        },
        "archived_exact_match": {
            "ordinal": True,
            "status": True,
            "factor_fingerprint": True,
            "reconstruction_relative_inf": (
                source["reconstruction_relative_inf"] == 4.9749880969656822e-16
            ),
            "maximum_backward_error": (
                source["maximum_backward_error"] == 3.3864446246440891e-16
            ),
            "maximum_solution_relative_inf": (
                source["maximum_solution_relative_inf"] == 5.0372372939477827e-11
            ),
        },
        "normalization": {
            "host_timing_elided": True,
            "candidate_raw_output": "ignored local input",
        },
    }
    require(
        all(normalized_feedback["archived_exact_match"].values()),
        "feedback metrics do not exactly match the archived observation",
    )
    FEEDBACK_OUTPUT.write_text(
        json.dumps(normalized_feedback, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    diagnosis_command = [
        str(native_executable("rapidrbf-projected-source-health-diagnosis-throwaway")),
        "--diagnosis-plan",
        str(ROOT / "diagnosis-plan.v1.json"),
        "--issue-41-plan",
        str(EXTRACTED / "factor-qualification-plan.v1.json"),
        "--bundle-root",
        str(EXTRACTED),
        "--output",
        str(DIAGNOSIS_OUTPUT),
    ]
    diagnosis_process = run(diagnosis_command, env=environment, timeout=600)
    diagnosis = json.loads(DIAGNOSIS_OUTPUT.read_text(encoding="utf-8"))
    require(
        diagnosis["disposition"] == "HEALTH_AUTHORITY_DEFECT_PROVEN",
        "diagnosis disposition differs",
    )
    require(
        diagnosis["closure"]["all_failed_samples_prove_authority_defect"]
        and diagnosis["closure"]["passing_control_closes"]
        and diagnosis["closure"]["all_serialization_roundtrips_bit_exact"],
        "diagnosis closure differs",
    )

    SUMMARY_OUTPUT.write_text(render_summary(diagnosis), encoding="utf-8", newline="\n")
    reproduction = {
        "schema": "RapidRBF/ProjectedSourceHealthDiagnosisReproduction/v1",
        "commands": {
            "entrypoint": [
                "python",
                "tools/prototypes/projected_source_health_diagnosis_throwaway/run.py",
            ],
            "feedback_stdout": feedback_process.stdout.strip(),
            "diagnosis_stdout": diagnosis_process.stdout.strip(),
        },
        "outputs": {
            "feedback-loop.json": {
                "bytes": FEEDBACK_OUTPUT.stat().st_size,
                "sha256": sha256_file(FEEDBACK_OUTPUT),
            },
            "diagnosis-evidence.json": {
                "bytes": DIAGNOSIS_OUTPUT.stat().st_size,
                "sha256": sha256_file(DIAGNOSIS_OUTPUT),
            },
            "observed-results.md": {
                "bytes": SUMMARY_OUTPUT.stat().st_size,
                "sha256": sha256_file(SUMMARY_OUTPUT),
            },
        },
        "disposition": diagnosis["disposition"],
    }
    REPRODUCTION_OUTPUT.write_text(
        json.dumps(reproduction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "feedback": feedback_process.stdout.strip(),
                "diagnosis": diagnosis_process.stdout.strip(),
                "disposition": diagnosis["disposition"],
                "evidence": str(EVIDENCE.relative_to(REPOSITORY)).replace("\\", "/"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"run failed: {error}") from error
