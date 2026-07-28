# Rust solver-stack candidates for RapidRBF v1

Research date: 2026-07-28

This note evaluates Rust dense linear-algebra, sparse-linear-algebra, and
Krylov/FGMRES candidates against the RapidRBF v1 constraints. It uses primary
sources only: versioned crate documentation and manifests, project source and
CI files, and vendor documentation. It is a capability and distribution
screen, not a performance benchmark.

Labels used below:

- **[E] Evidence** — directly supported by a linked primary source.
- **[I] Inference** — a RapidRBF-specific conclusion drawn from that evidence.
- **[G] Gap** — not established by the available primary-source evidence and
  therefore something the prototype or CI must test.

## Decision in brief

1. **First dense/local-factor probe: audited `faer` 0.24.4 behind a small
   RapidRBF-owned interface.** It is the strongest current source-evidence fit:
   pure Rust, MIT, active, broad `f64` dense decompositions, sparse direct
   solvers, explicit sequential/Rayon execution, and low-level caller-provided
   scratch. This is a probe order, not dependency adoption.
2. **Leading Krylov shape: own a small restarted right-FGMRES implementation.** None
   of the inspected crates simultaneously establishes the required
   matrix-free operator, changing right preconditioner, stored `Z` basis,
   restart, true-residual acceptance, cancellation/monitor callback, and
   caller-budgeted reusable workspace contract.
3. **Best off-the-shelf FGMRES spike/oracle: audited `kryst` 4.3.0.** Its implementation
   is the closest behavioral match and should be tested, but it is young,
   broad in scope, uses owned allocations, and its upstream CI currently
   establishes Linux only.
4. **Native BLAS/LAPACK: benchmark-only optional adapter, not the first
   artifact candidate.** `ndarray-linalg`/`lax` provide a sound Rust LAPACK layer, but
   OpenBLAS/MKL selection, artifacts, licenses, threading, and tier-one
   packaging become part of RapidRBF's product surface.
5. **Sparse libraries are not the critical path for v1.** The global RBF
   operator is matrix-free and the RAS subdomains are dense. Use `faer` sparse
   first if a coarse or experimental sparse path is added; do not introduce a
   second sparse type system without a measured need.

## RapidRBF requirements that drive the choice

- Tier-one artifacts: Windows x86-64, Linux x86-64 glibc, macOS arm64, and
  macOS x86-64.
- `f64` dense LU/QR/Cholesky and an indefinite symmetric factorization for
  constrained local systems; local domains can reach roughly 1024 unknowns.
- Matrix-free restarted **right flexible GMRES**: the preconditioner may change
  by iteration, so the implementation must retain both Arnoldi vectors `V`
  and preconditioned vectors `Z`.
- A recomputed true residual at least at restart boundaries and before
  reporting convergence; recurrence residuals may be used for cheap inner
  progress but cannot be the final acceptance test.
- A progress/cancellation hook, explicit termination reason, stable breakdown
  handling, and reusable, predictably bounded workspace.
- Coarse-grained outer parallelism without accidental nested Rayon or native
  BLAS thread pools.
- No strong-copyleft runtime dependency and a preference for a native-free
  artifact candidate.

## Dense and sparse substrate comparison

| Candidate | Primary-source facts | RapidRBF assessment |
|---|---|---|
| `faer` 0.24.4 | **[E]** The [0.24.4 manifest](https://docs.rs/crate/faer/0.24.4/source/Cargo.toml.orig) declares MIT, Rust 1.84, default sparse-linalg and Rayon features, and a pure-Rust normal dependency graph. The [decomposition inventory](https://docs.rs/faer/0.24.4/faer/#matrix-decompositions) includes LLT, LBLT, partial/full-pivot LU, QR, and column-pivoted QR. [Sparse solvers](https://docs.rs/faer/0.24.4/faer/sparse/linalg/solvers/index.html) include LLT, LU, and QR. Low-level routines pair a `MemStack` parameter with a [`*_scratch` requirement](https://docs.rs/faer/0.24.4/faer/linalg/index.html#memory-allocation). [`Par`](https://docs.rs/faer/0.24.4/faer/enum.Par.html) selects sequential or Rayon execution. The release was published 2026-06-24. | **Leading shortlist probe.** Best source-evidence match for local dense factors and any later sparse/coarse path. Use low-level APIs where scratch predictability matters and keep `faer` matrix types behind an adapter. Its [matrix-free module](https://docs.rs/faer/0.24.4/faer/matrix_free/index.html) has CG, BiCGSTAB, LSMR, and Krylov-Schur, but no GMRES/FGMRES; the Krylov core remains ours. Adoption still requires the captured-factor and end-to-end gates. |
| `nalgebra` 0.35.0 + `nalgebra-sparse` 0.12 | **[E]** The [0.35 manifest](https://docs.rs/crate/nalgebra/0.35.0/source/Cargo.toml.orig) declares Apache-2.0, Rust 1.89, pure-Rust `matrixmultiply`, and optional Rayon. Its [linear-algebra API](https://docs.rs/nalgebra/0.35.0/nalgebra/linalg/index.html) includes Cholesky, LBLT, LU, full-pivot LU, QR, and column-pivoted QR. [`LU::new`](https://docs.rs/nalgebra/0.35.0/nalgebra/linalg/struct.LU.html#method.new) consumes owned matrix storage and does not expose a scratch plan or per-call thread policy. `nalgebra-sparse` calls itself [early in development, limited in solvers, and correctness-first rather than performance-first](https://docs.rs/nalgebra-sparse/0.12.0/nalgebra_sparse/); its direct-factor module exposes only CSC Cholesky, whose docs say there is [no fill-reducing ordering and it is not recommended for serious projects](https://docs.rs/nalgebra-sparse/0.12.0/nalgebra_sparse/factorization/struct.CscCholesky.html). | **Viable fallback, not preferred core.** Mature and portable for small geometry math, but the evidence is weaker for explicit factor-workspace budgeting and medium local blocks. Adding it beside `faer` would also create two dense matrix type systems. |
| `ndarray-linalg` / `lax` 0.18.1 | **[E]** The project documents an [`ndarray` interface to external LAPACK implementations](https://github.com/rust-ndarray/ndarray-linalg), with exactly one of OpenBLAS, Netlib, or Intel MKL selected. The [feature matrix](https://docs.rs/crate/ndarray-linalg/0.18.1/features) exposes static/system variants and MKL LP64/ILP64 plus sequential/iomp choices. [`lax`](https://docs.rs/lax/0.18.1/lax/) wraps LAPACK for `f32`, `f64`, and complex types and exposes LU, Bunch-Kaufman, Cholesky, QR, SVD, and some reusable `Work` objects. The Rust crates are MIT OR Apache-2.0. | **Optional benchmark path only.** Dense capability is sufficient, but no sparse path or FGMRES is supplied. Native artifact production, native allocator behavior, and backend thread control remain outside a unified RapidRBF workspace contract. |
| `linfa-linalg` 0.2.1 | **[E]** Its [crate documentation](https://docs.rs/linfa-linalg/0.2.1/linfa_linalg/) describes a pure-Rust `ndarray` implementation without external BLAS/LAPACK. The [public item inventory](https://docs.rs/linfa-linalg/0.2.1/linfa_linalg/all.html) includes Cholesky and QR but not general LU or LDLT/LBLT. The crate is MIT OR Apache-2.0 and was published 2025-05-15. | **Disqualify as the sole substrate.** It cannot cover the required general/indefinite local factorization surface, and it adds neither sparse direct solvers nor FGMRES/workspace controls. |
| `sprs` 0.11.x / `sprs-ldl` 0.10 | **[E]** `sprs` provides generic CSR/CSC storage and operations under MIT OR Apache-2.0. Its [linear-solver module](https://docs.rs/sprs/latest/sprs/linalg/index.html) documents simple serial, unpreconditioned BiCGSTAB plus triangular solves, not GMRES or a general direct solver. The separate [`sprs-ldl` 0.10.0](https://docs.rs/crate/sprs-ldl/0.10.0) is an LGPL-2.1 sparse Cholesky/LDL crate last released 2022-06-20. | **Do not add for v1.** It does not solve the dense-local or FGMRES problem, would duplicate `faer` sparse storage, and `sprs-ldl` adds a weak-copyleft distribution obligation and a stale factorization dependency. It is not a strong-copyleft license, but it still needs an explicit policy/legal decision if ever shipped. |
| `rsparse` 1.2.1 | **[E]** The [crate docs](https://docs.rs/rsparse/1.2.1/rsparse/) describe a dependency-free, MIT, pure-Rust CSC package with sparse Cholesky, LU, and QR; 1.2.1 was released 2025-03-29. Its APIs return owned factor/work structures and do not document an explicit scratch allocator, threading policy, or matrix-free iterative solver. | **Focused oracle/watchlist.** Potentially useful for checking small sparse examples, but too narrow for the shared dense-plus-Krylov substrate and without current evidence for bounded workspace or all tier-one production testing. |
| `OxiBLAS` / `oxiblas-sparse` 0.2.1 | **[E]** The [dense crate](https://docs.rs/oxiblas/0.2.1/oxiblas/) is pure Rust, Apache-2.0, and advertises LU, pivoted QR, Cholesky/LDLT, workspace queries, and memory pools. The project was created in late 2025 and 0.2.1 was released 2026-03-16. Its repository keeps CI definitions under [`workflows.disabled`](https://github.com/cool-japan/oxiblas/tree/00dcf6441ed1e74c1b4e5fe75cad8a06b16ae7bf/.github/workflows.disabled), rather than active GitHub workflows at the inspected release commit. | **Promising watchlist, not v1 default.** Its workspace direction is attractive, but the project is very young and the broad capability claims need numerical, performance, and tier-one validation. Its FGMRES shortcomings are detailed below. |

### Why `faer` leads the first probe

- **[E]** It covers all decision-critical dense families in one crate, including
  pivoted general factorizations and symmetric-indefinite LBLT, plus sparse
  direct solvers if a later coarse path needs them.
- **[E]** The low-level allocation protocol computes a `StackReq` before the
  operation and runs from caller-provided `MemStack`. This is the clearest
  available route to make scratch memory visible to RapidRBF's budget.
- **[E]** Its execution policy is explicit: `Par::Seq` or
  `Par::Rayon(nonzero_threads)`, rather than an unavoidable native global
  thread pool.
- **[I]** Use `Par::Seq` while many RAS domains are being factored/solved in
  outer parallelism. Reserve inner `Par::Rayon` for a measured coarse or single
  large factorization where outer parallelism is absent.
- **[G]** High-level factor objects may retain full rectangular storage even
  when a packed triangular representation would suffice. The prototype must
  measure actual retained bytes and test whether low-level in-place factors can
  be packed or spilled without harming solve throughput.
- **[G]** The current upstream [test workflow](https://github.com/sarah-quinones/faer-rs/blob/main/.github/workflows/run-tests.yml)
  exercises Ubuntu and Windows but does not establish both macOS architectures.
  Pure Rust reduces packaging risk; it is not proof of RapidRBF's four
  tier-one artifacts.
- **[G]** The source distribution contains third-party notice files in addition
  to the crate's MIT license. The eventual binary/source notice inventory must
  be generated from the actually resolved dependency graph.

## Krylov and FGMRES comparison

The decisive distinction is not whether a crate exports something named
`gmres`; it is whether its exact convergence and memory semantics match the
solver contract.

| Candidate | What the implementation establishes | Decision |
|---|---|---|
| `kryst` 4.3.0 | **[E]** `kryst` is MIT, was released 2026-07-19, defaults to a `faer` backend, and documents FGMRES, shell/matrix-free operators, right preconditioning, restart, monitors, and true-versus-recurrence residual reporting ([crate source/docs](https://docs.rs/crate/kryst/4.3.0)). At the inspected release commit, [`FgmresOptions`](https://github.com/tmathis720/kryst/blob/8e9fff0feb7af16dabc915173dd62ab1e383555f/src/solver/fgmres.rs#L70-L132) includes restart, preallocation, a mutable preconditioner callback, restart callback, and configurable true-residual checks. Its [workspace](https://github.com/tmathis720/kryst/blob/8e9fff0feb7af16dabc915173dd62ab1e383555f/src/context/ksp_context/workspace.rs#L166-L210) stores contiguous `V`, `Z`, and Hessenberg regions and [reuses allocations](https://github.com/tmathis720/kryst/blob/8e9fff0feb7af16dabc915173dd62ab1e383555f/src/context/ksp_context/workspace.rs#L395-L438). The implementation can [verify a true residual before convergence and at restart](https://github.com/tmathis720/kryst/blob/8e9fff0feb7af16dabc915173dd62ab1e383555f/src/solver/fgmres.rs#L1485-L1528). | **Best integration spike and differential oracle.** Do not make it the v1 runtime yet: it is young and broad, its workspace owns `Vec` allocations rather than accepting RapidRBF's allocator/budget, and its [upstream CI](https://github.com/tmathis720/kryst/blob/8e9fff0feb7af16dabc915173dd62ab1e383555f/.github/workflows/ci.yml) runs on Ubuntu only. Gate adoption on four-platform CI, cancellation/termination semantics, adversarial numerical tests, and million-scale allocation measurements. |
| `faer_gmres` 0.5.0 | **[E]** It is MIT and provides restarted GMRES over `faer`, but its [public implementation](https://github.com/wgurecky/faer-gmres/blob/4a02119efeab5a3e1bb069b344db4f1398501fb2/src/lib.rs#L178-L233) is ordinary **left-preconditioned** GMRES. The Arnoldi loop [allocates matrix values and accepts the recurrence residual](https://github.com/wgurecky/faer-gmres/blob/4a02119efeab5a3e1bb069b344db4f1398501fb2/src/lib.rs#L237-L327); it has no flexible `Z` contract, true-residual acceptance policy, or monitor/cancel callback. | **Disqualify for the required solve.** Useful only as a simple GMRES comparison test. |
| `oxiblas-sparse` 0.2.1 FGMRES | **[E]** Its [FGMRES signature](https://github.com/cool-japan/oxiblas/blob/00dcf6441ed1e74c1b4e5fe75cad8a06b16ae7bf/crates/oxiblas-sparse/src/linalg/iterative/fgmres.rs#L11-L35) accepts a concrete CSR matrix rather than a general matrix-free operator. It [allocates residual, `V`, `Z`, and work vectors](https://github.com/cool-japan/oxiblas/blob/00dcf6441ed1e74c1b4e5fe75cad8a06b16ae7bf/crates/oxiblas-sparse/src/linalg/iterative/fgmres.rs#L42-L104). The inner loop [declares convergence from the recurrence residual](https://github.com/cool-japan/oxiblas/blob/00dcf6441ed1e74c1b4e5fe75cad8a06b16ae7bf/crates/oxiblas-sparse/src/linalg/iterative/fgmres.rs#L139-L162); the true residual is computed only on the final nonconverged path. There is no progress/cancel callback. | **Disqualify the current FGMRES API; retain the project as a watchlist.** |
| `gmres` 1.1.0 | **[E]** Its [only documented solver](https://docs.rs/gmres/1.1.0/gmres/fn.gmres.html) takes an `rsparse::Sprs` matrix. The public contract does not expose a matrix-free operator, flexible/right preconditioner, restart, true-residual policy, reusable workspace, or callback. | **Disqualify.** The API shape is incompatible before performance is considered. |
| Ferreus RBF 0.2.2 internal solver | **[E]** This is project source rather than a standalone solver crate. Its [FGMRES routine](https://github.com/graphic-goose/ferreus_rbf_rs/blob/main/ferreus_rbf/src/iterative_solvers.rs#L20-L68) accepts matrix-free operator/preconditioner closures, restart, and a progress sink and preallocates `V`, `Z`, and small arrays. However, it [returns success from the inner recurrence residual](https://github.com/graphic-goose/ferreus_rbf_rs/blob/main/ferreus_rbf/src/iterative_solvers.rs#L83-L152) and recomputes the true residual only after a restart cycle; the API returns a matrix rather than a structured termination reason and does not establish cancellation. | **Algorithm/reference only.** It demonstrates a compact domain-specific shape, but its convergence and allocation semantics are not the RapidRBF contract. |
| `faer` matrix-free solvers | **[E]** The [0.24.4 module inventory](https://docs.rs/faer/0.24.4/faer/matrix_free/index.html) exposes BiCGSTAB, CG, LSMR, and Krylov-Schur, not GMRES or FGMRES. | **No candidate to adopt.** Reuse `faer` vectors/matvec building blocks if useful, but own FGMRES. |

### Minimum owned FGMRES surface

The owned implementation should be deliberately smaller than a general solver
framework:

```text
operator.apply_into(x, y, operator_scratch)
preconditioner.apply_into(iteration, v, z, pc_scratch)
solve(x, b, restart, tolerances, workspace, monitor) -> SolveReport
monitor(SolveProgress) -> Continue | Cancel
```

Required invariants:

- Keep contiguous, reusable `V[(m+1) * n]` and `Z[m * n]` arenas; do not
  allocate a vector per Arnoldi step.
- Use checked byte arithmetic and fallible reservation before starting. Expose
  the complete plan—basis, work vectors, Hessenberg/Givens arrays, operator
  scratch, and preconditioner scratch—to the caller's budget.
- Treat the inexpensive recurrence residual as progress only. Recompute
  `r = b - A*x` at every restart and before `Converged`.
- Return a termination enum such as `Converged`, `IterationLimit`, `Cancelled`,
  `Breakdown`, `NonFinite`, and `AllocationLimit`, together with both residual
  histories and iteration/matvec/preconditioner counts.
- Test zero RHS, exact warm start, happy breakdown, near breakdown, non-finite
  operator/preconditioner output, restart-one behavior, changing
  preconditioners, false recurrence convergence, and cancellation at every
  callback boundary.
- Make reorthogonalization policy explicit. A one-pass MGS implementation is
  not numerically interchangeable with a guarded second pass.

**[I]** This surface is small enough to own and makes the hard product
semantics—budgeting, cancellation, and acceptance—visible. `kryst` should be
used as a differential comparison where its semantics overlap, not as the sole
oracle for those RapidRBF-specific policies.

## Native BLAS/LAPACK distribution and threading

### OpenBLAS

- **[E]** `openblas-src` documents source/system/static modes and states that
  [building OpenBLAS from source is not supported on Windows](https://github.com/blas-lapack-rs/openblas-src#requirements);
  Windows needs an installed library (including the documented vcpkg route).
  A source build also introduces C/Fortran/make toolchain requirements.
- **[E]** OpenBLAS is BSD-3-Clause. Its own FAQ recommends
  [`OPENBLAS_NUM_THREADS=1` when the application is already multithreaded](https://github.com/OpenMathLib/OpenBLAS/wiki/Faq/08848f2293927444abf06eec756f0fc17b33313f).
- **[I]** Static OpenBLAS would require four-platform artifact production,
  notices, architecture dispatch testing, and a process-global thread policy.
  It is not a drop-in distribution-neutral acceleration flag.

### Intel oneMKL

- **[E]** Intel's [oneMKL 2026 release notes](https://www.intel.com/content/www/us/en/developer/articles/release-notes/onemkl/2026.html)
  and [platform guide](https://www.intel.com/content/www/us/en/docs/onemkl/developer-guide-linux/2026-0/overview.html)
  cover current Windows/Linux Intel-architecture delivery, not a universal
  macOS-arm64 backend. Intel's [license FAQ](https://www.intel.com/content/www/us/en/developer/articles/tool/onemkl-license-faq.html)
  permits redistribution under the Intel Simplified Software License, so that
  license and notices would join the artifact surface.
- **[E]** The Rust [`intel-mkl-src`](https://github.com/rust-math/intel-mkl-src)
  wrapper is MIT but its latest release is from 2022; the linked binaries remain
  governed by Intel's terms.
- **[I]** oneMKL cannot be the single implementation for all tier-one targets,
  and selecting it only on some targets creates cross-backend numerical and
  support variance.

### Threading policy

- **[I]** Default to one level of parallelism. While factoring or applying many
  RAS domains, run each local dense operation sequentially and parallelize the
  domain loop. If a measured coarse operation warrants inner parallelism, stop
  the outer pool for that phase and select a bounded inner count explicitly.
- **[G]** A native-backend experiment must record backend identity, version,
  link mode, CPU dispatch, environment/runtime thread settings, and actual
  thread count. A microbenchmark that silently uses all cores is not comparable
  to a sequential `faer` kernel nested in the real solver.
- **[I]** Promote a native backend only if a same-host, same-thread-budget,
  end-to-end RapidRBF benchmark beats the pure-Rust path enough to pay for the
  packaging and support cost. Dense-kernel peak throughput alone is
  insufficient.

## Million-scale memory implications

For `n = 1,000,000` and restart length `m`, the two mandatory FGMRES basis
arenas alone require

```text
V: (m + 1) * n * 8 bytes
Z:       m * n * 8 bytes
total: (2m + 1) * n * 8 bytes
```

| Restart `m` | `V + Z` only |
|---:|---:|
| 16 | 264,000,000 bytes = 251.8 MiB |
| 32 | 520,000,000 bytes = 495.9 MiB |
| 64 | 1,032,000,000 bytes = 984.2 MiB |

This excludes `x`, `b`, residual/work vectors, operator scratch, the
preconditioner, resident RAS factors, allocator overhead, and application data.

For a dense local block of order 1024:

- a full `f64` square buffer is exactly 8 MiB;
- one packed triangle is 4,198,400 bytes, about 4.00 MiB;
- LU normally needs full factor storage plus pivots, while symmetric factors
  may admit triangular storage if the selected solve representation supports
  it.

**[I]** Restart length and resident-factor-cache size must be chosen by one
shared memory planner. For illustration, retaining 1000 full 1024-by-1024
factor buffers already approaches 7.8 GiB before FGMRES bases or application
data. Global dense assembly is categorically out of scope; dense algebra is for
local/coarse work only.

**[G]** Measure high-water resident set size rather than summing advertised
workspaces. Include transient assembly buffers, factorization scratch,
parallel-domain concurrency, packed/spilled factors, and allocator retention.

## Adoption gates

The recommendation is conditional on a focused prototype, not on crate
documentation alone:

1. Build and test the exact locked dependency graph on all four tier-one
   targets. Exercise release/LTO builds and artifact inspection, not only
   `cargo check`.
2. Compare `faer` sequential and bounded-Rayon factor/solve behavior on the
   actual SPD, symmetric-indefinite constrained, nonsymmetric, singular, and
   near-singular local matrices at representative orders through 1024.
3. Record factor bytes, scratch-plan bytes, peak RSS, factor serialization or
   packing cost, solve throughput, and numerical residual/backward error.
4. Run the owned FGMRES tests listed above at small scale, then million-vector
   allocation/cancellation tests with a cheap synthetic matrix-free operator.
5. Run `kryst` against the same operator/preconditioner as a behavioral
   comparison. Do not count a match until both implementations use an explicit
   true-residual acceptance rule.
6. Benchmark any OpenBLAS/MKL alternative with the identical outer/inner thread
   budget and full artifact pipeline. Keep it private/optional unless it wins
   end to end and passes every target's distribution gate.

## Final shortlist and disqualifiers

### Shortlist

- **First probe candidate:** `faer` behind RapidRBF-owned dense/sparse adapter.
- **Own:** compact restarted right-FGMRES plus its memory planner and reporting
  contract.
- **Spike/oracle:** `kryst` FGMRES, subject to tier-one and memory gates.
- **Optional benchmark:** `ndarray-linalg`/`lax` with one explicitly selected
  native backend.
- **Watch:** OxiBLAS as it matures; `rsparse` for narrow sparse comparison cases.

### Disqualify from the v1 core

- `linfa-linalg`: missing required LU/indefinite surface.
- `nalgebra-sparse`: explicitly early, limited, and not a serious sparse direct
  solver today; `nalgebra` dense remains a viable fallback but not the preferred
  substrate.
- `sprs`/`sprs-ldl`: does not address the core solver need, duplicates sparse
  types, and the factor crate adds LGPL-2.1 obligations.
- `faer_gmres`: left-preconditioned ordinary GMRES without the required true
  residual/callback/workspace contract.
- `oxiblas-sparse` FGMRES: concrete CSR input, allocation-heavy loop, and
  recurrence-residual success without true-residual confirmation.
- `gmres` 1.1: concrete sparse matrix only and lacks the required controls.
- Ferreus's internal FGMRES: useful reference, but not a reusable crate and its
  success/termination semantics are insufficient.
- OpenBLAS or oneMKL as the mandatory default: no single simple, consistent
  native distribution across all four tier-one artifacts.

The key architectural hedge is the owned adapter. It lets RapidRBF start with
a native-free `faer` probe, compare `kryst` or native LAPACK privately, and
replace an implementation later without leaking third-party matrix, allocator,
threading, or termination semantics into the engine API. Adoption remains a
later solver/resource-model decision backed by empirical gates.
