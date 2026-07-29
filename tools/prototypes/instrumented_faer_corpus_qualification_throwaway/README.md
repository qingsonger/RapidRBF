# THROWAWAY PROTOTYPE — instrumented-faer corpus qualification

## Question

Can the exact issue-42 instrumented in-process faer binding provide one
`QualifiedFactorAccess` path for every source in the admitted
12-workload/204-block/216-factor hierarchy on all four tier-one targets and
the registered `1/12`, `2/12`, and `8/16` lanes without weakening the frozen
factor-health, resource, cancellation, publication, or reload gates?

This artifact answers that question. It is decision evidence, not production
code. It does not adopt faer, compare FGMRES/RAS mechanisms, choose a
persistent factor store, or enter the 100k rung.

## Frozen authorities

- Canonical hierarchy corpus:
  `38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`.
- Candidate-independent `FactorHealthProfile` projection:
  `00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3`.
- Exact candidate binding:
  `RapidRBF/InstrumentedFaerCandidateExecutionBinding/v1/1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6`.
- Four-host lane contract:
  `d6edbf73cc9788dfb56eedc58010ce3b091d94014111a6a4b1f1171cc8f7c5a3`.
- Frozen per-source/lane/control plan:
  [`factor-qualification-plan.v1.json`](factor-qualification-plan.v1.json).

`prepare_bundle.py` mechanically derives the plan from the admitted raw
manifest and lock. It keeps all 216 source identities while storing
byte-identical matrices only once by SHA-256. The transport bundle is not a
factor store and has no acceptance authority beyond the hashes already frozen
in the plan.

## What one lane proves

For every factor source, one lane:

1. verifies source, profile, binding, plan, target, and lane metadata before
   backend entry;
2. denies an exact N-minus-one grant before permit acquisition, allocation,
   or backend entry;
3. reconstructs and externally compares the candidate factor;
4. solves three deterministic manufactured RHS families and certifies their
   backward and solution errors;
5. atomically publishes a private prototype factor pack, closes positive
   reload, and rejects truncated, corrupt, wrong-source, wrong-profile, and
   metadata-mismatch controls;
6. observes exact candidate allocation/high-water/cleanup and caller-owned
   worker/permit limits; and
7. separately cancels a replacement factor and replacement solve while
   preserving the prior validated factor and solved correction.

The factor, a possible `RunScopedRecomputeRecipe`, and solved-correction
publication are separate states. The recompute recipe is eligible only when
durable pack/reload is the sole nonpassing gate, owns a retained source lease,
and consumes one token from a single non-copyable
`RunRecomputeBudget(216)`. A passing private pack path leaves the recipe
disabled.

Every target and lane is non-compensating. The cohort returns
`ADMITTED_FOR_MECHANISM_PANEL` only when every required observation passes;
otherwise it returns an exact `NOT_ADMITTED_DIAGNOSTIC_ONLY` disposition.

The captured cohort and its decision are summarized in
[`observed-results.md`](observed-results.md).

## Prepare the immutable input bundle

Point at one verified reproduction of the admitted hierarchy corpus:

```powershell
python tools/prototypes/instrumented_faer_corpus_qualification_throwaway/prepare_bundle.py `
  --corpus-root "$env:RAPIDRBF_HIERARCHY_CORPUS" `
  --plan-output tools/prototypes/instrumented_faer_corpus_qualification_throwaway/factor-qualification-plan.v1.json `
  --bundle-output "$env:TEMP/rapidrbf-factor-qualification-input-v1.zip"
```

The committed `transport-manifest.v1.json` binds the exact archive supplied
to the four native GitHub-hosted jobs.

## Review the captured state

After the workflow evidence has been archived under `evidence/`:

```powershell
python tools/prototypes/instrumented_faer_corpus_qualification_throwaway/tui.py
```

For a non-interactive frame:

```powershell
python tools/prototypes/instrumented_faer_corpus_qualification_throwaway/tui.py --snapshot
```
