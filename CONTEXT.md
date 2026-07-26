# RapidRBF

RapidRBF is a Rust-native framework for radial basis function interpolation whose migration decisions are grounded in Polatory's observable behavior.

## Language

**Behavior-compatible successor**:
A Rust-native successor that preserves the selected observable capabilities, numerical semantics, and acceptance results of Polatory without promising C++ source compatibility, ABI compatibility, or the same internal architecture.
_Avoid_: Port, drop-in replacement, line-by-line rewrite

**Compatibility surface**:
The complete set of Polatory capabilities and documented semantic outcomes visible to library, CLI, and Python users, re-expressed through idiomatic Rust interfaces where appropriate. Incidental text, ordering, algorithm trajectories, internal helpers, and implementation details are outside this surface unless explicitly named.
_Avoid_: Public headers, internal API, source compatibility

**Intentional compatibility change**:
A documented RapidRBF behavior that deliberately differs from Polatory because the legacy behavior is mathematically undefined, structurally invalid, unsafe, or a proven defect. Where applicable, RapidRBF provides a stable error category and migration guidance rather than preserving the legacy outcome.
_Avoid_: Behavior drift, accidental incompatibility, silent fix

**Self-contained distribution**:
An official RapidRBF package that requires no separately installed compiler toolchain or native numerical dependency from its user, even when its internals include a native backend.
_Avoid_: Source-only release, system dependency

**Tier-one platform**:
A supported operating-system and architecture pair whose library, CLI, and Python artifacts must pass the v1.0.0 release gates. The tier-one set is Windows x86_64, Linux x86_64 with glibc, macOS arm64, and macOS x86_64.
_Avoid_: Best-effort platform, build-only target

**Million-scale workload**:
A release-blocking interpolation workload with at least one million input points whose fit, evaluation, convergence, peak memory, and runtime are assessed against the Polatory baseline on identical hardware and inputs.
_Avoid_: Scalability demo, aspirational benchmark

**Numerical compatibility**:
Agreement with Polatory's mathematical conventions and observable numerical outcomes under explicitly defined error, residual, and convergence tolerances. It does not require bitwise-identical results, identical coefficients, or identical solver and optimizer trajectories.
_Avoid_: Bitwise compatibility, visually similar output

**Fit success**:
A fitted interpolant state whose full value and gradient observation residuals, recomputed from the candidate outside the solver's internal convergence estimate, are finite and within their configured absolute infinity-norm tolerances. Sampling may guide computation but cannot establish fit success.
_Avoid_: Solver convergence, sampled convergence, internal residual success

**Kernel parameter domain**:
The finite parameter set in which `scale`, `psill`, `c`, and `nugget` are non-negative and covariance `range` is strictly positive. A zero-amplitude component remains part of the model with its family identity and CPD rules; negative `c` is invalid rather than normalized.
_Avoid_: Legacy permissive parameters, absolute-value normalization, zero-component elision

**Defined kernel derivative**:
A kernel derivative that has a unique finite mathematical value at the requested displacement; a zero-amplitude component is the identically zero function. Legacy zero, non-finite, or unsupported outcomes do not create a defined derivative.
_Avoid_: Legacy derivative behavior, arbitrary origin derivative

**Hermite-safe model**:
A model whose every non-zero RBF component has a defined Hessian at zero displacement, so gradient-center self-interactions are mathematically defined before assembly.
_Avoid_: Hessian method present, Polatory-supported Hermite model

**Valid anisotropy transformation**:
A finite, full-rank, orientation-preserving linear transform, including nonsymmetric shear, whose validity is established without relying on a raw determinant threshold. Ill-conditioning is diagnostic rather than invalidity; an operation that cannot produce a finite result fails with a numerical-domain error.
_Avoid_: Rotation-and-scale only, determinant-only validation, fixed condition-number cutoff

**Kernel branch contract**:
The piecewise classification of a kernel at compact-support and spheroidal switch boundaries, with exact branch membership and exact numerical zero outside compact support. Values within a selected branch are tolerance-based mathematical results rather than bitwise replays of legacy rounding.
_Avoid_: Fuzzy branch boundary, bitwise boundary replay

**Finite problem data**:
Public problem data and concrete numerical controls reaching the RapidRBF core contain only finite values; absence and unconstrained choices are represented structurally. Legacy NaN sentinels may be translated only at migration adapters before core validation.
_Avoid_: Core NaN sentinel, infinity as `Any`, infinity as an absent bound

**Duplicate interpolation observation**:
A value observation or full-gradient observation with the same signed-zero-normalized coordinates, channel, and exact payload as another observation; duplicates are merged deterministically, while conflicting payloads are invalid. A value and full gradient at the same point are distinct, valid Hermite constraints.
_Avoid_: Near-neighbor duplicate, tolerance-based auto-merge, conflicting repeat

**Solvable interpolation system**:
An interpolation problem whose combined value-and-gradient polynomial observation matrix has full column rank and whose complete interpolation operator can be solved without numerical breakdown. Rank failure never triggers implicit degree reduction, constraint removal, nugget insertion, or a minimum-norm fallback.
_Avoid_: Point-count heuristic, implicitly regularized fit, best-effort singular solve

**Numerical full column rank**:
A full-column-rank result on the deterministically coordinate-scaled and row/column-equilibrated matrix when its certified singular-value ratio exceeds an explicit threshold. Cases whose f64 uncertainty straddles the threshold are adjudicated at higher precision rather than delegated to backend rounding.
_Avoid_: Raw-coordinate rank, determinant magnitude threshold, BLAS-dependent boundary decision

**Observation-free fit**:
A fit request with no effective value, gradient, or inequality constraints; it is invalid rather than a fitted empty interpolant. Empty target batches are valid only for an already fitted interpolant and produce shape-correct empty results.
_Avoid_: Empty interpolant, zero-point fit, unfitted empty evaluation

**Compatible warm start**:
A prior interpolant with the same dimension and exact canonical model structure whose matching value and gradient observation weights may seed a new fit independently of observation order. It is only an acceleration input, never relaxes fit success, and incompatibility is explicit rather than a silent cold start.
_Avoid_: Best-effort model match, tolerance-matched warm start, silent fallback

**Value constraint interval**:
The inclusive lower and upper value bounds attached to one signed-zero-normalized coordinate; a singleton interval is an equality and either endpoint may be structurally absent. Constraints at the same coordinate intersect, with an empty intersection infeasible and two absent endpoints invalid.
_Avoid_: NaN constraint triplet, column precedence, infinite missing bound

**Inequality fit**:
The zero-nugget, minimum-native-seminorm interpolant that satisfies every value constraint interval and the model's CPD polynomial side conditions. Success is established by full feasibility and KKT checks rather than by reproducing an active-set trajectory.
_Avoid_: Active-set replay, soft-nugget inequality, sampled feasibility

**Certified inequality fit**:
An inequality fit whose independently recomputed values satisfy all equalities and intervals and whose finite kernel weights pass normalized dual-sign, complementarity, CPD side-condition, and native-seminorm checks. Budget exhaustion without an infeasibility certificate is non-convergence, not proof of infeasibility.
_Avoid_: Feasibility-only success, active-set stability as a KKT certificate, inferred infeasibility

**Incremental fit**:
A fit whose centers are a deterministic subset of the supplied value and full-gradient observations while fit success is checked against every supplied observation. It may retain all centers and does not promise a minimum subset or the legacy selection trajectory.
_Avoid_: Minimal-center fit, legacy reduction replay, sampled residual fit

**Incremental selection score**:
The channel-tolerance-normalized residual violation used to choose original observations, compared with certified error intervals and an original-index tie-break. Selection is repeatable within a release and independent of thread scheduling, while cross-backend compatibility is established by the full-data certificate rather than identical center membership.
_Avoid_: Raw mixed-unit residual ranking, scheduling-order tie-break, cross-backend subset identity

**Interpolation fit controls**:
Each present observation channel has a finite strictly positive absolute fit tolerance, while absent channels have no sentinel tolerance. The iteration budget is a non-negative integer; zero performs only complete certification of the supplied initial or warm-start candidate and otherwise ends as non-convergence.
_Avoid_: Zero fit tolerance, absent-channel numeric sentinel, zero-iteration cold solve

**Requested accuracy**:
A positive absolute infinity-norm ceiling on value or gradient approximation error against the canonical direct reference at the requested targets. `Any` removes the per-call ceiling but not the operation-level numerical acceptance standard.
_Avoid_: Relative accuracy, scale-adjusted accuracy, backend tuning hint

**Default accuracy profile**:
The public, named, and versioned absolute infinity-norm error envelope used when requested accuracy is `Any`. A backend must certify that envelope or refine, fall back, or fail; certificate-bearing operations instead derive a concrete internal budget from their outer tolerance.
_Avoid_: Unlimited `Any` error, undocumented backend default, using the default profile as a fit certificate

**Normal-score transformation**:
The inverse-standard-normal mapping of finite observations using plotting positions, with exact ties sharing a stable midrank and results restored to observation order. A singleton or constant sample maps to the zero score and a constant inverse; an empty sample is invalid.
_Avoid_: Unstable tied ranks, arbitrary tie order, undefined singleton transform

**Normal-score Hermite order**:
The non-negative truncation order of a transformed sample's Hermite back-transform, with default 30 and order zero retaining only the constant term. It is part of certified transformation state; recurrence failure is explicit and never triggers silent order reduction.
_Avoid_: Fixed order-30 capability, negative order, partial high-order output, implicit order fallback

**Normal-score semivariance**:
A transformed-scale semivariance `gamma_y = 1 - rho` in the mathematically valid interval `[0,2]` before Hermite back-transformation. Empirical estimates outside that interval are projected with an explicit diagnostic; the mathematical API rejects them.
_Avoid_: Unbounded Hermite extrapolation, silent semivariance clipping

**Experimental variogram**:
The non-empty directional lag bins formed from every unordered pair of distinct observation rows, each contributing half its squared value difference to every matching bin. Same-coordinate replicates are retained as directionless zero-lag pairs in every direction, and lag windows may overlap.
_Avoid_: Deduplicated replicate measurements, single-bin pair assignment, empty variogram artifact

**Variogram lag lattice**:
The inclusive windows `abs(distance - k * lag_distance) <= lag_tolerance` for `k` from zero through `num_lags - 1`. Empty bins and directions are stably omitted, pair counts remain exact, and floating aggregates use deterministic stable reduction without promising cross-platform bitwise identity.
_Avoid_: Open interval endpoints, one-based lag centers, empty artifacts, schedule-dependent pair membership

**Variogram membership count**:
The sum of bin memberships across every retained direction, so a source pair is counted once for each overlapping lag window and direction it enters. It is distinct from the number of unique unordered source pairs.
_Avoid_: Unique-pair count, deduplicated overlapping membership

**Variogram fit weight**:
A finite real exponent triple defining the weighted-least-squares objective weight `distance^e_h * model_gamma^e_g * num_pairs^e_n`, with six compatibility presets. Zero to a positive exponent yields a valid zero weight, zero to the zeroth power is one, and zero to a negative exponent is undefined; at least one objective term must have positive finite weight.
_Avoid_: Residual multiplier, six-preset-only API, epsilon-regularized denominator, silently omitted undefined bin

**Variogram fitting objective**:
The unnormalized weighted sum of squared bin errors `sum_b w_b(theta) * (gamma_hat_b - g_b(theta))^2` across every stored direction and bin. Model-dependent weights are recomputed for every candidate; a solver's square-root residuals or one-half cost convention do not redefine the reported objective.
_Avoid_: Squared weights, frozen model-dependent weights, direction-normalized objective, solver-native cost reporting

**Variogram direction**:
A finite normalized unoriented axis used to classify non-zero observation pairs; opposite signs are the same direction, duplicate unoriented axes are invalid, and isotropic calculation is a separate mode. Automatic classification selects one nearest axis with a stable tie-break, while an explicit angular tolerance in `[0, pi/2]` may select several.
_Avoid_: Oriented direction vector, duplicate axis, synthetic isotropic axis, unstable nearest direction

**Variogram bin model value**:
For a directional bin, the model semivariance at its mean distance along its stored unoriented axis; for an isotropic bin, the accuracy-certified uniform angular mean at that radius. Isotropic bins contribute to the objective but never to anisotropy-identifiability coverage.
_Avoid_: Synthetic `UnitX` isotropy, replaying discarded pair vectors, treating radial bins as directional evidence

**Identifiable variogram anisotropy**:
Directional coverage whose centered outer products `u*u^T - I/d` span the trace-free symmetric matrix space, followed by a full-column-rank anisotropy-parameter Jacobian at the fitted candidate. Structural insufficiency permits `Auto` to retain fixed metrics; numerical rank failure after selecting `Fit` is explicit.
_Avoid_: Vector-span-only coverage, isotropic-bin coverage, silent post-fit fallback

**Variogram anisotropy mode**:
`Fixed` preserves each supplied covariance metric, `Fit` estimates shared principal axes and component-specific axis ratios when directional coverage is identifiable, and `Auto` selects between them with a diagnostic. One-dimensional fitting is always fixed, and fitted metrics use a canonical positive-definite representative.
_Avoid_: Identity reset, silently disabled anisotropy, non-identifiable 1D anisotropy fit

**Canonical covariance metric**:
The unique symmetric positive-definite, determinant-one representative of anisotropic shape, with its common distance scale absorbed into `range`. The configurable compatibility-default `Fit` envelope permits a 2D major/minor principal-range ratio of 100 and, in 3D, each adjacent ratio up to 100 for an overall ratio up to 10000; it does not restrict otherwise valid `Fixed` metrics.
_Avoid_: Gauge-dependent `range`/matrix pairs, hidden post-fit clipping, treating fit bounds as model-validity bounds

**Reproducible variogram fit**:
A bounded deterministic multi-start fit whose starts are controlled by an explicit seed, whose candidates are independently revalidated and rescored, and whose winner is selected by objective value with a stable trial-order tie-break. Compatibility concerns the objective and modeled values within tolerance, not optimizer trajectory or bitwise parameter identity.
_Avoid_: Unseeded trials, accepting an unchecked terminal iterate, optimizer-specific trajectory contracts

**Usable variogram-fit candidate**:
A converged, in-domain covariance model whose objective and every weight are independently recomputable and finite. Trial-local invalidity is diagnostic and does not abort other starts, while a non-converged terminal iterate or an operation interrupted by cancellation, deadline, or resource failure is never returned as best-so-far.
_Avoid_: Lowest reported cost regardless of termination, clipped candidate, zero-trial identity result, interrupted best-so-far result

**Polynomial detrending**:
The finite residual from the least-squares orthogonal projection of observations onto the requested degree-zero, degree-one, or degree-two monomial space. The scaled design must be full column rank and the residual must satisfy a checked orthogonality condition.
_Avoid_: Core `-1` sentinels, unchecked normal equations, silent degree reduction, arbitrary rank-deficient coefficients

**Observation semivariance**:
For two distinct observation rows separated by `d`, the model value is `nugget + sum(C_i(0) - C_i(d))`, including when their coordinates coincide. A self-pair instead has semivariance zero and is never enumerated; nugget likewise applies only to the observation diagonal during fitting and is not added to smooth-field predictions.
_Avoid_: Conflating zero separation with self-identity, dropping zero-lag replicates, adding nugget to predictions

**Grouped cross-validation**:
Value-only prediction with a supplied fixed model, where equal set IDs define held-out folds processed in stable first-appearance order and predictions retain original row order. Each complementary training set must be independently solvable; any fold failure atomically fails the operation with the fold identity and underlying cause.
_Avoid_: Implicit model refitting or data transforms, hash-order-dependent folds, partial results padded with NaN

**Kriging drift degree**:
For a covariance model, polynomial degree minus one denotes a known zero mean, degree zero an unknown constant drift, and degrees one or two the corresponding universal-kriging drift spaces. Variogram fitting preserves but does not optimize this degree, and standalone detrending or normal-score state is never replayed implicitly by prediction or cross-validation.
_Avoid_: Hidden trend reconstruction, variogram-optimized drift degree, implicit transformation replay

**Certified interpolation fit**:
A transactional fit whose finite coefficients independently satisfy the complete augmented observation equations and the normalized CPD side-condition residual before replacing interpolant state. Nugget participates only in value observation equations, so certification does not require the resulting smooth field to pass through noisy values.
_Avoid_: Solver-recurrence-only stopping, unchecked polynomial moments, partially committed failed fits, best-effort coefficients

**Certified error budget**:
The acceptance rule for a result computed with a certified approximation error `alpha`: the independently measured residual plus `alpha` must remain within the public operation tolerance. A fit must obtain a concrete error bound even when public evaluation otherwise permits `Any`.
_Avoid_: Treating requested accuracy as a tuning hint, spending the full tolerance on solver residual, using `Any` as proof

**Atomic evaluation batch**:
An order-preserving value-only or value-and-gradient request that returns a complete finite result within requested accuracy or fails as a whole with the first failing target index and stable cause. Failure never emits partial arrays or mutates certified interpolant state.
_Avoid_: NaN-padded output, partial batch success, unordered failure diagnostics

**Legacy artifact**:
A model or fitted interpolant serialized by Polatory's unversioned native binary format and accepted by RapidRBF only through a one-way migration path.
_Avoid_: RapidRBF format, portable model

**Portable artifact**:
A versioned RapidRBF model or fitted interpolant representation with an explicit cross-platform compatibility contract.
_Avoid_: Native memory dump, legacy artifact

**Reference hierarchy**:
The order used to judge numerical discrepancies: explicit mathematical definitions and high-precision direct references first, Polatory's observable behavior second, and a RapidRBF candidate implementation third. Proven Polatory defects become documented intentional differences rather than compatibility requirements.
_Avoid_: Polatory is always correct, implementation-defined truth

**Polatory baseline**:
The frozen Polatory source revision `4a30beb`, together with its captured build configuration, dependency versions, datasets, and executable artifacts, used for RapidRBF v1.0.0 differential and performance comparisons.
_Avoid_: Latest Polatory, moving upstream target

**Reproducibility controls**:
Stable Rust, Python, and CLI inputs and metadata that expose build identity, random seeds, configured and effective thread counts, and relevant runtime configuration without promising identical random sequences across implementations.
_Avoid_: Bitwise deterministic execution, hidden execution defaults

**Performance parity**:
Absence of a material regression from the Polatory baseline in runtime, peak memory, or iterative convergence for the accepted benchmark suite, using empirically calibrated thresholds and a separate hard gate for million-scale workloads.
_Avoid_: Runs successfully, asymptotically similar

**Python migration compatibility**:
Preservation of Polatory Python workflows, array shapes, and numerical semantics through the `rapidrbf` package, with a mechanical migration path but no promise that existing source runs unchanged or that RapidRBF replaces the `polatory` package name.
_Avoid_: Drop-in Python replacement, unrelated Python API

**CLI migration compatibility**:
Preservation of Polatory command names, option meanings, exit behavior, and tabular input/output conventions under the new `rapidrbf` executable, except for explicitly justified incompatibilities.
_Avoid_: `polatory` executable replacement, unrelated CLI

**Official release set**:
The v1.0.0 artifacts whose successful publication is release-blocking: the stable Rust library, tier-one prebuilt CLI binaries, tier-one CPython wheels, and a source distribution with license inventory, SBOM, and checksums.
_Avoid_: Source-only release, package-manager availability
