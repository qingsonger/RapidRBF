# Issue 62 captured coarse4096 cohort

## Question

Does the one frozen canonical 4,096-target enriched coarse candidate survive
the complete 1k/10k mechanism panel under the accepted restarted
right-FGMRES / coarse-fine-coarse residual-correction RAS topology and strict
execution, factor, certificate, identity, resource, and cleanup controls?

## Frozen execution

- Canonical hierarchy corpus:
  `38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`.
- Existing-factor reference manifest:
  `6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a`.
- Exactly 18 runs: six unchanged 1k identity controls, six current-coarse 10k
  controls, and six coarse4096 10k candidates.
- Complete-direct matrix actions and external certificates throughout.
- Robust MGS/DGKS, `m=64`, maximum 100 iterations, unchanged overlap and
  coarse-fine-coarse residual correction, no scaling, at most 240
  preconditioner-internal operator actions.
- 8 OpenMP threads, 1 MKL thread, and an 8 GiB process peak limit.
- One cohort, no retry and no threshold relaxation.

The complete result is
[`issue62-coarse4096-frozen.json`](issue62-coarse4096-frozen.json), 35,314
bytes, SHA-256
`4879f1da043af898a0a0f2830529a241fb0a64da5ece6df81c467ee3b74e76c3`.
The exact executable/source/input binding, one-attempt ledger, normal exit, and
post-exit cleanup checks are captured in
[`issue62-reproduction.json`](issue62-reproduction.json).

## Evidence closure

- All six unchanged 1k identity controls passed.
- All six current-coarse 10k controls reproduced the accepted boundary: M1,
  M2, and all three M4 cases passed; M3-HERMITE-10K failed.
- All 12 generated coarse4096 QTAQ/P_top factor sources passed all 36
  candidate-independent reference judgments before candidate entry.
- Maximum generated-reference `q` upper bound was
  `5.4250434407940258e-2`; maximum relative enclosure radius was
  `2.9243586605439e-15`.
- All 18 run identities are unique. All action, factor, reference, solution,
  and run identities are present.
- Maximum preconditioner-internal operator actions were `200/240`.
- Maximum process peak was `4,329,594,880 / 8,589,934,592` bytes.
- The result was written atomically and no retry or threshold change occurred.

## Candidate result

The coarse4096 candidate passed M1-EXP-10K, M2-TH3-10K, and all three M4 10k
cases. It did not pass M3-HERMITE-10K:

| M3 control | Iterations | Value residual | Gradient residual | CPD eta |
| --- | ---: | ---: | ---: | ---: |
| Current coarse | 100 | `8.1776806348535347e-2` | `1.2238805446024865` | `2.05445787647073e-18` |
| Coarse4096 | 100 | `3.6434752952778648e-3` | `5.3808841088235727e-2` | `1.83823609921779e-18` |

The larger coarse space improves the M3 endpoint by approximately `22.44x`
in the value channel and `22.74x` in the gradient channel, but both residuals
remain orders of magnitude above the unchanged `2^-24` fit threshold after
the full work grant. The candidate therefore fails the global-survivor
contract.

## Proposed disposition

**`COARSE4096_REJECTED_DIAGNOSTIC_ONLY`**

The 4,096-target enriched coarse candidate remains useful diagnostic evidence
for the proven global coupling-capacity gap, but it is not a production
setting and cannot proceed into the 100k storage/resource experiment. This
result does not admit a solver or dense-factor backend and does not select a
replacement experiment.

Live human ratification is required before Issue 62 may close. Review the full
state with:

```powershell
.\review-issue62.ps1
```
