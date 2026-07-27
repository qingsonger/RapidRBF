# Ferreus target-Hessian throwaway probe

This probe answers one narrow question: can frozen Ferreus keep a scalar radial
M2L operator, carry `D` metric-vector right-hand sides, differentiate the
uniform-tree target expansion twice, and recover RapidRBF's `H` contraction?

It is prototype evidence only. It is not accepted harness evidence and does not
qualify a backend for `Auto`.

## Frozen input

- Repository: `https://github.com/graphic-goose/ferreus_rbf_rs`
- Commit: `d0442ee978668386f6ccbeec866bfa52fcc4484f`
- Toolchain used for the recorded run:
  `rustc 1.85.0 (4d91de4e4 2025-02-17)`,
  `x86_64-pc-windows-msvc`

The patch changes only:

- `ferreus_bbfmm/src/traits.rs`
- `ferreus_bbfmm/src/chebyshev.rs`
- `ferreus_bbfmm/src/bbfmm.rs`
- `ferreus_bbfmm/examples/throwaway_target_hessian_probe.rs`

No manifest or dependency change is required.

Captured SHA-256 identities:

- patch: `80A92472F60607F69D48C8D32911923EFF5F011BF29883459767DBBB5528703F`
- example: `DA426D514FE4198168F69CF4171DE85D6AC382611E825B8B3C233F5576A75F72`
- scalar-action example:
  `4C16000E4AD1C77FB77A4E7D86B0E350CA53C833E7A75963D35D78CEA40AB31E`

## Reproduce

From the RapidRBF repository root in PowerShell:

```powershell
$Probe = (Resolve-Path "tools/prototypes/ferreus_four_action_throwaway/probe").Path
$Work = Join-Path $env:TEMP ("ferreus-target-hessian-" + [guid]::NewGuid().ToString("N"))

git clone https://github.com/graphic-goose/ferreus_rbf_rs $Work
git -C $Work checkout --detach d0442ee978668386f6ccbeec866bfa52fcc4484f
git -C $Work apply (Join-Path $Probe "ferreus-d0442ee-target-hessian.patch")

cargo +1.85.0 check `
  --manifest-path (Join-Path $Work "Cargo.toml") `
  -p ferreus_bbfmm `
  --locked `
  --example throwaway_target_hessian_probe

cargo +1.85.0 run `
  --manifest-path (Join-Path $Work "Cargo.toml") `
  --release -q `
  -p ferreus_bbfmm `
  --locked `
  --example throwaway_target_hessian_probe
```

The final command must print twelve result rows followed by `PASS`. The exact
Windows observation is in
`observed-hessian-windows-x86_64.json`.

## Reproduce the scalar-action control from a separate clean clone

This is deliberately a second clone with no target-Hessian patch applied. It
captures the exact scalar-action example used for the canonical signed
observation.

```powershell
$Probe = (Resolve-Path "tools/prototypes/ferreus_four_action_throwaway/probe").Path
$ScalarWork = Join-Path $env:TEMP ("ferreus-scalar-action-" + [guid]::NewGuid().ToString("N"))

git clone https://github.com/graphic-goose/ferreus_rbf_rs $ScalarWork
git -C $ScalarWork checkout --detach d0442ee978668386f6ccbeec866bfa52fcc4484f
Copy-Item `
  -LiteralPath (Join-Path $Probe "throwaway_scalar_action_probe.rs") `
  -Destination (Join-Path $ScalarWork "ferreus_bbfmm/examples/rapidrbf_four_action_probe.rs")

Push-Location $ScalarWork
cargo +1.85.0 run -p ferreus_bbfmm --example rapidrbf_four_action_probe --locked
Pop-Location
```

The captured file and the source used for the recorded run both have SHA-256
`4C16000E4AD1C77FB77A4E7D86B0E350CA53C833E7A75963D35D78CEA40AB31E`.
The corresponding structured observation is
`observed-windows-x86_64.json`.

## What is compared

For canonical `F`, the scalar-action example evaluates `D` scalar radial
right-hand sides, contracts their target gradients diagonally, and applies the
fixed external sign `-1`. The rejected component-kernel control and complete
direct oracle apply the same sign. Every emitted row selects a nonzero direct
`F` witness, records its unsigned and canonical candidate/direct values, and
asserts that each canonical witness is the exact negative of its unsigned
value and that candidate/direct canonical signs agree.

For physical points and vectors, the example forms metric coordinates and
right-hand sides

```text
u = A x
w = A q
P_c(u_t) = sum_j Gaussian(u_t - u_j) w_jc
```

The prototype returns every target Hessian component of every scalar
right-hand side. It then contracts them as

```text
(H q)_r = -sum_k A[k,r] sum_c d2P_c / (du_k du_c)
```

and compares that result with a complete analytic Gaussian direct sum.

The `near` cases force a depth-one tree and assert zero V-list entries and zero
M2L reference operators. The `far` cases force refinement and assert positive
V-list and M2L-reference counts, so the far result cannot silently be an
all-P2P control.

## Deliberate limits

- Gaussian kernel only (`alpha = 0.45`), interpolation order 7.
- Uniform trees only. Adaptive W-list/M2P Hessians are not implemented.
- `M2LCompressionType::None`; reference-vector symmetry is still exercised.
- 96 sources and 96 self or 57 cross targets, in dimensions 1-3.
- Windows x86_64 only; no packaging, Python binding, scale, or performance run.
- No sound call-scoped certificate, cancellation, memory/thread accounting, or
  determinism claim.
- The prototype follows Ferreus's existing raw-pointer leaf accumulation style;
  it is not a production safety review.
- Hash-set traversal can change last-bit direct-accumulation order between
  runs. The recorded near-field differences remain at floating-point roundoff.
