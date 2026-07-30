"""Tiny terminal review for the Issue 61 throwaway diagnosis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from issue61_review_logic import build_review, transition


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def latest(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"no result matches {pattern!r} under {root}")
    return matches[-1]


def render(state: dict[str, Any]) -> None:
    print("\033[2J\033[H", end="")
    print("\033[1mRapidRBF Issue 61 - M3 mechanism review\033[0m")
    print("=" * 58)
    print(f"\033[1mreview_status\033[0m: {state['review_status']}")
    print(f"\033[1mmapping_closed\033[0m: {state['mapping_closed']}")
    print(
        "\033[1mGG/VV block-max ratio\033[0m: "
        f"{state['gradient_to_value_block_max_ratio']:.3f}"
    )
    print(
        "\033[1mscale-only rejected\033[0m: "
        f"{state['scale_only_rejected']}"
    )
    print(
        "\033[1mreorder-only rejected\033[0m: "
        f"{state['reorder_only_rejected']}"
    )
    print(
        "\033[1m4096 coarse signal supported\033[0m: "
        f"{state['coarse_supported']}"
    )

    print("\n\033[1mProbe state (external complete certificate)\033[0m")
    print("probe                 iter       value    gradient       CPD")
    for name, probe in state["probes"].items():
        print(
            f"{name:<21} {probe['iterations']:>4}  "
            f"{probe['value']:>10.3e}  {probe['gradient']:>10.3e}  "
            f"{probe['cpd']:>9.2e}"
        )

    signal = state["coarse_signal"]
    print("\n\033[1m4096 coarse improvement\033[0m")
    print(
        "one step: "
        f"value {signal['one_step_value_improvement']:.2f}x, "
        f"gradient {signal['one_step_gradient_improvement']:.2f}x"
    )
    print(
        "one m=32 cycle vs one-step baseline: "
        f"value {signal['cycle_value_improvement']:.2f}x, "
        f"gradient {signal['cycle_gradient_improvement']:.2f}x"
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
    repository = Path(__file__).resolve().parents[3]
    default_root = repository / ".prototype-cache" / "results"
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=default_root)
    args = parser.parse_args()
    root = args.results
    state = build_review(
        load(latest(root, "issue61-mechanism-audit-*.json")),
        load(latest(root, "issue61-repro-*.json")),
        load(latest(root, "issue61-scaled-full-*.json")),
        load(latest(root, "issue61-fcf-eight-*.json")),
        load(latest(root, "issue61-coarse4096-one-*.json")),
        load(latest(root, "issue61-coarse4096-eight-*.json")),
        load(latest(root, "issue61-coarse4096-cycle-*.json")),
    )

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
            state = transition(state, "adjust", input("Adjustment: ").strip())
        elif choice == "r":
            state = transition(state, "reject", input("Reason: ").strip())


if __name__ == "__main__":
    raise SystemExit(main())
