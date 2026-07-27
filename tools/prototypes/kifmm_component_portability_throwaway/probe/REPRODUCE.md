# kifmm component/portability throwaway probes

These probes answer two narrow questions:

1. Does the proposed scalar-radial/multiple-RHS decomposition reproduce
   RapidRBF's four canonical action formulas under metric transforms and
   1D/2D zero-padding?
2. Does frozen KiFMM actually consume the component-count methods advertised by
   green-kernels, and what build/dependency surface is present?

They are prototype evidence only. They do not execute an RBF through KiFMM,
establish a sound certificate, or qualify a backend for `Auto`.

## Frozen inputs

- kifmm:
  `d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068`
- green-kernels:
  `ed83120e5e74972fb0f21593b1f8f5047b6eefac`
- RLST:
  `33bd9a6339f2aa60076b74b6ed020473a81b1eb6`

The latter two revisions are part of the captured evidence because the kifmm
manifest uses moving git declarations and ignores `Cargo.lock`.

The exact audit-generated dependency graph is captured as
`kifmm-d4ca4b5-Cargo.lock`. Its SHA-256 is
`FF50830C7C5A7429EC03B4735453677912A71A60CF00AB7A5C0F3E2F16310690`.

## Reproduce the metric-action identity

From the RapidRBF repository root:

```powershell
python tools/prototypes/kifmm_component_portability_throwaway/probe/throwaway_metric_action_probe.py
```

The command emits 64 structured rows:

- dimensions 1–3;
- self and cross geometry;
- identity/diagonal transforms and nonsymmetric shear in 2D/3D;
- canonical `A`, `F`, `F^T`, and `H`.

It must terminate successfully with every maximum absolute difference below
the script's throwaway `2e-13` guard. That guard only detects an algebra or
implementation mistake in this probe; it is not a RapidRBF acceptance
threshold.

## Reproduce the source-surface audit

Create clean detached checkouts:

```powershell
$Work = Join-Path $env:TEMP ("rapidrbf-kifmm-source-" + [guid]::NewGuid().ToString("N"))
$Kifmm = Join-Path $Work "kifmm"
$Green = Join-Path $Work "green-kernels"
$Rlst = Join-Path $Work "rlst"

git clone https://github.com/bempp/kifmm.git $Kifmm
git -C $Kifmm checkout --detach d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068

git clone https://github.com/skailasa/green-kernels.git $Green
git -C $Green checkout --detach ed83120e5e74972fb0f21593b1f8f5047b6eefac

git clone https://github.com/skailasa/rlst.git $Rlst
git -C $Rlst checkout --detach 33bd9a6339f2aa60076b74b6ed020473a81b1eb6

python tools/prototypes/kifmm_component_portability_throwaway/probe/source_surface_probe.py `
  --kifmm $Kifmm `
  --green-kernels $Green `
  --rlst $Rlst
```

The source probe reads canonical `HEAD` Git blobs, rejects tracked checkout
changes, and fails closed on a revision or expected-blob-hash mismatch. It
does not rely on working-tree line endings or line numbers.

## Reproduce the Windows build observation

The captured run used:

- Windows x86_64;
- `x86_64-pc-windows-msvc`;
- Cargo/Rust 1.96.1;
- an audit-generated lock resolving green-kernels `ed83120`, RLST `33bd9a6`,
  and optional distributed-tools `9d5c832`;
- command `cargo check -p kifmm --lib --locked`.

A pristine clone has no lock because the library repository ignores it.
Restore and verify the captured graph before running the check:

```powershell
$CapturedLock = Resolve-Path `
  tools/prototypes/kifmm_component_portability_throwaway/probe/kifmm-d4ca4b5-Cargo.lock
$ExpectedLockHash = "FF50830C7C5A7429EC03B4735453677912A71A60CF00AB7A5C0F3E2F16310690"
$ActualLockHash = (Get-FileHash -Algorithm SHA256 $CapturedLock).Hash
if ($ActualLockHash -ne $ExpectedLockHash) {
  throw "Captured Cargo.lock hash mismatch: $ActualLockHash"
}

Copy-Item $CapturedLock (Join-Path $Kifmm "Cargo.lock")
Push-Location $Kifmm
try {
  cargo check -p kifmm --lib --locked
} finally {
  Pop-Location
}
```

On the recorded Windows host, this reaches `kifmm-fftw-src` and fails when
the build script executes FFTW's Unix `configure` file:

```text
os error 193: %1 is not a valid Win32 application
```

The exact normalized observation, captured-lock path, and digest are in
`observed-windows-build.json`.

The clean WSL Ubuntu observation is retained separately in that artifact. It
failed earlier in the parallel dependency graph at `openssl-sys` because the
host had no OpenSSL development package. It does not establish a terminal FFTW
result on Linux. Upstream's provisioned Ubuntu CI is positive Linux evidence,
but the frozen workflow has no Windows or macOS jobs.

## Deliberate limits

- Gaussian action identity only; no KiFMM tree or translation executes.
- No far/M2L path witness, expansion-order sweep, or compression study.
- No complete 16-family or derivative-boundary corpus.
- No call-scoped absolute-infinity certificate.
- No repeated-memory, cancellation, deadline, resource, thread, or
  determinism measurement.
- No clean tier-one artifact/runtime/license closure.
- No commercial FFTW license assumption.
