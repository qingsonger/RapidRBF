"""Verify the frozen issue-41 bundle and extract only the diagnosis subset."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
ARCHIVE = INPUTS / "rapidrbf-issue41-factor-qualification-input-v1.zip"
EXTRACTED = INPUTS / "extracted"
DIAGNOSIS_PLAN = ROOT / "diagnosis-plan.v1.json"
ISSUE_41 = ROOT.parent / "instrumented_faer_corpus_qualification_throwaway"
COMMITTED_PLAN = ISSUE_41 / "factor-qualification-plan.v1.json"
ARCHIVED_CANDIDATE = (
    ISSUE_41
    / "evidence"
    / "rapidrbf-faer-corpus-windows-x86_64-6c17cd0a60b031a8a908f59b36ca501c4346960f-run-30434309514-attempt-1"
    / "windows-x86_64"
    / "qualification"
    / "candidate-1-workers.json"
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checked_file(path: Path, expected: dict[str, Any], label: str) -> bytes:
    require(path.is_file(), f"missing {label}: {path}")
    data = path.read_bytes()
    require(len(data) == expected["bytes"], f"{label} byte count differs")
    require(sha256_bytes(data) == expected["sha256"], f"{label} SHA-256 differs")
    return data


def write_exact(path: Path, data: bytes) -> None:
    if path.exists():
        require(path.read_bytes() == data, f"cached output differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def main() -> int:
    diagnosis = json.loads(DIAGNOSIS_PLAN.read_text(encoding="utf-8"))
    authorities = diagnosis["authorities"]
    archive_authority = authorities["issue_41_bundle"]
    require(ARCHIVE.is_file(), f"missing frozen bundle: {ARCHIVE}")
    require(ARCHIVE.stat().st_size == archive_authority["bytes"], "bundle bytes differ")
    require(sha256_file(ARCHIVE) == archive_authority["sha256"], "bundle SHA-256 differs")

    committed_plan = COMMITTED_PLAN.read_bytes()
    require(
        sha256_bytes(committed_plan) == authorities["issue_41_plan"]["sha256"],
        "committed issue-41 plan SHA-256 differs",
    )
    checked_file(
        ARCHIVED_CANDIDATE,
        authorities["issue_41_windows_one_worker_observation"],
        "archived Windows one-worker observation",
    )

    original_plan = json.loads(committed_plan)
    require(
        original_plan["plan_id"] == authorities["issue_41_plan"]["plan_id"],
        "issue-41 plan identity differs",
    )
    by_ordinal = {source["ordinal"]: source for source in original_plan["factor_sources"]}
    selected_ordinals = [sample["ordinal"] for sample in diagnosis["samples"]]
    require(len(set(selected_ordinals)) == len(selected_ordinals), "duplicate sample ordinal")

    with zipfile.ZipFile(ARCHIVE) as bundle:
        archived_plan = bundle.read("factor-qualification-plan.v1.json")
        require(archived_plan == committed_plan, "bundle plan differs from committed issue-41 plan")
        write_exact(EXTRACTED / "factor-qualification-plan.v1.json", archived_plan)
        for sample in diagnosis["samples"]:
            source = by_ordinal[sample["ordinal"]]
            require(source["role"] == "projected_b", "diagnosis sample is not projected")
            require(source["dimension"] == sample["dimension"], "sample dimension differs")
            require(source["sha256"] == sample["source_sha256"], "sample source differs")
            payload = bundle.read(source["bundle_path"])
            require(len(payload) == source["bytes"], "source payload byte count differs")
            require(sha256_bytes(payload) == source["sha256"], "source payload SHA-256 differs")
            write_exact(EXTRACTED / source["bundle_path"], payload)

    feedback_ordinal = diagnosis["feedback_loop"]["ordinal"]
    require(feedback_ordinal in by_ordinal, "feedback ordinal is absent")
    feedback_plan = dict(original_plan)
    feedback_plan["factor_sources"] = [by_ordinal[feedback_ordinal]]
    feedback_plan["diagnostic_derivation"] = {
        "schema": "RapidRBF/Issue41SingleSourceDiagnosticDerivation/v1",
        "authoritative_plan_sha256": authorities["issue_41_plan"]["sha256"],
        "ordinal": feedback_ordinal,
        "authority": "diagnostic-only; never corpus admission",
    }
    feedback_bytes = canonical_json(feedback_plan)
    write_exact(INPUTS / "feedback-loop-plan.v1.json", feedback_bytes)

    print(
        json.dumps(
            {
                "bundle_sha256": archive_authority["sha256"],
                "issue_41_plan_sha256": authorities["issue_41_plan"]["sha256"],
                "selected_ordinals": selected_ordinals,
                "unique_payloads": len(
                    {sample["source_sha256"] for sample in diagnosis["samples"]}
                ),
                "feedback_ordinal": feedback_ordinal,
                "extracted_root": str(EXTRACTED),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit(f"prepare failed: {error}") from error
