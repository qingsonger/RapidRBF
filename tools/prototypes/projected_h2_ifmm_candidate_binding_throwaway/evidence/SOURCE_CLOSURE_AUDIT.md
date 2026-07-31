# Issue 66 executable source-closure audit

## Question

Can [Freeze and materialize the exact projected H2/IFMM candidate and
qualification authority](https://github.com/qingsonger/RapidRBF/issues/66)
bind one executable candidate now, without either:

1. leaving result-affecting implementation choices to the later execution
   ticket; or
2. implementing a production-scale RapidRBF solver inside a Wayfinder map
   whose stated destination is a decision-complete specification?

## Accepted inputs

- [Map the RapidRBF v1.0.0 migration from
  Polatory](https://github.com/qingsonger/RapidRBF/issues/1) says the effort
  plans the migration and does not implement RapidRBF; prototypes and tasks
  exist only to remove decision uncertainty.
- [Choose the post-RAS v1 solver and preconditioner qualification
  route](https://github.com/qingsonger/RapidRBF/issues/64) froze a projected
  strong-admissibility `H2`/IFMM-style approximate-factor family and a bounded
  qualification experiment, but admitted no implementation.
- [Qualify the projected H2/IFMM factor route on the complete mechanism
  panel](https://github.com/qingsonger/RapidRBF/issues/65) was live-ratified
  `INVALID_UNJUDGED` because ten result-affecting executable-identity choices
  remained open. Candidate entry stayed forbidden.
- Issue 66 requires exact source, dependency, four-target build, construction,
  fixture, controller, schema, verifier, and immutable-plan identity before
  any candidate coordinate may enter.

## Local source closure

The repository and its captured prototype branches contain decision documents,
corpora, factor-path controls, dense-factor experiments, FGMRES/RAS
experiments, and the Issue 65 source-closure TUI. They do not contain an
implementation of the projected hierarchical approximate-factor candidate.

A history-wide source search:

```powershell
git log --all --oneline --name-only `
  -G 'H2|IFMM|hierarchical approximate' `
  -- '*.rs' '*.c' '*.cc' '*.cpp' '*.h' '*.hpp' '*.py'
```

finds the Issue 65 audit, an unrelated M3 diagnostic, and the rejected KiFMM
adaptation probe. It finds no projected `B = Q^T A Q` hierarchical factor
source. Thus there are no candidate source bytes from which dependency,
compiler, runtime, or tier-one build identities can presently be derived.

## Upstream source closure

The primary-source investigation is captured in
[projected-h2-ifmm-executable-source-closure.md](../../../../docs/research/projected-h2-ifmm-executable-source-closure.md).
It pins and inspects the current source identities of H2Pack, H2Opus, and
STRUMPACK.

Those sources provide useful but different mechanisms:

- `H2Pack` constructs and applies `H2` matrices, and separately provides HSS
  ULV / SPD-HSS preconditioning.
- `H2Opus` constructs, applies, orthogonalizes, and compresses `H2` matrices,
  while its symmetric factor path uses a separate tile-low-rank format.
- `STRUMPACK` provides HSS, BLR, HODLR, and butterfly compression/factor paths,
  not a nested strong-admissibility `H2`/IFMM factor.

None supplies the exact Issue 66 combination: canonical projected-operator
entries; indivisible value/full-gradient groups; component-wise anisotropic
admissibility and compact-support partitioning; fixed deterministic
SVD/degeneracy semantics; the specified nested transfers; positive-pivot
approximate `LDL^T`; or the stated fill-in ownership, aggregation, and
recompression schedule.

Adopting any of them therefore requires a result-affecting fork rather than a
source/build binding. The fork itself would be the missing candidate
implementation.

## Why partial materialization is not closure

The complete-panel identities, three 100k geometry fixtures, append-only
schema, independent verifier, and immutable controller plan are independently
materializable. So is a control-plane executable that refuses candidate entry.

Those assets cannot identify the numerical candidate. Building that shell on
four targets would prove only that the shell builds. It would not bind the
source that constructs bases, eliminates supernodes, owns and recompresses
fill-ins, or applies the approximate factor. Calling such builds "candidate
build identities" would repeat the Issue 65 authority defect under a content
hash.

## Planning-boundary finding

Closing the missing source is not a small adaptation or a throwaway probe. It
means designing and implementing the projected hierarchical factor that the
future RapidRBF solver will execute. That is destination work, not a remaining
decision on the way to a specification.

The current map can consistently choose one of two scopes, but cannot silently
mix them:

1. keep the declared planning destination, freeze the mechanism and
   qualification contract in the specification, and make executable-source
   qualification an implementation/release gate; or
2. redraw the destination to include implementation of the solver candidate,
   then rechart the work rather than treating it as one prototype ticket.

That scope choice belongs to a live human decision.

## Proposed disposition

**`INVALID_UNJUDGED`**, with authority/feasibility defect
**`NO_EXECUTABLE_CANDIDATE_SOURCE_CLOSURE`**.

This disposition means:

- no projected hierarchical factor candidate is accepted or rejected;
- no implementation, dependency, threshold, pivot, rank, storage policy, or
  tier-one route is selected;
- all existing numerical, convergence, resource, cancellation, threading,
  cleanup, identity, and no-mixing controls remain unchanged;
- no candidate observation may be reused; and
- Issue 66 does not claim the frozen source/build/fixture/evidence disposition.

The proposed newly sharp frontier question is:

> Must an executable solver candidate be qualified before `/to-spec`, or
> should the specification freeze the projected hierarchical mechanism
> contract and make exact-source qualification an implementation/release gate?

## Zero-entry record

This audit executed:

| Candidate coordinate | Count |
| --- | ---: |
| factor setup | 0 |
| factor application | 0 |
| solve | 0 |

No observed numerical, rank, work, resource, portability, or structural-path
result informed the finding.
