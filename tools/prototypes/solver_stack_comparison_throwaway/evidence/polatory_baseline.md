# Polatory solver-stack baseline at `4a30beb`

Status: primary-source baseline for the Wayfinder child issue **“Compare Rust
linear-algebra, Krylov, and multilevel preconditioner stacks.”**

Scope: source inspection only. `P:` citations are 1-based line ranges under
`D:/CODE/polatory` at the clean commit
`4a30beb08053fb339ce899e255be4b6d3f74aa0c`. `B:` citations are from the
captured local build under `D:/CODE/polatory/build`; they describe that build,
not an immutable property of the commit. `R:` citations are under
`D:/CODE/interp/RapidRBF`.

## Bottom line

Polatory is not using a packaged solver stack. It has:

| Layer | Actual baseline | Consequence for a Rust comparison |
| --- | --- | --- |
| Dense algebra | Public Eigen `double` matrices, row-major except vectors; Eigen `LDLT`/`FullPivLU`; only BLAS interop is explicitly enabled. The captured x64 Windows build resolves Eigen 5.0.1 and sequential LP64 MKL. | Compare decomposition semantics and factor metadata, not just GEMM speed. Do not leak a candidate crate's matrix type into the RapidRBF contract. |
| Krylov | A small hand-written, right-flexible, **unrestarted** FGMRES. It retains both Arnoldi and preconditioned bases and has no tolerance or restart policy of its own. | A restarted Rust implementation is a deliberate semantic change and needs an unrestarted parity mode/trajectory oracle plus a memory gate. |
| Preconditioner | A custom geometric multilevel restricted additive Schwarz (RAS): dense constrained local solves, an in-memory dense coarse solve, FMM residual transfers, and local factors spilled to one temporary file. | The hierarchy and sweep are part of convergence behavior. Factor storage, I/O concurrency, workspace reuse, and observability must be compared end to end. |

Evidence: `P:include/polatory/types.hpp:7-20`;
`P:include/polatory/interpolation/solver.hpp:99-139`;
`P:include/polatory/preconditioner/ras_preconditioner.hpp:51-53,121-187,191-249`;
`B:vcpkg_installed/vcpkg/status:591-598,656-663`.

## Dense algebra, BLAS, and thread ownership

- `MatX` is an Eigen dynamic matrix of `double`; matrices are row-major while
  one-column vectors are column-major. `Eigen::Index` is the public index type.
  This makes Eigen layout and expression semantics part of Polatory's public
  C++ vocabulary. (`P:include/polatory/types.hpp:7-20`)
- On x64, CMake selects MKL with the sequential threading model and LP64
  interface. Polatory defines `EIGEN_DONT_PARALLELIZE` and `EIGEN_USE_BLAS`;
  `EIGEN_USE_MKL_ALL` is commented out. Thus the build explicitly permits
  Eigen's supported dense products to use BLAS, but the local factorizations
  remain the Eigen `LDLT` and `FullPivLU` implementations rather than an
  explicitly selected LAPACK solver. Apple non-x64 uses Accelerate's BLAS path.
  (`P:CMakeLists.txt:24-31,41-50`;
  `P:src/CMakeLists.txt:58-61,76-83,118-148`)
- The captured Windows build is Release `clang-cl`, `x64-windows`, with
  `-fopenmp`; its compile command contains `EIGEN_DONT_PARALLELIZE`,
  `EIGEN_USE_BLAS`, and OpenMP. (`B:CMakeCache.txt:51-54,274,333`;
  `B:compile_commands.json:184`)
- Parallelism is deliberately outside dense algebra: OpenMP distributes local
  domain setup/solves and the GMRES dot products, while MKL and Eigen are
  sequential. ScalFMM also uses its OpenMP algorithms. There is no solver API
  for thread count, affinity, nesting, or a caller-owned pool; behavior is
  controlled by the OpenMP environment/runtime. (`P:src/krylov/gmres.cpp:16-28`;
  `P:include/polatory/preconditioner/ras_preconditioner.hpp:141-150,280-294`;
  `P:src/fmm/fmm_evaluator.hpp:82-99`)
- The matrix-free interface is allocation-heavy:
  `LinearOperator::operator()(const VecX&) -> VecX` has no `apply_into`,
  workspace, diagnostic context, or batch action. Every operator,
  preconditioner, and transfer action can allocate full-length vectors.
  (`P:include/polatory/krylov/linear_operator.hpp:7-18`;
  `P:include/polatory/interpolation/operator.hpp:56-81`)

## GMRES: what is and is not implemented

### Variants

| Type | Behavior |
| --- | --- |
| `Gmres` | Unrestarted Arnoldi. It permits left and/or right preconditioner pointers. Its reconstruction combines `V` and applies the right preconditioner once, so this is the fixed-linear-right-preconditioner form. (`P:src/krylov/gmres_base.cpp:49-68,79-85`; `P:src/krylov/gmres.cpp:9-50`) |
| `Fgmres` | Inherits the same Arnoldi iteration, forbids a left preconditioner, stores every `z_j = M_j^{-1}v_j`, and reconstructs from `Z`. This is the flexible-right form used by interpolation. (`P:include/polatory/krylov/fgmres.hpp:11-25`; `P:src/krylov/fgmres.cpp:8-28`; `P:include/polatory/interpolation/solver.hpp:99-102`) |
| Restarted GMRES/FGMRES | **Absent.** Constructors accept only `max_iter`; setup allocates for that whole count, and no cycle-reset/restart API exists. (`P:include/polatory/krylov/gmres.hpp:9-14`; `P:include/polatory/krylov/fgmres.hpp:11-25`; `P:src/krylov/gmres_base.cpp:35-47,71-77`) |

The Arnoldi orthogonalization is one-pass classical Gram-Schmidt: all dot
products against the unchanged candidate vector are computed in an OpenMP
loop, followed by a separate serial subtraction loop. There is no
reorthogonalization and no happy-breakdown or near-zero guard before division
by the new basis norm, Givens denominator, or triangular diagonal.
(`P:src/krylov/gmres.cpp:16-28,30-49`;
`P:src/krylov/gmres_base.cpp:49-59`)

`setup()` preallocates `R` as `(max_iter + 1) x max_iter`, initializes the first
basis vector, and each iteration appends one `V` vector; FGMRES additionally
copies and appends one `Z` vector. For `n` unknowns and `k` completed iterations,
the persistent bases alone are approximately

```text
8 * n * ((k + 1) + k) = 8 * n * (2k + 1) bytes.
```

At `n = 1,000,000`, the public default ceiling `k = 100` permits about
1.608 GB decimal (1.498 GiB) for `V + Z`, excluding `rhs`, `x0`, the current
solution, action temporaries, FMM state, and RAS. (`P:include/polatory/krylov/gmres_base.hpp:51-89`;
`P:include/polatory/krylov/fgmres.hpp:21-25`;
`P:include/polatory/interpolant.hpp:77-85`)

Production calls `solution_vector()` before every convergence observation.
That method repeats the triangular back solve and a linear combination of all
stored `Z` vectors, so solution reconstruction alone accumulates
`O(n k^2)` vector traffic over an unrestarted run. Arnoldi similarly accumulates
`O(n k^2)` dot/axpy traffic. (`P:src/krylov/fgmres.cpp:8-25`;
`P:include/polatory/interpolation/solver.hpp:116-139`)

Two API observations matter for a port:

- `GmresBase::converged()` returns `converged_`, but a search of this commit
  finds no assignment that can make the default-initialized flag true.
  Production does not use it. (`P:include/polatory/krylov/gmres_base.hpp:18-38,90`;
  `P:src/krylov/gmres_base.cpp:7-15`)
- The Krylov tests cover 100-by-100 fixed operators/preconditioners and compare
  the recurrence residual with a recomputed residual when there is no left
  preconditioner. They do not exercise a changing flexible preconditioner,
  restart, zero RHS, breakdown, or maximum-iteration diagnostics.
  (`P:test/krylov/test_krylov.cpp:83-136`)

### The actual stopping observation

The Krylov core has no tolerance. The interpolation solver drives one iteration
at a time and stops on an independent interpolation-error observation:

1. At iteration 0 and after every Arnoldi step, it reconstructs the weights.
2. It directly evaluates at up to 1,024 value targets and up to 1,024 gradient
   targets. Indices are shuffled with a default-constructed `mt19937` and
   partitioned to prefer nonzero observations.
3. If either sampled absolute infinity-norm error exceeds its channel tolerance,
   it reports that sample (prefixed `~`) and performs another Krylov step.
4. If the sample passes, it evaluates all data sites and only then may declare
   convergence. For at most 1,024 sites the direct pass already covers all
   sites. (`P:include/polatory/interpolation/solver.hpp:109-139`;
   `P:include/polatory/interpolation/residual_evaluator.hpp:35,55-107,120-150`)

This is more truthful than stopping on `|g_k| / ||rhs||`, but “exact” in the
printed flags means **full-site coverage**, not exact arithmetic. For large
systems the full observation uses the configured symmetric evaluator. With the
public default `accuracy = infinity`, Polatory's FMM selector uses fixed order 6,
not a direct or zero-error calculation. The observation checks value and
gradient interpolation equations (including the value nugget), but not the
polynomial side equation `P^T lambda = 0`. (`P:include/polatory/interpolant.hpp:77-85`;
`P:src/fmm/fmm_accuracy_estimator.hpp:70-82`;
`P:include/polatory/interpolation/residual_evaluator.hpp:70-106`)

The internal recurrence residual is exposed but not printed or used except for
an exact-zero early return after setup. The only production iteration record is
unstructured stdout with `iter`, value residual, and gradient residual; reaching
`max_iter` throws a generic exception and does not return a termination record
or partial result. (`P:src/krylov/gmres_base.cpp:7-15`;
`P:include/polatory/interpolation/solver.hpp:104-139`)

## Current multilevel RAS

### Hierarchy and domain construction

- Let `N = mu + Dim*sigma` be the number of RBF unknown components. The level
  count is
  `max(ceil(log_10(N / 2048)), 0) + 1`; adjacent target sizes are distributed
  geometrically between the finest size and the approximately 2,048-component
  coarsest target. (`P:include/polatory/preconditioner/ras_preconditioner.hpp:51-72,127-140`)
- With exactly one non-identity-anisotropic RBF, partitioning uses transformed
  coordinates. With multiple RBFs it uses the original coordinates, even when
  individual anisotropies differ. (`P:include/polatory/preconditioner/ras_preconditioner.hpp:110-119`)
- A domain is recursively sorted along bbox axes and bisected until
  `num_values + Dim*num_grad_values <= 1024`. The split formula duplicates
  about `0.5 * 1024 = 512` scalar components across the two children; inner
  ownership remains disjoint. Polynomial unisolvent points are then inserted
  into every leaf and marked non-inner except where already owned. This is the
  restriction in RAS: local RHS restriction includes overlap, but scatter writes
  only inner components. (`P:include/polatory/preconditioner/domain_divider.hpp:26-27,161-269`;
  `P:include/polatory/preconditioner/domain.hpp:30-51`;
  `P:include/polatory/preconditioner/fine_grid.hpp:97-117`)
- Coarse representatives are selected by repeatedly splitting spatial clusters
  and choosing a point nearest each cluster bbox center; a gradient point counts
  with multiplicity `Dim`. Polynomial points are forced into every coarse set.
  (`P:include/polatory/preconditioner/domain_divider.hpp:54-125,132-159,278-309`)

### Local and coarse factorization

Each domain first assembles the full dense symmetric value/gradient matrix `A`
by pairwise RBF, gradient, and Hessian evaluation. There is no sparse matrix or
iterative local solve. (`P:include/polatory/preconditioner/mat_a.hpp:10-60`)

For polynomial models, the code represents a null-space basis as
`Q = [Q_top; I]`, forms dense `Q^T A Q`, and factors it with Eigen `LDLT`.
The local correction is recovered as `lambda = Q gamma`.
(`P:include/polatory/preconditioner/fine_grid.hpp:59-90,119-140`)

- Fine domains use a custom subclass that exposes Eigen's internal factor
  matrix. The lower triangle is packed and written to the cache, and the dense
  matrix storage is released. On every solve it allocates the full square
  matrix, reads/unpacks the factor, solves, and releases that matrix again.
  Only the matrix payload is spilled; the live Eigen decomposition object keeps
  the remaining pivot/decomposition state. A Rust factor record therefore
  cannot be specified as “lower triangle only” without defining all required
  permutation and status metadata. (`P:include/polatory/preconditioner/fine_grid.hpp:17-30,145-191`)
- The coarsest constrained `LDLT` remains resident. The coarse grid also retains
  the first `l` rows of `A` and a `FullPivLU` of the selected polynomial block
  to recover polynomial coefficients. (`P:include/polatory/preconditioner/coarse_grid.hpp:40-85,101-155`)
- No factorization `info`, rank, conditioning, or non-finite result is checked
  before solve in either grid. (`P:include/polatory/preconditioner/fine_grid.hpp:81-90,126-140`;
  `P:include/polatory/preconditioner/coarse_grid.hpp:62-85,111-130`)

### Application sweep

For more than one level, one right-preconditioner application is not a simple
sum of independent leaves. It performs:

1. a coarse solve and a residual update on the finest level;
2. for intermediate levels in ascending order, a level solve/update on the
   finest grid, polynomial orthogonalization, then another coarse solve/update;
3. for fine levels in descending order, a level solve whose effect is
   transferred to the next-coarser level, polynomial orthogonalization, then a
   coarse solve (with another transfer except after level 1).

Fine-level solves are OpenMP-parallel and scatter only unique inner ownership.
Residual transfers use lazily created, cached matrix-action evaluators; the
default infinite requested accuracy selects the fixed order-6 FMM configuration.
For `L > 1`, intermediate fine levels are therefore solved twice per
application, the finest level once, and the coarse grid repeatedly.
(`P:include/polatory/preconditioner/ras_preconditioner.hpp:191-249,255-328`;
`P:src/fmm/fmm_accuracy_estimator.hpp:74-82`)

Polynomial corrections are explicitly projected with an orthonormalized `P`,
and `A*P` is precomputed with full finest-level evaluations. This topology,
transfer accuracy, projection, and sweep order can change outer FGMRES
convergence if altered. (`P:include/polatory/preconditioner/ras_preconditioner.hpp:173-188,271-277`)

### Temporary factor I/O

`BinaryCache` owns one file in the operating-system temporary directory. Windows
opens it delete-on-close; POSIX unlinks it immediately. Every record uses a
shared file position, and every seek/read/write is inside one mutex. Return
values and short reads/writes are not checked; there is no capacity check,
memory tier, LRU, checksum, version header, user-selected directory, or I/O
metric. (`P:include/polatory/preconditioner/binary_cache.hpp:18-49,56-104`)

Parallel fine-grid construction can factor domains concurrently, but its writes
serialize. Parallel application can overlap unpacking and dense solves, but all
factor reads serialize through the same mutex/file cursor. Factors are reread
on every use, including the lower levels used twice in one RAS application.
(`P:include/polatory/preconditioner/ras_preconditioner.hpp:141-150,280-294`;
`P:include/polatory/preconditioner/fine_grid.hpp:126-140,145-170`)

Preconditioner residual reporting exists only behind
`static constexpr bool kReportResidual = false`; setup always prints a level
table, while applications report no level residuals, factor bytes, cache I/O,
or timings in the shipped source. (`P:include/polatory/preconditioner/ras_preconditioner.hpp:51-53,123-166,330-343`)

## Static million-unknown pressure points

These are code-derived estimates, **not measurements**. The calculation assumes
one million scalar value unknowns, balanced scalar splits, and ignores the small
`O(l)` polynomial correction. Mixed gradient multiplicities and floating-point
rounding of level targets change exact counts.

The hierarchy formula gives approximately
`2.0k -> 16.1k -> 127k -> 1.0M` components. Simulating the divider's scalar
count recurrence gives:

| Fine level | Level components | Approx. leaves | Local factor order | Packed factor bytes |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 16,126 | 32 | ~1,000 | 0.128 GB |
| 2 | 126,992 | 256 | ~1,006 | 1.037 GB |
| 3 | 1,000,000 | 2,048 | ~1,000 | 8.200 GB |
| **Total fine cache** |  |  |  | **~9.366 GB** |

The packed size uses exactly the source formula
`rows * (rows + 1) / 2 * sizeof(double)`. Because levels 1 and 2 are solved
twice and level 3 once, this idealized four-level application requests about
`2*0.128 + 2*1.037 + 8.200 = 10.53 GB` of factor reads per FGMRES iteration,
through the single cache mutex. OS caching may turn some disk reads into memory
traffic, but then the “spill” competes with Krylov/FMM memory through the page
cache. (`P:include/polatory/preconditioner/fine_grid.hpp:158-170`;
`P:include/polatory/preconditioner/ras_preconditioner.hpp:213-247`)

The leading million-scale bottlenecks visible from source are:

1. **Stopping oracle:** at one million value sources, the mandatory 1,024-target
   direct sample performs roughly 1.024 billion source-target kernel
   interactions at every convergence check. It is OpenMP-parallel, but it is
   still all-pairs and occurs before the full FMM check. (`P:include/polatory/interpolation/residual_evaluator.hpp:69-90,124-150`;
   `P:include/polatory/interpolation/direct_evaluator.hpp:38-79`)
2. **Serialized factor traffic:** approximately 9.4 GB of packed scratch in the
   ideal scalar case and about 10.5 GB requested per four-level application,
   plus full square factor matrices allocated in active domain tasks.
3. **FGMRES basis and reconstruction:** up to ~1.6 GB for the two bases at the
   default 100-iteration ceiling, with quadratic-in-iteration memory traffic.
4. **Repeated FMM plan/tree work:** non-symmetric evaluators release source and
   target trees after every evaluation, and symmetric evaluators release their
   tree too. Configurations/interpolators and sorted particles are retained, but
   group trees and interaction lists are rebuilt for later actions. One RAS
   application also performs many interlevel transfers. (`P:src/fmm/fmm_evaluator.hpp:77-111,226-270`;
   `P:src/fmm/fmm_symmetric_evaluator.hpp:66-95,227-251`)
5. **Setup:** every leaf forms an `O(s^2)` dense matrix and performs an
   `O(s^3)` dense factorization; many domains run concurrently, so setup peak
   RAM scales with OpenMP concurrency even though finished factors spill.
6. **Full-vector churn:** each solve/transfer constructs zeroed global or
   level-sized vectors, and the action interface cannot accept reusable output
   buffers. (`P:include/polatory/preconditioner/ras_preconditioner.hpp:197-249,280-327`)

The repository advertises “1M+ input points” and its benchmark script names 1M
fit/evaluation cases, but this evidence pass did not run them. The prior
RapidRBF baseline audit likewise records that no million-point workload had
been run and requires RAM/scratch/thread capture before treating it as a
performance result. (`P:README.md:7-21`;
`P:benchmark/benchmark.sh:5-18,40-43`;
`R:docs/research/polatory-validation-performance-release-baseline.md:41-43`)

## Comparison requirements induced by this baseline

A Rust candidate matrix should test the following rather than compare crate
feature lists:

- **Dense:** row/column layout conversion, symmetric pivoted `LDLT` behavior on
  the actual constrained matrices, full-pivot polynomial solve behavior,
  factor status/rank reporting, serialized factor representation including
  pivots, sequential-in-domain execution, and coarse-grid peak memory.
- **Krylov:** flexible-right FGMRES, an unrestarted parity mode, configurable
  restarted mode, classical-vs-modified Gram-Schmidt trajectory, optional
  reorthogonalization, breakdown handling, reusable workspaces, and both
  recurrence and independently recomputed residuals.
- **RAS:** identical level targets, anisotropy partition rule, coarse selection,
  overlap/inner restriction, polynomial projection, sweep order, transfer
  accuracy, and iteration envelope before tuning any constant.
- **Resources:** one caller-owned thread budget, a bounded resident-factor LRU,
  parallel positional reads or mmap rather than a shared cursor, configurable
  ephemeral scratch, early RAM/disk checks, and metrics for factor bytes,
  cache hits, I/O time, matvecs, preconditioner applications, and termination.

## Uncertainties and source-level risks to resolve

1. **ScalFMM is not frozen by the Polatory commit.** CMake shallow-fetches the
   moving tag `polatory`; the captured checkout reports
   `0be3d74f17adb28adec7004f712f693ac8ee9901`, but a clean future build can
   resolve differently. (`P:src/CMakeLists.txt:155-165`;
   `R:docs/research/polatory-validation-performance-release-baseline.md:50-61`)
2. **“True residual” needs a precise contract.** Final coverage is full, but
   its evaluator may be approximate; the polynomial constraint is not observed.
   A Rust comparison needs a genuinely independent high-accuracy final oracle,
   while retaining Polatory's printed trace as compatibility evidence.
3. **Gradient-row restriction appears suspicious.** Fine and coarse setup index
   gradient rows of the full Lagrange matrix using local `mu_ + Dim*i`, although
   the full matrix's gradient block begins at `points_full.rows()`. The component
   tests construct domains containing all value points, where those offsets
   coincide; a multilevel mixed value/gradient reproducer is needed before
   porting this literally. (`P:include/polatory/preconditioner/fine_grid.hpp:59-95`;
   `P:include/polatory/preconditioner/coarse_grid.hpp:40-59,87-89`;
   `P:test/preconditioner/test_fine_grid.cpp:38-43,98-107`)
4. **Numerical failure behavior is unspecified.** There are no factor-health
   checks, no GMRES breakdown guards, and no structured reason codes. Matching
   NaN/throw behavior should not be assumed to be the desired RapidRBF contract.
5. **RAS coverage is indirect.** The checked-in preconditioner tests exercise
   domain ownership and isolated fine/coarse solves, but no test directly names
   `RasPreconditioner`; full hierarchy/sweep parity needs new fixtures.
   (`P:test/preconditioner/test_domain_divider.cpp:18-99`;
   `P:test/preconditioner/test_fine_grid.cpp:37-141`;
   `P:test/preconditioner/test_coarse_grid.cpp:35-122`)
6. **The scale estimates require measurement.** Geometry, gradient
   multiplicities, polynomial degree, filesystem/page-cache behavior, FMM
   order, OpenMP count, and actual iteration count all affect peak RAM,
   scratch, and time. Capture those together; solver restart length and factor
   residency compete for the same memory budget.
