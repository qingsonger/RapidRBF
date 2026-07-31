"""Pure state model for the Issue 66 source-closure review."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_review() -> dict[str, Any]:
    requirements = [
        {
            "id": "exact-executable-source",
            "state": "blocking",
            "finding": (
                "No projected H2/IFMM factor implementation is present in the "
                "RapidRBF source or captured prototype branches."
            ),
        },
        {
            "id": "no-result-affecting-adaptation",
            "state": "blocking",
            "finding": (
                "The closest upstream packages provide H2 construction/matvec "
                "or HSS/TLR factorization, but not the ticket's exact projected, "
                "grouped, component-wise, fill-in-recompressed candidate."
            ),
        },
        {
            "id": "source-build-identity",
            "state": "blocked",
            "finding": (
                "Four target build identities cannot identify a candidate until "
                "the missing implementation and dependency closure exist."
            ),
        },
        {
            "id": "construction-semantics",
            "state": "blocked",
            "finding": (
                "Issue 65's ten result-affecting construction choices can be "
                "specified, but executable enforcement belongs to the missing "
                "candidate implementation."
            ),
        },
        {
            "id": "fixtures-and-evidence-authority",
            "state": "separable",
            "finding": (
                "Panel identities, 100k geometries, schema, verifier, and an "
                "execution plan can be frozen independently, but doing so does "
                "not create the absent candidate source."
            ),
        },
        {
            "id": "wayfinder-destination",
            "state": "conflict",
            "finding": (
                "Materializing a bespoke production-scale hierarchical factor "
                "implements RapidRBF, while the map Notes explicitly limit this "
                "effort to migration planning and uncertainty-removing prototypes."
            ),
        },
    ]
    blocking = sum(item["state"] in {"blocking", "blocked", "conflict"} for item in requirements)
    return {
        "question": (
            "Can Issue 66 freeze one executable projected H2/IFMM candidate "
            "without making result-affecting implementation choices or crossing "
            "the map's planning destination?"
        ),
        "review_status": "pending-live-review",
        "recommended_disposition": "INVALID_UNJUDGED",
        "authority_defect": "NO_EXECUTABLE_CANDIDATE_SOURCE_CLOSURE",
        "candidate_entry_permitted": False,
        "candidate_observations": {
            "factor_setup": 0,
            "factor_apply": 0,
            "solve": 0,
        },
        "requirement_count": len(requirements),
        "blocking_requirement_count": blocking,
        "requirements": requirements,
        "interpretation": [
            (
                "The H2/IFMM family remains a provisional implementation and "
                "qualification target; it is not rejected."
            ),
            (
                "A manifest, fixture set, or CI build of a control-plane shell "
                "cannot substitute for executable factor source."
            ),
            (
                "Writing the missing factor before /to-spec would redraw the "
                "destination from planning into implementation."
            ),
        ],
        "proposed_frontier": [
            {
                "order": 1,
                "title": (
                    "Choose the specification boundary for the unimplemented "
                    "projected hierarchical preconditioner"
                ),
                "type": "wayfinder:grilling",
                "question": (
                    "Must an executable solver candidate be qualified before "
                    "/to-spec, or should the specification freeze the mechanism "
                    "contract and make source qualification an implementation/"
                    "release gate?"
                ),
            }
        ],
        "review_note": "",
    }


def transition(state: dict[str, Any], action: str, note: str = "") -> dict[str, Any]:
    if action not in {"accept", "adjust", "reject"}:
        raise ValueError(f"unsupported review action: {action}")
    next_state = deepcopy(state)
    next_state["review_status"] = {
        "accept": "accepted",
        "adjust": "adjustment-requested",
        "reject": "rejected",
    }[action]
    next_state["review_note"] = note
    if action == "reject":
        next_state["recommended_disposition"] = "REVIEW_REJECTED_NO_DISPOSITION"
    return next_state
