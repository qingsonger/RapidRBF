"""Fast red-capable replay of the immutable Issue 56 evidence-path defect."""

from __future__ import annotations

import argparse
import json

from model import diagnose, load_fixed_evidence, load_plan, validate_replacement


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validate-replacement",
        action="store_true",
        help="validate the proposed Issue 58 contract instead of asserting clean evidence",
    )
    args = parser.parse_args()
    if args.validate_replacement:
        result = validate_replacement(load_plan())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if all(result.values()) else 1

    result = diagnose(load_fixed_evidence())
    print(json.dumps(result, indent=2, sort_keys=True))
    clean = (
        not result["producer_verifier_contract_drift"]
        and not result["artifact_kind_selection_alias"]
        and result["final_duplicate_root_bound_cohorts"] == 1
    )
    if not clean:
        print("PREFLIGHT_EVIDENCE_PATH_DEFECT_REPRODUCED")
        return 1
    print("PREFLIGHT_EVIDENCE_PATH_CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
