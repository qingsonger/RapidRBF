# Canonical hierarchy admission contract

This successor contract closes the prerequisite identified by
[Admit the canonical dense-factor corpus for mechanism-panel use](https://github.com/qingsonger/RapidRBF/issues/36).
It does not alter or promote the earlier representative dense-factor corpus.

## Scope and inventory

The source registry contains eight solver-panel rows: M1–M4 at the 1k and
10k rungs. Those rows expand to twelve positive hierarchy fixtures because
each M4 row requires all three named valid geometries:
`clustered-near-boundary`, `near-coincident`, and `nonuniform-boundary`.
The separate 1k `rank-invalid` geometry is a materialized negative control
and contributes no positive workload, block, or factor source. Non-finite,
malformed, and resource-denial cases are admission-tool controls rather than
positive corpus entries.

The frozen Polatory hierarchy expands those rows to:

- 192 level-1 fine blocks and twelve level-0 coarse blocks;
- 204 carried `Q^T A Q` sources;
- twelve carried coarse `P_top` sources;
- 216 carried factor sources in total; and
- twelve non-carried workload-global `LagrangeBasis` construction
  decompositions, recorded as auxiliary use-sites.

The 100 trial decompositions used while searching for an unisolvent point set
are generator internals, not carried factor sources. Fine blocks carry no
`P_top` factor and publish no polynomial coefficient. The two frozen-literal
M3 records with a local gradient offset remain diagnostic defect fixtures and
are excluded from the positive inventory.

## Canonical hierarchy and row map

The hierarchy profile is the frozen Polatory two-rung profile:

- level count
  `max(ceil(log10(scalar_rows / 2048)), 0) + 1`;
- fine-to-coarse ratio `10`;
- maximum pre-polynomial fine-leaf scalar order `1024`;
- overlap quota `0.5`; and
- a configured level-0 coarse scalar target of `2048`, evaluated through the
  frozen logarithm/power expression. Under the locked clang-cl 19.1.5
  `/O2 /fp:precise` environment that expression converts to the effective
  integer target `2047`.

Domain order and inner ownership masks are materialized, not regenerated from
an STL-dependent sort. Selected polynomial value rows precede the remaining
domain rows. The sole canonical scalar-row map is:

```text
value row      = global value index
gradient row   = source_value_rows
                 + 3 * global_gradient_point_index
                 + component
component      = x, y, z
```

`Q=[Q_top;I]` is constructed from those global Lagrange rows. No local value
count may replace `source_value_rows`.

The valid M4 near-coincident fixture uses row pairs `(4,5)`, `(6,7)`, and
`(8,9)` at dyadic centers `1/4`, `1/2`, and `3/4`. The pair axes are `x`,
`y`, and `z`; endpoints are the outward binary64 neighbors of
`center +/- 2^-13`, so every total separation is strictly greater than
`2^-12`. The pairs remain in the same geometric locality. They are not moved
between domains to hide conditioning, and they remain distinct from the exact
duplicate-row negative control.

## `RankScalingProfile/v1`

The issue resolution adopts the content-addressed
`rapidrbf-rank-scaling-v1` profile in
`admission/rank-scaling-profile.v1.json`. Its canonical profile hash is
`8d60d932464e04c1ce052ecf33acc93f6e72d424ba05d1af7e40cf69b456731e`;
the certifier pins that hash in code, so a semantic edit followed by a
self-consistent hash rewrite is still `IntegrityMismatch`. Its mechanics are
normative for this corpus:

1. Treat every finite binary64 coordinate as its exact dyadic value.
2. Use the workload-global bbox over value and gradient coordinates.
3. For each axis, use exact
   `center=(min+max)/2` and radius `max(abs(x-center))`.
4. Use scale one for zero radius; otherwise use the smallest power of two not
   below the radius.
5. Construct the fixed physical monomial observation matrix after that
   coordinate-basis transform. Gradient rows are differentiated with respect
   to physical coordinates.
6. Apply one deterministic row-then-column pass of power-of-two max-absolute
   equilibration. A zero row or column receives exponent zero.
7. Apply bbox scaling plus equilibration to `P` and coarse `P_top`. Apply only
   algebraic equilibration to the physical, hash-bound `Q^T A Q`.

Automatic rank uses
`tau_rank=max(rows,columns)*2^-53`. An outward ratio enclosure wholly above
the threshold is `Admitted`; one wholly at or below is `RankDeficient`; a
straddle escalates through 256, 512, 1024, and 2048 bits. A final unresolved
straddle must have width at most `tau_rank/8` and returns
`IndeterminateRank`; a wider or unavailable authority remains
`EVIDENCE_MISSING`. Every endpoint and threshold is serialized with an exact
binary64 hexadecimal representation.

The installed precision authority is
`exact-dyadic-gram-sturm-outward-v1`. It treats each equilibrated binary64
entry as an exact dyadic rational, forms the smaller exact Gram matrix,
computes its characteristic polynomial with exact Faddeev-LeVerrier
arithmetic, removes repeated factors, isolates the least and greatest roots
with a square-free Sturm chain and requested-bit dyadic bisection, then
propagates those root intervals and rounds the ratio endpoints outward by
exact comparison. It invokes no backend. The canonical limits are minimum
dimension eight, 100,000 matrix elements, 1,000,000 Gram term-products, and
2,048 bisection iterations. Every canonical `P` and `P_top` subject fits;
a larger `QTAQ` straddle may fail closed as `EVIDENCE_MISSING`. A genuine
control matrix crosses the binary64 authority at 53 bits and closes through
this production checker at 256 bits.

Rank resource preflight uses only artifact shapes already validated against
the immutable lock. For a `rows x columns` subject, retained logical units
are `rows*columns` for the subject,
`3*rows*columns+2*min(rows,columns)^2` for the proposer, and
`8*rows*columns+4*min(rows,columns)^2` for the checker. The complete
420-subject plan is checked before any artifact becomes an array or any
derived rank subject is constructed; one over-limit subject rejects the
whole semantic run as `ResourceDenied`. Resource loss after a genuine
threshold straddle starts but before the required final narrow enclosure
completes is unavailable authority and therefore `EVIDENCE_MISSING`.

The stable pre-backend states adopted here are `Admitted`,
`EVIDENCE_MISSING`, `MalformedCorpus`, `IntegrityMismatch`, `NonFinite`,
`ResourceDenied`, `RankDeficient`, `IndeterminateRank`, and
`NullspaceViolation`. No rank or rejection path calls a factor backend.

Before any semantic judgment, the CLI captures one immutable execution
coordinate: the length-prefixed byte closure of `certify.py`,
`exact_rank.py`, `pyproject.toml`, `uv.lock`, and the exact supplied profile
bytes; Python/NumPy identity; Windows build; binary64 properties; NumPy BLAS
build metadata; and the unique loaded OpenBLAS controller including DLL
basename, DLL SHA-256, version, architecture, environment, and effective
thread count. The canonical run requires scipy-openblas 0.3.30 and both
`OPENBLAS_NUM_THREADS=16` and an effective count of sixteen. CLI outputs use
a fresh-path contract: a same-directory fsynced temporary is atomically
published without replacement, and rejection diagnostics also exit nonzero.

## Canonical-Q certificate

For each block, exact rational arithmetic defines

```text
Q* = [-(P_top^T)^-1 P_tail^T; I].
```

The exact construction proves `P^T Q*=0` and the identity tail proves
structural rank `m-l`. The captured binary64 `Q_top` need not be bitwise equal
to a newly rounded `Q*`; it must use the canonical global row map and its exact
dyadic normalized `P^T Q` residual must be at most `2^-32`. The hash-bound
captured `Q` is the one used to assemble the carried `Q^T A Q`.

## Independent physical evaluator

Workload fixtures bind literal value and gradient coordinates, observation
payloads, requested and resolved polynomial degree, nugget, ordered RBF
families and parameters, and each component's row-major anisotropy. The
evaluator is independent of Polatory, Eigen, and every solver/factor backend.
It consumes untrusted coefficient witnesses but recomputes the physical
kernel action from coordinates and model data with outward arithmetic.
`evaluator/physical-evidence-profile.v1.json` is the independent
`RapidRBF/PhysicalEvidenceProfile/v1` judgment input, with canonical SHA-256
`cf64f2b26e2a3f4844a5c63027deb5bd4e1f856f0c7f45d4d2afdcccbff724a1`.
The evaluator verifies both its declared and compiled pinned hash. Precision,
all residual/QTAQ allowances, coefficient roundoff, CPD threshold, scratch,
and pair-work formulas are parsed from that profile and exercised by
profile-driving tests. The only accepted interval coordinate is exactly
256-bit directed multiprecision; smaller or larger precision is rejected
before corpus payloads are opened.

For displacement `d=x_target-x_source`, physical derivatives use
`g=A^T g_iso(A d)` and `H=A^T H_iso(A d) A`. Assembly signs are `+phi`,
source-gradient `-g`, target-gradient `+g`, and gradient-gradient `-H`.
Nugget appears only for the same local value-row identity. Polynomials remain
in physical coordinates.

Fine certificates check `lambda=Q gamma`, exact inner-mask scatter,
`Q^T(A_phys lambda-d)`, and the CPD side condition. They do not invent or
scatter `c`. Coarse certificates check the complete
`A_phys lambda+P_phys c-d` value and gradient equations, full scatter,
polynomial recovery, and the CPD side condition. With `0/0:=0`,
`eta_CPD+alpha_CPD` must be at most `2^-32`.

The coefficient closure covers the complete
`lambda=[Q_top;I]gamma`: the top `l` rows use the outward
`gamma_r*sum_abs` binary64 dot-product allowance and all `r` identity-tail
rows must be bitwise equal. For a physical action row, `scale_upper` is the
outward sum of absolute kernel-component, nugget, and polynomial
contributions after multiplying by the corresponding coefficient. Its
allowance is

```text
value:    scale_upper*2^-43 + |rhs|*2^-40
gradient: scale_upper*2^-38 + |rhs|*2^-35
```

Fine projection propagates row allowance `k` as
`allowed_tail[k]+sum_a |Q_top[a,k]|*allowed_top[a]`.

The captured factor candidate must also close entry by entry against the
independently reconstructed congruence

```text
Q^T A_phys Q =
  A22 + Q_top^T A12 + A12^T Q_top + Q_top^T A11 Q_top.
```

For a value-only entry its allowance is

```text
physical_component_scale*2^-43
  + (transform_scale + |captured_QTAQ|)*2^-40
```

For an entry involving a derivative, the exponents are `-38` and `-35`. The
captured reduced RHS must enclose `Q_top^T rhs_head+rhs_tail` within
`gamma_(l+1)*sum_abs`, where
`gamma_k=(k*2^-53)/(1-k*2^-53)`, and
`QTAQ*gamma=rhs_reduced` must pass the applicable physical row allowance.
The entry, reduced-RHS, and witness-equation checks are all mandatory;
captured `QTAQ` is evidence under comparison, never a physical oracle.

Before payloads are opened, the evaluator must grant the locked bytes of all
used coordinate/model/index/mask/Q/QTAQ/RHS/witness payloads plus
`1024*max(m)` scratch, and pair work

```text
sum[
  components*(m*(m+1)/2 + 3*gradient_points)
  + l*l*r + 3*l*r*(r+1)/2
  + r*r + (l*r+r) + m*l + l*r
  + (fine:l*r | coarse:m*l)
].
```

One byte or pair below either grant is `ResourceDenied`. The evaluator
streams physical entries through `O(m)` action accumulators and `O(l*m)`
congruence seams and never materializes dense `A_phys`. A rejected factor
must still publish atomic diagnostics and then make the CLI exit nonzero.
The summary, control report, and every block certificate bind the acceptance
profile schema/ID/hash. Both reports also bind the embedded
`Cargo.toml`/`Cargo.lock`/`physical-evidence-profile.v1.json`/`src/*.rs`
source closure and the running release executable SHA-256 and byte length.

This ticket may publish only hash-bound semantically admitted factor sources
and evaluator certificates. `ValidatedFactor`, factor packing/publication,
thread ownership, factor-health policy, faer qualification, backend
selection, persistent storage, and the 100k rung belong to the successor
factor-path and storage tickets.
