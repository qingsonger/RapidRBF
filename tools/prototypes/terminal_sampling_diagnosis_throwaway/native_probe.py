"""THROWAWAY candidate-independent controller probes for Issue 54."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
WITNESS = ROOT.parent / "double_double_refinement_witness_throwaway"
sys.path.insert(0, str(WITNESS))

from controller_observer import observe_process  # noqa: E402


HELPER = """
import pathlib
import sys
import time

release = pathlib.Path(sys.argv[1])
delay = float(sys.argv[2])
deadline = time.monotonic() + 5.0
while not release.exists():
    if time.monotonic() >= deadline:
        raise SystemExit(91)
    time.sleep(0.001)
time.sleep(delay)
"""


def run_probe(
    name: str,
    *,
    policy: str,
    fault_mode: str | None,
    exit_delay: float,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"rapidrbf-issue54-{name}-") as scratch:
        release = Path(scratch) / "release"
        completed, observation = observe_process(
            [sys.executable, "-c", HELPER, str(release), str(exit_delay)],
            cwd=ROOT,
            env=dict(os.environ),
            timeout_seconds=3.0,
            maximum_live_threads=12,
            candidate_entry=None,
            candidate_output=None,
            require_candidate_entry=False,
            require_successful_sample=True,
            invocation_kind=f"issue54-controller-only-{name}",
            fault_mode=fault_mode,
            after_first_sample=lambda: release.write_text(
                "release\n", encoding="utf-8"
            ),
            terminal_policy=policy,
        )
        return {
            "name": name,
            "policy": policy,
            "fault_mode": fault_mode,
            "exit_delay": exit_delay,
            "returncode": completed.returncode,
            "classification": observation["classification"],
            "successful_samples": observation["successful_samples"],
            "benign_terminal_races": observation["benign_terminal_races"],
            "invalidity": observation["invalidity"],
            "event_tail": observation["event_log"][-8:],
            "process_tree_empty_after_reap": observation["process_result"][
                "process_tree_empty_after_reap"
            ],
        }


def main() -> int:
    probes = [
        run_probe(
            "legacy-root-loss",
            policy="legacy",
            fault_mode="root-bound-esrch-after-sample",
            exit_delay=0.050,
        ),
        run_probe(
            "root-bound-terminal-closure",
            policy="root-bound",
            fault_mode="root-bound-esrch-after-sample",
            exit_delay=0.050,
        ),
        run_probe(
            "nonroot-loss",
            policy="root-bound",
            fault_mode="nonroot-esrch-after-sample",
            exit_delay=0.050,
        ),
        run_probe(
            "root-loss-without-timely-terminal",
            policy="root-bound",
            fault_mode="root-bound-esrch-after-sample",
            exit_delay=1.250,
        ),
        run_probe(
            "clean",
            policy="root-bound",
            fault_mode=None,
            exit_delay=0.010,
        ),
    ]
    expected = {
        "legacy-root-loss": "INVALID_CONTROLLER_EVIDENCE",
        "root-bound-terminal-closure": "PASS",
        "nonroot-loss": "INVALID_CONTROLLER_EVIDENCE",
        "root-loss-without-timely-terminal": "INVALID_CONTROLLER_EVIDENCE",
        "clean": "PASS",
    }
    passed = True
    for probe in probes:
        wanted = expected[probe["name"]]
        probe_passed = probe["classification"] == wanted
        passed &= probe_passed
        print(
            f"{probe['name']}: {probe['classification']} "
            f"(expected {wanted}) {'PASS' if probe_passed else 'FAIL'}"
        )
        print(json.dumps(probe, sort_keys=True))
    print(
        "state: candidate-entry=0 backend-calls=0 factor-calls=0 "
        f"probes={len(probes)} verdict={'PASS' if passed else 'FAIL'}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
