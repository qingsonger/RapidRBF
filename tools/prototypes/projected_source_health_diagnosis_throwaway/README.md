# THROWAWAY PROTOTYPE — projected-source solution-health diagnosis

This prototype answers
[Diagnose the projected-source solution-health failures and choose the next dense-factor route](https://github.com/qingsonger/RapidRBF/issues/45).
It is decision evidence, not production code.

## Question

Why do the exact same 170 admitted projected sources pass issue-41
reconstruction and reduced-backward-error gates yet fail only
`pack_reload_solution_relative_inf_max = 256*n*2^-53`, and is the narrowest
next route a candidate change, a replacement dense path, or repair of the
candidate-independent health authority?

## Frozen inputs

- Issue-41 release bundle:
  `a3b6417e61a604ee568d7bb5fed0416ce5c726f0e529ca1f998a7bdb272e207a`.
- Factor qualification plan:
  `fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce`.
- Windows one-worker observation:
  `bdc2ed4d326659668ef1cf4bfe18685e853528dc44320060ab64aa22009307c8`.
- Factor-health profile:
  `00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3`.
- Candidate binding:
  `1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6`.

The 453 MB input bundle is intentionally ignored. `prepare.py` verifies its
size and SHA-256, verifies the archived issue-41 observation, and extracts only
the four preregistered boundary samples. No issue-41 evidence or frozen health
gate is mutated.

## One command

Place
`rapidrbf-issue41-factor-qualification-input-v1.zip` under `inputs/`, then run
from the repository root:

```powershell
python tools/prototypes/projected_source_health_diagnosis_throwaway/run.py
```

The runner:

1. replays the exact issue-41 path on the nearest boundary failure as a
   deterministic two-second red feedback loop;
2. verifies the issue-41 factor fingerprint and failure shape exactly;
3. checks candidate LDLT, byte round-trip, symmetric max equilibration, and
   independent full-pivot LU;
4. refines the LDLT and LU solutions with 105-bit double-double residual and
   solution accumulation; and
5. captures deterministic JSON plus the readable disposition under
   `evidence/`.

Review all four boundary cards:

```powershell
python tools/prototypes/projected_source_health_diagnosis_throwaway/tui.py --snapshot
```

Run `tui.py` without arguments for the small interactive reviewer.

## Observed disposition

`HEALTH_AUTHORITY_DEFECT_PROVEN`

The issue-41 ordered binary64 manufactured RHS is a slightly perturbed
`A*x`, but the admitted projected sources amplify that perturbation. For every
selected failing boundary, independently pivoted LDLT and full-pivot LU
converge under double-double refinement to the same frozen-`b` solution, and
that mathematically correct solution is itself outside the fixed declared-`x`
gate. Equilibration and refinement therefore cannot repair the gate.

The owned factor and solved correction are bit-exact across byte round-trip.
The passing M1 projected control remains inside the same gate. The captured
numbers and decision boundary are in
[`evidence/observed-results.md`](evidence/observed-results.md).

This result does not replace the defective authority, requalify the complete
216-factor corpus, adopt faer, run the mechanism panel, choose persistent
factor storage, or enter the 100k rung.
