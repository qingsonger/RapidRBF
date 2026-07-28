# THROWAWAY PROTOTYPE - solver-stack solve-plan lab

Run it from the repository root:

```powershell
python tools/prototypes/solver_stack_comparison_throwaway/tui.py
```

Print one non-interactive frame for review or capture:

```powershell
python tools/prototypes/solver_stack_comparison_throwaway/tui.py --snapshot
```

## Question

Does the proposed invariant-checked solve plan expose the decisions that
actually couple at RapidRBF scale: dense local/coarse factorization,
orthogonalization, flexible GMRES restart memory, algebraic observation versus
terminal certification, multilevel RAS topology/factor storage, temporary I/O,
complete work budgets, and ownership of the thread grant?

More concretely, can a reviewer use this lab to decide which stack shapes are
contractually admissible, which are only comparison probes, and exactly what
evidence is still required before choosing the v1 solver and resource model?

This is a decision prototype, not a Rust implementation or a benchmark.
Resource arithmetic is limited to exact counts and explicit reservations.
Labelled source illustrations never become admission bytes. Unknown operator,
workspace, hierarchy, output, and runtime categories stay `UNMATERIALIZED`;
they can never imply admission. The lab never invents convergence or runtime
measurements. It prints a plan-shape fingerprint plus every immutable binding
requirement; it does not pretend that fingerprint is a fixture/evidence-bundle
identity. Every counterfactual evidence view is visibly marked `WHAT-IF` and
assumes the missing immutable manifest is supplied.

## Controls

- `s` - next canonical prototype case (never an acceptance ID)
- `d` - next dense algebra substrate
- `l` - next local/coarse factor algorithm
- `k` - next Krylov variant
- `a` - next orthogonalization/reorthogonalization policy
- `p` - next preconditioner topology
- `f` - next RAS factor-store policy
- `c` - next explicit resident-factor/recompute-pool cap
- `o` - next algebraic observation schedule
- `t` - next thread-ownership policy
- `n` - next canonical configured-thread lane (1, 2, physical-core)
- `b` - next complete work-budget policy
- `x` - next lifecycle/affinity/cache lane
- `y` - next tier-one evidence platform
- `m` - next Krylov window (restart length, or unrestarted iteration cap)
- `g` - next total memory grant
- `e` - next evidence/counterfactual view
- `v` - compare the next decision axis
- `r` - reset
- `q` - quit

Every action redraws the complete state. The useful feedback is where a
contract gap is missing, an evidence requirement is too weak, a resource charge
is counted in the wrong place, or two choices should not be allowed to compose.
The terminal success authority never cycles: it is always the complete external
value/gradient residual plus evaluator-error and CPD-side certificates inside
declared work budgets.

The registered restarted-window menu is deliberately only `m=5/32/64`.
`m=16` requires a later accepted bracket; `100` belongs only to the fixed
unrestarted Polatory-shape comparator. Thread ownership and configured-thread
lane are separate axes: `t` chooses who owns workers, while `n` chooses the
accepted 1/2/physical-core lane. Every `L1` release case rejects anything but
the physical-core lane.

## Audited seeds

The lab starts from accepted or frozen material:

- [Compare Rust linear-algebra, Krylov, and multilevel preconditioner stacks](https://github.com/qingsonger/RapidRBF/issues/13)
- [Define the v1.0.0 acceptance workload matrix](https://github.com/qingsonger/RapidRBF/issues/9)
- [Define the backend-neutral matrix-kernel contract](https://github.com/qingsonger/RapidRBF/issues/10)
- [Choose the v1.0.0 acceleration backend strategy](https://github.com/qingsonger/RapidRBF/issues/12)
- [Prototype the differential and resource measurement harness](https://github.com/qingsonger/RapidRBF/issues/15)
- [Set the numerical and convergence acceptance standard](https://github.com/qingsonger/RapidRBF/issues/16)
- `docs/research/engine-solver-and-dependency-options.md`
- `docs/adr/0001-use-a-private-action-level-matrix-kernel-adapter-seam.md`
- `docs/adr/0002-separate-measurement-evidence-from-acceptance-judgment.md`
- `docs/adr/0004-target-ferreus-for-v1-large-smooth-qualification.md`

Supporting primary-source notes live in `evidence/`. They distinguish source
facts from inferences and open empirical questions.

- `evidence/polatory_baseline.md`
- `evidence/rust_candidates.md`
- `evidence/alternatives_and_scenarios.md`

## Arithmetic boundary

The displayed FGMRES basis charge is:

```text
8 * scalar_unknowns * (2 * krylov_window + 1)
```

It counts the `V` and right-preconditioned `Z` bases only. The shared ledger
also charges the coefficient vector and the selected factor reservation when
those values are materialized. Prepared operator state, dense workspace,
hierarchy/transfer scratch, certification/output staging, allocator overhead,
and concurrent high-water remain named unknown reservations until a prototype
or captured factor corpus supplies them.

The scalar 1M Polatory source audit illustrates about 9.37 GB of packed factor
scratch and 10.53 GB of factor reads per frozen four-level preconditioner
application. It is approximate, source-derived, and never charged as an exact
reservation. It is attached only as a note to its matching prototype case and
is never generalized to Hermite, alternative topologies, or a RapidRBF peak.
The explicit-cap LRU and recompute choices instead reserve the resident-factor
or recompute-pool cap selected with `c`; dense factorization workspace and
scratch-disk capacity remain separate named reservations. Resident-if-admitted
remains unmaterialized where no hierarchy exists.

Evidence readiness is independent of workload tier. The canonical prototype
rows are `M1`-`M4`, `S1`, `S2`, `R1`, and `L1`; `s` cycles their explicitly
labelled scale/family cases without inventing new row IDs. The lab models only:
missing evidence; a counterfactually complete immutable bundle with no threshold set
(`COLLECTED, UNJUDGED`); and a visibly hypothetical selected-plan/lane gate
with accepted-ready authority and separately versioned thresholds. That closes
only one case/platform/thread/lifecycle bundle; it does not aggregate required
sibling lanes or promote another row, tier, platform, or RapidRBF v1 globally.
