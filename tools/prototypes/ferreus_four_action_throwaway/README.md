# THROWAWAY PROTOTYPE — Ferreus four-action adaptation lab

Run it from the repository root:

```powershell
python tools/prototypes/ferreus_four_action_throwaway/tui.py
```

Print one non-interactive frame:

```powershell
python tools/prototypes/ferreus_four_action_throwaway/tui.py --snapshot
```

## Question

Can frozen Ferreus
`d0442ee978668386f6ccbeec866bfa52fcc4484f` plausibly be adapted behind
RapidRBF's private matrix-kernel seam without unsafe component symmetry
reduction, and which observed failure or missing evidence gate keeps it out of
`Auto`?

This is an in-memory decision prototype. It does not execute Ferreus or
RapidRBF. The source facts and small Gaussian/transformed-coordinate probe
summaries are frozen inputs from the companion audit and recorded Rust probes;
changing controls only asks how those facts bear on a selected contract case.

Empirical agreement is useful to **falsify** an unsafe component transform and
to **support** the plausibility of a safe scalar-lift adaptation. Approximation
errors are therefore labelled `OBSERVED SUPPORT`, never an acceptance pass.
`OBSERVED PASS` is reserved here for a test that actually passed. Neither is a
sound call-scoped error certificate, complete family/action coverage,
scale/resource evidence, tier-one packaging closure, or an `Auto` promotion.
The all-gates-pass view is visibly counterfactual and cannot be read as an
observation.

## Controls

- `a` — next canonical `A`, `F`, `F^T`, or `H` action
- `d` — next dimension, 1D through 3D
- `f` — switch smooth contribution / `sp*` smooth tail
- `g` — switch self / cross geometry
- `x` — next identity / diagonal / valid nonsymmetric-shear anisotropy
  (a nonsymmetric shear is unavailable in 1D)
- `u` — switch `PreparedOperator` / `PreparedField`
- `e` — next current, observed-rejection, or counterfactual evidence view
- `r` — reset the lab
- `q` — quit

Every action redraws the full decision state. `cub` and `sph` remain
Rust-owned exact-neighbor routes; for `sp3/5/7/9`, the lab considers only the
smooth tail behind the adapter while Rust owns the canonical split and compact
contribution.

The frozen numerical rows apply only to the Gaussian smooth contribution with
1D diagonal scaling or 2D/3D nonsymmetric shear. Selecting an unrun
family/form or transform changes the selected-case ledger to `MISSING`; the
frozen row remains visible only as explicitly labelled context.

## Frozen evidence seed

- Ferreus is pinned to `d0442ee`. Its scalar BBFMM seam instantiates dimensions
  1-3. The current API has scalar evaluation and target gradients but no
  Hessian output.
- On Windows, 1 BBFMM unit test and 3 doctests pass with pinned Rust 1.85. The
  locked tree fails with current Rust 1.96 in transitive `spindle 0.2.5`.
- The small Gaussian corpus uses diagonal scaling in 1D and nonsymmetric shear
  in 2D/3D. It covers each dimension with 128 sources against 83 cross targets
  and 128 self targets. The per-row maximum near-control errors range from
  `5.773159728050814e-15` to
  `1.2434497875801753e-14`. There are 6 near-control and 6
  symmetry-reduced far-field rows, 12 total.
- The TUI selects the exact frozen row for its dimension and geometry.
  Across the six far-field rows, absolute errors were
  `1.11503408595226e-6` to `4.2364467345290535e-6` for `A`,
  `4.948867313903094e-5` to `3.306160658285151e-4` for `F^T`, and
  `7.964282082800755e-6` to `4.893211298861999e-5` for the radial
  multi-right-hand-side unsigned `F` mapping. The probe did not apply
  RapidRBF's canonical external minus on either side, so it supports the
  component mapping but does not test that sign.
- Treating scalar signed/permuted interaction offsets as component transforms is
  unsafe: far component-`F` errors span `1.0426441986466783` to
  `10.3755590606318`, and far component-`H` errors span
  `6.306803972941173` to `15.065703042324033`.
- A throwaway uniform-tree fork keeps M2L scalar/radial and differentiates the
  target expansion twice. Its separate 96-source Gaussian corpus uses 1D
  diagonal scaling and 2D/3D shear, covering self/cross and near/far cases.
  Near `H` max-absolute errors were
  `2.081668e-17`-`2.775558e-17`; far `H` max-absolute errors were
  `5.141875e-6`-`2.548270e-5`, with nonzero V-lists and M2L reference
  operators. This supports the mapping only; adaptive W-list/M2P Hessians,
  compression, other families, and a certificate remain untested.
- A sound complete-batch certificate, bounded immutable prepared sessions,
  cancellation, conservative resource and thread accounting, deterministic
  accumulation, the 1k -> 10k -> 100k scale ladder, and accepted clean-host
  evidence on all four tier-one platforms are missing.

These observations are deliberately not upgraded into thresholds. Numerical
and resource judgment remains owned by separately versioned acceptance
standards and the accepted paired-evidence boundary.

## State model under review

The lab tests three distinct conclusions:

1. The safe route keeps scalar M2L/local expansions, applies only the
   action-required source-vector and target-output transforms outside Ferreus,
   adds target Hessians in a fixed fork, and remains
   `FORCED-PROTOTYPE-ONLY` while any promotion gate is missing.
2. The component-kernel shortcut is `AUTO-INELIGIBLE` because actual probes
   falsify its reference-vector sign/axis component transforms.
3. An all-gates-pass state is useful only to test the promotion rule and is
   labelled `COUNTERFACTUAL AUTO-ELIGIBLE`.

The six gates shown together are semantic closure, a sound call-scoped
certificate, prepared-lifetime closure, operational control, scale
qualification, and tier-one distribution closure. The first blocking gate is
always visible.

## Decision context

This prototype raises the fidelity of:

- [Probe Ferreus four-action adaptation viability](https://github.com/qingsonger/RapidRBF/issues/29)
- [Define the backend-neutral matrix-kernel contract](https://github.com/qingsonger/RapidRBF/issues/10)
- [Compare direct, pure-Rust FMM, ScalFMM3 FFI, and hybrid backends](https://github.com/qingsonger/RapidRBF/issues/11)
- [Prototype the differential and resource measurement harness](https://github.com/qingsonger/RapidRBF/issues/15)
- [Set the numerical and convergence acceptance standard](https://github.com/qingsonger/RapidRBF/issues/16)
- [Set the performance, memory, threading, and cache acceptance standard](https://github.com/qingsonger/RapidRBF/issues/17)

The prototype remains on its throwaway branch as a primary source. Only a
human-reviewed decision belongs on `main`.

## Companion primary sources

- `probe/observed-windows-x86_64.json` records the scalar `A/F/F^T` and rejected
  component-kernel observations.
- `probe/observed-hessian-windows-x86_64.json` records all twelve target-Hessian
  rows and path assertions.
- `probe/throwaway_scalar_action_probe.rs` is the exact scalar-action example
  used to record the `A/F/F^T` and rejected component-kernel observations.
- `probe/ferreus-d0442ee-target-hessian.patch` is the exact frozen-source patch.
- `probe/throwaway_target_hessian_probe.rs` is the exact probe example.
- `probe/REPRODUCE.md` gives the clean-clone commands and deliberate limits.
