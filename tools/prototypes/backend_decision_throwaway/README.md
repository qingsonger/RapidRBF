# THROWAWAY PROTOTYPE — backend candidate evidence lab

Run it from the repository root:

```powershell
python tools/prototypes/backend_decision_throwaway/tui.py
```

To print one non-interactive frame for review or capture:

```powershell
python tools/prototypes/backend_decision_throwaway/tui.py --snapshot
```

## Question

Does the proposed backend-selection state model make the important distinction
between a route that fits the matrix-kernel contract, a candidate that is allowed
only in a forced probe, and a candidate that has enough evidence to enter
`Auto`? In particular, does it lead to a credible v1 route for every canonical
action, kernel form, reuse shape, scale, and tier-one platform without turning
missing measurements into claims?

This is a decision prototype, not a backend implementation or benchmark. Its
`current audited evidence` view contains only accepted contracts and facts
already captured by the repository. The other evidence views are visibly marked
counterfactuals used to test promotion and fallback logic. Qualitative
throughput and memory descriptions are hypotheses until the named probes exist.

## Controls

- `n` — next workload scenario
- `f` — next kernel family/model in the scenario
- `a` — next canonical action
- `x` — next anisotropy class
- `d` — next dimension
- `p` — next tier-one platform
- `e` — next evidence/counterfactual view
- `c` — focus the next candidate
- `r` — reset
- `q` — quit

Every action redraws the complete decision state. Under current evidence, any
large smooth comparison intentionally remains `UNRESOLVED`; the prototype must
not turn an audit recommendation into a backend decision. The useful feedback
is where the displayed route feels too permissive, too conservative, or fails
to expose an important risk.

## Evidence seed

The prototype is seeded from:

- [Define the backend-neutral matrix-kernel contract](https://github.com/qingsonger/RapidRBF/issues/10)
- [Define the v1.0.0 acceptance workload matrix](https://github.com/qingsonger/RapidRBF/issues/9)
- [Freeze the executable Polatory behavior oracle](https://github.com/qingsonger/RapidRBF/issues/6)
- `docs/research/engine-solver-and-dependency-options.md`
- `docs/research/polatory-validation-performance-release-baseline.md`
- `docs/adr/0001-use-a-private-action-level-matrix-kernel-adapter-seam.md`

No result in this prototype promotes a backend. Promotion requires the
content-addressed differential, certification, resource, repeated-evaluation,
million-scale, cancellation, and tier-one packaging evidence named by the
prototype.

The only numeric seed shown is the frozen Polatory 1k × 1k lower-rung direct
anchor (`0.268579 s`, `19,058,688` peak private bytes, `25,174,016` peak
working-set bytes) from
`baseline/polatory-4a30beb-windows-x86_64/runs/scale-input-ladder/outputs/resources.json`.
It is non-normative diagnostic evidence, not a measurement of any RapidRBF or
FMM candidate. The 10k/100k/1M files in that bundle freeze inputs; they do not
claim candidate execution.
