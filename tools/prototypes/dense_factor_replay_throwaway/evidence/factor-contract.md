# Prototype factor/fallback contract

Schemas:

- corpus lock: `rapidrbf-dense-factor-corpus-lock-v2`;
- semantic admission: `rapidrbf-factor-admission-v1`;
- private backend report: `rapidrbf-factor-attempt-v1`.

This contract normalizes observations. It does not make a crate's internal
factor object, status flag, or pivot threshold part of RapidRBF's public
compatibility surface.

The v2 lock binds its complete body: raw manifest and every referenced payload,
generator source/CMake/executable identities, and the registered native
artifact closure. The parent replay recomputes that identity and verifies every
file before workers start; each worker is bound to the parent digest and
rechecks the payloads for its own record.

## Semantic admission

1. The corpus record and every payload hash must match.
2. Dimensions and byte arithmetic must fit the declared resource grant.
3. The matrix and right-hand side must be finite.
4. The independently assembled full matrix must agree with the canonical
   symmetric payload where symmetry is required.
5. The interpolation layer supplies a hash-bound rank certificate. It uses the
   deterministically coordinate-scaled and row/column-equilibrated matrix,
   `tau_rank = max(m,n) * 2^-53`, and a certified singular-value-ratio
   interval. An interval wholly above the threshold passes; one wholly at or
   below fails. A straddle escalates through 256, 512, 1024, and 2048-bit
   references, whose final uncertainty must be at most `tau_rank/8`; otherwise
   admission is `IndeterminateRank`.

Any admission failure returns a structured status before a factor is
published. No fallback may reinterpret non-finite input, a malformed record,
or a semantically rank-invalid interpolation system.

A backend `info`, zero pivot, pivot magnitude, condition estimate, or solve
failure can only produce factor-health evidence such as `SingularPivot` or
`NumericalBreakdown`. It can never mint, replace, or widen the semantic rank
certificate.

## Private attempts and selection

Selection is defined by a versioned
`FactorHealthProfile { profile_id, profile_hash }`. The profile owns the
finite-output, reconstruction, reduced-residual, full-certificate, and
fallback thresholds. Stage 0 deliberately has no applicable profile. It
therefore runs all registered attempts side by side and reports
`COLLECTED, UNJUDGED`; it cannot name a selected route, a successful fallback,
or a production winner.

Every backend emits the same outer attempt report. The frozen Stage 0 routes
inside that report are:

1. `pivoted-lblt-audit` / native BK records status, available 1x1/2x2 pivot
   blocks, permutation,
   solve residual, factor bytes, and workspace high-water.
2. The faer-only `gated-llt` audit is selectable only when an independent, sound
   positive-definite certificate is bound before mutation and the factor/solve
   certificate passes. LLT/DPOTRF success is not that certificate. Without
   such authority Stage 0 records faer LLT as an audit attempt only. Native
   `DPOTRF/DPOTRS` and a nalgebra LLT audit are not materialized.
3. `explicit-partial-pivot-lu` is executed only after a hard symmetric
   factor/solve failure, from a fresh matrix, and the diagnostic reason is
   recorded. Without a `FactorHealthProfile` it is never described as a
   selected or successful production fallback.
4. A rank diagnostic may explain disagreement. It cannot repair rank, insert a
   nugget, reduce polynomial degree, drop constraints, or choose a
   minimum-norm solution.

Semantic admission states are:

- `EVIDENCE_MISSING` (Stage 0 certificate absent; diagnostic force-replay only)
- `NonFinite`
- `ResourceDenied`
- `RankDeficient`
- `IndeterminateRank`
- `Admitted`

Private factor-attempt states are:

- `Factored`
- `SingularPivot`
- `NumericalBreakdown`
- `NonFiniteOutput`
- `BackendUnavailable`
- `ContractViolation`

Every emitted attempt carries `schema=rapidrbf-factor-attempt-v1` and keeps
three axes separate:

- `collection_state` says whether the requested diagnostic observation exists;
- `factor_state.normalized` maps the backend observation to the states above;
- `semantic_admission` remains interpolation-owned and never derives from
  `info`, pivots, reconstruction, or a solve residual.

`attempt_state` remains only the backend-specific diagnostic observation. A
preflight non-finite rejection uses `NOT_RUN` for the factor because no backend
factorization was entered.

## External certificate

`Solved` is an interpolation-layer result, not a backend-attempt state. It
requires all of the following, computed outside the candidate factor:

- finite reduced solution;
- reduced normwise backward error
  `||B*x-b||_inf / (||B||_inf*||x||_inf + ||b||_inf)`, with `0/0 := 0`;
- finite reconstructed kernel correction `lambda = Q*x`;
- complete value and gradient augmented-equation residuals from the
  independently assembled `A`, `P`, actual right-hand side, `lambda`, and
  recovered polynomial coefficients;
- normalized CPD side condition
  `eta_CPD = ||P^T*lambda||_inf /
  (||P^T||_inf*||lambda||_inf)`, with `0/0 := 0`, and
  `eta_CPD + alpha_CPD <= 2^-32`;
- independently factored and certified coarse polynomial recovery; and
- no allocation, scratch, or thread escape from the declared prototype lane.

The corpus retains `A`, `P`, canonical and frozen row/channel maps, `Q`, the
actual right-hand side, expected `lambda` and polynomial coefficients, model
and geometry generator identity, and every payload hash. A literal frozen
Polatory mixed-gradient capture and a canonical row-map reassembly are kept as
separate evidence. Agreement among factor substrates cannot turn a possible
assembly mismatch into semantic authority or a confirmed defect.

The prototype records raw values and keeps judgment separate. Until the
corpus, the applicable rank authority, and attempts exist, its state is
`EVIDENCE_MISSING`, not `COLLECTED, UNJUDGED`. Completed diagnostic collection
without an applicable `FactorHealthProfile` is `COLLECTED, UNJUDGED`.

## Packing

The record header is RapidRBF-owned and includes schema, backend identity,
algorithm identity, dimensions, source hash, payload lengths, and checksum.
Payload eligibility is distinct:

- caller-owned documented factor components may be normalized and packed;
- an undocumented crate-internal object is `resident-only`;
- a source-matrix rebuild record is labelled as recomputation, never as a
  packed factor.

Cross-backend factor portability is not assumed.

For a coarse record, the projected symmetric factor and the small
polynomial-recovery factor have independent matrix hashes, rank certificates,
attempt reports, pivots, retained bytes, and workspace. A small recovery error
alone does not prove that the candidate coarse factor path is admissible.

## Atomicity and fallback staging

Every attempt starts from the same immutable, hash-verified source matrix and
right-hand side. Because factor and solve APIs overwrite their inputs, they
receive private staging. Failed staging is discarded completely; a fallback
never consumes a buffer mutated by an earlier attempt.

Preflight reserves the worst-case registered route at once: immutable source,
the largest factor and workspace attempt, packing/unpacking, solve staging, and
certificate staging. A late allocation failure cannot make the chosen fallback
depend on allocator timing.

Publication has two atomic stages:

1. `factorize` may publish `ValidatedFactor` only after factor finiteness,
   independent reconstruction, metadata validation, and—when advertised—
   pack/unpack replay pass. It does not depend on one particular right-hand
   side.
2. Each `solve` uses private staging and may publish one correction only after
   its complete external certificate passes. At least the operational
   right-hand side and deterministic constraint/dynamic-range manufactured
   witnesses are replayed.

Failure in either stage leaves the prior factor/cache/output state unchanged
and reusable. One successful right-hand side never promotes an invalid factor.
Stage 0 currently replays the operational captured right-hand side only; the
constraint/dynamic-range witnesses are therefore a named publication gap.

## Resources and threads

Each fresh worker reports:

- canonical input bytes;
- retained factor owned capacity, or a labelled lower bound that leaves
  admission unclosed;
- transient RAM scratch requested, granted, high-watered, and released;
- temporary-storage occupancy, bytes written, high-water, and residue;
- declared native workspace query where available;
- configured/effective/maximum-live threads; and
- whether the backend has a process-global or caller-scoped thread control.

The caller owns the thread lease. Local dense work is sequential; 1/2/8 lanes
refer to outer domain workers. A coarse solve may transfer permits to inner
parallel work only through an explicit lease handoff, never by reading an
unbounded process-global default.

This prototype executes one fresh outer worker at a time. It proves the pinned
sequential backend settings, not the 1/2/8 outer-lane maximum-live-thread
envelope; that envelope remains `EVIDENCE_MISSING`.

These are prototype diagnostics. Release memory channels, scratch occupancy,
paired measurements, and threshold judgment remain separate. Artifact closure
is also per target: backend binaries, transitive runtimes, CPU dispatch,
provenance, license evidence, and clean-host launch are recorded independently.
One locally executable Windows comparator cannot close Linux or either macOS
artifact.
