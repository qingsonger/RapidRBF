"""Tiny terminal reviewer for the Issue 62 frozen coarse4096 cohort."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from issue62_review_logic import build_review, transition


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def render(state: dict[str, Any], clear: bool = True) -> None:
    if clear:
        print("\033[2J\033[H", end="")
    print("\033[1mRapidRBF Issue 62 - coarse4096 cohort review\033[0m")
    print("=" * 62)
    print(f"\033[1mreview_status\033[0m: {state['review_status']}")
    print(
        f"\033[1mrecorded_disposition\033[0m: "
        f"{state['recorded_disposition']}"
    )
    cohort = state["cohort"]
    print("\n\033[1mCohort closure\033[0m")
    print(
        f"runs={cohort['runs']} "
        f"(1k={cohort['one_k_identity_controls']}, "
        f"current10k={cohort['current_10k_controls']}, "
        f"coarse4096={cohort['coarse4096_10k_candidates']})"
    )
    print(
        f"current controls match={cohort['current_controls_match']}  "
        f"1k all pass={cohort['one_k_all_pass']}  "
        f"candidate pass/fail={cohort['candidate_passes']}/"
        f"{cohort['candidate_failures']}  "
        f"unique run IDs={cohort['unique_run_ids']}"
    )

    factor = state["factor_reference"]
    print("\n\033[1mGenerated-factor references\033[0m")
    print(
        f"sources={factor['generated_factor_sources']}  "
        f"RHS passes={factor['reference_rhs_passes']}  "
        f"max q={factor['maximum_q_upper']:.3e}  "
        f"max relative radius={factor['maximum_relative_radius']:.3e}"
    )

    resources = state["resources"]
    print("\n\033[1mResource closure\033[0m")
    print(
        f"peak={resources['maximum_peak_bytes']} / "
        f"{resources['peak_limit_bytes']} bytes  "
        f"preconditioner actions={resources['maximum_preconditioner_actions']} / "
        f"{resources['preconditioner_action_limit']}"
    )

    print("\n\033[1mcoarse4096 10k results\033[0m")
    print("workload                             result  iter       value    gradient")
    for row in state["candidate_rows"]:
        print(
            f"{row['workload_id']:<36} "
            f"{'PASS' if row['pass'] else 'FAIL':<6} "
            f"{row['iterations']:>4}  {row['value']:>10.3e}  "
            f"{row['gradient']:>10.3e}"
        )

    m3 = state["m3"]
    print("\n\033[1mM3-HERMITE-10K rejection\033[0m")
    print(
        f"current value={m3['current']['value_residual']:.6e}, "
        f"gradient={m3['current']['gradient_residual']:.6e}"
    )
    print(
        f"coarse4096 value={m3['candidate']['value_residual']:.6e}, "
        f"gradient={m3['candidate']['gradient_residual']:.6e}"
    )
    print(
        f"improvement value={m3['value_improvement']:.2f}x, "
        f"gradient={m3['gradient_improvement']:.2f}x; "
        f"still nonpassing at {m3['iterations']} iterations"
    )

    print("\n\033[1mRecommended\033[0m")
    print(state["recommended_decision"])
    if state["review_note"]:
        print(f"\n\033[1mreview_note\033[0m: {state['review_note']}")
    print(
        "\n\033[1m[a]\033[0m accept  "
        "\033[1m[j]\033[0m adjust  "
        "\033[1m[r]\033[0m reject  "
        "\033[1m[q]\033[0m quit"
    )


def main() -> int:
    prototype = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=prototype / "evidence" / "issue62-coarse4096-frozen.json",
    )
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    state = build_review(load(args.evidence))
    if args.snapshot:
        render(state, clear=False)
        return 0

    while True:
        render(state)
        try:
            choice = input("> ").strip().lower()
        except EOFError:
            choice = "q"
        if choice == "q":
            print(f"LIVE_REVIEW={state['review_status']}")
            return 0
        if choice == "a":
            state = transition(state, "accept")
        elif choice == "j":
            state = transition(
                state, "adjust", input("Adjustment: ").strip()
            )
        elif choice == "r":
            state = transition(
                state, "reject", input("Reason: ").strip()
            )


if __name__ == "__main__":
    raise SystemExit(main())
