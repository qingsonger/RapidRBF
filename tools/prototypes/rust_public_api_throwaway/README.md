# PROTOTYPE — RapidRBF Rust public interface

This is throwaway code for one question:

> Can RapidRBF expose discoverable, Rust-native domain workflows while keeping
> backend routing, solver identities, unsafe/FFI, third-party types, runtime
> plans, and caches behind private seams?

It is not a numerical implementation and must not ship as the production
`rapidrbf` crate. The compiled contract returns deterministic mock values so the
interface and state transitions can be driven by hand.

Run it from the repository root:

```powershell
cargo run --manifest-path tools/prototypes/rust_public_api_throwaway/Cargo.toml
```

The terminal explorer compares four interface shapes and then exercises the
recommended hybrid. It redraws the complete state after every action, including
the last call shape, immutable interpolant identity, result/failure category,
and normalized execution report.

## Designs compared

1. **Minimal envelope** — `Engine::run(Operation)` centralizes every execution
   rule, but makes a large operation algebra part of the public interface.
2. **Extensible plan** — `Engine::plan(...).execute()` makes additive workflows
   and preflight visible, but risks stabilizing internal orchestration.
3. **Study facade** — `Study<D>.fit()/variogram()/geometry()` is friendly for
   value-only samples, but cannot cleanly own all RapidRBF data lifetimes.
4. **Recommended hybrid** — const-generic domain values and discoverable
   workflow builders call a private sealed execution engine through
   `.run(&Context, CallControl)`.

The hybrid keeps `Model<D>`, `Interpolant<D>`, observations, constraints,
variograms, geometry results, artifacts, failures, and reports public. Concrete
solver/backend route identities remain private. The only deliberate external
adapter seam is `CertifiedField`, because both an interpolant field and a
caller-provided analytic field must supply values plus sound cell enclosures.

## Proposed crate/module sketch

```text
rapidrbf                    published stable interface
├── model                   kernels, composition, anisotropy, polynomial choice
├── interpolation           fit, incremental/inequality fit, prepare, evaluate
├── kriging                 transforms, variograms, fitting, cross-validation
├── geometry                point cloud, SDF, certified fields, surfaces, meshes
├── artifact                portable logical state and declared legacy import
├── execution               context capacity, call grants, cancellation, reports
└── error                   stable categories and structured locations

private workspace modules   replaceable implementation
├── core                    canonicalization, planning, certification, precedence
├── matrix_kernel           private four-action adapter seam
├── solver                  dense/sparse/iterative/hierarchical route adapters
├── numerics                owned optimization, algebra, exact escalation
├── geometry_impl           predicates, topology, refinement, snapping
└── format_impl             bounded codecs and atomic replacement
```

Python and CLI are adapters over the published interface. They dispatch dynamic
dimensions to the Rust `D = 1 | 2 | 3` types privately.

## What this prototype intentionally does not decide

- The portable byte schema, integrity envelope, or codec (owned by the portable
  artifact schema ticket).
- Exact crate names or workspace splitting (owned by the architecture ticket).
- Python/CLI names and defaults.
- Production algorithms, thresholds, qualification evidence, or release
  packaging.
