# THROWAWAY PROTOTYPE - captured dense-factor replay

Run the interactive replay from the repository root:

```powershell
python tools/prototypes/dense_factor_replay_throwaway/tui.py
```

Print one non-interactive evidence summary:

```powershell
python tools/prototypes/dense_factor_replay_throwaway/tui.py --snapshot
```

The checked-in reaction snapshot is summarized in
[`evidence/observed-results.md`](evidence/observed-results.md); the TUI reads
the accompanying `evidence/observed-summary.json` by default.

## Canonical hierarchy successor

The Stage 0 representative corpus remains immutable. Its successor
materializes the complete registered M1-M4 1k/10k hierarchy and closes
pre-backend semantic admission:

- `capture/hierarchy_capture.cpp` writes the raw 12-workload, 204-block
  hierarchy corpus and one materialized rank-invalid control;
- `hierarchy_lock.py` independently reconstructs topology, payload metadata,
  canonical global row maps, fine-inner partitions, factor lineage, and
  control mutations before publishing an immutable lock;
- `admission/certify.py` produces the 420 rank and 204 canonical-Q
  certificates under the pinned, content-addressed `RankScalingProfile/v1`.
  Its reports bind the certifier source/dependency closure and the
  Python/NumPy/BLAS/thread runtime coordinate; and
- `evaluator/` uses the independent, content-addressed
  `PhysicalEvidenceProfile/v1` to drive its 256-bit pure-Rust directed
  arithmetic, reconstruct physical value/gradient action, bind every
  captured `Q^T A Q` entry and reduced witness to that operator, and certify
  the full `lambda=[Q_top;I]gamma` closure. Its summaries, controls, and block
  certificates bind the profile, source closure, and running executable
  identity and return nonzero after publishing any rejection diagnostics.

The normative boundary and observed result are in
[`evidence/hierarchy-admission-contract.md`](evidence/hierarchy-admission-contract.md)
and `evidence/hierarchy-admission-observed.md`. The checked-in raw manifest
and lock bind the generated 1.268 GiB payload corpus without treating those
large binary artifacts as a portable storage format.

The successor has its own `capture/hierarchy/CMakeLists.txt`; the Stage 0
`capture/CMakeLists.txt` remains byte-for-byte identical to its frozen
baseline. The observed capture coordinate was CMake 4.0.3, Visual Studio
17.14.11 (`17.14.36401.2`), MSBuild 17.14.18.37206, Windows SDK
10.0.26100.0, and ClangCL/LLD 19.1.5 targeting
`x86_64-pc-windows-msvc`. The hierarchy target applies `/Brepro` while
compiling and linking and disables incremental linking.

Reproduce the v3 successor from the repository root, using new absent or
empty corpus and result directories and the clean Polatory source tree at
`4a30beb08053fb339ce899e255be4b6d3f74aa0c`. Set
`RAPIDRBF_POLATORY_SOURCE` to that checkout before running:

```powershell
$hierarchyPrototype = Resolve-Path tools/prototypes/dense_factor_replay_throwaway
$hierarchyBuild = Join-Path $env:TEMP rapidrbf-hierarchy-build
$hierarchyCorpus = Join-Path $env:TEMP rapidrbf-hierarchy-corpus-fresh
$hierarchyResults = Join-Path $env:TEMP rapidrbf-hierarchy-results-fresh
$polatorySource = (
  Resolve-Path -LiteralPath $env:RAPIDRBF_POLATORY_SOURCE
).Path
New-Item -ItemType Directory -Force $hierarchyResults | Out-Null

cmake -S "$hierarchyPrototype\capture\hierarchy" -B $hierarchyBuild `
  -G "Visual Studio 17 2022" -A x64 -T ClangCL `
  -DPOLATORY_SOURCE_DIR="$polatorySource"
cmake --build $hierarchyBuild --config Release `
  --target rapidrbf_hierarchy_capture
$hierarchyCapture = Join-Path $hierarchyBuild `
  "Release\rapidrbf_hierarchy_capture.exe"
& $hierarchyCapture $hierarchyCorpus

python "$hierarchyPrototype\hierarchy_lock.py" $hierarchyCorpus `
  --capture-exe $hierarchyCapture --polatory-source $polatorySource
python "$hierarchyPrototype\hierarchy_lock.py" $hierarchyCorpus `
  --capture-exe $hierarchyCapture --polatory-source $polatorySource --verify

$canonicalFiles = @(
  @{
    Fresh = Join-Path $hierarchyCorpus "hierarchy.manifest.raw.json"
    Checked = Join-Path $hierarchyPrototype `
      "evidence\canonical-hierarchy.manifest.raw.json"
    Sha256 = "cf5aaa1e3fe6bf51c3f24f13455ac1036e7ec591668c18ec4c86f3243aa07f54"
  },
  @{
    Fresh = Join-Path $hierarchyCorpus "manifest.lock.json"
    Checked = Join-Path $hierarchyPrototype `
      "evidence\canonical-hierarchy.manifest.lock.json"
    Sha256 = "7abd17eabba0cd578fa8989075f9d09d5113a696df48c9643785822dadde5a75"
  }
)
foreach ($file in $canonicalFiles) {
  $freshSha = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $file.Fresh
  ).Hash.ToLowerInvariant()
  $checkedSha = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $file.Checked
  ).Hash.ToLowerInvariant()
  if ($freshSha -ne $file.Sha256 -or $checkedSha -ne $file.Sha256) {
    throw "fresh corpus differs from checked canonical evidence"
  }
}
$freshLock = Get-Content `
  (Join-Path $hierarchyCorpus "manifest.lock.json") -Raw | ConvertFrom-Json
if (
  $freshLock.corpus_sha256 -ne
  "38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79"
) {
  throw "fresh lock has a different canonical corpus digest"
}

python "$hierarchyPrototype\hierarchy_lock.py" $hierarchyCorpus `
  --capture-exe $hierarchyCapture --polatory-source $polatorySource `
  --self-test-controls `
  --output "$hierarchyResults\hierarchy-lock-controls.json"

Push-Location "$hierarchyPrototype\admission"
$env:OPENBLAS_NUM_THREADS = "16"
uv run --locked python -m unittest -v
uv run --locked python certify.py --self-test `
  --output "$hierarchyResults\hierarchy-admission-controls.json"
uv run --locked python certify.py `
  --manifest "$hierarchyCorpus\hierarchy.manifest.raw.json" `
  --output "$hierarchyResults\hierarchy-admission-report.json"
Pop-Location

Push-Location "$hierarchyPrototype\evaluator"
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
cargo run --release --locked -- controls `
  --output "$hierarchyResults\hierarchy-physical-controls.json"
cargo run --release --locked -- evaluate `
  "$hierarchyCorpus\hierarchy.manifest.raw.json" `
  --max-payload-bytes 685751487 `
  --max-pair-work 1158236153 `
  --output "$hierarchyResults\hierarchy-physical-evaluator-report.json" `
  --cert-dir "$hierarchyResults\physical-certificates"
Pop-Location

python "$hierarchyPrototype\hierarchy_lock.py" $hierarchyCorpus `
  --capture-exe $hierarchyCapture --polatory-source $polatorySource --verify
```

Reproduce the build/capture determinism claim with two different, absent
absolute roots and compare every resulting byte:

```powershell
$reproRuns = @(
  @{
    Build = Join-Path $env:TEMP rapidrbf-hierarchy-repro-build-a
    Corpus = Join-Path $env:TEMP rapidrbf-hierarchy-repro-corpus-a
  },
  @{
    Build = Join-Path $env:TEMP rapidrbf-hierarchy-repro-build-b
    Corpus = Join-Path $env:TEMP rapidrbf-hierarchy-repro-corpus-b
  }
)
foreach ($run in $reproRuns) {
  if ((Test-Path $run.Build) -or (Test-Path $run.Corpus)) {
    throw "repro roots must be absent"
  }
  cmake -S "$hierarchyPrototype\capture\hierarchy" -B $run.Build `
    -G "Visual Studio 17 2022" -A x64 -T ClangCL `
    -DPOLATORY_SOURCE_DIR="$polatorySource"
  cmake --build $run.Build --config Release `
    --target rapidrbf_hierarchy_capture
  $capture = Join-Path $run.Build `
    "Release\rapidrbf_hierarchy_capture.exe"
  & $capture $run.Corpus
  python "$hierarchyPrototype\hierarchy_lock.py" $run.Corpus `
    --capture-exe $capture --polatory-source $polatorySource
  python "$hierarchyPrototype\hierarchy_lock.py" $run.Corpus `
    --capture-exe $capture --polatory-source $polatorySource --verify
}

$binaryPaths = @(
  "Release\rapidrbf_hierarchy_capture.exe",
  "rapidrbf_hierarchy_capture.dir\Release\hierarchy_capture.obj"
)
foreach ($relative in $binaryPaths) {
  $binaryIdentities = foreach ($run in $reproRuns) {
    $path = Join-Path $run.Build $relative
    "$((Get-Item $path).Length):$(
      (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
    )"
  }
  if (($binaryIdentities | Sort-Object -Unique).Count -ne 1) {
    throw "clean build roots differ for $relative"
  }
}

function Get-LockedTreeTable {
  param([string] $Root)
  $resolved = (Resolve-Path $Root).Path
  Get-ChildItem $resolved -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
      [pscustomobject]@{
        Path = $_.FullName.Substring($resolved.Length).TrimStart("\")
        Bytes = $_.Length
        Sha256 = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash
      }
    }
}
$treeDiff = Compare-Object `
  @(Get-LockedTreeTable $reproRuns[0].Corpus) `
  @(Get-LockedTreeTable $reproRuns[1].Corpus) `
  -Property Path, Bytes, Sha256
if ($treeDiff) {
  $treeDiff
  throw "locked corpus roots differ"
}
```

## Stage 0 replay

Rebuild the original frozen Stage 0 representative corpus:

```powershell
python tools/prototypes/dense_factor_replay_throwaway/run.py --recapture
```

Verify and replay the current Stage 0 lock without capturing it again:

```powershell
python tools/prototypes/dense_factor_replay_throwaway/run.py --replay-only
```

## Question

Against one content-addressed M1-M4 corpus of captured local projected and
coarse matrices, can audited `faer 0.24.4`, `nalgebra 0.35.0`, and one exactly
bound native LAPACK implementation obey the same versioned factor/fallback
contract?

The replay makes these differences visible:

- normalized factor status and atomic failure;
- 1x1/2x2 pivots, permutations, and rank diagnostics;
- reduced solve residual, full correction residual, polynomial recovery, and
  CPD side-condition residual;
- source/factor packing, retained allocations, and factorization scratch;
- configured/effective/maximum-live threads; and
- the runtime and license closure each tier-one artifact would inherit.

This is Stage 0 decision evidence, not a production solver, acceptance
benchmark, or dependency adoption. Candidate-library success never certifies a
fit. The corpus registers semantic expectations, while the replay keeps
library status, the missing RapidRBF-owned rank authority, captured augmented
residuals, and the missing independent evaluator certificate separate.
Collected observations remain `COLLECTED, UNJUDGED`.

## Frozen comparison boundary

- Corpus schema: `rapidrbf-dense-factor-corpus-v1`.
- Contract schema: `rapidrbf-factor-attempt-v1`.
- Dense candidates: exactly `faer 0.24.4`, `nalgebra 0.35.0`, and Windows
  LP64 sequential Intel MKL `2023.0.0` from the frozen Polatory build.
- Native LAPACK calls: lower-triangle `DSYTRF/DSYTRS`, with fresh
  `DGETRF/DGETRS` only on a hard factor/solve failure; native threading is the
  explicitly linked sequential layer. Gated LLT is a faer audit in this
  prototype; native `DPOTRF/DPOTRS` is not materialized.
- Canonical matrix payload: little-endian `f64`, lower triangle in row order.
- Candidate factor payloads are never treated as a public or portable format.
  The replay records whether documented components can be normalized into a
  RapidRBF-owned record, otherwise the candidate is resident-only.

The common policy audits pivoted symmetric-indefinite factorization for every
finite symmetric block, admits LLT only through a declared positive-definite
gate, and uses an explicit LU fallback only after a failed or uncertifiable
symmetric path. QR/SVD-style rank evidence is diagnostic and cannot silently
repair an invalid interpolation system.

## Controls

- `j` / `k` - previous / next captured block
- `b` - next dense backend
- `v` - next evidence view
- `r` - verify the lock, then replay the selected block/backend in a fresh worker
- `a` - rebuild the corpus and rerun the complete audit
- `q` - quit

Each action redraws the complete state. Useful feedback is a status mapping
that hides a backend disagreement, an inadmissible fallback, a missing resource
charge, or an artifact-closure obligation that should block promotion.

## Deliberate prototype limits

- Captured blocks are mechanism-scale local/coarse representatives, not the
  accepted 1k/10k end-to-end workloads.
- Windows MKL is the one executable native comparator. The other tier-one
  native closures are reported as unclosed rather than simulated.
- Allocator and process-memory deltas are diagnostic snapshots, not the
  release memory acceptance channels.
- The replay deliberately does not publish timing: there is no paired timing
  plan or threshold authority in the dense-factor replay ticket.
- No candidate can advance past Stage 0 solely because this replay succeeds.
