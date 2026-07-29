"""Read-only presentation model for archived issue-41 qualification evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ADMITTED = "ADMITTED_FOR_MECHANISM_PANEL"
PROBLEM_PREVIEW_LIMIT = 12


@dataclass(frozen=True)
class ProfileCard:
    workers: int
    thread_grant: int
    observed_threads: int
    samples: int
    source_passes: int
    n_minus_one_passes: int
    cancellation: str
    negative_reload: str
    scratch_cleanup: bool


@dataclass(frozen=True)
class TargetCard:
    lane_id: str
    target: str
    disposition: str
    profiles: tuple[ProfileCard, ...]


@dataclass(frozen=True)
class QualificationDashboard:
    disposition: str
    plan_id: str
    commit: str
    run_id: str
    run_attempt: str
    transport_sha256: str
    problems: tuple[str, ...]
    targets: tuple[TargetCard, ...]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def locate_one(root: Path, name: str) -> Path:
    matches = sorted(root.rglob(name))
    if len(matches) != 1:
        raise ValueError(f"expected one {name} below {root}, found {len(matches)}")
    return matches[0]


def load_dashboard(evidence_root: Path) -> QualificationDashboard:
    root = evidence_root.resolve()
    summary = read_json(locate_one(root, "cohort-summary.json"))
    observations = {
        evidence["lane_id"]: evidence
        for evidence in (
            read_json(path)
            for path in sorted(root.rglob("target-observation.json"))
        )
    }
    cards: list[TargetCard] = []
    for lane_id, target in summary["required_targets"].items():
        evidence = observations.get(lane_id)
        if evidence is None:
            cards.append(
                TargetCard(
                    lane_id=lane_id,
                    target=target,
                    disposition="MISSING",
                    profiles=(),
                )
            )
            continue
        profiles = tuple(
            ProfileCard(
                workers=item["workers"],
                thread_grant=item["maximum_live_threads"],
                observed_threads=item["controller_threads"][
                    "maximum_live_threads"
                ],
                samples=item["controller_threads"]["samples"],
                source_passes=item["candidate_counts"]["passed_factor_sources"],
                n_minus_one_passes=item["candidate_controls"][
                    "exact_n_minus_one_observations"
                ],
                cancellation=item["candidate_controls"]["cancellation"]["status"],
                negative_reload=item["candidate_controls"]["negative_reload"][
                    "status"
                ],
                scratch_cleanup=item["candidate_scratch"]["cleanup_pass"],
            )
            for item in sorted(
                evidence["lane_observations"],
                key=lambda observation: observation["workers"],
            )
        )
        cards.append(
            TargetCard(
                lane_id=lane_id,
                target=target,
                disposition=evidence["disposition"],
                profiles=profiles,
            )
        )
    any_observation = next(iter(observations.values()), {})
    github = any_observation.get("github", {})
    transport = any_observation.get("transport", {}).get("asset", {})
    return QualificationDashboard(
        disposition=summary["disposition"],
        plan_id=summary["factor_qualification_plan"]["plan_id"],
        commit=str(github.get("sha") or "unknown"),
        run_id=str(github.get("run_id") or "unknown"),
        run_attempt=str(github.get("run_attempt") or "unknown"),
        transport_sha256=str(transport.get("sha256") or "unknown"),
        problems=tuple(summary.get("problems", [])),
        targets=tuple(cards),
    )


def status_mark(value: bool) -> str:
    return "PASS" if value else "FAIL"


def render_dashboard(
    dashboard: QualificationDashboard,
    selected_lane: str | None = None,
) -> str:
    selected = [
        card
        for card in dashboard.targets
        if selected_lane is None or card.lane_id == selected_lane
    ]
    lines = [
        "RapidRBF - instrumented faer corpus qualification",
        "=" * 58,
        f"Disposition : {dashboard.disposition}",
        f"Plan        : {dashboard.plan_id}",
        f"Cohort      : run {dashboard.run_id}, attempt {dashboard.run_attempt}",
        f"Commit      : {dashboard.commit}",
        f"Transport   : {dashboard.transport_sha256}",
        "",
    ]
    for card in selected:
        admitted = "[PASS]" if card.disposition == ADMITTED else "[DIAGNOSTIC]"
        lines.extend(
            [
                f"{admitted} {card.lane_id}  [{card.target}]",
                f"  {card.disposition}",
            ]
        )
        for profile in card.profiles:
            lines.append(
                "  "
                f"{profile.workers:>2} workers / {profile.thread_grant:>2} threads  "
                f"observed={profile.observed_threads:>2} "
                f"samples={profile.samples:<7} "
                f"sources={profile.source_passes}/216 "
                f"N-1={profile.n_minus_one_passes}/216 "
                f"cancel={profile.cancellation} "
                f"reload={profile.negative_reload} "
                f"cleanup={status_mark(profile.scratch_cleanup)}"
            )
        lines.append("")
    if dashboard.problems:
        preview = dashboard.problems[:PROBLEM_PREVIEW_LIMIT]
        lines.extend(["Diagnostic reasons:", *[f"  - {item}" for item in preview]])
        remaining = len(dashboard.problems) - len(preview)
        if remaining:
            lines.append(f"  ... {remaining} more; inspect cohort-summary.json")
    else:
        lines.append("Diagnostic reasons: none")
    return "\n".join(lines)
