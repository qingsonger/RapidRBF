# RapidRBF

RapidRBF is a Rust-native framework for radial basis function interpolation whose migration decisions are grounded in Polatory's observable behavior.

## Language

**Behavior-compatible successor**:
A Rust-native successor that preserves the selected observable capabilities, numerical semantics, and acceptance results of Polatory without promising C++ source compatibility, ABI compatibility, or the same internal architecture.
_Avoid_: Port, drop-in replacement, line-by-line rewrite

**Compatibility surface**:
The complete set of Polatory capabilities and documented semantic outcomes visible to library, CLI, and Python users, re-expressed through idiomatic Rust interfaces where appropriate. Incidental text, ordering, algorithm trajectories, internal helpers, and implementation details are outside this surface unless explicitly named.
_Avoid_: Public headers, internal API, source compatibility

**Intentional compatibility change**:
A documented RapidRBF behavior that deliberately differs from Polatory because the legacy behavior is mathematically undefined, structurally invalid, unsafe, or a proven defect. Where applicable, RapidRBF provides a stable error category and migration guidance rather than preserving the legacy outcome.
_Avoid_: Behavior drift, accidental incompatibility, silent fix

**Self-contained distribution**:
An official RapidRBF package that requires no separately installed compiler toolchain or native numerical dependency from its user, even when its internals include a native backend.
_Avoid_: Source-only release, system dependency

**Tier-one platform**:
A supported operating-system and architecture pair whose library, CLI, and Python artifacts must pass the v1.0.0 release gates. The tier-one set is Windows x86_64, Linux x86_64 with glibc, macOS arm64, and macOS x86_64.
_Avoid_: Best-effort platform, build-only target

**Million-scale workload**:
A release-blocking interpolation workload with at least one million input points whose fit, evaluation, convergence, peak memory, and runtime are assessed against the Polatory baseline on identical hardware and inputs.
_Avoid_: Scalability demo, aspirational benchmark

**Numerical compatibility**:
Agreement with Polatory's mathematical conventions and observable numerical outcomes under explicitly defined error, residual, and convergence tolerances. It does not require bitwise-identical results, identical coefficients, or identical solver and optimizer trajectories.
_Avoid_: Bitwise compatibility, visually similar output

**Legacy artifact**:
A model or fitted interpolant serialized by Polatory's unversioned native binary format and accepted by RapidRBF only through a one-way migration path.
_Avoid_: RapidRBF format, portable model

**Portable artifact**:
A versioned RapidRBF model or fitted interpolant representation with an explicit cross-platform compatibility contract.
_Avoid_: Native memory dump, legacy artifact

**Reference hierarchy**:
The order used to judge numerical discrepancies: explicit mathematical definitions and high-precision direct references first, Polatory's observable behavior second, and a RapidRBF candidate implementation third. Proven Polatory defects become documented intentional differences rather than compatibility requirements.
_Avoid_: Polatory is always correct, implementation-defined truth

**Polatory baseline**:
The frozen Polatory source revision `4a30beb`, together with its captured build configuration, dependency versions, datasets, and executable artifacts, used for RapidRBF v1.0.0 differential and performance comparisons.
_Avoid_: Latest Polatory, moving upstream target

**Reproducibility controls**:
Stable Rust, Python, and CLI inputs and metadata that expose build identity, random seeds, configured and effective thread counts, and relevant runtime configuration without promising identical random sequences across implementations.
_Avoid_: Bitwise deterministic execution, hidden execution defaults

**Performance parity**:
Absence of a material regression from the Polatory baseline in runtime, peak memory, or iterative convergence for the accepted benchmark suite, using empirically calibrated thresholds and a separate hard gate for million-scale workloads.
_Avoid_: Runs successfully, asymptotically similar

**Python migration compatibility**:
Preservation of Polatory Python workflows, array shapes, and numerical semantics through the `rapidrbf` package, with a mechanical migration path but no promise that existing source runs unchanged or that RapidRBF replaces the `polatory` package name.
_Avoid_: Drop-in Python replacement, unrelated Python API

**CLI migration compatibility**:
Preservation of Polatory command names, option meanings, exit behavior, and tabular input/output conventions under the new `rapidrbf` executable, except for explicitly justified incompatibilities.
_Avoid_: `polatory` executable replacement, unrelated CLI

**Official release set**:
The v1.0.0 artifacts whose successful publication is release-blocking: the stable Rust library, tier-one prebuilt CLI binaries, tier-one CPython wheels, and a source distribution with license inventory, SBOM, and checksums.
_Avoid_: Source-only release, package-manager availability
