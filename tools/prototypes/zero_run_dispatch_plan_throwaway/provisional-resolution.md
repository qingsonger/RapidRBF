## Provisional resolution — human review required

The zero-run mechanism is now proven without entering the candidate.

### Diagnosis

[Execute the evidence-path-bound fresh double-double refinement witness cohort](https://github.com/qingsonger/RapidRBF/issues/58)
created a new execution branch at materialization commit
`29b022d89af923720146a9e1d56cf6a25b719bac`, but that commit was already
reachable from the remote diagnostic branch. The target workflow was active,
repository Actions were enabled with all actions allowed, the branch filter
matched, and the exact workflow/branch/head/event run count was zero.

The throwaway probe froze one previously unremote commit,
`283b30eb264024b9a63cc0361bbc277cf5a159e5`, and used two workflows over two
fresh refs:

- On `codex/issue59-dispatch-probe-new-object`, the branch-only and path-gated
  workflows each created one successful `push` run:
  [branch-only run](https://github.com/qingsonger/RapidRBF/actions/runs/30511523100)
  and [path-gated run](https://github.com/qingsonger/RapidRBF/actions/runs/30511523102).
  The event carried the exact commit in its `commits` array.
- On `codex/issue59-dispatch-probe-ref-only`, created afterward at the
  identical already-remote commit, the
  [branch-only run](https://github.com/qingsonger/RapidRBF/actions/runs/30511548177)
  still ran once, proving that a `push` event existed, while the path-gated
  workflow created zero runs. Its event had `created=true`, an all-zero
  `before`, the exact `after`, and an empty `commits` array.

This isolates the first invalidity: the already-remote ref creation supplied no
changed files to the `paths` filter, so GitHub suppressed the cohort before a
run identity existed. Workflow registration, repository policy, and branch
filtering did not fail. The absence of a run says nothing about candidate
behavior.

This matches GitHub's documented event-associated workflow lookup,
conjunctive branch/path filters, and rule that a path-filtered workflow does not
run when no files changed:

- https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows#workflow-triggers
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#git-diff-comparisons

### Frozen replacement plan

The proposed successor is named **Execute the unique-commit-path-bound fresh
double-double refinement witness cohort**. It preserves `paths` and the
accepted execution shape while changing only the dispatch closure:

1. Start from exact materialization commit
   `29b022d89af923720146a9e1d56cf6a25b719bac`.
2. Create exactly one fresh child commit locally. It may only bind the
   successor/branch identity, add a content-addressed path-matching dispatch
   marker, add the exact run-cardinality guard and `actions:read`, and update
   issue-scoped artifact names without changing topology or semantic contents.
3. Keep that child unreachable from every remote ref until its exact SHA,
   changed-path inventory, source/controller/workflow/plan bindings, zero
   candidate calls, absent execution branch, and zero exact matching runs are
   human-ratified.
4. Perform exactly one dispatch:
   `git push origin <fresh-child-sha>:refs/heads/codex/execute-unique-commit-path-bound-refinement-witness`.
5. Require the resulting event to bind the exact ref/head, all-zero `before`,
   `created=true`, and `commits=[<fresh-child-sha>]`.
6. After all four zero-entry lanes close and immediately before unlock, query
   workflow `323339010` by exact workflow/branch/head/event. Only the unique
   current run at attempt 1 may emit the existing candidate unlock.

Zero runs are externally `INVALID_UNJUDGED`; more than one run or any rerun
withholds the unlock and is `INVALID_UNJUDGED`. No second push, alternate
dispatch, rerun, partial/replacement retry, attempt mixing, or favorable
selection is permitted.

The four native lanes, 277 ready-gated plus 25 root-bound checks per lane,
root-bound same-handle terminal closure, exact artifact topology, candidate,
reference, six sources, 18 RHS identities, double-double precision and stop
rule, `168*n` accounting, thresholds, resources, workers `1/2/8`, live-thread
ceilings `12/12/16`, one-attempt non-compensation, and zero-reuse rules remain
unchanged.

Removing `paths`, adding a default-branch `workflow_dispatch`, using `create`,
and reusing the invalid execution branch were rejected because the fresh
path-matching child commit closes the proven defect while preserving the
narrowest existing trigger and immutable one-attempt contract.

### Frozen artifacts

- Context branch:
  [`codex/diagnose-zero-run-dispatch`](https://github.com/qingsonger/RapidRBF/tree/d1ba10e3f662c22a06b79eab99f53a803fadef57/tools/prototypes/zero_run_dispatch_plan_throwaway)
- Fixed evidence SHA-256:
  `935e25ce28e05b542eab47e570ba00681f1129c11ef295cd9c9a7b08dc97f4e6`
- Replacement plan SHA-256:
  `3d5415e6ca3bc0ba0b1c350c90246f0a20b83a0b5f0e931a705b2fab6b800daa`
- Probe candidate calls: `0`

**Proposed resolution:**
`ZERO_RUN_DISPATCH_DEFECT_PROVEN_AND_REPLACEMENT_PLAN_FROZEN`

Per the prototype HITL gate, please accept, adjust, or reject this diagnosis
and replacement plan before this ticket is closed, the map is updated, or the
successor is created.
