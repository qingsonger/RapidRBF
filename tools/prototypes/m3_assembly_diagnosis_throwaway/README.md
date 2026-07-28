# THROWAWAY PROTOTYPE - M3 assembly diagnosis

This diagnostic artifact adjudicates the M3 mixed-Hermite canonical versus
frozen-literal row-map signal from Wayfinder issue 35. It is not a production
solver, a factor-backend selection, or an acceptance threshold.

The scripts use only the Python standard library. They require the locked v2
dense-factor corpus from the earlier prototype and a clean checkout of frozen
Polatory commit `4a30beb08053fb339ce899e255be4b6d3f74aa0c`.

The earlier capture/replay source is frozen at RapidRBF commit
[`b00160b318d2d1faf27ef6f305960ccadd3061eb`](https://github.com/qingsonger/RapidRBF/tree/b00160b318d2d1faf27ef6f305960ccadd3061eb/tools/prototypes/dense_factor_replay_throwaway).
Its generated corpus and replay executable are intentionally ignored. From a
clean RapidRBF checkout on the registered Windows environment, materialize
them with:

```powershell
$stage0 = 'C:\tmp\rapidrbf-stage0-b00160b'
git fetch origin codex/prototype-dense-factor-replay
git worktree add --detach $stage0 b00160b318d2d1faf27ef6f305960ccadd3061eb

python "$stage0\tools\prototypes\dense_factor_replay_throwaway\run.py" `
  --recapture `
  --polatory-source D:\CODE\polatory `
  --results-dir C:\tmp\rapidrbf-r35-results `
  --capture-build-dir C:\tmp\rapidrbf-r35-capture `
  --replay-target-dir C:\tmp\rapidrbf-r35-target
```

The commands below then use:

```powershell
$replay = 'C:\tmp\rapidrbf-r35-target\release\rapidrbf-dense-factor-replay-throwaway.exe'
$corpus = 'C:\tmp\rapidrbf-r35-results\corpora\sha256-ac282ee95062b4463d2e0a0c0ca83da454660e0e5048fa79ea3a07da280ef26e'
```

## Red-capable reproduction

Run the actual three-substrate replay for the canonical and frozen-literal fine
records:

```powershell
python tools/prototypes/m3_assembly_diagnosis_throwaway/repro.py `
  --replay-exe $replay `
  --corpus $corpus `
  --repeat 3 `
  --output tools/prototypes/m3_assembly_diagnosis_throwaway/evidence/observed-repro.json `
  --red-on-symptom
```

The command exits `1` when it reproduces the exact issue-35 symptom: both
reduced systems solve accurately on faer, nalgebra, and oneMKL, while only the
frozen-literal reconstruction has orders-of-magnitude larger augmented and CPD
residuals. The predicate bounds are diagnostic symptom detectors, not numerical
acceptance thresholds.

## Independent adjudication

```powershell
python tools/prototypes/m3_assembly_diagnosis_throwaway/diagnose.py `
  --corpus $corpus `
  --polatory-source D:\CODE\polatory `
  --output tools/prototypes/m3_assembly_diagnosis_throwaway/evidence/observed-summary.json
```

The diagnosis independently:

- verifies every file in the locked corpus;
- audits the exact FineGrid and CoarseGrid source expressions;
- checks the canonical and literal flattened row maps;
- derives the polynomial-nullspace basis directly from each local `P`;
- recomputes `P^T Q`, `P^T lambda`, reduced-RHS closure, and the complete
  augmented residual at 80 decimal digits from the binary64 payloads; and
- separates structural representation authority from still-missing production
  factor-health and reduced-matrix rank certificates.

The checked-in human-readable result is
[`evidence/observed-results.md`](evidence/observed-results.md).
