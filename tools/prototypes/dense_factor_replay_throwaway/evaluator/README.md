# Independent physical factor evaluator

This throwaway Rust CLI checks captured coefficient witnesses against a
reconstructed physical RBF operator. It accepts only the locked v3 hierarchy
corpus (`rapidrbf-canonical-hierarchy-admission-corpus-v3` plus its sibling
`manifest.lock.json` with schema
`rapidrbf-canonical-hierarchy-corpus-lock-v3`). Every report sets
`admission_claim=false`.

Judgment is governed by the independent
[`physical-evidence-profile.v1.json`](physical-evidence-profile.v1.json)
(`canonical-hierarchy-physical-evidence-v1`, SHA-256
`cf64f2b26e2a3f4844a5c63027deb5bd4e1f856f0c7f45d4d2afdcccbff724a1`).
The evaluator removes `profile_sha256`, recursively sorts object keys,
compact-serializes the remaining JSON, recomputes SHA-256, and requires both
the declared digest and a compile-time pinned digest to match. Consequently,
editing a threshold and recomputing its self-hash is still rejected before a
corpus payload is opened. The top-level report, controls report, and every
per-block certificate bind the profile schema, ID, and digest. Their output
schemas are v2.

The corpus lock identity is independently authenticated by
removing its top-level `corpus_sha256`, recursively sorting object keys,
compact-serializing the remaining JSON, and recomputing SHA-256.

## Reproduce

Run these commands from this `evaluator` directory:

```powershell
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
cargo build --release --locked
cargo run --release --locked -- controls --output controls.json
cargo run --release --locked -- evaluate <path-to-hierarchy.manifest.raw.json> `
  --max-payload-bytes 685751487 --max-pair-work 1158236153 `
  --output summary.json --cert-dir certificates
```

The frozen observed binary was built with
`rustc 1.96.1 (31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd)`,
`cargo 1.96.1 (356927216a2d746168cf76e5e88cc3f4b58e029d)`, LLVM
22.1.2, target `x86_64-pc-windows-msvc`, and
`cargo build --release --locked`. The report's executable SHA-256 identifies
the binary that actually ran; byte-for-byte rebuild identity is not inferred
from the toolchain coordinate alone.

Use one or more `--block <block-id>` arguments for a smoke run. The other
options are `--precision-bits 256` (the value required by the loaded profile),
`--max-payload-bytes <bytes>`, and `--max-pair-work <count>`. JSON files are
published through same-directory temporary files and atomic rename; existing
diagnostics are never overwritten. A run with any rejected factor writes its
summary and per-factor diagnostics first, then exits nonzero.

## Arithmetic authority and decisions

All payload numbers are finite little-endian binary64 values whose exact bits
are the arithmetic inputs. Kernel, anisotropy, polynomial, projection,
closure, and CPD calculations use outward-directed multiprecision intervals
through the pure-Rust `astro-float-num` 0.3.6 implementation. The profile
selects 256-bit proof precision; decisions use interval bounds, not formatted
decimals. Both smaller and larger `--precision-bits` values are rejected
before corpus payloads are opened, keeping the scratch grant tied to the
content-addressed profile.

For a physical action row, `scale_upper` is the outward sum of the absolute
per-component kernel, nugget, and polynomial contributions after
multiplication by the corresponding coefficient. The profile v1 row allowance
is:

```text
value:    scale_upper*2^-43 + |rhs|*2^-40
gradient: scale_upper*2^-38 + |rhs|*2^-35
```

For fine projected row `k`, the evaluator propagates this as
`allowed_tail[k] + sum_a |Q_top[a,k]|*allowed_top[a]`. No fine `c` is read,
created, or scattered.

Every packed captured `QTAQ` entry is checked against

```text
B = A22 + Q_top^T*A12 + A12^T*Q_top + Q_top^T*A11*Q_top
```

from the same streamed `A_phys` reconstruction used for `A_phys*lambda`.
`physical_component_scale` is the outward sum of absolute kernel-component
contributions after the entry's `Q` weights, and `transform_scale` is the
outward sum of absolute congruence terms. The QTAQ-entry allowance is:

```text
value-only:
  physical_component_scale*2^-43
  + (transform_scale + |captured_QTAQ|)*2^-40
derivative-involving:
  physical_component_scale*2^-38
  + (transform_scale + |captured_QTAQ|)*2^-35
```

The captured reduced RHS must enclose
`Q_top^T*rhs_head + rhs_tail` within
`gamma_(l+1)*sum_abs`, where
`gamma_k=(k*u)/(1-k*u)` and profile v1 sets `u=2^-53`. The candidate equation
`QTAQ*gamma=rhs_reduced` then uses the frozen physical row allowance above,
with `scale_upper=sum_j |QTAQ_ij*gamma_j|`. Matrix-entry closure, reduced-RHS
closure, and the witness equation must all pass.

The CPD certificate uses

```text
eta = ||P^T lambda||inf / (||P^T||inf * ||lambda||inf), with 0/0 = 0
```

where physical `P` is reconstructed from coordinates and derivative rows. The
point estimate is enclosed by a directed-rounding interval; `alpha` is the
larger distance from the point estimate to either enclosure edge.
Certification requires the outward upper bound of `eta + alpha` to be at most
the profile v1 threshold `2^-32`.

## Resource and trust boundary

Before opening payloads, the evaluator computes both grants:

```text
payload bytes =
  locked bytes of used coordinate/model/index/mask/Q/QTAQ/RHS/witness payloads
  + 1024 * max(block scalar order) logical O(m) scratch

pair work =
  sum[
    components*(m*(m+1)/2 + 3*gradient_points)
    + l*l*r + 3*l*r*(r+1)/2
    + r*r
    + l*r + r
    + m*l
    + l*r
    + (fine: l*r | coarse: m*l)
  ]
```

These formula coefficients and the `1024`-byte scratch factor are parsed from
the content-addressed profile and participate in the actual preflight
judgment. The first term is the shared physical-entry sweep. Its
`3*gradient_points` correction covers the three scalar entries omitted by a
triangular scalar count in each same-point 3x3 Hermite block, where all nine
directed channel pairs execute. The remaining terms cover `A11*Q` plus three
`l`-wide sums for each packed QTAQ entry, candidate QTAQ witness matvec,
reduced-RHS closure, CPD, full `lambda=[Q_top;I]gamma` coefficient closure, and the role-specific projection
or polynomial action.

Evaluation fails with `ResourceDenied` if either grant is smaller. Physical
entries stream into O(m) action accumulators plus O(l*m) congruence seams; the
evaluator never materializes dense `A_phys`.

Captured `A`, captured `P`, and coarse `P_top` are never opened. Captured
`QTAQ` is opened and hash-verified only as candidate evidence: it is compared
entry by entry with the independent physical congruence and is never an input
to physical reconstruction. The executable does not link or call Polatory,
Eigen, faer, a solver, or any factorization backend. Fine blocks check the
projected physical residual and coefficient closure without `c`; coarse blocks
check the full physical residual with witness `c`. Reports use corpus-relative
manifest/lock filenames, bind their SHA-256 identities, set
`admission_claim=false`, and always record `backend_calls=0`.

Each report also binds the evaluator rather than relying on corpus provenance:
it records a deterministic length-prefixed SHA-256 closure over `Cargo.toml`,
`Cargo.lock`, `physical-evidence-profile.v1.json`, and every `src/*.rs` file
embedded at compile time, plus the SHA-256 and byte length of the running
executable. The profile has its own identity in addition to participating in
that source closure, preserving the distinction between acceptance judgment
and evaluator implementation provenance.
