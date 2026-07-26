# Reproducible Polatory validation, performance, and release baseline

Status: resolved research for RapidRBF Issue #4

Captured: 2026-07-26

Reference implementation: Polatory `4a30beb08053fb339ce899e255be4b6d3f74aa0c`

## Answer

RapidRBF must not treat a Polatory executable, a Git revision, or the existing
`benchmark.sh` as the baseline by itself. The reproducible baseline is an
immutable evidence bundle that binds together:

1. exact source and dependency identities;
2. the complete build configuration and produced binary hashes;
3. frozen, content-addressed inputs and expected outputs;
4. the command, environment, host, thread, cache, and temporary-storage policy
   for every run;
5. raw numerical and convergence evidence;
6. platform-native resource measurements; and
7. release-installation evidence from clean tier-one hosts.

The local Windows build is useful as the first captured reference, but it is
not yet a replayable or cross-platform baseline. Its original configure
command is absent, its vcpkg provenance is internally inconsistent, the
benchmark value generator is unseeded and unavailable on this host, no
benchmark outputs have been retained, and its CLI directory still depends on
the Microsoft Visual C++ runtime. Those gaps must be closed by the protocol in
this document before numerical or performance gates are calibrated.

Two distinct executable modes are required:

- **canonical mode** uses the unmodified, optimized Polatory binary and is the
  authority for observable results, elapsed time, memory, I/O, thread count,
  and scratch-space measurements;
- **instrumented mode** may expose internal residuals or intermediate arrays,
  but its results are diagnostic and its timing is never mixed with canonical
  performance results.

No million-point workload was run during this research. Such a run is allowed
only after the scale ladder has produced an explicit time, RAM, scratch-space,
and failure-recovery estimate.

## Frozen implementation identity

The first baseline series is named `polatory-4a30beb`. The name is only an
alias; manifests and comparisons must always use the full object IDs below.

| Component | Captured identity | Finding |
| --- | --- | --- |
| Polatory source | `4a30beb08053fb339ce899e255be4b6d3f74aa0c` | Local `main` is clean. |
| ScalFMM source actually built | `0be3d74f17adb28adec7004f712f693ac8ee9901` | Detached, clean checkout under `build/scalfmm/src/scalfmm`. |
| vcpkg gitlink | `4b77da7fed37817f124936239197833469f1b9a8` | The repository submodule identity. |
| vcpkg executable | `2026-03-04-4b3e4c276b5b87a649e66341e11553e8c577459c` | Does **not** match the submodule identity; retain both facts and rebuild before calling the dependency graph canonical. |

Polatory's CMake currently fetches ScalFMM with the mutable `GIT_TAG polatory`
rather than an immutable object ID. A replayable baseline must either patch
the fetch recipe to the resolved SHA or archive and hash the complete resolved
ScalFMM tree. Recording only the branch name is insufficient. See the
[Polatory ScalFMM declaration](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L101-L165).

The vcpkg manifest lists dependencies but has no `builtin-baseline`; the
overlay-only configuration therefore does not make resolution reproducible by
itself. See the
[manifest](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/vcpkg.json#L1-L37)
and
[vcpkg configuration](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/vcpkg-configuration.json#L1-L4).
The canonical rerun must pin the vcpkg commit, add a registry baseline or lock
equivalent, retain the installed status file, and record every package ABI
hash.

### Captured dependency resolution

The current `x64-windows` installed-status database contains the following
direct numerical and test dependencies:

| Package | Resolved version |
| --- | --- |
| Boost modules | `1.90.0` (the manifest metapackage is `2025-03-29`) |
| Ceres | `2.2.0#6` |
| Eigen3 | `5.0.1` |
| fast-float | `8.2.4` |
| FLANN | `2022-10-28` |
| GoogleTest | `1.17.0#2` |
| Intel MKL | `2023.0.0#2` |
| libigl | `2.6.0#1` |

FFTW and pybind11 are not installed in this build because the Python binding
option is off. Transitive dependency versions and ABI hashes remain part of
the required lock record; the table above is not a substitute for the complete
installed-status file.

## Captured Windows build snapshot

This snapshot describes what was inspected, not a portable rebuild recipe.
The original CMake invocation and the build start time are not available.

| Setting | Captured value |
| --- | --- |
| CMake generator | Ninja `1.13.1` |
| CMake | `4.0.3` |
| C++ compiler | Visual Studio 2022 LLVM `clang-cl`, Clang `19.1.5`, target `x86_64-pc-windows-msvc` |
| Language | C++20 |
| Configuration | `Release` |
| C++ flags | `/DWIN32 /D_WINDOWS /GR /EHsc` |
| Release flags | `/O2 /Ob2 /DNDEBUG` |
| vcpkg triplet | `x64-windows` |
| Project options | CLI, examples, benchmarks, and tests on; Python bindings off |
| Linear algebra | MKL, dynamic on MSVC, LP64, sequential |
| Parallel runtime | LLVM OpenMP through `-Xclang -fopenmp` and `libomp.lib` |
| ScalFMM options | MKL on; MPI, StarPU, and CUDA off; checks, examples, tools, and unit tests off |

Polatory deliberately selects MKL on x86-64 and disables Eigen's own
parallelism; OpenMP remains active in evaluation and preconditioning. The
relevant project configuration is in
[top-level CMake](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/CMakeLists.txt#L15-L63)
and
[source CMake](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt#L58-L153).
The resolved ScalFMM cache says `Debug`, although ScalFMM is consumed primarily
as headers in this build. Preserve that cache as evidence, but do not infer a
performance penalty without inspecting emitted compile commands.

The canonical rerun must save the literal configure and build argument arrays,
not a reconstructed shell string. A Windows invocation equivalent to the
captured cache is:

```powershell
cmake -S . -B build-baseline -G Ninja `
  -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_CXX_COMPILER='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/Llvm/x64/bin/clang-cl.exe' `
  -DCMAKE_TOOLCHAIN_FILE="$PWD/vcpkg/scripts/buildsystems/vcpkg.cmake" `
  -DVCPKG_TARGET_TRIPLET=x64-windows `
  -DBUILD_CLI=ON `
  -DBUILD_EXAMPLES=ON `
  -DBUILD_BENCHMARKS=ON `
  -DBUILD_TESTS=ON `
  -DBUILD_PYTHON_BINDINGS=OFF `
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build-baseline --config Release --verbose
ctest --test-dir build-baseline -C Release --output-on-failure `
  --output-junit ctest-junit.xml
```

This is a prospective replay command, not proof of the historical command. A
successful baseline run must retain `CMakeCache.txt`,
`compile_commands.json`, the verbose build log, vcpkg status and install logs,
CTest XML, and hashes of each file.

### Host snapshot

| Field | Captured value |
| --- | --- |
| OS | Windows 11 Pro, `10.0.26200`, build `26200`, 64-bit |
| Machine | Lenovo `21AHA019CD` |
| CPU | 12th Gen Intel Core i7-1260P; 12 physical cores, 16 logical processors |
| Reported maximum clock | 2100 MHz |
| Physical memory | 16,864,305,152 bytes |
| Data volume | NTFS; 615,776,587,776 bytes total; 162,606,252,032 bytes free when captured |
| Scripting runtimes | Python `3.13.5`; `Rscript` not found |
| Relevant environment | `NUMBER_OF_PROCESSORS=16`; no `OMP_*`, `MKL_*`, BLAS, or Rayon controls were set |

This host snapshot is incomplete for authoritative performance work: it lacks
CPU microcode, firmware, power mode, thermal state, CPU affinity, storage
model, virtualization status, background-load sampling, and a clean-runner
image identifier. The first canonical run must add those fields.

### Built artifact snapshot

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `build/src/polatory.lib` | 134,396,922 | `E0DE6F65DF5EABD09BF98A8A6F3805A9F125A856B2727F18FFBF0B1E562416DD` |
| `build/cli/polatory.exe` | 13,902,848 | `95CD325F727E6F56D1656FEB52672A37A5FC655132A232CBB6976F031FFCCFE9` |
| `build/benchmark/points.exe` | 500,224 | `3E06B1F848A4C25A580BC1B3A236D5F0659DBA1B14AAD539097ABC79941C48A2` |
| `build/benchmark/predict.exe` | 5,551,616 | `D0C5C887773532095B2B8C9C4D95801AE1D2C8E62BAFE06005C7A9DA8CCF70B3` |
| `build/test/Unittest.exe` | 9,906,176 | `600736AA60CAEE4915D8CD3D8E2A9D5C8A53744DBA800DA6FE2D98EEEAEF1E52` |

The CLI directory contains 17 files totaling 395,614,076 bytes, including
378,449,984 bytes across eight MKL DLLs. Direct imports also include
`MSVCP140.dll`, `MSVCP140_2.dll`, `VCRUNTIME140.dll`, and
`VCRUNTIME140_1.dll`; those files are not adjacent to the executable. The
captured folder is consequently not a self-contained distribution under the
RapidRBF definition. Microsoft documents central, application-local, and
static runtime deployment options in
[Deployment in Visual C++](https://learn.microsoft.com/en-us/cpp/windows/deployment-in-visual-cpp?view=msvc-170).

## Existing validation and its limits

`ctest -N` exposes one aggregate test, `Unittest`. There are 89 source-level
GoogleTest macros, but no checked-in CTest log, CLI integration suite, wheel
installation suite, or platform release suite. The Python smoke file imports
four modules but is not registered with CTest; the inspected build has Python
disabled.

A bounded one-thread smoke command completed successfully:

```powershell
$env:OMP_NUM_THREADS = '1'
$env:OMP_DYNAMIC = 'FALSE'
.\build\test\Unittest.exe `
  '--gtest_filter=rbf.*:KrylovTest.*' `
  --gtest_brief=1
```

Result: 6 tests passed; GoogleTest reported 31 ms and the outer PowerShell
measurement reported 0.2582943 s. This verifies that a small part of the
captured binary runs; it is not a performance result.

A broader one-thread filter covering RBF evaluators, operators, and symmetric
evaluators did not finish within the deliberately bounded 60-second
observation. The owned process was terminated. At cleanup it had accumulated
179.97 s of CPU time and held 1,527,160,832 bytes in its working set. Because
sampling was not designed as a peak-memory measurement and the process was
killed, neither number is an acceptance datum. It does show that the full
validation suite needs its own estimated, scheduled runner rather than being
treated as a quick smoke test.

Existing source tests are valuable starting oracles:

- fitter cases reach 10,000 value and 10,000 gradient observations and use a
  fit tolerance of `1e-3`, with accuracy checks at tolerance divided by 100
  ([fitter tests](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/interpolation/test_fitter.cpp#L26-L73));
- RBF gradient and Hessian tests use finite differences with `h = 1e-8` and a
  norm tolerance of `1e-4`
  ([RBF tests](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/rbf/test_rbf.cpp#L83-L120));
- the Krylov test compares the reported and true relative residual to
  `1e-12`
  ([Krylov test](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/krylov/test_krylov.cpp#L97-L118)).

These numbers are test-specific. They must not be promoted to one global
RapidRBF tolerance: finite-difference error, FMM approximation error, fit
residuals, derivative scaling, and output comparison have different error
models.

## Existing benchmark and reproducibility gaps

The checked-in benchmark creates training and prediction point sets of 1,000,
10,000, 100,000, and 1,000,000 rows. It passes seed `0` to training-point
generation and seed `1` to prediction-point generation, simulates values using
R/gstat, and then runs all 16 train-by-predict size combinations. It measures
only shell `time`. See
[`benchmark.sh`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/benchmark.sh#L1-L43).

Point generation uses `std::mt19937(seed)` and
`std::uniform_real_distribution`, followed by a minimum-distance filter
([generator entry point](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/points.cpp#L13-L31),
[random-point implementation](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/random_points.cpp#L31-L58)).
The C++ standard does not make the floating-point distribution's exact output
portable across all library implementations, so seed and algorithm name alone
are not enough. Freeze the generated files and hash them.

The R/gstat script does not call `set.seed`; the simulated values therefore
cannot be reconstructed from repository state. It also makes results dependent
on the exact R and gstat versions. See
[`simulate.R`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/simulate.R#L1-L16).
`Rscript` is not installed on the inspected host, and no generated inputs or
results are present in the build tree.

The prediction driver exercises only a three-dimensional exponential
covariance with parameters `{1.0, 0.02}`, polynomial degree 0, and fit
tolerance `1e-4`
([driver](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/predict.cpp#L14-L32)).
It has no warm-up policy, repetition count, random run ordering, variance,
failure timeout, CPU/RSS/scratch/thread capture, or host record.

The existing script is therefore a workload sketch, not the canonical
baseline. Its generated input files may be retained as one compatibility
family only after they are generated once in a declared environment and
content-addressed.

Once those files are frozen, preserve the script's 16 literal Polatory argument
arrays in `run.json`; each has this form:

```text
predict <train-points> <train-values> <prediction-points> <output>
```

with train and prediction sizes independently selected from 1k, 10k, 100k,
and 1M. Invoke the executable through the measurement wrapper rather than the
shell `time` keyword, and never regenerate data in the timed region.

## Numerical and convergence evidence

### Oracle hierarchy

Each comparison record must declare one of these oracle classes:

1. analytic or independently high-precision reference;
2. Polatory's externally observable result at the frozen revision;
3. a RapidRBF self-consistency or metamorphic property.

Analytic or high-precision truth outranks Polatory when they conflict. A
confirmed Polatory defect is recorded as an intentional difference with a
minimal reproducer; it is never silently normalized away. Where no independent
truth exists, compatibility means matching Polatory within a
scenario-specific, empirically calibrated tolerance, not bit-for-bit identity.

### Required compatibility matrix

The frozen datasets must cover:

- dimensions 1, 2, and 3;
- every in-scope RBF family, including parameters at ordinary, small, large,
  and support-boundary values;
- value, gradient, gradient-transpose, Hessian, and symmetric operator paths;
- identity anisotropy, diagonal anisotropy, rotated full anisotropy, strongly
  conditioned but valid transforms, and invalid/singular transforms;
- polynomial degrees and value/gradient constraint mixtures;
- coincident, near-coincident, clustered, uniform, boundary, and
  highly nonuniform point clouds;
- direct evaluation, FMM evaluation, and paired cases on both sides of the
  implementation crossover;
- successful convergence, slow convergence, maximum-iteration exit, invalid
  input, and non-finite input behavior.

Polatory switches non-symmetric evaluation at
`n_source * n_target < 1024 * 1024` and symmetric evaluation at `n < 1024`.
The baseline therefore requires exact boundary pairs immediately below, at,
and above both thresholds, plus cases large enough for approximation error to
be measurable. See
[non-symmetric dispatch](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_evaluator.hpp#L226-L270)
and
[symmetric dispatch](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_symmetric_evaluator.hpp#L222-L252).

Each numeric result file must declare shape, scalar type, byte order, storage
order, units, coordinate convention, anisotropy convention, and the exact
input/output row relationship. Comparisons must retain, at minimum:

- maximum absolute error;
- maximum relative error using an explicit near-zero denominator policy;
- RMS or normalized L2 error;
- component-wise value/gradient/Hessian errors;
- symmetry error where applicable;
- constraint residuals and independent holdout error; and
- counts and locations of NaN, infinity, and signed zero when behavior matters.

Tolerance values are not chosen in this ticket. They must be calibrated from
analytic error, repeated Polatory runs, platform variation, and FMM requested
accuracy, and then frozen per scenario before RapidRBF is judged.

### FGMRES and RAS capture

The integrated solver prints `iter`, `residual`, and `grad_residual`; a `~`
prefix marks a sampled/approximate residual. Preserve stdout verbatim and parse
without dropping that marker. See the
[solver loop](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/solver.hpp#L95-L141).

The residual evaluator samples at most 1,024 value and 1,024 gradient targets
with a default-constructed deterministic `std::mt19937`, then performs a full
fast-evaluator check after the sample passes
([residual evaluator](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/residual_evaluator.hpp#L18-L151)).
Consequently, a baseline convergence record contains:

- every printed iteration row and whether each value was sampled or full;
- requested tolerance, maximum iterations, RAS level and partition parameters;
- terminal status and exception text;
- total iterations and evaluations;
- final independently recomputed value and gradient residuals;
- an instrumented internal FGMRES relative-residual trace, identified as
  diagnostic rather than canonical timing evidence; and
- the preconditioner partition/factorization summary and cache I/O.

FGMRES retains all Krylov basis vectors and all preconditioned vectors, while
its dense Hessenberg storage grows with the iteration limit. The relevant
storage is visible in
[`GmresBase`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/gmres_base.hpp#L49-L89),
[`GmresBase` allocation](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/krylov/gmres_base.cpp#L35-L47),
and
[`Fgmres`](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/fgmres.hpp#L11-L26).
Memory is therefore expected to include an `O(nk + k^2)` Krylov component.
Record `n`, `k`, restart policy, and termination reason with every memory
measurement.

RAS factors are streamed through a temporary `BinaryCache`. Windows opens the
file with delete-on-close semantics; Unix unlinks it immediately while the
descriptor remains open
([cache implementation](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/binary_cache.hpp#L18-L105)).
Directory size after exit is therefore not a valid scratch-space measurement.

## Canonical evidence bundle

Every build/run series is stored under an immutable series ID:

```text
baseline/
  schema-version.txt
  builds/<build-id>/
    identity.json
    host.json
    configure-argv.json
    build-argv.json
    environment.json
    CMakeCache.txt
    compile_commands.json
    vcpkg-status.txt
    dependency-lock.json
    dependency-licenses/
    build.log
    ctest.xml
    artifacts.json
    dynamic-dependencies/
  datasets/<dataset-id>/
    dataset-manifest.json
    input/
    oracle/
  runs/<run-id>/
    run.json
    stdout.txt
    stderr.txt
    process-samples.jsonl
    solver-history.jsonl
    metrics.json
    outputs/
    checksums.sha256
  release/<release-id>/
    install-tests/
    licenses/
    sbom/
    checksums.sha256
    provenance/
```

All JSON records carry a schema version. Paths in manifests are bundle-relative
and use forward slashes. SHA-256 covers every retained byte; the top-level
checksum file covers all child manifests and artifacts.

### `identity.json`

Required fields:

- Polatory, resolved ScalFMM, vcpkg, overlay-port, and baseline-generator
  commit IDs;
- dirty-state booleans plus a patch/archive hash when dirty;
- compiler, linker, standard library, CMake, Ninja, vcpkg executable, R,
  gstat, and measurement-wrapper versions;
- target triple, architecture, build type, compiler flags, linker flags,
  feature switches, and dependency linkage modes;
- hashes of the configure arguments, cache, compile database, dependency
  lock/status, build log, and produced files;
- complete direct and transitive native dependency inventory; and
- source and binary license inventory.

### `host.json`

Required fields:

- OS name/version/kernel or Windows build and runner-image version;
- CPU model, stepping/microcode, ISA, physical/logical cores, NUMA topology,
  affinity, frequency governor/power mode, and virtualization;
- physical RAM and configured swap/page file;
- storage model, filesystem, mount options, total/free space, and the separate
  scratch root;
- thermal/background-load preflight; and
- clock source and wrapper version.

### `dataset-manifest.json`

Required fields:

- stable scenario ID and schema version;
- generator source SHA and literal argument array;
- every explicit seed and all distribution/model parameters;
- generator/runtime/library versions;
- row count, dimensionality, scalar type, byte order, units, and coordinate
  convention;
- provenance and SHA-256 for every input and oracle file; and
- expected operator path, including direct/FMM/crossover classification.

Generated files are the authority. Seeds document provenance but never replace
content hashes.

### `run.json` and `metrics.json`

`run.json` records the build and dataset IDs, literal argument array, working
directory, allow-listed environment, affinity, thread settings, cache state,
warm-up/repetition index, randomized execution-order seed, timeout, start time,
and expected resource limits. It also records exit code/signal, terminal
status, output hashes, and whether instrumentation changed the binary.

`metrics.json` contains monotonic wall time, user and system CPU time, raw and
normalized peak-memory fields, I/O bytes and operations, maximum observed
thread count, scratch high-water mark, output bytes, and sampling interval.
Raw platform-native fields must be preserved alongside normalized bytes.

## Resource and thread measurement

### Common run policy

For a Polatory/RapidRBF pair:

1. use identical immutable inputs, designated physical host, CPU affinity,
   thread budget, scratch volume, cache policy, and wrapper version;
2. run a small preflight, then a declared warm-up only when the scenario
   specifies warm-cache behavior;
3. randomize paired run order with a recorded seed;
4. collect enough repetitions to estimate noise before setting a regression
   limit;
5. retain every run, including timeouts and out-of-memory failures;
6. compare distributions and confidence intervals, not only best times; and
7. never combine measurements from different hosts into a performance ratio.

Build CI may run on hosted machines, but release-blocking performance must use
pinned, dedicated self-hosted runners. GitHub says hosted runner images are
[updated weekly](https://github.com/actions/runner-images), and the exact image
is visible in the job's `Set up job` log. Hardware and image drift make hosted
runners unsuitable as the authoritative performance host. GitHub supports
[self-hosted x64 runners on Windows, Linux, and macOS](https://docs.github.com/en/actions/reference/runners/self-hosted-runners).

### Thread controls

Set these before process creation and record both set and absent values:

```text
OMP_NUM_THREADS
OMP_DYNAMIC
OMP_PROC_BIND
OMP_PLACES
OMP_THREAD_LIMIT
MKL_NUM_THREADS
MKL_DYNAMIC
OPENBLAS_NUM_THREADS
BLIS_NUM_THREADS
VECLIB_MAXIMUM_THREADS
RAYON_NUM_THREADS
```

The canonical single-thread profile uses `OMP_NUM_THREADS=1` and
`OMP_DYNAMIC=FALSE`; the canonical throughput profile uses an explicitly
chosen physical-core count and fixed affinity. The OpenMP specification lists
the runtime variables and warns that changing them after program start has no
effect ([OpenMP environment variables](https://www.openmp.org/spec-html/5.0/openmpch6.html),
[`OMP_NUM_THREADS`](https://www.openmp.org/spec-html/5.0/openmpse50.html)).

Polatory's Ceres-based variogram fitting independently asks for
`hardware_concurrency()`, so OpenMP settings alone do not establish a global
thread budget. The baseline must sample the process's actual maximum live
thread count and treat an exceeded budget as a failed run. Examples are visible
in the
[one-dimensional fitting implementation](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting_1d.hpp#L53-L59).

### Windows

A native wrapper records process creation-to-exit monotonic wall time, process
times and I/O counters, live/maximum thread count, and
`PROCESS_MEMORY_COUNTERS_EX2`. Preserve at least `PeakWorkingSetSize`,
`PeakPagefileUsage`, and `PrivateUsage`, which are byte counts documented by
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex2).
If a benchmark launches children, place the tree in a Job Object and separately
record job-wide values; do not label `PeakJobMemoryUsed` as RSS because it has
different semantics
([Job Object limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)).

Set the RAS cache and all temporary variables to a dedicated scratch volume.
Measure free-space high-water while the process is alive and enumerate open
handles where possible so delete-on-close files are counted.

### Linux

Run each repetition in a fresh cgroup v2. Retain
`memory.current`, `memory.peak`, `memory.swap.peak`, `cpu.stat`, `io.stat`,
termination events, and the wrapper's monotonic wall time. Cgroup measurements
cover descendants and avoid the ambiguity of a single `/usr/bin/time` process.
The kernel defines memory values in bytes, CPU time in microseconds, and I/O
bytes/operations in the
[cgroup v2 interface](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html).

Place the scratch directory on a dedicated mount or quota and sample used
bytes during execution. An after-exit directory walk cannot see unlinked-open
RAS files.

### macOS

A native wrapper records monotonic wall time and `getrusage` values, retaining
the raw unit and platform. Apple's interface reports `ru_maxrss` in KiB and
also exposes user/system time and block-operation counts
([`getrusage(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/getrusage.2.html)).
Convert KiB to bytes only in the normalized field. Use an isolated scratch
volume or an active open-file/free-space monitor to capture unlinked temporary
files.

## Workload ladder and safety gate

The baseline suite has five layers:

| Layer | Purpose | Typical scale |
| --- | --- | --- |
| Analytic/direct | Exact formulas, derivatives, anisotropy, serialization, errors | 1–1,000 observations |
| Crossover | Direct/FMM dispatch and approximation equivalence | Around the two dispatch boundaries |
| Differential | Full compatibility matrix and CLI/API behavior | 1,000–10,000 |
| Solver stress | FGMRES/RAS convergence, difficult geometry, iteration growth | 10,000–100,000 |
| Scale | Fit/evaluate/runtime/RSS/scratch/thread behavior | 1k, 10k, 100k, then 1M |

The old 16 train-by-predict combinations may remain in the scale layer, but
the release-blocking million case must also exercise the agreed full fit and
evaluation journey, not merely one convenient prediction shape.

Before advancing from size `N` to the next size, the runner produces an
estimate from at least two completed lower rungs:

```text
estimated_wall
estimated_peak_memory
estimated_scratch_high_water
estimated_output_bytes
configured_timeout
configured_memory_limit
configured_scratch_limit
recovery_and_cleanup_check
```

Advancement is rejected if the estimate does not fit the designated host with
the project's safety margin, if the previous rung failed, if scratch cleanup
was not verified, or if resource instrumentation is incomplete. A one-million
run is separately scheduled, never launched as an exploratory command in an
interactive task.

## Numerical acceptance and performance acceptance

The protocol intentionally separates evidence collection from threshold
selection.

### Numerical gate

A scenario passes only when:

- output shape, ordering, metadata, exit status, and diagnostic behavior match
  the compatibility contract;
- every declared absolute, relative, RMS, derivative, symmetry, and residual
  metric is below its pre-registered scenario threshold;
- no unexpected non-finite result occurs;
- FGMRES/RAS terminates in the allowed state and iteration envelope; and
- the independent oracle wins over a conflicting Polatory value when a
  confirmed reference defect is recorded.

Threshold calibration uses repeated results across all tier-one targets and
analytic/high-precision cases. It must distinguish deterministic
implementation spread from approximation or conditioning error.

### Performance gate

Performance comparisons are paired on the same host and input. Report median,
dispersion, and confidence interval for wall time; report peak-memory and
scratch ratios from every repetition; and report convergence iterations
separately from kernel throughput. A release passes only when no metric exceeds
its pre-registered material-regression envelope and the million-scale hard
gate completes within its absolute RAM, scratch, time, and convergence caps.

Exact regression percentages, repetition counts, confidence method, and
absolute million-scale caps remain decisions to calibrate from the first
canonical series. Choosing them without clean baseline measurements would
create false precision.

## Tier-one release baseline

RapidRBF's required release set is:

- one stable Rust library release;
- standalone CLI archives for Windows x86-64, Linux x86-64 glibc, macOS arm64,
  and macOS x86-64;
- CPython wheels for those four platform/architecture combinations; and
- a source distribution, license inventory, SBOM, checksums, and provenance.

### Rust library

`cargo package` is the required preflight and `cargo publish` is the release
action. Cargo verifies the packaged source by extracting and compiling it, and
crates.io limits a `.crate` file to 10 MB
([Cargo publishing](https://doc.rust-lang.org/cargo/reference/publishing.html)).
Native libraries must be isolated behind a `-sys`-style boundary with an
explicit `links` contract; build scripts must distinguish host and target
through Cargo's target configuration variables
([Cargo build scripts](https://doc.rust-lang.org/cargo/reference/build-scripts.html)).
The core crate may not require an undeclared local C++/Fortran/MKL installation
to build its documented default configuration.

Rust currently classifies `aarch64-apple-darwin`, Windows x86-64 MSVC, and
Linux x86-64 GNU as Tier 1, but `x86_64-apple-darwin` as Tier 2
([Rust platform support](https://doc.rust-lang.org/rustc/platform-support.html)).
RapidRBF's product-level macOS x86-64 commitment therefore requires its own
build and test gate; upstream Rust Tier 1 cannot be assumed. Rust documents
minimum supported macOS versions of 11 for arm64 and 10.12 for x86-64, with
`MACOSX_DEPLOYMENT_TARGET` controlling the deployment floor
([Apple targets](https://doc.rust-lang.org/rustc/platform-support/apple-darwin.html)).

### CLI archives

Each archive is tested on a clean minimum-version host without repository,
compiler, package manager, vcpkg, MKL, or developer environment variables.
The test covers `--help`, a required `--version`/build-identity command, a
small fit/evaluate workflow, malformed input, dynamic dependency inspection,
temporary-file cleanup, and license/SBOM discovery.

The captured Polatory CLI returns exit code 0 for `--help`, but `--version`
returns exit code 1 with `unknown command`. Its command registration contains
no version option
([CLI entry point](https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/main.cpp#L11-L78)).
RapidRBF needs a version/build-identity command so released evidence can be
bound to a running binary.

On macOS, externally distributed native binaries require a declared signing
and notarization policy. Apple requires manual signing for external build
systems and requires embedded executable code to be signed
([distribution-signed code](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/));
the notarization workflow uses Developer ID, hardened runtime, secure
timestamps, and `notarytool`
([notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)).
Whether unsigned development artifacts are permitted is separate from the
official-release gate.

### CPython wheels and source distribution

Wheel tags encode Python, ABI, and platform. Linux `manylinux_x_y` tags promise
glibc `x.y` or newer, while macOS tags encode deployment version and
architecture, including `universal2`
([platform compatibility tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)).
A compiled extension normally produces a Python-minor × OS × architecture
matrix unless RapidRBF deliberately adopts the stable ABI; Linux wheels must
build against a sufficiently old glibc and macOS wheels must set an explicit
deployment target
([binary extensions](https://packaging.python.org/en/latest/guides/packaging-binary-extensions/)).

Every wheel is repaired/audited with the platform-native tool, installed into
a clean virtual environment, imported, run through a numerical smoke test, and
checked for forbidden external libraries. Publish an sdist as well as wheels.
The wheel's `.dist-info` includes `METADATA`, `WHEEL`, and hashed `RECORD`;
license and SBOM directories follow the standardized installed-project layout
([wheel specification](https://packaging.python.org/en/latest/specifications/binary-distribution-format/),
[installed project metadata](https://packaging.python.org/en/latest/specifications/recording-installed-packages/)).

PyPI's default per-file limit is 100 MB
([PyPI storage limits](https://docs.pypi.org/project-management/storage-limits/)).
The current Windows Polatory CLI closure is about 395.6 MB before archive or
wheel compression, while crates.io allows only 10 MB. This does not prove that
a repaired RapidRBF wheel will exceed 100 MB, but it makes an early packaging
prototype and measured native dependency closure mandatory before choosing an
MKL/FFI distribution design.

### Publication and retained evidence

Use exact runner labels, never `*-latest`, for build jobs. GitHub-hosted runners
are suitable for clean build/install smoke tests; dedicated self-hosted
machines supply performance evidence. Save the exact hosted image version from
the job log
([GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)).

Publish all artifacts to a draft GitHub Release, verify checksums/install tests,
then make the release immutable. GitHub release assets are limited to 2 GiB
each and a release may have up to 1,000 assets
([About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)).
Immutable releases lock the tag and assets and generate a release attestation
([immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)).
Upload the source distribution as an explicit asset: GitHub notes that
automatically generated source archives cannot be verified with
`gh release verify`
([release verification](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity)).

Attach artifact attestations for binaries, wheels, source archive, SBOMs, and
checksums. Attestations bind artifacts to the repository, workflow, event, and
commit and may carry an SBOM
([artifact attestations](https://docs.github.com/en/enterprise-cloud@latest/actions/concepts/security/artifact-attestations)).
Do not rely on workflow artifacts as permanent baseline storage: their default
retention is 90 days
([artifact retention](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts?tool=cli)).

## Required gates before RapidRBF v1.0.0

The migration specification can now require these concrete gates:

1. **Identity gate:** every Polatory comparison names the full Polatory,
   ScalFMM, dependency, generator, dataset, build, and wrapper identities.
2. **Dataset gate:** all inputs and reference outputs are immutable and
   content-addressed; a seed without a frozen file is insufficient.
3. **Numerical gate:** the declared compatibility matrix passes
   scenario-specific thresholds with explicit oracle provenance.
4. **Convergence gate:** solver history, sampled/full markers, independent final
   residuals, iteration outcome, and RAS parameters are retained.
5. **Resource gate:** wall time, CPU, peak memory, maximum threads, I/O, and
   scratch high-water are measured with platform-native semantics.
6. **Pairing gate:** performance comparisons use the same designated host,
   inputs, affinity, thread budget, cache policy, and wrapper.
7. **Scale gate:** progression is estimated and bounded; the one-million case
   is a separately scheduled hard gate.
8. **Packaging gate:** Rust crate, CLI archives, wheels, and sdist are tested on
   clean tier-one hosts and contain no undeclared runtime dependency.
9. **Supply-chain gate:** licenses, SBOMs, checksums, provenance, explicit
   source asset, and immutable release evidence are published and retained.

## Remaining decisions and follow-up work

This research establishes the evidence contract but does not invent acceptance
numbers or product policy. The following remain specification decisions or
implementation tickets:

- calibrate per-scenario numerical tolerances, convergence envelopes,
  performance regression limits, repetition counts, and statistical method;
- choose absolute time, RAM, scratch, and iteration caps for the
  release-blocking million-scale workload;
- select the dedicated performance machines and implement one versioned
  cross-platform measurement wrapper;
- produce and approve the frozen dataset corpus, including a deterministic
  replacement or locked environment for the unseeded R/gstat values;
- decide FGMRES restart/storage policy and the RAS scratch strategy for
  million-scale memory bounds;
- prototype crate, wheel, and CLI native dependency closure before committing
  to MKL, ScalFMM FFI, or another large native backend;
- choose supported CPython minors or `abi3`, the manylinux/glibc floor, macOS
  deployment floors, Windows runtime strategy, and macOS x86-64 maintenance
  policy;
- decide release signing, notarization, code-signing identity custody, and
  whether unsigned development artifacts are permitted; and
- define retention and access control for large/private baseline datasets when
  GitHub Releases are not the appropriate store.

These are visible gaps, not reasons to weaken the baseline. They should be
resolved before thresholds or a self-contained distribution claim become
normative.
