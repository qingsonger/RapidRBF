# THROWAWAY PROTOTYPE - dense-factor admission disposition

Run the interactive disposition viewer from the repository root:

```powershell
python tools/prototypes/dense_factor_admission_throwaway/tui.py
```

Print the machine-readable disposition:

```powershell
python tools/prototypes/dense_factor_admission_throwaway/tui.py --snapshot
```

Verify that the checked-in snapshot still matches the pure admission model:

```powershell
python tools/prototypes/dense_factor_admission_throwaway/tui.py --verify-evidence
```

## Question

Can the immutable Stage 0 dense-factor corpus at
`ac282ee95062b4463d2e0a0c0ca83da454660e0e5048fa79ea3a07da280ef26e`
be promoted to an admissible input for the M1-M4 1k/10k mechanism panel, or
must it remain diagnostic-only?

This logic prototype makes the fail-closed state model concrete. It binds the
answer to the permanent dense replay and M3 diagnosis commits, checks the five
admission gates named by the Wayfinder ticket, and renders the exact downstream
permissions. It deliberately does not manufacture missing rank, evaluator,
publication, or resource authority from successful backend observations.

## Assumption and boundary

The locked corpus contains eight authoritative canonical representative
records derived from the 10k cases and two M3 frozen-literal defect fixtures.
It is not a complete 1k/10k hierarchy/factor manifest. The frozen-literal
records are excluded from every admissible or diagnostic factor input; they
remain useful only as defect fixtures.

The checked-in result is therefore a negative disposition:

```text
admission_disposition = NOT_ADMITTED
mechanism_input_authority = DIAGNOSTIC_ONLY
downstream_decision_authority = BLOCKED
```

Canonical source matrices and right-hand sides may be force-replayed in private
workers to collect diagnostics. They may not publish a `ValidatedFactor`, name
a production backend, declare mechanism convergence, or advance a mechanism
survivor. The only factor-free bounded fallback is the already registered
identity/no-factor ablation at 1k, and it remains diagnostic-only.

## Files

- `model.py` is the pure fail-closed admission model.
- `tui.py` is the throwaway terminal shell.
- `evidence/admission-bundle.json` is the hash-bound negative-evidence sidecar.
- `evidence/observed-summary.json` is the deterministic model output.
- `evidence/observed-results.md` records the human-readable verdict.

This prototype does not alter the immutable v2 corpus, its replay schema, or
its existing `COLLECTED, UNJUDGED` backend attempts.
