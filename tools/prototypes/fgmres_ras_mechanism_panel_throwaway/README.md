# Issue 32 throwaway mechanism panel

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

The accepted evidence identities and compact findings are recorded in
[`evidence/SUMMARY.md`](evidence/SUMMARY.md).
