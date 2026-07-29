# THROWAWAY PROTOTYPE — Issue 52 replacement controller plan

## Question

After reproducing the three Issue 51 controller-only preflight failures, what
diagnostic-first controller/evidence boundary and single immutable replacement
execution plan can validly re-run the unchanged double-double refinement
candidate without reusing or mixing any Issue 51 observation?

This prototype records a planning decision. It does not execute the candidate,
materialize the accepted reference, run a target profile, or admit a factor
route or corpus.

Frozen plan SHA-256:
`08036fb07eb581b5fce2664066956640be45cae136068ad69bb7b972e3f306ba`.

## Review

Render every decision view:

```text
python tools/prototypes/controller_preflight_replacement_plan_throwaway/tui.py --snapshot all
```

Drive the in-memory review:

```text
python tools/prototypes/controller_preflight_replacement_plan_throwaway/tui.py
```

Use `n`/`p` to move between diagnosis, boundary, execution, and scope; `q`
quits. The TUI persists nothing.
