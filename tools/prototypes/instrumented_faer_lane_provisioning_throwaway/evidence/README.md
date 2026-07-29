# Qualified lane evidence

## Result

The four native GitHub-hosted feasibility lanes are provisioned and qualified
for the bounded two-factor functional probe:

| Lane | Runner label | Observed image | Witness SHA-256 |
| --- | --- | --- | --- |
| Windows x86_64 | `windows-2025` | `windows-2025-vs2026` / `20260714.173.1` | `fade0f5a07c90fe3a3594515037b746e6a1dad861aa55fc203a7b268c986004e` |
| Linux x86_64 glibc | `ubuntu-24.04` | `ubuntu-24.04` / `20260720.247.2` | `87ac741420b0ba8a77fc19b7961c7e6f6c5635d68fc4eb5674545d9cdbfc6935` |
| macOS arm64 | `macos-15` | `macos-15-arm64` / `20260715.0234.1` | `45db90a25b5046b429576054771b54eed4bfa7ecd9bb650ea9f08d49f2f40a72` |
| macOS x86_64 | `macos-15-intel` | `macos-15` / `20260720.0353.1` | `aac16fa85d99aeac27929d9436ecc7b48ebc30ba281d7a14afbfc91e3358ae69` |

The accepted cohort is
[GitHub Actions run 30420466293](https://github.com/qingsonger/RapidRBF/actions/runs/30420466293),
attempt 1, at commit
[`af55916ce8845fc803976e97642723893afe24c9`](https://github.com/qingsonger/RapidRBF/commit/af55916ce8845fc803976e97642723893afe24c9).

- Lane contract SHA-256:
  `d6edbf73cc9788dfb56eedc58010ce3b091d94014111a6a4b1f1171cc8f7c5a3`.
- Cohort ID:
  `969a79cf2dbebdea15602854003fd394bd75dd9241a34fd81880f295446c5b9a`.
- Every lane compiled and executed a native Rust binary whose host triple and
  binary header matched the required target.
- Linux recorded glibc; every x86_64 lane observed AVX2 and FMA.
- All qualification checks passed. No candidate binding was loaded, backend
  calls remained zero, and factor publications remained zero.

## Durable capture

[`run-30420466293-attempt-1`](run-30420466293-attempt-1) contains:

- the five extracted GitHub artifact payloads;
- the exact five service artifact ZIP files;
- GitHub REST run, job, and artifact metadata;
- the complete Actions run-log ZIP, including every `Set up job` image and
  Included Software link; and
- file-level checksums in [`checksums.sha256`](checksums.sha256).

All five service ZIP SHA-256 values match the `digest` values in
`artifacts.json`. Every extracted lane and cohort JSON matches its adjacent
checksum. The run-log ZIP was opened and its five job log trees enumerated.

GitHub's transport artifacts expire on 2026-10-27. This committed,
content-addressed capture is the durable authority after that date.

## Retry ledger

[`attempt-ledger.v1.json`](attempt-ledger.v1.json) retains all runs:

- the first workflow was rejected before job creation because `runner.temp`
  was referenced outside an allowed context;
- the next run qualified all four lanes but emitted the platform's forced
  Node 20-to-24 migration warning; and
- the accepted run repeated the full quartet after every official action was
  pinned to a native Node 24 release.

No run crossed candidate entry. Evidence from different run IDs was not
combined, and only the final same-run cohort is accepted.

## Boundary

This evidence qualifies native host, isolation, identity, toolchain, artifact,
and retry surfaces for the later two-factor gate. It does not qualify the exact
instrumented-faer binding, execute either factor, prove allocation or
cancellation behavior, return a feasibility disposition, replay the 216-factor
corpus, or provide million-scale/performance authority.
