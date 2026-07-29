"""Read-only presentation model for captured issue-45 diagnosis evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ObservationCard:
    ordinal: int
    category: str
    workload: str
    archived_status: str
    threshold: float
    candidate_initial: float
    refined_reference: float
    reference_agreement: float
    directional_amplification: float
    roundtrip_exact: bool
    authority_defect_witness: bool


@dataclass(frozen=True)
class Dashboard:
    disposition: str
    failed_authority_witnesses: bool
    passing_control: bool
    roundtrips_exact: bool
    cards: tuple[ObservationCard, ...]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dashboard(path: Path) -> Dashboard:
    evidence = read_json(path)
    closure = evidence["closure"]
    cards = tuple(
        ObservationCard(
            ordinal=observation["ordinal"],
            category=observation["category"],
            workload=observation["workload_id"],
            archived_status=observation["archived"]["status"],
            threshold=observation["archived"]["solution_threshold"],
            candidate_initial=observation["candidate_lblt"]["metrics"][
                "maximum_declared_solution_relative_inf"
            ],
            refined_reference=observation["independent_reference"][
                "declared_solution_relative_inf"
            ],
            reference_agreement=observation["independent_reference"][
                "lblt_full_pivot_lu_relative_agreement"
            ],
            directional_amplification=observation["frozen_rhs"][
                "directional_forward_amplification"
            ],
            roundtrip_exact=(
                observation["serialization_roundtrip"][
                    "factor_fingerprint_bit_exact"
                ]
                and observation["serialization_roundtrip"]["solution_bit_exact"]
            ),
            authority_defect_witness=observation["judgment"][
                "authority_defect_witness"
            ],
        )
        for observation in evidence["observations"]
    )
    return Dashboard(
        disposition=evidence["disposition"],
        failed_authority_witnesses=closure[
            "all_failed_samples_prove_authority_defect"
        ],
        passing_control=closure["passing_control_closes"],
        roundtrips_exact=closure["all_serialization_roundtrips_bit_exact"],
        cards=cards,
    )


def mark(value: bool) -> str:
    return "PASS" if value else "FAIL"


def render_dashboard(dashboard: Dashboard, selected: int | None = None) -> str:
    lines = [
        "RapidRBF - projected-source solution-health diagnosis",
        "=" * 62,
        f"Disposition                 {dashboard.disposition}",
        f"Failed-source witnesses     {mark(dashboard.failed_authority_witnesses)}",
        f"Passing projected control   {mark(dashboard.passing_control)}",
        f"Factor/solve round-trips    {mark(dashboard.roundtrips_exact)}",
        "",
    ]
    cards = (
        dashboard.cards
        if selected is None
        else tuple(card for card in dashboard.cards if card.ordinal == selected)
    )
    for card in cards:
        witness = "AUTHORITY DEFECT" if card.authority_defect_witness else "CONTROL"
        lines.extend(
            [
                f"[{witness}] ordinal {card.ordinal} - {card.workload}",
                f"  {card.category}",
                f"  archived={card.archived_status:<4} "
                f"gate={card.threshold:.6e} "
                f"candidate={card.candidate_initial:.6e}",
                f"  refined frozen-b reference={card.refined_reference:.6e} "
                f"LDLT/LU agreement={card.reference_agreement:.6e}",
                f"  RHS directional amplification={card.directional_amplification:.6e} "
                f"roundtrip={'BIT-EXACT' if card.roundtrip_exact else 'CHANGED'}",
                "",
            ]
        )
    return "\n".join(lines)
