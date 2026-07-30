# Issue 61 captured diagnosis

## Question

Why does the accepted restarted right-FGMRES / same-hierarchy RAS family fail
the complete direct certificate only on `M3-HERMITE-10K`, and what is the
smallest falsifiable mechanism change plus exact next experiment?

## Frozen inputs

- Canonical hierarchy corpus:
  `38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`.
- Repaired factor reference manifest:
  `6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a`.
- Accepted Issue 32 source:
  `e14c9d94527e92f5d2591a77aa1d4d1b968d3be9`.
- All Issue 61 numerical probes use the complete direct M3 matrix action and
  unchanged fit/CPD thresholds.

## Feedback loop and structural diagnosis

The agent-runnable red loop is:

```powershell
.\repro-issue61.ps1 -MaximumIterations 1
```

The final reproduction result is
`0b716a01c32314208e6e5fd9b817e4c2bfe7100b70df455d54619472d9188158`.
Before any restart, the frozen coarse-fine-coarse route ends with value
residual `1.2233131107184336e-1`, gradient residual
`1.9573092124181182`, and CPD eta `2.3975701079225635e-18`.

The mechanism audit is
`77c230d6e7ec36035db07b80c79f9d9de75df80b6ed0306aa1758395e3ab7f5a`.
It established:

- every value row and gradient point has exactly one fine inner owner;
- every gradient point is restricted/scattered as one canonical three-channel
  triplet;
- every carried local matrix agrees with the corresponding complete-direct
  restriction to maximum absolute difference `8.8817841970012523e-15`;
- the coarse selection contains 1,109 value rows, 314 gradient points
  (942 gradient scalar rows), and all four polynomial columns;
- value and gradient coarse-selection escape ratios are nearly identical
  (`0.86645` and `0.86544` means), so a channel-specific ownership or coarse
  scatter defect is not supported;
- the complete operator's `GG` maximum is `48.193754666666685`, versus
  `6.6089279954343283` for `VV`, a `7.292` ratio.

This closes canonical row/channel application, fine ownership/scatter, and the
previous parity-defect hypothesis. The one-step red loop plus the accepted
robust/parity audit also closes restart and orthogonalization as the first
cause.

## One-variable probes

No row changes thresholds, overlap, iteration budget, or more than the named
mechanism variable.

| Probe | Iterations | Value residual | Gradient residual | Result identity |
| --- | ---: | ---: | ---: | --- |
| Frozen baseline | 1 | `1.2233131107184336e-1` | `1.9573092124181182` | `0b716a01c32314208e6e5fd9b817e4c2bfe7100b70df455d54619472d9188158` |
| Symmetric block-max channel scale (`Dg=0.37031399801146325`) | 100 | `8.0696758953403669e-2` | `1.2919924847046671` | `d055095388a9e325678e1883310006d160150408e28d7fc5c7421f6a36b74598` |
| Fine-coarse-fine reverse sweep | 8 | `9.3030059469137949e-1` | `1.8282426079987275` | `e75275deeddb38fcfa959c289e84caee0149306c5e36f956870a503575bee1bc` |
| Enriched coarse target 4096 | 1 | `1.9292853285608980e-2` | `3.7417100141222281e-1` | `b594374b672a1c502aaf44797154a1efc1669bb666797bf1391d468443125007` |
| Enriched coarse target 4096 | 8 | `1.6643840044590463e-2` | `3.1469910876600626e-1` | `9eb8d9f551d9fbdec6869414b9fd8b48536cbfafb22a75a90d41e75119effa16` |
| Enriched coarse target 4096 | 32 | `1.1168001480767853e-2` | `8.7080604278222840e-2` | `1ddb8e609ea23a4919b24ad4194cec192837607b6f9a2c9d6e3927753e15d27f` |

Scaling changes the trajectory but does not close the gradient gap. Reversing
the sweep trades gradient improvement for an order-of-magnitude value
regression. Only the coarse-capacity change improves both channels by more than
fivefold in the first step and continues improving both through one complete
`m=32` cycle. The 32-step probe used 64 internal operator actions, 1,024 local
solves, 64 coarse solves, and a 4,223,508,480-byte process peak.

## Diagnosis

The evidence supports `COARSE_VALUE_GRADIENT_COUPLING_CAPACITY_GAP`, not an
implementation/parity defect. The frozen 2,047-scalar coarse selection is too
small to carry the global coupled error modes of the mixed `th3 + gau` Hermite
system under the unchanged work grant. Channel scaling and sweep ordering
affect where the residual lands but cannot supply the missing global
correction content.

The 4,096 target is a falsifiable qualification candidate, not a selected
production setting. Its prototype factor is diagnostic-only and cannot be
reused as qualified evidence.

## Frozen next experiment

Run exactly one candidate, with no coarse-target, overlap, scaling,
orthogonalization, topology, or restart sweep:

- Generate a canonical `4096` scalar-target coarse selection using the same
  `DomainDivider`, polynomial anchors, point/gradient multiplicities, canonical
  row map, and complete local matrix semantics as the admitted corpus.
- Materialize and independently qualify each new coarse factor against its
  frozen binary64 system before candidate entry. Keep this run-scoped evidence
  distinct from production factor-backend admission.
- Fix restarted right-FGMRES to robust MGS/DGKS, `m=64`, maximum 100
  iterations, the accepted coarse-fine-coarse residual-correction topology,
  no channel scaling, unchanged overlap, and at most 240 preconditioner-internal
  operator actions.
- Execute distinct current-coarse and coarse4096 controls for all six 10k
  workloads (`M1`, `M2`, `M3`, and the three `M4` cases) plus the six unchanged
  1k identity controls. Use complete direct solver actions and complete
  external certificates throughout; do not mix Issue 32 endpoints into the
  new cohort.
- Retain the accepted 8-thread OpenMP / 1-thread MKL lane, 8 GiB process peak,
  exact factor/action/run identities, dynamic backward checks, CPD, cleanup,
  and no-retry/no-threshold-relaxation rules.
- `COARSE4096_GLOBAL_SURVIVOR` requires M3 and every previously passing
  workload to pass the unchanged complete certificate within all work and
  resource grants. Any numerical or resource regression is
  `COARSE4096_REJECTED_DIAGNOSTIC_ONLY`. Missing or invalid evidence is
  `INVALID_UNJUDGED`.

The complete cohort requires live human ratification before closure. It may
carry at most this one survivor into the 100k storage/resource experiment.
