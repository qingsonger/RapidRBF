#!/usr/bin/env python3
"""Freeze bounded Polatory Python-build failure observations.

This is deliberately a one-way, write-once evidence copier.  It copies only
the six explicitly reviewed stdout/stderr logs, never build intermediates, and
does not treat any captured failure as accepted behavioral truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any


SCHEMA_VERSION = "1.0.0"
POLATORY_COMMIT = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"
BUNDLE_NAME = "windows-x86_64-polatory-4a30beb"

# A whitelist is intentional: the capture directory also contains interrupted
# vcpkg state and a PowerShell-wrapped duplicate.  Neither belongs in the
# frozen evidence bundle.
EXPECTED_LOGS: tuple[dict[str, Any], ...] = (
    {
        "path": "setup-build-ext.raw.stdout.log",
        "run_id": "direct-setup-build-ext",
        "stream": "stdout",
        "bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    {
        "path": "setup-build-ext.raw.stderr.log",
        "run_id": "direct-setup-build-ext",
        "stream": "stderr",
        "bytes": 189,
        "sha256": "475b87101e6194a483d5ac5c27dd65e10e8152dcb8cea9c4982d44bc49f28a86",
    },
    {
        "path": "setup-vcvars.stdout.log",
        "run_id": "setup-vcvars-14.39",
        "stream": "stdout",
        "bytes": 1_970,
        "sha256": "eaf16d1b62095be11a1995cc5e576f31ccb15605e700b2f80639efda95c1827d",
    },
    {
        "path": "setup-vcvars.stderr.log",
        "run_id": "setup-vcvars-14.39",
        "stream": "stderr",
        "bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    {
        "path": "configure.stdout.log",
        "run_id": "direct-cmake-python-configure",
        "stream": "stdout",
        "bytes": 16_485,
        "sha256": "1d42f19301af2b8ca9338f4f7d59839bdf12305ddadded6b98a13b775be118da",
    },
    {
        "path": "configure.stderr.log",
        "run_id": "direct-cmake-python-configure",
        "stream": "stderr",
        "bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_verified_sources(source: pathlib.Path) -> dict[str, bytes]:
    if not source.is_dir():
        raise FileNotFoundError(f"capture directory does not exist: {source}")

    payloads: dict[str, bytes] = {}
    for expected in EXPECTED_LOGS:
        path = source / expected["path"]
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(f"expected a regular, non-symlink log: {path}")
        payload = path.read_bytes()
        actual_size = len(payload)
        actual_hash = sha256_bytes(payload)
        if actual_size != expected["bytes"] or actual_hash != expected["sha256"]:
            raise RuntimeError(
                f"capture mismatch for {path}: "
                f"expected bytes={expected['bytes']} sha256={expected['sha256']}, "
                f"got bytes={actual_size} sha256={actual_hash}"
            )
        payloads[expected["path"]] = payload
    return payloads


def stream_paths(run_id: str) -> dict[str, str]:
    matching = {
        item["stream"]: item["path"]
        for item in EXPECTED_LOGS
        if item["run_id"] == run_id
    }
    if set(matching) != {"stdout", "stderr"}:
        raise RuntimeError(f"run {run_id} does not have exactly stdout and stderr")
    return matching


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": "polatory-4a30beb-windows-x86_64-python-build-reproduction",
        "artifact_kind": "python_build_reproduction_evidence",
        "accepted_truth": False,
        "authority": "diagnostic_observation_only",
        "interpretation": (
            "These files preserve environment-specific build failure observations. "
            "They are not accepted Polatory behavior truth and must not be used as "
            "a compatibility success oracle."
        ),
        "source": {
            "repository": "polatory",
            "commit": POLATORY_COMMIT,
            "short_commit": "4a30beb",
            "tracked_files_modified_by_capture": False,
            "vcpkg_gitlink": "4b77da7fed37817f124936239197833469f1b9a8",
        },
        "platform": {
            "os": "windows",
            "os_version": "10.0.26200.0",
            "architecture": "x86_64",
        },
        "logical_placeholders": {
            "${POLATORY_ROOT}": (
                "root of the Polatory checkout at source.commit"
            ),
            "${PYTHON_BUILD_EVIDENCE}": (
                "fresh ${POLATORY_ROOT}/build-python-oracle capture directory"
            ),
            "${PYTHON}": "captured CPython 3.13.5 executable",
            "${COMSPEC}": "Windows cmd.exe",
            "${VCVARS64}": (
                "Visual Studio 2022 Community VC/Auxiliary/Build/vcvars64.bat"
            ),
            "${CMAKE}": "CMake 4.0.3 executable",
            "${CLANG_CL}": "Visual Studio LLVM x64 clang-cl 19.1.5 executable",
        },
        "tools": {
            "python": {
                "implementation": "CPython",
                "version": "3.13.5",
                "setuptools": "absent",
                "wheel": "absent",
            },
            "cmake": {"version": "4.0.3"},
            "ninja": {"version": "1.13.1"},
            "clang_cl": {"version": "19.1.5"},
            "visual_studio_developer_prompt": {"version": "17.14.11"},
            "msvc_toolset_detected_by_vcpkg": {"version": "14.44.35207"},
            "vcpkg_executable": {
                "version": (
                    "2026-03-04-"
                    "4b3e4c276b5b87a649e66341e11553e8c577459c"
                ),
                "note": "executable identity differs from source.vcpkg_gitlink",
            },
        },
        "runs": [
            {
                "id": "direct-setup-build-ext",
                "accepted_truth": False,
                "command": {
                    "argv": [
                        "${PYTHON}",
                        "setup.py",
                        "build_ext",
                        "--build-temp",
                        "${PYTHON_BUILD_EVIDENCE}/setup-build-temp",
                        "--build-lib",
                        "${PYTHON_BUILD_EVIDENCE}/setup-build-lib",
                    ],
                    "cwd": "${POLATORY_ROOT}",
                    "shell": False,
                },
                "status": {
                    "terminal_status": "exited",
                    "exit_code": 1,
                    "classification": "missing_build_requirement",
                },
                "streams": stream_paths("direct-setup-build-ext"),
                "observations": [
                    "setup.py failed at line 8 while importing setuptools.",
                    "The CMakeBuild implementation was not entered.",
                ],
            },
            {
                "id": "setup-vcvars-14.39",
                "accepted_truth": False,
                "command": {
                    "argv": [
                        "${COMSPEC}",
                        "/d",
                        "/s",
                        "/c",
                        "\"${VCVARS64}\" -vcvars_ver=14.39 && set",
                    ],
                    "cwd": "${POLATORY_ROOT}",
                    "shell": False,
                    "command_interpreter_payload_index": 4,
                },
                "status": {
                    "terminal_status": "exited",
                    "exit_code": 1,
                    "classification": "requested_msvc_toolset_absent",
                },
                "streams": stream_paths("setup-vcvars-14.39"),
                "observations": [
                    "Visual Studio Developer Command Prompt was version 17.14.11.",
                    "vcvars64 reported that toolset directory 14.39 was not found.",
                    "The unchanged setup.py invokes this helper before CMake configure.",
                ],
            },
            {
                "id": "direct-cmake-python-configure",
                "accepted_truth": False,
                "command": {
                    "argv": [
                        "${CMAKE}",
                        "-S",
                        "${POLATORY_ROOT}",
                        "-B",
                        "${PYTHON_BUILD_EVIDENCE}",
                        "-G",
                        "Ninja",
                        "-DCMAKE_BUILD_TYPE=Release",
                        "-DCMAKE_CXX_COMPILER=${CLANG_CL}",
                        (
                            "-DCMAKE_TOOLCHAIN_FILE=${POLATORY_ROOT}/"
                            "vcpkg/scripts/buildsystems/vcpkg.cmake"
                        ),
                        (
                            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY="
                            "${PYTHON_BUILD_EVIDENCE}/python-package/polatory"
                        ),
                        "-DVCPKG_TARGET_TRIPLET=x64-windows",
                        "-DBUILD_BENCHMARKS=OFF",
                        "-DBUILD_CLI=OFF",
                        "-DBUILD_EXAMPLES=OFF",
                        "-DBUILD_PYTHON_BINDINGS=ON",
                        "-DBUILD_TESTS=OFF",
                        "-DPOLATORY_VERSION=0.1.0",
                    ],
                    "cwd": "${POLATORY_ROOT}",
                    "shell": False,
                    "environment_setup": {
                        "vcvars64": "${VCVARS64}",
                        "vcvars64_arguments": [],
                    },
                },
                "status": {
                    "terminal_status": "bounded_wrapper_timeout",
                    "wrapper_exit": 124,
                    "child_exit": "unknown",
                    "classification": "dependency_bootstrap_interrupted",
                    "configure_completed": False,
                    "build_invoked": False,
                },
                "streams": stream_paths("direct-cmake-python-configure"),
                "observations": [
                    "vcpkg planned 86 packages and the log ends at install 56/86.",
                    "No CMakeCache.txt or build.ninja was produced.",
                    "The _core target was not invoked.",
                ],
            },
        ],
        "evidence_files": [dict(item) for item in EXPECTED_LOGS],
        "exclusions": [
            {
                "path": "setup-build-ext.stderr.log",
                "reason": (
                    "PowerShell NativeCommandError wrapper; superseded by the raw "
                    "setup-build-ext.raw.stderr.log"
                ),
            },
            {
                "path": "setup-build-ext.stdout.log",
                "reason": (
                    "PowerShell-captured duplicate; superseded by the raw stdout log"
                ),
            },
            {
                "path": "CMakeFiles/",
                "reason": "interrupted configure intermediate, not stable evidence",
            },
            {
                "path": "vcpkg_installed/",
                "reason": "interrupted dependency-install state, not stable evidence",
            },
        ],
        "limitations": [
            (
                "The direct CMake run did not reach compilation, so the statically "
                "identified SdfDataGenerator constructor mismatch was not a "
                "dynamically observed failure in this capture."
            ),
            (
                "wrapper_exit=124 belongs to the bounded outer runner; the CMake "
                "child exit status was not captured and remains unknown."
            ),
        ],
    }


def write_exclusive(path: pathlib.Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def validate_bundle(output: pathlib.Path, manifest: dict[str, Any]) -> None:
    expected_paths = {item["path"] for item in EXPECTED_LOGS} | {"manifest.json"}
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise RuntimeError(
            f"unexpected frozen file set: expected={sorted(expected_paths)}, "
            f"actual={sorted(actual_paths)}"
        )

    by_path = {item["path"]: item for item in manifest["evidence_files"]}
    for expected in EXPECTED_LOGS:
        frozen = output / expected["path"]
        payload = frozen.read_bytes()
        recorded = by_path[expected["path"]]
        if len(payload) != recorded["bytes"]:
            raise RuntimeError(f"frozen size mismatch: {frozen}")
        if sha256_bytes(payload) != recorded["sha256"]:
            raise RuntimeError(f"frozen SHA256 mismatch: {frozen}")

    loaded = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if loaded != manifest:
        raise RuntimeError("serialized manifest differs from in-memory manifest")
    if loaded["accepted_truth"] is not False:
        raise RuntimeError("build failure evidence must not be accepted truth")
    if any(run["accepted_truth"] is not False for run in loaded["runs"]):
        raise RuntimeError("every captured build run must remain observation-only")
    cmake_status = next(
        run["status"]
        for run in loaded["runs"]
        if run["id"] == "direct-cmake-python-configure"
    )
    if cmake_status["wrapper_exit"] != 124 or cmake_status["child_exit"] != "unknown":
        raise RuntimeError("bounded CMake status lost wrapper/child distinction")


def freeze(source: pathlib.Path, output: pathlib.Path) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing bundle: {output}")

    payloads = read_verified_sources(source)
    manifest = build_manifest()

    output.parent.mkdir(parents=True, exist_ok=True)
    # exist_ok=False is the write-once publication boundary and also closes the
    # race between the preflight existence check and bundle creation.
    output.mkdir(exist_ok=False)
    for expected in EXPECTED_LOGS:
        write_exclusive(output / expected["path"], payloads[expected["path"]])

    serialized = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    write_exclusive(output / "manifest.json", serialized)
    validate_bundle(output, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze reviewed Polatory Python-build failure logs once."
    )
    parser.add_argument(
        "--source",
        type=pathlib.Path,
        default=pathlib.Path(r"D:\CODE\polatory\build-python-oracle"),
        help="capture directory containing the six reviewed raw logs",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("oracle") / "fixtures" / "python-build" / BUNDLE_NAME,
        help=(
            "write-once destination "
            "(relative paths are resolved from the repository)"
        ),
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    output = args.output
    if not output.is_absolute():
        output = repo_root / output
    freeze(args.source.resolve(), output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
