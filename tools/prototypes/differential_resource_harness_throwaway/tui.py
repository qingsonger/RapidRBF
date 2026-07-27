"""Thin interactive shell for the throwaway differential/resource harness lab."""

from __future__ import annotations

import argparse
import os
import textwrap

from model import BASELINE_SUBJECT, LabState, audit, short, slots, transition


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"


def styled(text: str, style: str, color: bool) -> str:
    if not color:
        return text
    return f"{style}{text}{RESET}"


def wrapped(label: str, value: str, width: int = 108) -> list[str]:
    prefix = f"{label}: "
    return textwrap.wrap(
        value,
        width=width,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix),
        break_long_words=False,
        break_on_hyphens=False,
    )


def mark(passed: bool) -> str:
    return "x" if passed else " "


def pair_records(state: LabState, pair_index: int) -> list:
    return [
        record
        for record in state.evidence
        if record.slot.pair_index == pair_index
    ]


def render_pair_ledger(state: LabState) -> list[str]:
    lines = ["pair order runs state                       normalized digests"]
    all_slots = slots(state)
    for pair_index in range(1, state.repetitions + 1):
        marker = ">" if pair_index == state.focus_pair else " "
        pair_slots = [
            slot for slot in all_slots if slot.pair_index == pair_index
        ]
        order = ">".join(
            "P" if slot.role == "polatory" else "C" for slot in pair_slots
        )
        records = pair_records(state, pair_index)
        anomalies = sorted(
            {
                record.anomaly
                for record in records
                if record.anomaly != "none"
            }
        )
        if not records:
            status = "pending"
        elif len(records) < 2:
            status = "incomplete"
        elif anomalies == ["raw-byte-drift"]:
            status = "captured + raw diagnostic"
        elif anomalies:
            status = "anomaly: " + ",".join(anomalies)
        else:
            status = "captured"
        normalized = "/".join(
            short(record.normalized_observation_digest, 8) for record in records
        ) or "-"
        lines.append(
            f"{marker}{pair_index:>3}  {order:>3}   {len(records)}/2  "
            f"{status[:27]:27} {normalized}"
        )
    return lines


def render_record_detail(record) -> list[str]:
    lines: list[str] = []
    lifecycle = record.lifecycle
    phase_text = ", ".join(
        (
            f"{phase.name}({'M' if phase.primary_measurement else 'D'}:"
            f"{phase.monotonic_wall_ms}ms/{phase.peak_tree_rss_bytes}B)"
        )
        for phase in lifecycle.phases
    )
    channel_text = ", ".join(
        f"{item.key}={item.status}" for item in record.channels
    )
    lines.append(
        f"position {record.slot.position} / {record.slot.role.upper()} -- "
        f"{record.subject} -- terminal={record.terminal_status} "
        f"anomaly={record.anomaly}"
    )
    lines.extend(
        wrapped(
            "Identity",
            f"build={record.build_identity}; adapter={record.adapter_identity}; "
            f"role={record.build_role}; wrapper={record.wrapper_identity}; "
            f"env={short(record.environment_digest)}...; "
            f"invocation={short(record.invocation_digest)}...; "
            f"cwd={record.working_directory}",
        )
    )
    lines.extend(
        wrapped(
            "Lane",
            f"host={record.host_identity}; affinity={record.affinity}; "
            f"cache={record.cache_profile}; "
            f"scratch={record.scratch_volume_identity}; seed={record.seed}",
        )
    )
    lines.extend(
        wrapped(
            "Digests",
            f"record={short(record.record_digest)}...; "
            f"raw={short(record.raw_artifact_digest)}...; "
            f"normalized={short(record.normalized_observation_digest)}...; "
            f"stdout/stderr={short(record.stdout_digest)}/"
            f"{short(record.stderr_digest)}...",
        )
    )
    lines.extend(
        wrapped(
            "Lifecycle",
            f"session={short(lifecycle.session_identity)}...; "
            f"apply={lifecycle.apply_index}; "
            f"precondition="
            f"{short(lifecycle.precondition_digest) + '...' if lifecycle.precondition_digest else 'none'}; "
            f"retained={lifecycle.retained_tree_rss_bytes}; "
            f"cleanup={lifecycle.session_cleanup_verified}; phases={phase_text}",
        )
    )
    lines.extend(
        wrapped(
            "Resources",
            f"wall/user/system={record.resources.monotonic_wall_ms}/"
            f"{record.resources.user_cpu_ms}/{record.resources.system_cpu_ms}ms; "
            f"native/tree-RSS={record.resources.platform_peak_memory_bytes}/"
            f"{record.resources.normalized_peak_tree_rss_bytes}; "
            f"scratch={record.resources.scratch_high_water_bytes}; "
            f"I/O={record.resources.io_read_bytes}/"
            f"{record.resources.io_write_bytes}; "
            f"output={record.resources.output_bytes}; "
            f"threads={record.resources.configured_threads}/"
            f"{record.resources.effective_threads}/"
            f"{record.resources.maximum_live_threads}; "
            f"sample={record.resources.sampling_interval_ms}ms; "
            f"scope={record.resources.resource_scope}",
        )
    )
    lines.extend(wrapped("Channels", channel_text))
    return lines


def render_pair_detail(state: LabState) -> list[str]:
    records = pair_records(state, state.focus_pair)
    if not records:
        return [f"Pair {state.focus_pair} has no captured records."]
    lines: list[str] = []
    for index, record in enumerate(records):
        if index:
            lines.append("-" * 108)
        lines.extend(render_record_detail(record))
    return lines


def render(state: LabState, color: bool) -> str:
    report = audit(state)
    planned = slots(state) if state.plan_digest else ()
    polatory_count = sum(
        record.slot.role == "polatory" for record in state.evidence
    )
    candidate_count = len(state.evidence) - polatory_count
    lines: list[str] = []

    lines.append(styled("RAPIDRBF DIFFERENTIAL/RESOURCE HARNESS LAB -- THROWAWAY", BOLD, color))
    lines.append(
        styled(
            "SYNTHETIC SHAPE CHECK ONLY -- no run is compatibility or benchmark evidence",
            DIM,
            color,
        )
    )
    lines.append("")
    lines.append(styled("REGISTERED MEANING", BOLD, color))
    lines.extend(wrapped("Scenario", state.scenario.stable_id))
    lines.extend(wrapped("Purpose", state.scenario.description))
    lines.append(
        f"Tier / authority: {state.scenario.minimum_tier} / "
        f"{state.scenario.oracle_authority}"
    )
    lines.append(f"Readiness: {state.scenario.readiness}")
    lines.append(
        f"Fixture: sha256:{short(state.scenario.fixture_digest)}...  "
        f"phase={state.phase}  plan="
        f"{short(state.plan_digest) + '...' if state.plan_digest else 'unregistered'}  "
        f"bundle="
        f"{short(state.bundle_digest) + '...' if state.bundle_digest else 'open'}"
    )
    lines.append("")
    lines.append(styled("EXECUTION LANE (does not redefine the scenario)", BOLD, color))
    lines.append(f"Pair: {BASELINE_SUBJECT}  <->  {state.candidate.label}")
    lines.extend(wrapped("Lifecycle", f"{state.lane.label} -- {state.lane.lifecycle}"))
    lines.extend(wrapped("Cache claim", state.lane.cache_claim))
    lines.append(
        f"Same-host demo: threads={4}, affinity=cores 0-3, "
        f"illustrative pairs={state.repetitions}, order-seed={state.order_seed}"
    )
    lines.append(
        styled(
            "Repetition count and statistics are symbolic; downstream threshold policy owns them.",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "Canonical optimized runs own timing; instrumented diagnostics link separately.",
            DIM,
            color,
        )
    )
    lines.append("")
    lines.append(
        styled(f"APPEND-ONLY EVIDENCE -- {state.view}", BOLD, color)
    )
    next_slot = planned[len(state.evidence)] if planned and len(state.evidence) < len(planned) else None
    next_text = (
        f"pair {next_slot.pair_index}/position {next_slot.position}: {next_slot.subject}"
        if next_slot
        else ("register plan" if not planned else "none")
    )
    lines.append(
        f"Captured: {len(state.evidence)}/{len(planned) if planned else state.repetitions * 2} "
        f"(Polatory {polatory_count}, candidate {candidate_count}); next={next_text}"
    )
    lines.append(
        f"Next anomaly: {state.fault.label}; focused pair={state.focus_pair}"
    )
    if state.view == "pair-ledger":
        lines.extend(render_pair_ledger(state))
    else:
        lines.extend(render_pair_detail(state))
    lines.append("")
    lines.append(styled(f"AUDIT / REPORT -- {report.status}", BOLD, color))
    grouped = []
    for label, passed in report.checks:
        grouped.append(f"[{mark(passed)}] {label}")
    for index in range(0, len(grouped), 2):
        lines.append("  ".join(grouped[index : index + 2]))
    lines.extend(wrapped("Conclusion", report.conclusion))
    if report.findings and state.report_requested:
        lines.extend(wrapped("Blocking gaps", "; ".join(report.findings)))
    if report.diagnostics:
        lines.extend(wrapped("Diagnostics", " ".join(report.diagnostics)))
    lines.append("")
    lines.extend(wrapped("Notice", state.notice))
    lines.append(
        styled(
            "[s] scenario  [c] candidate  [l] lane/cache  [n] repeats  [o] order seed",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[p] register  [x] capture  [i] anomaly  [v] view  [j] next pair",
            DIM,
            color,
        )
    )
    lines.append(
        styled(
            "[a] audit  [r] reset  [q] quit",
            DIM,
            color,
        )
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the throwaway RapidRBF differential/resource harness lab."
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="print the initial frame once instead of starting the interaction loop",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    color = not args.snapshot and "NO_COLOR" not in os.environ
    state = LabState()

    if args.snapshot:
        print(render(state, color=False))
        return 0

    while True:
        print("\x1b[2J\x1b[H", end="")
        print(render(state, color=color))
        try:
            command = input("\ncommand> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if command == "q":
            return 0
        state = transition(state, command)


if __name__ == "__main__":
    raise SystemExit(main())
