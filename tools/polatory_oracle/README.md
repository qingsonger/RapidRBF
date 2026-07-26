# Polatory oracle tools

These tools form one narrow capture/verify/replay module around the frozen
Polatory build. They are not the future cross-implementation differential
harness and do not define numerical tolerances.

## Prerequisites

The commands below assume:

- a clean Polatory checkout at
  `4a30beb08053fb339ce899e255be4b6d3f74aa0c`;
- the Windows x86_64 Release CLI at `build/cli/polatory.exe` with SHA-256
  `95cd325f727e6f56d1656feb52672a37a5fc655132a232cbb6976f031ffccfe9`;
- the matching test and benchmark executables; and
- a probe built from [`probe`](probe) by following
  [`probe/README.md`](probe/README.md).

The baseline does not redistribute these heavy native executables. Replay
requires their exact local builds.

## Build and validate the index

From the RapidRBF repository root:

```powershell
python -B tools/polatory_oracle/build_index.py
python -B tools/polatory_oracle/oracle.py verify `
  --index oracle/manifests/oracle-index.json
```

`build_index.py` embeds the reviewed compatibility items and refuses a missing
accepted-surface scenario definition. Review changes to both
`compatibility-items.json` and the generated `oracle-index.json`.

## Capture a new bundle

```powershell
$polatoryRoot = "D:/CODE/polatory"
$probe = (
  Resolve-Path `
    "tools/polatory_oracle/probe/build/polatory_frozen_source_probe.exe"
).Path

python -B tools/polatory_oracle/oracle.py capture `
  --index oracle/manifests/oracle-index.json `
  --out baseline/polatory-4a30beb-windows-x86_64 `
  --repo-root . `
  --var "POLATORY_ROOT=$polatoryRoot" `
  --var "PROBE=$probe"
```

Capture never overwrites an existing path. Each scenario runs in an isolated
temporary directory with an allowlisted environment, forced isolated temp
variables, explicit thread settings, a timeout, and Windows Job Object
descendant cleanup.

## Verify and replay

```powershell
python -B tools/polatory_oracle/oracle.py verify `
  --index oracle/manifests/oracle-index.json `
  --bundle baseline/polatory-4a30beb-windows-x86_64

python -B tools/polatory_oracle/oracle.py replay `
  --index oracle/manifests/oracle-index.json `
  --bundle baseline/polatory-4a30beb-windows-x86_64 `
  --repo-root . `
  --var "POLATORY_ROOT=$polatoryRoot" `
  --var "PROBE=$probe" `
  --diff-out baseline/polatory-4a30beb-windows-x86_64-replay.json
```

Replay compares scenario structure and configured raw outputs exactly. This is
an evidence-integrity and drift check, not a claim that every replayed byte is
compatibility truth. Scenario roles govern coverage authority; machine-readable
selectors and downstream operation contracts choose the accepted semantic
fields. Replay reports the first differing byte and a small text diff where
possible, but applies no numeric tolerance. Outputs marked
`replay_compare: false`, currently resource samples, remain inside the checksum
closure and are still integrity-checked. The diff output also refuses
overwrite.

## Fixture materializers

The materializers are intentionally one-shot and refuse an existing output:

```powershell
python -B tools/polatory_oracle/materialize_legacy.py `
  --polatory-root D:/CODE/polatory `
  --output oracle/fixtures/legacy/windows-x86_64-polatory-4a30beb

python -B tools/polatory_oracle/freeze_python_build.py `
  --source D:/CODE/polatory/build-python-oracle `
  --output oracle/fixtures/python-build/windows-x86_64-polatory-4a30beb
```

The legacy materializer verifies the source commit and CLI hash before it
generates models, fitted interpolants, logs, checksum closure, and bounded
corruption cases. The Python materializer copies only the six reviewed raw
streams; it excludes PowerShell wrapper noise and interrupted CMake/vcpkg
intermediates.

`workflows.py` groups public commands so every child argv, environment,
stdout/stderr stream, output, terminal state, and content hash can be captured.
Its `evidence.json` is deterministic; child resource samples are written
separately to `resources.json`.

## Tests

```powershell
python -m unittest discover -s tools/polatory_oracle/tests -v
python -m py_compile `
  tools/polatory_oracle/oracle.py `
  tools/polatory_oracle/workflows.py `
  tools/polatory_oracle/build_index.py `
  tools/polatory_oracle/materialize_legacy.py `
  tools/polatory_oracle/freeze_python_build.py
```

The tests cover checksum closure, index binding, role/authority separation,
unsafe paths, cwd/temp isolation, no-overwrite behavior, exact replay,
diagnostic-only outputs, Windows thread sampling, and descendant-process
timeouts.
