# Instrumented in-process faer feasibility probe

## Disposition

**`UNJUDGED_EVIDENCE_MISSING`.**

The candidate-independent profile and exact stock source facts are frozen, but no exact fork, executable two-factor control, or qualified-host target witness exists. The current evidence therefore supports neither feasibility nor rejection.

## Frozen identities

- Projected FactorHealthProfile: `00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3`.
- Stock source closure: `530103a7c8f62e8cf225045d39410b9d36e67d11f5acf6793f403bb0fc1a9fb9`.
- Two-factor plan: `5b288e33d13464ae79948b1afcb2d76d0d08f9c81b27010ad51d4906cfc66892`.
- Candidate binding: `MISSING_EXACT_FORK`.

## Gates

| Gate | State | Reason |
| --- | --- | --- |
| Mechanical candidate-independent profile projection | `PASS` | The allowlisted rule fields are canonicalized and hashed before any candidate observation. |
| Exact stock faer/private-gemm/dyn-stack source closure | `PASS` | All complete crate closures and the selected source surfaces match the accepted direct-faer evidence. |
| Exact hash-bound narrow fork | `EVIDENCE_MISSING` | The binding deliberately contains no fork commit, patch-set digest, per-target source digest, or executable identity. |
| Maximum projected-B and coarse-P_top execution | `NOT_REACHED` | Candidate execution cannot begin before one exact binding freezes the implementation being observed. |
| ExecutionLease allocation and temporary-storage closure | `NOT_REACHED` | Stock x86 private-gemm still retains a TLS Vec and declares zero scratch; no fork exists to route it or the selected dyn-stack paths through a lease. |
| Deterministic exact N-minus-one denial | `NOT_REACHED` | There is no candidate preflight calculation to challenge with N-1 before permit acquisition, allocation, and backend entry. |
| Bounded pivot, panel, packing, macro-kernel, and solve cancellation | `NOT_REACHED` | The selected stock paths contain no cancellation vocabulary; no fallible checkpoint implementation or maximum unpolled work-unit record exists. |
| Four tier-one target and qualified-host witnesses | `EVIDENCE_MISSING` | Every target lacks a bound candidate build and qualified-host acknowledgment-latency witness. |
| Prior-state preservation, zero publication, and cleanup | `NOT_REACHED` | No executable factor or solve attempt exists from which to observe cancellation, cleanup, and prior-state reuse. |

## Target witnesses

| Target | Build | Factor run | Allocation | N-1 | Cancellation | Host latency |
| --- | --- | --- | --- | --- | --- | --- |
| `x86_64-pc-windows-msvc` | `EVIDENCE_MISSING` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `EVIDENCE_MISSING` |
| `x86_64-unknown-linux-gnu` | `EVIDENCE_MISSING` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `EVIDENCE_MISSING` |
| `aarch64-apple-darwin` | `EVIDENCE_MISSING` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `EVIDENCE_MISSING` |
| `x86_64-apple-darwin` | `EVIDENCE_MISSING` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `NOT_REACHED` | `EVIDENCE_MISSING` |

## What the source audit establishes

- The accepted rule set can be projected mechanically without carrying the rejected direct candidate identity forward.
- The low-level Bunch-Kaufman and full-pivot paths accept caller-provided matrices, permutations, and dyn-stack scratch.
- The selected x86 matmul path still declares zero scratch while private-gemm owns a persistent TLS `Vec` plus a reentrant `Vec` fallback.
- The selected stock factor, matmul, and solve paths expose no cancellation checkpoint vocabulary.

## Evidence still required

- one immutable fork/patch-set identity shared by all target bindings;
- executable allocation traces showing every selected byte charged to one `ExecutionLease` and zero temporary-storage use;
- exact N and N-1 controls before permit acquisition and backend entry;
- measured maximum unpolled pivot, panel, packing, macro-kernel, and solve work units;
- cancellation, prior-state reuse, zero-publication, and cleanup controls on both factors; and
- build identities plus qualified-host acknowledgment-latency evidence on all four tier-one targets.

Missing evidence is not an evidence-backed rejection. The mechanism-panel qualification remains blocked.
