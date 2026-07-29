# Instrumented faer feasibility gate evidence

This directory is the durable evidence capture for
[Execute the frozen two-factor instrumented faer feasibility gate](https://github.com/qingsonger/RapidRBF/issues/44).

The one admitted execution cohort completed successfully with disposition
`FEASIBLE_FOR_216_FACTOR_QUALIFICATION`.

## Provenance

- Workflow run: [30425496342, attempt 1](https://github.com/qingsonger/RapidRBF/actions/runs/30425496342)
- Trigger: branch-scoped `push`
- Frozen execution commit: `4b966150fc109582f8ac0fbfb29cf2ee4dcb71b0`
- Branch: `codex/execute-instrumented-faer-gate`
- Started: `2026-07-29T05:34:58Z`
- Completed: `2026-07-29T05:39:43Z`
- Workflow conclusion: `success`
- Execution contract SHA-256: `57f784756ec4ca36bb2c0d631e5aafccfba4dd5746cfe68257531bf5728dfd47`
- Cohort summary SHA-256: `c02d3d9c157db2d1de4e35a33bfe01d7f87eb9dbc29778db52ecbe5e707b01c1`

The failed pre-entry manual-dispatch request is recorded separately in
`../instrumented_faer_feasibility_gate_throwaway/pre-observation-attempt-ledger.v1.json`.
It created no workflow run, loaded no candidate binding, and made zero backend calls.
Run `30425496342` is therefore the sole admitted execution cohort.

## Contents

- `api/`: immutable GitHub Actions run, job, and artifact metadata snapshots.
- `artifacts/`: extracted cohort and per-lane evidence, including every producer
  SHA-256 sidecar.
- `service-artifacts/`: the five original ZIP archives returned by the GitHub
  artifact service.
- `run-logs.zip`: the complete GitHub Actions log archive.
- `observed-results.md`: concise human-readable result table and decision boundary.
- `checksums.sha256`: repository-local SHA-256 manifest for every other file in
  this directory.

To verify the capture in PowerShell:

```powershell
$root = Resolve-Path tools/prototypes/instrumented_faer_feasibility_gate_evidence_throwaway
Get-Content "$root/checksums.sha256" | ForEach-Object {
    $hash, $relative = $_ -split '  ', 2
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $relative)).Hash.ToLowerInvariant() -ne $hash) {
        throw "checksum mismatch: $relative"
    }
}
```

## Decision boundary

This evidence answers only whether the frozen two-factor, instrumented, in-process
faer path is feasible enough to enter the already-scoped 216-factor qualification.
It does not replay that corpus, adopt faer for production, compare solver
mechanisms, select persistent storage, or enter the 100k rung. Production
`ValidatedFactor` and solved-result publication remained zero in every lane.
