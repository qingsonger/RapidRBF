# Observed Stage 0 dense-factor results

This is reaction material for
[Replay captured local and coarse factors across shortlisted dense substrates](https://github.com/qingsonger/RapidRBF/issues/33).
It is not a production backend choice or an acceptance result.

## Evidence identity

- corpus lock: `rapidrbf-dense-factor-corpus-lock-v2`;
- corpus SHA-256:
  `AC282EE95062B4463D2E0A0C0CA83DA454660E0E5048FA79EA3A07DA280EF26E`;
- capture: 10 records, 190 payloads, 30 requested backend/record pairs;
- coverage: `30/30`, with no missing, duplicate, or unexpected pair;
- state: `COLLECTED, UNJUDGED`;
- selection authority: absent
  `FactorHealthProfile { profile_id, profile_hash }`.

Every registered record also says
`semantic_admission.state=EVIDENCE_MISSING`: the Stage 0 corpus does not carry
the independently certified rank interval required to admit a production
factor path. Backend status and pivots remain factor-health evidence only.

## Substrate comparison

| Substrate | Collected factor path | Reconstruction and packing | Resource/thread evidence | Artifact closure |
|---|---|---|---|---|
| `faer 0.24.4` | 10/10 `Factored` by LBLT; no positive-corpus LU fallback | Independent public L/B/P reconstruction; 10/10 owned component pack → reload → solve roundtrips | Retained `5.018–32.125 MiB`; allocator diagnostic `46.706–277.135 MiB`; high-level scratch and max-live threads missing; fresh worker pins process-global `Seq` | Cargo coordinate locked; per-tier-one runtime/provenance closure not established |
| `nalgebra 0.35.0` | 10/10 `Factored` by LBLT; no positive-corpus LU fallback | Public reconstruction collected; private pivots prevent a stable factor record and roundtrip | Exact retained bytes and high-level scratch missing; lower bound only; allocator diagnostic `31.702–194.578 MiB`; no injectable thread lease; max-live missing | Blocked for bounded spill/resume because the private factor cannot be materialized |
| oneMKL `2023.0.0#2` LP64 sequential | 10/10 `Factored` by `DSYTRF/DSYTRS`; no positive-corpus LU fallback | Exact factor/IPIV byte stream can be hashed, but independent reconstruction and pack → reload → solve are missing | Retained `4.996–32.070 MiB`; declared LAPACK workspace `0.148–0.751 MiB`; MKL-only allocator peak `10,824–20,752 B` excludes Rust-owned staging; local thread limit is 1 but no caller lease/max-live proof exists | Exact Windows files and loaded version verified; minimum CPU-dispatch runtime is `136.622 MiB`, already above the registered `128 MiB` CLI runtime budget; license, clean-host, Linux, and macOS closure remain missing |

The resource channels are deliberately not interchangeable. In particular,
the MKL allocator peak excludes Rust vectors, while the Rust allocator
diagnostics include verification/reconstruction work. These observations
describe ownership gaps; they are not a cross-provider memory benchmark.

## Numerical observations

Across the eight canonical records and all three substrates:

- reduced normwise backward error is at most `2.564e-17`;
- public faer/nalgebra factor reconstruction is at most `6.094e-16`;
- captured augmented-equation residual `alpha` is at most `9.233e-15`;
- normalized CPD side-condition `eta` is at most `1.327e-17`.

Those are diagnostic values, not passes. The independent value/gradient
evaluator uncertainty, semantic rank certificate, publication witnesses, and
factor-health profile are missing.

The M3 frozen-literal/canonical pair exposes a substrate-independent assembly
signal:

| M3 frozen-literal block | Reduced error across substrates | Captured `alpha` | `eta_CPD` |
|---|---:|---:|---:|
| max-order fine | `5.024e-18–9.680e-18` | `5.927e-10` | `9.568e-5` |
| level-0 coarse | `2.882e-18–4.928e-18` | `8.292e-7` | `1.948e-3` |

All three substrates solve the frozen-literal reduced systems to small
backward error while the independently reconstructed augmented quantities
deteriorate by many orders of magnitude. This isolates assembly sensitivity
from the dense factor substrate. It is research-only evidence: no semantic
rank authority or accepted intentional-difference adjudication labels it a
Polatory defect.

## Failure controls

- Exact singular diagonal: semantic admission rejects first; diagnostic
  force-replay yields `NonFiniteOutput` (faer), `NumericalBreakdown`
  (nalgebra), and `SingularPivot` (oneMKL).
- NaN matrix and infinite RHS: every substrate is rejected before
  factorization and reports factor state `NOT_RUN`.
- Rank-threshold straddle: declared and kept out of backend execution; the
  required 256–2048-bit precision ladder remains unmaterialized.

## What the prototype supports—and does not

The evidence supports carrying `faer` forward as the only substrate in this
probe that exposes enough public structure for an owned, replayed factor
record. It supports retaining nalgebra as a useful independent numerical
comparator, while its private pivots block bounded spill/resume. It supports
keeping the exact oneMKL build as a Windows diagnostic comparator, not as the
current four-target release substrate.

It does **not** select a production winner or establish an admissible factor
path. Before the downstream FGMRES/RAS comparison can consume factors as
admitted inputs, a follow-up must materialize the registered rank authority,
bind a versioned factor-health profile, complete the external correction
evaluator/publication witnesses, and close the applicable resource lanes.

Human reaction is requested on two points:

1. whether `faer` should be the sole dense factor candidate carried into that
   materialization work, with nalgebra and oneMKL retained as comparators; and
2. whether the M3 frozen-literal signal should graduate into a separate
   diagnosis/adjudication ticket or remain research-only context.
