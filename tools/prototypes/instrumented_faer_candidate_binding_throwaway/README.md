# THROWAWAY TASK ASSET — exact instrumented faer candidate binding

This directory materializes the candidate requested by
[issue 42](https://github.com/qingsonger/RapidRBF/issues/42). It binds one
immutable source closure and one target-independent caller seam for all four
tier-one targets. It does **not** execute or judge the two frozen factors,
qualify the 216-factor corpus, adopt faer, compare solver mechanisms, choose
persistent storage, or enter the 100k rung.

The binding identity is in
[`binding-manifest.v1.json`](binding-manifest.v1.json). The manifest hashes
every file in this task asset except itself, `target/`, and future execution
evidence. Its `observation_boundary` must remain at `backend_calls=0`; issue 44
owns all factor observations and the feasibility disposition.

## Frozen inputs and closure

- candidate-independent `FactorHealthProfile` projection:
  `00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3`;
- two-factor/four-target plan:
  `5b288e33d13464ae79948b1afcb2d76d0d08f9c81b27010ad51d4906cfc66892`;
- stock `faer 0.24.4` + `private-gemm-x86 0.1.20` + `dyn-stack 0.13.2`
  closure:
  `530103a7c8f62e8cf225045d39410b9d36e67d11f5acf6793f403bb0fc1a9fb9`;
- exact changed/added bytes: [`patch-set.v1.json`](patch-set.v1.json);
- exact Cargo manifests, features, and resolution: the vendored
  `Cargo.toml` files plus [`Cargo.lock`](Cargo.lock);
- frozen generated x86 assembly and declarations:
  `vendor/private-gemm-x86-0.1.20/generated/x86_64/`.

`private-gemm` retains its stock generator for review, but normal builds copy
the frozen generated outputs. Only an intentional
`RAPIDRBF_REGENERATE_PRIVATE_GEMM` environment setting regenerates them; doing
so invalidates the binding until the patch set and manifest are refreshed.

## Deep execution seam

The solver/preconditioner side sees only:

```text
CandidateExecutionBinding
  .plan(FactorShape) -> ResourceSchedule
  .preflight(ResourceSchedule, ResourceGrant) -> Result
  .checkpoint_bounds(FactorShape) -> [CheckpointBound; 5]
  .execute(ResourceSchedule, ExecutionLease, CancellationToken, operation)
      -> Result
```

Faer types, dyn-stack carving, private-gemm cache geometry, aligned allocation,
TLS observer wiring, and typed unwind cancellation stay behind that seam. The
selected path is `Par::Seq`, consumes one caller-owned outer compute permit,
uses no nested automatic pool, and denies temporary storage.

The schedule exposes every byte count and alignment needed before backend
entry. The N-minus-one test proves a one-byte-short grant is rejected before
permit acquisition, operation entry, or backend entry. The checkpoint metadata
records source-level work-unit bounds; it deliberately makes no unconditional
wall-clock promise. Issue 44 must measure acknowledgment latency per qualified
host. `ExecutionLease::metrics()` exposes transient high-water/residue,
cumulative reserve/release, stack-carve and checkpoint counts, backend entries,
live outer permits, and the always-zero denied-temporary-storage counters.

## Reproduce

Use Rust `1.85.0` from this directory:

```powershell
python verify_binding.py
cargo +1.85.0 test --locked `
  -p rapidrbf-faer-control `
  -p rapidrbf-instrumented-factor
cargo +1.85.0 run --locked `
  -p rapidrbf-instrumented-factor `
  --example binding_report
```

The example computes only preflight schedules and checkpoint bounds. It does
not call a factor or solve backend.

The GitHub workflow `.github/workflows/instrumented-faer-binding-build.yml`
runs the same verifier and control tests natively on the already-provisioned
fixed lanes:

| Target | Runner |
| --- | --- |
| `x86_64-pc-windows-msvc` | `windows-2025` |
| `x86_64-unknown-linux-gnu` | `ubuntu-24.04` |
| `aarch64-apple-darwin` | `macos-15` |
| `x86_64-apple-darwin` | `macos-15-intel` |

## Deliberate boundary

The tests exercise manifest verification, resource-denial ordering, typed
cancellation transport, and cleanup of the caller-owned permit/TLS control
scope. They do not factor either frozen matrix. A successful four-lane build
materializes one portable candidate; it is not a feasibility observation.
