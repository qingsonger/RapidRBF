# THROWAWAY PROTOTYPE — differential/resource harness lab

Run it from the repository root:

```powershell
python tools/prototypes/differential_resource_harness_throwaway/tui.py
```

Print one non-interactive frame:

```powershell
python tools/prototypes/differential_resource_harness_throwaway/tui.py --snapshot
```

## Question

Does this state model give RapidRBF one cheap, auditable way to register an
acceptance scenario, drive the same frozen logical request through Polatory and
one candidate adapter, retain semantic and resource evidence, and produce a
reviewable paired report without smuggling in numerical thresholds, performance
statistics, or a backend choice?

This is an in-memory decision prototype. Pressing `capture` creates visibly
**synthetic shape-check records**, not benchmark or compatibility evidence. It
does not execute Polatory, RapidRBF, a million-scale workload, or any backend.

## Controls

- `s` — next acceptance scenario
- `c` — next RapidRBF candidate adapter
- `l` — next execution-lane/cache profile
- `n` — next illustrative repetition count
- `o` — next paired-order seed
- `p` — register and freeze the plan
- `x` — capture the next synthetic run slot
- `i` — inject an anomaly into the next capture
- `v` — switch between the compact pair ledger and focused pair detail
- `j` — focus the next repetition pair
- `a` — derive the current audit/report view
- `r` — reset the lab
- `q` — quit

Configuration is immutable after registration. Resetting and changing a lane
creates a new measurement plan; it does not create a new acceptance-scenario
identity. The demo uses a seeded balanced crossover order; the production order
policy remains downstream. Every repetition has a pre-registered subject order,
so an incomplete pair cannot silently disappear.

Try a complete clean plan first. Then reset and inject fixture drift, a cache
mismatch, thread-budget overrun, a missing evidence channel, or a timeout.
`raw-byte drift with equal semantics` should remain a diagnostic rather than a
compatibility failure.

## Proposed shape under test

```text
versioned acceptance-scenario ref + content-addressed fixture
                            |
                    immutable paired plan
                            |
             process-isolated subject adapter slots
                /                           \
       frozen Polatory                 RapidRBF candidate
                \                           /
        append-only raw + normalized run evidence
                            |
          identity/channel/resource closure audit
                            |
           COLLECTED, UNJUDGED reviewable report
                            |
       separately versioned threshold sets attach later
```

The production shape implied by the prototype is:

1. A controller owns stable scenario references, content identities, paired
   order, process-tree containment, scratch space, and evidence closure.
2. Thin subject adapters translate the same logical request into Polatory or a
   RapidRBF seam. Adapter-specific argv and serialization remain declared
   differences; they do not become the common semantic model.
3. Each run retains raw streams and artifacts, plus a normalized observation
   envelope. A channel is explicitly `observed`, `derived`, `unavailable`, or
   `not-applicable`; missing is never confused with unavailable.
4. Resources record monotonic wall time, user/system CPU, platform-native and
   normalized process-tree memory, I/O, scratch high-water, output size,
   configured/effective/maximum-live threads, sampling scope, cache/reuse facts,
   terminal state, and cleanup.
   Warm-up, preparation, and measured apply/invoke phases are separately hashed.
   Prepared sessions share an identity, carry ordered apply indices and retained
   process-tree memory samples, and close only on their final slot.
5. Comparisons reference immutable run records rather than copying them.
   Numerical arrays, stable failures, fit certificates, convergence records,
   point-cloud states, and certified geometry use operation-specific normalized
   envelopes. Raw text, mesh numbering, tessellation, OBJ bytes, solver
   trajectory, and backend route are not global equality targets.
6. The report first judges evidence closure and pair invariants. With no
   separately versioned numerical/resource threshold sets attached, its only
   valid success state is `COLLECTED, UNJUDGED`.
   The bundle root hashes the frozen plan and every complete-record digest;
   audit recomputes plan, phase, record, and bundle identities rather than
   checking only that hash-shaped strings exist.
7. Canonical optimized runs own performance and resource evidence.
   Instrumented runs may add residual histories or internal diagnostics, but
   they are separate immutable records linked by scenario, fixture, and build
   lineage; their timings never enter the canonical paired comparison.

## Execution-lane vocabulary being tested

- **Fresh process** means a new subject process and isolated scratch directory.
  It deliberately makes no claim that the operating-system page cache is cold.
- **Declared warm-up** means each subject independently performs and records an
  untimed precondition before its measured slot.
- **Prepared reuse** separates preparation from repeated application and keeps
  retained-memory and cleanup evidence across the sequence.

These labels are proposed for human review. Exact cache policies, repetitions,
statistics, thresholds, and resource caps remain owned by
[Set the performance, memory, threading, and cache acceptance standard](https://github.com/qingsonger/RapidRBF/issues/17).
Numerical, geometric, residual, rank, KKT, accuracy, and convergence judgments
remain owned by
[Set the numerical and convergence acceptance standard](https://github.com/qingsonger/RapidRBF/issues/16).

## Evidence seed and boundaries

The prototype is seeded from:

- [Establish the reproducible Polatory validation, performance, and release baseline](https://github.com/qingsonger/RapidRBF/issues/4)
- [Freeze the executable Polatory behavior oracle](https://github.com/qingsonger/RapidRBF/issues/6)
- [Define the v1.0.0 acceptance workload matrix](https://github.com/qingsonger/RapidRBF/issues/9)
- [Define the backend-neutral matrix-kernel contract](https://github.com/qingsonger/RapidRBF/issues/10)
- `CONTEXT.md`
- `oracle/manifests/oracle-index.json`
- `baseline/polatory-4a30beb-windows-x86_64`

The existing oracle contributes content-addressing, isolation, role/authority,
and checksum lessons. It explicitly is not the future cross-implementation
harness: its exact replay is an integrity check, its current resource samples
are non-normative and mostly direct-process-only, and it defines no
operation-specific comparison tolerance.

The repetition counts in this lab exist only to make the state machine
driveable. They are not a recommendation. CI runners, triggers, shards, and
schedules remain downstream of this ticket.

## Feedback this prototype is asking for

The useful human reaction is whether any of these boundaries feel wrong:

- Are `Fresh process`, `Declared warm-up`, and `Prepared reuse` the right
  top-level cache/reuse facts, or must OS page cache, process state, and backend
  prepared state be independent axes?
- Should the common performance boundary be end-to-end isolated subject
  processes, or may a RapidRBF core action be measured as a separately metered
  phase while Polatory remains a CLI workflow?
- Is an explicit `unavailable` diagnostic channel acceptable when the
  comparison-required semantic channels are complete?
- Must retries always append a new attempt, preserve the failed attempt, and
  remain excluded from the primary summary until a downstream policy admits
  them?
- Is the canonical/instrumented evidence split sufficiently visible, or should
  it be a first-class paired slot type in the plan?
