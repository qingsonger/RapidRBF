#!/usr/bin/env python3
"""Run the deterministic issue-48 evidence diagnosis."""

from __future__ import annotations

import argparse
import json
import sys

from model import analyze


def current_failures(result: dict) -> list[str]:
    failures = []
    for witness in result["witnesses"]:
        for family in witness["families"]:
            if family["pre_pack_statuses"] == ["FAIL"]:
                failures.append(
                    f"ordinal={witness['ordinal']} "
                    f"workload={witness['workload_id']} "
                    f"family={family['family']} "
                    f"threshold_ratio_lower="
                    f"{family['minimum_threshold_ratio_lower']:.9g}"
                )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-current-candidate-admitted",
        action="store_true",
        help="assert the unchanged issue-47 candidate passes every witness",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="print only the disposition and key identities",
    )
    args = parser.parse_args()
    result = analyze()
    failures = current_failures(result)

    if args.require_current_candidate_admitted:
        if failures:
            print("RED: unchanged issue-47 candidate is not admitted")
            print(
                "symptom: frozen-system forward-solution FAIL while "
                "reconstruction and backward gates pass"
            )
            for failure in failures:
                print(f"  {failure}")
            print(
                "selected pre/post failure coordinates across 12 lanes: "
                f"{result['feedback_loop']['pre_and_post_reference_solution_failures']}"
            )
            return 1
        print("GREEN: unchanged issue-47 candidate passes every selected witness")
        return 0

    if args.compact:
        print(
            json.dumps(
                {
                    "disposition": result["disposition"],
                    "proven_mechanism": result["proven_mechanism"],
                    "next_experiment": result["next_experiment"],
                    "input_identities": result["input_identities"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"diagnosis failed: {error}", file=sys.stderr)
        raise
