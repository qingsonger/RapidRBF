# THROWAWAY PROTOTYPE — direct in-process stock faer qualification

## Question

Can the pinned Stage-0 Windows x86-64 build of stock `faer 0.24.4`
(`default-features=false`, `std+linalg`), behind a direct in-process
RapidRBF-owned run-scoped factor module with sequential local dense calls,
publish `ValidatedFactor` and externally certified `Solved` corrections for
every factor in the canonical M1–M4 1k/10k hierarchy while also closing exact
resources, atomicity, cancellation, and the registered thread lanes?

This prototype answers the qualification question. It does not implement a
production solver or adopt a dependency.

## One-command evidence run

The 1.268 GiB payload corpus is intentionally not checked into Git. Point the
lab at a verified reproduction plus the checked-in upstream reports:

```powershell
$evidenceOut = Join-Path $env:TEMP `
  ("rapidrbf-faer-factor-qualification-" + [guid]::NewGuid())
python tools/prototypes/faer_factor_qualification_throwaway/run.py `
  --corpus-manifest "$env:RAPIDRBF_HIERARCHY_CORPUS\hierarchy.manifest.raw.json" `
  --admission-report tools/prototypes/dense_factor_replay_throwaway/evidence/hierarchy-admission-report.json `
  --physical-report tools/prototypes/dense_factor_replay_throwaway/evidence/hierarchy-physical-evaluator-report.json `
  --faer-source "$env:USERPROFILE\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f\faer-0.24.4" `
  --output $evidenceOut
```

The generated output path must not exist; the command above creates a fresh
one under the system temporary directory. The runner verifies the frozen
corpus, lock, admission report, physical report, Stage-0 Cargo manifest/lock,
and `FactorHealthProfile` identities before verifying the complete pinned
source closures and auditing the relevant APIs. It atomically publishes:

- `$evidenceOut/qualification-summary.json`;
- `$evidenceOut/observed-results.md`.

The checked-in `evidence/` directory captures the reviewed run reported by
this prototype; the fresh path prevents a rerun from overwriting that record.

## Review the state

```powershell
python tools/prototypes/faer_factor_qualification_throwaway/tui.py
```

For a non-interactive frame:

```powershell
python tools/prototypes/faer_factor_qualification_throwaway/tui.py --snapshot
```

The TUI is a thin shell over `model.py`. It always displays the complete gate
state. Use `j`/`k` to select a gate, `v` to change the detail view, `r` to
reload the immutable summary, and `q` to quit.

## Why backend calls remain zero

The preregistered profile requires every backend allocation and retained cache
byte to be caller-owned or exactly precomputable before backend entry, plus
bounded cancellation during a factor or solve. `faer` exposes logical factor
components and low-level `MemStack` requirements, so a RapidRBF-owned factor
record is feasible. On the bound `x86_64 + std + AVX2/FMA` route, those
declared requirements do not include native `f64` GEMM's persistent TLS
buffer. The direct in-process candidate has neither allocator instrumentation
nor an isolated-worker quota, and its factor/solve kernels expose no
cancellation callback.

This candidate therefore fails at preflight. Running all 216 factors and
printing small residuals would not repair either missing authority. Because
durable pack/reload is not the only gap, the profile does not permit the
bounded run-scoped recompute exception. This does not establish that every
possible RapidRBF-owned faer adapter fails: an instrumented or
process-isolated adapter is a separate candidate requiring its own accepted
resource and cancellation design.

## Deliberate limits

- This is a source- and authority-bound decision probe, not a factor
  benchmark.
- It does not certify runtime faer witnesses with the physical evaluator.
- It does not compare FGMRES/RAS mechanisms, choose persistent factor
  storage, run the 100k rung, select a production backend, or adopt `faer`.
- A later probe may evaluate an instrumented fork or isolated adapter with an
  accepted quota allocator and hard-cancellation design. That is a new
  decision, not a hidden continuation of this prototype.
