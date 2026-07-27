# ScalFMM3 narrow C-ABI decision lab

Issue: [Probe the pinned ScalFMM3 narrow C-ABI boundary](https://github.com/qingsonger/RapidRBF/issues/31)

## Question

Can Polatory's pinned ScalFMM3 fork (`0be3d74`) be contained behind a
versioned, narrow C ABI without leaking its mutable C++ evaluator into
RapidRBF—and which observed failure first disqualifies it from large-workload
`Auto`?

## Short answer

The caller-first boundary is mechanically plausible. This prototype recommends
**forced-prototype-only**, pending human review; it does not record an accepted
Wayfinder decision.

The throwaway DLL successfully contains a Gaussian probe behind six versioned C
exports. It checks structure versions and exact lengths, copies fixed inputs,
owns plan/lane lifetimes, rejects concurrent use of one lane, stages output,
and leaves the caller's values buffer unchanged on exercised failures while
resetting `value_count` to zero. A forced boundary exception was caught, the
affected lane was poisoned, and a fresh lane from the same plan remained
usable; an exception originating inside an OpenMP worker was not exercised.

That success does not make the backend `Auto`-eligible. The first hard
disqualifier is certification: the frozen estimator samples at most 10,000
locations, is sensitive to changing weights, and cannot provide a sound
complete-batch, call-scoped absolute-infinity bound. On the observed
1024-by-1024 ScalFMM matrix, full-direct *diagnostic* errors ranged from about
`4.91e-4` to `3.02e-1`; all 36 exceeded the requested `1e-6` budget. The shim
correctly refuses certified success; only an explicit evidence-only flag
permits publication. The evidence route deliberately uses the frozen
infinity/default order-6 configuration rather than claiming that a tuned
configuration met the caller budget, so this range is not a tuned capability
result.

## Caller-first seam

RapidRBF's Rust-facing module keeps the two workflows already selected by the
matrix-kernel design:

- `PreparedOperator`: fixed source/target geometry, changing weights.
- `PreparedField`: fixed sources/weights, changing target batches.

The private C plan is narrower still: one isotropic term, one dimension, one
`A`/`F`/`F^T`/`H` action, one geometry, and one reuse shape. An exclusive lane
owns the mutable native evaluator.

Rust remains responsible for anisotropy transforms, term and split composition,
the public error algebra, complete certification, resource policy, and direct
fallback. This prototype does not turn ScalFMM into a public backend/plugin
interface.

## Collected observations

The checked-in JSON is classified **`COLLECTED, UNJUDGED`**:

- All 23 mechanical probe checks passed.
- The public header compiled as C11, and a C executable crossed the DLL seam
  and observed the versioned `ABI_MISMATCH` contract.
- 24 `PreparedOperator` cases covered 1D–3D, all four actions, and self/cross
  geometry on the legacy direct route.
- 12 `PreparedField` cases covered 1D–3D and all four actions; an empty target
  batch also succeeded without native work.
- 36 Gaussian cases at 1024-by-1024 covered both workflows, 1D–3D, all four
  actions, and operator self/cross geometry on the actual ScalFMM route.
- ABI mismatch, insufficient fixed-input grant, bad dynamic length,
  out-of-bbox target, unavailable certificate, and pre-cancellation all
  returned stable statuses without publishing partial output. The lane
  remained reusable.
- Mutating caller-owned fixed coordinates after plan creation did not change
  output, demonstrating an owned copy.
- A forced C++ boundary exception returned `INTERNAL_FAILURE`, did not publish
  values, conservatively poisoned that lane, and left the plan able to open a
  working replacement lane.
- Two overlapping calls on one lane produced one evidence result and one
  `BUSY` result.
- The shim restored the caller thread's OpenMP dynamic/max-thread settings;
  actual effective and maximum-live native team sizes remain reported as
  `unknown`.
- Eight short repeated FMM evaluations stayed within the probe-only 128 MiB
  process-private span. The exact volatile samples are in the JSON; this is not
  scale qualification.
- The DLL imports LLVM OpenMP, sequential oneMKL, and MSVC runtimes. Only the
  local Windows x86-64 path was exercised.
- The reused `polatory.lib`, native import libraries, and local runtime DLLs
  are content-hashed. Those hashes identify the artifacts but do not prove
  that the existing `polatory.lib` was built from the observed checkout heads.
- The 152-file installed ScalFMM header tree used for compilation is
  content-identical to the pinned source checkout's public-core header tree.

The source probe separately freezes the Polatory and ScalFMM revisions, source
hashes, mutable evaluator facts, sampled estimator behavior, missing
cancellation-symbol matches across 193 scanned FMM/public-core files, build
dependencies, and the CeCILL-C marker. The negative scan is evidence, not a
formal proof that no differently named hook exists.

## Auto promotion gates

| Gate | Current evidence |
| --- | --- |
| Semantic/action closure | Partial: Gaussian mechanics only |
| Sound call-scoped certificate | **Fail: first hard disqualifier** |
| Owned bounded prepared reuse | Partial: lane persists, frozen evaluator releases trees |
| Finite cancellation/resource control | Fail: monolithic work and partial accounting |
| Scale/repeated stability | Missing: short process-wide sample only |
| Tier-one runtime/license closure | Missing |

The prototype recommendation is therefore to keep this as an implementation
containment experiment, not select ScalFMM through `Auto`. Issue 31 remains
open, and no map decision should be recorded until the HITL questions below
are answered.

## Explore it

From the repository root:

```powershell
python tools/prototypes/scalfmm3_narrow_c_abi_throwaway/tui.py
```

Use `w/a/d/g/k/x/r/e` to vary workflow, action, dimension, geometry, term,
anisotropy ownership, run case, and scenario profile. Use `0` to reset and `q`
to quit. A non-interactive frame is available with `--snapshot`.

The native build and evidence collection steps are in
[`probe/REPRODUCE.md`](probe/REPRODUCE.md).

## What this prototype does not claim

- Only Gaussian mechanics are compiled; other required families and split
  compositions are not qualified.
- Full direct comparison is a diagnostic, not a conservative certificate.
- Cancellation before or after monolithic work is not a finite in-flight
  cancellation quantum.
- Declared grants do not govern every ScalFMM/OpenMP/MKL allocation or thread.
- The frozen evaluator does not retain the intended trees/multipoles across
  evaluations.
- The short memory sample is not the required 1k→10k→100k or million-scale
  evidence.
- This is not a clean-host or four-tier-one-platform distribution proof.
- The embedded backend revision is a declared source identity, not
  cryptographic build provenance.
- No exception originating inside an OpenMP worker was exercised.
- License notes are engineering inventory, not legal advice.

## Human review requested

1. Accept the two Rust workflows plus single-term/action plan-lane C seam as
   the right private boundary?
2. Accept rejecting a direct pass-through of Polatory's mutable evaluator?
3. Treat missing sound certification, finite cancellation, and enforceable
   resources as hard `Auto` disqualifiers?
4. Treat the macOS-arm64 FFTW path and CeCILL-C/MKL/OpenMP release closure as
   remediable release blockers, or as candidate-killing evidence?
5. Keep ScalFMM forced-prototype-only for later fork work, or reject it from the
   v1 candidate set now?
6. Treat 36/36 order-6 evidence diagnostics exceeding `1e-6` as additional
   candidate-rejection evidence, or only as the expected result of an untuned,
   uncertified evidence route?

This directory is intentionally throwaway. It changes neither RapidRBF
production code nor the pinned external checkouts.
