# Captured evidence

## Frozen identities

- Canonical hierarchy corpus:
  `38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`
- Repaired factor reference manifest:
  `6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a`
- Full panel JSON:
  `5a9667b0d9fc96b3066e6ea2600ca969b4344d90b9a66139ea17f319a6ac6a31`
- Full panel transcript:
  `b0d4942c3cb817b65f6844cfac7c72a7e5914f9bf9060a82513101a7085d4820`
- Orthogonalization audit JSON:
  `c3229ca05aaa1a2997e9cc87df94776f4048c529ebcb539ca9902d13b779b0bb`
- Orthogonalization audit transcript:
  `d56e72448c9e699695b0133e6b56298f4ffafbd1a17716a4858699f757d968f7`

Raw results remain in the prototype worktree's ignored
`.prototype-cache/results/` directory. They are deliberately separate from
the throwaway source commit.

## Full panel

- 216 runs covered all 12 registered workloads: 144 exact-action 1k
  robust/parity runs and 72 robust 10k runs.
- All 216 factor sources passed qualification, including 648 repaired-reference
  RHS judgments. The evidence makes no factor-backend release-admission claim.
- Peak process working set was 4,573,929,472 bytes, below the 8 GiB ceiling.
- All 1k combinations certified in one iteration. Robust MGS+DGKS and legacy
  one-pass CGS differed slightly in residual rounding but not in outcome or
  iteration count.
- No configuration screened on all six 10k workloads. Seven configurations
  screened on five; all missed only M3-HERMITE-10K.
- Projected-deflated RAS with `m=64` ranked first among the incomplete
  configurations: five screens, 153 total iterations, 339 total counted
  operator actions, and a 15,484,128-byte maximum Krylov basis.
- M3-HERMITE-10K used a complete direct matrix action. Every topology/window
  exhausted 100 iterations. The least-bad endpoint was frozen
  residual-correction RAS with `m=64`: value residual
  `8.1776806348535347e-2`, gradient residual `1.2238805446024865`.

## Orthogonalization/direct audit

- The diagnostic frontier was projected-deflated `m=64` and frozen
  residual-correction `m=64`.
- Across M1, M2, and all three M4 10k workloads, robust and parity runs had the
  same iteration counts and all 20 runs passed the complete direct certificate.
- On M3-HERMITE-10K, both orthogonalizations followed the same failure
  endpoints for both topologies; all four runs exhausted 100 iterations and
  failed the complete direct certificate.

## Decision exposed to live review

The evidence supports accepting the finding that this candidate family has no
global winner. It does not support selecting a solver default. The next map
decision must add or repair a mixed-gradient mechanism before the 100k
resource/storage experiment can use a global solver configuration.
