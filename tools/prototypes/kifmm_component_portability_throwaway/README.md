# THROWAWAY PROTOTYPE — kifmm component/portability lab

Run it from the RapidRBF repository root:

```powershell
python tools/prototypes/kifmm_component_portability_throwaway/tui.py
```

Print one non-interactive frame:

```powershell
python tools/prototypes/kifmm_component_portability_throwaway/tui.py --snapshot
```

## Question

Can frozen `kifmm`
`d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068` be adapted behind
RapidRBF's private matrix-kernel seam for dimensions 1–3, canonical
`A`/`F`/`F^T`/`H`, smooth and split RBF contributions, anisotropy, certified
accuracy, bounded reuse, operational control, and tier-one distribution; and
which observed failure keeps a route out of `Auto`?

This is an in-memory HITL decision lab backed by two throwaway probes. It does
not implement RapidRBF and does not qualify kifmm:

- the metric-action probe checks the algebra of a scalar-radial, multiple-RHS,
  target-derivative adapter against an independent direct formulation;
- the source-surface probe checks what the frozen kifmm and green-kernels source
  actually expose and consume.

The first probe demonstrates a mapping identity, not a kifmm execution. The
second demonstrates source structure, not runtime behavior. A Windows
`cargo check` observation supplies one concrete build result. None of these is
a sound call-scoped certificate, accepted scale evidence, or tier-one closure.

## Decision routes

Use `e` in the lab to switch among four deliberately distinct claims:

1. **Current bounded-fork candidate** — a plausible fork keeps scalar
   equivalent/local expansions, embeds 1D/2D metric coordinates in 3D,
   generalizes the hard-coded kernel metadata, adds target Hessians, removes
   unconditional FFTW, and remains `FORCED-PROTOTYPE-ONLY`.
2. **Frozen as-is** — the exact checkout is `AUTO-INELIGIBLE`: it cannot build
   on Windows as shipped and its core does not consume the advertised
   component counts or expose RapidRBF RBF/Hessian semantics.
3. **Component-trait shortcut** — treating green-kernels' component-count
   methods as proof that KiFMM supports arbitrary component actions is
   `AUTO-INELIGIBLE`; the frozen KiFMM core never calls those methods.
4. **All gates close** — a visibly counterfactual view used only to review the
   promotion rule.

The fork route is intentionally substantial. Calling it plausible means only
that the scalar action decomposition and lower-dimensional embedding are not
mathematically contradicted by the probes. It does not mean that the frozen
implementation already has that capability.

## Seam discipline

RapidRBF's matrix-kernel module remains the deep module. Its small action-level
interface owns canonical semantics, anisotropy, split composition,
certification, routing, resources, and normalized failures. A kifmm fork would
be one crate-private adapter at that existing seam, alongside direct and
exact-neighbor adapters; it does not justify a public backend/plugin interface.

The green-kernels trait and KiFMM's mutable object model are implementation
details behind the adapter. Their component counts, expansion orders, FFT/BLAS
selection, tree depth, and native handles must not leak into the matrix-kernel
interface or portable artifacts. Tests and acceptance evidence cross the
action-level interface and assert outcomes, certificates, and failures—not
KiFMM internals.

## Controls

- `a` — next canonical `A`, `F`, `F^T`, or `H` action
- `d` — next physical dimension, 1D through 3D
- `f` — switch smooth contribution / `sp*` smooth tail
- `x` — next identity / diagonal / valid nonsymmetric-shear anisotropy
- `u` — switch `PreparedOperator` / `PreparedField`
- `e` — next decision/evidence route
- `r` — reset the lab
- `q` — quit

Every action redraws the full state. The frame keeps source facts, mapping
evidence, missing evidence, and counterfactual assumptions visibly separate.

## Frozen source findings

- The checkout is pinned to `d4ca4b5`, but it ignores `Cargo.lock`. Resolving
  the audited graph selected green-kernels `ed83120` and RLST `33bd9a6`; a
  production fork must pin or vendor the complete graph rather than rely on the
  moving git declarations.
- green-kernels' `Kernel` trait declares `domain_component_count()` and
  `range_component_count(...)`. Frozen KiFMM's non-binding Rust core contains
  no call to either method. It instead derives output width from the closed
  `Value` / `ValueDeriv` enum and `dim + 1`.
- The single-node builder hard-codes `dim = 3`; the tree, surfaces, Morton keys,
  FFT layouts, and transfer vectors are three-dimensional. Zero-padding 1D/2D
  metric coordinates is a candidate adapter technique, not native
  lower-dimensional support.
- KiFMM's source/target/M2L metadata implementations are specialized for
  `Laplace3dKernel` and `Helmholtz3dKernel`. The frozen crate has no RapidRBF
  RBF kernel implementation and no generic plug-in path requiring only the
  green-kernels trait.
- Multiple scalar right-hand sides and value-plus-target-gradient output exist.
  The single-node BLAS translation exercises matrix RHS, while the FFT
  translation explicitly rejects it. The BLAS path is enough to make `A`,
  `F`, and `F^T` decomposition plausible after a custom scalar RBF fork. `H`
  needs target Hessians, which the two-value `GreenKernelEvalType` cannot
  request.
- Frozen homogeneous scaling is Laplace-specific. A candidate RBF fork must
  use level-specific non-homogeneous metadata rather than falsely marking every
  family homogeneous.
- The candidate family scope is the ten complete smooth families
  `bh2/bh3/th2/th3/exp/gau/gc3/gc5/gc7/gc9` plus only the smooth tails of
  `sp3/sp5/sp7/sp9`. Rust-owned exact-neighbor remains responsible for
  `cub/sph` and each `sp*` compact correction.
- Zero-padding preserves radial algebra for 1D/2D, but frozen depth estimation
  assumes 3D occupancy. A fork needs explicit or occupancy-aware depth; a
  zero-span all-coincident metric cloud must capability-skip to direct rather
  than build a degenerate tree.
- `attach_charges_*` clears and reuses one mutable KiFMM object. That is useful
  partial geometry reuse, but it is not RapidRBF's immutable, `Send + Sync`
  prepared handle with exclusive call sessions and proof-scoped state.
- The core has no cancellation/deadline checks, uses Rayon parallel iterators
  without an owned explicit pool in its interface, and delegates dense work to
  BLAS/LAPACK without complete thread/resource accounting.
- Approximation order and compression thresholds are tuning inputs. Frozen
  tests use sampled/L2 comparisons; no call-scoped full-batch absolute
  infinity-norm certificate is produced.

## Windows and distribution observation

On Windows x86_64 MSVC with Rust 1.96.1, the exact frozen checkout resolved its
git dependencies and then failed in `kifmm-fftw-src`: the build script tried to
execute FFTW's Unix `configure` script directly and Windows returned OS error
193 (“not a valid Win32 application”). This is a terminal observed build
failure, not an inference from the README.

The dependency is more than a build inconvenience:

- kifmm unconditionally builds and statically links FFTW 3.3.9;
- FFTW's ordinary distribution terms are GPL, while the Wayfinder map forbids
  strong-copyleft runtime dependencies in official v1.0.0 artifacts;
- RLST uses external BLAS/LAPACK calls, so a concrete provider, licenses,
  runtime bundling, and thread ownership still need closure even if the
  low-rank BLAS translation replaces the FFT path.

A viable fork must remove or feature-gate FFTW from the shipped graph and pick
reviewed, redistributable numerical providers. Merely making `configure` run
on Windows would not close the release gate.

## Metric-action probe

For physical points and gradient weights, the probe forms metric coordinates
and weights

```text
u = A (x - origin)
w = A q
```

for deterministic 1D/2D/3D self and cross cases. With a scalar Gaussian radial
kernel it compares:

```text
A   : sum phi(u_t-u_s) * alpha
F   : -sum_c d/du_c [sum phi * w_c]
F^T : A^T grad_u [sum phi * alpha]
H   : -A^T [sum_c Hessian_u(sum phi * w_c)[:, c]]
```

against direct physical formulas. Lower-dimensional cases are zero-padded into
3D on the adapter side. Identity, diagonal, and valid nonsymmetric-shear
transforms are covered where meaningful.

Agreement supports the decomposition only. The probe deliberately bypasses
KiFMM's tree, translations, compression, accumulation order, native
dependencies, and error estimation.

## Promotion rule under review

`Auto` requires all six gates together:

1. complete semantic coverage;
2. a sound call-scoped certificate;
3. bounded immutable prepared lifetimes;
4. cancellation, resource, thread, and deterministic execution control;
5. accepted scale and repeated-memory qualification; and
6. tier-one build, runtime, artifact, and license closure.

An observed contradiction is a hard failure. An unmeasured or unimplemented
gate is missing, not a pass. The first blocking gate is always displayed.

## Companion primary sources

- `probe/throwaway_metric_action_probe.py` — exact scalar decomposition probe.
- `probe/observed-metric-action-windows-x86_64.json` — captured probe output.
- `probe/source_surface_probe.py` — exact frozen-source assertions.
- `probe/observed-source-surface.json` — captured source audit.
- `probe/observed-windows-build.json` — terminal Windows build observation.
- `probe/kifmm-d4ca4b5-Cargo.lock` — exact dependency graph used by the build
  observation.
- `probe/REPRODUCE.md` — clean-checkout commands and deliberate limits.

This branch remains throwaway primary evidence. Only the eventual human-reviewed
decision belongs in the Wayfinder map or on `main`.
