# Preflight evidence-path diagnosis and replacement plan (THROWAWAY)

Question: why did the sole Issue 56 root-bound refinement-witness attempt
become `INVALID_UNJUDGED` before candidate entry, and can one fresh plan close
the evidence-path defect without weakening any accepted controller, numerical,
resource, or non-reuse gate?

Review the complete in-memory decision:

```text
python tools/prototypes/preflight_evidence_path_plan_throwaway/tui.py --snapshot all
```

Drive the review interactively:

```text
python tools/prototypes/preflight_evidence_path_plan_throwaway/tui.py
```

The fast diagnostic loop is intentionally red on the immutable Issue 56
evidence:

```text
python tools/prototypes/preflight_evidence_path_plan_throwaway/diagnose.py
```

It reproduces two independent evidence-path defects. Every complete 277-check
lane journal produced the Issue 56 authority-check name, while the shared
verifier still required the Issue 53 name. After the release artifact existed,
the final judge's `preflight-*` selector also selected that release alongside
the four lane artifacts, then downloaded it again by exact name.

Validate the proposed replacement contract:

```text
python tools/prototypes/preflight_evidence_path_plan_throwaway/diagnose.py --validate-replacement
```

The proposed Issue 58 materialization gives the authority check one shared
definition, downloads every artifact by exact name into a declared kind/lane
directory, forbids recursive singleton discovery, preserves the accepted
1,108 ready-gated plus 100 root-bound checks, and keeps the candidate locked
until one exact unlock exists. It performs no candidate execution in Issue 57.

The proposal remains `PROVISIONAL_HITL_REQUIRED`. The human must accept,
adjust, or reject it before Issue 57 can close.

Frozen artifact digests:

- `replacement-execution-plan.v1.json`:
  `a0132ab26af2e4e99fb8edeeecc2b51a8e0090b6e0dccf6f804573bad0ff97b1`
- `fixed-evidence.v1.json`:
  `d40b45978176c8d527a66d6968f3a2930194b191481d41f564552bc9008c7312`
