# THROWAWAY PROTOTYPE — hierarchy semantic admission

This directory prototypes the immutable rank and canonical-nullspace gate for
the complete M1–M4 1k/10k hierarchy. It is not a production solver and never
invokes a factor backend.

Run the self-test controls and synthetic end-to-end fixture:

```powershell
$env:OPENBLAS_NUM_THREADS = "16"
uv run --locked python certify.py --self-test
```

Run the unit tests:

```powershell
uv run --locked python -m unittest -v
```

Hash and validate a production inventory without claiming semantic closure:

```powershell
uv run --locked python certify.py `
  --manifest C:\path\to\corpus\hierarchy.manifest.raw.json `
  --inventory-only `
  --output inventory-report.json
```

Materialize all 420 rank, 204 Q/nullspace, and one materialized negative-control
certificate:

```powershell
$env:OPENBLAS_NUM_THREADS = "16"
uv run --locked python certify.py `
  --manifest C:\path\to\corpus\hierarchy.manifest.raw.json `
  --output admission-report.json
```

Production input must close the immutable 12-workload, 204-block, 216-carried
factor-source inventory and verify every artifact hash from the adjacent
`manifest.lock.json`. Synthetic fixtures are accepted only by `--self-test`.

NumPy SVD and inverse results are untrusted witness proposers. Admission
authority comes only from the analytic outward checker described by the frozen
profile. Each outward endpoint, width, and threshold is also serialized as an
exact binary64 hexadecimal string. Anything the checker cannot enclose is
reported as `EVIDENCE_MISSING` or, after a genuine completed precision
straddle, `IndeterminateRank`.

The profile must match the certifier's pinned canonical hash; changing a
judgment rule and merely recomputing the profile's self-hash is rejected as
`IntegrityMismatch`. A genuine binary64 threshold straddle installs the exact
dyadic precision checker and requests 256, 512, 1024, then 2048-bit outward
enclosures. Resource denial during that started ladder remains
`EVIDENCE_MISSING`.

Every CLI report binds the byte identities of `certify.py`, `exact_rank.py`,
`pyproject.toml`, `uv.lock`, and the supplied rank profile. It also records the
Python, NumPy, BLAS/LAPACK, platform, binary64, and thread-environment
coordinate. Reproduce checked evidence with
`OPENBLAS_NUM_THREADS=16`; the certifier verifies both the environment and
the effective loaded OpenBLAS controller count.

`--output` is a fresh-path contract. The certifier fsyncs a same-directory
temporary file and publishes it without replacement; an existing report is
never overwritten. Rejection diagnostics are published the same way and the
process exits nonzero.

When `--max-resource-units` is supplied, all 420 rank-subject grants are
computed from immutable-lock shapes before any payload is materialized as an
array. One over-limit subject rejects the complete semantic run as
`ResourceDenied`. Loss of precision authority after a threshold straddle has
started remains `EVIDENCE_MISSING`; it is never relabeled as a completed
`IndeterminateRank` decision.
