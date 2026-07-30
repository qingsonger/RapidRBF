"""THROWAWAY captured-trace feedback loop for Issue 54.

This script is intentionally not a production test. It replays the compact
tail of the seven invalid Issue 53 controller observations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from model import diagnostic_boundary_classification, legacy_classification


ROOT = Path(__file__).resolve().parent
TRACES = ROOT / "captured-terminal-traces.v1.json"


def load_traces() -> list[dict[str, object]]:
    return json.loads(TRACES.read_text(encoding="utf-8"))["traces"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--feedback-loop",
        action="store_true",
        help="assert the desired terminal-root closure against the Issue 53 policy",
    )
    args = parser.parse_args()

    traces = load_traces()
    legacy_invalid = 0
    print("Issue 54 captured terminal-sampling replay")
    for trace in traces:
        legacy = legacy_classification(trace)
        boundary = diagnostic_boundary_classification(trace)
        legacy_invalid += legacy == "INVALID_CONTROLLER_EVIDENCE"
        delta_ms = (
            trace["terminal_ns"] - trace["sample_started_ns"]
        ) / 1_000_000
        print(
            f"{trace['coordinate']}: legacy={legacy}; "
            f"diagnostic={boundary}; terminal-from-sample={delta_ms:.3f}ms; "
            f"successful-samples={trace['successful_samples']}"
        )

    print(
        f"state: traces={len(traces)} legacy-invalid={legacy_invalid} "
        "old-observations-reusable=NO missing-field=error.subject_pid"
    )
    if args.feedback_loop and legacy_invalid:
        print(
            "RED: the legacy policy rejects every captured normal terminal "
            "closure instead of reconciling a root-bound ESRCH."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
