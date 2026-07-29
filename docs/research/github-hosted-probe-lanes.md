# GitHub-hosted native probe lanes

Status: resolved bounded research for the Wayfinder map

Captured: 2026-07-29

Scope: standard GitHub-hosted runners for a public repository; no larger,
self-hosted, or container runners

## Answer

RapidRBF can run four isolated, host-native functional probe jobs on standard
GitHub-hosted runners:

| Product lane | `runs-on` | GitHub architecture | Expected Rust host triple | Public-runner resources |
|---|---|---|---|---|
| Windows x86_64 | `windows-2025` | x64 | `x86_64-pc-windows-msvc` | 4 CPU, 16 GB RAM, 14 GB SSD |
| Linux x86_64 glibc | `ubuntu-24.04` | x64 | `x86_64-unknown-linux-gnu` | 4 CPU, 16 GB RAM, 14 GB SSD |
| macOS arm64 | `macos-15` | arm64, M1 | `aarch64-apple-darwin` | 3 CPU, 7 GB RAM, 14 GB SSD |
| macOS x86_64 | `macos-15-intel` | Intel/x64 | `x86_64-apple-darwin` | 4 CPU, 14 GB RAM, 14 GB SSD |

**Fact.** All four labels and architectures are in GitHub's public-repository
standard-runner table. Standard hosted-runner use is free and unlimited for
public repositories. The pinned GitHub Docs source records Linux x64 and
Windows x64 at
[`e1e4aa9`, lines 18-43](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/data/reusables/actions/supported-github-runners.md#L18-L43)
and both macOS architectures at
[lines 67-90](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/data/reusables/actions/supported-github-runners.md#L67-L90).

**Recommendation.** Use exactly the four versioned labels above. Do not use
`windows-latest`, `ubuntu-latest`, or `macos-latest`. Each lane must checkout,
build, inspect, and execute its own binary in one job. Artifacts are evidence
leaving a completed lane, not a way to import a binary built by another lane.

**Limitation.** These are compatibility and functional probe hosts, not
performance authorities. Their published CPU, memory, and storage resources do
not satisfy a gate that requires 8 physical cores, 64 GiB RAM, or 512 GiB
scratch space. Hosted image and hardware drift also prevent stable performance
host identity. A standard GitHub-hosted job also has a six-hour maximum
execution time
([Actions limits](https://docs.github.com/en/actions/reference/limits#job-execution-time)).
Do not infer performance parity from timings across these jobs.

## Evidence policy and provenance

This document uses these labels:

- **Fact**: directly supported by a linked GitHub document, GitHub-owned
  source repository, or read-only GitHub REST response.
- **Inference**: a conclusion drawn from one or more facts.
- **Recommendation**: the proposed RapidRBF protocol.
- **Unknown**: not guaranteed by the cited evidence and requiring a real
  workflow run or a later policy check.

The two source snapshots used for time-sensitive claims are:

- GitHub Docs
  [`e1e4aa937308f21c411c248b4966873536bb0cba`](https://github.com/github/docs/commit/e1e4aa937308f21c411c248b4966873536bb0cba),
  committed 2026-07-28;
- `actions/runner-images`
  [`f46f8afc002f4a9748081785f1fed2e3be5a56d9`](https://github.com/actions/runner-images/commit/f46f8afc002f4a9748081785f1fed2e3be5a56d9),
  committed 2026-07-28.

The rendered [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
remains the operational authority. The pinned sources make this research
auditable after that page changes.

## What is pinned and what is only auditable

### Labels, OS generations, and architecture

**Fact.** At the pinned `runner-images` revision, the official image mapping is:

- `ubuntu-24.04` is Ubuntu 24.04 x64;
- `windows-2025` is Windows Server 2025 x64;
- `macos-15` is macOS 15 arm64; and
- `macos-15-intel` is macOS 15 x64.

The mappings are visible in the official
[`runner-images` table](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/README.md#L21-L40).
The `-large` and `-xlarge` macOS suffixes belong to larger runners and are not
part of this standard-runner design
([label scheme](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/README.md#L42-L46)).

**Fact.** A versioned runner label pins an OS/image family, not an immutable VM
image build. GitHub normally updates GA images weekly
([policy](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/README.md#L80-L97),
[deployment cadence](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/README.md#L99-L114)).
The `*-latest` labels can migrate over one to two months, during which different
jobs can receive different OS versions.

**Recommendation.** Pin the OS generation with the selected versioned labels,
then audit the actual assigned image on every run. Never describe a label alone
as a reproducible machine identity.

**Unknown.** GitHub publishes no standard-runner scheduling syntax that selects
an immutable image build ID, physical CPU model, microcode, or virtualization
host. Label lifetime beyond the current support table is also not guaranteed.
`windows-2022` remains a supported x64 fallback as of the capture date, but it
is not the selected lane.

### Research-time image snapshot

The following values are facts about the pinned repository revision, not a
promise about the VM assigned to a future job:

| Lane | Snapshot recorded by the official image README |
|---|---|
| `windows-2025` | Windows `10.0.26100`, build `33158`, image `20260719.202.1` ([source](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/windows/Windows2025-Readme.md#L5-L7)) |
| `ubuntu-24.04` | Ubuntu `24.04.4 LTS`, kernel `6.17.0-1020-azure`, image `20260720.247.2` ([source](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/ubuntu/Ubuntu2404-Readme.md#L6-L10)) |
| `macos-15` | macOS `15.7.7 (24G720)`, Darwin `24.6.0`, image `20260715.0234.1` ([source](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/macos/macos-15-arm64-Readme.md#L7-L10)) |
| `macos-15-intel` | macOS `15.7.7 (24G720)`, Darwin `24.6.0`, image `20260720.0353.1` ([source](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/macos/macos-15-Readme.md#L8-L11)) |

**Fact.** GitHub says the authoritative way to learn the image and software
used by a specific job is its `Set up job` log
([runner-images FAQ](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/README.md#L195-L200)).
The image source also sets `ImageVersion` and `ImageOS` on
[Ubuntu](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/ubuntu/scripts/build/configure-environment.sh#L11-L13),
[Windows](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/windows/scripts/build/Configure-SystemEnvironment.ps1#L6-L15),
and [macOS](https://github.com/actions/runner-images/blob/f46f8afc002f4a9748081785f1fed2e3be5a56d9/images/macos/scripts/build/configure-preimagedata.sh#L27-L44).

**Recommendation.** Save the selected label, `ImageOS`, `ImageVersion`, and
the `Set up job` image-release and included-software links in the lane manifest.
Treat `ImageOS` and `ImageVersion` only as corroborating runtime evidence. The
`Set up job` log is authoritative if an environment variable is missing or
differs.

## Host-native execution protocol

**Fact.** GitHub provisions a new VM per standard hosted-runner job. All steps
in that job share its filesystem, and GitHub decommissions the VM when the job
finishes
([pinned documentation](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/content/actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners.md#L23-L33)).
GitHub supplies `RUNNER_OS`, `RUNNER_ARCH`, and `RUNNER_ENVIRONMENT`;
`RUNNER_ARCH` can be `X86`, `X64`, `ARM`, or `ARM64`
([variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables#default-environment-variables)).

**Inference.** A runner label proves the host family and advertised
architecture, but does not prove that a compiler was not passed a cross target.
The produced binary and the process that actually ran must close that evidence
gap.

**Recommendation.** A lane is accepted as host-native only when all of the
following pass in the same job:

1. `RUNNER_ENVIRONMENT` is `github-hosted`.
2. `RUNNER_OS` and `RUNNER_ARCH` match the lane table.
3. The OS reports the expected machine architecture.
4. `rustc -vV` reports the expected host triple.
5. The build command omits a cross target or names only that expected host
   triple.
6. The final binary header reports the expected architecture and platform
format.
7. That exact binary executes successfully on the same host.
8. Only after execution succeeds are the binary, logs, and manifest uploaded.

The minimum platform-specific evidence is:

| Lane | Host and runtime evidence | Binary evidence |
|---|---|---|
| Windows x86_64 | `RUNNER_ARCH=X64`; Windows build; CPU model; `rustc -vV` host `x86_64-pc-windows-msvc` | PE/COFF machine from `llvm-readobj --file-headers`; linked runtime inventory; successful execution |
| Linux x86_64 glibc | `RUNNER_ARCH=X64`; `uname -m=x86_64`; `/etc/os-release`; CPU model/features; `getconf GNU_LIBC_VERSION`; `ldd --version`; Rust host `x86_64-unknown-linux-gnu` | ELF machine, interpreter, `NEEDED` entries, and required `GLIBC_*` symbol versions from `readelf`; successful execution |
| macOS arm64 | `RUNNER_ARCH=ARM64`; `uname -m=arm64`; `sw_vers`; CPU/model facts; Rust host `aarch64-apple-darwin` | Mach-O architecture from `file` and `lipo -archs`; dependencies from `otool -L`; successful execution |
| macOS x86_64 | `RUNNER_ARCH=X64`; `uname -m=x86_64`; `sw_vers`; CPU/model facts; Rust host `x86_64-apple-darwin` | Mach-O architecture from `file` and `lipo -archs`; dependencies from `otool -L`; successful execution |

**Recommendation.** Do not declare `container:` on the Linux job. A container
would introduce another OS/libc boundary. Do not download another lane's
binary before the native execution gate. A later aggregation job may download
only completed evidence and must not execute foreign-lane binaries.

**Unknown until runtime.** The exact glibc version and the final binary's
glibc symbol floor are not guaranteed by `ubuntu-24.04`. The current image
README establishes Ubuntu x64 and lists GNU/Clang toolchains, but the actual
job must record `getconf`, `ldd`, the ELF interpreter, dynamic dependencies,
and version requirements. An Ubuntu host does not prevent a workflow from
deliberately producing a musl, static, or cross-compiled binary.

**Unknown until runtime.** The public-runner table promises x64 architecture,
CPU count, memory, and storage; it does not promise a CPU model or AVX2/FMA
instruction support. No reviewed GitHub source provides an AVX2/FMA label SLA.

**Recommendation.** If an x86_64 RapidRBF lane requires AVX2 and FMA, detect
both from the running process before building or probing and record the raw
CPU-feature evidence. A missing required feature makes that job
`UNQUALIFIED`, not a negative product result and not evidence about the next VM
assigned to the same label.

## Isolation and evidence transfer

**Fact.** The isolation boundary is the job, not the step: steps in one job
share a VM filesystem, while separate jobs receive separate VMs
([GitHub-hosted runner lifecycle](https://docs.github.com/en/actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners)).
No filesystem state should be expected to survive into an aggregation job.

**Recommendation.**

- Implement the four lanes as four jobs.
- Let every lane independently checkout the same `GITHUB_SHA` and build from
  source.
- Keep probe inputs in the checkout or verify their content hashes.
- Do not use a shared binary cache as probe evidence. If a dependency cache is
  later enabled, record its key and hit state and never cache final probe
  binaries.
- Use workflow artifacts only to move completed reports, manifests, logs, and
  outputs into an optional aggregation job.

## Artifact integrity, visibility, and retention

**Fact.** GitHub's `upload-artifact` and `download-artifact` actions transfer
data between jobs. Current-generation artifacts are immutable, upload returns a
SHA-256 digest, and download recalculates and validates it
([pinned `upload-artifact` behavior](https://github.com/actions/upload-artifact/blob/ea165f8d65b6e75b540449e92b4886f43607fa02/README.md#L49-L57),
[official digest tutorial](https://docs.github.com/en/actions/tutorials/store-and-share-data#validating-artifacts)).
A digest mismatch is a warning in the UI and job log, so a RapidRBF aggregation
step must make any mismatch fatal rather than relying on the default warning.

**Fact.** Workflow artifacts and logs default to 90-day retention. Public
repositories may configure 1 to 90 days; a per-artifact `retention-days` value
cannot exceed the repository, organization, or enterprise limit
([pinned retention policy](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/data/reusables/actions/about-artifact-log-retention.md#L1-L12),
[per-artifact setting](https://docs.github.com/en/actions/tutorials/store-and-share-data#configuring-a-custom-artifact-retention-period)).
Deleting a workflow run also deletes its artifacts
([GitHub Docs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts#artifacts-from-deleted-workflow-runs)).

**Fact.** The Actions artifact REST representation includes `id`, `digest`,
`expired`, `created_at`, `expires_at`, and the workflow run's `head_sha`.
Public resources can be read without authentication
([REST artifact endpoints](https://docs.github.com/en/rest/actions/artifacts?apiVersion=2026-03-10)).
Probe artifacts in this public repository must therefore be treated as public.

**Recommendation.**

- Give every lane a unique artifact name containing the lane, `GITHUB_SHA`,
  `GITHUB_RUN_ID`, and `GITHUB_RUN_ATTEMPT`.
- Retain the artifact ID, URL, service digest, expiration time, head SHA, and
  file-level SHA-256 hashes in the aggregation manifest.
- Set an explicit retention period. Use 30 days for routine probes and 90 days
  for decision or release-candidate probes unless project policy chooses a
  different value.
- Do not use workflow artifacts as permanent release or baseline storage.
- Never include credentials, a complete environment dump, home-directory
  content, `.env` files, or unreviewed hidden files.

## Token and credential boundary

**Fact.** GitHub creates a unique `GITHUB_TOKEN` for each job. It is a GitHub
App installation token whose permissions are limited to the workflow's
repository, and it expires when the job finishes or reaches its maximum
lifetime
([pinned source](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/content/actions/concepts/security/github_token.md#L15-L24)).
An action can access `github.token` even when the workflow does not explicitly
pass the token
([GitHub Docs](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)).

**Fact.** The `permissions` key can reduce token access at workflow or job
scope. Once any permission is specified, unspecified permissions become
`none`; `permissions: {}` disables them all
([pinned permission syntax](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/data/reusables/actions/github-token-available-permissions.md)).
For forked `pull_request` workflows, GitHub normally reduces write permissions
to read, whereas `pull_request_target` is privileged and can expose a
repository when it executes untrusted code
([permission calculation](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/content/actions/reference/workflows-and-actions/workflow-syntax.md#L276-L286),
[secure-use warning](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/content/actions/reference/security/secure-use.md#L111-L137)).

**Recommendation.**

- Declare `permissions: contents: read`; do not depend on repository defaults.
- Set `persist-credentials: false` on `actions/checkout`. Checkout otherwise
  persists its token for later Git commands
  ([official checkout README](https://github.com/actions/checkout/blob/f548e57e544e1ff5a4c46bf1e1b8685f8e4a348a/README.md#L29-L35)).
- Inject no PAT, publishing credential, cloud credential, environment secret,
  or OIDC permission into probe jobs.
- Trigger untrusted contribution probes with `pull_request`, never
  `pull_request_target`.
- Pin every referenced action to a verified full-length commit SHA; GitHub
  describes that as the only immutable action reference
  ([secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions)).
- Regard every action and step in a job as inside that job's token boundary.
  There is no step-level credential isolation.

## Required identity manifest

**Fact.** GitHub provides stable per-run variables including `GITHUB_SHA`,
`GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `RUNNER_OS`, `RUNNER_ARCH`, and
`RUNNER_ENVIRONMENT`
([pinned variable table](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/content/actions/reference/workflows-and-actions/variables.md#L52-L78)).
GitHub warns against printing the complete `github` context because it contains
sensitive information
([contexts reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#example-printing-context-information-to-the-log)).

**Recommendation.** Each lane should write a machine-readable manifest with at
least:

- repository, workflow ref/SHA, tested `GITHUB_SHA`, run ID, attempt, event,
  and job/lane name;
- requested `runs-on` label, `RUNNER_OS`, `RUNNER_ARCH`,
  `RUNNER_ENVIRONMENT`, and runner name;
- image name/version, included-software URL, and image-release URL from
  `Set up job`;
- OS version, kernel or Windows build, CPU vendor/model/features, logical CPU
  count, memory, and free disk;
- Rust, Cargo, compiler, linker, CMake, and other exercised tool versions;
- compiler host and target triples, build profile, features, flags, and
  dependency lock hash;
- final file hashes, executable format/architecture, dynamic dependencies,
  probe inputs, outputs, exit code, and elapsed time;
- Linux host glibc version, ELF interpreter, and binary `GLIBC_*`
  requirements.

Record selected fields, not the whole process environment or context objects.

## macOS public-runner availability and restrictions

**Fact.** Both selected macOS lanes are standard public-repository runners:
`macos-15` is an arm64 M1 VM with 3 CPU and 7 GB RAM, while
`macos-15-intel` is an Intel VM with 4 CPU and 14 GB RAM. Both have 14 GB SSD
([public-runner table](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for-public-repositories)).

**Fact.** `macos-26` and `macos-26-intel` are also current GA standard-runner
alternatives for arm64 and x64 respectively
([GitHub announcement](https://github.blog/changelog/2026-02-26-macos-26-is-now-generally-available-for-github-hosted-runners/),
[pinned public-runner table](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/data/reusables/actions/supported-github-runners.md#L67-L90)).
They are not the lanes selected for this task. Keeping both macOS probes on
version 15 holds the OS generation constant across architectures; any move to
version 26 is a later contract change, not an automatic `*-latest` migration.

**Fact.** GitHub documents these arm64 macOS limitations:

- GitHub-provided actions are compatible, but community actions may not be;
- nested virtualization is unavailable;
- arm64 runners have no static UUID/UDID; and
- Intel macOS runners have a static UDID documented by GitHub.

The pinned source is
[`macos-runner-limitations.md`](https://github.com/github/docs/blob/e1e4aa937308f21c411c248b4966873536bb0cba/data/reusables/actions/macos-runner-limitations.md#L1-L4).
Its networking restriction is specifically about macOS larger runners and is
not a reason to replace these standard lanes.

**Recommendation.** Use only GitHub-owned or source-audited, SHA-pinned actions
on arm64. Do not require nested virtualization or a fixed arm64 UDID. Do not
compare arm64 and Intel wall times as if the hosts had equal resources.

**Unknown.** Current availability does not guarantee indefinite Intel runner
support. Re-check the public-runner table and `runner-images` deprecation
announcements before every release-series change.

## RapidRBF repository snapshot

The following are read-only facts captured from GitHub REST on 2026-07-29, not
platform guarantees:

| Endpoint | Captured response |
|---|---|
| [`GET /repos/qingsonger/RapidRBF`](https://api.github.com/repos/qingsonger/RapidRBF) | public repository |
| [`GET /repos/qingsonger/RapidRBF/actions/permissions`](https://api.github.com/repos/qingsonger/RapidRBF/actions/permissions) | Actions enabled; all actions allowed; SHA pinning not required by repository policy |
| [`GET /repos/qingsonger/RapidRBF/actions/permissions/workflow`](https://api.github.com/repos/qingsonger/RapidRBF/actions/permissions/workflow) | default workflow permission `read`; workflows cannot approve pull-request reviews |
| [`GET /repos/qingsonger/RapidRBF/actions/permissions/artifact-and-log-retention`](https://api.github.com/repos/qingsonger/RapidRBF/actions/permissions/artifact-and-log-retention) | retention `90` days; maximum `90` days |
| [`GET /repos/qingsonger/RapidRBF/actions/artifacts`](https://api.github.com/repos/qingsonger/RapidRBF/actions/artifacts) | `total_count: 0` |

**Recommendation.** Encode least privilege and full-SHA action pins in the
workflow itself even though the current repository does not enforce SHA
pinning. Repository settings can change independently of workflow history.

## Final boundary

These four lanes can establish that the same RapidRBF commit builds and runs on
four fresh, advertised host architectures with auditable OS, image, toolchain,
binary, and runtime evidence. They cannot establish an immutable hosted image,
a fixed physical CPU, cross-run performance comparability, or non-cross
compilation from the runner label alone. The per-run manifest, `Set up job`
log, binary inspection, and successful same-host execution are mandatory parts
of the proof.
