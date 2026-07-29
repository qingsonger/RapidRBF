# Observed result

## Disposition

`NOT_ADMITTED_DIAGNOSTIC_ONLY`

The exact issue-42 instrumented in-process faer binding is **not** admitted to
the mechanism panel. The frozen health thresholds were not changed.

The authoritative cohort is GitHub Actions
[run 30434309514](https://github.com/qingsonger/RapidRBF/actions/runs/30434309514),
attempt 1, at commit
`6c17cd0a60b031a8a908f59b36ca501c4346960f`. Its archived
`cohort-summary.json` is 122,733 bytes with SHA-256
`2c3452465aca518e90c105b2b4acf2c4fcae09ad994b4ac270829cc6ef61cff6`.

## Stable finding

Each of the 12 target/profile observations saw all 216 planned factor sources:

- 46 passed and published a `QualifiedFactorAccess`;
- 170 failed;
- the failed ordinal set was identical in all 12 observations; and
- every failure was a projected source in `M2-TH3`, `M3-HERMITE`, or
  `M4-GEOMETRY`.

For all 170 failures, reconstruction and backward error remained within their
frozen thresholds. Only the positive pack/reload solution-relative check was
outside its frozen limit. Observed failing values ranged from
`5.0372372939477827e-11` to `2.171678472185104e-4`, or approximately
`1.18x` to `9.44e6x` the source-specific threshold. All 12 `coarse_p_top`
sources and all 34 `M1-EXP` projected sources passed.

## Non-compensating controls

All 12 observations passed all of these controls:

- exactly 216 N-minus-one denials, with no candidate operation or backend
  entry;
- truncated, corrupt, wrong-source, wrong-profile, and metadata-mismatch pack
  reload rejection, with no backend entry;
- mid-factor and mid-solve typed cancellation after backend entry, preserving
  the prior factor and solved correction and publishing no failed result;
- positive pack/reload and pack removal for every passing source;
- zero transient residue and zero scratch residue; and
- the registered caller-owned thread grants with no sampling errors.

| Target | Workers | Observed threads | Grant | Samples |
| --- | ---: | ---: | ---: | ---: |
| Linux x86_64 glibc | 1 | 2 | 12 | 11,812 |
| Linux x86_64 glibc | 2 | 3 | 12 | 6,426 |
| Linux x86_64 glibc | 8 | 9 | 16 | 4,464 |
| macOS ARM64 | 1 | 2 | 12 | 2,509 |
| macOS ARM64 | 2 | 3 | 12 | 1,425 |
| macOS ARM64 | 8 | 9 | 16 | 1,153 |
| macOS x86_64 | 1 | 2 | 12 | 7,787 |
| macOS x86_64 | 2 | 3 | 12 | 4,591 |
| macOS x86_64 | 8 | 9 | 16 | 2,714 |
| Windows x86_64 | 1 | 4 | 12 | 2,021 |
| Windows x86_64 | 2 | 5 | 12 | 1,008 |
| Windows x86_64 | 8 | 11 | 16 | 191 |

## Decision boundary

This result rejects admission of this exact binding across the admitted
216-factor corpus. It does not select or reject a Krylov/RAS mechanism, define
a durable factor store, or qualify the 100k rung.

The complete target observations, candidate records, lane witnesses, digest
sidecars, and cohort report are archived under [`evidence/`](evidence/).
The earlier official attempts and why each was retained are recorded in
[`pre-observation-attempt-ledger.v1.json`](pre-observation-attempt-ledger.v1.json).
