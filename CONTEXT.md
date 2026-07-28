# RapidRBF

RapidRBF is a Rust-native framework for radial basis function interpolation whose migration decisions are grounded in Polatory's observable behavior.

## Language

**Behavior-compatible successor**:
A Rust-native successor that preserves the selected observable capabilities, numerical semantics, and acceptance results of Polatory without promising C++ source compatibility, ABI compatibility, or the same internal architecture.
_Avoid_: Port, drop-in replacement, line-by-line rewrite

**Compatibility surface**:
The complete set of Polatory capabilities and documented semantic outcomes visible to library, CLI, and Python users, re-expressed through idiomatic Rust interfaces where appropriate. Incidental text, ordering, algorithm trajectories, internal helpers, and implementation details are outside this surface unless explicitly named.
_Avoid_: Public headers, internal API, source compatibility

**Acceptance workload tier**:
The earliest cumulative gate at which an acceptance scenario must pass: `PR`, `Extended`, `Nightly`, or `Release-blocking`. Each higher tier includes the lower tiers; platform, oracle, resource, and workflow attributes remain orthogonal scenario metadata rather than duplicate tiers.
_Avoid_: Exclusive test bucket, importance label, duplicated workload matrix

**Acceptance workload coverage**:
Coverage of every level of each compatibility axis plus deterministic pairwise combinations and explicitly required high-risk interactions, without requiring the full Cartesian product. Cheap atomic kernel semantics may be exhaustive, while expensive fit, geometry, and scale scenarios use pre-registered representative journeys.
_Avoid_: Full Cartesian matrix, ad hoc sampling, one happy path per feature

**Acceptance surface ownership**:
The Rust core owns the complete numerical and semantic acceptance corpus. Python and CLI adapters own exhaustive interface shapes, options, defaults, mappings, exception and exit categories, and public workflows plus a representative end-to-end semantic spine; release artifacts additionally pass clean-host installation and execution journeys.
_Avoid_: Repeating the full numerical matrix per interface, adapter-only semantic authority

**PR acceptance spine**:
The complete set of cheap, deterministic, environment-independent contract checks, including exhaustive atomic kernel semantics, every cheaply constructible stable state and validation failure, atomic failure with prior-state preservation and object reusability, and small end-to-end representatives for each public workflow. It is always part of the `PR` acceptance workload tier rather than a smoke-test sample.
_Avoid_: Smoke-only PR gate, change-selected correctness subset

**Extended acceptance matrix**:
The deterministic, repeatable integration and differential corpus that applies constrained pairwise coverage and mandatory high-risk interactions across every operation shape and public workflow at small-to-moderate scale. It includes the accepted legacy artifact matrix but excludes solver stress, fuzzing, performance judgment, and large-scale resource evidence.
_Avoid_: PR smoke suite, nightly stress suite, Cartesian integration matrix

**Nightly acceptance stress**:
The cumulative scheduled corpus for medium-to-large solver stress, conditioning sweeps, complex geometry, property and metamorphic exploration, bounded fuzzing, concurrency determinism, operational-failure checks, and repeated numerical and resource trends through each scenario's declared scale ceiling, normally 100k but 10k for quadratic-pair kriging workloads. Trend collection does not itself define the final release thresholds.
_Avoid_: Deterministic integration matrix, million-scale hard gate, uncalibrated release judgment

**Release-blocking evidence**:
The immutable, content-addressed, pre-registered evidence closure required for publication, including every lower acceptance workload tier, tier-one clean-host journeys, the complete million-scale fit and evaluation gate, paired performance evidence, and identity, dataset, numerical, convergence, resource, packaging, and supply-chain records. Missing required evidence is a failed gate even before calibrated thresholds are applied.
_Avoid_: Best-effort release run, post-release evidence, unregistered benchmark

**Acceptance boundary triplet**:
The three-sided workload around a numerical or geometric decision boundary: a difficult valid case that must certify success, an uncertain or mathematically degenerate case that must return its defined indeterminate category, and an invalid-side case that must fail validation. Exact thresholds belong to the operation's numerical acceptance standard.
_Avoid_: Happy-path/invalid pair, epsilon guessing, boundary waiver

**Evaluation batch equivalence**:
One atomic evaluation batch and any ordered partition of the same targets, reassembled in original order, agree within requested accuracy while preserving duplicates and source coincidences. Success shapes include empty, singleton, and many-target batches; failure remains atomic and names the same first original target index regardless of internal chunking.
_Avoid_: Chunk-size semantics, reordered targets, partial batch result

**Acceptance execution lane**:
An orthogonal execution of one semantic workload under a declared platform, backend, thread, affinity, and cache profile; it does not create a second workload identity. The canonical single-thread lane reaches 100k, while million-scale release journeys use a fixed physical-core throughput lane and always record configured, effective, and maximum live threads.
_Avoid_: Duplicated semantic scenario, cross-host performance ratio, implicit thread count

**Acceptance scenario**:
A stable semantic workload identity that declares its minimum tier, covered contract, operation and data shape, expected outcome, oracle authority, content-addressed fixture, required evidence, and readiness. Execution lanes and later numerical or resource thresholds attach to this identity without redefining it.
_Avoid_: CI job, test-function name, backend-specific benchmark

**Paired measurement plan**:
An immutable binding of one acceptance scenario and content-addressed fixture to one acceptance execution lane, the Polatory baseline, and one RapidRBF candidate, with every comparison pair, subject order, and required evidence channel declared before collection. Changing the lane, candidate, order, or evidence obligations creates a new plan without changing the scenario identity.
_Avoid_: Acceptance scenario, mutable benchmark configuration, post-hoc run selection

**Measurement lifecycle profile**:
The declared reuse condition of a paired measurement plan: `Fresh process` means a new subject process and isolated scratch without claiming a cold operating-system page cache; `Declared warm-up` adds a recorded untimed precondition for each subject; and `Prepared reuse` separates preparation from ordered measured applications while retaining resource evidence through cleanup.
_Avoid_: Cold-cache run, implicit warm state, backend-state guess

**Paired measurement evidence**:
The complete, content-addressed, integrity-audited record of a paired measurement plan, with every planned Polatory/RapidRBF observation and every required semantic and resource channel accounted for. Without the relevant separately versioned threshold sets, its disposition is `COLLECTED, UNJUDGED`, which asserts neither numerical compatibility nor performance parity.
_Avoid_: Benchmark result, provisional pass, partial run log

**Acceptance readiness**:
The evidence state of an acceptance scenario, independent of its tier: `accepted-ready` has executable content-addressed authority, `source-only` records non-executable surface facts, `research-only` is diagnostic without acceptance authority, and `missing` identifies required evidence not yet built. Every required release scenario must be `accepted-ready` before publication.
_Avoid_: Passing by omission, tier downgrade, diagnostic oracle authority

**Acceptance corpus**:
The immutable, versioned set of acceptance scenarios and their materialized content-addressed fixtures, including generator and build identity rather than a seed alone. A semantic input, expected-outcome, or oracle-authority change creates a new scenario version; thresholds and adjudicated compatibility changes attach as separately reviewed records.
_Avoid_: Mutable golden data, seed-only fixture, in-place benchmark rewrite

**Numerical acceptance profile**:
The named, versioned set of operation-, channel-, metric-, and scenario-specific correctness thresholds, escalation rules, and evidence requirements applied unchanged across cumulative acceptance workload tiers. A tier changes coverage, scale, execution lanes, and evidence closure, never the semantic pass/fail rule of the same scenario.
_Avoid_: Global epsilon, tier-specific correctness, release-only tolerance

**Acceptance metric role**:
The non-substitutable purpose of a numerical acceptance metric: exact comparison owns discrete semantics, absolute infinity norm owns public accuracy and fit residuals, componentwise absolute-plus-relative comparison owns floating reference agreement, and scale-normalized metrics own dimensionless certificates. ULP, RMS, and L2 measurements are diagnostic and cannot mask a failed primary metric.
_Avoid_: Metric voting, RMS-only success, ULP compatibility, aggregate-error waiver

**Acceptance threshold calibration**:
The independent, content-addressed process that freezes each numerical acceptance profile threshold before candidate acceptance as the smallest power of two covering the sound error bound, four times calibration error, and eight times oracle uncertainty without exceeding its hard ceiling. Holdout or candidate results cannot widen a threshold, and any later change creates a new profile version.
_Avoid_: Candidate-tuned tolerance, mutable threshold, inherited test epsilon

**Reference error scale**:
The candidate-independent local magnitude formed from the high-precision absolute sum of the canonical mathematical contributions to one compared output component, or a sound upper bound on that sum. It scales only the absolute term of floating reference agreement; exact-zero semantics and public unscaled requested accuracy remain separate.
_Avoid_: Candidate-derived scale, batch-global maximum, reference magnitude alone, post-hoc normalization

**Intentional compatibility change**:
A documented RapidRBF behavior that deliberately differs from Polatory because the legacy behavior is mathematically undefined, structurally invalid, unsafe, or a proven defect. Where applicable, RapidRBF provides a stable error category and migration guidance rather than preserving the legacy outcome.
_Avoid_: Behavior drift, accidental incompatibility, silent fix

**Intentional difference adjudication**:
The immutable, content-addressed lifecycle record that retains frozen Polatory evidence while an accepted independent mathematical, structural, safety, or reproduced-defect adjudication supersedes only its acceptance authority for one narrowly scoped, versioned compatibility change. It binds evidence readiness, oracle authority, the required RapidRBF outcome, unchanged acceptance profiles, migration guidance, and human approval; every non-accepted record remains non-authoritative and no numerical correctness waiver exists.
_Avoid_: Candidate-as-oracle, tolerance waiver, expected failure, blanket exception, silent incompatibility

**Self-contained distribution**:
An official RapidRBF package that requires no separately installed compiler toolchain or native numerical dependency from its user, even when its internals include a native backend.
_Avoid_: Source-only release, system dependency

**Tier-one platform**:
A supported operating-system and architecture pair whose canonical release build must pass the million-scale correctness, convergence, and absolute-resource journey once through the core release harness, while each library, CLI, and Python artifact passes its own clean-host installation and public-workflow gates without repeating the core numerical corpus. The tier-one set is Windows x86_64, Linux x86_64 with glibc, macOS arm64, and macOS x86_64; performance parity is measured only on separately designated same-host Polatory/RapidRBF pairs, never by cross-platform ratios.
_Avoid_: Best-effort platform, build-only target

**Million-scale workload**:
The release-blocking set contains two 3D model/data journeys with at least one million supplied fit-point rows and one million independent evaluation targets: the frozen-ladder value-only `exp(psill=1, range=0.02)` model with identity anisotropy, degree zero, and zero nugget, and a Hermite-safe `th3(c>0) + gau` composite with distinct valid full anisotropy including shear, `AUTO` degree, non-zero nugget, 75% value rows, and 25% full-gradient rows. The first journey runs separate ordinary and incremental fits with full-data certification and million-target value evaluation, while the second runs ordinary fit and million-target value-plus-gradient evaluation; all variants advance through content-addressed lower rungs and retain scalar-equation count, accuracy, convergence, peak-memory, scratch, and thread evidence on every tier-one platform, with paired Polatory performance required only on designated same-host lanes.
_Avoid_: Scalability demo, aspirational benchmark, prediction-only million case

**Numerical compatibility**:
Agreement with Polatory's mathematical conventions and observable numerical outcomes under explicitly defined error, residual, and convergence tolerances. It does not require bitwise-identical results, identical coefficients, or identical solver and optimizer trajectories.
_Avoid_: Bitwise compatibility, visually similar output

**Semantic numerical determinism**:
The requirement that every non-operational execution lane of the same acceptance scenario has identical discrete semantic results and independently passes the same oracle, while continuous two-sided results remain within the sum of their certified error envelopes. Agreement among candidates, averaging, or selection of a favorable run cannot replace an oracle pass, and internal solver, optimizer, or mesh identities remain non-contractual.
_Avoid_: Bitwise reproducibility, majority-vote correctness, best-run selection, trajectory determinism

**Fit success**:
A fitted interpolant state whose full value and gradient observation residuals, recomputed from the candidate outside the solver's internal convergence estimate, are finite and within their configured absolute infinity-norm tolerances. Sampling may guide computation but cannot establish fit success.
_Avoid_: Solver convergence, sampled convergence, internal residual success

**Certified convergence**:
An operation reports numerical convergence only after its complete external result certificate passes within its declared iteration and work budgets. Recurrence residuals, optimizer stop criteria, restart trajectories, and Polatory outcomes are diagnostic triggers rather than proof; exhausting a budget without a certificate is non-convergence unless a more specific proven failure applies.
_Avoid_: Solver-declared convergence, recurrence-residual success, Polatory-success proxy, hidden extra iterations

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

**Matrix-kernel action**:
One canonical RBF contribution mapping value or full-gradient source weights to value or full-gradient targets as value `A`, source-gradient `F`, target-gradient `F^T`, or Hessian `H`, with derivative signs, component order, and self-interaction semantics fixed by the numerical contract. It excludes nugget, polynomial blocks, and solver behavior.
_Avoid_: Backend kernel, arbitrary channel map, complete interpolation operator

**Large-smooth adapter**:
A private matrix-kernel adapter that may evaluate infinite-support smooth contributions and spheroidal smooth tails at accepted large scales only after semantic coverage, sound call-scoped certification, prepared-lifetime, operational-control, scale, and tier-one distribution gates all pass. Before then it is a qualification target rather than an `Auto` route.
_Avoid_: Prototype-selected backend, sampling-certified backend, quadratic direct fallback

**Acceleration routing profile**:
A named, versioned, build-specific internal decision table that deterministically selects among canonical direct, exact compact-neighbor, and eligible large-smooth routes from the kernel form, matrix-kernel action, geometry, work size, neighborhood occupancy, preparation shape, requested accuracy, and resource grant. Its calibrated crossover values are diagnostic rather than public compatibility semantics.
_Avoid_: Global pair-count cutoff, public backend selector, unversioned routing heuristic

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

**Canonical direct reference**:
The deterministic full pairwise evaluation of a canonical matrix-kernel action used as the zero backend-approximation reference for requested accuracy. It is a floating-point reference governed by the operation-level numerical acceptance standard, not a claim of exact real arithmetic.
_Avoid_: Sampled fast estimate, backend trajectory, exact-real oracle

**Direct accumulation certificate**:
A per-output sound error bound that composes interval bounds for every weighted canonical kernel contribution with deterministic reduction, polynomial, and nugget roundoff. It keeps direct-reference error separate from backend approximation and solver residual rather than replacing them with one matrix epsilon.
_Avoid_: Flat matrix epsilon, sampled accumulation proof, merged error budget

**Kernel approximation certificate**:
A call-scoped sound upper bound on the absolute infinity-norm error of a complete requested value or gradient batch against the canonical direct reference, including adapter approximation and matrix-kernel transformation, composition, and accumulation error. Sampling may select a route or tune it but cannot alone certify success.
_Avoid_: Sampled calibration result, backend convergence flag, per-point spot check

**Default accuracy profile**:
The public, named, and versioned absolute infinity-norm error envelope used when requested accuracy is `Any`; `rapidrbf-default-v1` derives its effective value and gradient ceilings before execution from sound reference error scales and direct accumulation certificates. A backend must certify that envelope or refine, fall back, or fail, while fit, KKT, and geometry operations derive concrete internal budgets from their outer tolerances instead.
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

**Certified variogram-fit convergence**:
An in-domain variogram-fit candidate whose independently recomputed projected first-order KKT residual passes the numerical acceptance profile in normalized positive, zero-boundary, and rotation-manifold coordinates. Optimizer termination, cost or step stagnation, and iteration exhaustion are diagnostic and cannot establish convergence.
_Avoid_: Optimizer-declared convergence, stagnation success, iteration-limit success, unchecked terminal candidate

**Variogram-fit output equivalence**:
Agreement between a certified fitted model and its independent reference in modeled semivariances, one-sided canonical objective regret, and preregistered held-out predictions under the numerical acceptance profile. A lower objective cannot waive an output or prediction discrepancy, while parameter values, optimizer trajectories, and trial membership are not compatibility targets.
_Avoid_: Parameter-vector equality, objective-only equivalence, training-selected holdout, lower-cost waiver

**Usable variogram-fit candidate**:
A covariance model with certified variogram-fit convergence whose objective and every weight are independently recomputable and finite. Trial-local invalidity is diagnostic and does not abort other starts, while a non-converged terminal iterate or an operation interrupted by cancellation, deadline, or resource failure is never returned as best-so-far.
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
The channel-specific additive ledger that assigns every evaluator, oracle, reduction, and rounding uncertainty exactly once before requiring the worst-case sum plus any independently measured residual to remain within the public operation tolerance. An uncertainty already enclosed by an outward interval is not charged again, while a point estimate must expose every omitted uncertainty explicitly; value, gradient, and geometry channels cannot borrow from one another.
_Avoid_: Double-counted interval radius, omitted point-estimate error, root-sum-square budgeting, cross-channel borrowing

**Atomic evaluation batch**:
An order-preserving value-only or value-and-gradient request that returns a complete finite result within requested accuracy or fails as a whole with the first failing target index and stable cause. Failure never emits partial arrays or mutates certified interpolant state.
_Avoid_: NaN-padded output, partial batch success, unordered failure diagnostics

**First-survivor distance filter**:
A greedy point-cloud reduction that processes candidates in caller-supplied order, retains each first unsuppressed candidate, and removes later candidates whose exact Euclidean distance is strictly less than a finite positive radius; empty input yields empty output. Survivors preserve candidate order, points exactly at the radius both survive, and boundary membership is independent of neighbor-search traversal and backend rounding.
_Avoid_: Order-independent deduplication, canonical point subset, nearest-neighbor clustering, tolerance-band radius, FLANN minimum radius

**Valid distance-filter request**:
A finite `n x dim` point table with `dim` in `{1,2,3}`, finite positive radius, and optional ordered row-index sequence. An omitted sequence means every row in original order, an empty sequence is valid, and repeated indices are ordinary repeated candidates whose later occurrences are suppressed at zero distance; an out-of-range index atomically rejects the request with its candidate position and value, without emitting partial survivors.
_Avoid_: Unchecked candidate index, duplicate-index rejection, partial filtered result

**Plane factor**:
For centered-neighborhood singular values `s0 >= s1 >= s2` and `n` points, define `e0=max(hypot(s0,s1,s2)/sqrt(n),1e-10)`, `e1=max(hypot(s1,s2)/sqrt(n),1e-10*e0)`, and `e2=max(abs(s2)/sqrt(n),1e-10*e1)`; the plane factor is `e1^2/(e2*e0)`. It is a public planarity measure compared numerically rather than bitwise.
_Avoid_: Backend-specific SVD score, curvature score, undocumented quality heuristic, fuzzy factor threshold

**Multiscale normal estimate**:
The unit, unoriented least-variance normal and plane factor selected independently at each point by maximizing plane factor over one caller-supplied candidate-scale list shared by every point; an exact factor tie selects the largest scale, and threshold filtering retains equality. Candidate scales are not per-point arrays, and the PCA/SVD backend and raw singular-vector sign are not part of compatibility.
_Avoid_: Per-point scale array, first successful scale, backend eigenvector sign

**Deterministic normal neighborhood**:
A `k`-nearest normal-estimation neighborhood contains its query row and then selects up to `k-1` other rows by exact Euclidean distance with original-row-index ties; a radius neighborhood contains every row at exact distance less than or equal to the radius. Both use stable `(distance, original row index)` order and backend-independent boundary adjudication.
_Avoid_: Self-omitting neighborhood, open radius ball, backend neighbor order, unstable equidistant tie

**Normal estimate state**:
The per-input-row result is `Estimated` with a unit normal, plane factor, and selected scale; `UnresolvedNormal` without a selected scale or plane factor when no candidate containing at least three points has a certified unique least-variance direction or when the multiscale winner, threshold boundary, or eigengap cannot be certified within the row-local numerical budget; `RejectedNormal` with its selected scale and plane factor but no usable normal after plane-factor filtering; or `AmbiguousOrientation`, which retains the selected scale, plane factor, and normal axis only modulo sign but exposes no usable oriented vector. Invalid local candidates are skipped, global validation failures remain atomic, and zero-vector missing markers exist only at migration adapters.
_Avoid_: Arbitrary degenerate normal, core zero-normal sentinel, whole-batch failure for local insufficiency

**Directed normal orientation**:
An estimated normal oriented toward a finite non-zero direction `d` has a certified strictly positive `n dot d`; orientation toward a finite target point uses `d=target-point`. A zero direction or a dot-product sign that cannot be certified produces the per-row state `AmbiguousOrientation` rather than exposing the backend's unoriented PCA sign.
_Avoid_: Non-negative orientation test, preserved SVD sign at orthogonality, arbitrary coincident-target orientation

**Closed-surface normal orientation**:
The per-component assignment of normal signs on a deterministic union-`k`-nearest graph over only `Estimated` rows: each row's neighborhood includes itself, uses the deterministic normal-neighborhood cutoff rule, and is clamped to the available estimated rows; an undirected edge exists when either endpoint selects the other. Every orientation edge must have a certified non-zero endpoint-normal dot-product sign, and the resulting signs make every edge positive before a component flip makes its canonical `(z,y,x,original-index)` maximum anchor point toward positive z. `RejectedNormal` and `UnresolvedNormal` rows remain outside the graph with their existing states; one uncertifiable edge sign, contradictory sign constraints, or an uncertifiable anchor makes every row in the affected union-graph component `AmbiguousOrientation`, while graph traversal and queue order are not compatibility behavior.
_Avoid_: Priority-queue replay, whole-cloud sign flip, backend-dependent component anchor

**Valid normal-estimation request**:
A request over finite 3D point rows with a non-empty caller list of integer estimation scales `k >= 3` or finite positive radius scales, an optional finite plane-factor threshold, and an optional orientation mode `None`, `TowardDirection`, `TowardPoint`, or `Closed(k)`, where only `Closed` requires integer `k >= 2`. The estimation list is canonicalized by numeric ascending sort and duplicate collapse; only integer estimation scales above the available row count use all applicable rows, while radius values are never clamped. Without filtering no row becomes `RejectedNormal`; `None` preserves an unoriented `Estimated` normal axis that is not usable for SDF generation. Empty input is valid, duplicate coordinates remain distinct rows, and any request-level failure leaves prior estimator state unchanged.
_Avoid_: FLANN radius domain, per-row scale list, duplicate-coordinate merge, partially replaced estimate

**Certified normal estimate**:
A per-row normal result whose discrete state, deterministic neighborhood, and selected scale agree exactly with the canonical high-precision centered-PCA reference; an estimate additionally passes finite unit length, PCA residual and least-direction optimality, plane-factor error, and sign-invariant or sign-aware angular checks under the numerical acceptance profile. A row-local winner, threshold, or eigengap that remains uncertifiable yields `UnresolvedNormal`, while an orientation sign that remains uncertifiable yields `AmbiguousOrientation`; the concrete residual, factor, eigengap, and angular ceilings belong to the numerical acceptance standard, while backend decomposition and floating-point bits are irrelevant.
_Avoid_: Angle-only normal acceptance, backend SVD replay, tolerance-masked degeneracy

**Provided oriented normal**:
A finite non-zero normal direction supplied with an explicit caller assertion that its sign has the intended surface orientation. It is a trusted logical input rather than a RapidRBF normal-estimation certificate, remains associated with its source row, and is normalized under the metric-normalized SDF rule; a zero or non-finite provided vector invalidates the request rather than representing absence.
_Avoid_: Forged Estimated provenance, implicit orientation claim, zero-vector missing marker

**Usable oriented normal**:
A RapidRBF `Estimated` unit normal whose requested direction, point-target, or closed-surface sign has been certified without ambiguity, or a `ProvidedOrientedNormal` carrying the caller's explicit sign assertion. `RejectedNormal`, `UnresolvedNormal`, and `AmbiguousOrientation` rows are unavailable to SDF offset generation but retain their own diagnostic state.
_Avoid_: Zero-marker normal, unoriented PCA sign, rejected normal used for offset

**Signed-distance sample set**:
A sparse set keyed by `(source row, side)` rather than a continuous field: every source has one unchanged zero-valued `Surface` sample, and every selected usable oriented normal additionally has one `Negative` and one `Positive` sample. Membership and association are exact, while array and table adapters order all surfaces first, then negative and positive samples, with original source-row order inside each block.
_Avoid_: Full signed-distance field, geometry-only comparison, unassociated offset rows

**Metric-normalized SDF normal**:
A finite non-zero physical normal used only as a direction: under a valid anisotropy transformation `A`, `A^-T n` is robustly normalized and offsets are taken along that transformed-space unit direction, including when `A` is identity. Exact zero denotes an unavailable normal only at array migration adapters; no hidden near-zero threshold changes sample membership.
_Avoid_: Magnitude-bearing normal, identity-only unnormalized offset, Eigen zero tolerance

**Certified SDF offset**:
For source `p`, let `y=A*p`, `u=normalize(A^-T*n)`, and side `s` be `-1` or `+1`. For every other unique request source `p_j` with `s*u dot (A*p_j-y) > 0`, its transformed-space Voronoi-boundary distance on that ray is `b_j=norm(A*p_j-y)^2/(2*s*u dot (A*p_j-y))`; let `b_s` be their minimum, or infinity when none exists. For a finite positive cap `D` and configured clearance ratio `rho` with `0 < rho < 1`, use `d_s=min(D,rho*b_s)` for finite `b_s` and `d_s=D` otherwise, emitting `q_s=p+A^-1(s*d_s*u)` with value `v_s=s*d_s`. All sources participate in clearance regardless of normal usability or subsample membership; legacy neighbor-adjustment loops and trajectories are not compatibility behavior.
_Avoid_: Mandatory fixed displacement, unchecked offset, six-neighbor adjustment replay

**Automatic SDF offset**:
A structural offset policy whose per-source cap is the maximum transformed distance in its deterministic `min(6,n)` neighborhood over every unique request source, including itself and then other rows by `(norm(A*(p_j-p)), original row index)`, followed independently on each side by certified SDF offset selection. A source without a positive local scale has `UnresolvedOffset`; numeric zero may map to `Auto` only at migration adapters, while negative offsets are invalid.
_Avoid_: Core numeric AUTO sentinel, negative AUTO spelling, coincident zero-distance offset

**Unique SDF source**:
A signed-zero-normalized source coordinate that occurs in exactly one input row of a signed-distance sample request. Exact coordinate duplicates make the request atomically invalid with both row identities rather than being merged or assigned arbitrary Voronoi ownership; distinct near-neighbors remain valid.
_Avoid_: Duplicate-source tie-break, silent source merge, legacy pathological adjustment

**Valid SDF request**:
A finite `n x 3` source table paired row-for-row with `n` RapidRBF normal-result states or explicitly asserted provided oriented normals, a valid anisotropy transformation, a structural `Auto` policy or finite positive explicit offset cap, a configured clearance ratio strictly between zero and one, a finite subsample ratio in `[0,1]`, and an explicit unsigned 64-bit seed. Source coordinates are unique after signed-zero normalization; empty input is valid, produces an empty sample set, and does not require a positive automatic scale. Validation failure is atomic and identifies stable offending rows or fields.
_Avoid_: Mismatched normal rows, numeric AUTO sentinel, implicit random seed, partial validation success

**Reproducible SDF subsample**:
The `round_half_up(ratio*m)` sources selected from the `m` usable oriented normals by ascending canonical priority, so ratios zero and one select none and all respectively. Version 1 priority is the full SHA-256 digest of the ASCII domain separator `RapidRBF/SDF-subsample/v1` followed by one zero byte, the explicit unsigned 64-bit seed in little-endian order, and the little-endian IEEE-754 binary64 bits of signed-zero-normalized `(x,y,z)`; digests are compared as unsigned-byte lexicographic sequences and a collision is ordered by unsigned lexicographic `(x_bits,y_bits,z_bits)`. Selection is invariant to source-row permutation and runtime scheduling; adapters expose the configured and effective seed while emitted samples retain source-row order.
_Avoid_: Standard-library shuffle, hidden seed, ratio over unavailable normals, selection-order output

**SDF source state**:
The per-source outcome is `Generated`, which atomically contributes both offset sides; `NormalUnavailable`; `NotSelected`; or `UnresolvedOffset`, while every source in a valid request retains its zero-valued surface sample. Request validation, cancellation, resource, or accuracy failure is atomic and leaves prior generated state unchanged.
_Avoid_: One-sided offset, partial failure table, overwritten prior result

**Point-cloud operation result**:
A valid distance filter returns its complete ordered survivor sequence, normal processing returns one state for every input row, and SDF generation returns one source state plus its complete logical sample set for every input row. Row-local geometric or numerical ambiguity is represented only by `UnresolvedNormal`, `RejectedNormal`, `AmbiguousOrientation`, `NormalUnavailable`, `NotSelected`, or `UnresolvedOffset`; it does not discard other rows. Global outcomes use the precedence `InvalidRequest`, systemic `AccuracyUnattainable`, `ResourceExhausted`, `Cancelled`, then `DeadlineExceeded`, and any such failure is atomic with no partial survivor list, row-state vector, or sample set.
_Avoid_: Local ambiguity as batch failure, partial global failure payload, traversal-dependent failure

**Certified field contract**:
A runtime field capability that supplies finite point values and gradients with accuracy bounds and can supply sound interval enclosures, including evaluator error, for values and gradients over adaptively queried bbox cells, or certified derivative bounds from which RapidRBF can derive those enclosures. Only this evidence can justify a certified surface state or complete component claim; a point-sampling-only callback yields `TopologyUnresolved`, and any separately exposed unchecked extraction is outside certified isosurface equivalence.
_Avoid_: Sampling-as-proof, test-oracle-only guarantee, unchecked mesh labeled certified

**Certified surface state**:
The exact bbox-local result is `Surface` for a certified regular two-dimensional level set, `Empty` when a certified lower bound is strictly above the isovalue everywhere, or `Entire` when a certified upper bound is strictly below everywhere, with interior defined by `field < isovalue`. Proven interior tangency, non-transverse contact with a bbox stratum, a field proven identically equal to the isovalue throughout a non-empty cell, or lower-dimensional contact produces `DegenerateLevelSet`; insufficient evidence to decide regularity or global classification produces `TopologyUnresolved`, never a sampled sentinel guess.
_Avoid_: Single-sample Empty/Entire, zero-is-positive shortcut, unclassified no-face mesh

**Topology-resolved surface**:
A certified underlying regular level set relative to the bbox stratification whose connected components, orientability, embedded topology, per-component Euler characteristic and genus, transverse bbox boundary loops, and boundary incidence are determined exactly. An uncertifiable bbox tangency, sub-resolution feature, component completeness, or near-critical ambiguity must refine or return `TopologyUnresolved`; discrete output-mesh defects belong only to certified mesh validity and its failure states, and geometric proximity alone cannot excuse different topology.
_Avoid_: Defect-free-only acceptance, face-count topology, Hausdorff-only equivalence

**Oriented isosurface**:
A topology-resolved surface whose unsnapped face winding points from `field < isovalue` toward `field > isovalue`, equivalently satisfying a certified positive face-normal/field-gradient dot product at regular points; snapped regions inherit that orientation through their certified orientation-preserving deformation, and bbox boundaries inherit the induced orientation. Cyclic face rotation is equivalent, face reversal and whole-surface reversal are not, and a 2.5D `z-h(x,y)` surface points toward positive z.
_Avoid_: Unoriented triangle soup, global-reversal equivalence, vertex-order polarity

**Certified base surface**:
Every successful `Surface` result before optional snapping is a certified mesh-valid, topology-resolved oriented mesh ambient-isotopic to the requested union of underlying regular bbox-local level-set components relative to the bbox stratification, with certified anisotropic triangle-surface position, normalized field-residual, transformed-normal, bbox-containment, and clipping-boundary errors. All-lattice mode requests every underlying bbox component and returns `TopologyUnresolved` rather than omitting one; seeded mode requests only the complete components certified for its seeds. This guarantee applies with refinement disabled as well as enabled; refinement strategy and tessellation remain internal.
_Avoid_: Uncertified coarse success, refine-only correctness, sample-point residual

**Surface accuracy profile**:
A versioned set of numerical bounds and certification budgets used by base, equivalent, refined, seeded, snapped, 2.5D, and mesh-validity results. Position uses transformed distance `norm(A*(x-y))`, physical normals compare as normalized `A^-T*n`, and normalized field residual is `(abs(f_hat-isovalue)+value_error)/certified_lower_bound(norm(A^-T*grad(f)))` over full triangle surfaces; inability to certify a positive denominator is `TopologyUnresolved`. Seed capture uses an inclusive finite positive profile factor times resolution, while continuous coordinate guards never establish discrete bbox incidence. The v1 factors, angular ceilings, robust-predicate escalation, and work budgets belong to the numerical acceptance standard rather than mesh implementation identity.
_Avoid_: Bbox-relative visual tolerance, unversioned hidden epsilon, implementation-iteration budget

**Surface proof certificate**:
The independently verifiable, bounded evidence that every continuous field claim is supported by sound interval enclosures and every finite-coordinate topology or mesh claim resolves to an exact sign or identity under the surface accuracy profile. Its budget measures canonical certificate leaves and clauses rather than extraction or refinement iterations; exhaustion yields the owning unresolved result and never partial success.
_Avoid_: Sampled topology proof, epsilon predicate, iteration-budget certificate, successful mesh as proof

**Geometrically equivalent isosurface**:
Topology-resolved oriented surfaces ambient-isotopic to the same requested underlying level-set component union relative to the bbox stratification, inducing a component bijection that preserves interior/exterior orientation, embedded topology, per-component Euler characteristic and genus, and bbox-boundary-loop incidence, followed by componentwise certified anisotropic symmetric triangle-surface Hausdorff distance, normalized level-set positional residual outside snapped regions, transformed-space oriented-normal angle, and finite physical-bbox containment and clipping-boundary criteria under the same surface accuracy profile. Vertex samples alone, bbox-relative visual similarity, or any one metric cannot establish equivalence.
_Avoid_: Vertex-only distance, residual-only acceptance, visual equivalence, topology-blind tolerance

**2.5D surface**:
A topology-resolved oriented single-valued height field `z=h(x,y)` extracted from `field=z-h(x,y)` at isovalue zero, possibly clipped into several bbox components but never containing an overhang or projected self-intersection. Refinement preserves the graph property; snapping belongs to the general 3D isosurface workflow and forfeits this guarantee.
_Avoid_: Snapped height field, overhanging 2.5D mesh, arbitrary 3D level set

**Certified seed tracking**:
An order-independent non-empty set of finite in-bbox seeds, each of which must certify exactly one regular level-set component within the surface accuracy profile's inclusive capture radius; a non-finite or outside-bbox seed invalidates the request rather than being clamped. The result is the deduplicated union of those complete underlying components and is geometrically equivalent to those components in all-lattice mode. A seed certified to match zero or multiple components atomically fails a `Surface` request as `SeedUnmatched` or `SeedAmbiguous` with its original index, while inability to decide the match is `TopologyUnresolved`; a globally certified `Empty` or `Entire` field returns that state with `NoSurfaceInDomain` seed statuses.
_Avoid_: Clamped seed, silent tracking miss, partial component, first-seed sentinel

**Seed tracking status**:
The per-original-seed success status is `Selected` and associated with a result component for a certified `Surface`, or `NoSurfaceInDomain` for a certified `Empty` or `Entire` field. Cross-implementation association is compared through the geometric-equivalence component bijection rather than a shared numeric component identifier. An unmatched or multiply matching seed is instead the indexed atomic operation failure `SeedUnmatched` or `SeedAmbiguous`; duplicate seeds selecting the same component retain separate statuses.
_Avoid_: Silent seed drop, traversal-order component number, partial seed success

**Certified surface refinement**:
An enabled refinement whose final mesh satisfies the requested mode's surface accuracy profile, and for 2.5D also its single-valued injective projection certificate. Candidate vertices, accepted or rejected steps, local remeshing, and projection methods are internal. Earlier field, topology, or mesh-validity causes retain their specific failure; `RefinementFailed` means only that an otherwise valid base problem cannot meet refinement-specific geometry or graph targets within its certified budget.
_Avoid_: Single-step refinement promise, silent rejected move, partially refined success

**Certified mesh snapping**:
A per-input-point constraint whose active or out-of-range classification is certified against the requested canonical underlying component union, not a candidate tessellation. Before its unsnapped base surface `M0` is frozen, every active target must also be certified within one anisotropic resolution of `M0`; the final mesh must meet each finite relative tolerance times resolution, with a zero-tolerance point as an exact mesh vertex.
_Avoid_: Best-effort snap, silent dishonored point, winner-only contention, iteration-limit success

**Canonical snap constraints**:
The order-independent candidate set derived from finite snap locations with finite relative tolerances in `[0,1]`, defaulting to zero: an outside-bbox location is diagnostic only, and an in-bbox location becomes active exactly when its certified distance to the requested underlying component union is within the inclusive capture radius. Signed-zero-normalized duplicates coalesce at their minimum tolerance while retaining every original index; near-but-distinct points never merge, and an active target without a certified local `M0` anchor is incomplete rather than silently reclassified.
_Avoid_: Input-order winner, duplicate snap vertices, implicit positive tolerance, near-point merge

**Snap point status**:
For a certified `Surface`, the per-original-point success status is `OutsideDomain` for a finite point outside the bbox, `OutOfRange` for an in-bbox point beyond the underlying-union capture radius, or `Satisfied` for every active constraint, including one already satisfied before deformation. For certified `Empty` or `Entire`, outside-bbox points remain `OutsideDomain` and in-bbox points are `NoSurfaceInDomain`; unresolved distance or local-anchor evidence is `SnapIncomplete`, while only proven joint infeasibility is `SnapConflict`.
_Avoid_: Winner-only status, already-satisfied ambiguity, partial snap success

**Certified snapped surface**:
An orientation-preserving ambient-isotopic deformation `M1` of a certified unsnapped surface `M0`, relative to the bbox stratification and preserving its boundary incidence, whose anisotropic symmetric Hausdorff distance from `M0` is at most one resolution. Outside the transformed one-resolution neighborhoods of active in-bbox snap targets it retains the level-set certificate; inside, snap constraints replace field residuals but the surface accuracy profile's normal-deviation bound plus topology, bbox, and mesh-validity certificates still apply. Diagnostic outside-domain and out-of-range points never relax the field certificate.
_Avoid_: Unbounded snap deformation, topology-changing snap, globally relaxed level-set residual

**Certified mesh validity**:
A robustly certified finite indexed triangle surface with no unreferenced vertices, invalid indices, zero-area or duplicate/oppositely duplicated faces, non-manifold edge or vertex links, inconsistent winding, T-junctions, non-adjacent contact or intersection, or coplanar overlap beyond an adjacent pair's declared shared vertex or edge. Every boundary primitive is single-sided, uses the canonical bbox endpoint coordinate on its declared stratum, and is exactly incident with that face, edge, or corner; a proven defect yields `MeshValidityFailed`, while an indeterminate predicate refines or yields `MeshValidityUnresolved`.
_Avoid_: Legacy-defect parity, boundary-singularity exception, floating-predicate guess, cluster-success certificate

**Certified mesh post-processing**:
Clustering, smoothing, thinning, local remeshing, and duplicate consolidation are internal tessellation transformations, not independently replayed compatibility algorithms. They may change vertex and face counts or positions only when the operation's final base or snapped surface, topology, orientation, bbox, and mesh-validity certificates still hold; otherwise the enclosing stage returns its defined atomic failure.
_Avoid_: Legacy cluster replay, mesh-hash equivalence, defect-finder-only acceptance

**Semantic geometry determinism**:
Exact agreement of normalized inputs, semantic surface or failure state, topology, orientation, seed and snap statuses, and other discrete membership across runs, thread counts, platforms, and backends, with continuous geometry compared by its certified tolerances. Externally induced `ResourceExhausted`, `Cancelled`, and `DeadlineExceeded` outcomes are operational rather than semantic determinism claims. Vertex and face counts, numbering, mesh row order, tessellation, floating-point bits, raw hashes, and OBJ bytes remain non-contractual even when exact same-backend snapshots are retained diagnostically.
_Avoid_: Byte determinism, combinatorial mesh identity, schedule-dependent topology

**Logical OBJ surface artifact**:
A locale-independent minimal export containing a block of finite `v` records followed by a block of one-based oriented triangular `f` records for a certified `Surface`, only `# empty` for `Empty`, or only `# entire` for `Entire`. The parsed-back mesh must satisfy the source result's same base or snapped, orientation, topology, bbox, mesh-validity, and exact zero-tolerance snap certificates, but numeric spelling, whitespace, line endings, ordering within each block, and equivalent vertex numbering are non-contractual; file output atomically replaces its target or returns `IoFailure` without damaging the prior file.
_Avoid_: Raw-byte OBJ compatibility, partial OBJ, sentinel mesh, implicit normals or materials

**Valid isosurface request**:
A request with a finite non-degenerate bbox, finite isovalue, finite positive transformed-space resolution, valid anisotropy transformation, and structurally valid all-lattice or seeded mode plus refinement and snap configuration. Field-provider execution, output shape and finiteness, and accuracy evidence are runtime operation results rather than request validity; successful all-lattice mode covers every underlying bbox level-set component or returns `TopologyUnresolved`, and successful seeded mode covers exactly its certified selections. Every validation, callback, accuracy, topology, refinement, snapping, resource, cancellation, or deadline failure is atomic, preserves prior state, and leaves the generator reusable.
_Avoid_: Degenerate bbox, partial mesh success, poisoned generator, sampled-component all-lattice

**Surface operation result**:
Exactly one success state `Surface`, `Empty`, or `Entire`, or one atomic failure selected by the normative stage order: request validation (`InvalidRequest`); field execution and evidence (`FieldEvaluationFailed`, `InvalidFieldOutput`, `AccuracyUnattainable`); level-set classification and topology (`DegenerateLevelSet`, `TopologyUnresolved`); seeded selection (`SeedUnmatched`, `SeedAmbiguous`); refinement (`RefinementFailed`); snapping (`SnapConflict`, `SnapIncomplete`); and final mesh certification (`MeshValidityFailed`, `MeshValidityUnresolved`). Stages and alternatives inside each parenthesis use the written left-to-right precedence; provider errors are `FieldEvaluationFailed`, structurally wrong or non-finite replies are `InvalidFieldOutput`, and sound finite replies that cannot meet their requested enclosure are `AccuracyUnattainable`. An earlier specific cause propagates rather than being wrapped by a later stage; same-category indexed failures aggregate sorted original indices. `ResourceExhausted`, `Cancelled`, and `DeadlineExceeded` may terminate work operationally, while export alone adds `IoFailure`.
_Avoid_: Overlapping error categories, traversal-first index, partial success payload, cancellation-dependent semantic claim

**Legacy artifact**:
A model or fitted interpolant encoded by a supported legacy layout profile and accepted by RapidRBF only through a one-way migration path.
_Avoid_: RapidRBF format, portable model

**Legacy layout profile**:
A closed byte-level decoding contract for Polatory's unversioned native format, defined by field order, byte order, scalar encodings, native integer widths, boolean representation, and matrix storage. Producer platform and build are provenance; byte-identical layouts share a profile, and support requires accepted-ready fixtures.
_Avoid_: Platform-named format, guessed ABI, inferred legacy layout

**Legacy import declaration**:
The caller-supplied artifact kind, dimension, and legacy layout profile that together fix one interpretation of a legacy artifact. RapidRBF neither infers a declaration nor retries alternative declarations after a failed import.
_Avoid_: Format autodetection, fallback parsing, ambiguous legacy import

**Legacy import coverage**:
Every valid RapidRBF-compatible `Model` or fitted `Interpolant` logical state expressible by a supported legacy layout profile. Accepted-ready fixtures establish coverage evidence rather than forming a hash or shape whitelist.
_Avoid_: Fixture whitelist, known-file-only import, unfitted interpolant import

**Validated legacy interpolant**:
A fitted legacy artifact whose model, finite field state, canonical bbox, weight shape, Hermite eligibility, and CPD side condition have passed import validation. It may be evaluated, converted, or used as a compatible warm start, but it makes no historical fit-success claim because the original observations and tolerances are absent.
_Avoid_: Certified interpolation fit, trusted legacy coefficients, reconstructed fit evidence

**Legacy numeric preservation**:
The migration obligation to retain accepted finite model parameters, anisotropy, centers, and weights with their decoded binary64 values, except for explicit domain canonicalization. Exact imported state and numerical evaluation equivalence are both required; neither substitutes for the other.
_Avoid_: Refitted import, coefficient-tolerant migration, evaluation-only import

**Legacy import result**:
Exactly one validated `Model` or validated legacy interpolant, or one atomic failure selected in stage order: `InvalidRequest`, `UnsupportedLegacyLayout`, `IoFailure`, `MalformedLegacyArtifact`, `UnsupportedLegacyVariant`, then `InvalidLegacyState`. Operational termination uses `ResourceExhausted`, `Cancelled`, then `DeadlineExceeded`; failure never exposes partial state or poisons importer reuse.
_Avoid_: Partial legacy import, guessed hint mismatch, loader exception text

**Legacy import resource grant**:
The caller-resolved ceilings on input bytes, decoded memory, and element counts for one legacy import. A structurally possible artifact beyond the grant is retryable `ResourceExhausted`; an impossible or overflowing encoded size is `MalformedLegacyArtifact`.
_Avoid_: Unbounded native allocation, layout-encoded machine limit, corruption-by-size alone

**Legacy layout conversion route**:
The bounded source-side migration path for an artifact outside every supported legacy layout profile: decode it on its matching producer platform and ABI, preserve its validated logical state into a portable artifact, then revalidate that output in RapidRBF. It is not importer fallback, refitting, resampling, or a RapidRBF runtime dependency.
_Avoid_: Layout guessing, native-loader fallback, evaluation-based conversion

**Portable artifact**:
A versioned RapidRBF model or fitted interpolant representation with an explicit cross-platform compatibility contract.
_Avoid_: Native memory dump, legacy artifact

**Reference hierarchy**:
The order used to judge numerical discrepancies: explicit mathematical definitions and high-precision direct references first, Polatory's observable behavior second, and a RapidRBF candidate implementation third. Proven Polatory defects become documented intentional differences rather than compatibility requirements.
_Avoid_: Polatory is always correct, implementation-defined truth

**Oracle escalation**:
The mandatory promotion from ordinary floating-point evidence to analytic, higher-precision, interval, or exact-predicate adjudication whenever uncertainty crosses a semantic boundary or a Polatory difference may be a defect. When a full direct reference is infeasible at scale, only a sound full-batch error certificate plus the complete operation certificate can replace it; fixed audit samples validate that evidence but never prove success alone.
_Avoid_: Spot-check proof, boundary guess, sampled certificate, Polatory tie-break

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
