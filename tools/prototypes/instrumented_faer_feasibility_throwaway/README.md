# THROWAWAY PROTOTYPE — instrumented in-process faer feasibility

## Question

Can one exact, hash-bound narrow fork of `faer 0.24.4`, together with every
selected `private-gemm` and `dyn-stack` path, close the two execution-boundary
proofs on the largest admitted projected `B` factor and the largest admitted
coarse `P_top` factor across all four tier-one targets before the 216-factor
qualification begins?

This prototype answers only whether the evidence presently supports one of the
three dispositions allowed by the ticket:

- `FEASIBLE_FOR_216_FACTOR_QUALIFICATION`;
- `EVIDENCE_BACKED_REJECTED`; or
- `UNJUDGED_EVIDENCE_MISSING`.

It does not replay the 216 factors, adopt `faer`, compare solver mechanisms,
choose persistent factor storage, or enter the 100k rung.

## Run it

From the repository root:

```powershell
python tools/prototypes/instrumented_faer_feasibility_throwaway/tui.py
```

The full relevant state is redrawn after every action:

- `j` / `k` select the next or previous gate;
- `v` rotates summary, source-path, and evidence views;
- `r` reloads the captured evidence;
- `q` quits.

For a deterministic non-interactive frame:

```powershell
python tools/prototypes/instrumented_faer_feasibility_throwaway/tui.py --snapshot
```

To print all gate and target states:

```powershell
python tools/prototypes/instrumented_faer_feasibility_throwaway/tui.py --matrix
```

## Reproduce the local source audit

The audit expects the exact crates already downloaded by Cargo:

```powershell
$evidenceOut = Join-Path $env:TEMP `
  ("rapidrbf-instrumented-faer-feasibility-" + [guid]::NewGuid())
python tools/prototypes/instrumented_faer_feasibility_throwaway/run.py `
  --registry-root "$env:USERPROFILE\.cargo\registry\src\index.crates.io-1949cf8c6b5b557f" `
  --output $evidenceOut
```

The output directory must not already exist. The runner:

1. verifies the complete stock source closures captured by the direct-faer
   qualification;
2. mechanically projects the accepted candidate-independent
   `FactorHealthProfile` fields from the old mixed profile;
3. binds the two maximum-shape factor sources and the exact four-target route
   matrix;
4. checks the stock allocation and cancellation surfaces; and
5. emits a portable JSON summary and readable Markdown report without host
   paths.

The runner deliberately does not synthesize a fork identity or target witness.
An absent exact fork, executable control, or qualified-host observation remains
missing evidence.

## Deep module read

The prototype keeps the solver/preconditioner-side factor seam unchanged:

```text
SourceFeasibilityProbe::evaluate(
    FrozenFactorHealthProjection,
    CandidateExecutionBinding?,
    TwoFactorPlan,
    TargetWitnesses[4],
) -> FeasibilityDisposition
```

The interface is intentionally small. Source hashing, patch-surface discovery,
allocation-path classification, cancellation checkpoint accounting, target
identity, and evidence precedence remain inside the probe module. No faer type,
allocator detail, or platform-specific path leaks through the existing private
factor seam.

## Evidence rule

`FEASIBLE_FOR_216_FACTOR_QUALIFICATION` requires every gate and every target
witness to pass. `EVIDENCE_BACKED_REJECTED` requires a reproducible observed
failure of a frozen executable control. A missing fork, unexecuted target,
unqualified host, or unmeasured acknowledgment latency is not rejection; it
forces `UNJUDGED_EVIDENCE_MISSING`.

The captured run therefore separates:

- what stock-source facts are proven;
- what exact candidate must exist before execution is meaningful;
- what a target build can establish; and
- what only a qualified target host can establish.

## Primary context

- [Prototype the next factor-execution boundary after direct faer remains diagnostic-only](https://github.com/qingsonger/RapidRBF/issues/39#issuecomment-5111770941)
- [Qualify the run-scoped faer factor path for mechanism-panel use](https://github.com/qingsonger/RapidRBF/issues/38#issuecomment-5111113874)
- [Materialize the canonical 1k/10k hierarchy admission corpus and certificates](https://github.com/qingsonger/RapidRBF/issues/37#issuecomment-5109692128)
