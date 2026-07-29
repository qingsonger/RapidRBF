# Repaired factor requalification — throwaway prototype

This prototype answers one frozen question: can the exact issue-41
instrumented-faer binding pass the repaired, candidate-independent
solution-health authority over all 216 logical factor sources, all three
worker profiles, and all four native targets in one non-compensating cohort?

The reference phase consumes only the frozen issue-41 bundle, plans, repaired
authority, and its own crates.io-locked source/dependency closure. It completes
before any candidate entry. Every target/profile then reuses the exact same
certified reference-manifest SHA-256. The final result is exactly one of:

- `ADMITTED_FOR_MECHANISM_PANEL`
- `NOT_ADMITTED_DIAGNOSTIC_ONLY`, with exact nonpassing coordinates
- `INVALID_UNJUDGED`, with frozen retry semantics

This is throwaway evidence code, not a production solver or storage design. It
does not adopt faer, mutate issue-41 evidence, run the mechanism panel, select
factor storage, or enter the 100k rung.

## Run the full frozen cohort

From a pushed branch, one command dispatches the native four-target run:

```text
gh workflow run instrumented-faer-corpus-qualification.yml --ref <branch>
```

## Review a captured judgment

Once `cohort-summary.json` has been downloaded, one command opens the
in-memory terminal reviewer:

```text
python tools/prototypes/repaired_factor_requalification_throwaway/tui.py <path-to-cohort-summary.json>
```

The reviewer never edits the judgment or writes an acceptance decision. It
surfaces the complete review state after each action so the human can accept,
request adjustment, or reject the prototype in the Wayfinder issue.
