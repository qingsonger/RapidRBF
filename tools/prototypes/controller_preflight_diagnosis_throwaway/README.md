# THROWAWAY PROTOTYPE — Issue 52 controller-preflight diagnosis

## Question

Which exact Issue 51 controller-only preflight checks fail on the frozen
Windows x86_64, macOS arm64, and macOS x86_64 lanes, and what failure-detail
boundary is sufficient to freeze one new immutable execution plan without
executing the candidate or mixing Issue 51 observations?

This prototype starts from Issue 51 commit
`53e9d28aa78a3bbe2cbb486a1ef35f1a3aad5387`. It verifies and invokes the
unchanged Issue 51 controller model, observer, and native helper. Every check
result is atomically persisted before any aggregate status is computed.

It does not build or execute the refinement candidate, materialize a reference,
run a target profile, or judge/admit a factor route.

## Run

Run the local platform's controller-only diagnostic:

```text
python tools/prototypes/controller_preflight_diagnosis_throwaway/diagnose.py --lane-id windows-x86_64 --target x86_64-pc-windows-msvc --lane-witness <lane-identity.json> --output <empty-output-directory>
```

Dispatch all four frozen controller-only lanes:

```text
gh workflow run diagnose-controller-preflight.yml --ref codex/diagnose-controller-preflight
```

The diagnostic command returns success when evidence collection closes, even
when the unchanged Issue 51 controller check is nonpassing. The recorded
`original_controller_status` carries that verdict.
