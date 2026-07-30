"""Replay the accepted Issue 62 trace and assert the exact Issue 63 symptom."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_EVIDENCE_SHA256 = (
    "4879f1da043af898a0a0f2830529a241fb0a64da5ece6df81c467ee3b74e76c3"
)
FIT_THRESHOLD = 2.0**-24
EXPECTED_VALUE = 3.6434752952778648e-3
EXPECTED_GRADIENT = 5.3808841088235727e-2


def load_evidence(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_EVIDENCE_SHA256:
        raise ValueError(f"unexpected Issue 62 evidence identity: {digest}")
    return json.loads(payload)


def main() -> int:
    prototype = Path(__file__).resolve().parent
    evidence = load_evidence(
        prototype / "evidence" / "issue62-coarse4096-frozen.json"
    )
    candidates = [
        run
        for run in evidence["runs"]
        if run["scale_id"] == "10k"
        and run["enriched_coarse_target"] == 4096
    ]
    failures = [
        run for run in candidates if not run["direct_certificate"]["pass"]
    ]
    if len(candidates) != 6 or len(failures) != 1:
        raise AssertionError("coarse4096 survivor boundary changed")

    m3 = failures[0]
    certificate = m3["direct_certificate"]
    if m3["workload_id"] != "M3-HERMITE-10K":
        raise AssertionError("the isolated failing workload changed")
    if (
        m3["iterations"] != 100
        or m3["actions"]["preconditioner_internal"] != 200
    ):
        raise AssertionError("the frozen work-grant endpoint changed")
    if (
        certificate["value_residual"] != EXPECTED_VALUE
        or certificate["gradient_residual"] != EXPECTED_GRADIENT
    ):
        raise AssertionError("the accepted M3 residual endpoint changed")
    if (
        certificate["value_residual"] <= FIT_THRESHOLD
        or certificate["gradient_residual"] <= FIT_THRESHOLD
    ):
        raise AssertionError("the accepted M3 endpoint no longer fails")

    print("ISSUE63_RED_REPRODUCED")
    print(f"evidence_sha256={EXPECTED_EVIDENCE_SHA256}")
    print(
        "coarse4096_boundary="
        f"{len(candidates) - len(failures)}_pass/{len(failures)}_fail"
    )
    print(
        f"m3_endpoint=iterations:{m3['iterations']},"
        f"actions:{m3['actions']['preconditioner_internal']},"
        f"value:{certificate['value_residual']:.17e},"
        f"gradient:{certificate['gradient_residual']:.17e}"
    )
    print(f"threshold={FIT_THRESHOLD:.17e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
