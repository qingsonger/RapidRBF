"""Tiny terminal reviewer for the Issue 63 stagnation diagnosis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from issue63_review_logic import build_review, transition


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def render(state: dict[str, Any], clear: bool = True) -> None:
    if clear:
        print("\033[2J\033[H", end="")
    print("\033[1mRapidRBF Issue 63 - residual stagnation review\033[0m")
    print("=" * 64)
    print(f"\033[1mreview_status\033[0m: {state['review_status']}")

    m64 = state["accepted_m64"]
    m100 = state["full_window_m100"]
    comparison = state["comparison"]
    print("\n\033[1mAccepted m64 endpoint\033[0m")
    print(
        f"iterations={m64['iterations']}  "
        f"preconditioner_actions={m64['preconditioner_actions']}  "
        f"value={m64['value']:.6e}  gradient={m64['gradient']:.6e}"
    )
    print("\n\033[1mSingle-variable full-window probe\033[0m")
    print(
        f"iterations={m100['iterations']}  "
        f"preconditioner_actions={m100['preconditioner_actions']}  "
        f"value={m100['value']:.6e}  gradient={m100['gradient']:.6e}"
    )
    print(
        f"m64->m100 improvement: value={comparison['value_improvement']:.2f}x  "
        f"gradient={comparison['gradient_improvement']:.2f}x"
    )
    print(
        "remaining threshold multiples: "
        f"value={comparison['value_threshold_multiple']:.0f}x  "
        f"gradient={comparison['gradient_threshold_multiple']:.0f}x"
    )
    print(
        f"CPD={m100['cpd']:.3e}  "
        f"orthogonality_defect={m100['orthogonality_defect']:.3e}  "
        f"peak={m100['peak_bytes']} bytes"
    )

    print("\n\033[1mClosed hypotheses\033[0m")
    for hypothesis in state["closed_hypotheses"]:
        print(f"- {hypothesis}")
    print("\n\033[1mSurviving mechanism\033[0m")
    print(state["surviving_mechanism"])
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
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    evidence = prototype / "evidence"
    state = build_review(
        load(evidence / "issue62-coarse4096-frozen.json"),
        load(evidence / "issue63-m100-diagnostic.json"),
    )
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
