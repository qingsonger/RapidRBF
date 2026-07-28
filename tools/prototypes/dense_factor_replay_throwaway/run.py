#!/usr/bin/env python3
"""Driver for the captured local/coarse dense-factor Wayfinder prototype.

This is deliberately a throwaway prototype driver. It refuses to bless files
that the capture manifest does not reference, removes only a byte-verified
duplicate pending capture, and writes only schema-marked summary files it owns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import uuid
from typing import Any, Iterable, Mapping, Sequence


PROTOTYPE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROTOTYPE_DIR.parents[2]
CAPTURE_DIR = PROTOTYPE_DIR / "capture"
REPLAY_DIR = PROTOTYPE_DIR / "replay"
DEFAULT_RESULTS_DIR = PROTOTYPE_DIR / "results"
DEFAULT_CAPTURE_BUILD_DIR = CAPTURE_DIR / "build-clangcl"
DEFAULT_REPLAY_TARGET_DIR = REPLAY_DIR / "target"
DEFAULT_POLATORY_SOURCE = Path(
    os.environ.get("RAPIDRBF_POLATORY_SOURCE", "D:/CODE/polatory")
)
CAPTURE_SCHEMA = "rapidrbf-dense-factor-corpus-v1"
LOCK_SCHEMA = "rapidrbf-dense-factor-corpus-lock-v2"
UI_SCHEMA = "rapidrbf-dense-factor-ui-summary-v1"
MANAGED_SCHEMAS = {
    UI_SCHEMA,
    "rapidrbf-dense-factor-replay-v1",
    "rapidrbf-dense-factor-replay-summary-v1",
    "rapidrbf-factor-replay-summary-v1",
    "rapidrbf-factor-replay-bootstrap-v1",
}
REPLAY_BACKENDS = ("faer", "nalgebra", "mkl")
NATIVE_CLOSURE_FILES = (
    "lib/intel64/mkl_intel_lp64_dll.lib",
    "lib/intel64/mkl_sequential_dll.lib",
    "lib/intel64/mkl_core_dll.lib",
    "bin/mkl_core.2.dll",
    "bin/mkl_sequential.2.dll",
    "bin/mkl_def.2.dll",
    "bin/mkl_avx2.2.dll",
)


class DriverError(RuntimeError):
    """A user-actionable failure that should not print a Python traceback."""


def _display_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    rendered = _display_command(command)
    print(f"+ {rendered}", flush=True)
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            check=True,
            text=True,
            capture_output=capture,
        )
    except FileNotFoundError as exc:
        raise DriverError(f"command was not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        if capture:
            if exc.stdout:
                print(exc.stdout, end="" if exc.stdout.endswith("\n") else "\n")
            if exc.stderr:
                print(
                    exc.stderr,
                    file=sys.stderr,
                    end="" if exc.stderr.endswith("\n") else "\n",
                )
        raise DriverError(
            f"command failed with exit code {exc.returncode}: {rendered}"
        ) from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DriverError(f"required JSON file is missing: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DriverError(f"cannot read JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DriverError(f"expected a JSON object in {path}")
    return value


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(_json_bytes(value))
    except FileExistsError as exc:
        raise DriverError(f"refusing to replace existing file: {path}") from exc


def _write_managed_json(path: Path, value: Any) -> None:
    """Atomically replace only a summary/replay file carrying a known schema."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = _load_json(path)
        schema = existing.get("schema")
        if schema not in MANAGED_SCHEMAS:
            raise DriverError(
                f"refusing to replace unrecognized existing JSON at {path}; "
                f"found schema {schema!r}"
            )

    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    _write_new_json(temporary, value)
    try:
        os.replace(temporary, path)
    except OSError as exc:
        raise DriverError(f"cannot publish managed JSON at {path}: {exc}") from exc


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
    except OSError as exc:
        raise DriverError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


def _safe_manifest_member(corpus_root: Path, relative: str) -> Path:
    if not relative or "\\" in relative:
        raise DriverError(f"unsafe corpus member path: {relative!r}")
    member = PurePosixPath(relative)
    if (
        member.is_absolute()
        or member.as_posix() != relative
        or "." in member.parts
        or ".." in member.parts
        or any(":" in part for part in member.parts)
    ):
        raise DriverError(f"unsafe corpus member path: {relative!r}")

    path = corpus_root.joinpath(*member.parts)
    root_resolved = corpus_root.resolve()
    path_resolved = path.resolve()
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise DriverError(f"corpus member escapes capture root: {relative!r}") from exc
    if path.is_symlink():
        raise DriverError(f"corpus member must not be a symlink: {relative!r}")
    return path


def _referenced_files(manifest: Mapping[str, Any]) -> set[str]:
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise DriverError("capture manifest has no records")

    referenced: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise DriverError(f"capture record {index} is not an object")
        files = record.get("files")
        if not isinstance(files, dict) or not files:
            raise DriverError(
                f"capture record {record.get('record_id', index)!r} has no files"
            )
        for logical_name, relative in files.items():
            if not isinstance(logical_name, str) or not isinstance(relative, str):
                raise DriverError(
                    f"capture record {record.get('record_id', index)!r} "
                    "contains a non-string file entry"
                )
            referenced.add(relative)
    return referenced


def _actual_capture_files(corpus_root: Path) -> set[str]:
    actual: set[str] = set()
    for path in corpus_root.rglob("*"):
        if path.is_symlink():
            raise DriverError(f"capture output contains a symlink: {path}")
        if path.is_file():
            actual.add(path.relative_to(corpus_root).as_posix())
    return actual


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lock_corpus(
    corpus_root: Path,
    capture_executable: Path,
    polatory_source: Path,
) -> dict[str, Any]:
    raw_manifest_path = corpus_root / "manifest.raw.json"
    manifest = _load_json(raw_manifest_path)
    if manifest.get("schema") != CAPTURE_SCHEMA:
        raise DriverError(
            f"capture schema mismatch: expected {CAPTURE_SCHEMA!r}, "
            f"found {manifest.get('schema')!r}"
        )

    referenced = _referenced_files(manifest)
    expected = {"manifest.raw.json", *referenced}
    actual = _actual_capture_files(corpus_root)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise DriverError(
            "capture manifest references missing files: " + ", ".join(missing)
        )
    if extra:
        raise DriverError(
            "capture output contains unreferenced files; refusing to bless stale "
            "data: " + ", ".join(extra)
        )

    entries: dict[str, dict[str, Any]] = {}
    for relative in sorted(expected):
        path = _safe_manifest_member(corpus_root, relative)
        sha256, size = _sha256_file(path)
        entries[relative] = {"bytes": size, "sha256": sha256}

    capture_cpp_sha256, capture_cpp_bytes = _sha256_file(
        CAPTURE_DIR / "capture.cpp"
    )
    cmake_sha256, cmake_bytes = _sha256_file(CAPTURE_DIR / "CMakeLists.txt")
    executable_sha256, executable_bytes = _sha256_file(capture_executable)
    generator_provenance = {
        "capture/capture.cpp": {
            "bytes": capture_cpp_bytes,
            "sha256": capture_cpp_sha256,
        },
        "capture/CMakeLists.txt": {
            "bytes": cmake_bytes,
            "sha256": cmake_sha256,
        },
        "capture_executable": {
            "bytes": executable_bytes,
            "sha256": executable_sha256,
        },
    }

    native_root = (
        polatory_source.resolve()
        / "build"
        / "vcpkg_installed"
        / "x64-windows"
    )
    native_files: dict[str, dict[str, Any]] = {}
    for relative in NATIVE_CLOSURE_FILES:
        path = native_root.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise DriverError(
                f"registered native closure member is missing: {path}"
            )
        sha256, size = _sha256_file(path)
        native_files[relative] = {"bytes": size, "sha256": sha256}

    lock_body = {
        "schema": LOCK_SCHEMA,
        "capture_schema": manifest["schema"],
        "hash_algorithm": "sha256",
        "record_count": len(manifest["records"]),
        "referenced_payload_count": len(referenced),
        "files": entries,
        "generator_provenance": generator_provenance,
        "native_artifacts": {
            "coordinate": (
                "intel-mkl 2023.0.0#2; Windows x86_64; LP64; sequential"
            ),
            "runtime_identity": "Intel oneMKL 2023.0-Product Build 20221128",
            "files": native_files,
        },
    }
    lock = {
        **lock_body,
        "corpus_sha256": _canonical_sha256(lock_body),
    }
    _write_new_json(corpus_root / "manifest.lock.json", lock)
    return lock


def _verify_locked_corpus(corpus_root: Path, expected_digest: str) -> None:
    lock = _load_json(corpus_root / "manifest.lock.json")
    if lock.get("schema") != LOCK_SCHEMA:
        raise DriverError(f"existing corpus has an unrecognized lock: {corpus_root}")
    if lock.get("corpus_sha256") != expected_digest:
        raise DriverError(
            f"existing corpus lock digest does not match {expected_digest}: "
            f"{corpus_root}"
        )
    digest_body = {
        key: value for key, value in lock.items() if key != "corpus_sha256"
    }
    actual_digest = _canonical_sha256(digest_body)
    if actual_digest != expected_digest:
        raise DriverError(
            "existing corpus lock body does not reproduce its digest: "
            f"{corpus_root}"
        )

    entries = lock.get("files")
    if not isinstance(entries, dict):
        raise DriverError(f"existing corpus lock has no file table: {corpus_root}")
    manifest = _load_json(corpus_root / "manifest.raw.json")
    manifest_expected = {"manifest.raw.json", *_referenced_files(manifest)}
    if lock.get("capture_schema") != manifest.get("schema"):
        raise DriverError(
            f"existing corpus lock capture schema does not match: {corpus_root}"
        )
    if lock.get("record_count") != len(manifest.get("records", [])):
        raise DriverError(
            f"existing corpus lock record count does not match: {corpus_root}"
        )
    if lock.get("referenced_payload_count") != len(manifest_expected) - 1:
        raise DriverError(
            f"existing corpus lock payload count does not match: {corpus_root}"
        )
    if not isinstance(lock.get("generator_provenance"), dict):
        raise DriverError(
            f"existing corpus lock has no generator provenance: {corpus_root}"
        )
    native_artifacts = lock.get("native_artifacts")
    if (
        not isinstance(native_artifacts, dict)
        or not isinstance(native_artifacts.get("files"), dict)
        or set(native_artifacts["files"]) != set(NATIVE_CLOSURE_FILES)
    ):
        raise DriverError(
            f"existing corpus lock has an incomplete native closure: {corpus_root}"
        )
    if set(entries) != manifest_expected:
        raise DriverError(
            f"existing corpus lock does not exactly cover its manifest: {corpus_root}"
        )
    actual = _actual_capture_files(corpus_root)
    expected_actual = {*entries, "manifest.lock.json"}
    if actual != expected_actual:
        missing = sorted(expected_actual - actual)
        extra = sorted(actual - expected_actual)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("extra " + ", ".join(extra))
        raise DriverError(
            f"existing locked corpus has an unexpected file set ({'; '.join(detail)}): "
            f"{corpus_root}"
        )
    for relative, expected in entries.items():
        if not isinstance(relative, str) or not isinstance(expected, dict):
            raise DriverError(f"malformed lock entry in {corpus_root}")
        path = _safe_manifest_member(corpus_root, relative)
        sha256, size = _sha256_file(path)
        if sha256 != expected.get("sha256") or size != expected.get("bytes"):
            raise DriverError(f"existing locked corpus was modified: {path}")


def _configure_and_build_capture(args: argparse.Namespace) -> Path:
    if args.capture_exe is not None:
        executable = args.capture_exe.resolve()
        if not executable.is_file():
            raise DriverError(f"capture executable does not exist: {executable}")
        return executable

    build_dir = args.capture_build_dir.resolve()
    polatory_source = args.polatory_source.resolve()
    eigen3_dir = (
        args.eigen3_dir.resolve()
        if args.eigen3_dir is not None
        else polatory_source
        / "build"
        / "vcpkg_installed"
        / "x64-windows"
        / "share"
        / "eigen3"
    )
    generator = (
        ["-G", "Visual Studio 17 2022", "-A", "x64", "-T", "ClangCL"]
        if os.name == "nt"
        else []
    )
    configure = [
        args.cmake,
        *generator,
        "-S",
        str(CAPTURE_DIR),
        "-B",
        str(build_dir),
        f"-DPOLATORY_SOURCE_DIR={polatory_source}",
        f"-DPOLATORY_EIGEN3_DIR={eigen3_dir}",
        "-DCMAKE_BUILD_TYPE=Release",
        *args.cmake_arg,
    ]
    _run(configure, cwd=PROTOTYPE_DIR)
    _run(
        [
            args.cmake,
            "--build",
            str(build_dir),
            "--config",
            "Release",
            "--target",
            "rapidrbf_dense_factor_capture",
        ],
        cwd=PROTOTYPE_DIR,
    )

    suffix = ".exe" if os.name == "nt" else ""
    candidates = [
        build_dir / "Release" / f"rapidrbf_dense_factor_capture{suffix}",
        build_dir / f"rapidrbf_dense_factor_capture{suffix}",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise DriverError(
        "capture build succeeded but the executable was not found at: "
        + ", ".join(str(path) for path in candidates)
    )


def _remove_duplicate_capture(staging: Path, staging_parent: Path) -> None:
    if (
        staging.is_symlink()
        or staging.name != "capture-pending"
        or staging.parent.resolve() != staging_parent.resolve()
    ):
        raise DriverError(f"refusing to remove unsafe capture staging: {staging}")
    try:
        shutil.rmtree(staging)
    except OSError as exc:
        raise DriverError(
            f"cannot remove verified duplicate capture staging {staging}: {exc}"
        ) from exc


def _capture_and_publish(
    executable: Path, results_dir: Path, polatory_source: Path
) -> tuple[Path, dict[str, Any], Path | None]:
    staging_parent = results_dir / "staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    # A fixed pending slot bounds failed/duplicate captures to one directory.
    # A failed capture remains available for inspection and must be dealt with
    # explicitly before another recapture can start.
    staging = staging_parent / "capture-pending"
    if staging.exists():
        raise DriverError(
            "capture staging is already occupied; inspect or remove the prior "
            f"generated capture before retrying: {staging}"
        )
    staging.mkdir()

    _run([str(executable), str(staging)], cwd=CAPTURE_DIR)
    lock = _lock_corpus(staging, executable, polatory_source)
    digest = str(lock["corpus_sha256"])
    destination = results_dir / "corpora" / f"sha256-{digest}"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        _verify_locked_corpus(destination, digest)
        lock = _load_json(destination / "manifest.lock.json")
        _remove_duplicate_capture(staging, staging_parent)
        print(
            "Locked corpus already exists; removed the verified duplicate "
            f"capture staging at {staging}",
            flush=True,
        )
    else:
        try:
            staging.rename(destination)
        except FileExistsError:
            _verify_locked_corpus(destination, digest)
            lock = _load_json(destination / "manifest.lock.json")
            _remove_duplicate_capture(staging, staging_parent)
        else:
            print(f"Published locked corpus: {destination}", flush=True)
    return destination, lock, None


def _build_replay(args: argparse.Namespace) -> Path:
    if args.replay_exe is not None:
        executable = args.replay_exe.resolve()
        if not executable.is_file():
            raise DriverError(f"replay executable does not exist: {executable}")
        return executable

    target_dir = args.replay_target_dir.resolve()
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(target_dir)
    environment.setdefault(
        "RAPIDRBF_MKL_ROOT",
        str(
            args.polatory_source.resolve()
            / "build"
            / "vcpkg_installed"
            / "x64-windows"
        ),
    )
    profile_args = ["--release"] if args.profile == "release" else []
    _run(
        [
            args.cargo,
            "build",
            "--locked",
            "--manifest-path",
            str(REPLAY_DIR / "Cargo.toml"),
            *profile_args,
        ],
        cwd=REPLAY_DIR,
        env=environment,
    )

    suffix = ".exe" if os.name == "nt" else ""
    executable = (
        target_dir
        / args.profile
        / f"rapidrbf-dense-factor-replay-throwaway{suffix}"
    )
    if not executable.is_file():
        raise DriverError(
            f"replay build succeeded but the executable is missing: {executable}"
        )
    return executable


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    if not stripped:
        raise DriverError("replay produced neither an output file nor JSON stdout")
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
        for line in reversed(stripped.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                value = candidate
                break
    if not isinstance(value, dict):
        raise DriverError("could not find a JSON object in replay stdout")
    return value


def _expand_replay_args(
    tokens: Iterable[str],
    *,
    manifest: Path,
    lock: Path,
    output: Path,
    corpus: Path,
) -> list[str]:
    replacements = {
        "{manifest}": str(manifest),
        "{lock}": str(lock),
        "{output}": str(output),
        "{corpus}": str(corpus),
    }
    expanded: list[str] = []
    for token in tokens:
        value = token
        for marker, replacement in replacements.items():
            value = value.replace(marker, replacement)
        expanded.append(value)
    return expanded


def _backend_key(value: Any) -> str:
    name = str(value or "").lower()
    return "mkl" if "mkl" in name else name


def _scope_key(record: str | None, backend: str | None) -> str:
    if record is None and backend is None:
        return "all"
    label_parts: list[str] = []
    for name, value in (("record", record), ("backend", backend)):
        if value is None:
            continue
        slug = "".join(
            character if character.isalnum() or character in "-._" else "-"
            for character in value
        ).strip("-._")
        label_parts.append(f"{name}-{slug[:48] or 'empty'}")
    identity = json.dumps(
        {"record": record, "backend": backend},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{'__'.join(label_parts)}--{hashlib.sha256(identity).hexdigest()[:12]}"


def _requested_scope(
    manifest: Mapping[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    records = _record_index(manifest)
    record_ids = [str(record.get("record_id") or "") for record in records]
    if not record_ids or any(not record_id for record_id in record_ids):
        raise DriverError("capture manifest has a record without a record_id")
    if len(set(record_ids)) != len(record_ids):
        raise DriverError("capture manifest contains duplicate record_id values")
    if args.record is not None and args.record not in record_ids:
        raise DriverError(f"requested record is not in the locked corpus: {args.record}")

    expected_records = [args.record] if args.record is not None else record_ids
    expected_backends = (
        [args.backend] if args.backend is not None else list(REPLAY_BACKENDS)
    )
    return {
        "key": _scope_key(args.record, args.backend),
        "kind": (
            "full"
            if args.record is None and args.backend is None
            else "filtered"
        ),
        "record_filter": args.record,
        "backend_filter": args.backend,
        "expected_record_ids": expected_records,
        "expected_backends": expected_backends,
        "expected_attempt_count": len(expected_records) * len(expected_backends),
    }


def _scope_output_dir(
    results_dir: Path, corpus_digest: str, scope: Mapping[str, Any]
) -> Path:
    root = results_dir / "summaries" / f"sha256-{corpus_digest}"
    if scope.get("kind") == "full":
        return root
    return root / "scopes" / str(scope["key"])


def _run_replay(
    executable: Path,
    corpus_root: Path,
    lock: Mapping[str, Any],
    results_dir: Path,
    args: argparse.Namespace,
    scope: Mapping[str, Any],
) -> tuple[dict[str, Any], Path]:
    manifest = corpus_root / "manifest.raw.json"
    lock_path = corpus_root / "manifest.lock.json"
    replay_stage = results_dir / "staging" / f"replay-{scope['key']}-pending.json"
    replay_stage.parent.mkdir(parents=True, exist_ok=True)
    if replay_stage.exists():
        raise DriverError(
            "replay staging is already occupied; inspect or remove the prior "
            f"generated replay before retrying: {replay_stage}"
        )

    if args.replay_arg:
        replay_args = _expand_replay_args(
            args.replay_arg,
            manifest=manifest,
            lock=lock_path,
            output=replay_stage,
            corpus=corpus_root,
        )
    else:
        replay_args = [str(manifest), "--output", str(replay_stage)]
        if args.backend is not None:
            replay_args.extend(["--backend", args.backend])
        if args.record is not None:
            replay_args.extend(["--record", args.record])

    environment = os.environ.copy()
    environment.update(
        {
            "RAPIDRBF_FACTOR_CORPUS": str(corpus_root),
            "RAPIDRBF_FACTOR_CORPUS_MANIFEST": str(manifest),
            "RAPIDRBF_FACTOR_CORPUS_LOCK": str(lock_path),
            "RAPIDRBF_FACTOR_REPLAY_OUTPUT": str(replay_stage),
        }
    )
    completed = _run(
        [str(executable), *replay_args],
        cwd=REPLAY_DIR,
        env=environment,
        capture=True,
    )
    if completed.stdout:
        print(
            completed.stdout,
            end="" if completed.stdout.endswith("\n") else "\n",
            flush=True,
        )
    if completed.stderr:
        print(
            completed.stderr,
            file=sys.stderr,
            end="" if completed.stderr.endswith("\n") else "\n",
        )

    replay = (
        _load_json(replay_stage)
        if replay_stage.is_file()
        else _parse_json_stdout(completed.stdout)
    )
    stable_replay = _sanitize_summary_value(replay)
    if not isinstance(stable_replay, dict):
        raise DriverError("replay summary normalization did not produce an object")
    digest = str(lock["corpus_sha256"])
    published = _scope_output_dir(results_dir, digest, scope) / "replay.json"
    _write_managed_json(published, stable_replay)
    if replay_stage.is_file():
        replay_stage.unlink()
    return stable_replay, published


def _relative_for_summary(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<outside-results-root>"


def _record_index(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    keys = (
        "record_id",
        "panel_id",
        "case_id",
        "role",
        "assembly_variant",
        "assembly_authority",
        "matrix_kind",
        "registered_rank_expectation",
        "semantic_rank_state",
        "scalar_order",
        "polynomial_order",
        "reduced_order",
    )
    result: list[dict[str, Any]] = []
    records = manifest.get("records")
    if not isinstance(records, list):
        return result
    for record in records:
        if isinstance(record, dict):
            result.append({key: record.get(key) for key in keys})
    return result


def _m3_status(
    records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    canonical = [
        str(record.get("record_id"))
        for record in records
        if str(record.get("record_id", "")).startswith("M3-")
        and record.get("assembly_variant") == "canonical-row-channel-map"
    ]
    literal = [
        str(record.get("record_id"))
        for record in records
        if str(record.get("record_id", "")).startswith("M3-")
        and record.get("assembly_variant") != "canonical-row-channel-map"
    ]
    collected_ids = {
        str(attempt.get("record_id"))
        for attempt in attempts
        if isinstance(attempt, Mapping)
        and str(
            attempt.get("collection_state")
            or attempt.get("attempt_state")
            or attempt.get("state")
            or ""
        ).startswith("COLLECTED")
    }
    both_collected = bool(canonical and literal) and bool(
        collected_ids.intersection(canonical)
        and collected_ids.intersection(literal)
    )
    replay_corpus = replay.get("corpus")
    replay_audit = (
        replay_corpus.get("m3_assembly_audit")
        if isinstance(replay_corpus, Mapping)
        else None
    )
    result: dict[str, Any] = {
        "state": "COLLECTED, UNJUDGED" if both_collected else "EVIDENCE_MISSING",
        "canonical_records": canonical,
        "literal_records": literal,
        "comparison": "mechanical disagreement only; no semantic verdict",
    }
    if replay_audit is not None:
        result["replay_audit"] = _sanitize_summary_value(replay_audit)
        audit_items = (
            replay_audit if isinstance(replay_audit, list) else [replay_audit]
        )
        if audit_items and all(
            isinstance(item, Mapping)
            and str(item.get("state", "")).startswith("COLLECTED")
            for item in audit_items
        ):
            result["state"] = "COLLECTED, UNJUDGED"
    return result


def _sanitize_summary_value(value: Any) -> Any:
    """Remove host/run-specific locations from a stable UI summary."""

    omitted_keys = {
        "manifest_directory",
        "manifest_path",
        "output_path",
        "staging_path",
        "working_directory",
        "root",
        "lib",
        "bin",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_summary_value(item)
            for key, item in value.items()
            if str(key) not in omitted_keys
        }
    if isinstance(value, list):
        return [_sanitize_summary_value(item) for item in value]
    return value


def _coverage(
    scope: Mapping[str, Any], attempts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    expected = {
        (str(record_id), str(backend))
        for record_id in scope["expected_record_ids"]
        for backend in scope["expected_backends"]
    }
    observed_counts: dict[tuple[str, str], int] = {}
    collected: set[tuple[str, str]] = set()
    uncollected: list[dict[str, str]] = []
    for attempt in attempts:
        pair = (
            str(attempt.get("record_id") or ""),
            _backend_key(attempt.get("backend")),
        )
        observed_counts[pair] = observed_counts.get(pair, 0) + 1
        collection_state = str(
            attempt.get("collection_state")
            or attempt.get("attempt_state")
            or attempt.get("state")
            or ""
        )
        if collection_state.startswith("COLLECTED"):
            collected.add(pair)
        else:
            uncollected.append(
                {
                    "record_id": pair[0],
                    "backend": pair[1],
                    "collection_state": collection_state or "NOT_REPORTED",
                    "backend_observation": str(
                        attempt.get("attempt_state") or "NOT_REPORTED"
                    ),
                }
            )

    observed = set(observed_counts)
    missing = sorted(expected - collected)
    unexpected = sorted(observed - expected)
    duplicates = sorted(
        (record_id, backend, count)
        for (record_id, backend), count in observed_counts.items()
        if count != 1
    )
    complete = (
        collected == expected
        and observed == expected
        and not duplicates
        and len(attempts) == len(expected)
    )

    def pairs(values: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
        return [
            {"record_id": record_id, "backend": backend}
            for record_id, backend in values
        ]

    return {
        "state": "COMPLETE" if complete else "INCOMPLETE",
        "complete": complete,
        "expected_attempt_count": len(expected),
        "observed_attempt_count": len(attempts),
        "collected_pair_count": len(collected.intersection(expected)),
        "missing_or_uncollected_pairs": pairs(missing),
        "unexpected_pairs": pairs(unexpected),
        "duplicate_pairs": [
            {"record_id": record_id, "backend": backend, "count": count}
            for record_id, backend, count in duplicates
        ],
        "uncollected_attempts": uncollected,
    }


def _normalize_summary(
    manifest: Mapping[str, Any],
    lock: Mapping[str, Any],
    replay: Mapping[str, Any],
    *,
    scope: Mapping[str, Any] | None = None,
    corpus_root: Path,
    replay_path: Path,
    results_dir: Path,
) -> dict[str, Any]:
    if scope is None:
        scope = _requested_scope(
            manifest, argparse.Namespace(record=None, backend=None)
        )
    raw_attempts = replay.get("attempts")
    attempts = (
        [
            _sanitize_summary_value(attempt)
            for attempt in raw_attempts
            if isinstance(attempt, dict)
        ]
        if isinstance(raw_attempts, list)
        else []
    )
    records = _record_index(manifest)
    coverage = _coverage(scope, attempts)
    evidence_state = (
        "COLLECTED, UNJUDGED"
        if coverage["complete"]
        else "EVIDENCE_MISSING"
    )
    artifact_closure = replay.get("artifact_closure")
    if artifact_closure is None:
        artifact_closure = {
            "state": "EVIDENCE_MISSING",
            "note": "consult each attempt; no global artifact closure was reported",
        }

    summary: dict[str, Any] = {
        "schema": UI_SCHEMA,
        "evidence_state": evidence_state,
        "judgement": "UNJUDGED",
        "scope": {
            **scope,
            "coverage": coverage,
        },
        "corpus": {
            "schema": manifest.get("schema"),
            "lock_schema": lock.get("schema"),
            "generator": manifest.get("generator"),
            "polatory_commit": manifest.get("polatory_commit"),
            "compiler": manifest.get("compiler"),
            "build_mode": manifest.get("build_mode"),
            "floating_point_mode": manifest.get("floating_point_mode"),
            "eigen_version": manifest.get("eigen_version"),
            "projected_matrix_assembly": manifest.get(
                "projected_matrix_assembly"
            ),
            "projected_rhs_assembly": manifest.get("projected_rhs_assembly"),
            "sha256": lock.get("corpus_sha256"),
            "raw_manifest_sha256": (
                lock.get("files", {})
                .get("manifest.raw.json", {})
                .get("sha256")
            ),
            "generator_provenance": lock.get("generator_provenance"),
            "native_artifacts": _sanitize_summary_value(
                lock.get("native_artifacts")
            ),
            "record_count": len(records),
            "records": records,
        },
        "policy": _sanitize_summary_value(
            replay.get(
                "policy",
                {
                    "selection": "UNJUDGED",
                    "semantic_rank_source": "NOT_INFERRED_FROM_BACKENDS",
                },
            )
        ),
        "attempts": attempts,
        "controls": _sanitize_summary_value(replay.get("controls", [])),
        "artifact_closure": _sanitize_summary_value(artifact_closure),
        "m3_literal_canonical": _m3_status(records, attempts, replay),
        "replay": {
            "schema": replay.get("schema"),
            "status": replay.get("status"),
        },
        "paths": {
            "corpus": _relative_for_summary(corpus_root, results_dir),
            "manifest": _relative_for_summary(
                corpus_root / "manifest.raw.json", results_dir
            ),
            "lock": _relative_for_summary(
                corpus_root / "manifest.lock.json", results_dir
            ),
            "replay": _relative_for_summary(replay_path, results_dir),
        },
    }
    return summary


def _publish_summary(
    summary: Mapping[str, Any],
    *,
    results_dir: Path,
    corpus_digest: str,
    scope: Mapping[str, Any] | None = None,
) -> tuple[Path, Path | None]:
    if scope is None:
        summary_scope = summary.get("scope")
        scope = (
            summary_scope
            if isinstance(summary_scope, Mapping)
            else {"key": "all", "kind": "full"}
        )
    content_addressed = (
        _scope_output_dir(results_dir, corpus_digest, scope) / "summary.json"
    )
    _write_managed_json(content_addressed, summary)
    current: Path | None = None
    if scope.get("kind") == "full":
        current = results_dir / "summary.json"
        _write_managed_json(current, summary)
    return content_addressed, current


def _resolve_locked_corpus(
    args: argparse.Namespace, results_dir: Path
) -> tuple[Path, dict[str, Any]]:
    corpus_root: Path | None = (
        args.corpus.resolve() if args.corpus is not None else None
    )
    if corpus_root is None:
        current = results_dir / "summary.json"
        if current.is_file():
            current_summary = _load_json(current)
            digest = (
                current_summary.get("corpus", {}).get("sha256")
                if isinstance(current_summary.get("corpus"), Mapping)
                else None
            )
            if isinstance(digest, str) and digest:
                candidate = results_dir / "corpora" / f"sha256-{digest}"
                if candidate.is_dir():
                    corpus_root = candidate

    if corpus_root is None:
        corpora_root = results_dir / "corpora"
        candidates = (
            sorted(
                path
                for path in corpora_root.glob("sha256-*")
                if path.is_dir() and (path / "manifest.lock.json").is_file()
            )
            if corpora_root.is_dir()
            else []
        )
        if len(candidates) == 1:
            corpus_root = candidates[0].resolve()
        elif not candidates:
            raise DriverError(
                "no locked corpus is available for replay-only; run --recapture "
                "or pass --corpus"
            )
        else:
            raise DriverError(
                "multiple locked corpora are available; pass --corpus explicitly"
            )

    if not corpus_root.is_dir():
        raise DriverError(f"locked corpus directory does not exist: {corpus_root}")
    lock = _load_json(corpus_root / "manifest.lock.json")
    digest = lock.get("corpus_sha256")
    if not isinstance(digest, str) or not digest:
        raise DriverError(f"locked corpus has no digest: {corpus_root}")
    _verify_locked_corpus(corpus_root, digest)
    return corpus_root, lock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Configure/build the frozen C++ capture, content-lock its manifest "
            "and referenced payloads, build the locked Rust replay, run it, and "
            "publish deterministic UI summaries."
        )
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--recapture",
        action="store_true",
        help="run the complete capture -> lock -> replay pipeline",
    )
    actions.add_argument(
        "--replay-only",
        "--replay",
        dest="replay_only",
        action="store_true",
        help="verify an existing locked corpus, then build and run only the replay",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=f"generated artifact root (default: {DEFAULT_RESULTS_DIR})",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        help=(
            "locked corpus directory for --replay-only (default: corpus named "
            "by results/summary.json, or the sole locked corpus)"
        ),
    )
    parser.add_argument(
        "--polatory-source",
        type=Path,
        default=DEFAULT_POLATORY_SOURCE,
        help="clean Polatory checkout at the frozen capture commit",
    )
    parser.add_argument(
        "--eigen3-dir",
        type=Path,
        help="Eigen3 CMake package directory (default: frozen Polatory vcpkg tree)",
    )
    parser.add_argument("--cmake", default="cmake", help="CMake executable")
    parser.add_argument(
        "--cmake-arg",
        action="append",
        default=[],
        metavar="ARG",
        help="extra configure argument; repeat as needed",
    )
    parser.add_argument(
        "--capture-build-dir",
        type=Path,
        default=DEFAULT_CAPTURE_BUILD_DIR,
        help=f"C++ build directory (default: {DEFAULT_CAPTURE_BUILD_DIR})",
    )
    parser.add_argument(
        "--capture-exe",
        type=Path,
        help="use an existing frozen capture executable instead of building",
    )
    parser.add_argument("--cargo", default="cargo", help="Cargo executable")
    parser.add_argument(
        "--replay-target-dir",
        type=Path,
        default=DEFAULT_REPLAY_TARGET_DIR,
        help=f"Cargo target directory (default: {DEFAULT_REPLAY_TARGET_DIR})",
    )
    parser.add_argument(
        "--profile",
        choices=("release", "debug"),
        default="release",
        help="Rust build profile (default: release)",
    )
    parser.add_argument(
        "--replay-exe",
        type=Path,
        help="use an existing replay executable instead of building",
    )
    parser.add_argument(
        "--replay-arg",
        action="append",
        default=[],
        metavar="TOKEN",
        help=(
            "replace the default Rust CLI arguments; repeat per token. "
            "Supported placeholders: {manifest}, {lock}, {output}, {corpus}"
        ),
    )
    parser.add_argument(
        "--backend",
        choices=("faer", "nalgebra", "mkl"),
        help="limit the default replay command to one backend",
    )
    parser.add_argument(
        "--record",
        help="limit the default replay command to one record id",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not (args.recapture or args.replay_only):
        parser.error("no action selected; use --recapture or --replay-only")

    try:
        results_dir = args.results_dir.resolve()
        if results_dir == Path(results_dir.anchor) or results_dir == REPO_ROOT:
            raise DriverError(f"unsafe results directory: {results_dir}")
        results_dir.mkdir(parents=True, exist_ok=True)

        if args.recapture:
            capture_executable = _configure_and_build_capture(args)
            corpus_root, lock, _ = _capture_and_publish(
                capture_executable, results_dir, args.polatory_source
            )
        else:
            corpus_root, lock = _resolve_locked_corpus(args, results_dir)
        manifest = _load_json(corpus_root / "manifest.raw.json")
        scope = _requested_scope(manifest, args)
        replay_executable = _build_replay(args)
        replay, replay_path = _run_replay(
            replay_executable, corpus_root, lock, results_dir, args, scope
        )
        summary = _normalize_summary(
            manifest,
            lock,
            replay,
            scope=scope,
            corpus_root=corpus_root,
            replay_path=replay_path,
            results_dir=results_dir,
        )
        content_addressed, current = _publish_summary(
            summary,
            results_dir=results_dir,
            corpus_digest=str(lock["corpus_sha256"]),
            scope=scope,
        )
    except DriverError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Evidence state: {summary['evidence_state']}")
    print(
        "Requested coverage: "
        f"{summary['scope']['coverage']['collected_pair_count']}/"
        f"{summary['scope']['coverage']['expected_attempt_count']}"
    )
    print(f"Scoped summary: {content_addressed}")
    if current is not None:
        print(f"Default TUI summary: {current}")
    else:
        print("Default TUI summary: unchanged (filtered replay)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
