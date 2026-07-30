# Issue 61 throwaway M3 mechanism diagnosis

This branch extends the accepted Issue 32 mechanism-panel primary source to
answer one new question: why does the complete direct certificate fail only on
`M3-HERMITE-10K`, and what single bounded mechanism change should be carried
into the next experiment?

The diagnosis is throwaway evidence, not production solver code. Existing
canonical factors keep their repaired-reference checks. The generated
4096-target coarse factor is deliberately diagnostic-only; it has not passed
the candidate-independent factor qualification required by the frozen next
experiment and makes no factor-backend or solver-admission claim.

## Issue 61 commands

The deterministic one-step red loop is:

```powershell
.\repro-issue61.ps1 -MaximumIterations 1
```

It exits red only when the canonical `M3-HERMITE-10K` complete-direct path
reproduces the isolated mixed-gradient failure before any restart.

The structural/operator audit and the three one-variable probes are:

```powershell
.\run.ps1 -Workload M3-HERMITE-10K -MechanismAuditOnly
.\run.ps1 -Quick -Workload M3-HERMITE-10K -MaximumIterations 100 -BalanceGradientBlockMax
.\run.ps1 -Quick -Workload M3-HERMITE-10K -MaximumIterations 8 -FineCoarseFine
.\run.ps1 -Quick -Workload M3-HERMITE-10K -MaximumIterations 32 -EnrichedCoarseTarget 4096
```

No probe combines variables. The enriched-coarse target is intentionally
restricted to exactly `4096`; this prototype is not a parameter sweep.

Review the complete state and ratify, adjust, or reject the frozen experiment:

```powershell
.\review-issue61.ps1
```

The captured result identities and proposed experiment contract are in
[`evidence/ISSUE61.md`](evidence/ISSUE61.md).

## Issue 32 source lineage

This prototype answers one decision question: whether restarted right-FGMRES
with the registered one-level, additive, projected-deflated, or frozen
residual-correction RAS topology has a globally admissible mechanism on the
canonical M1-M4 1k/10k panel.

It is evidence code, not production solver code. Run-scoped Eigen factors are
checked against the repaired frozen-system reference but are not a
release-admitted factor backend. The frozen Polatory FMM action is only a 10k
screening route; successful diagnostic candidates are recomputed with the
complete direct evaluator.

## Live review

After producing the two result JSON files, start the tiny interactive review:

```powershell
.\review.ps1
```

The review shows every decision-relevant state and asks the reviewer to accept,
adjust, or reject the finding. It does not mutate GitHub.

## Reproduce

The main panel and the targeted robust/parity audit each use one command:

```powershell
.\run.ps1 -Output D:\fresh\issue32-panel.json
.\run.ps1 -AuditOnly -Output D:\fresh\issue32-orthogonalization-audit.json
```

`run.ps1` freezes OpenMP at 8 threads and MKL at 1 thread, builds with the
frozen Polatory checkout, verifies the canonical corpus and repaired reference
identities, and requires a fresh result path.

The accepted Issue 32 evidence identities and compact findings remain recorded
in [`evidence/SUMMARY.md`](evidence/SUMMARY.md).
