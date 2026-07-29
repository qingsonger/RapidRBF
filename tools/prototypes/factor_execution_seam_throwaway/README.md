# THROWAWAY PROTOTYPE - next factor-execution seam

## Question

After the bound direct in-process stock-`faer 0.24.4` candidate remained
`NOT_ADMITTED_DIAGNOSTIC_ONLY`, which one concrete v1 factor-execution seam is
plausible enough to advance to full qualification against all 216 admitted
factor sources?

This prototype makes two candidate execution seams and one contingency
tangible:

1. an instrumented in-process faer adapter;
2. a process-isolated faer worker; and
3. a bounded reopening of the dense-factor substrate.

It preserves the admitted hierarchy authority and proposes a mechanical
candidate-independent projection of the accepted health rules currently mixed
into `RapidRBF/FactorHealthProfile/v1`. It does not run factorization, qualify a
candidate, adopt a dependency, compare solver mechanisms, choose persistent
factor storage, or enter the 100k rung.

## Run it

From the repository root:

```powershell
python tools/prototypes/factor_execution_seam_throwaway/tui.py
```

The whole relevant state is redrawn after every action. Use:

- `1` / `2` / `3` to inspect the two candidates and the disabled contingency;
- `j` / `k` to switch the scenario;
- `Space` to advance one state transition;
- `r` to reset the current scenario;
- `v` to rotate through state, interface, and trade-off views; and
- `q` to quit.

For a deterministic non-interactive frame:

```powershell
python tools/prototypes/factor_execution_seam_throwaway/tui.py `
  --route process_isolated_faer_worker `
  --scenario cancel_mid_factor `
  --steps 99 `
  --snapshot
```

To show every scenario's last modeled outcome:

```powershell
python tools/prototypes/factor_execution_seam_throwaway/tui.py --matrix
```

## Fixed authority and invariants

Every route must preserve these facts rather than renegotiate them:

- the admitted corpus has 12 workloads, 204 blocks, and 216 factor sources;
- semantic rank and canonical-nullspace authority precede backend health;
- the candidate-independent `FactorHealthProfile` projection is frozen before
  candidate observations begin;
- a factor stays private until finiteness, independent reconstruction, and
  metadata/checksum checks pass, followed by either successful pack/reload or
  the one explicitly bounded run-scoped recompute exception;
- each solve stays private until reduced-error plus independent
  value/gradient and CPD certificates pass;
- one byte below the exact total grant returns `ResourceDenied` before any
  backend call or publication;
- cancellation is bounded during a factor or solve, not merely polled at the
  outer interface;
- factor failure preserves the previous `ValidatedFactor`; solve failure
  preserves both its `ValidatedFactor` and the previous `SolvedCorrection`;
- every attempt either releases its caller-owned `ExecutionLease` after
  cleanup is proven or quarantines it after containment/audit failure; the
  lease carries the exact aligned transient arena, retained-byte reservation,
  one compute permit, allocation guard, temporary-storage policy, observer,
  and cleanup guard; and
- the registered `1/12`, `2/12`, and `8/16` lanes pass independently.

## Identity model correction

The captured direct-faer `factor-health-profile.v1.json` mixes two different
identities: candidate-independent health rules and the direct-faer candidate
binding. Its whole-file hash therefore cannot be reused as a
candidate-independent profile hash.

Every contender in this prototype uses three explicit concepts:

- `FactorHealthProfile`: immutable algorithms, thresholds, required logical
  factor fields, checksum/source-binding and reload semantics, controls,
  publication rules, and the narrow recompute rule; candidate observations
  cannot change it.
- `CandidateExecutionBinding`: exact substrate/version/source closure,
  features, target, execution seam, allocator/cancellation implementation,
  and concrete encoding/schema implementation.
- `FactorQualificationPlan`: the immutable combination of admitted corpus,
  profile digest, binding digest, factor/RHS inventory, target/lane, exact
  resource schedule, cancellation bound, controls, and required evidence. It
  contains no observations or disposition.

The old whole-file identity remains valid evidence for the rejected direct
candidate. A new contender must use a deterministic mechanical projection of
the accepted rule fields, canonicalize and hash those projected bytes before
candidate observations, and preserve an auditable mapping to the old file. A
manual re-expression is not an identity-preserving operation. The contender
then obtains a new qualification-plan identity; it must not silently reuse or
reinterpret the old whole-file hash.

## Competing interfaces

### Instrumented in-process faer adapter

```text
RunScopedFactorModule::factorize(
    FactorSource,
    FactorQualificationPlan,
    ExecutionLease,
    Cancellation,
) -> QualifiedFactorAccess

QualifiedFactorAccess =
    ValidatedFactor |
    RunScopedRecomputeRecipe

RunScopedFactorModule::reload(
    ExpectedFactorIdentity,
    PackedFactorBytes,
    FactorQualificationPlan,
    ExecutionLease,
    Cancellation,
) -> ValidatedFactor

ValidatedFactor::solve_certified(
    CertifiedRhs,
    CertificateContext,
    ExecutionLease,
    Cancellation,
) -> SolvedCorrection

RunScopedRecomputeRecipe::solve_certified(
    CertifiedRhs,
    CertificateContext,
    RecomputeToken,
    ExecutionLease,
    Cancellation,
) -> SolvedCorrection
```

This is the deepest interface for callers and fits the self-contained Rust
library. Its implementation must be a new, hash-bound candidate: a narrowly
maintained source fork that routes every faer/private-gemm/dyn-stack byte
through the allocation domain inside a caller-owned `ExecutionLease`, removes
persistent unowned TLS state, and polls cancellation at bounded pivot, panel,
packing, and macro-kernel safe points. A source change that bypasses either
proof fails closed.

`ExecutionLease` is caller-owned and call-scoped. It binds `plan_id` and
`operation_id` to an exact-size/alignment transient arena, retained-byte
reservation, exactly one computational permit, allocation-domain guard,
temporary-storage grant or deny policy, resource/thread observer, and RAII
cleanup guard. Factor and solve receive distinct leases. This adapter fixes
faer at `Par::Seq`; it cannot mint workers from the lease or escape an outer
caller-owned permit.

Reload rejects truncated, corrupt, wrong-source, wrong-profile, and
metadata-mismatched records before replacement publication. The previous
immutable factor remains directly reusable after every rejection.

The recipe variant is a separate publication slot, never a factor. It owns an
accounted `RetainedSourceLease`. The `FactorQualificationPlan` freezes the cap
and budget identity; the caller owns one non-copyable, run-wide
`RunRecomputeBudget(216)` shared by every recipe. Each backend entry requires
a `RecomputeToken` issued from that monotonic budget.
Exact N-minus-one rejection occurs before token issuance or backend entry; a
cancelled recomputation consumes one token, discards its private draft, and
returns its compute lease. A recipe has no private 216-token allowance, no
eviction rebuild, and no cross-run cache; its retained source is released by
RAII at run end.

The cooperative guarantee must be stated honestly: no selected call path may
execute more than a preregistered number of work units without polling, and a
qualified-host acknowledgment-latency gate must also pass. It is not an
unconditional wall-clock guarantee when the operating system stops scheduling
the process, nor can it preserve state after a process abort.

Smallest honest next probe: before replaying 216 factors, patch one worst-case
projected `B` and one coarse `P_top` path and prove exact allocation closure,
grant-minus-one behavior, and maximum cancellation latency on all tier-one
targets.

### Process-isolated faer worker

```text
FactorWorkerController::factorize(
    FactorSource,
    FactorQualificationPlan,
    ExecutionLease,
    Cancellation,
) -> QualifiedFactorAccess

QualifiedFactorAccess =
    ValidatedFactor |
    RunScopedRecomputeRecipe

FactorWorkerController::reload(
    ExpectedFactorIdentity,
    PackedFactorBytes,
    FactorQualificationPlan,
    ExecutionLease,
    Cancellation,
) -> ValidatedFactor

ValidatedFactor::solve_certified(
    CertifiedRhs,
    CertificateContext,
    ExecutionLease,
    Cancellation,
) -> SolvedCorrection

RunScopedRecomputeRecipe::solve_certified(
    CertifiedRhs,
    CertificateContext,
    RecomputeToken,
    ExecutionLease,
    Cancellation,
) -> SolvedCorrection
```

The parent alone owns publication. A private protocol binds every request and
reply to an epoch, source, profile, `binding_id`, `plan_id`, executable, and
payload identity. The parent validates all of them before decode or
publication. Platform adapters own process creation, the complete process-tree
enclosure, hard kill, reap, high-water accounting, and scratch cleanup.

This makes crash and cancellation containment strong, but it adds two
current blockers before corpus replay is honest:

- four target-specific adapters must each satisfy the same abstract
  grant/containment/high-water/cleanup obligation while preserving their raw
  operating-system measurement semantics; the exact macOS process-group
  closure is currently unproven; and
- ordinary stable Cargo library consumers must reliably obtain a matching
  helper executable without turning the Rust crate into a platform-specific
  binary package.

Process isolation also does not make one-byte-below preflight exact by itself.
Operating-system high-water evidence can contain and observe hidden
allocations, but the worker still needs exact precomputation or a controlled
allocator to reject an insufficient grant before backend entry.

The worker recipe variant has the same separate publication,
`RetainedSourceLease`, and shared run-wide budget contract. Each
backend-entered token uses a fresh cohort; N-minus-one consumes neither a token
nor a spawn, while cancellation consumes the token and must finish full cohort
cleanup within the registered bound.

Factor and solve use fresh worker cohorts so their high-water measurements
remain per operation. A worker never receives a writable alias to prior
published state. Publication occurs only after the cohort has exited and been
reaped, final accounting passes, scratch residue and live handles are zero,
and a final cancellation check passes. Cancellation kills and reaps the whole
tree and discards queued replies. The cancellation bound covers termination,
reap, cleanup, and audit; failure or timeout in any of those stages is
`ContainmentFailure` and quarantines the lease rather than returning an
ordinary `Cancelled`.

Canonical worker wall time is end-to-end: spawn, handshake, transfer,
factor/solve, pack/reload, independent validation, reap, and cleanup. A
backend-only timer is diagnostic evidence.

### Reopen the dense-factor substrate

```text
DenseSubstrateAdmission::screen(
    CandidateExecutionBinding,
    CanonicalCorpus,
    FactorHealthProfile,
    ResourceGrant,
) -> CandidateDisposition
```

This is not a factor-execution adapter and is not selectable for this ticket
today. Its current state is `ROUTE_NOT_TRIGGERED / V1_BLOCKER`. It is a
fail-fast search seam, so it cannot publish `ValidatedFactor` or unblock the
mechanism panel. It is a contingency only after both faer seams are reproducibly
`EVIDENCE_BACKED_REJECTED` under the same controls and at least one pinned
replacement binding passes a static structural screen. `EVIDENCE_MISSING`,
an unimplemented wrapper, or "looks difficult" cannot trigger it.

If triggered, the single fixed `CandidateFamily` is
`OxiBLAS 0.2.1 @ 00dcf6441ed1e74c1b4e5fe75cad8a06b16ae7bf`, comprising four
target-specific bindings. `nalgebra 0.35.0` and the exact Windows oneMKL
candidate remain excluded by existing evidence. Cap the family at five
person-days after its binding family, plan, and `STATIC_PLAUSIBLE=PASS`
evidence are frozen: day 1 audits that immutable plan, days 2-4 run one
maximum-fine and one coarse executable control probe, and day 5 records
exactly one disposition:
`CONTENDER_FOR_HITL`, `NO_PLAUSIBLE_SUBSTRATE_V1_BLOCKER`, or
`UNJUDGED_TIMEBOX_EXHAUSTED`. Worker crash and protocol controls apply only if
the candidate execution mode is a worker. A
`NO_PLAUSIBLE_SUBSTRATE_V1_BLOCKER` disposition requires a reproducible
executable-control rejection, not a repeated static screen. None of these
outcomes is factor qualification, and no second family may be substituted
inside the timebox.

## Dependency classification

- Linked factor code, health checks, identity reducers, and resource
  arithmetic are **in-process** dependencies, even when the source is a
  third-party crate.
- Temporary storage, an independent evaluator executable, and a process
  supervisor are **local-substitutable** dependencies behind internal
  adapters.
- This module has no remote-but-owned or true-external service dependency and
  needs no network port or mock seam.

The external `FactorExecution` seam is real because the in-process and worker
adapters have materially different implementations. It remains crate-private;
no faer type or runtime backend selector crosses it.

## Provisional design read

The strongest and only currently plausible next probe is the instrumented
in-process faer adapter, subject to an early, cheap source-feasibility gate for
complete allocation ownership and bounded cancellation. It gives the caller
the smallest interface, keeps complexity local, and preserves the official
Rust library's ordinary distribution shape.

The process worker has better hard-failure containment, but its helper
distribution and cross-tier-one quota semantics are part of the production
interface, not harness details, and are current admission blockers. Reopening
the substrate is not a concrete seam choice; it is justified only after both
faer seams fail with evidence and the fixed replacement is structurally
plausible.

This is a recommendation to react to, not the HITL decision itself.

## Primary context

- [Qualify the run-scoped faer factor path for mechanism-panel use](https://github.com/qingsonger/RapidRBF/issues/38#issuecomment-5111113874)
- [Materialize the canonical 1k/10k hierarchy admission corpus and certificates](https://github.com/qingsonger/RapidRBF/issues/37#issuecomment-5109692128)
- [Compare Rust linear-algebra, Krylov, and multilevel preconditioner stacks](https://github.com/qingsonger/RapidRBF/issues/13)
- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Linux cgroup v2 memory controller](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [Apple `setrlimit(2)` manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/setrlimit.2.html)
- [Cargo artifact-dependency status](https://doc.rust-lang.org/cargo/reference/unstable.html#artifact-dependencies)

The platform links explain why process isolation is not one uniform adapter:
Windows Job Objects manage and account for a process tree; Linux cgroup v2
exposes `memory.max` and `memory.peak` with documented enforcement caveats;
Apple's documented `RLIMIT_RSS` is a process-level preference under memory
pressure rather than a hard process-tree quota; and Cargo artifact
dependencies for building dependency binaries remain unstable.
