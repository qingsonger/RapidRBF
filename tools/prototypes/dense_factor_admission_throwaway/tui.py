"""Throwaway terminal shell for the dense-factor admission disposition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from model import canonical_json, render_snapshot


HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLE = HERE / "evidence" / "admission-bundle.json"
DEFAULT_SUMMARY = HERE / "evidence" / "observed-summary.json"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
VIEWS = ("verdict", "gates", "contract", "lineage")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the throwaway dense-factor admission state model."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--verify-evidence", action="store_true")
    parser.add_argument("--write-evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = render_snapshot(args.input.resolve())
    except (OSError, ValueError) as error:
        print(f"dense-factor admission: {error}", file=sys.stderr)
        return 2

    if args.snapshot:
        print(canonical_json(summary), end="")
        return 0
    if args.write_evidence is not None:
        output = args.write_evidence.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(canonical_json(summary), encoding="utf-8", newline="\n")
        print(output)
        return 0
    if args.verify_evidence:
        try:
            observed = json.loads(DEFAULT_SUMMARY.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"dense-factor admission: cannot read checked evidence: {error}", file=sys.stderr)
            return 2
        if observed != summary:
            print("checked evidence differs from the pure model", file=sys.stderr)
            return 1
        print(
            "verified "
            f"{summary['bundle']['sha256']} -> "
            f"{summary['disposition']['admission_disposition']} / "
            f"{summary['disposition']['mechanism_input_authority']}"
        )
        return 0

    view_index = 0
    while True:
        clear()
        render(summary, VIEWS[view_index])
        command = input(
            f"\n{BOLD}[n]{RESET} next  {BOLD}[p]{RESET} previous  "
            f"{BOLD}[q]{RESET} quit\n> "
        ).strip().lower()
        if command == "q":
            return 0
        if command in {"", "n"}:
            view_index = (view_index + 1) % len(VIEWS)
        elif command == "p":
            view_index = (view_index - 1) % len(VIEWS)


def clear() -> None:
    print("\x1b[2J\x1b[H", end="")


def render(summary: dict[str, Any], view: str) -> None:
    disposition = summary["disposition"]
    print(f"{BOLD}Dense-factor admission disposition{RESET}")
    print(
        f"{DIM}{summary['corpus']['sha256']} | view {view}{RESET}\n"
    )
    if view == "verdict":
        field("admission", disposition["admission_disposition"])
        field("mechanism input", disposition["mechanism_input_authority"])
        field("downstream decision", disposition["downstream_decision_authority"])
        field(
            "bounded recompute",
            str(disposition["bounded_recompute_fallback_ready"]).lower(),
        )
        field("attempt evidence", summary["attempt_evidence_state"])
        field(
            "unclosed gates",
            f"{summary['gate_summary']['unclosed_gate_count']}/"
            f"{summary['gate_summary']['required_gate_count']}",
        )
        print(f"\n{BOLD}Why{RESET}")
        for reason in disposition["reasons"]:
            print(f"- {reason}")
    elif view == "gates":
        print(f"{BOLD}Prerequisites{RESET}")
        for item in summary["prerequisites"]:
            gate_line(item)
        print(f"\n{BOLD}Ticket gates{RESET}")
        for item in summary["gates"]:
            gate_line(item)
    elif view == "contract":
        contract = summary["diagnostic_contract"]
        field("fallback", contract["bounded_factor_free_fallback"]["name"])
        field("fallback scope", contract["bounded_factor_free_fallback"]["scope"])
        print(f"\n{BOLD}Allowed{RESET}")
        for item in contract["allowed"]:
            print(f"+ {item}")
        print(f"\n{BOLD}Forbidden{RESET}")
        for item in contract["forbidden"]:
            print(f"- {item}")
    else:
        for key, value in summary["lineage"].items():
            field(key.replace("_", " "), value)
        print(f"\n{BOLD}Successor questions{RESET}")
        for item in summary["successor_questions"]:
            print(f"- {item['title']}")
            print(f"  {DIM}{item['purpose']}{RESET}")


def field(name: str, value: Any) -> None:
    print(f"{BOLD}{name}:{RESET} {value}")


def gate_line(item: dict[str, Any]) -> None:
    print(f"{BOLD}{item['id']}:{RESET} {item['state']}")
    print(f"  {DIM}{item['evidence']}{RESET}")


if __name__ == "__main__":
    raise SystemExit(main())
