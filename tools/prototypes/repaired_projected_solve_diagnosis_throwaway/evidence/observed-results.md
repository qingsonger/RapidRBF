# Observed result

## Disposition

`NEXT_DENSE_FACTOR_EXPERIMENT_FROZEN`

The accepted issue-47 evidence supports one candidate-owned failure mechanism:
the unchanged binary64 projected-B Bunch–Kaufman route reconstructs the frozen
matrix and remains well inside the reduced-backward-error gate, but its forward
solve error is amplified beyond the candidate-independent frozen-system
threshold along particular RHS directions.

This does not admit a factor path or dependency. It freezes one bounded
double-double-refinement witness experiment.

## Tight red loop

```text
python tools/prototypes/repaired_projected_solve_diagnosis_throwaway/run.py --require-current-candidate-admitted
```

The command deterministically exits `1` and reports 10 failing source/family
coordinates per target/profile, or 240 pre-pack/post-reload coordinates across
the 12 selected observations. In every case, reconstruction and reduced
backward error pass and pre/post solutions are bit exact.

## Boundary-complete witness panel

| Ordinal | Boundary | Current RHS result | Smallest failure multiple across 12 lanes | Max backward-gate fraction | Max reconstruction-gate fraction |
| ---: | --- | --- | ---: | ---: | ---: |
| 0 | projected passing control | P/P/P | — | 2.912e-4 | 6.683e-5 |
| 36 | M2-TH3 1k failure | F/F/F | 146.7x | 1.562e-4 | 7.224e-5 |
| 69 | M2-TH3 smallest-dimension/duplicate-source boundary | F/F/F | 9.763x | 1.128e-4 | 7.812e-5 |
| 72 | repaired M3-HERMITE 1k pass/rank-pivot boundary | P/P/P | — | 3.186e-5 | 4.950e-5 |
| 106 | M3-HERMITE partial-family exception | F/P/P | 2.465x | 2.312e-5 | 5.694e-5 |
| 150 | M4-GEOMETRY worst frozen-system failure | F/F/F | 2.489e4x | 2.673e-4 | 9.066e-5 |

RHS order is operational, constraint, dynamic-range. Every source has
`expected_rank == dimension`, all 18 references are members of the issue-47
manifest that certified 537/537 RHS with zero `INDETERMINATE`, and every
source/family status vector is identical across all four targets and all three
worker/thread profiles.

Ordinal 106 is the key separator: one full-rank matrix, one factor and one
pivot path fail only the operational RHS while the other two RHS families pass.
Problem conditioning therefore supplies the amplification context, but neither
a matrix-only condition label nor a pivot-only explanation is a sufficient
factor verdict.

## Alternative-route separation

The accepted issue-45 comparison already covers ordinals 0, 69, 72, and 150:

- directional amplification rises from `1.742e3` on the M1 control through
  `4.688e6` on ordinal 69 and `3.871e10` on ordinal 150;
- raw full-pivot LU and raw symmetrically equilibrated Bunch–Kaufman do not
  close ordinals 69 or 150—the first refinement correction minus the sum of
  every later correction remains outside the unchanged threshold; and
- double-double-refined Bunch–Kaufman and full-pivot LU converge on the same
  frozen-system solution, agreeing to `6.312e-25` at ordinal 69 and
  `3.587e-21` at ordinal 150.

This falsifies pivot replacement and symmetric equilibration as sole remedies.
It supports owned high-precision residual refinement, but leaves exactly two
numerical boundaries untested by that accepted route comparison: the M2 1k
failure at ordinal 36 and the ordinal-106 partial-family exception. Resource
accounting and typed cancellation inside the refinement loop are also still
open.

## Frozen next experiment

The selected candidate is the unchanged issue-47 instrumented faer 0.24.4
Bunch–Kaufman factor and binary64 correction solve wrapped by a RapidRBF-owned
double-double residual and solution-accumulation boundary, with one final
nearest-ties-to-even binary64 rounding.

The exact plan runs:

- the six named sources and their 18 already-certified RHS;
- all four tier-one native targets;
- the unchanged `1/12`, `2/12`, and `8/16` worker/thread profiles;
- an unchanged-candidate baseline replay before the refined arm;
- pre-pack and post-reload judgments, exact N-minus-one denial including
  `168*n` added refinement bytes, typed mid-refinement cancellation, prior-state
  preservation, allocation/thread/scratch closure, and non-compensating
  aggregation.

The only valid outcomes are
`REFINEMENT_ROUTE_SUPPORTED_FOR_FULL_CORPUS_PLAN`,
`REFINEMENT_ROUTE_REJECTED_DIAGNOSTIC_ONLY`, or `INVALID_UNJUDGED`.
A witness-gate pass supports a separately frozen full-corpus plan; it does not
admit the factor path.

Plan file SHA-256:
`7018a1a33d601076ff17b6824068ada146039fa57aab5b1cf71793cbe6d13d60`.

## Scope

The prototype reads but does not rerun or mutate the issue-47 full cohort. It
does not admit faer, qd, a factor path, or the corpus; run the mechanism panel;
select persistent factor storage; enter the 100k rung; or unblock downstream
solver comparison.
