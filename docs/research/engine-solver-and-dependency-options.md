# Engine, solver, and dependency migration options

Status: decision basis for RapidRBF v1.0.0 `/to-spec`

Scope: GitHub issue [#3](https://github.com/qingsonger/RapidRBF/issues/3)

Researched: 2026-07-26

## Evidence and revision policy

This audit uses the following labels throughout:

- **Fact** — directly supported by linked source, test, build, or primary project
  documentation.
- **Inference** — a design or risk conclusion drawn from one or more facts.
- **Unknown** — evidence is insufficient; the item needs a spike, benchmark, legal
  review, or product decision.
- **Recommendation** — the proposed RapidRBF v1 decision.

The comparison baseline is Polatory commit
[`4a30beb08053fb339ce899e255be4b6d3f74aa0c`](https://github.com/polatory/polatory/tree/4a30beb08053fb339ce899e255be4b6d3f74aa0c).
The built ScalFMM source is the Polatory fork at commit
[`0be3d74f17adb28adec7004f712f693ac8ee9901`](https://github.com/polatory/ScalFMM3/tree/0be3d74f17adb28adec7004f712f693ac8ee9901).
Pure-Rust candidates were inspected at Ferreus commit
[`d0442ee978668386f6ccbeec866bfa52fcc4484f`](https://github.com/graphic-goose/ferreus_rbf_rs/tree/d0442ee978668386f6ccbeec866bfa52fcc4484f)
and `kifmm` commit
[`d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068`](https://github.com/bempp/kifmm/tree/d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068).

**Fact.** Polatory's build requests the moving ScalFMM branch `polatory` with a
shallow clone rather than an immutable commit
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L155-L165)).
**Inference.** A clean rebuild cannot be assumed to reproduce the locally built
baseline. RapidRBF must record the exact native source revision and patch set.

## Decision summary

| Area | v1 recommendation | Reason and exit condition |
|---|---|---|
| Product architecture | **Rust-owned hybrid**: Rust owns numerical semantics, direct/neighbor evaluation, the four-block operator, solver, RAS, memory policy, and public API. | Keeps the compatibility surface reviewable while isolating the one immature migration area: large smooth-kernel FMM. |
| Production FMM | Retain the fixed ScalFMM fork behind a narrow, private C ABI and ship prebuilt native artifacts for tier-one platforms. | It is the only audited route that already implements the Polatory baseline. Remove it only after a pure-Rust backend passes all kernel/block, convergence, scale, and platform gates below. |
| Pure-Rust FMM | Prototype Ferreus first and `kifmm` second, behind the same backend-neutral Rust contract; neither is a v1 production dependency yet. | Ferreus is RBF-specific but scalar-only at the kernel seam. `kifmm` has a component-aware kernel seam but is 3D/Unix/native-FFTW today. |
| Solver | Port flexible right-preconditioned GMRES to Rust, add a configurable restart, and retain an independent true-residual oracle. | Polatory's unrestarted basis grows with iteration count; an unchecked restart would change convergence semantics. |
| Preconditioner | Port Polatory's multilevel RAS topology and constants before tuning; add explicit memory budgets and a bounded factor cache. | This preserves the known convergence mechanism without retaining every dense local factor in RAM. |
| Dense linear algebra | Use Faer as the default pure-Rust factorization backend, sequential inside parallel domain tasks. | Avoids a mandatory BLAS runtime and nested thread pools. Optional native BLAS is a post-parity optimization. |
| Variogram fitting | Keep fitting outside the interpolation engine seam. If it is in v1 scope, retain Ceres behind a second narrow adapter until a Rust implementation passes differential tests. | Ceres currently supplies bounds, numeric differentiation, dense QR, and quaternion-manifold behavior; no audited Rust crate is a drop-in replacement. |
| Spatial index | Replace FLANN with a Rust exact-radius index, with Kiddo as the first candidate. | The compatibility burden is cutoff/tie/accumulation behavior, not the FLANN API. |
| Parallelism | Own one configurable Rayon pool in Rust. Run inner Faer operations sequentially and give the native FMM wrapper an explicit thread count. | Prevents Rayon/Faer/OpenMP/BLAS oversubscription and makes thread use observable. |

**Recommendation.** Do not make “100% Rust” a v1 release criterion. Make removal
of the private native fallback a measured milestone. Do not start a new FMM
implementation from scratch on the v1 critical path.

## Baseline semantics that the engine must preserve

### Four matrix kernels

**Fact.** Polatory constructs a saddle-point operator from scalar `A`, gradient
`F`, gradient-transpose `Fᵀ`, and Hessian `H` evaluators, plus the polynomial
block
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/operator.hpp#L44-L104)).
Its ScalFMM kernel traits give the following channel and symmetry protocol:

| Block | Source channels → target channels | Symmetry | Evaluated quantity |
|---|---:|---|---|
| `A` | `1 → 1` | symmetric | `φ(T(x-y))` |
| `F` | `d → 1` | non-symmetric | `-∇φ(T(x-y)) T` |
| `Fᵀ` | `1 → d` | non-symmetric | `+∇φ(T(x-y)) T` |
| `H` | `d → d` | symmetric | `-Tᵀ Hφ(T(x-y)) T` |

The channel counts and scalar evaluation are in
[`kernel.hpp`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/fmm/kernel.hpp#L14-L68);
the signs and transformed derivatives are in
[`gradient_kernel.hpp`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/fmm/gradient_kernel.hpp#L15-L60),
[`gradient_transpose_kernel.hpp`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/fmm/gradient_transpose_kernel.hpp#L16-L62),
and
[`hessian_kernel.hpp`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/fmm/hessian_kernel.hpp#L15-L64).
Here `T` is Polatory's anisotropy transform and `d ∈ {1,2,3}`.

**Inference.** An FMM API that accepts only `k(x,y) -> f64` is not sufficient.
The RapidRBF backend contract must explicitly describe source and target channel
counts, transpose/sign behavior, symmetry, dimension, and anisotropy. Treating
gradient evaluation of a scalar interpolant as equivalent to gradient
observations in the fitted system would omit `F`, `Fᵀ`, and `H`.

**Fact.** The runtime factory instantiates 1D, 2D, and 3D versions of 16 concrete
RBF types: the 2D/3D biharmonic and triharmonic functions, cubic, exponential,
Gaussian, generalized Cauchy 3/5/7/9, spherical, and spheroidal 3/5/7/9
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/make_fmm_evaluator.cpp#L20-L280)).
**Recommendation.** The Rust contract should use stable RBF and block enums, not
C++ template names, and reject unsupported backend combinations explicitly.

### Evaluation routes and accuracy selection

**Fact.** Polatory uses direct all-pairs evaluation when
`n_source × n_target < 1024²`; otherwise it constructs ScalFMM trees and
operators. The evaluator transforms points by anisotropy, uploads weights in
tree-sorted order, keeps an interpolator LRU of capacity two, and releases the
source/target trees after each evaluation
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_evaluator.hpp#L77-L180),
[dispatch](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_evaluator.hpp#L226-L270)).
The symmetric evaluator uses direct evaluation below 1,024 points and handles
self interactions explicitly
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_symmetric_evaluator.hpp#L163-L251)).

**Fact.** The FMM-accuracy estimator compares direct and approximate values on a
deterministic sample of at most 10,000 points, searches interpolation order 8–20
and tree separation settings, and has special choices for zero and infinite
requested accuracy
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_accuracy_estimator.hpp#L70-L167)).
**Recommendation.** Preserve these dispatch and calibration rules during the
parity phase. A backend may later choose different parameters only if it meets
the same measured error contract.

**Fact.** Smooth/polyharmonic, exponential, Gaussian, and Cauchy evaluators use
the FMM route. Compact cubic and spherical evaluators use a radius-neighbor
route. Spheroidal kernels add a compact direct part to a fast part
([factory routes](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/make_fmm_evaluator.cpp#L20-L280),
[spheroidal composition](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/spheroidal_evaluator.hpp#L18-L58)).
**Inference.** “FMM compatibility” covers only one route in a composite
evaluator. Direct and neighbor implementations must be independently
differential-tested.

**Fact.** The current neighbor route transforms points before indexing, performs
radius queries using FLANN's single-tree index, asks for unlimited checks and
unsorted results, casts the squared radius to `float`, and accumulates results in
OpenMP loops with thread-local buffers
([evaluator](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/direct_evaluator.hpp#L41-L90),
[index wrapper](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/kdtree.cpp#L12-L70)).
**Unknown.** Points exactly at the support radius can change membership when
RapidRBF stops rounding the squared radius to `float`. The desired behavior must
be specified from mathematical semantics and accompanied by a legacy
compatibility fixture.

## Acceleration choices

### Option matrix

| Route | Relevant evidence | Fit for RapidRBF v1 |
|---|---|---|
| Pinned ScalFMM through a private C ABI | The audited fork is a C++20, header-oriented ScalFMM variant with OpenMP and no C ABI in its source/build contract ([CMake source](https://github.com/polatory/ScalFMM3/blob/0be3d74f17adb28adec7004f712f693ac8ee9901/CMakeLists.txt#L21-L47), [main target](https://github.com/polatory/ScalFMM3/blob/0be3d74f17adb28adec7004f712f693ac8ee9901/CMakeLists.txt#L114-L126)). | **Production parity fallback.** The wrapper is new work, but the numerical engine is already the baseline. |
| Ferreus BBFMM | The kernel trait is scalar `evaluate(target, source) -> f64` with optional target value/gradient ([trait](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_bbfmm/src/traits.rs#L13-L33)). Its RBF input builder accepts scalar point values ([builder](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/rbf.rs#L189-L262)); output gradients are supported, but gradient observations are not represented ([evaluation](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/rbf.rs#L705-L754)). | **First pure-Rust spike.** Good RBF/solver/domain-decomposition reference; not a drop-in four-block engine. |
| `kifmm` + `green-kernels` | `green-kernels` exposes domain and range component counts ([trait](https://github.com/skailasa/green-kernels/blob/ed83120e5e74972fb0f21593b1f8f5047b6eefac/src/traits.rs#L10-L115)). `kifmm` is currently 3D, Unix-only, and requires native FFTW plus BLAS/LAPACK ([README](https://github.com/bempp/kifmm/blob/d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068/README.md#L218-L280)); its implementation and C/Python interfaces have a peer-reviewed JOSS description ([paper](https://joss.theoj.org/papers/10.21105/joss.07124)). | **Second spike / architectural reference.** The component seam is promising, but dimension, kernel set, Windows, and native-dependency gaps are release blockers. |
| PETSc | PETSc provides flexible right-preconditioned GMRES ([`KSPFGMRES`](https://petsc.org/release/manualpages/KSP/KSPFGMRES/)), restricted additive Schwarz ([`PCASMType`](https://petsc.org/main/manualpages/PC/PCASMType/)), and multigrid ([`PCMG`](https://petsc.org/release/manualpages/PC/PCMG/)). | **Oracle or experiment only.** Mapping RapidRBF's dense matrix-free operator and custom hierarchy into a C/MPI runtime adds more packaging surface than it removes. |
| New FMM written for RapidRBF | No implementation or validation evidence exists. | **Reject for v1 critical path.** Reconsider only as a separately staffed project after the compatibility suite exists. |

### Ferreus-specific gaps

**Fact.** Ferreus' Chebyshev implementation derives interactions from reference
vectors using axis and sign permutations
([construction](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_bbfmm/src/chebyshev.rs#L243-L260),
[operator precomputation](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_bbfmm/src/chebyshev.rs#L681-L812)).
**Inference.** This symmetry reduction is safe for scalar radial values but
derivative components require explicit component permutation/sign transforms,
or a full non-symmetric block-operator path. This is the core technical question
for the Ferreus spike.

**Fact.** Ferreus currently lists linear, thin-plate spline, cubic, and spheroidal
RBF families
([enum](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/interpolant_config.rs#L35-L50)).
**Inference.** Even after the four-block seam is implemented, exponential,
Gaussian, generalized Cauchy, spherical, and the exact Polatory conventions
remain migration work.

**Fact.** Ferreus is MIT-licensed
([license](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/LICENSE))
and has CI/release jobs for Linux x86-64, Windows x86-64, macOS Intel, and macOS
ARM
([workflow](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/.github/workflows/publish-py-ferreus-rbf.yml#L13-L25)).
**Inference.** This is useful build evidence, not evidence of RapidRBF numerical
coverage or million-point behavior.

### Required native boundary

**Recommendation.** The fallback ABI must be narrower than the Rust backend
trait. It should have opaque handles and versioned plain-C request structures:

```c
typedef struct rrbf_fmm_handle rrbf_fmm_handle;

rrbf_status rrbf_fmm_create(
    const rrbf_fmm_create_v1* request,
    rrbf_fmm_handle** out);
rrbf_status rrbf_fmm_set_sources(
    rrbf_fmm_handle*, const double* row_major_points, size_t point_count);
rrbf_status rrbf_fmm_set_targets(
    rrbf_fmm_handle*, const double* row_major_points, size_t point_count);
rrbf_status rrbf_fmm_set_weights(
    rrbf_fmm_handle*, const double* row_major_channels, size_t value_count);
rrbf_status rrbf_fmm_evaluate(
    rrbf_fmm_handle*, double* row_major_output, size_t value_count);
const char* rrbf_fmm_last_error(const rrbf_fmm_handle*);
void rrbf_fmm_destroy(rrbf_fmm_handle*);
```

The create request must include ABI size/version, dimension, RBF identifier and
parameters, block (`A`, `F`, `FT`, `H`), anisotropy matrix, requested accuracy,
and thread count. Every call must carry checked lengths. The wrapper must:

1. compile all supported C++ template combinations internally;
2. catch all C++ exceptions and return status codes;
3. expose no STL, Eigen, allocator, or ScalFMM type;
4. document that a handle is not concurrently callable;
5. copy or clearly own all input lifetimes;
6. report backend revision and selected FMM configuration;
7. have C and Rust ABI tests, including failure paths and unload/destruction; and
8. be pinned and built as part of release artifacts so users need no C++ toolchain.

**Inference.** The C ABI stabilizes the process boundary, not the ScalFMM
implementation. Upgrading the fork remains a numerical migration and must rerun
the complete differential suite.

**Unknown.** Whether one native handle can efficiently retain source trees and
interpolators across many evaluations without changing Polatory's lifecycle or
peak memory. RapidRBF should expose an explicitly bounded prepared plan, not an
implicit unbounded global cache.

## FGMRES and residual semantics

**Fact.** Polatory uses flexible GMRES with a right RAS preconditioner and an
initial solution
([solver](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/solver.hpp#L99-L139)).
Its implementation is unrestarted: the Arnoldi basis `V` and preconditioned basis
`Z` grow with the iteration count
([GMRES base](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/gmres_base.hpp#L51-L89),
[`Z` basis](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/fgmres.hpp#L21-L25)).

For `n` unknowns and restart length `m`, the two dense bases alone require
approximately:

`8 × n × (2m + 1)` bytes.

At one million unknowns, `m=32` is 520 MB decimal (about 496 MiB), before work
vectors, the operator, and RAS. `m=64` is about 1.03 GB decimal.

**Recommendation.** Implement restarted FGMRES with right flexible
preconditioning, modified Gram-Schmidt plus optional reorthogonalization, and
configurable `restart`, maximum iterations, absolute tolerance, and relative
tolerance. The API must surface iterations, restarts, recurrence residual, true
residual, and termination reason. Do not copy Ferreus' small default restart
without calibration.

**Fact.** Ferreus already has restarted right-preconditioned FGMRES, but its
default RBF call uses 20 outer iterations and a five-vector inner cycle
([implementation](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/iterative_solvers.rs#L20-L172),
[call site](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/rbf.rs#L536-L555)).
**Inference.** Its code is a useful reference, but its residual trajectory is not
a compatibility oracle for Polatory.

**Fact.** Polatory's convergence callback evaluates an independent residual. It
first computes direct infinity-norm residuals on a deterministic sample of up to
1,024 nonzero points, then switches to the full FMM residual
([residual evaluator](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/residual_evaluator.hpp#L62-L150)).
**Recommendation.** Retain this two-stage oracle during parity work. Always
re-evaluate the true residual at restart boundaries and before declaring
convergence; an approximate FMM matvec can make the Arnoldi recurrence
optimistic.

## Multilevel restricted additive Schwarz

**Fact.** Polatory's RAS hierarchy uses a fine/coarse ratio of 10, a coarsest
target of 2,048, parallel level/domain setup, a polynomial projection, and
multilevel residual updates
([hierarchy and setup](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/ras_preconditioner.hpp#L51-L187),
[sweep](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/ras_preconditioner.hpp#L191-L327)).
Domains use 50% overlap and at most 1,024 points
([divider](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/domain_divider.hpp#L26-L125)).
For a single anisotropic RBF the partition coordinates are transformed; the
multi-RBF case partitions raw coordinates
([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/ras_preconditioner.hpp#L110-L119)).

**Recommendation.** Port the hierarchy, restriction, overlap, polynomial
projection, sweep order, and single-versus-multiple anisotropy behavior before
changing constants. Treat changes in partition geometry as solver changes, not
mere optimizations.

**Fact.** Fine domains factor dense constrained `QᵀAQ` matrices with LDLT and
store the lower triangle; the coarsest solve uses dense constrained LDLT and
full-pivot LU
([fine grid](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/fine_grid.hpp#L59-L170),
[coarse grid](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/coarse_grid.hpp#L40-L130)).
A maximum-size 1,024-point lower triangle contains 524,800 doubles, about 4.0
MiB, before metadata. **Inference.** Keeping thousands of such factors resident
can dominate million-point memory even if each domain is individually small.

**Fact.** Polatory can spill factors into an anonymous delete-on-close temporary
file, but access is serialized by a mutex around seek/read/write
([cache](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/binary_cache.hpp#L20-L89)).
Ferreus instead retains every domain factor in memory and tries Cholesky before
pivoted LDLT
([domain factorization](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/domain.rs#L49-L70),
[domain construction](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/ferreus_rbf/src/domain.rs#L135-L382)).
**Recommendation.** Neither policy should be copied unchanged.

RapidRBF should use:

- packed, immutable factor records with versioned headers and checksums;
- a configured total memory budget and a bounded in-memory LRU;
- ephemeral temporary storage by default;
- positional or memory-mapped reads so independent domains do not share one
  seek mutex;
- deterministic cache keys if persistence is later offered;
- early disk-space and address-space checks;
- metrics for resident bytes, spilled bytes, cache hits, and I/O time; and
- parallel outer domain scheduling with sequential dense solves inside each task.

**Unknown.** The best resident/spill ratio and restart length are coupled:
FGMRES bases and RAS factors compete for the same memory budget. A million-point
benchmark must tune them together rather than reporting each subsystem in
isolation.

## Dense linear algebra, BLAS, and threads

**Fact.** Polatory exposes Eigen matrices in its public C++ type aliases
([types](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/types.hpp#L7-L20))
and uses Eigen throughout local factorizations and anisotropy. The build disables
Eigen's own parallelism, enables BLAS calls, links sequential MKL on x86-64, and
uses Accelerate plus FFTW on Apple ARM
([compile definitions](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L58-L61),
[linear algebra selection](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L118-L148)).

**Recommendation.** Use [Faer](https://github.com/sarah-quinones/faer-rs) as the
default dense backend for Rust matrices and LLT/LDLT/LU/QR operations. Faer is
MIT-licensed and has optional Rayon support
([crate manifest](https://docs.rs/crate/faer/latest/source/Cargo.toml.orig),
[decomposition API](https://docs.rs/faer/latest/faer/?search=sub)).
Put the matrix layout behind RapidRBF-owned types so a future backend does not
leak into the public API.

**Recommendation.** Use a single RapidRBF-owned
[Rayon](https://github.com/rayon-rs/rayon) pool and pass an explicit thread count
to every evaluator. Use Faer's sequential mode inside parallel RAS domains and
direct-evaluation chunks. Only enable Faer internal parallelism for isolated
large coarse factorizations after measurement. If native OpenMP remains in the
fallback, its thread count must be coordinated with the Rust pool.

**Inference.** Defaulting to pure-Rust dense algebra removes mandatory MKL,
Accelerate, OpenBLAS, and their independent thread runtimes from most of
RapidRBF. An optional native BLAS feature is justified only by an end-to-end
benchmark, not a microbenchmark.

## Dependency migration boundary

| Existing dependency | Observed role | v1 boundary |
|---|---|---|
| ScalFMM3 | Large smooth-kernel `A/F/Fᵀ/H` evaluation through C++20/OpenMP ([Polatory integration](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L101-L165)). | Keep only in the private FMM native component, pinned to an exact revision and patch set. |
| Eigen | Public matrix vocabulary plus dense factorization and geometry ([types](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/types.hpp#L7-L20)). | Replace with RapidRBF-owned Rust types and Faer internally; never cross the C ABI. |
| MKL | Sequential x86-64 BLAS/LAPACK and packaged DLLs on Windows ([root build](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/CMakeLists.txt#L24-L63)). | Remove from default Rust core. Permit only as an optional native-fallback build after licensing, runtime, and performance checks. |
| Accelerate | Apple ARM BLAS/LAPACK selection ([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L118-L148)). | System-only option for a macOS native fallback; not a Rust API dependency. Apple documents BLAS/LAPACK in Accelerate ([documentation](https://developer.apple.com/documentation/accelerate)). |
| FFTW | Apple ARM native-FMM dependency in the package manifest ([manifest](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/vcpkg.json#L5-L29)). | Avoid in default artifacts if possible. If linked, release policy must resolve its GPLv2-or-later or commercial terms ([FFTW licensing](https://www.fftw.org/faq/section1.html)). |
| Ceres | 1D/2D/3D variogram fitting with parameter bounds, numeric differentiation, dense QR, and 3D quaternion manifold ([1D](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting_1d.hpp#L37-L67), [2D](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting_2d.hpp#L40-L107), [3D](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting_3d.hpp#L39-L115)). | Keep outside the core. If fitting ships in v1, retain a narrow Ceres adapter; prototype [Argmin](https://argmin-rs.github.io/argmin/argmin/) or a purpose-built Rust solver only behind differential tests. |
| FLANN | KNN and radius lookup for compact support, with specific float-radius and ordering behavior ([wrapper](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/kdtree.cpp#L12-L70)). | Replace with a Rust exact index. Evaluate [Kiddo](https://docs.rs/kiddo/latest/kiddo/) first and [RTree](https://docs.rs/rstar/latest/rstar/struct.RTree.html) second; specify inclusivity, tie, and summation behavior. |
| libigl | Production use is a barycentric-coordinate calculation in the isosurface snapper ([call site](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/isosurface/snapper/snapper.hpp#L212-L218)); it is linked privately ([build](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L85-L89)). | Remove. Implement the small barycentric formula independently in Rust and test degeneracy, orientation, and boundary cases. Do not copy MPL-covered source. |
| Boost | Filesystem/cache, CLI parsing, containers/hashing, iterator/range utilities, and `erfc_inv`; Polatory declares the relevant components ([manifest](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/vcpkg.json#L5-L29)). | Map to `std`/`tempfile`, `clap`, Rust collections or `hashbrown`, iterators, and a tested inverse-error-function implementation such as [`statrs`](https://docs.rs/statrs/latest/statrs/function/erf/). Tail behavior needs differential tests. |
| OpenMP | Outer parallel loops in FMM, direct/neighbor evaluation, RAS, fitting, point-cloud, and isosurface code; ScalFMM's Windows build is forced to clang with `-fopenmp` ([build](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L101-L116)). | Replace with Rayon in Rust. Keep LLVM `libomp` only inside the fallback and bundle it where required; LLVM documents platform status ([support](https://clang.llvm.org/docs/OpenMPSupport.html)). |
| `fast_float` | Fast numeric parsing is a linked public dependency ([build](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L76-L99)). | Use Rust `f64::from_str` or [`fast-float`](https://crates.io/crates/fast-float) after a corpus test for accepted syntax, infinities, NaNs, underflow, and error reporting. |

## Tier-one release consequences

| Platform | Pure-Rust core | Native parity fallback | Release decision |
|---|---|---|---|
| Windows x86-64 | Rust/Faer/Rayon avoids a compiler and BLAS runtime. | Polatory currently forces clang for ScalFMM/OpenMP and inventories MKL DLLs ([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/CMakeLists.txt#L46-L63), [ScalFMM build](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L101-L116)). | Build with a controlled LLVM toolchain; bundle and smoke-test every runtime DLL. The C ABI prevents an MSVC Rust/C++ ABI dependency. |
| Linux x86-64, glibc | Native-free default is straightforward. | Native fallback can introduce `libomp`, MKL/OpenBLAS, and FFTW plus a glibc baseline. | Publish the minimum supported glibc and audit dynamic dependencies in CI. |
| macOS ARM64 | Pure Rust is the preferred shipping path. | Current Polatory selection is Accelerate + FFTW; OpenMP may also be required ([source](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L118-L148)). | Highest licensing/build-risk fallback. Prefer a wrapper configuration that does not require FFTW; otherwise resolve FFTW terms before release. |
| macOS x86-64 | Pure Rust is the preferred shipping path. | Polatory selects MKL on x86-64, but Intel ended macOS support beginning with oneAPI 2024 ([Intel guide](https://cdrdv2-public.intel.com/792838/oneapi_installation-guide-macos_2024.0-766282-792838.pdf)). | Use Accelerate if the fallback can be validated against it, or explicitly freeze an old MKL toolchain with an owned maintenance and security policy. |

**Unknown.** The fallback's actual need for FFTW and BLAS on each target is
configuration-dependent. Record the transitive dynamic library graph from each
release artifact rather than inferring it from CMake options.

## License and redistribution checklist

This section is an engineering inventory, not legal advice.

- **Fact.** The fixed ScalFMM fork carries CeCILL-C
  ([license file](https://github.com/polatory/ScalFMM3/blob/0be3d74f17adb28adec7004f712f693ac8ee9901/LICENCE);
  [official CeCILL licenses](https://www.cecill.info/licences.en.html)).
  **Unknown.** Counsel must confirm notice, source/patch availability, and
  static-versus-dynamic wrapper obligations for RapidRBF's distribution model.
- **Fact.** FFTW is GPLv2-or-later unless a commercial license is obtained
  ([official FAQ](https://www.fftw.org/faq/section1.html)).
  **Recommendation.** Do not silently add FFTW to an otherwise permissively
  licensed binary.
- **Fact.** oneMKL components are redistributable under Intel's Simplified
  Software License subject to its terms
  ([Intel FAQ](https://www.intel.com/content/www/us/en/developer/articles/tool/onemkl-license-faq.html)).
  **Recommendation.** Preserve the required license files and inventory every
  redistributed runtime.
- **Fact.** Eigen is MPL2
  ([project page](https://libeigen.gitlab.io/)); libigl is primarily MPL2 with
  separately licensed third-party material
  ([license page](https://libigl.github.io/)); Boost uses the Boost Software
  License
  ([official text](https://live.boost.org/users/license.html)); FLANN uses BSD
  ([project page](https://www.cs.ubc.ca/research/flann/)); Ceres uses BSD-3-Clause
  ([license](https://github.com/ceres-solver/ceres-solver/blob/master/LICENSE));
  PETSc uses BSD-2-Clause
  ([license](https://petsc.org/release/install/license/)); Ferreus uses MIT
  ([license](https://github.com/graphic-goose/ferreus_rbf_rs/blob/d0442ee978668386f6ccbeec866bfa52fcc4484f/LICENSE));
  `kifmm` uses BSD-3-Clause
  ([license](https://github.com/bempp/kifmm/blob/d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068/LICENSE));
  Rayon is MIT/Apache-2.0
  ([repository](https://github.com/rayon-rs/rayon)); and LLVM OpenMP is covered by
  Apache-2.0 with the LLVM exception
  ([LLVM policy](https://llvm.org/docs/DeveloperPolicy.html)).
- **Recommendation.** Generate a software bill of materials and third-party
  notice bundle per target from the actual locked dependency graph and native
  artifact, not from this research list.

## Differential validation and acceptance gates

### Required reference corpus

**Recommendation.** Capture reference inputs and outputs from the already-built
Polatory binary at the fixed revision. Fixtures must span:

1. every supported RBF and dimensions 1, 2, and 3;
2. `A`, `F`, `Fᵀ`, and `H`, including mixed scalar/gradient observations;
3. identity, rotated, strongly scaled, and near-degenerate valid anisotropy;
4. coincident/self, near-zero, support-boundary, widely separated, and extreme
   coordinate-scale cases;
5. direct/FMM dispatch on both sides of the exact thresholds;
6. requested FMM accuracy values `0`, finite representative values, and
   infinity;
7. compact, fast, and split spheroidal routes;
8. polynomial degrees and constrained systems;
9. RAS hierarchies with one/multiple RBFs and small/coarse boundary sizes; and
10. thread counts 1 and the supported multicore default.

The current million-point benchmark covers only a 3D exponential covariance
interpolant with polynomial degree zero and tolerance `1e-4`
([benchmark driver](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/benchmark.sh#L5-L43),
[configuration](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/predict.cpp#L20-L30)).
**Inference.** It is a useful scale fixture but cannot validate the derivative
blocks or the complete kernel family.

### Numerical gates

The spec should express error using

`|new - reference| <= atol + rtol × |reference|`

and report maximum absolute, scaled relative, infinity-norm, and non-finite
mismatches. **Recommendation.** Use these values as provisional starting gates,
then freeze or tighten them from baseline measurements before implementation:

| Layer | Provisional acceptance |
|---|---|
| Pure Rust direct scalar kernels | `rtol=1e-12`, scale-aware `atol=1e-13`; signed zero may differ, NaN/Inf classification may not. |
| Direct gradients | `rtol=2e-11`, scale-aware `atol=2e-12`, plus the expected `F/Fᵀ` sign/transpose identities. |
| Direct Hessians | `rtol=5e-10`, scale-aware `atol=5e-12`, plus symmetry after anisotropy. |
| Neighbor evaluator | Same per-interaction kernel gates and identical mathematically defined support membership; additionally compare aggregate outputs under a documented summation-order envelope. |
| FMM backend | Against the Rust direct oracle, error must be no worse than `max(1.25 × Polatory error, 2 × requested_accuracy × reference_scale)` on the same fixture. Zero/infinite-accuracy special modes get separately frozen envelopes. |
| Solved interpolant | Final independently evaluated infinity residual must meet the user tolerance and be no worse than `1.25 ×` the Polatory residual. Compare predictions/derivatives, not coefficient vectors alone. |
| FGMRES/RAS convergence | No false convergence. On the hard-case suite, failures may not increase; median iterations should be no worse than `1.10 ×` baseline and any case over `1.25 ×` requires review. |

**Inference.** Derivatives near singular or zero-valued references cannot be
judged by relative error alone, which is why fixtures need physical
kernel/coordinate scales and absolute tolerances. The exact constants above are
not facts about current Polatory error.

### Scale, memory, and threading gates

**Recommendation.** Benchmark direct/neighbor/FMM matvec, RAS setup, each
preconditioner application, end-to-end solve, and repeated prepared evaluation
at logarithmic sizes through one million unknowns where applicable. Record:

- wall and CPU time, peak resident memory, mapped/temp bytes, and temp I/O;
- FGMRES iterations/restarts and both recurrence/true residual histories;
- FMM configuration, direct/FMM split, backend revision, and measured error;
- RAS levels, domains, factor bytes, cache hit rate, and spill time;
- requested/actual threads and every native dynamic library; and
- cold/warm runs separately.

For the same machine, inputs, thread count, and accuracy, the hybrid v1 candidate
should not regress Polatory end-to-end wall time by more than 25% at 100k and 1M
scale. Peak resident memory must remain within the user-configured budget plus a
documented fixed overhead and must not grow with repeated prepared evaluations.
**Unknown.** The absolute default memory budget and acceptable fixed overhead
require measurements on the intended release hardware.

Determinism policy should require identical membership, termination reason, and
iteration count for one-thread repeated runs. Multithreaded floating-point
outputs may vary only inside the numerical envelope; cache and scheduler order
must not change the mathematical route.

## Requirements to carry into `/to-spec`

The specification should make the following explicit and testable:

1. A backend-neutral Rust `KernelOperator`/`PreparedEvaluator` contract supports
   dimensions 1–3, all v1 RBFs, `A/F/Fᵀ/H`, source/target channel counts,
   anisotropy, direct reference evaluation, requested accuracy, and backend
   diagnostics.
2. Evaluator selection is capability-driven. Unsupported combinations fail
   explicitly or use the deterministic direct route; they never silently drop a
   derivative block.
3. Direct and compact-neighbor evaluators are pure Rust. The large smooth route
   may use the pinned native fallback.
4. Native components are private implementation details, built and tested by
   the release pipeline. The public Rust API and serialized formats contain no
   C++/Eigen/ScalFMM type or layout.
5. FGMRES is flexible, right-preconditioned, restartable, and guarded by the
   independent residual oracle. Memory use is estimated before allocation.
6. Multilevel RAS initially matches Polatory topology and ordering. All dense
   factors participate in one explicit memory/spill budget.
7. One thread-control policy owns Rust, dense algebra, and native backend
   parallelism; nested oversubscription is disabled by default.
8. Backend plans and caches have explicit lifetimes, bounds, metrics, and
   invalidation/version behavior.
9. Release artifacts cover Windows x86-64, Linux x86-64 glibc, macOS ARM64, and
   macOS x86-64, and pass dependency, license-notice, smoke, numerical, and
   multithread tests.
10. Removal of ScalFMM is gated by the entire differential, convergence,
    million-scale, and tier-one-platform suite—not by successful compilation or
    scalar value evaluation alone.

## Open questions and follow-up spikes

These are deliberately unresolved; each changes architecture, schedule, or
acceptance and should become a tracked follow-up rather than an implicit
implementation choice.

1. **Unknown — derivative BBFMM.** Can Ferreus' symmetry-reduced M2L protocol be
   extended to all four matrix blocks and anisotropy without prohibitive operator
   storage or error?
2. **Unknown — component FMM.** Can `green-kernels`/`kifmm` support RapidRBF's
   1D/2D/3D RBF family, non-symmetric derivative blocks, Windows, and a
   native-free FFT path?
3. **Unknown — wrapper portability.** Does the proposed narrow ScalFMM C ABI
   build, load, and pass differential tests on all four tier-one targets, and
   what exact runtime graph does each artifact contain?
4. **Unknown — redistribution.** What CeCILL-C and FFTW obligations apply to the
   chosen wrapper/linking/distribution model?
5. **Unknown — restarted convergence.** Which restart length and
   reorthogonalization policy preserve Polatory convergence on the hard-case
   corpus within the total memory budget?
6. **Unknown — RAS storage.** Which bounded LRU/spill implementation wins on
   million-point RSS, I/O, and solve time without a global file-position mutex?
7. **Unknown — fitting scope.** Is variogram fitting required in v1, and can a
   Rust solver reproduce bounds, numeric differentiation, quaternion-manifold
   behavior, and final-cost/output semantics?
8. **Unknown — neighbor boundary.** Should RapidRBF preserve FLANN's
   `float`-rounded radius boundary or adopt exact `f64` mathematical support
   membership with a documented compatibility exception?
9. **Unknown — Intel macOS.** Should the x86-64 macOS fallback use Accelerate or
   freeze a retired MKL toolchain?
10. **Unknown — source pin.** What exact differences exist between the locally
    built ScalFMM commit and the moving `polatory` branch at each historical
    Polatory build, and which patch set will RapidRBF vendor?
