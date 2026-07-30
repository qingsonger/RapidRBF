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
`replacement-execution-plan.v1.json` is added only after the probe supports a
sound fail-closed plan.
