"""THROWAWAY native inventory-phase reproductions for Issue 54.

The helper is synthetic and candidate-independent. On Linux it exits just
before the process-group snapshot; on macOS it exits after the group snapshot
but before BSD identity capture. Those are the two exact Issue 53 failure
phases.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
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
deadline = time.monotonic() + 5.0
while not release.exists():
    if time.monotonic() >= deadline:
        raise SystemExit(91)
    time.sleep(0.001)
"""


def run(policy: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rapidrbf-issue54-native-") as scratch:
        release = Path(scratch) / "release"
        fired = False

        def release_and_cross_terminal() -> None:
            nonlocal fired
            if fired:
                return
            fired = True
            release.write_text("release\n", encoding="utf-8")
            # Rosetta startup on the x86_64 macOS runner can exceed 50 ms.
            # The hook is diagnostic-only, so wait long enough to cross the
            # root terminal on every native lane before resuming inventory.
            time.sleep(0.250 if sys.platform == "darwin" else 0.050)

        before = release_and_cross_terminal if sys.platform.startswith("linux") else None
        after = (
            (lambda _pids: release_and_cross_terminal())
            if sys.platform == "darwin"
            else None
        )
        completed, observation = observe_process(
            [sys.executable, "-c", HELPER, str(release)],
            cwd=ROOT,
            env=dict(os.environ),
            timeout_seconds=3.0,
            maximum_live_threads=12,
            candidate_entry=None,
            candidate_output=None,
            require_candidate_entry=False,
            require_successful_sample=False,
            invocation_kind=f"issue54-native-inventory-{policy}",
            terminal_policy=policy,
            before_group_snapshot=before,
            after_group_snapshot=after,
        )
        errors = [
            event["raw_adapter_result"]
            for event in observation["event_log"]
            if event["kind"] == "sample_error"
        ]
        return {
            "platform": sys.platform,
            "policy": policy,
            "classification": observation["classification"],
            "returncode": completed.returncode,
            "diagnostic_pid": observation["diagnostic_pid"],
            "benign_terminal_races": observation["benign_terminal_races"],
            "successful_samples": observation["successful_samples"],
            "sample_errors": errors,
            "invalidity": observation["invalidity"],
            "event_tail": observation["event_log"][-6:],
            "process_tree_empty_after_reap": observation["process_result"][
                "process_tree_empty_after_reap"
            ],
        }


def main() -> int:
    if sys.platform == "win32":
        print("SKIP: exact Issue 53 native failure phases are Linux/macOS-only")
        return 0
    legacy = run("legacy")
    root_bound = run("root-bound")
    phase = "group-membership" if sys.platform.startswith("linux") else "bsd-identity"
    adapter = (
        "linux-proc-process-tree"
        if sys.platform.startswith("linux")
        else "macos-proc-process-tree"
    )
    error = root_bound["sample_errors"][0] if root_bound["sample_errors"] else {}
    passed = (
        legacy["classification"] == "INVALID_CONTROLLER_EVIDENCE"
        and root_bound["classification"] == "PASS"
        and root_bound["benign_terminal_races"] == 1
        and root_bound["returncode"] == 0
        and error.get("adapter") == adapter
        and error.get("phase") == phase
        and error.get("subject_pid") == root_bound["diagnostic_pid"]
        and root_bound["process_tree_empty_after_reap"]
    )
    print(json.dumps({"legacy": legacy, "root_bound": root_bound}, sort_keys=True))
    print(
        "state: candidate-entry=0 backend-calls=0 factor-calls=0 "
        f"native-adapter={adapter} phase={phase} "
        f"verdict={'PASS' if passed else 'FAIL'}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
