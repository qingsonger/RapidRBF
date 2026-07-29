# THROWAWAY PROTOTYPE — controller-valid thread evidence

## Question

Can an external controller distinguish a normal macOS `proc_pidinfo` ESRCH
process-exit race from a real loss of thread evidence without weakening the
hard thread ceiling or changing the frozen double-double refinement
candidate? This prototype exercises the controller state machine only. It
does not execute the candidate, reuse Issue 49 observations as acceptance
evidence, admit a factor route, or change any numerical, resource, witness,
target, or retry decision.

The proposed answer is
`CONTROLLER_VALID_REFINEMENT_WITNESS_PLAN_FROZEN`. The complete immutable
replacement plan is in `controller-evidence-plan.v1.json`.

## Run

Interactive review:

```text
python tools/prototypes/controller_thread_evidence_plan_throwaway/tui.py
```

Render every frozen scenario without interaction:

```text
python tools/prototypes/controller_thread_evidence_plan_throwaway/tui.py --snapshot all
```

The model is pure and in-memory. The TUI is throwaway review scaffolding.
