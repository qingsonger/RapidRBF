# Captured issue-47 evidence

The complete official cohort returned
`NOT_ADMITTED_DIAGNOSTIC_ONLY`. The concise verdict is
`verdict.v1.json`; `attempt-ledger.v1.json` preserves the invalid first
controller attempt and the complete replacement attempt without mixing them.

The 46-file primary evidence archive is published as
[`rapidrbf-issue47-repaired-factor-requalification-evidence-v1.zip`](https://github.com/qingsonger/RapidRBF/releases/download/issue-47-repaired-factor-requalification-evidence-v1/rapidrbf-issue47-repaired-factor-requalification-evidence-v1.zip).
It is 32,875,345 bytes with SHA-256
`b38870fedb17886c105d9162ac79ed81661a4a1f8428d6a80f627ddaf37e96a1`.

After extracting the archive, review the full 12,144-coordinate judgment with:

```text
python tools/prototypes/repaired_factor_requalification_throwaway/tui.py <extracted-path>/cohort-summary.json
```

The live reviewer accepted the prototype result and ratified the single
complete replacement attempt under the frozen retry rule on 2026-07-29.
