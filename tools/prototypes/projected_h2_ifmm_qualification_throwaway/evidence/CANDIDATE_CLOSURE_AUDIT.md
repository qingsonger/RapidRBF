# Issue 65 candidate-closure audit

## Question

Can the projected hierarchical approximate-factor candidate frozen by
[Choose the post-RAS v1 solver and preconditioner qualification route](https://github.com/qingsonger/RapidRBF/issues/64)
and presented for execution in
[Qualify the projected H2/IFMM factor route on the complete mechanism panel](https://github.com/qingsonger/RapidRBF/issues/65)
be implemented, executed on four tier-one targets, and judged without selecting
result-affecting semantics after the candidate was supposedly frozen?

## Closed controls

The operator boundary, approximate-factor family, leaf capacity, `eta`, spectral
threshold, rank cap, FGMRES grant, external convergence authority, rejection
conditions, complete-panel topology, and setup-only 100k boundary are all
stated. They meaningfully constrain a future candidate.

## Authority defect

They do not identify one executable candidate. At least the following choices
remain open:

- the content-addressed global `Q`/`P_top` construction, reduced-coordinate
  permutation, polynomial-anchor order, and ties;
- signed-zero-normalized coordinate equality, merged value/full-gradient group
  ownership, total order, and ties;
- cluster split axis and position, degenerate-geometry handling, child order,
  and serialized tree identity;
- the component-wise strong-admissibility diameter/distance formula,
  anisotropy metric, equality branch, and compact-support partition;
- the matrices used to build nested bases, deterministic SVD implementation,
  sign/degenerate-singular-value rules, and transfer construction;
- elimination/supernode order, block-pivot interpretation, symmetry handling,
  and arithmetic binding;
- fill-in ownership, aggregation order, recompression schedule, and the exact
  point at which rank/cap overflow becomes a candidate failure;
- candidate source, dependency, compiler, runtime, and four-target build
  digests;
- the append-only evidence schema, independent verifier, attempt cardinality,
  and candidate-entry boundary; and
- content-addressed materializations of the named 100k structural geometries.

Each item can alter numerical rank, pivot validity, factor bytes, setup work,
memory, cancellation points, or FGMRES convergence. Choosing any of them after
looking at candidate outcomes would violate the ticket's no-rebuild and
non-compensating controls. Choosing them before execution but without recording
their identity would make the observations irreproducible and unable to prove
which candidate was judged.

## Proposed disposition

**`INVALID_UNJUDGED`**

This is not a negative H2/IFMM result. No candidate coordinate has entered, so
there is no numerical, portability, rank, work, resource, or structural-path
observation to reuse. Existing thresholds and authorities remain unchanged.

## Proposed successor slice

1. **Freeze and materialize the exact projected H2/IFMM candidate and
   qualification authority.** Bind the missing construction semantics, source,
   dependency/build identities, admitted panel and materialized 100k fixtures,
   controller, evidence schema, independent verifier, and one immutable
   execution plan. Its preflight must execute zero candidate coordinates.
2. **Execute the source-bound projected H2/IFMM complete-panel and 100k
   structural qualification.** Run only the immutable binding. It may resolve
   to the original survivor, rejection, or invalid-unjudged dispositions, but
   it may not select a new tree, rank, threshold, retry, or evidence policy.

Live human ratification is required before Issue 65 may close or either
successor is added to the map.
