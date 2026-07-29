# THROWAWAY PROTOTYPE — frozen instrumented-faer feasibility gate

This directory answers
[Execute the frozen two-factor instrumented faer feasibility gate](https://github.com/qingsonger/RapidRBF/issues/44).
It consumes the exact issue-42 candidate binding without modifying that
binding, and it uses the exact issue-43 four-lane contract.

The artifact is decision evidence, not production code. It does not replay the
216-factor corpus, adopt faer, compare solver mechanisms, choose persistent
storage, or enter the 100k rung.

## Frozen inputs

- candidate binding:
  `RapidRBF/InstrumentedFaerCandidateExecutionBinding/v1/1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6`;
- factor-health profile:
  `00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3`;
- two-factor plan:
  `5b288e33d13464ae79948b1afcb2d76d0d08f9c81b27010ad51d4906cfc66892`;
- lane contract:
  `d6edbf73cc9788dfb56eedc58010ce3b091d94014111a6a4b1f1171cc8f7c5a3`;
- canonical hierarchy corpus:
  `38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`;
- maximum mixed-Hermite projected `B`:
  `e33319fe9a5f02a91bcf7410a784eccc1bded3e05628b59d1d7f0350614d7945`;
- maximum coarse `P_top`:
  `d8f2c6eda87764e279872463d89cbd344d53947ecffeb7bbc0e55cf90438679e`.

The two checked-in payloads were deterministically rematerialized from
Polatory `4a30beb` with the admitted hierarchy capture tool. The reproduced
raw manifest, lock, and complete corpus identities matched the accepted
evidence before these two payloads were copied.

## What one lane does

1. Qualify the native GitHub-hosted lane with the unchanged issue-43
   collector.
2. Verify the exact issue-42 binding at `backend_calls=0`.
3. Build the frozen runner with Rust `1.85.0`.
4. Run projected-B Bunch-Kaufman factor/solve and coarse-P_top full-pivot
   LU/solve through one `ExecutionLease` and `Par::Seq`.
5. Check exact retained bytes, transient cleanup, live outer permit,
   source-level checkpoint bounds, factor/solution finiteness, and reduced
   backward error.
6. Deny an exact one-byte-short transient grant for each factor before
   operation/backend entry.
7. Retain the successful projected-B probe factor while cancelling one
   replacement projected-B attempt 10 ms after its backend signal; record
   qualified-host acknowledgment latency, unchanged prior fingerprint/bytes,
   zero failed publication, and cleanup closure.
8. Confirm the candidate's dedicated temporary-storage root remained empty.

The four lanes are non-compensating. The cohort returns exactly one of:

- `FEASIBLE_FOR_216_FACTOR_QUALIFICATION`;
- `EVIDENCE_BACKED_REJECTED`;
- `UNJUDGED_EVIDENCE_MISSING`.

Even a feasible result only opens the full 216-factor qualification ticket.
Production `ValidatedFactor` and `Solved` publication counts remain zero.

## One command

The branch-local workflow is intentionally triggered by the push that
publishes the frozen preregistration commit:

```powershell
git push origin codex/execute-instrumented-faer-gate
```

GitHub does not expose a newly introduced branch-local workflow to
`workflow_dispatch` until the file also exists on the default branch. The
pre-observation attempt ledger records the rejected manual dispatch; it
created no job and entered no candidate backend.

For a qualified lane job, the underlying single command is:

```powershell
python tools/prototypes/instrumented_faer_feasibility_gate_throwaway/run.py `
  --lane-id windows-x86_64 `
  --target x86_64-pc-windows-msvc `
  --lane-witness lane-evidence/windows-x86_64/lane/lane-identity.json `
  --output lane-evidence/windows-x86_64/execution
```

Do not use a local run as substitute evidence: the disposition requires all
four exact native GitHub-hosted lane identities in one run attempt.
