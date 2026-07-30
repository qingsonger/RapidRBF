# PROTOTYPE — wipe me: zero-run dispatch diagnosis

## Question

This throwaway logic prototype asks which server-side gate suppressed the Issue 58
cohort and whether a fresh one-push plan can make exactly one candidate-bearing
attempt observable before candidate entry. It distinguishes workflow
registration, repository policy, `push` event creation, branch filtering, and
path-diff filtering without calling the numerical candidate.

Run the interactive state model with:

```powershell
python tools/prototypes/zero_run_dispatch_plan_throwaway/tui.py
```

## Remote probe

The probe uses one commit and two fresh remote refs:

- `codex/issue59-dispatch-probe-new-object` receives the commit while it is not
  reachable from any remote ref.
- `codex/issue59-dispatch-probe-ref-only` is then created at the identical
  already-remote commit.

Two tiny workflows listen to both refs. The branch-only workflow proves whether
a `push` trigger exists. The path-gated workflow additionally proves whether
GitHub constructed a non-empty changed-file set. Neither workflow checks out,
builds, or enters the candidate.

The discriminating matrix is:

| New-object branch | Ref-only branch | Meaning |
| --- | --- | --- |
| branch-only = 1; path-gated = 1 | branch-only = 1; path-gated = 0 | `push` exists; the empty path diff suppressed Issue 58 |
| branch-only = 1; path-gated = 1 | branch-only = 0; path-gated = 0 | no `push` trigger exists for the ref-only update |
| anything else | anything else | evidence is invalid or a different mechanism is active |

`fixed-evidence.v1.json` captures observations after both refs are created.
The observed matrix was `(1, 1)` for the new-object branch and `(1, 0)` for
the ref-only branch. The ref-only branch's branch-only run carried
`event_name=push`, `created=true`, the exact head SHA, an all-zero `before`,
and an empty `commits` array. This proves that the `push` event existed while
the path-diff gate suppressed the second workflow.

The resulting `replacement-execution-plan.v1.json` keeps `paths`, requires one
fresh local-only child commit with a matching dispatch marker, and adds an
exact-run cardinality check to the zero-entry aggregation before it may emit
the candidate unlock.

Frozen artifact digests:

- `fixed-evidence.v1.json`:
  `935e25ce28e05b542eab47e570ba00681f1129c11ef295cd9c9a7b08dc97f4e6`
- `replacement-execution-plan.v1.json`:
  `3d5415e6ca3bc0ba0b1c350c90246f0a20b83a0b5f0e931a705b2fab6b800daa`

Primary GitHub behavior:

- [Workflow trigger lookup and event-associated workflow version](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows#workflow-triggers)
- [`push` branch and path filters](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push)
- [Changed-file and new-branch diff construction](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#git-diff-comparisons)
- [Exact workflow-run filtering](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow)
