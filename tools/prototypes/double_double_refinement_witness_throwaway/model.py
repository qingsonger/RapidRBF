"""Pure in-memory review state for the Issue 53 throwaway prototype."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class ReviewState:
    disposition: str
    source_binding_sha256: str | None
    controller_binding_sha256: str | None
    preflight_count: int
    target_profile_count: int
    witness_source_observations: int
    invalidity_reasons: tuple[str, ...]
    nonpassing_coordinates: tuple[dict[str, Any], ...]
    scope: tuple[tuple[str, bool], ...]
    cursor: int = 0
    detail: bool = True
    human_reaction: str = "UNREVIEWED"


def from_summary(summary: dict[str, Any]) -> ReviewState:
    return ReviewState(
        disposition=summary["disposition"],
        source_binding_sha256=summary.get("source_binding_sha256"),
        controller_binding_sha256=summary.get("controller_binding_sha256"),
        preflight_count=summary["preflight_count"],
        target_profile_count=summary["target_profile_count"],
        witness_source_observations=summary["witness_source_observations"],
        invalidity_reasons=tuple(summary["invalidity_reasons"]),
        nonpassing_coordinates=tuple(summary["nonpassing_coordinates"]),
        scope=tuple(sorted(summary["scope"].items())),
    )


def reduce(state: ReviewState, action: str) -> ReviewState:
    count = len(state.nonpassing_coordinates)
    if action == "next" and count:
        return replace(state, cursor=(state.cursor + 1) % count)
    if action == "previous" and count:
        return replace(state, cursor=(state.cursor - 1) % count)
    if action == "toggle-detail":
        return replace(state, detail=not state.detail)
    if action in {"ACCEPT", "ADJUST", "REJECT", "UNREVIEWED"}:
        return replace(state, human_reaction=action)
    return state
