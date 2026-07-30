# Issue 63 captured residual-stagnation diagnosis

## Question

Why does canonical coarse4096 improve both `M3-HERMITE-10K` residual channels by
about 22x yet still exhaust the unchanged work grant, and does one bounded
mechanism remain credible inside restarted right-FGMRES with same-hierarchy
RAS?

## Accepted red state

The deterministic replay command is:

```powershell
.\repro-issue63.ps1
```

It binds the accepted Issue 62 evidence identity
`4879f1da043af898a0a0f2830529a241fb0a64da5ece6df81c467ee3b74e76c3`
and reproduces exactly one coarse4096 failure among the six 10k candidates:
`M3-HERMITE-10K` at 100 iterations and 200 preconditioner-internal actions,
with value residual `3.6434752952778648e-3` and gradient residual
`5.3808841088235727e-2`.

## Diagnosis

- Generated factor health, complete-direct action identity, dynamic backward
  error, CPD, resource, and cleanup evidence all close. The 4096 factor path
  is not the explanation.
- Current-coarse to coarse4096 improvement is nearly channel-proportional:
  about `22.44x` for value and `22.74x` for gradient. The gradient/value
  residual ratio stays near 15, so target growth attenuates the same coupled
  error shape rather than introducing a qualitatively new correction.
- Accepted topology evidence already rejects one-level, additive,
  projected-deflated, reversed residual correction, scaling-only, and robust
  versus parity orthogonalization as the missing mechanism.
- The sole new single-variable probe keeps the complete-direct M3 action,
  coarse4096 factor, robust MGS/DGKS, 100 iterations, 200 internal actions,
  thresholds, topology, overlap, scale, and execution lane unchanged, and
  changes only the Krylov window from 64 to the full 100-iteration grant.
- That full-window run still exhausts the grant at value residual
  `2.5424728685288223e-3` and gradient residual
  `3.8802020459015263e-2`. It improves the m64 endpoint by only about
  `1.43x` and `1.39x`, while remaining about `42,657x` and `650,989x` above
  `2^-24`.
- The full-window basis has a `2.2204460492503131e-15` maximum
  orthogonality defect, passes CPD at `9.4759747951520585e-18`, uses exactly
  100 solver and 200 preconditioner actions, and peaks at
  `4,224,020,480 / 8,589,934,592` bytes. Restart truncation, orthogonalization,
  work-accounting, and the resource gate therefore do not explain the gap.

The surviving cause is structural: geometrically selected same-hierarchy
coarse content does not contain the coupled global M3 slow modes. Conditioning
of the qualified factor may affect coefficient sensitivity, but it cannot
explain a complete-direct, backward-stable, CPD-clean trajectory that remains
nonpassing even when all 100 Krylov directions are retained. Fine/coarse
composition can move residual between channels but every registered
composition remains nonpassing.

## Proposed disposition

**`SAME_HIERARCHY_RAS_FAMILY_EXHAUSTED_FOR_V1`**

Do not freeze another coarse-size, restart, scaling, overlap, topology, or
orthogonalization experiment. A credible million-scale successor must change
the preconditioner space construction or solver family, not escalate the same
geometric hierarchy. Selecting that successor belongs to the downstream
solver-and-resource-model decision; the current same-hierarchy 100k storage
experiment has no globally viable mechanism to measure.

This diagnosis does not select a replacement solver and does not admit a
factor backend. Live human ratification is required before Issue 63 may close.
