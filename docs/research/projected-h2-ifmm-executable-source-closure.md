# Projected H2/IFMM executable-source closure

Checked 2026-07-31. This note answers a narrow prerequisite to
[Issue 66](https://github.com/qingsonger/RapidRBF/issues/66): whether an
already-published implementation can be frozen as the required projected
hierarchical approximate-factor candidate without writing result-affecting
factor code. It does not choose the issue's disposition and no candidate
factor, application, or solve was run.

## Finding

**No inspected executable source is already the frozen candidate.** H2Pack
and H2Opus supply useful `H^2` construction/matvec substrates, but their
available factorizations are respectively HSS and TLR. STRUMPACK supplies
HSS/BLR/HODLR factorizations, not `H^2`. Turning any of them into the Issue 66
candidate would require result-affecting implementation choices for at least
the projected operator, group ownership, component-wise geometry, or
factor/fill-in recompression. None supplies the required exact four-tier-one
build identities.

The distinction matters because RapidRBF defines this candidate as a
strong-admissibility `H^2`/IFMM-style approximate `LDL^T` of
`B = Q^T A Q`, with exact dense near fields, nested far-field bases, and
recompressed fill-ins
([RapidRBF definition at `0b421c0a`](https://github.com/qingsonger/RapidRBF/blob/0b421c0a3af3ce526af76a375417f80f3d3c65bb/CONTEXT.md#L163-L165)).
An `H^2` matvec, an HSS ULV solve, or a flat TLR factor is not that mechanism.

## Pinned upstream sources

| Source | Inspected default-branch commit | What is already executable | Closure against Issue 66 |
|---|---|---|---|
| H2Pack | [`2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae`](https://github.com/scalable-matrix/H2Pack/commit/2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae) | Kernel `H^2` construction and matvec; separate HSS ULV and SPD-HSS-from-H2 preconditioner | No `H^2`/IFMM factor path |
| H2Opus | [`cbc7985d9716e015c019003073a6f1f5c53dd2fc`](https://github.com/ecrc/h2opus/commit/cbc7985d9716e015c019003073a6f1f5c53dd2fc) | Strong/weak `H^2` construction, matvec, compression and randomized HARA; separate TLR symmetric factors | Factor is TLR, not nested `H^2`/IFMM |
| STRUMPACK | [`be784ab4ced0a603e8643ef011ecd0fc1b77a83e`](https://github.com/pghysels/STRUMPACK/commit/be784ab4ced0a603e8643ef011ecd0fc1b77a83e) | HSS, BLR, HODLR, Butterfly and HODBF matrices; HSS ULV/LU-based factor/solve | No `H^2` format or required factor |

### H2Pack

H2Pack's own capability statement limits the `H^2` path to construction,
matvec and matmul, while describing ULV decomposition/solve under **HSS**
([README](https://github.com/scalable-matrix/H2Pack/blob/2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae/README.md#L1-L60)).
Its SPD-HSS route constructs an HSS preconditioner from an `H^2` matrix
([API](https://github.com/scalable-matrix/H2Pack/blob/2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae/src/H2Pack_SPDHSS_H2.h#L1-L22)),
and the available factor API is explicitly HSS Cholesky/LU ULV
([API](https://github.com/scalable-matrix/H2Pack/blob/2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae/src/H2Pack_HSS_ULV.h#L25-L55)).
That is an HSS approximation followed by ULV, not elimination in one
strong-admissibility `H^2` hierarchy with recompressed fill-ins.

The construction interface also fixes one `krnl_dim` for every point
([types/API](https://github.com/scalable-matrix/H2Pack/blob/2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae/src/H2Pack_typedef.h#L87-L101)),
so it does not already encode mixed one-scalar value groups and indivisible
full-gradient groups of a different size. Its built-in admissibility test
declares a pair admissible when separation succeeds in any raw coordinate
axis
([implementation](https://github.com/scalable-matrix/H2Pack/blob/2d9ad18b3b8cc4f6b0631b1ee0be383dafbaa5ae/src/H2Pack_utils.c#L10-L27));
it is not Issue 66's per-nonzero-component anisotropy/admissibility predicate.
Supplying projected-`B` entries, variable-size group ownership, or a new
predicate and factor would therefore be implementation work that can change
ranks, near fields, pivots and convergence.

### H2Opus

H2Opus does provide both weak and strong-admissibility `H^2` partitions and
lists construction, Hgemv, Hcompress and randomized HARA
([README](https://github.com/ecrc/h2opus/blob/cbc7985d9716e015c019003073a6f1f5c53dd2fc/README.md#L7-L22)).
Its published factor capability is listed separately as **tile-low-rank**
symmetric factorization, not an `H^2` factor. The source reinforces this
boundary: its LDL-like routine accepts `TTLR_Matrix`, performs dense
**unpivoted** block `sytrf`, and updates TLR columns
([TLR source](https://github.com/ecrc/h2opus/blob/cbc7985d9716e015c019003073a6f1f5c53dd2fc/include/h2opus/core/tlr/tlr_sytrf.h#L600-L688));
the example leaves that call commented out
([example](https://github.com/ecrc/h2opus/blob/cbc7985d9716e015c019003073a6f1f5c53dd2fc/examples/tlr/test_tlr.cpp#L145-L168)).

The shipped strong predicates use one bounding-box distance and diameter
test
([edge and center predicates](https://github.com/ecrc/h2opus/blob/cbc7985d9716e015c019003073a6f1f5c53dd2fc/include/h2opus/util/geometric_admissibility.h#L25-L69)).
A custom predicate could encode RapidRBF's component-wise anisotropy and
equality branch, and HARA could sample projected `B`, but both are new
candidate-defining integration. HARA and TLR update compression are adaptive
randomized algorithms, not the frozen SVD sign/degenerate-subspace and
original-block/fill-in recompression semantics. Thus H2Opus is a plausible
construction or experimentation substrate, not an executable closure.

### STRUMPACK

STRUMPACK's current first-party overview enumerates HSS, BLR, HODLR,
Butterfly and HODBF formats, not `H^2`
([README](https://github.com/pghysels/STRUMPACK/blob/be784ab4ced0a603e8643ef011ecd0fc1b77a83e/README.md#L36-L85)).
Its dense HSS API can compress from matrix multiplication plus element
extraction callbacks, which could expose projected `B`, but its factor is
explicitly ULV
([HSS API](https://github.com/pghysels/STRUMPACK/blob/be784ab4ced0a603e8643ef011ecd0fc1b77a83e/src/HSS/HSSMatrix.hpp#L213-L337))
and internally applies pivoted dense LU
([factor source](https://github.com/pghysels/STRUMPACK/blob/be784ab4ced0a603e8643ef011ecd0fc1b77a83e/src/HSS/HSSMatrix.factor.hpp#L36-L123)).
This is not the symmetric strong-admissibility approximate `LDL^T` requested
by the ticket.

The HSS construction policies are explicitly randomized, including adaptive
restart/sample choices
([options](https://github.com/pghysels/STRUMPACK/blob/be784ab4ced0a603e8643ef011ecd0fc1b77a83e/src/HSS/HSSOptions.hpp#L82-L126)).
They do not define Issue 66's deterministic SVD degeneracy conventions or
one fill-in ownership/aggregation/recompression schedule. STRUMPACK also
contains no coordinate-group or component-wise anisotropy authority for the
projected RapidRBF operator; adding those rules and changing the factor
format would be result-affecting work.

## Portability and local closure

Issue 66 requires source/dependency/compiler/runtime identities and native
build identities for Windows x86_64, Linux x86_64 glibc, macOS arm64 and
macOS x86_64. An upstream source commit is not those four identities. At the
inspected revisions, H2Opus's top-level build distinguishes Darwin from a
generic `.so` branch
([Makefile](https://github.com/ecrc/h2opus/blob/cbc7985d9716e015c019003073a6f1f5c53dd2fc/Makefile#L30-L53)),
while STRUMPACK's checked-in CI executes only Ubuntu
([workflow](https://github.com/pghysels/STRUMPACK/blob/be784ab4ced0a603e8643ef011ecd0fc1b77a83e/.github/workflows/test.yml#L1-L12)).
These facts do not prove the code cannot be ported; they prove the required
four-target, content-addressed build closure is not already supplied by the
upstreams.

The local repository was inventoried at
[`0b421c0a3af3ce526af76a375417f80f3d3c65bb`](https://github.com/qingsonger/RapidRBF/commit/0b421c0a3af3ce526af76a375417f80f3d3c65bb)
and across local/remote branch trees. No H2Pack, H2Opus or STRUMPACK source,
lock, adapter, factor implementation, or four-target build materialization
exists. The only matching branch artifact is Issue 65's
candidate-closure **audit** at
[`b25486f099bf62ac64724c984a09e90477249dd9`](https://github.com/qingsonger/RapidRBF/blob/b25486f099bf62ac64724c984a09e90477249dd9/tools/prototypes/projected_h2_ifmm_qualification_throwaway/evidence/CANDIDATE_CLOSURE_AUDIT.md);
it explicitly does not implement or execute a factor candidate.

Therefore any executable binding for Issue 66 still needs a separately
reviewed implementation/integration step. This is a source-closure result
only, not a recommendation or decision on either exclusive issue
disposition.
