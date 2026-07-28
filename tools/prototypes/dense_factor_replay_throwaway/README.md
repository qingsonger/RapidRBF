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

Rebuild the frozen corpus from the clean Polatory source tree at
`4a30beb08053fb339ce899e255be4b6d3f74aa0c`:

```powershell
python tools/prototypes/dense_factor_replay_throwaway/run.py --recapture
```

Verify and replay the current locked corpus without capturing it again:

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
