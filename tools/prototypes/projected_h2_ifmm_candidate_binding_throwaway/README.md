# THROWAWAY PROTOTYPE — Issue 66 source-closure review

This prototype answers a narrower prerequisite question for
[Freeze and materialize the exact projected H2/IFMM candidate and qualification authority](https://github.com/qingsonger/RapidRBF/issues/66):
can that ticket produce one executable, content-addressed candidate without
silently turning the Wayfinder map into implementation of RapidRBF?

The map says it plans the migration and does not implement RapidRBF. Issue 66,
however, can reach its frozen disposition only if a complete projected
hierarchical factor implementation already exists or can be adopted without
result-affecting adaptation. The review compares that requirement with:

- the source closure already present in RapidRBF and its captured prototype
  branches;
- the ten executable-identity gaps accepted by Issue 65;
- primary-source facts about the closest upstream hierarchical-matrix
  implementations; and
- the distinction between freezing a qualification contract and implementing
  the candidate that contract would execute.

It never constructs `Q`, builds a cluster tree, calls an SVD, enters factor
setup, applies a preconditioner, or solves a system. Candidate observation
counts remain exactly zero.

Run the in-memory live review from the repository root:

```powershell
python tools/prototypes/projected_h2_ifmm_candidate_binding_throwaway/review.py
```

Print the initial state non-interactively:

```powershell
python tools/prototypes/projected_h2_ifmm_candidate_binding_throwaway/review.py --snapshot
```

The proposed finding is **`INVALID_UNJUDGED`** with defect
`NO_EXECUTABLE_CANDIDATE_SOURCE_CLOSURE`. This is not a numerical or
performance rejection of projected hierarchical preconditioning. It says the
map currently owns a production-scale implementation task while its declared
destination is a decision-complete specification.

The reviewer must accept, adjust, or reject that finding before Issue 66 is
closed or the map is changed.
