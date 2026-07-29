# Observed results — projected-factor solution-health repair

Disposition: `REPLACEMENT_HEALTH_AUTHORITY_AND_PLAN_FROZEN`

This is a boundary prototype and frozen requalification plan, not a 216-source candidate judgment.

## Frozen identities

- Replacement authority: `c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6`.
- Requalification plan: `3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829`.
- Accepted issue-45 evidence: `b5dbe24ace553df3d390673feef5cad1912bdc8130d97875739f13e8512587d2`.

## Boundary witnesses

| Ordinal | Workload | Old | Repaired | Candidate/reference interval | Threshold |
| ---: | --- | --- | --- | ---: | ---: |
| 0 | `M1-EXP-1K` | `PASS` | `PASS` | `[6.740450e-15, 6.740450e-15]` | `2.839329e-11` |
| 69 | `M2-TH3-10K` | `FAIL` | `FAIL` | `[2.241942e-10, 2.241942e-10]` | `2.296474e-11` |
| 72 | `M3-HERMITE-1K` | `FAIL` | `PASS` | `[3.121391e-12, 3.121391e-12]` | `4.251888e-11` |
| 150 | `M4-GEOMETRY-NEAR-COINCIDENT-10K` | `FAIL` | `FAIL` | `[6.236846e-07, 6.236855e-07]` | `2.299316e-11` |

Ordinal 72 changes from old `FAIL` to repaired `PASS`: its candidate solution is inside the unchanged threshold around the frozen-`(A,b)` reference. Ordinals 69 and 150 remain `FAIL`, demonstrating that the repair is not a blanket accommodation for the candidate. The projected passing control remains `PASS`.

## Adversarial guards

- `PASS` — **declared-vector-perturbation**: `PASS`. Changing the diagnostic declared vector after frozen b exists does not enter the new judgment; ordinal 72 remains PASS.
- `PASS` — **threshold-overlap**: `INDETERMINATE`. An oracle interval straddling the unchanged threshold cannot be rounded or voted into PASS.
- `PASS` — **low-backward-error-false-admission**: `FAIL`. A candidate two thresholds from the reference fails even when a separate backward-error gate would pass.
- `PASS` — **candidate-circularity**: `REJECTED_BEFORE_REFERENCE_GENERATION`. A reference request containing a candidate binding, factor, solution, residual, or observation is identity-invalid.
- `PASS` — **candidate-threshold-override**: `REJECTED_BEFORE_CANDIDATE_ENTRY`. The threshold is fixed by the authority profile; a candidate or lane override changes identity and cannot enter the cohort.

## Decision boundary

The declared vector remains only the frozen RHS-construction input and a diagnostic. The exact binary64 system is authoritative. A directed-rounding reference certificate owns oracle uncertainty; overlap is `INDETERMINATE`, never a pass. The full cohort remains unexecuted and unjudged.
