# Native comparator artifact closure

This is prototype evidence for
[Replay captured local and coarse factors across shortlisted dense substrates](https://github.com/qingsonger/RapidRBF/issues/33).
It does not approve a production native dependency.

## Exact executable coordinate

- source context: Polatory
  `4a30beb08053fb339ce899e255be4b6d3f74aa0c`;
- package context: vcpkg
  `4b77da7fed37817f124936239197833469f1b9a8`;
- package: `intel-mkl 2023.0.0#2`;
- runtime identity: Intel oneMKL `2023.0-Product Build 20221128`;
- ABI: Windows x86_64, LP64, sequential;
- calls: `LAPACKE_dsytrf_work` / `LAPACKE_dsytrs_work`, with an
  independently staged `LAPACKE_dgetrf_work` / `LAPACKE_dgetrs_work`
  diagnostic route;
- layout: `LAPACK_COL_MAJOR=102`, lower triangle, `lapack_int=i32`;
- import libraries:

| Library | SHA-256 |
|---|---|
| `mkl_intel_lp64_dll.lib` | `487B430C0A2BCCA41DC40ABCAB8CBC18471701B621EFB850136F6D45821F5DB4` |
| `mkl_sequential_dll.lib` | `3859198460BD0D04A617A7FECB9CEB9C18F7E8B14EBCB439A0EEBACA7B9D01B2` |
| `mkl_core_dll.lib` | `110C0433D4665F8535174059D9042992CD88E566C7B2B13281FD776A7D46CC02` |

Runtime libraries staged beside both prototype executables:

| Library | SHA-256 |
|---|---|
| `mkl_core.2.dll` | `3E7EDB4328ABF430B62C7C75E33447042DC8033F0CC75910708FD3BB5F27C792` |
| `mkl_sequential.2.dll` | `478FDA28A98021FB7F95B27B2876CAC7346D77C4A491003BA0F50BAF17B66FE3` |
| `mkl_def.2.dll` | `0AFF76A9A8C4618C1F467BF08334EC3A93E92ADA04B62F31864C8F052BEA9745` |
| `mkl_avx2.2.dll` | `CC85F0C3B1F0F02998A14923037873530645A77039E95A6A3FB90A7D01468D41` |

Both build frontends reject a library whose registered SHA-256 does not
match. The replay also checks the loaded runtime version string before a
native attempt and stages exact bytes beside the worker. A filename match is
not sufficient evidence for this coordinate.

`mkl_rt`, the Fortran 95 wrappers, and `libiomp` are outside this coordinate.
The worker disables dynamic adjustment, requests one local thread, and records
the effective maximum. The outer replay owns concurrency.

## Runtime-size observation

| Closure | Observed size |
|---|---:|
| core + sequential | 99.289 MiB |
| minimum CPU-dispatch runtime | 136.622 MiB |
| this host's AVX2 dispatch | 140.793 MiB |
| frozen Polatory six-dispatch closure | 360.918 MiB |

The throwaway build stages both the generic and AVX2 dispatch DLLs beside the
worker so it does not mutate global `PATH`; that local directory contains
178.126 MiB of MKL DLLs. This is staged closure, not proof that both dispatch
modules were loaded during every call.

Even the minimum CPU-dispatch closure exceeds the registered 128 MiB CLI
runtime-closure budget. This is a packaging counterexample, not an acceptance
failure: Stage 0 has no authority to change the release threshold.

## Tier-one closure state

| Target | Executable evidence | Runtime/provenance/license/clean-host closure |
|---|---|---|
| Windows x86_64 | local toolchain, hash-gated import/runtime libraries, loaded version, symbols, and ABI available | `EVIDENCE_MISSING`; minimum closure is already above the registered runtime budget and vcpkg SPDX reports `NOASSERTION` for the MKL license |
| Linux x86_64 glibc | none for this exact provider | `EVIDENCE_MISSING` |
| macOS arm64 | this provider is unavailable | `EVIDENCE_MISSING`; another provider is not the same backend |
| macOS x86_64 | none on this host | `EVIDENCE_MISSING` |

Therefore oneMKL is registered only as the exactly bound Windows native
comparator. It is not a four-target candidate and cannot close the ticket's
tier-one artifact obligation through local numerical success.

## Numerical limits

`DSYTRF`/`DGETRF info > 0` reports an exact zero pivot. It is not the semantic
rank authority. `DGETRF` is partial row-pivoting LU and is not rank revealing.
The packed lower BK factor plus `ipiv` can be serialized into a
RapidRBF-owned record, but `DSYTRS` requires a full `n*n` unpack buffer; that
buffer is transient scratch, not retained packed storage.
