# THROWAWAY TASK ASSET — instrumented-faer feasibility lanes

This asset provisions and qualifies the four native host lanes required by
[Provision the four qualified instrumented-faer feasibility lanes](https://github.com/qingsonger/RapidRBF/issues/43).
It does not contain, build, or execute the candidate from
[Materialize the exact instrumented faer candidate binding](https://github.com/qingsonger/RapidRBF/issues/42),
and it cannot return the feasibility disposition owned by
[Execute the frozen two-factor instrumented faer feasibility gate](https://github.com/qingsonger/RapidRBF/issues/44).

## Provisioned lanes

| Lane | Native target | Fixed runner label |
| --- | --- | --- |
| Windows x86_64 | `x86_64-pc-windows-msvc` | `windows-2025` |
| Linux x86_64 glibc | `x86_64-unknown-linux-gnu` | `ubuntu-24.04` |
| macOS arm64 | `aarch64-apple-darwin` | `macos-15` |
| macOS x86_64 | `x86_64-apple-darwin` | `macos-15-intel` |

The labels are deliberately versioned rather than `*-latest`. A lane witness is
still qualified per concrete job, not forever: it records the runner image
version, OS, native Rust host, CPU identity and features, toolchain identity,
and GitHub run identity. Cross-compilation has no evidence authority.
`ImageOS` and `ImageVersion` are useful fail-closed runtime fields but are not
the sole image authority; the final evidence bundle must also retain each job's
`Set up job` log and Included Software link.

## Isolation and access

- Each lane is a separate fresh GitHub-hosted job. No dependency cache,
  workspace cache, service container, or cross-job writable state is used.
- Checkout is read-only and does not persist credentials. The workflow has only
  `contents: read`.
- The repository is public and GitHub Actions is enabled. No repository Actions
  secret or variable is needed. GitHub issues a job-scoped `GITHUB_TOKEN`; the
  workflow never prints or copies it.
- An operator triggers or downloads a run through the repository Actions page
  or an authenticated `gh` session. The operator credential remains in the
  operator's GitHub/OS credential store and is not an evidence input.
- Every lane uses `RUNNER_TEMP` for scratch and verifies write/delete cleanup.
  The later two-factor gate must put its Cargo target, probe scratch, and all
  transient evidence below the same isolated root and must not use Actions
  caches.
- Standard hosted-runner capacity is sufficient only for this bounded native
  two-factor portability probe. It does not satisfy the separately frozen
  eight-physical-core, 64 GiB-memory, 512 GiB-scratch million-scale envelope
  and has no authority to judge performance parity or million-scale release
  gates.

The repository-side settings snapshot used for this task is
[`repository-actions-snapshot.v1.json`](inputs/repository-actions-snapshot.v1.json).

## Qualification

The preflight workflow compiles and executes a native Rust smoke binary on each
host, then checks:

1. GitHub-hosted execution and the expected `RUNNER_OS` / `RUNNER_ARCH`;
2. exact equality between the lane's required target and `rustc -vV` host;
3. the expected native machine architecture and compiled executable header;
4. versioned image identity and usable isolated scratch;
5. glibc identity on Linux; and
6. AVX2 and FMA on x86_64 lanes, because the frozen plan selects the
   `private-gemm-x86` path only on such a host.

The preflight proves that a real native lane is available and can compile and
run Rust. It intentionally does not claim that the not-yet-materialized
instrumented fork builds or satisfies its execution controls.

## Evidence transport

Each lane uploads a 90-day artifact containing:

- `lane-identity.json`;
- `lane-identity.json.sha256`; and
- no repository credential, host path, or candidate result.

The cohort job downloads only artifacts from the same workflow run attempt,
requires all four non-compensating witnesses, and uploads a separate aggregate
summary. This is a public repository, so the run logs and artifacts are not a
secret transport; the collector therefore allowlists identity fields instead
of copying the environment. Retrieve an attempt with:

```powershell
gh run download <run-id> --dir <new-empty-directory>
```

Issue 44 must copy the final complete evidence bundle into an immutable
hash-bound task asset before the 90-day transport artifacts expire. Artifact
retention is transport, not durable authority. That capture must include the
run/job metadata and job logs obtained through GitHub's Actions APIs, not only
the uploaded JSON.

## Retry invalidation

One evidence cohort is exactly one `(GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT,
GITHUB_SHA, lane-contract hash)` tuple.

- Witnesses from different run attempts must never be combined.
- A partial rerun invalidates the quartet for disposition purposes; rerun all
  four lanes as a new attempt.
- Only an infrastructure failure before candidate entry may authorize a retry.
  The retry reason must be recorded before the new attempt.
- Once a future run reaches candidate entry, any failure or cancellation is an
  observation. It cannot be discarded as runner noise without a separate
  evidence-backed adjudication.
- Old attempts remain evidence and are linked alongside the accepted attempt.

The preflight contains no candidate-entry event. Issue 44 must freeze the
candidate binding hash, plan hash, resource schedule, checkpoint schedule, and
retry authorization before adding that event to the shared lane runner.
