# Frozen Polatory behavior oracle

This directory is the executable observation basis for the RapidRBF
v1.0.0 migration. It binds machine-readable fixtures and raw process evidence
to Polatory commit
`4a30beb08053fb339ce899e255be4b6d3f74aa0c` and the Windows x86_64 CLI with
SHA-256
`95cd325f727e6f56d1656feb52672a37a5fc655132a232cbb6976f031ffccfe9`.

The blessed bundle is
[`baseline/polatory-4a30beb-windows-x86_64`](../baseline/polatory-4a30beb-windows-x86_64).
It contains 19 scenarios:

- 11 `accepted_surface` scenarios that cover the applicable items in the
  accepted compatibility manifest;
- 1 `provenance_only` selected upstream-test scenario; and
- 7 `research_only` scenarios for malformed inputs, suspected defects, and
  Python buildability observations.

The first independent full replay produced
[`differences: []`](../baseline/polatory-4a30beb-windows-x86_64-replay.json).
Every bundle and run directory has a closed `checksums.sha256` file: missing,
duplicate, extra, resized, or changed files fail verification.

## Evidence is not a global acceptance threshold

The oracle freezes what the selected Polatory executable did. It does not make
Polatory independent mathematical truth, and it applies no floating-point
tolerance. Later numerical, geometry, resource, CLI, Python, and artifact
decisions select semantic fields and define their own operation-specific
comparisons.

The oracle index enforces the three scenario roles as **coverage authority**:
only an `accepted_surface` scenario can satisfy a required manifest item.
Capture integrity is deliberately broader. A scenario may retain extra
diagnostic bytes, and full-stream replay detects any drift in those bytes
without promoting them to compatibility truth. Machine-readable selectors and
per-observation classifications identify the accepted subset.

| Role | May satisfy required compatibility coverage? | Meaning |
| --- | --- | --- |
| `accepted_surface` | Yes | Valid-input observation selected by the scenario, or a reviewed prerequisite inventory; the role does not accept every captured byte |
| `research_only` | No | Suspected defect, invalid/unsafe input, malformed artifact, or build failure awaiting adjudication |
| `provenance_only` | No | Build/test context useful for diagnosis but outside compatibility truth |

This separation is deliberate. Polatory crashes, unsafe allocation behavior,
incidental NaN/Inf propagation, malformed-number acceptance, and suspected
defects never become RapidRBF requirements merely because their bytes were
captured.

## Contents

- [`manifests/compatibility-items.json`](manifests/compatibility-items.json)
  is the reviewed mapping from the accepted compatibility decision to stable
  scenario IDs.
- [`manifests/oracle-index.json`](manifests/oracle-index.json) is the executable
  capture contract, including scenario role, authority, command, environment,
  timeout, thread configuration, seed policy, and output policy.
- [`manifests/python-surface.json`](manifests/python-surface.json) freezes the
  accepted Python workflow and logical array-shape inventory without promising
  exact legacy signatures or the `polatory` import name.
- [`fixtures/source`](fixtures/source) contains small, reviewable source tables
  for interpolation, Hermite, kriging, point-cloud, geometry, CLI, and defect
  observations.
- [`fixtures/legacy/windows-x86_64-polatory-4a30beb`](fixtures/legacy/windows-x86_64-polatory-4a30beb)
  contains 105 valid Model/Interpolant artifacts, generation logs, three
  differential-only `VariogramSet` files, and ten bounded malformed derivatives.
- [`fixtures/python-build/windows-x86_64-polatory-4a30beb`](fixtures/python-build/windows-x86_64-polatory-4a30beb)
  contains six byte-exact streams from three Python build reproductions.

Polatory executables are not redistributed. Build identity evidence records
their sizes and SHA-256 values, the selected CMake cache, the Ninja graph hash,
dependency revisions, compiler/tool versions, MKL sequential LP64 linkage,
LLVM OpenMP linkage, host identity, and configured/effective thread data.

## Coverage highlights

The instrumented C++ probe emits 401 deterministic JSONL records with SHA-256
`315a9c5d111ba568f453c01e42e786fcddfe1b9d562ffca67361d2bde6f16872`.
Its accepted selector covers valid RBF, Model, polynomial, anisotropy,
derivative, and dense Hermite-layout observations. It selects the actual
`shear` records for general positive-determinant anisotropy and only
returned-finite RBF evaluation fields; invalid and undefined fields remain
diagnostic.

The public CLI workflows cover all 14 commands and representative successful
1D/2D/3D interpolation, mixed value/gradient fitting and evaluation, ordinary,
incremental and inequality fitting, all six variogram weight schemes,
cross-validation, point-cloud/SDF operations, and 2.5D/3D geometry. Exact mesh
numbering and tessellation remain excluded even though raw OBJ bytes are
retained.

The legacy matrix loads all 51 valid Model and 54 valid Interpolant artifacts
through the frozen executable. RapidRBF's migration input remains valid Model
and Interpolant only: it never writes the native format and does not import
legacy `VariogramSet`.

The scale scenario content-addresses the upstream 1k, 10k, 100k, and 1M point
sets for literal training seed `0` and prediction seed `1`, and executes a
1k-by-1k fit/evaluation anchor. It intentionally records
`release_gate_satisfied: false`: the full million-point fit/evaluation waits for
the lower-rung resource bounds and differential/resource measurement harness
already owned by the Wayfinder map.

## Deliberately open boundaries

- The million-point fit/evaluation, memory, scratch, and runtime gate is not
  claimed by this capture.
- The frozen Python extension did not build on this host. The accepted Python
  item here is a source-bound workflow/shape prerequisite, not an executable
  Python-extension behavior oracle. Runtime buildability and workflow execution
  remain downstream work and are separate from the research-only build logs.
- The inequality active-set, zero-RHS GMRES, small normal-score,
  multi-radius-normal, pathological-SDF, and Python SDF-binding observations
  remain unadjudicated.
- An unfitted Interpolant cannot be constructed through the frozen CLI; the
  legacy import-boundary decision owns whether a source-linked diagnostic
  writer is needed.

Capture, verification, replay, and fixture-regeneration instructions live in
[`tools/polatory_oracle/README.md`](../tools/polatory_oracle/README.md).
