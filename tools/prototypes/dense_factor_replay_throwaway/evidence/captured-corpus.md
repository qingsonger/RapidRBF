# Captured M1-M4 corpus

Capture host observation on 2026-07-28:

- frozen Polatory commit:
  `4a30beb08053fb339ce899e255be4b6d3f74aa0c`;
- compiler: clang-cl 19.1.5, Release, frozen Polatory-compatible
  `EIGEN_USE_BLAS` with oneMKL LP64 sequential;
- Eigen: 3.5.0;
- projected matrix operation graph:
  `frozen-four-block-expression-v1`;
- projected RHS operation graph:
  `q_top.transpose() * d.head(l) + d.tail(m-l)`, followed by the
  frozen head-GEMV/tail-assignment reconstruction;
- capture source SHA-256:
  `F038E36420A080D13A4716E9359F100FAFCE47658DD4CF22E07B59E12CA778D1`;
- capture CMake SHA-256:
  `4D4ACC457F8BEEFE26A741FFF55A9887BBDA0B879FD861D47C0E6258B68A8C7E`;
- raw manifest SHA-256:
  `B488D8FA726872CF17CFE4F1BB48E08C44DE1A1ECF2370A2D08FB59EB7384CBC`;
- locked corpus SHA-256:
  `AC282EE95062B4463D2E0A0C0CA83DA454660E0E5048FA79EA3A07DA280EF26E`;
- capture executable SHA-256:
  `269111E0EEAC92ACEA4CE25AC24A9D9E72D4CB98E9921A5594A0AC8079F7133A`;
- raw payload: 191 files, 300,188,945 bytes (286.282 MiB).

The raw payload is deliberately ignored by Git. `run.py --recapture` rebuilds
it and refuses replay publication until the v2 lock covers the raw manifest,
all 190 referenced payloads, capture sources/CMake/executable, and seven
registered oneMKL import/runtime identities. Rust independently recomputes the
lock digest and verifies every payload before workers start. A raw manifest
alone is instrumentation input, not replay evidence. Two independent audited
captures matched the same v2 digest and all 191 locked entries by size and
SHA-256; the verified duplicate staging capture was then removed.

## Selection

Each registered 10k source shape is rebuilt deterministically. The capture
selects the lexicographically first maximum-scalar-order fine domain and the
level-0 coarse selection returned by the frozen `DomainDivider` at target
2048. This produces eight candidate-independent assembly blocks:

| Panel | Fine `(m,l,m-l)` | Coarse `(m,l,m-l)` |
|---|---:|---:|
| M1 EXP value-only | `(810,1,809)` | `(2049,1,2048)` |
| M2 TH3 CPD | `(813,4,809)` | `(2052,4,2048)` |
| M3 mixed Hermite composite | `(971,4,967)` | `(2054,4,2050)` |
| M4 hard-valid clustered geometry | `(813,4,809)` | `(2052,4,2048)` |

The capture also emits two M3 `research-only` assembly blocks using the frozen local
gradient-row offset literally. They share the selected domain with the
canonical M3 blocks but are separate matrix/RHS/factor records.

## Frozen Eigen observation

These are diagnostics, not acceptance thresholds:

| Record | Reduced backward error | `P_top` rank |
|---|---:|---:|
| M1 fine / coarse | `3.143e-17` / `2.658e-17` | `1` / `1` |
| M2 fine / coarse | `6.758e-18` / `4.384e-18` | `4` / `4` |
| M3 canonical fine / coarse | `8.569e-18` / `2.434e-18` | `4` / `4` |
| M3 frozen-literal fine / coarse | `2.642e-16` / `3.618e-16` | `4` / `4` |
| M4 fine / coarse | `2.155e-17` / `7.698e-17` | `4` / `4` |

The frozen literal M3 factors are indefinite while the canonical pair is
reported positive by Eigen. That is a research signal about assembly
sensitivity. It is neither semantic rank evidence nor a Polatory defect
verdict.

## Admission gaps

The corpus closes deterministic matrix capture, not semantic admission. Every
record says `semantic_rank_state=certificate-missing`; the canonical records
carry only a registered source-workload expectation, while the literal M3
records carry no rank expectation. The
following remain explicit controls or missing authorities in Stage 0:

- #16 high-precision, hash-bound rank certificates for `P`, `Q^T A Q`, and
  coarse `P_top`;
- registered M4 rank-fail and rank-straddle admission records;
- non-finite matrix and RHS mutations;
- independent full evaluator uncertainty for the value/gradient correction
  certificate; and
- a versioned `FactorHealthProfile`.

Where those are absent, the replay must report `EVIDENCE_MISSING`, not infer
admission from Eigen, faer, nalgebra, or LAPACK status.
