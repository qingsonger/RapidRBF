# Observed result

## Disposition

`HEALTH_AUTHORITY_DEFECT_PROVEN`

The frozen `pack_reload_solution_relative_inf_max = 256*n*2^-53` authority is unsound for the issue-41 manufactured-RHS construction. The issue-41 candidate and factor bytes are not admitted by this result; the representative subset is not corpus requalification.

## Tight feedback loop

The exact issue-41 candidate path was replayed on ordinal 72 alone. It reproduced the archived factor fingerprint and metrics exactly: reconstruction and reduced backward error pass, while only the declared-solution-relative gate fails at 1.184706x its limit.

## Boundary-complete diagnosis subset

| Ordinal | Boundary | Frozen status | Gate | Refined frozen-b solution error | LDLT/LU reference agreement | RHS directional amplification |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 0 | projected passing control | `PASS` | 2.839329e-11 | 1.119829e-11 | 3.741199e-28 | 1.741659e+03 |
| 69 | smallest-dimension failed source and duplicate-logical-source boundary | `FAIL` | 2.296474e-11 | 2.622900e-09 | 6.311892e-25 | 4.688448e+06 |
| 72 | nearest frozen failure boundary | `FAIL` | 4.251888e-11 | 4.892481e-11 | 6.246003e-27 | 1.640587e+05 |
| 150 | worst frozen failure boundary | `FAIL` | 2.299316e-11 | 3.278590e-05 | 3.586758e-21 | 3.871444e+10 |

## What the probes separate

- **Conditioning / authority:** the ordered binary64 `b = fl(Ax)` has only a small backward perturbation, but the admitted projected sources amplify it enough that the mathematically correct frozen-b solution is outside the fixed declared-x gate. The passing M1 control stays inside the same gate.
- **Candidate-local solve:** exact issue-41 LDLT, symmetric max equilibration, and independent full-pivot LU converge under 105-bit residual refinement to the same frozen-b solution. None of the three routes restores the failed declared-x gate.
- **Serialization / reuse:** every selected factor payload and solved correction is bit-exact across the owned-component byte round-trip.
- **Source / rank authority:** the two independently pivoted refined routes agree far below the gate and reach roughly 1e-31 normalized backward error; the evidence does not support reopening exact-rank or physical-source admission.

## Decision boundary

This result proves a defect in the candidate-independent health authority. It does not replace that authority, requalify the 216 factors, adopt faer, run the mechanism panel, choose factor storage, or enter the 100k rung. A fresh decision ticket must define a candidate-independent reference for the same frozen `(A, b)` system with explicit oracle uncertainty and then preregister a new full-corpus qualification plan.
