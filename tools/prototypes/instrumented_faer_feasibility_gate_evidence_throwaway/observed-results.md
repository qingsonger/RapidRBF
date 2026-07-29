# Observed results

The frozen cohort disposition is
`FEASIBLE_FOR_216_FACTOR_QUALIFICATION`. All four required lanes produced the
same disposition with no reported problems.

| Lane | Projected peak bytes | Retained bytes | Projected backward error | Factor backend entries / checkpoints | Cancel acknowledgement | Cancel backend entries / checkpoints |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Linux x86_64 glibc | 101,761,063 | 33,570,800 | 1.420337517129258e-17 | 33 / 466,986 | 346,161 ns | 2 / 26,945 |
| macOS arm64 | 34,652,199 | 33,570,800 | 1.725388254569498e-17 | 1 / 6,175 | 6,807,209 ns | 1 / 258 |
| macOS x86_64 | 38,846,503 | 33,570,800 | 1.420337517129258e-17 | 33 / 478,611 | 2,753,870 ns | 3 / 51,820 |
| Windows x86_64 | 43,040,807 | 33,570,800 | 1.420337517129258e-17 | 33 / 463,723 | 2,845,600 ns | 2 / 27,730 |

The projected-factor backward-error threshold was
`1.454480980100925e-11`. The coarse factor used 359 peak bytes, retained 256
bytes, and produced zero backward error in every lane against a
`2.842170943040401e-14` threshold.

Every lane also demonstrated:

- exact scheduled peak and retained-byte accounting;
- denial at one byte below both factor schedules without entering the backend;
- cancellation after a backend signal within the frozen deadline;
- preservation of the previously successful projected factor across cancellation;
- zero failed-factor, production-factor, and production-solve publication;
- complete private retained-state cleanup.

The canonical machine-readable record is the extracted `cohort-summary.json`;
the per-lane `lane-observation.json` files retain the full measurements, controls,
candidate binding, lane identity, and source hashes.
