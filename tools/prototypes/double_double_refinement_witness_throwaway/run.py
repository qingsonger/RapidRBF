"""Controller for the frozen Issue 56 root-bound refinement witness cohort."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from controller_observer import observe_process
from preflight_journal import (
    PreflightJournal,
    stream_record,
    verify_preflight_journal,
)


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
CANDIDATE = ROOT.parent / "instrumented_faer_candidate_binding_throwaway"
LANES = ROOT.parent / "instrumented_faer_lane_provisioning_throwaway"
PLAN = ROOT / "factor-qualification-plan.v1.json"
TRANSPORT = ROOT / "transport-manifest.v1.json"
CONTRACT = ROOT / "execution-contract.v1.json"
ROOT_BOUND_FRESH_PLAN = (
    ROOT.parent
    / "root_bound_terminal_plan_throwaway"
    / "fresh-cohort-plan.v1.json"
)
ROOT_BOUND_MODEL = ROOT.parent / "root_bound_terminal_plan_throwaway" / "model.py"
ROOT_BOUND_PREFLIGHT = (
    ROOT.parent / "root_bound_terminal_plan_throwaway" / "preflight.py"
)
ROOT_BOUND_AGGREGATE = (
    ROOT.parent / "root_bound_terminal_plan_throwaway" / "aggregate.py"
)
CONTROLLER_PLAN = (
    ROOT.parent
    / "controller_thread_evidence_plan_throwaway"
    / "controller-evidence-plan.v1.json"
)
CONTROLLER_MODEL = (
    ROOT.parent / "controller_thread_evidence_plan_throwaway" / "model.py"
)
CONTROLLER_HELPER = ROOT / "controller_helper.rs"
WITNESS_PLAN = (
    ROOT.parent
    / "repaired_projected_solve_diagnosis_throwaway"
    / "next-experiment-plan.v1.json"
)
AUTHORITY = (
    ROOT.parent
    / "projected_factor_health_authority_throwaway"
    / "authority-profile.v1.json"
)
REQUALIFICATION_PLAN = (
    ROOT.parent
    / "projected_factor_health_authority_throwaway"
    / "requalification-plan.v1.json"
)

WITNESS_PLAN_SHA256 = (
    "7018a1a33d601076ff17b6824068ada146039fa57aab5b1cf71793cbe6d13d60"
)
ISSUE41_PLAN_SHA256 = (
    "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce"
)
REFERENCE_SHA256 = (
    "6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a"
)
AUTHORITY_SHA256 = (
    "c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6"
)
REQUALIFICATION_PLAN_SHA256 = (
    "3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829"
)
BINDING_SHA256 = (
    "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
)
CONTROLLER_PLAN_SHA256 = (
    "347cd33670d4f53c3d0b439fcc01085081f019324fdf23f107d2b5e32b4ceea4"
)
ISSUE49_SOURCE_BINDING_SHA256 = (
    "54a5c04609562963a4eb73af82a101197d42a1298e46f06bd3c8caf7c69c54b8"
)
ROOT_BOUND_FRESH_PLAN_SHA256 = (
    "720723f0ebef2b7a7d6b19878d1547cf28ed5029fb37dad4f69a1e1b0130a68a"
)
ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256 = (
    "1370ecd1ee86ca569d53b5f474dc861879ae252c34544599d5fb2c2e84ca0409"
)
ROOT_BOUND_PREFLIGHT_SOURCE_BINDING_SHA256 = (
    "3d85a473bcf6efffd309c22cb6682369741814eb504e3a497fac46e0eba4d391"
)
ROOT_BOUND_PREFLIGHT_WORKFLOW_SHA256 = (
    "e164d49f6821d07c1c1d43392ace093b0ada82a61c6b1405b96f6cfbe84d628f"
)
PINNED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
}
TARGETS = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "linux-x86_64-glibc": "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}
PROFILES = (
    {"workers": 1, "maximum_live_threads": 12},
    {"workers": 2, "maximum_live_threads": 12},
    {"workers": 8, "maximum_live_threads": 16},
)
UNCHANGED_EXECUTION_PATHS = {
    "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.toml": (
        ROOT / "Cargo.toml"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.lock": (
        ROOT / "Cargo.lock"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/src/main.rs": (
        ROOT / "src/main.rs"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/factor-qualification-plan.v1.json": (
        ROOT / "factor-qualification-plan.v1.json"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/transport-manifest.v1.json": (
        ROOT / "transport-manifest.v1.json"
    ),
    "tools/prototypes/repaired_projected_solve_diagnosis_throwaway/next-experiment-plan.v1.json": (
        WITNESS_PLAN
    ),
    "tools/prototypes/projected_factor_health_authority_throwaway/authority-profile.v1.json": (
        AUTHORITY
    ),
    "tools/prototypes/projected_factor_health_authority_throwaway/requalification-plan.v1.json": (
        REQUALIFICATION_PLAN
    ),
}
UNCHANGED_EXECUTION_SHA256 = {
    "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.toml": (
        "34e00566234d6e74e33a0a222e47f0438e68156f64eecfe6d99b4db400188fdc"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.lock": (
        "a3e690fe628fa78934bc0b22ed5a7f13e7f90644e73eea25621d52967365e89e"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/src/main.rs": (
        "fffed0348e1eb73b09abd2e760d0d5a534903a842539ed93d635b273e762c4cd"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/factor-qualification-plan.v1.json": (
        "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/transport-manifest.v1.json": (
        "42b1e236975da60b3204c2656d73ed25cef32ef7615f9481e02ff2519eddb4c5"
    ),
    "tools/prototypes/repaired_projected_solve_diagnosis_throwaway/next-experiment-plan.v1.json": (
        "7018a1a33d601076ff17b6824068ada146039fa57aab5b1cf71793cbe6d13d60"
    ),
    "tools/prototypes/projected_factor_health_authority_throwaway/authority-profile.v1.json": (
        "c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6"
    ),
    "tools/prototypes/projected_factor_health_authority_throwaway/requalification-plan.v1.json": (
        "3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829"
    ),
}
CONTROLLER_BINDING_PATHS = {
    "tools/prototypes/double_double_refinement_witness_throwaway/run.py": (
        ROOT / "run.py"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/controller_observer.py": (
        ROOT / "controller_observer.py"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/controller_helper.rs": (
        CONTROLLER_HELPER
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/preflight_journal.py": (
        ROOT / "preflight_journal.py"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/verify_cohort.py": (
        ROOT / "verify_cohort.py"
    ),
    "tools/prototypes/double_double_refinement_witness_throwaway/execution-contract.v1.json": (
        ROOT / "execution-contract.v1.json"
    ),
    "tools/prototypes/root_bound_terminal_plan_throwaway/fresh-cohort-plan.v1.json": (
        ROOT_BOUND_FRESH_PLAN
    ),
    "tools/prototypes/root_bound_terminal_plan_throwaway/model.py": (
        ROOT_BOUND_MODEL
    ),
    "tools/prototypes/root_bound_terminal_plan_throwaway/preflight.py": (
        ROOT_BOUND_PREFLIGHT
    ),
    "tools/prototypes/root_bound_terminal_plan_throwaway/aggregate.py": (
        ROOT_BOUND_AGGREGATE
    ),
    "tools/prototypes/controller_thread_evidence_plan_throwaway/controller-evidence-plan.v1.json": (
        CONTROLLER_PLAN
    ),
    "tools/prototypes/controller_thread_evidence_plan_throwaway/model.py": (
        CONTROLLER_MODEL
    ),
    "tools/prototypes/instrumented_faer_lane_provisioning_throwaway/collect_lane_identity.py": (
        LANES / "collect_lane_identity.py"
    ),
    "tools/prototypes/instrumented_faer_lane_provisioning_throwaway/lane-contract.v1.json": (
        LANES / "lane-contract.v1.json"
    ),
    ".github/workflows/ready-gated-double-double-refinement-witness.yml": (
        REPOSITORY
        / ".github/workflows/ready-gated-double-double-refinement-witness.yml"
    ),
}
SUPPORTED = "REFINEMENT_ROUTE_SUPPORTED_FOR_FULL_CORPUS_PLAN"
REJECTED = "REFINEMENT_ROUTE_REJECTED_DIAGNOSTIC_ONLY"
INVALID = "INVALID_UNJUDGED"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 3600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {list(command)!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def git_value(*arguments: str) -> str:
    return run(["git", *arguments], cwd=REPOSITORY, timeout=60).stdout.strip()


def git_blob(relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        timeout=60,
    )
    require(completed.returncode == 0, f"HEAD blob is absent: {relative}")
    return completed.stdout


def verify_static_authority() -> dict[str, Any]:
    require(
        sha256_file(ROOT_BOUND_FRESH_PLAN) == ROOT_BOUND_FRESH_PLAN_SHA256,
        "root-bound fresh-cohort plan differs",
    )
    require(
        sha256_file(CONTROLLER_PLAN) == CONTROLLER_PLAN_SHA256,
        "controller-valid plan differs",
    )
    require(sha256_file(WITNESS_PLAN) == WITNESS_PLAN_SHA256, "witness plan differs")
    require(sha256_file(PLAN) == ISSUE41_PLAN_SHA256, "issue-41 plan differs")
    require(sha256_file(AUTHORITY) == AUTHORITY_SHA256, "authority differs")
    require(
        sha256_file(REQUALIFICATION_PLAN) == REQUALIFICATION_PLAN_SHA256,
        "requalification plan differs",
    )
    verifier = run([sys.executable, "verify_binding.py"], cwd=CANDIDATE)
    manifest = json.loads(
        (CANDIDATE / "binding-manifest.v1.json").read_text(encoding="utf-8")
    )
    require(manifest["binding_sha256"] == BINDING_SHA256, "candidate binding differs")
    for relative, expected in UNCHANGED_EXECUTION_SHA256.items():
        require(
            sha256_bytes(git_blob(relative)) == expected,
            f"unchanged Issue 49 execution byte differs: {relative}",
        )
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(
        contract["root_bound_fresh_cohort_plan_sha256"]
        == ROOT_BOUND_FRESH_PLAN_SHA256
        and contract["accepted_root_bound_controller_binding_sha256"]
        == ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256
        and contract["candidate_binding_sha256"] == BINDING_SHA256
        and contract["witness_plan_sha256"] == WITNESS_PLAN_SHA256
        and contract["reference_manifest_sha256"] == REFERENCE_SHA256
        and contract["maximum_attempts"] == 1
        and contract["required_run_attempt"] == 1,
        "Issue 56 execution contract differs",
    )
    workflow = CONTROLLER_BINDING_PATHS[
        ".github/workflows/ready-gated-double-double-refinement-witness.yml"
    ].read_text(encoding="utf-8")
    for action, commit in PINNED_ACTIONS.items():
        require(
            f"{action}@{commit}" in workflow,
            f"workflow action pin differs: {action}",
        )
    witness = json.loads(WITNESS_PLAN.read_text(encoding="utf-8"))
    issue_41 = json.loads(PLAN.read_text(encoding="utf-8"))
    require(
        sha256_file(LANES / "lane-contract.v1.json")
        == issue_41["authority"]["lane_contract"]["sha256"],
        "lane contract differs",
    )
    require(
        [item["ordinal"] for item in witness["witness_corpus"]]
        == [0, 36, 69, 72, 106, 150],
        "witness inventory differs",
    )
    return {
        "root_bound_fresh_cohort_plan_sha256": ROOT_BOUND_FRESH_PLAN_SHA256,
        "accepted_root_bound_controller_binding_sha256": (
            ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256
        ),
        "root_bound_preflight_source_binding_sha256": (
            ROOT_BOUND_PREFLIGHT_SOURCE_BINDING_SHA256
        ),
        "root_bound_preflight_workflow_sha256": (
            ROOT_BOUND_PREFLIGHT_WORKFLOW_SHA256
        ),
        "controller_plan_sha256": CONTROLLER_PLAN_SHA256,
        "issue49_materialized_source_binding_sha256": (
            ISSUE49_SOURCE_BINDING_SHA256
        ),
        "witness_plan_sha256": WITNESS_PLAN_SHA256,
        "issue_41_plan_sha256": ISSUE41_PLAN_SHA256,
        "authority_profile_sha256": AUTHORITY_SHA256,
        "requalification_plan_sha256": REQUALIFICATION_PLAN_SHA256,
        "candidate_binding_sha256": BINDING_SHA256,
        "binding_verifier_stdout": verifier.stdout.strip(),
    }


def file_manifest(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for relative, path in sorted(paths.items(), key=lambda item: item[0].encode()):
        blob = git_blob(relative)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            require(
                blob == path.read_bytes(),
                f"clean checkout byte does not equal exact HEAD blob: {relative}",
            )
        result[relative] = {
            "bytes": len(blob),
            "sha256": sha256_bytes(blob),
        }
    return result


def controller_binding() -> dict[str, Any]:
    files = file_manifest(CONTROLLER_BINDING_PATHS)
    serialized = b"".join(
        relative.encode("utf-8")
        + b"\0"
        + files[relative]["sha256"].encode("ascii")
        + b"\n"
        for relative in sorted(files, key=lambda value: value.encode("utf-8"))
    )
    return {
        "algorithm": (
            "sha256(path_utf8 + NUL + lowercase_blob_sha256 + LF), "
            "sorted by UTF-8 path bytes"
        ),
        "files": files,
        "controller_binding_sha256": sha256_bytes(serialized),
    }


def source_binding() -> dict[str, Any]:
    unchanged = file_manifest(UNCHANGED_EXECUTION_PATHS)
    controller = controller_binding()
    candidate_manifest = json.loads(
        (CANDIDATE / "binding-manifest.v1.json").read_text(encoding="utf-8")
    )
    value = {
        "schema": "RapidRBF/RootBoundRefinementWitnessExecutionSourceBinding/v1",
        "git_commit": git_value("rev-parse", "HEAD"),
        "rust_toolchain": "1.85.0",
        "cargo_lock_sha256": unchanged[
            "tools/prototypes/double_double_refinement_witness_throwaway/Cargo.lock"
        ]["sha256"],
        "cargo_features": {
            "witness_crate": "default",
            "candidate": candidate_manifest["features"],
        },
        "panic_profile": "unwind",
        "candidate_binding_sha256": BINDING_SHA256,
        "controller_binding_sha256": controller["controller_binding_sha256"],
        "controller_files": controller["files"],
        "unchanged_issue49_execution_files": unchanged,
        "issue49_materialized_source_binding_sha256": (
            ISSUE49_SOURCE_BINDING_SHA256
        ),
        "controller_plan_sha256": CONTROLLER_PLAN_SHA256,
        "root_bound_fresh_cohort_plan_sha256": ROOT_BOUND_FRESH_PLAN_SHA256,
        "accepted_root_bound_controller_binding_sha256": (
            ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256
        ),
        "root_bound_preflight_source_binding_sha256": (
            ROOT_BOUND_PREFLIGHT_SOURCE_BINDING_SHA256
        ),
        "root_bound_preflight_workflow_sha256": (
            ROOT_BOUND_PREFLIGHT_WORKFLOW_SHA256
        ),
        "witness_plan_sha256": WITNESS_PLAN_SHA256,
        "accepted_reference_sha256": REFERENCE_SHA256,
        "transport_bundle_sha256": json.loads(
            TRANSPORT.read_text(encoding="utf-8")
        )["asset"]["sha256"],
        "pinned_actions": PINNED_ACTIONS,
        "accepted_issue45_refinement_source": json.loads(
            WITNESS_PLAN.read_text(encoding="utf-8")
        )["authorities"]["accepted_issue45_refinement_source"],
    }
    value["source_binding_sha256"] = canonical_sha256(value)
    return value


def native_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return (
        ROOT
        / "target"
        / "release"
        / f"rapidrbf-double-double-refinement-witness-throwaway{suffix}"
    )


def build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["CARGO_INCREMENTAL"] = "0"
    environment["RUSTUP_TOOLCHAIN"] = "1.85.0"
    return environment


def unchecked(command: Sequence[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {
            "command": list(command),
            "returncode": None,
            "stdout": "",
            "stderr": str(error),
        }
    return {
        "command": list(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def linker_identity() -> dict[str, Any]:
    if sys.platform == "win32":
        linker = shutil.which("link.exe")
        if linker is None:
            installer = Path(
                os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
            ) / "Microsoft Visual Studio/Installer/vswhere.exe"
            if installer.is_file():
                found = unchecked(
                    [
                        str(installer),
                        "-latest",
                        "-products",
                        "*",
                        "-requires",
                        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                        "-find",
                        r"VC\Tools\MSVC\**\bin\Hostx64\x64\link.exe",
                    ]
                )
                candidates = [
                    line.strip()
                    for line in found["stdout"].splitlines()
                    if line.strip()
                ]
                linker = candidates[-1] if candidates else None
        version_command = [linker, "/?"] if linker else ["link.exe", "/?"]
    else:
        linker = shutil.which("cc")
        version_command = [linker, "--version"] if linker else ["cc", "--version"]
    resolved = Path(linker).resolve() if linker else None
    return {
        "path": str(resolved) if resolved else None,
        "executable": (
            {
                "bytes": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
            }
            if resolved and resolved.is_file()
            else None
        ),
        "version": unchecked(version_command),
    }


def lane_equivalence(witness: dict[str, Any]) -> dict[str, Any]:
    python_path = Path(sys.executable).resolve()
    return {
        "lane": {
            "lane_id": witness["lane"]["lane_id"],
            "runner_label": witness["lane"]["runner_label"],
            "target": witness["lane"]["target"],
            "runner_os": witness["lane"]["runner_os"],
            "runner_arch": witness["lane"]["runner_arch"],
        },
        "runner_image": {
            "image_os": witness["github"]["image_os"],
            "image_version": witness["github"]["image_version"],
        },
        "os": {
            key: witness["host"]["os"][key]
            for key in (
                "platform_system",
                "platform_release",
                "platform_version",
                "platform_machine",
            )
        },
        "isa": {
            "native_rust_features": witness["host"]["native_rust_features"],
            "required_cpu_features": witness["lane"]["required_cpu_features"],
        },
        "rust": {
            "rustc_vv": witness["toolchain"]["rustc_verbose"]["stdout"],
            "cargo_version": witness["toolchain"]["cargo_version"]["stdout"],
            "active_toolchain": witness["toolchain"][
                "rustup_active_toolchain"
            ]["stdout"],
        },
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable_path": str(python_path),
            "executable_bytes": python_path.stat().st_size,
            "executable_sha256": sha256_file(python_path),
        },
        "linker": linker_identity(),
    }


def load_controller_model() -> Any:
    spec = importlib.util.spec_from_file_location(
        "rapidrbf_issue50_controller_model", CONTROLLER_MODEL
    )
    require(spec is not None and spec.loader is not None, "controller model unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_root_bound_model() -> Any:
    spec = importlib.util.spec_from_file_location(
        "rapidrbf_issue55_root_bound_model", ROOT_BOUND_MODEL
    )
    require(spec is not None and spec.loader is not None, "root-bound model unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_root_bound_adapter_failure(observation: dict[str, Any]) -> None:
    """Attach and independently classify the accepted structured closure record."""

    observation["terminal_policy"] = "root-bound"
    observation["root_bound_adapter_failures"] = []
    benign = [
        event
        for event in observation["event_log"]
        if event["kind"] == "benign_terminal_race"
    ]
    if not benign:
        return
    if len(benign) != 1:
        observation["invalidity"].append(
            {
                "gate": "root-bound-record",
                "error": "expected at most one root-bound reconciliation",
            }
        )
        observation["classification"] = "INVALID_CONTROLLER_EVIDENCE"
        return
    sample_id = benign[0]["sample_id"]
    error = next(
        (
            event
            for event in observation["event_log"]
            if event["kind"] == "sample_error" and event["sample_id"] == sample_id
        ),
        None,
    )
    terminal = next(
        (
            event
            for event in observation["event_log"]
            if event["kind"] == "terminal_observed"
        ),
        None,
    )
    reap = next(
        (event for event in observation["event_log"] if event["kind"] == "reaped"),
        None,
    )
    if error is None:
        observation["invalidity"].append(
            {
                "gate": "root-bound-record",
                "error": "reconciled adapter failure is absent",
            }
        )
        observation["classification"] = "INVALID_CONTROLLER_EVIDENCE"
        return
    raw = error["raw_adapter_result"]
    last_ns = observation["event_log"][-1]["monotonic_ns"]
    record = {
        "schema": "RapidRBF/RootBoundAdapterFailure/v1",
        "adapter": raw["adapter"],
        "errno": raw["errno"],
        "error_name": raw["error_name"],
        "phase": raw["phase"],
        "subject_pid": raw["subject_pid"],
        "root_pid": observation["diagnostic_pid"],
        "invocation_nonce": observation["invocation_nonce"],
        "sample_started_ns": error["sample_started_ns"],
        "sample_finished_ns": error["sample_finished_ns"],
        "terminal": (
            {
                "owner": terminal["owner"],
                "invocation_nonce": terminal["invocation_nonce"],
                "observed_ns": terminal["monotonic_ns"],
                "returncode": terminal["returncode"],
            }
            if terminal is not None
            else None
        ),
        "reap": (
            {
                "owner": reap["owner"],
                "invocation_nonce": reap["invocation_nonce"],
                "observed_ns": reap["monotonic_ns"],
            }
            if reap is not None
            else None
        ),
        "process_tree_cleanup": {
            "invocation_nonce": observation["invocation_nonce"],
            "observed_ns": last_ns + 1,
            "complete": observation["process_result"][
                "process_tree_empty_after_reap"
            ],
        },
        "prior_reconciliations": 0,
        "incomplete_sample_effect": {
            "successful_sample_delta": 0,
            "sample_error_delta": 0,
            "maximum_live_threads_delta": 0,
        },
    }
    model = load_root_bound_model()
    classification = model.classify_adapter_failure(record)
    observation["root_bound_adapter_failures"].append(
        {
            "classification": classification,
            "record": record,
        }
    )
    if classification != model.BENIGN:
        observation["invalidity"].append(
            {
                "gate": "root-bound-record",
                "error": classification,
            }
        )
        observation["classification"] = "INVALID_CONTROLLER_EVIDENCE"


def helper_observation(
    scratch: Path,
    *,
    helper_executable: Path,
    name: str,
    threads: int,
    grant: int,
    environment: dict[str, str],
    require_sample: bool,
    fault_mode: str | None = None,
) -> dict[str, Any]:
    entry = scratch / f"{name}-entry.json"
    release = scratch / f"{name}-release"
    command = [
        str(helper_executable),
        "--threads",
        str(threads),
        "--entry",
        str(entry),
        "--release",
        str(release),
    ]
    completed, observation = observe_process(
        command,
        cwd=ROOT,
        env=environment,
        timeout_seconds=5.0,
        maximum_live_threads=grant,
        candidate_entry=entry,
        candidate_output=None,
        require_candidate_entry=True,
        require_successful_sample=require_sample,
        invocation_kind=f"controller-preflight-{name}",
        fault_mode=fault_mode,
        after_first_sample=lambda: release.write_bytes(b"release\n"),
        stop_sampling_after_first_callback=True,
        sample_readiness=entry.is_file,
    )
    observation["diagnostic_streams"] = {
        "stdout": stream_record(completed.stdout),
        "stderr": stream_record(completed.stderr),
    }
    observation["helper"] = {
        "name": name,
        "requested_threads": threads,
        "returncode": completed.returncode,
        "entry": (
            {
                "bytes": entry.stat().st_size,
                "sha256": sha256_file(entry),
            }
            if entry.is_file()
            else None
        ),
    }
    return observation


def run_controller_preflight(
    environment: dict[str, str],
    *,
    journal: PreflightJournal,
    authority: dict[str, Any],
    controller: dict[str, Any],
) -> dict[str, Any]:
    identity_pass = (
        authority["root_bound_fresh_cohort_plan_sha256"]
        == ROOT_BOUND_FRESH_PLAN_SHA256
        and authority["candidate_binding_sha256"] == BINDING_SHA256
        and authority["witness_plan_sha256"] == WITNESS_PLAN_SHA256
        and controller["controller_binding_sha256"]
        == source_binding()["controller_binding_sha256"]
    )
    journal.record(
        name="issue56-authority-and-controller-binding",
        group="identity",
        passed=identity_pass,
        detail={
            "authority": authority,
            "controller_binding": controller,
        },
    )

    model = load_controller_model()
    traces: dict[str, Any | None] = {}
    for name, scenario in model.scenario_catalog().items():
        def drive(scenario: dict[str, Any] = scenario) -> dict[str, Any]:
            state = model.initial_state(scenario["grant"])
            for action in scenario["actions"]:
                state = model.reduce(state, action)
            return {
                "expected": scenario["expected"],
                "observed": state["verdict"],
                "history": state["history"],
            }

        traces[name] = journal.capture(
            name=f"pure-state-{name}",
            group="pure-state-trace",
            action=drive,
            predicate=lambda value: value["observed"] == value["expected"],
        )
    pure_state_pass = all(
        result is not None and result["observed"] == result["expected"]
        for result in traces.values()
    )
    journal.record(
        name="pure_state_traces",
        group="global-check",
        passed=pure_state_pass,
        detail={"scenario_count": len(traces)},
    )

    scratch = Path(tempfile.mkdtemp(prefix="rapidrbf-issue56-controller-preflight-"))
    observations: dict[str, Any | None] = {}
    fast_exits: list[Any | None] = []
    try:
        helper_executable = scratch / (
            "controller-helper.exe" if sys.platform == "win32" else "controller-helper"
        )
        def build_helper() -> dict[str, Any]:
            completed = run(
                [
                    "rustc",
                    str(CONTROLLER_HELPER),
                    "-C",
                    "opt-level=0",
                    "-o",
                    str(helper_executable),
                ],
                cwd=ROOT,
                env=environment,
                timeout=300,
            )
            return {
                "source_sha256": sha256_file(CONTROLLER_HELPER),
                "executable_sha256": sha256_file(helper_executable),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }

        helper_build = journal.capture(
            name="native-helper-build",
            group="helper-build",
            action=build_helper,
            predicate=lambda value: helper_executable.is_file(),
        )
        if helper_build is not None and helper_executable.is_file():
            def observe(
                name: str,
                threads: int,
                require_sample: bool,
                fault_mode: str | None = None,
            ) -> dict[str, Any]:
                return helper_observation(
                    scratch,
                    helper_executable=helper_executable,
                    name=name,
                    threads=threads,
                    grant=12,
                    environment=environment,
                    require_sample=require_sample,
                    fault_mode=fault_mode,
                )

            observations["one_thread"] = journal.capture(
                name="one-thread",
                group="native-helper-observation",
                action=lambda: observe("one-thread", 1, True),
                predicate=lambda value: (
                    value["classification"] == "PASS"
                    and 1 <= value["maximum_live_threads"] <= 12
                ),
            )
            observations["grant_plus_one"] = journal.capture(
                name="grant-plus-one",
                group="native-helper-observation",
                action=lambda: observe("grant-plus-one", 13, True),
                predicate=lambda value: (
                    value["classification"] == "VALID_CANDIDATE_OWNED_NONPASS"
                    and value["maximum_live_threads"] >= 13
                ),
            )
            for index in range(256):
                name = f"fast-exit-{index:03d}"
                fast_exits.append(
                    journal.capture(
                        name=name,
                        group="fast-exit-observation",
                        action=lambda name=name: observe(name, 1, False),
                        predicate=lambda value: (
                            value["classification"] == "PASS"
                            and value["process_result"][
                                "process_tree_empty_after_reap"
                            ]
                        ),
                    )
                )
            observations["unpaired_esrch"] = journal.capture(
                name="fault-unpaired-esrch",
                group="native-helper-observation",
                action=lambda: observe(
                    "fault-unpaired-esrch", 1, False, "unpaired-esrch"
                ),
                predicate=lambda value: (
                    value["classification"] == "INVALID_CONTROLLER_EVIDENCE"
                ),
            )
            observations["other_error"] = journal.capture(
                name="fault-non-esrch",
                group="native-helper-observation",
                action=lambda: observe(
                    "fault-non-esrch", 1, False, "non-esrch"
                ),
                predicate=lambda value: (
                    value["classification"] == "INVALID_CONTROLLER_EVIDENCE"
                ),
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    one_thread = observations.get("one_thread")
    over_grant = observations.get("grant_plus_one")
    unpaired_esrch = observations.get("unpaired_esrch")
    other_error = observations.get("other_error")
    checks = {
        "pure_state_traces": pure_state_pass,
        "one_thread_detected": (
            one_thread is not None
            and one_thread["classification"] == "PASS"
            and 1 <= one_thread["maximum_live_threads"] <= 12
        ),
        "grant_plus_one_detected": (
            over_grant is not None
            and over_grant["classification"] == "VALID_CANDIDATE_OWNED_NONPASS"
            and over_grant["maximum_live_threads"] >= 13
        ),
        "fast_exit_closure": (
            len(fast_exits) == 256
            and all(
                item is not None
                and item["classification"] == "PASS"
                and item["process_result"]["process_tree_empty_after_reap"]
                for item in fast_exits
            )
        ),
        "unpaired_esrch_invalid": (
            unpaired_esrch is not None
            and
            unpaired_esrch["classification"] == "INVALID_CONTROLLER_EVIDENCE"
        ),
        "other_sampling_error_invalid": (
            other_error is not None
            and
            other_error["classification"] == "INVALID_CONTROLLER_EVIDENCE"
        ),
        "helper_scratch_removed": not scratch.exists(),
    }
    for name, passed in checks.items():
        if name == "pure_state_traces":
            continue
        journal.record(
            name=name,
            group="global-check",
            passed=passed,
            detail={"frozen_controller_check": name},
        )
    status = "PASS" if identity_pass and all(checks.values()) else "FAIL"
    journal_identity = journal.finalize(status=status)
    return {
        "schema": "RapidRBF/RootBoundExecutionControllerZeroEntryPreflight/v1",
        "status": status,
        "candidate_backend_entries": 0,
        "factor_or_solve_calls": 0,
        "candidate_observations": 0,
        "checks": checks,
        "failed_global_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "completed_check_count": journal_identity["completed_check_count"],
        "journal": journal_identity,
    }


def run_preflight(
    lane_id: str,
    target: str,
    lane_witness_path: Path,
    output: Path,
) -> None:
    require(lane_id in TARGETS and TARGETS[lane_id] == target, "target identity differs")
    require(not output.exists(), f"preflight output must be absent: {output}")
    lane = json.loads(lane_witness_path.read_text(encoding="utf-8"))
    require(
        lane["qualification"] == "PASS"
        and lane["lane"]["lane_id"] == lane_id
        and lane["lane"]["target"] == target,
        "preflight lane witness differs",
    )
    require(
        str(lane["github"]["run_attempt"]) == "1",
        "root-bound fresh-cohort plan forbids a workflow rerun",
    )
    output.mkdir(parents=True)
    journal = PreflightJournal(
        output=output,
        lane_id=lane_id,
        target=target,
        replacement_plan_sha256=ROOT_BOUND_FRESH_PLAN_SHA256,
        lane_witness=lane_witness_path,
    )
    authority = verify_static_authority()
    environment = build_environment()
    environment["RAPIDRBF_LANE_ID"] = lane_id
    environment["RAPIDRBF_TARGET"] = target
    build = run(
        ["cargo", "build", "--release", "--locked"],
        cwd=ROOT,
        env=environment,
        timeout=3600,
    )
    executable = native_executable()
    require(executable.is_file(), "native executable missing")
    journal.mark_candidate_built()
    binary_path = output / "binary-preflight.json"
    binary = {
        "schema": "RapidRBF/UnexecutedCandidateBuildPreflight/v1",
        "status": "PASS",
        "candidate_executed": False,
        "backend_entries": 0,
        "factor_or_solve_calls": 0,
        "candidate_observations": 0,
        "lane_id": lane_id,
        "target": target,
        "native_executable": {
            "bytes": executable.stat().st_size,
            "sha256": sha256_file(executable),
        },
    }
    binary_path.write_text(json.dumps(binary, indent=2, sort_keys=True) + "\n")
    controller = run_controller_preflight(
        environment,
        journal=journal,
        authority=authority,
        controller=controller_binding(),
    )
    controller_path = output / "controller-preflight.json"
    controller_path.write_text(
        json.dumps(controller, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    binding = source_binding()
    evidence = {
        "schema": "RapidRBF/RootBoundRefinementWitnessTargetPreflight/v1",
        "status": controller["status"],
        "lane_id": lane_id,
        "target": target,
        "authority": authority,
        "source_binding": binding,
        "binary_preflight": {
            "file": binary_path.name,
            "bytes": binary_path.stat().st_size,
            "sha256": sha256_file(binary_path),
            "candidate_executed": False,
            "backend_entries": 0,
            "factor_or_solve_calls": 0,
            "candidate_observations": 0,
        },
        "controller_preflight": {
            "file": controller_path.name,
            "bytes": controller_path.stat().st_size,
            "sha256": sha256_file(controller_path),
            "status": controller["status"],
            "journal": controller["journal"],
        },
        "lane_witness": lane,
        "lane_witness_sha256": sha256_file(lane_witness_path),
        "lane_equivalence": lane_equivalence(lane),
        "native_executable": {
            "bytes": executable.stat().st_size,
            "sha256": sha256_file(executable),
        },
        "build": {
            "command": ["cargo", "build", "--release", "--locked"],
            "stdout": build.stdout.strip(),
            "stderr": build.stderr.strip(),
            "rustc": run(["rustc", "-vV"], cwd=ROOT, env=environment).stdout.strip(),
            "cargo": run(["cargo", "-V"], cwd=ROOT, env=environment).stdout.strip(),
        },
        "git_sha": git_value("rev-parse", "HEAD"),
    }
    path = output / "preflight-observation.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    (output / "preflight-observation.json.sha256").write_text(
        f"{sha256_file(path)}  preflight-observation.json\n"
    )
    require(controller["status"] == "PASS", "controller-only preflight failed")


def verify_preflight_cohort(root: Path) -> dict[str, Any]:
    paths = sorted(root.rglob("preflight-observation.json"))
    require(len(paths) == 4, f"expected four preflights, found {len(paths)}")
    observations = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    by_lane = {item["lane_id"]: item for item in observations}
    require(set(by_lane) == set(TARGETS), "preflight lane set differs")
    bindings = {
        item["source_binding"]["source_binding_sha256"] for item in observations
    }
    controllers = {
        item["source_binding"]["controller_binding_sha256"]
        for item in observations
    }
    commits = {item["git_sha"] for item in observations}
    run_coordinates = {
        (
            str(item["lane_witness"]["github"]["run_id"]),
            str(item["lane_witness"]["github"]["run_attempt"]),
            str(item["lane_witness"]["github"]["sha"]),
        )
        for item in observations
    }
    require(
        len(bindings) == 1
        and len(controllers) == 1
        and len(commits) == 1
        and len(run_coordinates) == 1,
        "preflight cohort mixed bindings",
    )
    for lane_id, target in TARGETS.items():
        item = by_lane[lane_id]
        parent = next(
            path
            for path in paths
            if json.loads(path.read_text(encoding="utf-8"))["lane_id"] == lane_id
        ).parent
        binary = item["binary_preflight"]
        controller = item["controller_preflight"]
        require(
            item["schema"]
            == "RapidRBF/RootBoundRefinementWitnessTargetPreflight/v1"
            and item["status"] == "PASS"
            and item["target"] == target
            and not binary["candidate_executed"]
            and binary["backend_entries"] == 0
            and binary["factor_or_solve_calls"] == 0
            and binary["candidate_observations"] == 0
            and controller["status"] == "PASS"
            and str(item["lane_witness"]["github"]["run_attempt"]) == "1",
            f"preflight {lane_id} failed",
        )
        require(
            (parent / binary["file"]).stat().st_size == binary["bytes"]
            and sha256_file(parent / binary["file"]) == binary["sha256"]
            and (parent / controller["file"]).stat().st_size == controller["bytes"]
            and sha256_file(parent / controller["file"]) == controller["sha256"],
            f"preflight descendants differ for {lane_id}",
        )
        journal_result = verify_preflight_journal(
            parent,
            lane_id=lane_id,
            target=target,
            replacement_plan_sha256=ROOT_BOUND_FRESH_PLAN_SHA256,
        )
        require(
            {
                name: journal_result[name]
                for name in (
                    "file",
                    "bytes",
                    "sha256",
                    "sidecar",
                    "completed_check_count",
                )
            }
            == controller["journal"],
            f"preflight journal envelope differs for {lane_id}",
        )
        sidecar = parent / "preflight-observation.json.sha256"
        require(
            sidecar.is_file()
            and sidecar.read_text(encoding="ascii").strip()
            == (
                f"{sha256_file(parent / 'preflight-observation.json')}  "
                "preflight-observation.json"
            ),
            f"preflight sidecar differs for {lane_id}",
        )
    local = source_binding()
    require(
        next(iter(bindings)) == local["source_binding_sha256"],
        "executing source differs from preflight binding",
    )
    return {
        "status": "PASS",
        "source_binding_sha256": local["source_binding_sha256"],
        "controller_binding_sha256": local["controller_binding_sha256"],
        "git_sha": next(iter(commits)),
        "workflow_coordinate": {
            "run_id": next(iter(run_coordinates))[0],
            "run_attempt": next(iter(run_coordinates))[1],
            "sha": next(iter(run_coordinates))[2],
        },
        "lanes": {
            lane: {
                "target": item["target"],
                "lane_equivalence": item["lane_equivalence"],
                "preflight_bytes": next(
                    path.stat().st_size
                    for path in paths
                    if json.loads(path.read_text(encoding="utf-8"))["lane_id"]
                    == lane
                ),
                "preflight_sha256": sha256_file(
                    next(
                        path
                        for path in paths
                        if json.loads(path.read_text(encoding="utf-8"))["lane_id"]
                        == lane
                    )
                ),
            }
            for lane, item in sorted(by_lane.items())
        },
    }


def verify_root_bound_preflight_cohort(
    path: Path,
    ready: dict[str, Any],
) -> dict[str, Any]:
    require(path.is_file(), f"root-bound preflight cohort is absent: {path}")
    sidecar = path.with_name(path.name + ".sha256")
    require(
        sidecar.is_file()
        and sidecar.read_text(encoding="ascii").strip()
        == f"{sha256_file(path)}  {path.name}",
        "root-bound preflight cohort sidecar differs",
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    identity = value["identity"]
    coordinate = ready["workflow_coordinate"]
    require(
        value["schema"] == "RapidRBF/RootBoundZeroEntryPreflightCohort/v1"
        and value["issue"] == 55
        and value["status"] == "ROOT_BOUND_FOUR_LANE_ZERO_ENTRY_PREFLIGHT_PASS"
        and value["inherited_ready_gated_check_count"] == 1108
        and value["root_bound_check_count"] == 100
        and value["scope"]
        == {
            "candidate_built": False,
            "candidate_executed": False,
            "candidate_entries": 0,
            "backend_entries": 0,
            "factor_calls": 0,
            "solve_calls": 0,
            "candidate_observations": 0,
        },
        "root-bound preflight cohort status or scope differs",
    )
    require(
        identity["git_commit"] == ready["git_sha"]
        and str(identity["run_id"]) == coordinate["run_id"]
        and str(identity["run_attempt"]) == coordinate["run_attempt"] == "1"
        and str(identity["workflow_sha"]) == coordinate["sha"] == ready["git_sha"]
        and identity["controller_binding_sha256"]
        == ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256
        and identity["source_binding_sha256"]
        == ROOT_BOUND_PREFLIGHT_SOURCE_BINDING_SHA256
        and identity["workflow_sha256"] == ROOT_BOUND_PREFLIGHT_WORKFLOW_SHA256
        and identity["candidate_binding_sha256"] == BINDING_SHA256
        and identity["witness_plan_sha256"] == WITNESS_PLAN_SHA256
        and identity["accepted_reference_sha256"] == REFERENCE_SHA256,
        "root-bound preflight identity differs",
    )
    require(
        value["required_native_reproductions"]
        == {
            "linux-proc-process-tree/group-membership": "PASS",
            "macos-arm64/macos-proc-process-tree/bsd-identity": "PASS",
            "macos-x86_64/macos-proc-process-tree/bsd-identity": "PASS",
            "windows-x86_64": "NOT_APPLICABLE_WITH_POLICY_CONTROLS_PASS",
        }
        and value["non_reuse"]
        == {
            "issue_53_observations_used": 0,
            "issue_54_diagnostic_observations_used_as_candidate_counts": 0,
            "issue_55_observations_are_candidate_counts": False,
        },
        "root-bound native reproduction or non-reuse record differs",
    )
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "identity": identity,
        "lanes": value["lanes"],
        "scope": value["scope"],
    }


def aggregate_execution_preflight(
    preflight_root: Path,
    root_bound_cohort: Path,
    output: Path,
) -> None:
    require(not output.exists(), f"preflight unlock output must be absent: {output}")
    verify_static_authority()
    ready = verify_preflight_cohort(preflight_root)
    root_bound = verify_root_bound_preflight_cohort(root_bound_cohort, ready)
    local = source_binding()
    coordinate = ready["workflow_coordinate"]
    require(
        coordinate
        == {
            "run_id": str(os.environ.get("GITHUB_RUN_ID")),
            "run_attempt": str(os.environ.get("GITHUB_RUN_ATTEMPT")),
            "sha": str(os.environ.get("GITHUB_SHA")),
        },
        "preflight aggregation workflow coordinate differs",
    )
    aggregation_sha256 = canonical_sha256(
        {
            "source_binding_sha256": local["source_binding_sha256"],
            "ready_lanes": {
                lane: ready["lanes"][lane]["preflight_sha256"]
                for lane in sorted(ready["lanes"])
            },
            "root_bound_cohort_sha256": root_bound["sha256"],
            "root_bound_aggregation_sha256": root_bound["identity"][
                "aggregation_sha256"
            ],
        }
    )
    value = {
        "schema": "RapidRBF/RootBoundRefinementWitnessExecutionUnlock/v1",
        "issue": 56,
        "status": "PASS",
        "git_sha": ready["git_sha"],
        "workflow_coordinate": coordinate,
        "root_bound_fresh_cohort_plan_sha256": ROOT_BOUND_FRESH_PLAN_SHA256,
        "accepted_root_bound_controller_binding_sha256": (
            ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256
        ),
        "execution_source_binding_sha256": local["source_binding_sha256"],
        "execution_controller_binding_sha256": local[
            "controller_binding_sha256"
        ],
        "ready_gated_preflight": ready,
        "root_bound_preflight": root_bound,
        "scope": {
            "candidate_built_for_byte_identity": True,
            "candidate_executed": False,
            "candidate_entries": 0,
            "backend_entries": 0,
            "factor_calls": 0,
            "solve_calls": 0,
            "candidate_observations": 0,
        },
        "non_reuse": {
            "issue_53_observations_used": 0,
            "issue_54_diagnostic_observations_used": 0,
            "issue_55_observations_used_as_candidate_counts": 0,
        },
        "aggregation_sha256": aggregation_sha256,
    }
    output.mkdir(parents=True)
    path = output / "execution-preflight-unlock.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    path.with_name(path.name + ".sha256").write_text(
        f"{sha256_file(path)}  {path.name}\n",
        encoding="ascii",
    )


def verify_execution_preflight(root: Path) -> dict[str, Any]:
    ready = verify_preflight_cohort(root)
    root_paths = sorted(root.rglob("root-bound-preflight-cohort.json"))
    unlock_paths = sorted(root.rglob("execution-preflight-unlock.json"))
    require(
        len(root_paths) == 1 and len(unlock_paths) == 1,
        "execution preflight release artifacts are incomplete",
    )
    root_bound = verify_root_bound_preflight_cohort(root_paths[0], ready)
    unlock_path = unlock_paths[0]
    sidecar = unlock_path.with_name(unlock_path.name + ".sha256")
    require(
        sidecar.is_file()
        and sidecar.read_text(encoding="ascii").strip()
        == f"{sha256_file(unlock_path)}  {unlock_path.name}",
        "execution preflight unlock sidecar differs",
    )
    unlock = json.loads(unlock_path.read_text(encoding="utf-8"))
    local = source_binding()
    expected_aggregation = canonical_sha256(
        {
            "source_binding_sha256": local["source_binding_sha256"],
            "ready_lanes": {
                lane: ready["lanes"][lane]["preflight_sha256"]
                for lane in sorted(ready["lanes"])
            },
            "root_bound_cohort_sha256": root_bound["sha256"],
            "root_bound_aggregation_sha256": root_bound["identity"][
                "aggregation_sha256"
            ],
        }
    )
    require(
        unlock["schema"]
        == "RapidRBF/RootBoundRefinementWitnessExecutionUnlock/v1"
        and unlock["issue"] == 56
        and unlock["status"] == "PASS"
        and unlock["git_sha"] == ready["git_sha"]
        and unlock["workflow_coordinate"] == ready["workflow_coordinate"]
        and unlock["root_bound_fresh_cohort_plan_sha256"]
        == ROOT_BOUND_FRESH_PLAN_SHA256
        and unlock["accepted_root_bound_controller_binding_sha256"]
        == ACCEPTED_ROOT_BOUND_CONTROLLER_BINDING_SHA256
        and unlock["execution_source_binding_sha256"]
        == local["source_binding_sha256"]
        and unlock["execution_controller_binding_sha256"]
        == local["controller_binding_sha256"]
        and unlock["ready_gated_preflight"] == ready
        and unlock["root_bound_preflight"] == root_bound
        and unlock["scope"]
        == {
            "candidate_built_for_byte_identity": True,
            "candidate_executed": False,
            "candidate_entries": 0,
            "backend_entries": 0,
            "factor_calls": 0,
            "solve_calls": 0,
            "candidate_observations": 0,
        }
        and unlock["non_reuse"]
        == {
            "issue_53_observations_used": 0,
            "issue_54_diagnostic_observations_used": 0,
            "issue_55_observations_used_as_candidate_counts": 0,
        }
        and unlock["aggregation_sha256"] == expected_aggregation,
        "execution preflight unlock differs",
    )
    return {
        **ready,
        "root_bound": root_bound,
        "unlock": {
            "bytes": unlock_path.stat().st_size,
            "sha256": sha256_file(unlock_path),
            "aggregation_sha256": unlock["aggregation_sha256"],
        },
    }


def verify_reference(path: Path) -> dict[str, Any]:
    require(path.is_file() and sha256_file(path) == REFERENCE_SHA256, "reference differs")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(
        manifest["schema"] == "RapidRBF/ProjectedFactorReferenceManifest/v1"
        and manifest["disposition"] == "CERTIFIED_REFERENCE"
        and manifest["certified_references"] == 537
        and manifest["indeterminate_references"] == 0
        and not manifest["candidate_inputs_observed"],
        "reference completeness or independence differs",
    )
    return {
        "schema": manifest["schema"],
        "sha256": REFERENCE_SHA256,
        "certified_references": 537,
        "candidate_inputs_observed": False,
    }


def safe_extract(bundle: Path, destination: Path) -> None:
    with zipfile.ZipFile(bundle) as archive:
        for member in archive.infolist():
            relative = Path(member.filename)
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and "\\" not in member.filename,
                f"unsafe bundle member {member.filename!r}",
            )
        archive.extractall(destination)


def verify_transport(bundle: Path) -> tuple[dict[str, Any], Path]:
    manifest = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    asset = manifest["asset"]
    require(
        bundle.stat().st_size == asset["bytes"]
        and sha256_file(bundle) == asset["sha256"],
        "transport bundle differs",
    )
    extraction = Path(
        tempfile.mkdtemp(
            prefix="rapidrbf-issue49-input-",
            dir=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())),
        )
    )
    safe_extract(bundle, extraction)
    require(
        (extraction / "factor-qualification-plan.v1.json").read_bytes()
        == PLAN.read_bytes(),
        "transported plan differs",
    )
    return manifest, extraction


def windows_thread_count(pid: int) -> int:
    from ctypes import wintypes

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Thread32First.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ThreadEntry32),
    ]
    kernel32.Thread32First.restype = wintypes.BOOL
    kernel32.Thread32Next.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ThreadEntry32),
    ]
    kernel32.Thread32Next.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot")
    entry = ThreadEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    count = 0
    try:
        success = kernel32.Thread32First(snapshot, ctypes.byref(entry))
        while success:
            if entry.th32OwnerProcessID == pid:
                count += 1
            success = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return count


def macos_thread_count(pid: int) -> int:
    class ProcTaskInfo(ctypes.Structure):
        _fields_ = [
            ("pti_virtual_size", ctypes.c_uint64),
            ("pti_resident_size", ctypes.c_uint64),
            ("pti_total_user", ctypes.c_uint64),
            ("pti_total_system", ctypes.c_uint64),
            ("pti_threads_user", ctypes.c_uint64),
            ("pti_threads_system", ctypes.c_uint64),
            ("pti_policy", ctypes.c_int32),
            ("pti_faults", ctypes.c_int32),
            ("pti_pageins", ctypes.c_int32),
            ("pti_cow_faults", ctypes.c_int32),
            ("pti_messages_sent", ctypes.c_int32),
            ("pti_messages_received", ctypes.c_int32),
            ("pti_syscalls_mach", ctypes.c_int32),
            ("pti_syscalls_unix", ctypes.c_int32),
            ("pti_csw", ctypes.c_int32),
            ("pti_threadnum", ctypes.c_int32),
            ("pti_numrunning", ctypes.c_int32),
            ("pti_priority", ctypes.c_int32),
        ]

    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    libproc.proc_pidinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    libproc.proc_pidinfo.restype = ctypes.c_int
    info = ProcTaskInfo()
    observed = libproc.proc_pidinfo(
        pid, 4, 0, ctypes.byref(info), ctypes.sizeof(info)
    )
    if observed != ctypes.sizeof(info):
        raise OSError(ctypes.get_errno(), "proc_pidinfo")
    return int(info.pti_threadnum)


def process_thread_count(pid: int) -> int:
    if sys.platform == "win32":
        return windows_thread_count(pid)
    if sys.platform == "darwin":
        return macos_thread_count(pid)
    return len(list(Path(f"/proc/{pid}/task").iterdir()))


def run_observed(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    maximum_live_threads: int,
    candidate_entry: Path,
    candidate_output: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    completed, observation = observe_process(
        command,
        cwd=cwd,
        env=env,
        timeout_seconds=float(timeout),
        maximum_live_threads=maximum_live_threads,
        candidate_entry=candidate_entry,
        candidate_output=candidate_output,
        require_candidate_entry=True,
        require_successful_sample=True,
        invocation_kind="double-double-refinement-candidate",
        terminal_policy="root-bound",
    )
    bind_root_bound_adapter_failure(observation)
    return (
        subprocess.CompletedProcess(
            completed.args,
            completed.returncode,
            completed.stdout.decode("utf-8", errors="replace"),
            completed.stderr.decode("utf-8", errors="replace"),
        ),
        observation,
    )


def execute_target(args: argparse.Namespace) -> None:
    require(
        args.lane_id in TARGETS and TARGETS[args.lane_id] == args.target,
        "target identity differs",
    )
    require(not args.output.exists(), f"output must be absent: {args.output}")
    authority = verify_static_authority()
    preflights = verify_execution_preflight(args.preflight_root)
    require(
        os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
        "root-bound fresh-cohort plan forbids a workflow rerun",
    )
    require(
        preflights["git_sha"] == git_value("rev-parse", "HEAD"),
        "preflight commit differs from executing commit",
    )
    reference = verify_reference(args.reference_manifest)
    transport, extraction = verify_transport(args.bundle)
    environment = build_environment()
    try:
        lane = json.loads(args.lane_witness.read_text(encoding="utf-8"))
        require(
            lane["qualification"] == "PASS"
            and lane["lane"]["lane_id"] == args.lane_id
            and lane["lane"]["target"] == args.target,
            "lane witness differs",
        )
        current_lane_equivalence = lane_equivalence(lane)
        require(
            current_lane_equivalence
            == preflights["lanes"][args.lane_id]["lane_equivalence"],
            "target lane/toolchain witness differs from same-attempt preflight",
        )
        build = run(
            ["cargo", "build", "--release", "--locked"],
            cwd=ROOT,
            env=environment,
            timeout=3600,
        )
        executable = native_executable()
        args.output.mkdir(parents=True)
        observations: list[dict[str, Any]] = []
        for profile in PROFILES:
            workers = profile["workers"]
            output = args.output / f"candidate-{workers}-workers.json"
            entry = args.output / f"candidate-{workers}-workers-entry.json"
            baseline = entry.with_suffix(".baseline.json")
            scratch = Path(
                tempfile.gettempdir(),
                f"rapidrbf-issue56-{args.lane_id}-{workers}-{os.getpid()}",
            )
            require(
                not output.exists()
                and not entry.exists()
                and not baseline.exists()
                and not scratch.exists(),
                "candidate paths are not fresh",
            )
            command = [
                str(executable),
                "--plan",
                str(PLAN),
                "--bundle-root",
                str(extraction),
                "--reference-manifest",
                str(args.reference_manifest),
                "--lane-id",
                args.lane_id,
                "--target",
                args.target,
                "--workers",
                str(workers),
                "--maximum-live-threads",
                str(profile["maximum_live_threads"]),
                "--entry-marker",
                str(entry),
                "--scratch",
                str(scratch),
                "--output",
                str(output),
            ]
            completed, threads = run_observed(
                command,
                cwd=ROOT,
                env=environment,
                timeout=7200,
                maximum_live_threads=profile["maximum_live_threads"],
                candidate_entry=entry,
                candidate_output=output,
            )
            controller_classification = threads["classification"]
            if (
                controller_classification == "INVALID_CONTROLLER_EVIDENCE"
                or (
                    not output.is_file()
                    and controller_classification == "PASS"
                )
            ):
                disposition = INVALID
                observations.append(
                    {
                        "workers": workers,
                        "disposition": disposition,
                        "baseline_file": baseline.name if baseline.is_file() else None,
                        "baseline_bytes": (
                            baseline.stat().st_size if baseline.is_file() else None
                        ),
                        "baseline_sha256": (
                            sha256_file(baseline) if baseline.is_file() else None
                        ),
                        "candidate_entry_file": entry.name if entry.is_file() else None,
                        "candidate_entry_bytes": (
                            entry.stat().st_size if entry.is_file() else None
                        ),
                        "candidate_entry_sha256": (
                            sha256_file(entry) if entry.is_file() else None
                        ),
                        "candidate_file": output.name if output.is_file() else None,
                        "candidate_bytes": (
                            output.stat().st_size if output.is_file() else None
                        ),
                        "candidate_sha256": (
                            sha256_file(output) if output.is_file() else None
                        ),
                        "failure": {
                            "classification": "external-controller-invalidity",
                            "returncode": completed.returncode,
                            "timed_out": threads["timed_out"],
                        },
                        "controller_observation": threads,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                )
                continue
            if not output.is_file():
                observations.append(
                    {
                        "workers": workers,
                        "disposition": REJECTED,
                        "baseline_file": (
                            baseline.name if baseline.is_file() else None
                        ),
                        "baseline_bytes": (
                            baseline.stat().st_size if baseline.is_file() else None
                        ),
                        "baseline_sha256": (
                            sha256_file(baseline) if baseline.is_file() else None
                        ),
                        "candidate_entry_file": (
                            entry.name if entry.is_file() else None
                        ),
                        "candidate_entry_bytes": (
                            entry.stat().st_size if entry.is_file() else None
                        ),
                        "candidate_entry_sha256": (
                            sha256_file(entry) if entry.is_file() else None
                        ),
                        "candidate_file": None,
                        "candidate_bytes": None,
                        "candidate_sha256": None,
                        "failure": {
                            "classification": "candidate-owned-after-entry",
                            "returncode": completed.returncode,
                            "timed_out": threads["timed_out"],
                        },
                        "controller_observation": threads,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                )
                continue
            candidate = json.loads(output.read_text(encoding="utf-8"))
            require(
                candidate["schema"]
                == "RapidRBF/DoubleDoubleRefinementWitnessLaneObservation/v1"
                and candidate["lane_id"] == args.lane_id
                and candidate["target"] == args.target
                and candidate["lane"]["configured_workers"] == workers
                and candidate["disposition"] in {SUPPORTED, REJECTED},
                "candidate observation identity differs",
            )
            profile_disposition = (
                REJECTED
                if controller_classification == "VALID_CANDIDATE_OWNED_NONPASS"
                or completed.returncode != 0
                else candidate["disposition"]
            )
            observations.append(
                {
                    "workers": workers,
                    "disposition": profile_disposition,
                    "baseline_file": baseline.name,
                    "baseline_bytes": baseline.stat().st_size,
                    "baseline_sha256": sha256_file(baseline),
                    "candidate_entry_file": entry.name,
                    "candidate_entry_bytes": entry.stat().st_size,
                    "candidate_entry_sha256": sha256_file(entry),
                    "candidate_file": output.name,
                    "candidate_bytes": output.stat().st_size,
                    "candidate_sha256": sha256_file(output),
                    "failure": (
                        {
                            "classification": "candidate-owned-after-entry",
                            "returncode": completed.returncode,
                            "timed_out": threads["timed_out"],
                        }
                        if profile_disposition == REJECTED
                        and candidate["disposition"] == SUPPORTED
                        else None
                    ),
                    "controller_observation": threads,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        if any(item["disposition"] == INVALID for item in observations):
            disposition = INVALID
        elif all(
            item["disposition"] == SUPPORTED
            and item["controller_observation"]["classification"] == "PASS"
            for item in observations
        ):
            disposition = SUPPORTED
        else:
            disposition = REJECTED
        evidence = {
            "schema": "RapidRBF/RootBoundRefinementWitnessTargetEvidence/v1",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "lane_id": args.lane_id,
            "target": args.target,
            "disposition": disposition,
            "authority": authority,
            "preflight_cohort": preflights,
            "reference_manifest": reference,
            "transport": transport,
            "lane_witness": lane,
            "lane_witness_file": {
                "bytes": args.lane_witness.stat().st_size,
                "sha256": sha256_file(args.lane_witness),
            },
            "lane_equivalence": current_lane_equivalence,
            "profiles": observations,
            "native_executable": {
                "bytes": executable.stat().st_size,
                "sha256": sha256_file(executable),
            },
            "build": {
                "stdout": build.stdout,
                "stderr": build.stderr,
                "rustc": run(
                    ["rustc", "-vV"], cwd=ROOT, env=environment
                ).stdout.strip(),
                "cargo": run(
                    ["cargo", "-V"], cwd=ROOT, env=environment
                ).stdout.strip(),
            },
            "source_binding": source_binding(),
            "git_sha": git_value("rev-parse", "HEAD"),
            "github": {
                "repository": os.environ.get("GITHUB_REPOSITORY"),
                "sha": os.environ.get("GITHUB_SHA"),
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            },
        }
        path = args.output / "target-observation.json"
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        (args.output / "target-observation.json.sha256").write_text(
            f"{sha256_file(path)}  target-observation.json\n"
        )
    finally:
        shutil.rmtree(extraction, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--aggregate-preflight", action="store_true")
    parser.add_argument("--lane-id")
    parser.add_argument("--target")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--lane-witness", type=Path)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--preflight-root", type=Path)
    parser.add_argument("--root-bound-cohort", type=Path)
    args = parser.parse_args()
    args.output = args.output.resolve()
    require(
        not (args.preflight_only and args.aggregate_preflight),
        "preflight modes are mutually exclusive",
    )
    if args.aggregate_preflight:
        require(
            args.preflight_root is not None and args.root_bound_cohort is not None,
            "preflight aggregation requires ready and root-bound evidence",
        )
        args.preflight_root = args.preflight_root.resolve()
        args.root_bound_cohort = args.root_bound_cohort.resolve()
        return args
    require(
        args.lane_id is not None and args.target is not None,
        "lane id and target are required",
    )
    require(args.lane_witness is not None, "lane witness is required")
    args.lane_witness = args.lane_witness.resolve()
    if not args.preflight_only:
        require(
            all(
                value is not None
                for value in (
                    args.bundle,
                    args.reference_manifest,
                    args.preflight_root,
                )
            ),
            "execution requires bundle, lane witness, reference, and preflight root",
        )
        args.bundle = args.bundle.resolve()
        args.reference_manifest = args.reference_manifest.resolve()
        args.preflight_root = args.preflight_root.resolve()
    return args


if __name__ == "__main__":
    try:
        parsed = parse_args()
        if parsed.aggregate_preflight:
            aggregate_execution_preflight(
                parsed.preflight_root,
                parsed.root_bound_cohort,
                parsed.output,
            )
        elif parsed.preflight_only:
            run_preflight(
                parsed.lane_id,
                parsed.target,
                parsed.lane_witness,
                parsed.output,
            )
        else:
            execute_target(parsed)
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TimeoutError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        raise SystemExit(f"double-double witness controller failed: {error}") from error
