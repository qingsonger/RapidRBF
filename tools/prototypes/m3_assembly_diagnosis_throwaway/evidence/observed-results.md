# M3 mixed-Hermite assembly-sensitivity diagnosis

This is the resolution evidence for
[Diagnose and adjudicate the M3 frozen-literal assembly-sensitivity signal](https://github.com/qingsonger/RapidRBF/issues/35).
It adjudicates representation authority for downstream mechanism work. It is
not a production dense-factor admission, a backend selection, or a change to
the frozen Polatory source.

## Answer

The signal is a confirmed legacy internal assembly defect in the frozen
literal row map.

`RasPreconditioner` constructs the full Lagrange matrix over all value rows and
then all point-major gradient rows. `FineGrid` and `CoarseGrid`, however, form
gradient row indices with their **local** value-row count `mu_`:

```text
mu_ + 3 * global_gradient_index + component
```

The correct offset into the full matrix is the **source** value-row count:

```text
source_value_rows + 3 * global_gradient_index + component
```

The frozen expressions are visible in
[`fine_grid.hpp:53-73`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/fine_grid.hpp#L53-L73)
and
[`coarse_grid.hpp:34-54`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/coarse_grid.hpp#L34-L54);
the full-matrix construction is in
[`ras_preconditioner.hpp:81-91`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/ras_preconditioner.hpp#L81-L91).

Consequently, the frozen-literal `Q` has an identity tail and full algebraic
column rank but is not a basis for `null(P^T)`. A dense factor can solve its
reduced system accurately without restoring the missing polynomial
orthogonality.

The downstream M3 representation authority is therefore the
`canonical-row-channel-map`. The frozen-literal representation is retained
only as a diagnostic defect fixture and must not provide factors or expected
semantics to the mechanism panel. The dense substrate is not causal.

## Evidence identity

- corpus lock: `rapidrbf-dense-factor-corpus-lock-v2`;
- corpus SHA-256:
  `AC282EE95062B4463D2E0A0C0CA83DA454660E0E5048FA79EA3A07DA280EF26E`;
- corpus verification: the canonical lock body independently reproduces the
  registered digest; its manifest coverage and directory closure are exact;
  all `191` locked files and `300,188,945` bytes rehashed successfully;
- source authority: clean frozen Polatory commit
  `4a30beb08053fb339ce899e255be4b6d3f74aa0c`;
- arithmetic oracle: Python standard library `Decimal` at `80` decimal
  digits, reconstructed from raw binary64 `A`, `P`, `d`, `lambda`, and `c`;
- precision sensitivity: the checked-in
  [`120`-digit summary](observed-summary-120d.json) reproduces all `20`
  reported structural/residual metrics from the `80`-digit summary at the
  emitted `24` significant digits;
- machine-readable outputs:
  [`observed-repro.json`](observed-repro.json) and
  [`observed-summary.json`](observed-summary.json), plus the linked
  `120`-digit sensitivity summary.

The summaries record hashes for both scripts, the exact replay executable,
every audited frozen source file, each backend's version/artifact coordinates,
and the per-record matrix/RHS input identities.

## Deterministic three-substrate reproduction

The max-order fine canonical/literal pair was replayed three times on every
registered substrate. Key numerical metrics were exactly repeatable across the
three runs, and the symptom predicate reproduced on all substrates.

| Substrate | Canonical reduced error | Literal reduced error | Canonical / literal `alpha` | Canonical / literal `eta_CPD` |
|---|---:|---:|---:|---:|
| faer | `6.503e-18` | `6.126e-18` | `1.209e-17` / `5.927e-10` | `7.507e-18` / `9.568e-5` |
| nalgebra | `6.932e-18` | `5.024e-18` | `1.399e-17` / `5.927e-10` | `5.223e-18` / `9.568e-5` |
| oneMKL LP64 sequential | `8.877e-18` | `9.680e-18` | `1.445e-17` / `5.927e-10` | `5.653e-18` / `9.568e-5` |

The literal/canonical ratio is at least `4.10e7` for `alpha` and `1.27e13`
for `eta_CPD`, even though both reduced solves have backward errors below
`1e-17`. These bounds identify the reported symptom; they are not RapidRBF
acceptance thresholds.

## Row-map isolation

The canonical and frozen-literal records share byte-identical `A`, `P`, full
right-hand side, domain value indices, domain gradient indices, and polynomial
top block. Only assembly outputs differ.

| Role | Local value rows | Source value rows | Gradient scalar rows | Literal offset delta | Wrong rows | Rows still in value block |
|---|---:|---:|---:|---:|---:|---:|
| max-order fine | `479` | `7500` | `492` | `-7021` | `492` | `456` |
| level-0 coarse | `1109` | `7500` | `945` | `-6391` | `945` | `822` |

The independent oracle derives
`Q = [-(P_top^T)^-1 P_tail^T; I]` from each local `P`, without consuming the
captured `Q`. Canonical `Q_top` agrees with that oracle at binary64 roundoff;
the literal `Q_top` differs by as much as `8.551`.

## High-precision adjudication

The complete augmented residual and normalized CPD side condition were
recomputed independently. `2^-32 = 2.3283064365386962890625e-10` is the
registered limit for `eta_CPD + alpha_CPD`. The table compares `eta_CPD`
alone; the missing external-evaluator uncertainty prevents a production pass.
Conversely, a literal `eta_CPD` that already exceeds the limit cannot be
rescued by adding nonnegative uncertainty.

| Role / representation | max component of `P^T Q` | Normalized augmented `alpha` | `eta_CPD` | `eta_CPD` vs limit |
|---|---:|---:|---:|---|
| fine canonical | `1.332e-15` | `9.868e-18` | `1.721e-17` | below; not admission |
| fine frozen-literal | `1.159e0` | `5.927e-10` | `9.568e-5` | violated |
| coarse canonical | `1.332e-15` | `4.963e-18` | `4.897e-18` | below; not admission |
| coarse frozen-literal | `1.163e0` | `8.292e-7` | `1.948e-3` | violated |

The captured reduced right-hand side closes against each record's own `Q`,
which falsifies an RHS-only explanation. The direct reconstruction reproduces
the residual split without the earlier replay implementation, which falsifies
a bug in that matrix-residual calculation. It does not replace the still
missing external value/gradient evaluator.

For both roles, the local 4-by-4 `P_top` diagnostic has
`sigma_min / sigma_max = 0.0462`. It is more than `1.0e14` times above its
`4 * 2^-53` binary64 threshold and remains more than `2.0e11` times above the
deliberately more conservative parent-scalar-order diagnostic. Both stored
`Q` matrices have exact identity tails and therefore full structural column
rank. The frozen-literal failure persists at 80 decimal digits: this is a
semantic nullspace defect, not a rank boundary or binary64-roundoff effect.

This diagnostic does **not** supply the still-required formal
`Q^T A Q` semantic-rank certificate or `FactorHealthProfile`.

## Hypothesis disposition

| Hypothesis | Result | Discriminating evidence |
|---|---|---|
| H1: local/global gradient offset corrupts `Q` | **Supported** | Frozen source, locked row maps, direct `Q` oracle, `P^T Q`, CPD, and augmented residual all agree |
| H2: replay matrix-residual implementation creates a false positive | Falsified | Independent 80-digit standard-library matrix reconstruction reproduces the gap; the external value/gradient evaluator remains separately missing |
| H3: rank boundary or binary64 roundoff causes the split | Falsified as cause | `P_top` is far from the threshold; literal `P^T Q` remains order one at 80 digits |
| H4: only reduced-RHS mapping is wrong | Falsified | `P^T Q` fails without an RHS; both reduced RHS payloads close against their own `Q` |
| H5: capture misread the full Lagrange layout | Falsified | Frozen source and locked indices independently produce the captured literal map |

## Boundary and follow-up

No registered public outcome difference is established by this internal
representation adjudication, so a public
`IntentionalDifferenceAdjudication/v1` record is not applicable yet. If
validation observes a public difference, it remains unadjudicated until the
validation program materializes a narrow record and obtains human approval.

Production factor admission remains `EVIDENCE_MISSING` pending:

- formal `Q^T A Q` semantic-rank certificates;
- a versioned `FactorHealthProfile`;
- independent value/gradient evaluator and publication witnesses;
- bounded scratch, maximum-live concurrency, and caller thread-lease evidence;
- atomic pack, reload, and reuse semantics.

That admission work is a separate Wayfinder ticket and a prerequisite for the
downstream mechanism-panel comparison.

## Reproduce

The generated replay executable and approximately 300 MB locked corpus are not
versioned. First follow the exact Stage 0 materialization commands in the
parent [`README`](../README.md), which bind the source to RapidRBF commit
`b00160b318d2d1faf27ef6f305960ccadd3061eb` and produce `$replay` and
`$corpus`. Then, from this diagnosis checkout:

```powershell
python tools/prototypes/m3_assembly_diagnosis_throwaway/repro.py `
  --replay-exe $replay `
  --corpus $corpus `
  --repeat 3 `
  --output tools/prototypes/m3_assembly_diagnosis_throwaway/evidence/observed-repro.json `
  --red-on-symptom
```

The final flag intentionally returns exit code `1` when the issue symptom is
present.

```powershell
python tools/prototypes/m3_assembly_diagnosis_throwaway/diagnose.py `
  --corpus $corpus `
  --polatory-source D:\CODE\polatory `
  --output tools/prototypes/m3_assembly_diagnosis_throwaway/evidence/observed-summary.json
```
