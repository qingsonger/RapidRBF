# THROWAWAY PROTOTYPE — projected-factor solution-health authority

This prototype answers
[Repair the projected-factor solution-health authority and freeze a replacement qualification plan](https://github.com/qingsonger/RapidRBF/issues/46).
It is decision evidence, not production code.

## Question

What candidate-independent authority should replace the defective
declared-solution comparison for projected factor solves, and what immutable
plan should govern the resulting 216-source, three-profile, four-target
requalification?

The prototype assumes the exact binary64 matrix `A` and the ordered binary64
manufactured right-hand side `b = fl(A*x_declared)` are the system under
judgment. The declared vector remains an input to RHS construction and a
diagnostic only; it is never the reference solution.

## Proposed authority

[`authority-profile.v1.json`](authority-profile.v1.json) defines a
candidate-independent reference enclosure:

1. convert the frozen binary64 `A` and `b` exactly into directed-rounding MPFR
   intervals;
2. generate a deterministic complete-pivot reference center and approximate
   inverse at the next preregistered precision rung;
3. certify `q = ||I - R*A||_inf < 1`;
4. enclose the unique exact solution in
   `||x* - x0||_inf <= ||R*(b-A*x0)||_inf / (1-q)`; and
5. compare a candidate solution, treated as exact binary64 data, with that
   enclosure using three-valued `PASS`, `FAIL`, or `INDETERMINATE` judgment.

The existing `256*n*2^-53` solution-relative threshold is unchanged. Oracle
and comparison rounding are included by outward intervals. A reference that
cannot certify uniqueness, or a comparison band that overlaps the threshold,
is `INDETERMINATE`; it never passes by approximation or by agreement with a
candidate.

The reference manifest is generated and hashed before candidate entry. It
contains no candidate binding, factor bytes, packed solution, or candidate
observation. The same manifest is reused on all four targets and all three
worker profiles.

## Frozen requalification

[`requalification-plan.v1.json`](requalification-plan.v1.json) binds:

- the unchanged issue-41 bundle and 216-source qualification plan;
- the replacement authority;
- the exact instrumented-faer candidate binding;
- the four tier-one native targets;
- the `1/12`, `2/12`, and `8/16` worker/thread profiles;
- positive and negative pack/reload controls;
- reconstruction, backward-error, reference-solution, cancellation, resource,
  publication, cleanup, aggregation, retry, and disposition rules.

This ticket does not execute or prejudge that full cohort.

## One command

From the repository root:

```powershell
python tools/prototypes/projected_factor_health_authority_throwaway/run.py
```

The command verifies the accepted issue-45 boundary evidence byte-for-byte,
applies the new rule to ordinals 0, 69, 72, and 150, exercises adversarial
declared-vector, threshold, circularity, indeterminate-boundary, and
low-backward-error false-admission cases, then writes deterministic evidence.

Review the complete state:

```powershell
python tools/prototypes/projected_factor_health_authority_throwaway/tui.py --snapshot
```

Run `tui.py` without arguments for the small interactive reviewer.

## Scope boundary

The boundary exercise is not a 216-source requalification. It does not admit
faer, admit the factor corpus, run the mechanism panel, select persistent
factor storage, or enter the 100k rung.
