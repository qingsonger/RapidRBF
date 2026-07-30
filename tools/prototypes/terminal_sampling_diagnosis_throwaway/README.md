# Terminal sampling diagnosis (THROWAWAY)

Question: what exact terminal-adjacent process-tree sampling race invalidated
seven otherwise complete Issue 53 profiles, and what evidence must a
candidate-independent controller diagnostic capture before a new execution
plan can be considered?

This directory is disposable diagnostic code. It does not execute the
refinement candidate, repair or rerun Issue 53, admit a factor route, or turn
Issue 53 observations into successor counts.

Run the red-capable captured-trace loop:

```text
python tools/prototypes/terminal_sampling_diagnosis_throwaway/diagnose.py --feedback-loop
```

The expected non-zero result is the exact symptom: all seven captured
terminal-root closures are classified as invalid by the Issue 53 policy.
The replay also exposes why those observations cannot be reinterpreted:
the failing adapter call did not record the PID, so the stored evidence cannot
prove that the disappearing process was the root owned by the sole waiter.

Run the candidate-independent boundary probes:

```text
python tools/prototypes/terminal_sampling_diagnosis_throwaway/native_probe.py
```

These probes execute only a synthetic Python helper. They compare the Issue 53
policy with a diagnostic-only root-bound policy, and keep non-root ESRCH,
non-ESRCH, wrong-handle, and late/missing terminal closure nonpassing.

The workflow `.github/workflows/diagnose-terminal-sampling.yml` additionally
forces the helper to cross the native inventory boundary at the two captured
failure phases: Linux process-group membership and macOS BSD identity. It is
diagnostic-only and has no candidate build or execution step.
