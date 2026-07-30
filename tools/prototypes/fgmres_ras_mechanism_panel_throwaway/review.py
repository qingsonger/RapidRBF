"""Interactive live review for the Issue 32 throwaway mechanism panel."""

from __future__ import annotations

import argparse
from pathlib import Path

from review_logic import build_review, load_result


def gibibytes(value: int) -> float:
    return value / (1024**3)


def main() -> int:
    repository = Path(__file__).resolve().parents[3]
    result_root = repository / ".prototype-cache" / "results"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--panel",
        type=Path,
        default=result_root / "issue32-full-panel-v2.json",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=result_root / "issue32-orthogonalization-audit.json",
    )
    args = parser.parse_args()
    state = build_review(load_result(args.panel), load_result(args.audit))

    print("\nRapidRBF Issue 32 - live mechanism review")
    print("=" * 48)
    print(f"Disposition: {state['disposition']}")
    print(
        f"Coverage: {state['run_count']} runs / "
        f"{state['workload_count']} workloads"
    )
    factors = state["factor_evidence"]
    print(
        "Factors: "
        f"{factors['qualified_factor_sources']} qualified sources, "
        f"{factors['repaired_reference_rhs_passes']} reference RHS passes, "
        "release admission not claimed"
    )
    print(
        "Peak working set: "
        f"{gibibytes(state['peak_working_set_bytes']):.2f} GiB / 8 GiB"
    )

    print("\n10k robust screen ranking")
    print("screen  actions  basis MiB  configuration")
    for score in state["scores"]:
        print(
            f"{score['screened_10k']:>2}/6  "
            f"{score['total_actions']:>7}  "
            f"{score['maximum_basis_bytes'] / (1024**2):>9.2f}  "
            f"{score['topology']} m={score['window']}"
        )

    best = state["m3_best"]
    cert = best["bound_certificate"]
    print("\nBlocking witness")
    print(
        "M3-HERMITE-10K: "
        f"{best['topology']} m={best['window']} ended after "
        f"{best['iterations']} iterations with "
        f"value={cert['value_residual']:.6e}, "
        f"gradient={cert['gradient_residual']:.6e}."
    )

    print("\nRobust vs parity diagnostic frontier")
    print(
        "Iteration counts equal: "
        f"{state['all_pair_iterations_equal']}; "
        "statuses/direct outcomes equal: "
        f"{state['all_pair_outcomes_equal']}."
    )
    for row in state["orthogonalization_pairs"]:
        outcome = "PASS" if row["robust_direct_pass"] else "FAIL"
        print(
            f"{row['workload']:<34} {row['topology']:<31} "
            f"iter {row['robust_iterations']:>3}/{row['parity_iterations']:<3} "
            f"direct {outcome}"
        )

    print("\nRecommended")
    print(state["recommended_decision"])
    print("\n[A]ccept finding  [J]ust adjust experiment  [R]eject evidence  [Q]uit")
    try:
        choice = input("> ").strip().lower()
    except EOFError:
        choice = "q"
    if choice == "a":
        print(
            "LIVE_REVIEW=ACCEPT_FINDING "
            "(no solver selected; mixed-gradient gap required)"
        )
    elif choice == "j":
        note = input("Adjustment requested: ").strip()
        print(f"LIVE_REVIEW=ADJUST note={note}")
    elif choice == "r":
        note = input("Reason for rejection: ").strip()
        print(f"LIVE_REVIEW=REJECT note={note}")
    else:
        print("LIVE_REVIEW=NO_DECISION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
