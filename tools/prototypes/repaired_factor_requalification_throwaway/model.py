"""Pure in-memory review state for the issue-47 throwaway prototype."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class ReviewState:
    disposition: str
    cohort_key: tuple[Any, ...]
    target_dispositions: tuple[tuple[str, str], ...]
    invalidity_reasons: tuple[str, ...]
    nonpassing_coordinates: tuple[dict[str, Any], ...]
    cursor: int
    detail: bool
    human_reaction: str


def from_summary(summary: dict[str, Any]) -> ReviewState:
    keys = summary.get("cohort_keys", [])
    cohort_key = tuple(keys[0]) if len(keys) == 1 else tuple()
    return ReviewState(
        disposition=summary.get("disposition", "INVALID_UNJUDGED"),
        cohort_key=cohort_key,
        target_dispositions=tuple(
            sorted(summary.get("target_dispositions", {}).items())
        ),
        invalidity_reasons=tuple(summary.get("invalidity_reasons", [])),
        nonpassing_coordinates=tuple(
            summary.get("nonpassing_coordinates", [])
        ),
        cursor=0,
        detail=True,
        human_reaction="UNREVIEWED",
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
