#!/usr/bin/env python3
"""Red-capable issue-35 replay against the locked dense-factor corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


CORPUS_SHA256 = "ac282ee95062b4463d2e0a0c0ca83da454660e0e5048fa79ea3a07da280ef26e"
CANONICAL_RECORD = "M3-HERMITE-COMPOSITE-max-order-fine-canonical"
LITERAL_RECORD = "M3-HERMITE-COMPOSITE-max-order-fine-frozen-literal"
EXPECTED_BACKENDS = {"faer", "nalgebra", "onemkl-lp64-sequential"}
EXPECTED_BACKEND_COORDINATES = {
    "faer": {"cargo_lock": True, "crate": "faer", "version": "0.24.4"},
    "nalgebra": {"cargo_lock": True, "crate": "nalgebra", "version": "0.35.0"},
    "onemkl-lp64-sequential": {
        "version": "oneMKL 2023.0.0#2",
        "interface": "LP64",
        "threading": "sequential",
    },
}

# These bounds identify the already-reported mechanical symptom. They are not
# RapidRBF numerical acceptance thresholds.
MAX_REDUCED_ERROR = 1.0e-15
MAX_CANONICAL_ALPHA = 1.0e-12
MAX_CANONICAL_ETA = 1.0e-12
MIN_LITERAL_ALPHA = 1.0e-11
MIN_LITERAL_ETA = 1.0e-6
MIN_ALPHA_RATIO = 1.0e6
MIN_ETA_RATIO = 1.0e10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the canonical and frozen-literal M3 fine records on every "
            "registered dense substrate and detect the exact issue-35 symptom."
        )
    )
    parser.add_argument("--replay-exe", type=Path, required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="locked v2 corpus directory containing manifest.raw.json",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="number of canonical/literal pairs; at least 2 is required to assess repeatability",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional path for the machine-readable reproduction summary",
    )
    parser.add_argument(
        "--red-on-symptom",
        action="store_true",
        help="exit 1 when the issue-35 symptom is reproduced",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_record(executable: Path, manifest: Path, record: str) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    completed = subprocess.run(
        [str(executable), str(manifest), "--record", record],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"replay failed for {record} with {completed.returncode}:\n"
            f"{completed.stderr.strip()}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"replay emitted invalid JSON for {record}: {error}\n"
            f"stdout={completed.stdout[:1000]!r}\n"
            f"stderr={completed.stderr[:1000]!r}"
        ) from error
    return payload, elapsed


def extract_metrics(payload: dict[str, Any], record: str) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for attempt in payload.get("attempts", []):
        if attempt.get("record_id") != record:
            continue
        backend = attempt["backend"]
        correction = attempt["solve"]["full_correction"]
        input_identity = attempt["input_identity"]
        metrics[backend] = {
            "reduced_backward_error": float(attempt["solve"]["reduced_backward_error"]),
            "augmented_alpha": float(correction["captured_augmented_matrix_residual_alpha"]),
            "eta_cpd": float(correction["cpd_orthogonality_eta"]),
            "backend_version": attempt["backend_version"],
            "artifact_coordinates": attempt["artifact_closure"]["coordinates"],
            "assembly_variant": attempt["assembly_variant"],
            "assembly_authority": attempt["assembly_authority"],
            "input_identity": {
                "corpus_sha256": input_identity["corpus_sha256"],
                "b_lower_sha256": input_identity["b_lower_sha256"],
                "rhs_reduced_sha256": input_identity["rhs_reduced_sha256"],
            },
        }
    if set(metrics) != EXPECTED_BACKENDS:
        raise RuntimeError(
            f"{record} replayed backends {sorted(metrics)}, "
            f"expected {sorted(EXPECTED_BACKENDS)}"
        )
    for backend, expected in EXPECTED_BACKEND_COORDINATES.items():
        actual = metrics[backend]["artifact_coordinates"]
        if any(actual.get(key) != value for key, value in expected.items()):
            raise RuntimeError(
                f"{record} backend coordinate mismatch for {backend}: "
                f"actual={actual}, expected subset={expected}"
            )
    return metrics


def exact_repeat_match(
    observations: list[dict[str, dict[str, dict[str, Any]]]],
) -> bool:
    if len(observations) < 2:
        return False
    first = observations[0]
    return all(observation == first for observation in observations[1:])


def symptom_by_backend(
    observation: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for backend in sorted(EXPECTED_BACKENDS):
        canonical = observation["canonical"][backend]
        literal = observation["frozen_literal"][backend]
        alpha_ratio = literal["augmented_alpha"] / canonical["augmented_alpha"]
        eta_ratio = literal["eta_cpd"] / canonical["eta_cpd"]
        reproduced = (
            canonical["reduced_backward_error"] < MAX_REDUCED_ERROR
            and literal["reduced_backward_error"] < MAX_REDUCED_ERROR
            and canonical["augmented_alpha"] < MAX_CANONICAL_ALPHA
            and canonical["eta_cpd"] < MAX_CANONICAL_ETA
            and literal["augmented_alpha"] > MIN_LITERAL_ALPHA
            and literal["eta_cpd"] > MIN_LITERAL_ETA
            and alpha_ratio > MIN_ALPHA_RATIO
            and eta_ratio > MIN_ETA_RATIO
        )
        result[backend] = {
            "canonical": canonical,
            "frozen_literal": literal,
            "alpha_ratio": alpha_ratio,
            "eta_ratio": eta_ratio,
            "symptom_reproduced": reproduced,
        }
    return result


def corpus_identity(payload: dict[str, Any]) -> dict[str, Any]:
    corpus = payload["corpus"]
    return {
        "corpus_sha256": corpus["corpus_sha256"],
        "manifest_sha256": corpus["manifest_sha256"],
        "lock_schema": corpus["lock_schema"],
        "capture_schema": corpus["capture_schema"],
        "generator": corpus["generator"],
        "polatory_commit": corpus["polatory_commit"],
        "compiler": corpus["compiler"],
        "eigen_version": corpus["eigen_version"],
        "record_count": corpus["record_count"],
    }


def main() -> int:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be at least 1")

    executable = args.replay_exe.resolve(strict=True)
    corpus = args.corpus.resolve(strict=True)
    manifest = (corpus / "manifest.raw.json").resolve(strict=True)
    lock = json.loads((corpus / "manifest.lock.json").read_text(encoding="utf-8"))
    recorded_digest = lock.get("corpus_sha256", "").lower()
    lock_body = {key: value for key, value in lock.items() if key != "corpus_sha256"}
    recomputed_digest = canonical_sha256(lock_body)
    if recorded_digest != CORPUS_SHA256 or recomputed_digest != CORPUS_SHA256:
        raise RuntimeError(
            "wrong corpus identity: "
            f"recorded={recorded_digest}, recomputed={recomputed_digest}, "
            f"expected={CORPUS_SHA256}"
        )

    observations: list[dict[str, dict[str, dict[str, Any]]]] = []
    corpus_identities: list[dict[str, Any]] = []
    elapsed_seconds: list[dict[str, float]] = []
    for _ in range(args.repeat):
        canonical_payload, canonical_elapsed = run_record(
            executable, manifest, CANONICAL_RECORD
        )
        literal_payload, literal_elapsed = run_record(executable, manifest, LITERAL_RECORD)
        canonical_corpus_identity = corpus_identity(canonical_payload)
        literal_corpus_identity = corpus_identity(literal_payload)
        if canonical_corpus_identity != literal_corpus_identity:
            raise RuntimeError("canonical/literal replay corpus identities differ")
        if canonical_corpus_identity["corpus_sha256"] != CORPUS_SHA256:
            raise RuntimeError("replay did not bind the expected corpus identity")
        corpus_identities.append(canonical_corpus_identity)
        observations.append(
            {
                "canonical": extract_metrics(canonical_payload, CANONICAL_RECORD),
                "frozen_literal": extract_metrics(literal_payload, LITERAL_RECORD),
            }
        )
        elapsed_seconds.append(
            {
                "canonical": canonical_elapsed,
                "frozen_literal": literal_elapsed,
                "pair": canonical_elapsed + literal_elapsed,
            }
        )

    repeatability_assessed = len(observations) >= 2
    deterministic = exact_repeat_match(observations)
    corpus_identity_repeatable = (
        repeatability_assessed
        and all(identity == corpus_identities[0] for identity in corpus_identities[1:])
    )
    backend_results = symptom_by_backend(observations[0])
    reproduced = all(
        result["symptom_reproduced"] for result in backend_results.values()
    )
    summary = {
        "schema": "rapidrbf-m3-assembly-reproduction-v1",
        "corpus_sha256": CORPUS_SHA256,
        "corpus_lock_body_sha256_recomputed": recomputed_digest,
        "corpus_identity": corpus_identities[0],
        "corpus_identity_repeatable": corpus_identity_repeatable,
        "reproduction_script_sha256": sha256_file(Path(__file__).resolve()),
        "replay_executable": {
            "name": executable.name,
            "bytes": executable.stat().st_size,
            "sha256": sha256_file(executable),
        },
        "python": {
            "implementation": sys.implementation.name,
            "version": sys.version.split()[0],
        },
        "records": {
            "canonical": CANONICAL_RECORD,
            "frozen_literal": LITERAL_RECORD,
        },
        "repeat_count": args.repeat,
        "repeatability_assessed": repeatability_assessed,
        "key_metrics_bitwise_repeatable": (
            deterministic if repeatability_assessed else None
        ),
        "backend_results": backend_results,
        "elapsed_seconds": elapsed_seconds,
        "symptom_reproduced_on_all_backends": reproduced,
        "diagnostic_evidence_complete": (
            reproduced
            and repeatability_assessed
            and deterministic
            and corpus_identity_repeatable
        ),
        "predicate_role": "diagnostic symptom detector; not an acceptance threshold",
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if args.red_on_symptom and reproduced:
        print(
            "RED: issue 35 M3 canonical/frozen-literal residual gap reproduced "
            "on all three substrates",
            file=sys.stderr,
        )
        return 1
    if args.red_on_symptom:
        print("GREEN: exact issue-35 symptom was not reproduced", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
