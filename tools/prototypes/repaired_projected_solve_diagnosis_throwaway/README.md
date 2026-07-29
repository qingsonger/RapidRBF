# Repaired projected-solve diagnosis — throwaway prototype

This logic prototype answers one decision question from
[Diagnose the repaired projected-solve failures and freeze the next dense-factor experiment](https://github.com/qingsonger/RapidRBF/issues/48):
what candidate-owned mechanism remains after the accepted issue-47 evidence is
reduced to a boundary-complete witness set, and what one bounded experiment
should run next?

It does not rerun or mutate the issue-47 cohort. It does not admit faer, a
factor path, the factor corpus, or a new dependency; run the mechanism panel;
select persistent factor storage; or enter the 100k rung.

The committed witness subset is derived from the immutable issue-47 release
archive and the accepted issue-45 comparison evidence. It contains:

- one passing projected control;
- M2-TH3 failures at the 1k and smallest-dimension 10k boundaries;
- the repaired M3-HERMITE 1k pass boundary;
- the ordinal-106 M3-HERMITE partial-family exception; and
- the M4-GEOMETRY worst-boundary witness.

## One-command review

From the repository root:

```text
python tools/prototypes/repaired_projected_solve_diagnosis_throwaway/tui.py --snapshot
```

For an interactive review:

```text
python tools/prototypes/repaired_projected_solve_diagnosis_throwaway/tui.py
```

The reviewer keeps state only in memory and prints the complete review state
after every action.

## Tight red loop

The issue-47 symptom can be replayed in seconds:

```text
python tools/prototypes/repaired_projected_solve_diagnosis_throwaway/run.py --require-current-candidate-admitted
```

It intentionally exits non-zero because the selected issue-47 witnesses
contain candidate-owned frozen-system forward-solution failures while their
reconstruction and reduced-backward-error gates pass.

## Re-derive the committed subset

`prepare.py` verifies the 32,875,345-byte issue-47 archive against SHA-256
`b38870fedb17886c105d9162ac79ed81661a4a1f8428d6a80f627ddaf37e96a1`,
then extracts only the six selected logical-source records from all twelve
target/profile observations and their candidate-independent references.

```text
python tools/prototypes/repaired_projected_solve_diagnosis_throwaway/prepare.py <issue-47-release-archive.zip> <issue-41-factor-qualification-plan.v1.json> <issue-45-diagnosis-evidence.json>
```

The full archive and cohort are read-only inputs and are never rewritten.
