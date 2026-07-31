# Use Rust-owned dependency admission boundaries

RapidRBF v1 owns every public, semantic, certification, resource, and failure boundary and uses pure-Rust dependencies by default. A native dependency is admissible only as a private, replaceable, pinned, self-contained exception when no Rust route can pass the unchanged capability and release gates; strong-copyleft runtime dependencies and runtime-downloaded components are excluded from official artifacts. This accepts more RapidRBF-owned orchestration and a small amount of purpose-built numerical and geometry code in exchange for portable self-contained releases, stable semantics, auditable resource control, and backend replaceability.

## Production responsibility matrix

| Responsibility | Boundary |
| --- | --- |
| Dense algebra and BLAS | Faer is the private default substrate. RapidRBF owns matrices at public seams, solve/refinement/certification semantics, and resource control. v1 has no native BLAS dependency. |
| FMM and SIMD | RapidRBF maintains a private fork of the Ferreus BBFMM layer for the accepted four-action adaptation and target-Hessian work, with exact upstream source and patch identity. Pulp sits behind a private SIMD facade with a scalar authority path. Neither backend nor ISA selection is public; the large-smooth route cannot enter `Auto` before every qualification gate passes. |
| Nonlinear optimization | RapidRBF owns a narrow deterministic bounded least-squares module and uses Faer for its small dense subproblems. Ceres and Argmin are development comparators only. |
| Nearest-neighbor search | Kiddo is a private candidate-superset index. RapidRBF recomputes distances and owns inclusive boundaries, stable original-index ties, duplicate handling, and deterministic scan fallback. |
| Geometry predicates and mesh operations | RapidRBF owns topology, orientation, refinement, snapping, intersection, validity, and spatial broad-phase algorithms. The `robust` crate supplies adaptive predicates and `num-bigint` supplies bounded exact-dyadic fallback; neither owns semantic surface states. |
| Parallel runtime | Rayon is the sole production CPU task runtime, through one RapidRBF-owned pool per execution context. Nested libraries cannot create competing pools; cancellation, deadlines, deterministic reductions, and task cleanup remain RapidRBF responsibilities. |
| CLI | Clap is confined to the CLI adapter with a minimal feature set. RapidRBF owns commands, defaults, table workflows, and stable exit categories. |
| Parsing | The `csv` crate supplies streaming record framing; standard-library numeric parsing plus RapidRBF's frozen lexical rules own value semantics and indexed failures. |
| Collections | Standard-library collections are sufficient. Hash iteration order is never observable, and normalized RapidRBF keys own floating identity. |
| Special functions | Statrs is used through a minimal-feature private wrapper for error-function and inverse-normal primitives; RapidRBF owns domains, tails, transformations, and high-precision validation. |
| Compression | v1 has no runtime compression dependency. Release archives are produced by packaging tools, and the portable schema must justify any future codec independently. |
| Temporary storage | Tempfile supplies secure creation. RapidRBF owns named auditable scratch sessions, quotas, immutable factor records, positional I/O, occupancy/write evidence, atomic durable replacement, and cleanup. |

The Ferreus fork uses the workspace-selected Faer, Rayon, and Pulp versions so it cannot introduce duplicate dense or thread runtimes. General mesh runtimes, native BLAS, ScalFMM3, FFTW, Ceres, Argmin, RStar, fast-float, and general compression libraries do not enter the v1 production graph under this decision.

## Admission and upgrade rules

Production dependencies use permissive licenses by default; reviewed weak copyleft requires a written exception, while strong copyleft is forbidden in official runtime closure. Official builds use an audited lockfile, fixed toolchain, source checksums, and exact fork patch identity. Direct and transitive license, advisory, provenance, default-feature, MSRV, native-link, and `unsafe` inventories are reviewed; unsafe code is isolated behind documented invariants and targeted dynamic checks. Every target emits an SBOM and notice bundle, and all required runtime content counts toward the artifact-size gates without debug-package, deferred-download, or system-dependency exclusions. Upgrades replay the affected semantic, resource, and platform gates, and an abandoned or unsafe dependency must be forked, replaced, or removed without weakening RapidRBF's contracts.

The complete rationale and decision dialogue are authoritative in [Choose the dependency and licensing boundary for each Polatory responsibility](https://github.com/qingsonger/RapidRBF/issues/18).
