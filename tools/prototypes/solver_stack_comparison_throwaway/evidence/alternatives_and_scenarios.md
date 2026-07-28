# Solver/preconditioner alternatives and the smallest discriminating scenarios

Status: research note for the Wayfinder child issue
[“Compare Rust linear-algebra, Krylov, and multilevel preconditioner
stacks”](https://github.com/qingsonger/RapidRBF/issues/13). No candidate in
this note has RapidRBF convergence, resource, runtime, or release evidence yet.
The proposed experiments collect that evidence; they do not preselect a winner.

The frozen source-level comparator is Polatory commit
`4a30beb08053fb339ce899e255be4b6d3f74aa0c`. See
[the detailed baseline audit](./polatory_baseline.md). This note uses:

- **F** — fact visible in a frozen implementation, accepted RapidRBF decision,
  paper, or official library documentation;
- **I** — inference from those facts that is plausible but not established for
  RapidRBF;
- **P** — proposition that must be decided by a prototype or paired run.

Paper results and crate feature lists are never treated as RapidRBF performance
evidence.

## Recommendation in one page

The smallest defensible v1 search should start from this shape:

1. a RapidRBF-owned, **restarted, right-preconditioned FGMRES** driver, with an
   unrestarted Polatory-shape mode retained only as a lower-rung trajectory
   comparator;
2. a RapidRBF-owned preconditioner interface, initially able to reproduce the
   frozen multilevel residual-correction RAS topology;
3. **Faer as the first pure-Rust dense-factor probe**, with nalgebra and one
   narrow native LAPACK path used on the same captured factor corpus rather
   than multiplied through every solver experiment;
4. recurrence residuals as diagnostics, independently recomputed algebraic
   residuals at declared observation points, and the already accepted complete
   external fit/CPD certificate as the only success authority;
5. one caller-owned memory, scratch, and thread grant shared by Krylov bases,
   operator sessions, RAS factors, dense workspaces, and factor I/O.

The first preconditioner alternatives worth measuring are deliberately close
to the frozen hierarchy:

- one-level RAS as an ablation;
- an additive two-/multilevel RAS using the **same** domains, overlap,
  restrictions, local solves, transfer operators, and coarse basis;
- a projected/deflated coarse correction using that same geometric coarse
  space;
- the frozen multilevel residual-correction sweep.

This isolates topology from domain construction. A local-cardinal-function
preconditioner and an H-matrix/null-space preconditioner are credible
research alternatives, but both change too many modules to belong in the first
discriminating matrix.

Flexible GCRO-DR is a follow-up only for declared sequences with reusable
operator identity. It cannot be selected by single-fit results, and it must
compete under the same retained-vector byte cap as restarted FGMRES. Standard
LGMRES and DGMRES are not drop-in replacements for a changing/nonlinear right
preconditioner. Pipelined FGMRES primarily addresses distributed-reduction
latency and is not a first-order v1 question for the accepted single-host,
shared-memory scope.

## Accepted constraints that shape the experiment

The candidate solver is not free to invent a convenient benchmark:

- **F:** The accepted workload ladder is Extended `1k–10k`, Nightly
  `10k–100k`, and Release `1M`. The solver panel includes `exp`, `gau`, `th2`,
  `th3`, `bh3`, `cub`, `sp5`, and heterogeneous `th3+gau`, with geometry,
  warm-start, incremental, operator-stress, thread, and lifecycle lanes. The
  three release journeys are `SCL.EXP-ORDINARY-1M`,
  `SCL.EXP-INCREMENTAL-1M`, and `SCL.HERMITE-COMPOSITE-1M`
  ([accepted issue #9 resolution](https://github.com/qingsonger/RapidRBF/issues/9#issuecomment-5085942864);
  [context summary](../../../../CONTEXT.md#L107-L129)).
- **F:** The matrix-kernel seam owns prepared immutable geometry and
  session-local mutable scratch. Solver, RAS, and stopping policy stay outside
  it. The execution context owns resource and thread permits across Rust,
  Faer, and native code
  ([accepted issue #10 resolution](https://github.com/qingsonger/RapidRBF/issues/10#issuecomment-5086543505)).
- **F:** The sole v1 large-smooth target is the Ferreus-derived action adapter;
  it must qualify through `1k -> 10k -> 100k -> 1M`, while exact-direct and
  compact-neighbor routes remain independently available
  ([accepted issue #12 resolution](https://github.com/qingsonger/RapidRBF/issues/12#issuecomment-5098685468)).
- **F:** Paired measurements require immutable plans, process/scratch
  containment, explicit Fresh/Warm/Prepared-reuse lifecycle labels, and
  configured/effective/maximum-live thread observations. Evidence collected
  before a threshold set exists is `COLLECTED, UNJUDGED`
  ([accepted issue #15 resolution](https://github.com/qingsonger/RapidRBF/issues/15#issuecomment-5087107516)).
- **F:** A successful fit requires complete external value/gradient residual
  coverage, its evaluator certificate, and the normalized CPD-side check.
  Recurrence residuals, restart histories, and Polatory outcomes are
  diagnostics. An operation may spend only its allocated portion of the outer
  error ledger, and no hidden iterations are allowed
  ([accepted issue #16 resolution](https://github.com/qingsonger/RapidRBF/issues/16#issuecomment-5088282917);
  [context summary](../../../../CONTEXT.md#L123-L129)).

Consequently, iteration count alone cannot select a solver, a sampled residual
cannot declare success, and an unbounded “let BLAS decide” thread mode cannot
enter qualification.

## What the frozen stack actually fixes

| Frozen fact | Consequence for comparison |
| --- | --- |
| **F:** Production uses right FGMRES and reconstructs a candidate for an independent interpolation-residual observation after each iteration. There is no restart cycle ([solver](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/solver.hpp#L99-L139)). | Restarting is a deliberate algorithm change. Preserve an unrestarted lower-rung comparator, but do not assume its unbounded basis is release-admissible. |
| **F:** The implementation stores `V` and, for FGMRES, every right-preconditioned `Z` vector ([GMRES storage](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/gmres_base.hpp#L51-L89), [FGMRES storage](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/fgmres.hpp#L21-L25)). | Basis bytes must be charged before the solve. “Maximum iterations” is also a memory policy in an unrestarted implementation. |
| **F:** Arnoldi uses one pass of classical Gram–Schmidt with no reorthogonalization ([implementation](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/krylov/gmres.cpp#L16-L28)). | A robust Rust path needs explicit orthogonalization and breakdown policy; changed trajectories are expected and are not semantic failures. |
| **F:** The preconditioner is not merely a sum of leaf corrections. It applies coarse corrections and ordered multilevel residual-update sweeps ([application](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/ras_preconditioner.hpp#L191-L249)). | “RAS parity” must include hierarchy, transfers, projection, and sweep order. A textbook additive RAS is an alternative, not a port. |
| **F:** Domains overlap, solve a dense constrained local problem, and restrict scatter to inner ownership. The nominal scalar-domain limit is 1024 with about 50% split overlap ([divider](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/domain_divider.hpp#L26-L27), [local solve/scatter](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/fine_grid.hpp#L97-L140)). | Dense factor semantics and storage dominate the local algebra comparison; sparse-matrix benchmark results are not representative. |
| **F:** Fine factors are packed to one anonymous temporary file and reread for each solve. A single mutex protects shared seek/read/write state ([factor handling](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/fine_grid.hpp#L145-L191), [binary cache](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/binary_cache.hpp#L56-L104)). | The baseline has a real bounded-RAM mechanism, but its serialized cursor, unchecked I/O, and invisible page-cache effects are comparison liabilities. |
| **F:** The full-site Polatory observation can still use an approximate FMM action and does not certify the polynomial side constraint ([residual evaluator](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/residual_evaluator.hpp#L55-L107), [accuracy selector](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_accuracy_estimator.hpp#L70-L82)). | Polatory convergence is compatibility evidence, never the RapidRBF success oracle. |

For `n` scalar unknowns and an FGMRES window of `m`, the `V + Z` bases alone
cost

```text
B_basis = 8 * n * (2m + 1) bytes
```

before work vectors, Hessenberg data, candidate reconstruction, operator
sessions, RAS, dense workspaces, and output staging. At `n = 1,000,000`:

| `m` | `V + Z`, decimal | Purpose in the first probe |
| ---: | ---: | --- |
| 5 | 88 MB | Ferreus-lineage small-restart reference |
| 16 | 264 MB | optional refinement point |
| 32 | 520 MB | bounded middle point |
| 64 | 1.032 GB | large-window comparison |
| 100 unrestarted steps | 1.608 GB | frozen public-ceiling shape, diagnostic only |

Mixed Hermite systems have more scalar equations, so the charge scales
linearly above these value-only illustrations.

## Rust dense and Krylov substrate disposition

The deep module should own matrix views, factor records, workspaces, errors,
and diagnostics. No candidate crate type should cross the public solver or
preconditioner seam.

| Candidate | Source-backed capability | RapidRBF disposition |
| --- | --- | --- |
| **Faer** | **F:** Current official docs expose dense LLT, pivoted LBLT, partial/full-pivot LU, QR/column-pivoted QR, SVD, explicit parallelism vocabulary, and Rayon support ([Faer decompositions and features](https://docs.rs/faer/latest/faer/)). | **P:** First pure-Rust factor candidate. Run sequential inside outer domain parallelism. Verify pivot/block metadata, factor-health reporting, scratch sizing, and a stable RapidRBF-owned serialization format; docs establish capability, not parity or speed. |
| **nalgebra** | **F:** Current `linalg` exposes Cholesky, Bunch–Kaufman LBLT, partial/full-pivot LU, column-pivoted QR, and SVD ([nalgebra `linalg`](https://docs.rs/nalgebra/latest/nalgebra/linalg/)). | **P:** Pure-Rust comparison on captured blocks and one end-to-end survivor. Do not infer relative speed or stability from API breadth. |
| **ndarray-linalg / narrow LAPACK** | **F:** `ndarray-linalg` delegates to LAPACK, and its backend selection adds an OpenBLAS, Netlib, or MKL linkage choice ([crate docs](https://docs.rs/ndarray-linalg/latest/ndarray_linalg/), [backend description](https://github.com/rust-ndarray/ndarray-linalg#backend-features)). | **P:** Native comparison only. A narrower owned `dsytrf/dsytrs`/LU adapter may be easier to package and audit than adopting an additional array vocabulary. Either choice must prove tier-one artifact closure and force native worker counts inside the caller grant. |
| **Owned restarted FGMRES** | **F:** Flexible GMRES is specifically defined to allow a changing preconditioner at each step; iterative and multilevel methods are motivating examples ([Saad 1993](https://doi.org/10.1137/0914028)). PETSc exposes restart, modified versus classical Gram–Schmidt, and refinement controls, and supports only right preconditioning for FGMRES ([official `KSPFGMRES`](https://petsc.org/release/manualpages/KSP/KSPFGMRES/)). | **P:** Leading shape because it can make memory, work, observation, and termination contracts first-class. Algorithm authority does not select restart length or reorthogonalization policy. |
| **Kryst** | **F:** Current Rust docs describe a PETSc-like KSP/PC lifecycle, a Faer backend, operator structure/value identities, and classical/pipelined GMRES/FGMRES variants ([Kryst docs](https://docs.rs/kryst/latest/kryst/)). | **P:** Audit as an external Rust oracle/implementation donor, not as a default. Its public feature list does not establish the accepted RapidRBF certificate, RAS topology, resource accounting, cancellation, or tier-one behavior. |
| **PETSc/HPDDM** | **F:** PETSc provides a mature external FGMRES monitor surface; HPDDM provides GCRO-DR, flexible variants, and harmonic-Ritz recycle controls ([`KSPHPDDM`](https://petsc.org/release/manualpages/KSP/KSPHPDDM/)). | **P:** Numerical experiment/oracle only. Shipping PETSc/HPDDM would radically enlarge v1 native distribution and ownership scope. |

### Local and coarse factor choices

The comparison should preserve Polatory's null-space projection and polynomial
recovery while changing one dense solve at a time.

1. **Pivoted LBLT first robust comparator.** It matches the self-adjoint shape
   without assuming every captured projected block is safely positive definite.
   Report 1x1/2x2 pivots, permutations, finite status, solve residual, factor
   bytes, and workspace high-water.
2. **LLT fast-path probe.** Attempt it only after a declared positive-definite
   gate. A failed gate must select a recorded fallback before mutation, not
   silently continue with invalid factors.
3. **Partial/full-pivot LU fallback.** Use it to determine whether generic
   pivoting rescues hard local or coarse cases and what its memory/runtime cost
   is. It is not automatically the production default.
4. **Column-pivoted QR/SVD diagnostic.** Use only on small captured blocks to
   establish rank and explain disagreement. They are not first-order
   million-scale factor choices.
5. **Direct coarse solve first.** The frozen coarse target is small relative to
   the full problem. An iterative/inexact coarse solve makes the
   preconditioner variable and adds another stopping/error budget. FGMRES can
   accommodate that shape, but it belongs in a follow-up only if measurements
   show direct coarse setup, memory, or apply time is material.

**P:** Replay identical byte-for-byte blocks through each candidate before
running full fits. End-to-end solver comparisons should initially fix Faer (or
the first factor survivor) so dense substrate is not confounded with Krylov and
preconditioner topology.

## Krylov alternatives

| Alternative | What authoritative sources establish | What the RapidRBF probe must decide |
| --- | --- | --- |
| Unrestarted right FGMRES | **F:** It preserves the frozen trajectory shape and avoids restart loss, but its two bases grow with every step. The original GMRES paper establishes the full-space method, not an acceptable million-scale memory footprint ([Saad–Schultz 1986](https://doi.org/10.1137/0907058)). | **P:** Lower-rung parity and an upper bound on restart penalty. Do not run it when preflight cannot reserve its full declared basis charge. |
| Restarted right FGMRES | **F:** It bounds basis storage. PETSc exposes restart and orthogonalization policies; Saad establishes flexibility of the right preconditioner. | **P:** Whether `m=5`, `32`, or `64` reaches the external certificate within the declared action/work budget on each mechanism fixture. Add `m=16` only to resolve a bracket between a failing small and successful middle window. |
| Flexible GCRO-DR/recycling | **F:** GCRO-DR was designed for sequences in which both matrix and right-hand side may change and recycles selected prior subspaces ([Parks et al. 2006](https://doi.org/10.1137/040607277), [author/archive PDF](https://vtechworks.lib.vt.edu/bitstream/handle/10919/48161/040607277.pdf)). PETSc/HPDDM exposes flexible GCRO-DR and harmonic-Ritz controls. | **P:** Net action/time reduction over a declared multi-solve sequence after extraction, projection, storage, certificate, and invalidation costs. Give it the same total retained-vector bytes as restarted FGMRES. Never infer value from a single fit. |
| LGMRES | **F:** It augments restart spaces with prior restart error approximations. PETSc notes that it generally still stalls when GMRES(`m`) stalls and documents ordinary left/right, not flexible, preconditioning ([`KSPLGMRES`](https://petsc.org/release/manualpages/KSP/KSPLGMRES/)). | Defer. It is neither a direct flexible replacement nor the strongest sequence-specific discriminator. |
| DGMRES | **F:** PETSc's implementation deflates approximate small-eigenvalue modes at restart and supports left/right but not flexible preconditioning ([`KSPDGMRES`](https://petsc.org/release/manualpages/KSP/KSPDGMRES/)). | Use only as a fixed-linear-preconditioner diagnostic if stagnation needs explanation. Do not substitute it for FGMRES around variable local/coarse work. |
| Pipelined FGMRES | **F:** It requires an extra shift heuristic and is intended to overlap reductions; PETSc notes asynchronous MPI progress as important to performance ([`KSPPIPEFGMRES`](https://petsc.org/release/manualpages/KSP/KSPPIPEFGMRES/)). | Defer for single-host v1 unless profiling shows reductions, rather than operator/preconditioner work and memory traffic, dominate. |
| CG/MINRES after a null-space transform | **F:** CPD RBF interpolation produces a dense indefinite saddle system; published RBF work converts it through augmentation or a null-space method before positive-definite H-Cholesky preconditioning ([Le Borne–Wende 2019](https://doi.org/10.1137/18M119063X)). | Follow-up architecture only. The current approximate action and restricted/multilevel right preconditioner are not a proven fixed symmetric pair, so symmetry-based Krylov methods are not first-round substitutes. |

Two distinctions are essential:

- Flexible preconditioning does **not** automatically license changing the
  matrix action at every Arnoldi step. Inexact-Krylov theory places explicit
  conditions on approximate products
  ([Simoncini–Szyld 2003](https://doi.org/10.1137/S1064827502406415)).
  **P:** Keep the action route and requested accuracy fixed in the first
  comparison; adaptive action accuracy needs its own certified-error probe.
- A geometric coarse/deflation space inside the preconditioner and a harmonic
  Ritz recycle space in GCRO-DR solve different problems. Do not enable both in
  the first sequence experiment; otherwise a gain or regression is
  uninterpretable.

## Preconditioner alternatives

Use one frozen domain hierarchy and factor corpus for the first four rows. This
makes the composition rule—not partition quality—the discriminator.

| Topology | Evidence and hypothesis | First-round role |
| --- | --- | --- |
| Identity | Exposes the exact-action Krylov implementation without RAS. | `1k` diagnostic only; never a credible large hard-case default. |
| One-level RAS | **F:** RAS restricts local corrections to nonoverlap ownership. Cai and Sarkis reported cheaper/faster behavior than classical additive Schwarz for their sparse nonsymmetric examples ([Cai–Sarkis 1999](https://doi.org/10.1137/S106482759732678X)); PETSc exposes basic/restrict/interpolate/none variants and approximate local solves ([`PCASM`](https://petsc.org/release/manualpages/PC/PCASM/)). | Ablation. It reveals whether the coarse/multilevel work is needed for each RBF mechanism. Sparse PDE results do not predict dense RBF behavior. |
| Same-hierarchy additive RAS | Apply all admitted local and coarse corrections as an explicit sum, with no frozen residual-update sweep. | Leading alternative: potentially more parallel and fewer transfer actions, but convergence is wholly empirical. |
| Projected/deflated RAS with geometric coarse space | For full-rank `Z`, use an explicitly versioned coarse projector. PETSc documents `Q = Z(Z'AZ)^{-1}Z'`, `P = I-QA`, and a composed preconditioner `P M^{-1} + factor Q` ([`PCDEFLATION`](https://petsc.org/release/manualpages/PC/PCDEFLATION/)). | Leading coarse-space alternative. Verify `Z'AZ` rank/conditioning, polynomial compatibility, right-preconditioned composition, deterministic fallback, and complete fit certification. |
| Frozen multilevel residual-correction RAS | Exact parity target for hierarchy, restriction, projection, ordered transfers, and coarse solves. | Required comparator and initial port shape, not presumed winner. |
| Multiplicative/hybrid Schwarz variants | RBF domain-decomposition literature establishes that alternating/multiplicative local corrections are meaningful for conditionally positive kernels in specific settings ([Beatson–Light–Billings 2001](https://doi.org/10.1137/S1064827599361771)). | The frozen sweep already supplies the relevant first comparator. More orderings wait until additive versus frozen results show a gap. |
| Local-cardinal/local-Lagrange approximate inverse | RBF-specific work accelerates a closest-point/cardinal-function preconditioner and reports near-linearithmic overall behavior for its multiquadric/biharmonic settings ([Gumerov–Duraiswami 2007](https://doi.org/10.1137/060662083)). | Follow-up if factor volume/I/O is the measured blocker. It needs new value/gradient, composite-kernel, anisotropy, nugget, CPD, and failure-semantics evidence. |
| H-matrix/null-space or augmentation | Published work addresses the actual CPD saddle structure using H-matrices, augmentation/null-space conversion, and H-Cholesky, with reported tests around `N ≈ 40,000` ([Le Borne–Wende 2019](https://doi.org/10.1137/18M119063X)). | Research fallback, not a narrow v1 substitution: it adds a hierarchical-matrix representation and its own accuracy/resource/distribution problem. |
| Generic ASM/MG package | PETSc supplies ASM and multigrid composition primitives, but MG requires problem-specific restriction/interpolation/coarse operators ([`PCMG`](https://petsc.org/release/manualpages/PC/PCMG/)). | External oracle for a matched hierarchy only. “Use AMG” is not a specified alternative for a dense matrix-free CPD/Hermite operator. |

The RBF literature helps choose discriminators, not winners. PetRBF showed that
a one-level RAS/GMRES combination can work extremely well for a rapidly
decaying Gaussian in its distributed 2D setting
([Yokota–Barba–Knepley](https://arxiv.org/abs/0909.5413)). That does not
establish the result for RapidRBF's 3D `exp`, global polyharmonic `th3`, mixed
Hermite rows, or heterogeneous anisotropy. It specifically motivates keeping a
localized smooth case and a global CPD case in the smallest panel.

## Stopping and observation policy

“True residual” must name the operator and the norm:

| Observation | Meaning | Authority |
| --- | --- | --- |
| Arnoldi/least-squares recurrence | Cheap solver-state estimate. | Diagnostic only. |
| Recomputed `b - A_route x` | Algebraic residual for the same fixed configured action route. With an approximate action, it is not the exact physical-system residual. | Diagnostic, useful for detecting recurrence drift and deciding when to attempt certification. PETSc likewise distinguishes its possibly estimated/preconditioned residual from a recomputed true residual ([official monitor](https://petsc.org/release/manualpages/KSP/KSPMonitorTrueResidual/)). |
| Complete external fit observation plus evaluator certificate | Every accepted value/gradient channel in absolute infinity norm, with the action-error allocation included. | Required success authority. |
| Normalized CPD-side residual plus its certificate | Independent polynomial-side constraint. | Required success authority. |
| Small exact-direct reference | Direct full action/solve where feasible. | Lower-rung oracle; not a release substitute. |

Recommended candidate schedule:

1. At iteration zero, compute the declared recomputed algebraic observation.
   An apparent zero initial residual still requires the complete external/CPD
   certificate before success.
2. Record the recurrence every Arnoldi step.
3. Recompute `b - A_route x` at every restart boundary and when the recurrence
   first crosses the certification trigger. On the `1k` calibration fixtures,
   also recompute every iteration so the cheaper schedule can be compared
   against a complete trace.
4. Attempt the complete external/CPD certificate only for a candidate that
   crosses its declared trigger, and once at declared exhaustion if required by
   the experiment plan. Count every action and certificate operation.
5. Return structured `Converged`, `BudgetExhausted`, `Breakdown`,
   `NonFinite`, `RankDeficient`, `ResourceDenied`, or `Cancelled` state.
   Failure publishes no partial interpolant.

The recurrence threshold, restart schedule, complete certificate, and
iteration/action/work budgets must be in the immutable plan. Observation work
must not become hidden solver work.

## Memory, factor I/O, and thread alternatives

### Factor storage

A full lower triangle for a 1024-by-1024 `f64` block is about 4.00 MiB before
pivots, dimensions, checksums, alignment, and format metadata. The actual
projected dimensions and domain count are workload-dependent, so multiplying
that number into a hierarchy is a measurement, not an accepted budget.

Compare these policies only after the factor record is self-describing and
validated:

1. **Frozen single-cursor spill** — parity mechanism and contention baseline.
2. **Resident-if-admitted** — keep immutable factors in RAM only when the
   resource preflight admits all persistent bytes.
3. **Bounded resident LRU plus positional spill** — charge a declared resident
   cap, issue independent offset-based reads, validate lengths/checksums, and
   record hits, misses, bytes, queue/wait time, and page-fault-sensitive
   lifecycle. This is the leading bounded policy.
4. **Recompute-on-use** — constrained-resource diagnostic. It avoids factor
   scratch but repeats cubic setup and therefore must report rebuild work.
5. **Memory mapping** — diagnostic only until RSS/page-cache accounting is
   portable enough for the accepted resource contract. It must not make
   disk-backed pages look free.

Never serialize an undocumented crate-internal factor object. RapidRBF must own
the factor format or rebuild from a documented matrix representation.

### Shared grant and threading

The first production-shaped policy should parallelize independent RAS domains
and operator chunks in one caller-owned pool while forcing each local dense
factor/solve to sequential mode. A coarse factorization may receive an
explicit temporary sub-grant only after the outer domain work is quiescent.

Every run records:

- configured, effective, and maximum-live threads;
- whether Rayon, BLAS/LAPACK, operator, and I/O workers are inside the grant;
- persistent prepared/operator/preconditioner bytes;
- session and factorization workspace high-water;
- Krylov basis bytes and retained recycle bytes;
- scratch reserved/high-water/read/written bytes and I/O wait;
- cache hits/misses and factor rebuilds.

An independent Rayon global pool plus a threaded BLAS is not an admissible
configuration merely because it is fast. Thread overrun, scratch escape, or
post-preflight allocation beyond the declared policy blocks qualification.

## Smallest discriminating scenario matrix

These are prototype IDs, not new acceptance IDs. Each row is a deliberate
slice of already accepted workload families. The full issue #9 matrix remains
the eventual gate.

| Prototype row | Accepted seed and exact lower-rung shape | It discriminates | Why it cannot be removed |
| --- | --- | --- | --- |
| `M1-EXP-LOCAL` | Lower rungs of `SCL.EXP-ORDINARY-1M`: 3D value-only `exp(psill=1, range=0.02)`, identity anisotropy, degree 0, zero nugget; `1k` exact-direct and `10k` assigned large-smooth route. | Identity/one-level RAS versus coarse/multilevel work; restart cost on a localized smooth kernel. | Without it, a globally robust but unnecessarily expensive preconditioner can win by construction. |
| `M2-TH3-CPD` | `th3` from the fixed solver panel, value-only, AUTO degree, nonuniform-boundary geometry; `1k` exact-direct and `10k` assigned route. | Polynomial constraint, geometric coarse space, additive versus projected/deflated versus frozen sweep. | `exp` cannot reveal whether global CPD modes require the coarse path. |
| `M3-HERMITE-COMPOSITE` | Lower rungs of `SCL.HERMITE-COMPOSITE-1M`: `th3(c>0)+gau`, distinct full anisotropies including shear, AUTO degree, nonzero nugget, 75% value plus 25% full-gradient observations; `1k` exact-direct and `10k` assigned route. | Mixed scalar multiplicity, derivative blocks, local/coarse pivoting, anisotropy partitioning, false convergence, and basis memory. | Value-only blocks do not exercise the release-critical Hermite algebra. |
| `M4-GEOMETRY-FAILURE` | `FIT.GEOMETRY` at `1k`, then selected valid cases at `10k`: clustered, near-coincident, and nonuniform boundary triplets, plus a separately labelled exact-coincident/rank-invalid control. | CGS versus robust orthogonalization, LLT gate versus pivoted factors, rank/breakdown/nonfinite reporting, and atomic failure. | Well-spaced successful fits cannot select a safe factor or termination policy. Invalid controls must not be scored as convergence failures. |
| `S1-SAME-A-SEQUENCE` | One prepared geometry/model/operator with at least several deterministic payload/right-hand-side changes, plus accepted compatible `FIT.WARM` orderings. | Warm start alone versus byte-capped flexible GCRO-DR; preparation and factor reuse; complete per-solve certification. | Recycling has no testable value in a single solve. |
| `S2-CHANGED-A-SEQUENCE` | Nested `FIT.INCREMENTAL` `1k -> 10k` plus an explicitly incompatible warm case. | Conservative recycle invalidation when dimensions, geometry, anisotropy, polynomial space, action route, or factor identity changes. | A recycler that is fast only because it reuses an invalid space is a correctness defect. Standard GCRO-DR vectors cannot cross a dimension change without an explicit mapping. |
| `R1-RESOURCE-100K` | Nightly `100k` lower rungs for `exp`, `th3`, and the Hermite composite; Fresh, declared warm-up, and Prepared-reuse lifecycles; accepted 1/2/physical-core lanes. | Restart basis versus factor residency, bounded LRU versus frozen spill, operator/preconditioner workspace, scratch, cache warmth, thread ownership, cancellation, and preflight failure. | `10k` does not create the million-scale memory/I/O competition; jumping straight to `1M` makes diagnosis too expensive. |
| `L1-RELEASE-1M` | The exact three accepted release journeys, physical-core tier-one lane, immutable paired plan and complete rectangular evaluations. | Finalist-only correctness, convergence, resource, runtime, artifact, and baseline parity. | No lower rung can release the solver. |

`M1–M4` are the minimum mechanism panel. The other fixed solver families still
run before qualification; they are not all needed to choose which alternatives
deserve the expensive `100k` rung.

## Staged experiment matrix, not a Cartesian product

### Stage 0 — captured dense-factor corpus

Capture local projected blocks, coarse blocks, right-hand sides, and expected
polynomial recovery from `M1–M4`. Replay:

- Faer LBLT and gated LLT;
- nalgebra LBLT;
- one narrow native pivoted symmetric-indefinite/LU path;
- LU and QR/SVD diagnostics only on disagreements.

Compare solution/correction residuals, polynomial recovery, pivot/rank/status,
nonfinite handling, setup/apply time, factor/workspace bytes, serialization,
and sequential thread count. Promote at most two factor substrates to one
end-to-end `10k` replay. This prevents dense-library choice from multiplying
the Krylov/preconditioner matrix.

### Stage 1 — `1k` exact-action algorithm truth table

Fix the first factor survivor. Run:

- Krylov: unrestarted FGMRES with the frozen declared cap; restarted FGMRES
  `m = 5, 32, 64`;
- orthogonalization: frozen one-pass CGS and the candidate robust policy;
- preconditioner: identity, one-level RAS, same-hierarchy additive RAS,
  projected/deflated RAS, frozen multilevel residual-correction RAS;
- observation: every-iteration recomputed exact algebraic residual plus the
  complete external/CPD certificate.

Use identical initial guesses and budgets. Add `m=16` only if it resolves the
boundary between a failing `m=5` and successful `m=32`; do not add restart
points merely to make a smooth chart.

### Stage 2 — `10k` mechanism panel

Remove identity except as a targeted diagnostic. Keep:

- unrestarted FGMRES only as the affordable trajectory/reference run;
- restarted `m = 5, 32, 64`;
- the robust orthogonalization policy, with legacy CGS rerun only where
  trajectories or certification differ;
- the four RAS topologies using the same hierarchy;
- fixed exact-direct action where feasible and the assigned/certified action
  route as a paired operator comparison;
- restart-boundary/triggered algebraic observations calibrated against Stage
  1.

Advance only configurations that certify all valid cases and return the
expected structured failure on invalid controls.

### Stage 3 — sequence-only recycling

On `S1`, compare warm-started restarted FGMRES with flexible GCRO-DR. Charge
all `U`, `C`, harmonic-Ritz, and work vectors, and reduce the ordinary restart
space so both runs have the same retained-vector byte grant. Record first-solve
overhead and cumulative action/time curves over the whole declared sequence.

On `S2`, test invalidation, not speed. A recycle space has a declared identity
including dimensions, geometry/model/anisotropy/polynomial fingerprint, action
route/certificate version, preconditioner/hierarchy identity, and numeric
generation. Unknown identity means discard. Mapping a recycle space across an
incremental dimension change is a separate future algorithm, not an implicit
optimization.

### Stage 4 — `100k` resource and thread rung

Carry at most two Krylov/preconditioner combinations. Compare:

- frozen serialized spill;
- resident-if-admitted;
- bounded LRU plus positional spill;
- one deliberately constrained recompute-on-use diagnostic;
- 1, 2, and physical-core thread lanes;
- Fresh, declared warm-up, and Prepared-reuse lifecycles.

Resource grant values must come from a versioned threshold set. Until that set
exists, runs are collection-only and remain `COLLECTED, UNJUDGED`. An
additional `mandatory_bytes - 1` preflight fixture may verify atomic
`ResourceDenied`; it is not a performance threshold.

### Stage 5 — release

Run only finalists on all three `1M` journeys, paired against the frozen
baseline under the same pinned host, inputs, affinity, thread grant, cache
policy, lifecycle, wrapper, and artifact provenance. Retain scalar-equation
count, complete certificates, iteration/restart trajectory, actions,
preconditioner work, peak memory, scratch/I/O, effective threads, and
rectangular evaluation evidence.

## Decision order and hard gates

Judge in this order:

1. **Semantic and failure correctness.** Reject false success, incomplete
   external coverage, CPD failure, nonfinite publication, invalid recycle
   reuse, partial state on cancellation/failure, or mismatch with required
   deterministic channels.
2. **Operational admissibility.** Reject thread/scratch escape, undeclared
   allocation after preflight, uncontained temporary files, corrupt/short
   factor records, or failure to clean up.
3. **Convergence robustness.** Compare success coverage under the same declared
   iteration, action, preconditioner-work, and certificate budgets. A smaller
   recurrence residual is not a win when the external certificate fails.
4. **Resource shape.** Compare persistent/session peak bytes, vector/factor
   competition, scratch high-water, I/O wait, cache dependence, and factor
   rebuilds.
5. **Work and runtime.** Compare expensive action count, transfer actions,
   local/coarse solves, orthogonalization/reconstruction traffic, certificate
   work, and paired wall time. Report empirical results by scenario and
   lifecycle; do not convert paper asymptotics into measured RapidRBF claims.
6. **Distribution closure.** A native path must still pass the four tier-one
   artifacts and thread-control contract. Local speed cannot waive that gate.

An unrestarted method that cannot reserve its declared bases is not “slow”; it
is operationally inadmissible for that grant and remains a lower-rung oracle.
Likewise, a one-level method that wins `exp` but fails `th3` is a useful
route-specific result, not a global winner.

## Claim boundaries

| Source claim | It licenses | It does **not** license |
| --- | --- | --- |
| Saad's FGMRES permits changing preconditioners. | Owning a flexible-right driver around iterative/multilevel local work. | Changing the matrix action without an inexact-action contract; selecting restart length or declaring RapidRBF convergence. |
| Cai–Sarkis report favorable RAS examples. | Testing restricted versus basic/additive scatter. | Assuming sparse PDE iteration/runtime results transfer to dense CPD/Hermite RBF systems. |
| PetRBF reports strong Gaussian RAS/GMRES scaling. | Keeping a localized smooth discriminator and measuring overlap/domain trade-offs. | Predicting 3D `exp`, global `th3`, composite Hermite, or single-host behavior. |
| Beatson et al. analyze RBF domain decomposition. | Treating multiplicative/domain decomposition as mathematically relevant to CPD RBF interpolation. | Assuming the frozen hierarchy or every accepted kernel has that paper's convergence. |
| Gumerov–Duraiswami accelerate a local cardinal preconditioner. | A factor-I/O-saving follow-up hypothesis. | Shipping it without Hermite/composite/aniso/nugget/CPD evidence. |
| Parks et al. establish recycling for sequences. | A same-operator/changing-RHS and conservative changed-operator experiment. | Enabling recycle state for ordinary isolated fits or across dimension changes without a mapping. |
| Faer/nalgebra/LAPACK/Kryst docs list capabilities. | Building narrow probes and external oracles. | Any claim about factor parity, convergence, runtime, resource use, cancellation, or tier-one artifacts. |

## Open axes after the smallest matrix

The prototype should return evidence on these axes rather than hide them in
defaults:

1. restart window and robust orthogonalization/reorthogonalization trigger;
2. one-level versus additive hierarchy versus projected coarse correction
   versus frozen residual-correction sweep;
3. coarse-space construction, dimension, rank gate, and reuse identity;
4. LBLT default versus gated LLT and explicit LU fallback;
5. direct coarse factor versus a later bounded inexact coarse solve;
6. recurrence/algebraic/certified observation cadence and action-accuracy
   allocation;
7. resident-factor cap, positional-spill record format, eviction policy,
   recomputation fallback, and whether mmap can be accounted portably;
8. division of the one thread grant between outer domains, operator chunks,
   dense kernels, and coarse work;
9. warm start versus GCRO-DR benefit under equal retained-vector bytes and
   conservative invalidation;
10. owned FGMRES versus Kryst/PETSc as implementation donor/oracle;
11. whether measured factor/I/O pressure justifies a local-cardinal or
    H-matrix/null-space follow-up;
12. whether any benefit survives the complete accepted family, geometry,
    lifecycle, thread, resource, tier-one, and `1M` gates.

Until those runs exist, the narrow recommendation is architectural: own the
restarted flexible solver and its truth/resource contracts, port the frozen RAS
topology as the parity comparator, and spend the first empirical budget on the
same-hierarchy additive and projected-coarse variants. That is the smallest
experiment capable of distinguishing restart memory, global-mode robustness,
local-factor safety, factor I/O, and sequence reuse without conflating all of
them.
