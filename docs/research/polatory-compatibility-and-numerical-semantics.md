# Polatory compatibility surface and numerical semantics

**Status:** decision-ready research for RapidRBF v1.0.0
**Frozen reference:** Polatory [`4a30beb08053fb339ce899e255be4b6d3f74aa0c`][polatory-commit]
**Research issue:** [RapidRBF #2](https://github.com/qingsonger/RapidRBF/issues/2)
**Audit date:** 2026-07-26

## Evidence convention

This report deliberately distinguishes four kinds of statements:

- **[F] Fact** — directly observed in the frozen source, build, executable, or test output. Every source-derived fact has a frozen permalink; executable observations include the command and environment in [Baseline execution](#baseline-execution).
- **[I] Inference** — a consequence of facts, but not itself an upstream promise.
- **[S] Suspicion** — a plausible defect or undefined edge that was found by inspection but not proven by a focused reproducer.
- **[R] Recommendation** — a proposed RapidRBF v1.0.0 contract or migration decision.

An **[R, conditional …]** item is not an adopted compatibility exception; its stated reproducer/adjudication gate must pass first.

“Compatible” below means behavior-compatible at selected user-visible library, CLI, Python, and artifact boundaries. It does not mean C++ source compatibility, ABI compatibility, identical coefficients, identical iteration histories, or identical FMM/RAS internals.

## Executive answer

**[F]** Polatory promises scattered-data RBF interpolation in one, two, and three dimensions; gradient and inequality constraints; large-data fitting; kriging/variograms; point-cloud normal and SDF preparation; 2.5D/3D surface reconstruction; and CLI and Python entry points. Its public umbrella exports 16 RBF families, `Model`, `Interpolant`, `DirectEvaluator`, geometry, point-cloud, and isosurface types; kriging has a separate umbrella. [README][readme] [C++ umbrella][umbrella] [kriging umbrella][kriging-umbrella]

**[R]** RapidRBF v1.0.0 should preserve the mathematically meaningful surface: dimensions, RBF names and parameter order, polynomial rules and basis order, anisotropy chain rule, Hermite signs and vector layout, fit/evaluation accuracy semantics, workflow input/output shapes, CLI command meanings/defaults, Python migration coverage, and one-way import of frozen artifacts.

**[R]** RapidRBF should make explicit migration decisions for legacy behavior that is demonstrably unsafe rather than copying it silently: unchecked non-finite/negative kernel parameters, zero ranges, undefined derivatives at coincident points, and malformed native-binary allocation sizes. Suspected solver, active-set, geometry, and Python-binding defects must first be reproduced and adjudicated; only proven/adopted changes become intentional incompatibilities.

**[I]** ScalFMM3, Eigen, MKL, Ceres, and FLANN are implementation dependencies rather than compatibility boundaries. A Rust-native implementation, a private FFI backend, or another algorithm is compatible if it satisfies the observable numerical, convergence, performance, memory, and cross-platform gates in this report. The strongest reason to retain a ScalFMM fallback is delivery risk, not an observable requirement.

## RapidRBF project constraints consumed

**[F, project decision]** RapidRBF is a greenfield Rust-native successor, not a C++ port. It targets Windows x86_64, Linux x86_64 glibc, macOS arm64, and macOS x86_64; million-scale fit and evaluation are release-blocking; official output includes the Rust crate, CLI, CPython wheels, source archive, license inventory, SBOM, and checksums. The CLI and package names become `rapidrbf`; frozen model/interpolant artifacts are imported one way into a new portable format. [Wayfinder map][rapidrbf-map]

**[F, project decision]** The project explicitly ranks mathematical/high-precision references above Polatory when a defect is proven, permits native backends only behind replaceable Rust boundaries, excludes strong-copyleft runtime dependencies from official artifacts, and does not require cross-platform bitwise floating-point identity. [Wayfinder map][rapidrbf-map]

## Compatibility classification for `/to-spec`

**[R]** Use the following scope classification as the v1 specification boundary:

| Surface | v1 classification | Required compatibility |
| --- | --- | --- |
| Mathematical RBF values, gradients, Hessians, anisotropy | **Required** | Formula, orientation, branch, parameter, and chain-rule compatibility at defined inputs |
| Model composition, CPD, polynomial degree/basis | **Required** | Exact structural compatibility |
| Value and full-gradient Hermite interpolation | **Required** | Exact block signs/layout; tolerance-based predictions/residuals |
| Ordinary, incremental, and value-inequality fitting | **Required** | Same modes/constraint meaning; full residual plus scenario iteration/matvec envelope, without exact iteration identity |
| Fast evaluation and million-scale solve | **Required release gate** | Accuracy, convergence, wall-time, peak-memory/scratch, cache-I/O, and thread-scaling gates |
| Variogram, model fitting, cross-validation, normal score | **Required** | Same mathematical outputs and tabular shapes; optimizer trajectory is not contractual |
| Point-cloud/SDF and 2.5D/3D isosurface workflows | **Required** | Same workflow semantics; compare geometry, not vertex order |
| CLI | **Required migration surface** | Command names, option meanings/defaults/conflicts, table shapes, exit status |
| Python | **Required migration surface** | `rapidrbf` coverage with mechanical migration; no promise of import-name drop-in compatibility |
| Frozen Polatory model/interpolant binaries | **Import only** | One-way, dimension-explicit legacy reader with fixtures and corruption limits |
| C++ headers, templates, ABI, Eigen objects | **Excluded** | No compatibility requirement |
| Exact ScalFMM tree/order, RAS partition, GMRES basis | **Excluded** | Treat as backend details |
| Exact progress text, OpenMP reduction order, coefficients | **Excluded** | Test outcomes within declared tolerances instead |

## Baseline execution

### Provenance

The read-only provenance probes were:

```powershell
git -C D:\CODE\polatory rev-parse HEAD
git -C D:\CODE\polatory status --short
git -C D:\CODE\polatory\build\scalfmm\src\scalfmm rev-parse HEAD
D:\CODE\polatory\vcpkg\vcpkg.exe version
git -C D:\CODE\polatory\vcpkg rev-parse HEAD
Select-String -Path D:\CODE\polatory\build\CMakeCache.txt `
  -Pattern 'BUILD_|CMAKE_BUILD_TYPE|CMAKE_CXX_COMPILER|VCPKG_TARGET_TRIPLET|MKL|OpenMP'
```

**[F, local]** `git -C D:\CODE\polatory rev-parse HEAD` returned `4a30beb08053fb339ce899e255be4b6d3f74aa0c`; `git status --short` was empty. The same object is available at the frozen upstream [commit][polatory-commit].

**[F, local]** The captured build is Windows x86_64, Release, Ninja 1.13.1, CMake 4.0.3, clang-cl 19.1.5, vcpkg triplet `x64-windows`, MKL sequential, and OpenMP. Tests, CLI, examples, and benchmarks were enabled; Python bindings were disabled. These values were read from `build/CMakeCache.txt`, tool `--version` output, and the vcpkg installed-status database.

**[F, local]** The build contained Eigen 5.0.1, Ceres 2.2.0 port 6, fast-float 8.2.4, FLANN snapshot 2022-10-28, GoogleTest 1.17.0, libigl 2.6.0, Intel MKL 2023.0.0, and Boost 1.90.0. The dependency roles also appear in the frozen [manifest][vcpkg-manifest] and build files.

**[F, local]** Polatory's build fetches `https://github.com/polatory/ScalFMM3.git` at the moving tag/branch `polatory`; the captured checkout was detached at `0be3d74f17adb28adec7004f712f693ac8ee9901`. The source does not pin that object. [ScalFMM external project][src-cmake]

**[F, local]** The vcpkg gitlink is `4b77da7fed37817f124936239197833469f1b9a8`, but the executable identifies itself as `2026-03-04-4b3e4c276b5b87a649e66341e11553e8c577459c`; `vcpkg-configuration.json` contains no `builtin-baseline`. The original configure argument array was not retained. [vcpkg configuration][vcpkg-config] [baseline audit][baseline-research]

**[I]** Rebuilding frozen Polatory does not reproduce the same FMM implementation unless the captured ScalFMM object is pinned separately. RapidRBF differential baselines must record both object IDs.

**[I]** The inspected Windows build is an evidence starting point, not a replayable or authoritative performance baseline. Performance gates must use the immutable evidence bundle and designated same-host paired baseline defined by Issue #4. [baseline audit][baseline-research]

### Executable observations

The executable probes were:

```powershell
D:\CODE\polatory\build\test\Unittest.exe
D:\CODE\polatory\build\cli\polatory.exe --help
D:\CODE\polatory\build\cli\polatory.exe
D:\CODE\polatory\build\cli\polatory.exe unknown-command
Get-FileHash D:\CODE\polatory\build\test\Unittest.exe -Algorithm SHA256
# Each registered command was also invoked as: polatory.exe COMMAND --help
```

**[F, local diagnostic]** The complete built test executable (`SHA-256 600736AA60CAEE4915D8CD3D8E2A9D5C8A53744DBA800DA6FE2D98EEEAEF1E52`) reported `89 tests from 37 test suites`, all passed, in `590493 ms`. No explicit OMP/MKL thread environment, content-addressed stdout/stderr, or process-resource trace was retained, so this is diagnostic compatibility evidence—not replayable numerical or performance evidence. [baseline audit][baseline-research]

**[F, local]** `polatory --help` succeeded. Help for all 14 registered commands succeeded. Running with no arguments returned exit code 1; an unknown command returned exit code 1 and wrote `error: unknown command` to stderr. This agrees with the frozen dispatcher. [commands][cli-commands] [main][cli-main]

**[F, local]** No Python extension (`.pyd`) was produced because `BUILD_PYTHON_BINDINGS=OFF`; Python behavior in this report is therefore a source audit, not a successful runtime baseline.

## Public compatibility surface

### C++ library

**[F]** The umbrella includes geometry, `Interpolant`, `DirectEvaluator`, isosurface, `Model`, point-cloud tools, tables/types, and all 16 RBFs. Kriging is exported by a second umbrella. [C++ umbrella][umbrella] [kriging umbrella][kriging-umbrella]

**[F]** The implementation is a template-heavy C++ static/source-build library with Eigen types at the public boundary; the frozen build files do not define a stable installed C ABI or exported package target. [root build][root-cmake] [library build][src-cmake]

**[R]** Preserve capabilities, not the C++ surface. Rust APIs should use owned/borrowed slices and explicit row counts, with checked conversions at Python/CLI/FFI edges.

### CLI

**[F]** The dispatcher registers 14 commands: `create-model`, `cross-validate`, `estimate-normals`, `evaluate`, `extract-model`, `fit`, `fit-model-to-variogram`, `isosurface`, `normals-to-sdf`, `show-model`, `show-variogram`, `surface-25d`, `unique`, and `variogram`. [command registry][cli-commands]

**[F, source and executable]** The frozen command contracts below agree between each command source and the successful `polatory COMMAND --help` probes recorded in [Baseline execution](#baseline-execution).

| Command | Input and material defaults | Output/observable shape | Evidence |
| --- | --- | --- | --- |
| `create-model` | dimension; one multi-token RBF grammar containing one or more RBFs; nugget `0`; degree `AUTO` | native model artifact | [source][cli-create-model] |
| `cross-validate` | rows `coords,value,set_id,…`; fit tolerance; max iterations `100`; accuracy `ANY`; model file or inline model | original rows plus `prediction` | [source][cli-cross-validate] |
| `estimate-normals` | `x,y,z`; default multiscale `k = 10,30,100,300`; plane-factor threshold `1.8`; default closed orientation `k=100`; optional radius/point/direction | `x,y,z,nx,ny,nz` | [source][cli-estimate-normals] |
| `evaluate` | interpolant, dimension, evaluation coordinates; optional gradients; value/gradient accuracy `ANY` | coordinates, value, then optional `dx,dy,dz` to dimension | [source][cli-evaluate] |
| `extract-model` | interpolant and dimension | native model artifact | [source][cli-extract-model] |
| `fit` | value rows `coords,value[,lower,upper]`; optional full-gradient rows; tolerance; gradient tolerance defaults to value tolerance; max iterations `100`; accuracies `ANY`; optional initial/inequality/reduction | native interpolant artifact | [source][cli-fit] |
| `fit-model-to-variogram` | variogram plus model; weight scheme `1`; trials `30` | native model artifact | [source][cli-fit-variogram] |
| `isosurface` | 3D interpolant; optional seeds and snap `x,y,z[,relative_tolerance]`; bbox `AUTO`; required resolution; identity anisotropy; isovalue `0`; accuracies `ANY` | OBJ mesh | [source][cli-isosurface] |
| `normals-to-sdf` | `x,y,z,nx,ny,nz`; offset `AUTO`; identity anisotropy; retained-normal ratio `0.5` | `x,y,z,value` | [source][cli-normals-sdf] |
| `show-model` | model and dimension | formatted covariance-model description | [source][cli-show-model] |
| `show-variogram` | variogram and dimension; ID `NONE` | formatted variogram table | [source][cli-show-variogram] |
| `surface-25d` | 2D interpolant; optional 3D seeds; required bbox and resolution; accuracies `ANY` | OBJ mesh | [source][cli-surface-25d] |
| `unique` | coordinate-leading rows and dimension; minimum distance `1e-19` | surviving original rows | [source][cli-unique] |
| `variogram` | coordinate/value rows; detrend degree `-1`; optional normal score; 15 lags; lag/angular tolerance `AUTO`; optional anisotropic directions | native variogram artifact | [source][cli-variogram] |

**[F]** Command exceptions are printed to stderr as `error: …` and return 1. Parse failures print command usage before the error; successful commands return 0. [CLI main][cli-main]

**[F]** Model syntax is a single multi-token stream `--rbf NAME PARAMS [aniso A_11 A_12 ... A_dd] ...`; literal token `aniso` attaches a `Dim×Dim` matrix to the preceding RBF, and numeric tokens map in row-major order. Nugget defaults to 0 and polynomial degree to `AUTO`. Fit accepts value centers followed by optional full-gradient centers, absolute fit tolerance/fast-evaluation accuracy, and optional inequality or incremental-reduction modes. [model option grammar][model-options] [model parser][make-model] [matrix layout][types] [fit command][cli-fit]

**[F]** Text tables split on each space, tab, or comma without token compression. Only a line whose first character is `#` is a comment. The first parsed row fixes the column count; later mismatches are warned and skipped. Numeric parsing ignores the fast-float result status, so malformed or partially parsed tokens are not reliably rejected. Output uses `std::to_chars`. [table parser][table] [numeric conversion][conv]

**[R]** Preserve command names, option meanings/defaults/conflicts, column order, output shapes, and exit-code categories under the new `rapidrbf` executable. Do not preserve malformed-token acceptance, exact warning/progress wording, whitespace quirks, or partial parsing; replace them with deterministic checked errors.

**[R]** Add `--version`/build identity as an intentional extension so installed binaries can be tied to release evidence; frozen Polatory has no version command. [command registry][cli-commands] [CLI main][cli-main]

### Python

**[F]** The package is named `polatory`, requires Python 3.8 or newer plus NumPy, and exposes dimension modules `one`, `two`, and `three` through a pybind11 extension. [Python packaging][python-setup] [Python build][python-cmake] [package init][python-init]

**[F]** Each dimension exposes `Bbox`, the RBF base and all 16 RBF classes, `Model`, `Interpolant`, `DistanceFilter`, variogram calculation/fitting/set types, cross-validation, and detrending. Dimension-independent bindings include normal estimation, SDF generation, RBF field functions, isosurface/mesh, normal-score transformation, and variogram weight functions. [Python binding][python-binding]

**[F]** The bound RBF class names are `Biharmonic2D`, `Biharmonic3D`, `Triharmonic2D`, `Triharmonic3D`, `CovCubic`, `CovExponential`, `CovGaussian`, `CovGeneralizedCauchy3/5/7/9`, `CovSpherical`, and `CovSpheroidal3/5/7/9`; their short names are the 16 names in the RBF table below. [Python binding][python-binding] [RBF factory][make-rbf]

**[F]** RBF bindings expose anisotropy, CPD/covariance flags, parameter metadata, short name, value, gradient, and Hessian. `Interpolant` exposes ordinary/incremental/inequality fit, value and value-plus-gradient evaluation, and load/save. [Python binding][python-binding]

**[F]** The frozen Python test only imports the package and the three dimension modules; the captured build did not compile the extension. [Python test][python-test] [baseline execution](#baseline-execution)

**[S]** The SDF binding calls a constructor-shaped API `(points, normals, min_distance, max_distance, anisotropy)`, while the frozen C++ class accepts `(points, normals, offset[, anisotropy])`. This appears compile-incompatible if Python is enabled, but was not proven because the captured build disables Python. [Python SDF binding][python-binding] [C++ SDF API][sdf-generator]

**[R]** Treat the intended Python capabilities as required migration coverage, adjudicate and repair the SDF signature after a focused build reproducer, and test wheels/imports on every RapidRBF Tier-1 target. The new package should be `rapidrbf`, with a documented mechanical name/signature migration rather than pretending the unbuilt frozen binding is a trustworthy drop-in oracle.

## Numeric representation and orientation

**[F]** Scalar values are `double`; dynamic matrices are Eigen matrices with row-major storage except column vectors. `Index` is `Eigen::Index`. Points are rows of an `N × Dim` matrix. [types][types] [point types][point3d]

**[F]** A row point transforms as `point * A.transpose()`. For the physical row difference `d = x_target - x_source`, the column-vector equivalent used by formulas is `A d`. [point transform][point3d]

**[F]** Eigen defines row-major storage as consecutive row entries, which explains the frozen raw-byte matrix layout but should not leak into the new portable format. [Eigen storage-order documentation][eigen-storage]

**[R]** The Rust core should define one canonical convention: points are logical rows, gradient components are point-major, and anisotropy acts as `A d`. Internal storage may differ if public array strides and serialized order are explicit.

## RBF semantics

### Shared anisotropy and derivative rule

For isotropic radial function `φ(u)` and `u = A(x_t - x_s)`:

```text
value(d)    = φ(A d)
gradient(d) = (∇φ(A d)) A                  # row-vector form
hessian(d)  = Aᵀ (Hφ(A d)) A
```

**[F]** Those three expressions are the frozen implementation. `set_anisotropy` checks only `det(A) > 0`; it accepts non-symmetric matrices and shear, rejects reflections, and does not separately check finiteness or conditioning. [RBF base][rbf-base]

For a scalar radial profile `f(r)` and `r = ||u|| > 0`, the family-specific code is equivalent to:

```text
∇φ(u) = (f′(r)/r) uᵀ
Hφ(u) = (f′(r)/r) I + (f″(r)/r² - f′(r)/r³) u uᵀ
```

**[F]** The frozen kernels expand these derivatives algebraically per family, then apply the shared anisotropy chain above. Origin branches and unavailable Hessians listed below override the generic `r > 0` expression. [polyharmonic implementations][poly-even] [covariance exemplar][cov-gau] [RBF base][rbf-base]

**[R]** Preserve general positive-determinant linear anisotropy, including shear, because narrowing it to rotation-plus-scale changes results. Add finite/nonsingular/conditioning checks with explicit errors.

### Family inventory and value formulas

Let `r = ||A d||`. For covariance kernels let `ρ = r / range`; their parameters are ordered `[psill, range]`, CPD order is 0, and their minimum polynomial degree is `-1`. [covariance base][cov-base]

| Name | Parameters/default shorthand | Value | CPD | Evidence |
| --- | --- | --- | ---: | --- |
| `bh2` | `[scale=1, c=0]` | `+scale·q²·ln(q)`, `q = sqrt(r²+c²)` | 2 | [even polyharmonic][poly-even] |
| `bh3` | `[scale=1, c=0]` | `-scale·q` | 1 | [odd polyharmonic][poly-odd] |
| `th2` | `[scale=1, c=0]` | `-scale·q⁴·ln(q)` | 3 | [even polyharmonic][poly-even] |
| `th3` | `[scale=1, c=0]` | `+scale·q³` | 2 | [odd polyharmonic][poly-odd] |
| `cub` | `[psill, range]` | for `r < range`: `psill·(1-7ρ²+8.75ρ³-3.5ρ⁵+0.75ρ⁷)`; otherwise `0` | 0 | [cubic covariance][cov-cubic] |
| `exp` | `[psill, range]` | `psill·exp(-3ρ)` | 0 | [exponential covariance][cov-exp] |
| `gau` | `[psill, range]` | `psill·exp(-3ρ²)` | 0 | [Gaussian covariance][cov-gau] |
| `gc3` | `[psill, range]` | `psill/(1+7ρ²)^(3/2)` | 0 | [generalized Cauchy 3][cov-gc3] |
| `gc5` | `[psill, range]` | `psill/(1+2.4822022531844965ρ²)^(5/2)` | 0 | [generalized Cauchy 5][cov-gc5] |
| `gc7` | `[psill, range]` | `psill/(1+1.438027308408951ρ²)^(7/2)` | 0 | [generalized Cauchy 7][cov-gc7] |
| `gc9` | `[psill, range]` | `psill/(1+ρ²)^(9/2)` | 0 | [generalized Cauchy 9][cov-gc9] |
| `sph` | `[psill, range]` | for `r < range`: `psill·(1-1.5ρ+0.5ρ³)`; otherwise `0` | 0 | [spherical covariance][cov-sph] |
| `sp3` | `[psill, range]` | piecewise spheroidal formula below with `p=3` | 0 | [spheroidal 3][cov-sp3] |
| `sp5` | `[psill, range]` | piecewise spheroidal formula below with `p=5` | 0 | [spheroidal 5][cov-sp5] |
| `sp7` | `[psill, range]` | piecewise spheroidal formula below with `p=7` | 0 | [spheroidal 7][cov-sp7] |
| `sp9` | `[psill, range]` | piecewise spheroidal formula below with `p=9` | 0 | [spheroidal 9][cov-sp9] |

**[F]** The “2D” and “3D” in polyharmonic class names identify the traditional radial formula, not a template-dimension restriction; all 16 names are constructible in each of dimensions 1, 2, and 3. [RBF factory][make-rbf] [RBF tests][test-rbf]

**[F]** Polyharmonic constructors accept zero parameters as `[1,0]`, one as `[scale,0]`, or exactly two. Although all families advertise non-negative lower bounds, the common setter validates only parameter count; negative values and zero/negative covariance ranges can enter evaluation. [polyharmonic parameter handling][poly-even] [common setter][rbf-base] [covariance bounds][cov-base]

For spheroidal kernels:

```text
L(ρ) = psill·(1-Aρ)
T(ρ) = psill·B/(1+Cρ²)^(p/2)
sp(ρ) = L(ρ), ρ < ρ₀
        T(ρ), ρ >= ρ₀
```

| Name | `ρ₀` | `A` | `B` | `C` |
| --- | ---: | ---: | ---: | ---: |
| `sp3` | 0.18657871684006438 | 2.009875543958482 | 0.8734640537108553 | 7.181510581693163 |
| `sp5` | 0.2580127411803573 | 1.6149073288415876 | 0.8575980168032007 | 2.5036086535164204 |
| `sp7` | 0.2944149476843637 | 1.4859979204216045 | 0.8494862533016855 | 1.44208314742683 |
| `sp9` | 0.31622776601683794 | 1.4230249470757708 | 0.8445585690332554 | 1 |

**[F]** The constants and strict `< ρ₀` branch are frozen in the four spheroidal headers. For fast evaluation each full spheroidal kernel can be split into a compact direct correction `L-T` below `ρ₀` and an infinite-support fast tail `T`; the full user-visible function is the piecewise sum above. [sp3][cov-sp3] [sp5][cov-sp5] [sp7][cov-sp7] [sp9][cov-sp9]

### Origin and support-edge behavior

**[F]** Even polyharmonic value, gradient, and Hessian return exact zero when `q == 0`; odd polyharmonic gradient and Hessian return zero there. These are explicit legacy conventions around otherwise singular expressions. [even polyharmonic][poly-even] [odd polyharmonic][poly-odd]

**[F]** Cubic and spherical use a strict `r < range` support branch, so value and implemented gradient are exactly zero at the support radius. Their Hessian methods throw “not implemented.” [cubic covariance][cov-cubic] [spherical covariance][cov-sph]

**[F]** Exponential, spherical, and full spheroidal derivative formulas divide by `r` or `ρ` at coincidence; they can produce non-finite gradients/Hessians at `d=0`. Gaussian and generalized Cauchy formulas are finite at the origin. [exponential][cov-exp] [spherical][cov-sph] [spheroidal 3 exemplar][cov-sp3] [Gaussian][cov-gau] [generalized Cauchy 3 exemplar][cov-gc3]

**[I]** Hermite self-interaction is therefore not numerically defined for `exp`, `sph`, or `sp*`, and cubic/spherical cannot form the gradient-gradient block because Hessians are unavailable. The upstream fit tests exercise Hermite fitting only with `th3`. [direct operator][direct-op] [fitter tests][test-fitter]

**[R]** Define a kernel capability matrix (`value`, `gradient`, `Hessian`, `Hermite-safe at coincidence`). Reject unsupported Hermite models before solving. Preserve exact support branch values; report singular coincident derivatives as checked domain errors rather than NaN propagation.

## Model and polynomial semantics

**[F]** A `Model` must contain at least one RBF. Composite models sum their RBFs; CPD order is the maximum component order. Automatic polynomial degree is `CPD-1`; an explicit degree must be between that minimum and 2. A model is a covariance model only if every component is a covariance function. [Model][model]

**[F]** Nugget must be non-negative and is parameter 0, followed by each RBF's parameters in model order. Model equality compares RBFs, polynomial degree, and nugget exactly. Human-readable descriptions are only available for covariance models. [Model parameters and equality][model]

**[F]** Covariance descriptions decompose inverse anisotropy and multiply the base range by axis scales. Two-dimensional output reports major/minor ranges and rotation normalized to `[0,180)`; three-dimensional output reports major/semi-major/minor ranges, dip azimuth in `[0,360)`, dip in `[0,90]`, and rotation in `[0,180)`, with four-decimal formatting. [Model descriptions][model]

**[F]** Degree `-1` has no polynomial. Monomial order is:

- 1D: `1, x, x²`
- 2D: `1, x, y, x², xy, y²`
- 3D: `1, x, y, z, x², xy, xz, y², yz, z²`

Gradient polynomial rows are point-major, then component order. [basis size][poly-base] [monomial implementation][monomial]

**[F]** Nugget is added only to the value/value self diagonal in the interpolation operator; it does not alter gradient blocks. Public prediction evaluates the smooth RBF-plus-polynomial field and does not add nugget back at training points. [direct operator][direct-op] [direct evaluator][direct-eval]

**[R]** Preserve model composition, CPD/degree rules, parameter order, basis order, anisotropy range/angle interpretation, and smooth-predictor nugget semantics exactly. Preserve `show-model` column meaning, but not padding or last-decimal artifacts. Validate all deserialized models through the same constructors rather than bypassing invariants.

## Hermite signs, block layout, and vector order

For value centers `X`, full-gradient centers `G`, and `d = target-source`, the frozen direct operator is:

```text
┌ Φ(X,X)+ηI     -D₂Φ(X,G)      P(X)  ┐
│ D₁Φ(G,X)      -D₁D₂Φ(G,G)    Pᵍ(G) │
└ P(X)ᵀ          Pᵍ(G)ᵀ         0     ┘
```

**[F]** The sign convention follows from differentiating with respect to source versus target:

- value from a value-source weight: `+φ(d)`
- value from a gradient-source weight: `-∇φ(d)·λg`
- target gradient from a value-source weight: `+∇φ(d) λ`
- target gradient from a gradient-source weight: `-Hφ(d) λg`

[direct operator][direct-op] [direct evaluator][direct-eval]

**[F]** Unknowns, right-hand sides, and mixed evaluation results place all scalar values first, then all `Dim` components of each gradient point in point-major order; polynomial weights are last. A gradient center always supplies a complete `Dim`-component gradient—there is no partial-component constraint. [direct evaluator][direct-eval] [fit input assembly][cli-fit]

**[R]** Make this block matrix and flattened order a normative specification with direct dense golden tests in 1D/2D/3D. Compare field predictions and residuals; do not require identical coefficient vectors when systems admit numerically different equivalent solutions.

## Fitting modes and validation

**[F]** `Interpolant` exposes ordinary fit, greedy incremental fit, value-only inequality fit, reuse of an initial fitted interpolant, value evaluation, mixed value/gradient evaluation, and save/load. [Interpolant][interpolant]

**[F]** Ordinary fit validates point/value shapes, strictly positive tolerance and requested fast-evaluation accuracy, non-negative maximum iterations, and enough constraints for the polynomial basis. A special linear case permits one value center plus at least one gradient center. [Interpolant validation][interpolant]

**[F]** Inequality fitting uses `NaN` as “bound absent,” rejects a non-zero nugget, and accepts lower/equality/upper value columns. Incremental fitting greedily adds centers with the largest current residual, applies a spatial distance filter, and halves the filter distance until its configured minimum. [inequality fitter][inequality-fitter] [incremental fitter][incremental-fitter]

**[F]** Initial-interpolant reuse requires exact model equality and exact floating-point coordinate hashing. A different model warns and starts from zero; only exactly matching coordinates transfer weights. [fitter][fitter]

**[S]** In the inequality active-set update, entries are removed from an `indices` vector while later values appear to be read from a still-full `values_fit` vector. A focused reproducer is required to determine whether this misaligns active constraints after removals. [inequality fitter][inequality-fitter]

**[R]** Preserve the three fit modes and constraint meanings. Permit warm starts across equivalent serialized models and coordinates only under an explicitly defined match policy; exact legacy hash behavior need not constrain the new API.

## Solver, convergence, and memory

### FGMRES contract

**[F]** The large solver is unrestarted right-preconditioned FGMRES with a multi-level restricted additive Schwarz (RAS) preconditioner. The Krylov implementation stores both Arnoldi basis vectors `v` and flexible preconditioned vectors `z`. [solver][solver] [FGMRES][fgmres] [RAS][ras]

**[F]** User-visible convergence is not the internal relative GMRES estimate. Polatory computes the interpolation residual and requires the maximum absolute residual over all scalar values, and separately over all gradient components, to be at most the requested fit tolerance. It checks a direct sample of up to 1024 value observation points and 1024 gradient observation points (each contributing `Dim` components) first, then the full fast residual only after the sample passes. Default `mt19937` plus standard-library sampling fixes the sample within the captured toolchain, but does not guarantee identical indices across C++ standard-library implementations. Equality with tolerance passes because the check is `> tolerance`. Exhausting iterations throws. [solver][solver] [residual evaluator][residual]

**[I]** At iteration `k`, just `v` and `z` require approximately `(2k+1)·N·8` bytes for `N` scalar unknowns, excluding Hessenberg data, centers, FMM trees, RAS matrices/factorizations, and application buffers. At `N=1,000,000` and `k=100`, that is about 1.61 GB. Total Krylov storage is `O(Nk+k²)`. [FGMRES storage][fgmres] [GMRES storage][gmres-base]

**[S]** With an all-zero right-hand side, GMRES setup normalizes a zero residual and the later early-return test sees a `0/0` relative residual. The outer interpolation-residual check may still return the zero solution before Arnoldi runs, but a NaN Krylov basis has already been stored; focused zero-RHS and exact-warm-start tests should determine whether any path leaks it. [GMRES base][gmres-base] [solver][solver]

**[R]** RapidRBF convergence acceptance must use a full, independently recomputed infinity norm by value and gradient channel. Exact iteration identity and the internal relative-residual trace are not required, but every scenario must enforce an iteration/matvec/preconditioner-application envelope as a convergence and performance gate. Add an exact zero-RHS fast path and a bounded/restarted or compressed-basis memory policy before the million-scale gate.

### FMM and requested accuracy

**[F]** Fast operators construct scalar, gradient, transposed-gradient, and Hessian FMM evaluators per RBF and divide requested absolute accuracy among contributing terms. Coordinates are transformed by anisotropy before FMM evaluation and derivative outputs are transformed back consistently. [fast operator][fast-op] [fast evaluator][fast-eval] [FMM kernels][fmm-eval]

**[F]** Direct evaluation is selected below `1024²` source-target interactions for a non-symmetric evaluator and below 1024 centers for a symmetric evaluator. The symmetric path manually adds self-interactions. [FMM evaluator][fmm-eval] [symmetric FMM evaluator][fmm-sym]

**[F]** FMM configuration uses fixed defaults for infinite/internal-zero accuracy; otherwise it samples up to 10,000 source points with default `mt19937` and `std::shuffle`, tries interpolation orders/degrees, and throws if none meets the sampled error. The sequence is fixed within the captured toolchain but not a cross-standard-library contract. The configuration cache is keyed by tree height, even though a source comment notes that significant weight changes may require recomputation. [FMM accuracy estimator][fmm-accuracy] [FMM evaluator configuration][fmm-eval]

**[I]** Polatory's “requested accuracy” is an empirical sampled backend target, not a proof of uniform error for arbitrary targets or changing solver vectors. A differential test that merely repeats its sampling can accept an inaccurate backend.

**[R]** Validate fast evaluation against a direct/high-precision oracle on held-out targets, adversarial anisotropy, support boundaries, source points, and sizes around both direct/FMM cutovers. Require actual max absolute error no greater than the public `accuracy` value, with a documented small floating comparison allowance.

**[R, cross-research decision]** Issue #3 proposes a provisional backend-promotion envelope `max(1.25×Polatory_error, 2×requested_accuracy×reference_scale)`, while frozen Polatory compares an absolute infinity error directly with its divided absolute accuracy. `/to-spec` must not make both normative. This audit recommends preserving absolute public semantics; the scaled Issue #3 expression may remain a prototype/promotion tolerance until calibration supplies an explicit unit/scale rationale. [FMM accuracy estimator][fmm-accuracy] [engine/solver research][engine-research]

### RAS behavior

**[F]** RAS uses fine-to-coarse size ratio 10, a coarsest target of 2048, subdomains of at most 1024 centers, overlap quota 0.5, and OpenMP dynamic scheduling. [RAS preconditioner][ras] [domain divider][domain-divider]

**[F]** Domain partitioning uses anisotropy-transformed coordinates only when the model has exactly one non-identity RBF. Composite-RBF models partition raw coordinates. [RAS preconditioner][ras]

**[F]** RAS factors are streamed through a temporary binary cache whose reads and writes are serialized by one mutex. Windows opens the cache with delete-on-close semantics; Unix unlinks it while still open. An after-exit directory scan therefore cannot recover peak scratch usage or cache I/O. [binary cache][binary-cache]

**[I]** Matching these constants or partitions is neither sufficient nor necessary for compatible convergence. They are useful baseline metadata for difficult cases, not a public contract.

**[R]** Specify RAS/FGMRES at the capability level: convergence envelope, iteration/matvec ceiling on named corpora, peak-memory and peak-scratch ceilings, cache-I/O accounting, thread-scaling floor, and deterministic failure reporting. Runs need a dedicated temporary root, live scratch high-water and I/O measurement, and cleanup verification. Preserve each platform's raw memory semantics—Windows working set and commit, Linux cgroup `memory.peak`, and macOS `ru_maxrss`—alongside normalized bytes. Allow a Rust-native preconditioner, private C ABI wrapper, or replacement method to satisfy the same gates. [baseline audit][baseline-research]

## Kriging and variogram semantics

**[F]** Polynomial detrending supports degrees 0–2 and solves normal equations with LDLT; it does not explicitly report rank deficiency. [detrend][detrend]

**[F]** An experimental pair contributes `γ = 0.5·(v_j-v_i)²`. With lag `h` and tolerance `t`, its distance can enter every integer bin from `ceil((distance-t)/h)` through `floor((distance+t)/h)`, clipped to the configured range; a pair may therefore enter multiple overlapping bins. Default tolerance is half a lag. [variogram calculator][variogram-calculator]

**[F]** Automatic directional classification assigns a pair to the direction with maximum squared dot product. An explicit angular tolerance may assign it to more than one direction. Direction vectors are normalized; generated sets contain one isotropic direction, 8 directions in 2D, and 46 in 3D. Pair enumeration is `O(n²)` and OpenMP partial sums merge through critical sections. [variogram calculator][variogram-calculator] [variogram builder][variogram-builder]

**[I]** Pair counts should be exact for fixed inputs, while final mean distances/semivariances can vary by floating reduction order and thread count.

**[F]** Normal-score transformation sorts values, maps rank `i` to `(2i+1)/(2n)`, and uses a 30-term Hermite approximation by default. `std::sort` is not stable, so tied observations can receive distinct rank scores. [normal-score transform][normal-score]

**[S]** Empty and one-element normal-score inputs reach divisions/indexing that are not guarded as public errors. [normal-score transform][normal-score]

**[F]** A covariance model's semivariogram is `nugget + Σ(C_i(0)-C_i(h))`. Weight-function code returns the square root of the intended least-squares weight because Ceres squares residual blocks; six schemes are exposed. [variogram][variogram] [weight function][weight-function]

**[F]** Variogram model fitting uses Ceres dynamic numeric differentiation and `DENSE_QR`, at most 100 iterations, and `hardware_concurrency` threads. It performs multiple trials (CLI default 30); anisotropic trials randomize orientation but expose no seed. Two-dimensional anisotropy requires at least two variograms and three-dimensional anisotropy at least three. [variogram fitting][variogram-fitting] [2D fitting][variogram-fitting-2d] [3D fitting][variogram-fitting-3d] [fit CLI][cli-fit-variogram]

**[F]** The fitting routine first resets every input RBF anisotropy to identity, so `fit_anisotropy=false` does not preserve a supplied anisotropy. It also assumes the second parameter is a range without first rejecting non-covariance/polyharmonic models. [variogram fitting][variogram-fitting]

**[F]** Ceres documents dynamic numeric differentiation and `DENSE_QR`; those establish what the frozen implementation invokes, not a requirement that RapidRBF use Ceres. [Ceres modeling documentation][ceres-modeling] [Ceres solver documentation][ceres-solving]

**[F]** Cross-validation holds out integer set IDs and returns predictions in original row positions. It exposes prediction only, not kriging variance/uncertainty. [cross-validation][cross-validate]

**[I]** The README's “dual kriging” promise is therefore observable as covariance-model prediction through the shared interpolant, variogram, fitting, and cross-validation surfaces—not as a separate uncertainty/variance API. [README][readme] [cross-validation][cross-validate]

**[R]** Preserve variogram bin membership, directions, semivariance formula, weights, prediction order, and documented defaults. A narrow private Ceres adapter may remain for v1 if packaging gates pass; replace it only after a Rust fitter matches differential objectives/predictions and bounds. Do not require optimizer parameters bit-for-bit. Add seed control, validate covariance models, and define tie/small-input normal-score behavior. [engine/solver research][engine-research]

## Point-cloud and SDF semantics

**[F]** The FLANN KD-tree requests exact searches (`checks = unlimited`) with unsorted results and converts squared distances back with `sqrt`. Radius squared is cast to `float`, creating a precision boundary near inclusion thresholds. [KD-tree][kdtree]

**[F]** `DistanceFilter` greedily preserves the first surviving input index and removes its radius neighbors. Results are therefore input-order and radius-membership dependent. Its minimum accepted distance is `sqrt(min positive float)`, approximately `1.08e-19`. [distance filter][distance-filter]

**[F]** Plane estimation centers neighbors, uses SVD/PCA, takes the right singular vector for the smallest singular value as the normal, and computes a plane factor after flooring three error terms. [plane estimator][plane-estimator]

**[F]** Normal estimation supports neighbor-count and radius scales and retains the candidate with highest plane factor. It requires `k >= 3`; fewer than three total points yield zero normals, and an underpopulated maximum radius can also yield zeros. Orientation modes include toward a point, toward a direction, and a closed-surface priority traversal; the closed-surface default uses 100 neighbors and prints connected-component information. [normal estimator][normal-estimator]

**[S]** In multi-radius estimation, a smaller radius can reduce a previously sufficient neighborhood below three before `PlaneEstimator` is called; the only evident guard there is a debug assertion. [normal estimator][normal-estimator] [plane estimator][plane-estimator]

**[F]** SDF generation keeps every surface point at value zero and, for each non-zero normal, creates positive/negative off-surface points. Non-positive offset selects an automatic starting distance from up to six nearest neighbors and adjusts until the original point remains nearest. Under anisotropy, points transform by `A` and normals by `A⁻ᵀ`, then renormalize. [SDF generator][sdf-generator]

**[F]** The `normals-to-sdf` CLI rounds `ratio · normal_count`, shuffles indices with a default-constructed `mt19937`, and keeps that many normals before SDF generation. The selection is repeatable for one standard-library implementation but is not a portable seeded-file contract. [normals-to-SDF command][cli-normals-sdf]

**[S]** Non-positive cosine/alignment and unvalidated offsets can make the adjustment invalid or non-terminating for pathological neighborhoods. A focused adversarial test is required. [SDF generator][sdf-generator]

**[R]** Replace FLANN with a Rust-native exact neighbor index while specifying radius inclusivity, tie/order behavior, finite-input requirements, and bounded SDF adjustment. Preserve first-survivor filtering by default because it is visible in generated centers.

## Isosurface and mesh semantics

**[F]** Isosurface construction accepts a bounding box, resolution, and anisotropy with positive determinant. It supports all-lattice traversal or seed tracking; seed mode requires non-empty seeds. Relative snap tolerances must lie in `[0,1]`. [isosurface API][isosurface]

**[F]** The pipeline performs two cluster/smooth passes, refines the second pass, then performs up to 20 snap/smooth iterations with a mesh-hash cycle stop, followed by two thinning/smoothing passes and clipping. [isosurface implementation][isosurface]

**[F]** A 2.5D RBF field is exactly `z - interpolant(x,y)`. [2.5D field][rbf-field-25d]

**[F]** Mesh OBJ output contains vertices and one-based triangles only. Empty and entire fields use textual sentinels `# empty` and `# entire`; normals and materials are not emitted. [mesh][mesh]

**[F]** The extraction lineage cites regularised marching tetrahedra; the publisher record is the primary external description of that algorithm. [Treece et al.][treece]

**[R]** Geometry acceptance should compare sentinel state, manifold/defect invariants, bounding-box containment, isovalue residual, and symmetric surface distance. Vertex/triangle ordering and exact tessellation are non-contractual unless a downstream format requires them.

## Persistence layout and import boundary

**[F]** Frozen I/O writes trivially copyable objects as native bytes. Strings/vectors prefix native `size_t`; dynamic Eigen matrices prefix native `Eigen::Index` dimensions and then raw storage. Reads do not encode or verify a magic value, version, type, endian, scalar width, checksum, maximum length, or trailing bytes. [common I/O][common-io]

**[F]** Model field order is RBF vector, native `int` polynomial degree, and `double` nugget. An RBF writes short-name string, parameter vector, and fixed anisotropy matrix. An interpolant writes model, fitted flag, value centers, gradient centers, bounding-box min/max, and weights. Variogram sets write a vector whose entries contain distances, semivariances, pair counts, and direction. [Model serialization][model] [RBF serialization][rbf-io] [Interpolant serialization][interpolant] [Variogram serialization][variogram-set]

**[F]** Dimension is implicit in the C++ template/fixed matrix columns and is not encoded. CLI load operations therefore require the caller's `--dim`; artifact type is likewise not self-described. Deserialization uses private default constructors and can bypass public invariants. [Model serialization][model] [Interpolant serialization][interpolant] [CLI extraction][cli-extract-model]

**[I]** A malformed length can request an unbounded allocation before a short read is detected, and an artifact written with different native widths/endian/layout is not portable.

**[R]** Implement a bounded, one-way model/interpolant importer for every known 64-bit RapidRBF Tier-1 legacy layout, beginning with the captured Windows x86_64 fixtures. If layouts differ and cannot be detected safely, the specification must state the supported matrix explicitly and provide a conversion route; this research must not silently narrow import to Windows. Require the caller or wrapper to supply artifact kind and dimension; reject impossible sizes, truncation, non-finite fields, invalid models, and trailing bytes. Never write the legacy format. Legacy `VariogramSet` import is a separate scope decision, not implied by the standing project constraint.

**[R]** Define the new RapidRBF artifact with magic, schema version, artifact kind, dimension, scalar encoding, canonical little-endian integer/floating representation, explicit row-major logical arrays, length limits, and checksum. Capture required legacy model/interpolant fixtures across dimensions and RBF families before Polatory tooling is retired; retain variogram fixtures as differential evidence and promote them to import fixtures only if that scope is adopted.

## Dependency migration boundary

| Dependency | Frozen role | Observable contract | v1 boundary recommendation |
| --- | --- | --- | --- |
| Eigen | Dense/sparse arrays, factorizations, row-major public data | Shapes, logical ordering, numerical result | Replace in Rust; never expose Eigen ABI |
| MKL | BLAS/LAPACK acceleration and ScalFMM build option | Performance and numeric tolerances | Optional backend; portable fallback required |
| ScalFMM3 | Far-field matvec/evaluation | Absolute error, scale, memory, threading | Private backend seam; FFI is acceptable only behind a safe Rust interface |
| Ceres | Variogram nonlinear least squares | Objective/predictions and bounds | A narrow private adapter may remain for v1; replace after a Rust fitter passes differential gates |
| FLANN | Exact nearest/radius queries | Neighbor membership plus specified tie policy | Replace with Rust-native spatial index |
| Boost/fast-float | Boost supports CLI, temp paths, containers/hashing, math, strings/ranges; fast-float parses numeric tables | Valid-input math/workflow behavior, not Boost types | Replace or isolate per role; intentionally harden malformed parsing |
| libigl | Geometry support | Mesh invariants/geometric accuracy | Replace or isolate; no source compatibility |

**[F]** The frozen dependency roles are visible in the root/library/Python build files, manifest, temporary cache, normal-score transform, and parser. [root build][root-cmake] [library build][src-cmake] [Python build][python-cmake] [manifest][vcpkg-manifest] [binary cache][binary-cache] [normal score][normal-score] [parser][conv]

**[F]** ScalFMM's official quick-start describes near-field direct work plus far-field uniform/Chebyshev interpolation; this is consistent with Polatory's direct/fast split, but does not define Polatory's user contract. [ScalFMM documentation][scalfmm-docs]

**[F]** Restricted additive Schwarz is an established domain-decomposition preconditioner family; the frozen constants and hierarchy are Polatory-specific. [Cai and Sarkis][ras-paper] [Polatory RAS][ras]

**[F, sibling research]** Issue #3 selects a Rust-led hybrid: Rust owns the four-block operator, FGMRES, RAS, memory cache, Faer linear algebra, and Rayon thread policy; ScalFMM is only a controlled C-ABI fallback. That architecture is compatible with every observable boundary in this audit. [engine/solver research][engine-research]

**[R]** Make the far-field engine an internal trait with capabilities for scalar, gradient, transposed-gradient, and Hessian actions. Keep direct evaluation as the oracle. This supports the Rust-native path plus a controlled ScalFMM fallback without changing the public API or acceptance corpus.

## What the frozen tests prove—and do not prove

**[F]** The captured suite passed 89 tests, but fast evaluator/operator/symmetric tests use only anisotropic `th3`, approximately 1024 points, and error around `1e-4`. The large fitter test uses only `th3` with 10,000 values and 10,000 gradients, tolerance `1e-3`, and fast accuracy `1e-5`. [baseline execution](#baseline-execution) [evaluator test][test-evaluator] [operator test][test-operator] [fitter test][test-fitter]

**[F]** RBF derivative tests use random non-coincident 3D points, finite-difference step `h = 1e-8`, and norm tolerance `1e-4`; cubic and spherical Hessian checks are commented out. [RBF tests][test-rbf]

**[F]** Kriging tests cover detrending and variogram calculation, but not model fitting, cross-validation, or normal-score transformation. Python tests cover imports only. No CLI integration suite exists in the frozen test tree. [kriging tests][test-variogram] [detrend tests][test-detrend] [Python test][python-test] [test build inventory][test-cmake]

**[F]** The only focused serialization round-trip found in the test tree is for `VariogramSet`; model/interpolant compatibility and corrupt-input behavior lack fixtures. [variogram test][test-variogram]

**[F]** The benchmark script generates 1k, 10k, 100k, and 1M point sets and separately emits five `gstat` and sixteen Polatory prediction outputs; it contains no comparison command. The R simulation has no `set.seed`, and the repository contains no retained result bundle or peak-resource acceptance record. [benchmark driver][benchmark-sh] [simulation][benchmark-sim]

**[I]** Passing the upstream suite is necessary regression evidence but far from sufficient for RapidRBF v1.0.0. It misses most kernels in fast/Hermite paths, singular/support edges, persistence portability, Python buildability, CLI behavior, and an immutable million-scale gate.

## Differential validation and numerical acceptance

### Reference hierarchy

**[R]** Use this oracle order:

1. Mathematical formula evaluated directly in extended/high precision for RBF value/gradient/Hessian and small systems.
2. Deterministic dense direct evaluation/solve in double precision.
3. Frozen Polatory `4a30beb` plus captured ScalFMM `0be3d74…` for observable legacy behavior.
4. RapidRBF candidate.

This prevents a Polatory defect or sampled FMM error from becoming the definition of mathematical correctness. Carr et al. provide primary background for direct and fast RBF reconstruction at scale, but RapidRBF acceptance must be based on the explicit formulas and corpus here. [Carr et al.][carr]

### Required corpus

**[R]** The v1 differential corpus should include:

- every RBF in 1D, 2D, and 3D;
- identity, rotation/scale, ill-conditioned-valid, and shear anisotropy;
- regular points, coincidence, `nextafter` points around every strict support/spheroidal branch, very small/large ranges, and parameter validation failures;
- polynomial degrees `-1,0,1,2` wherever legal, composite models, nugget, values-only, gradients-only-where-legal, and mixed Hermite layouts;
- ordinary, incremental, lower/equality/upper inequality, zero RHS, warm start, non-convergence, and invalid input;
- direct/FMM cutover neighborhoods, adversarial target boxes, changing weights, captured sample-index fixtures, and thread counts 1 plus available cores;
- variogram overlapping bins/directions/ties, deterministic fitting trials, cross-validation ordering, and normal-score small/tied inputs;
- point-cloud ties/radius boundaries/disconnected components/degenerate neighborhoods and SDF adversarial normals;
- empty/entire/seeded/all-lattice 2.5D and 3D isosurfaces;
- every required legacy model/interpolant kind/dimension plus truncation, huge length, wrong kind/dimension, non-finite, and trailing-byte cases.

### Norms and pass criteria

**[R]** Apply these comparison rules; exact numeric constants remain a calibration task for the immutable corpus:

| Case | Required comparison |
| --- | --- |
| RBF regular value/gradient/Hessian | `abs(candidate-oracle) <= atol + rtol·abs(oracle)` componentwise; per-family tolerances generated from high-precision conditioning |
| Compact/spheroidal branches | Exact branch classification and exact zero outside support; tolerance inside |
| Small dense interpolation | Full value and gradient residual infinity norms `<= fit_tolerance`; held-out predictions compared to direct oracle |
| Fast evaluation/matvec | Actual held-out max absolute error `<= requested_accuracy` plus a small documented floating guard |
| Large iterative fit | Independently recomputed full value and gradient infinity norms `<= fit_tolerance`; no coefficient/iteration identity requirement |
| Variogram | Bin/direction membership and counts exact; means/gammas use declared reduction tolerance |
| Optimized variogram model | Valid bounds, objective and held-out predictions within tolerance; parameters need not be identical |
| Point cloud | Exact membership/order only where specified; otherwise compare distances, orientations, and invariants |
| Isosurface | Sentinel exact; manifold/defect/bbox/isovalue and symmetric surface-distance thresholds |
| Legacy import | Exact structural fields plus tolerance for floats; every malformed fixture fails safely |
| New artifact | Canonical bytes and round-trip exactness across RapidRBF Tier-1 platforms |

**[R]** Do not require cross-platform bitwise equality for floating calculations. Require immutable content-addressed datasets and stable failure categories. Generator seeds are provenance, not identity: record generator SHA, literal arguments, runtime/standard-library versions, and SHA-256 of generated files. Bitwise identity is appropriate only for the new canonical artifact encoding and explicitly deterministic integer/structural outputs.

### Million-scale release gate

**[R]** Establish an immutable, content-addressed million-scale corpus with value-only and mixed-gradient variants. Declare `n_value_centers`, `n_gradient_centers`, polynomial size, and `n_scalar_unknowns = n_value_centers + Dim·n_gradient_centers + n_polynomial`; do not call one million mixed-gradient centers “one million unknowns.” A seed alone is insufficient because `std::uniform_real_distribution`, shuffle/sample algorithms, and the unseeded R/gstat simulation are not portable replay identities. [point generator][benchmark-points] [random point implementation][random-points] [residual sampling][residual] [FMM sampling][fmm-accuracy] [simulation][benchmark-sim]

Record:

- dataset/generator hashes, literal arguments, seeds, and runtime/library versions;
- end-to-end fit and evaluation wall time;
- raw platform-native peak-memory fields plus normalized bytes per scalar unknown;
- scratch-space high-water mark and cache I/O while the process is alive;
- matvec count, preconditioner applications, and final full residuals;
- 1-thread and all-core results, effective thread count, and oversubscription policy;
- cold/warm cache runs and artifact I/O;
- held-out direct-oracle error on frozen, content-addressed samples;
- failure behavior under a configured memory ceiling.

**[R]** Execute the million rung only after lower rungs produce explicit wall-time, peak-memory, scratch, output-size, timeout, cleanup, and recovery estimates under the Issue #4 safety gate. [baseline audit][baseline-research]

**[R]** Performance parity should be expressed as an agreed envelope against the Issue #4 evidence bundle's designated same-host paired baseline, with absolute memory and scratch ceilings. The current local snapshot is not that authority. FGMRES memory growth must be measured separately from centers, FMM, RAS, and output buffers so a backend change cannot hide a regression. [baseline audit][baseline-research]

## Proposed differences and adjudication gates

These are recommendations, not already-adopted exceptions. `/to-spec` may make fact-backed hardening choices deliberate changes; every item derived from **[S]** evidence requires a focused reproducer and explicit adjudication first.

1. **[R]** Reject non-finite kernel/model/coordinate inputs, negative `psill`/scale/`c`, and non-positive covariance range instead of evaluating them.
2. **[R]** Reject non-finite or singular anisotropy while retaining every finite, non-singular, positive-determinant transform, including shear. Ill-conditioning alone should produce diagnostics, not rejection, unless a separately approved numerical limit is exceeded.
3. **[R]** Reject undefined coincident derivatives and Hermite-incompatible kernels before assembly.
4. **[R, conditional on reproducer]** Adjudicate the zero-RHS/NaN-basis path; regardless of legacy outcome, define bounded Krylov-memory behavior.
5. **[R, conditional on reproducer]** Define stable tied-rank and empty/singleton normal-score behavior.
6. **[R, conditional on reproducers]** Bound KD/SDF searches and fail degenerate geometry safely.
7. **[R]** Use checked CLI parsing rather than preserving malformed/partial numeric reads.
8. **[R]** Import but never emit unsafe native Polatory binaries; emit a versioned portable artifact.
9. **[R, conditional on build reproducer]** Repair the stale Python SDF API and test actual wheels.
10. **[R]** Add seed/thread controls where randomized or parallel reduction behavior affects reproducibility.

## Decisions and follow-up work exposed by this audit

The audit resolves the compatibility question but exposes implementation tickets that `/to-spec` should either include or explicitly defer:

- **[R]** Capture the required frozen model/interpolant fixture matrix before any upstream/toolchain drift, and decide separately whether legacy variograms are imported or differential evidence only.
- **[R]** Build the frozen Python extension in an isolated branch and prove the SDF signature mismatch; specify the corrected `rapidrbf` API.
- **[R]** Add focused reproducers for the inequality active-set index suspicion, zero-RHS FGMRES, normal-score `n<=1`, multi-radius underpopulation, and pathological SDF adjustment.
- **[R]** Define the kernel derivative/Hermite capability matrix and intentional domain errors.
- **[R]** Pin the captured ScalFMM object for baseline reproducibility and define a backend-neutral fast-operator trait.
- **[R]** Produce content-addressed direct-oracle and million-scale corpora with generator provenance, machine metadata, peak-memory/scratch collection, and thread controls.
- **[R]** Decide the numerical tolerance budget per operation/family; a single global epsilon is not defensible across direct, FMM, fitting, and geometry workflows.

## Bottom line

**[R]** The safe migration target is not “rewrite the classes in Rust.” It is a Rust-native domain model whose direct evaluator is the mathematical oracle, whose fast operator is replaceable, whose solver is accepted by full residual and scale gates, and whose CLI/Python/artifact edges make legacy behavior explicit.

**[R]** A staged ScalFMM FFI fallback is compatible with this target only if it is private, pinned, safe at the Rust boundary, prebuilt and transparent to users, license-compliant, self-contained on every RapidRBF Tier-1 target, and judged by the same oracle corpus. Crate, wheel, and CLI closure size plus clean-host installation must be proven before adoption. The Rust-native engine can replace or bypass it without a public breaking change. Conversely, retaining ScalFMM without those proofs, held-out accuracy validation, and memory/scratch gates would not preserve the behavior RapidRBF actually needs.

## Frozen and primary sources

[polatory-commit]: https://github.com/polatory/polatory/commit/4a30beb08053fb339ce899e255be4b6d3f74aa0c
[rapidrbf-map]: https://github.com/qingsonger/RapidRBF/issues/1
[readme]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/README.md
[umbrella]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/polatory.hpp
[kriging-umbrella]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging.hpp
[root-cmake]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/CMakeLists.txt
[src-cmake]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/CMakeLists.txt
[vcpkg-manifest]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/vcpkg.json
[vcpkg-config]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/vcpkg-configuration.json
[baseline-research]: https://github.com/qingsonger/RapidRBF/blob/0066f21a98ffb941fb83af27d35055f431a7064b/docs/research/polatory-validation-performance-release-baseline.md
[engine-research]: https://github.com/qingsonger/RapidRBF/blob/391acd13206c81911a9b97e2eda8361c2b6a90b2/docs/research/engine-solver-and-dependency-options.md
[types]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/types.hpp
[point3d]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/geometry/point3d.hpp
[rbf-base]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/rbf_base.hpp
[make-rbf]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/make_rbf.hpp
[poly-even]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/polyharmonic_even.hpp
[poly-odd]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/polyharmonic_odd.hpp
[cov-base]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/covariance_function_base.hpp
[cov-cubic]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_cubic.hpp
[cov-exp]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_exponential.hpp
[cov-gau]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_gaussian.hpp
[cov-gc3]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_generalized_cauchy3.hpp
[cov-gc5]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_generalized_cauchy5.hpp
[cov-gc7]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_generalized_cauchy7.hpp
[cov-gc9]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_generalized_cauchy9.hpp
[cov-sph]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_spherical.hpp
[cov-sp3]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_spheroidal3.hpp
[cov-sp5]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_spheroidal5.hpp
[cov-sp7]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_spheroidal7.hpp
[cov-sp9]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/cov_spheroidal9.hpp
[model]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/model.hpp
[poly-base]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/polynomial/polynomial_basis_base.hpp
[monomial]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/polynomial/monomial_basis.hpp
[direct-op]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/direct_operator.hpp
[direct-eval]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/direct_evaluator.hpp
[interpolant]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolant.hpp
[fitter]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/fitter.hpp
[incremental-fitter]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/incremental_fitter.hpp
[inequality-fitter]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/inequality_fitter.hpp
[solver]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/solver.hpp
[residual]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/residual_evaluator.hpp
[fgmres]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/fgmres.hpp
[gmres-base]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/krylov/gmres_base.hpp
[fast-op]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/operator.hpp
[fast-eval]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/interpolation/evaluator.hpp
[fmm-eval]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_evaluator.hpp
[fmm-sym]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_symmetric_evaluator.hpp
[fmm-accuracy]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/fmm/fmm_accuracy_estimator.hpp
[ras]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/ras_preconditioner.hpp
[domain-divider]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/domain_divider.hpp
[binary-cache]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/preconditioner/binary_cache.hpp
[detrend]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/detrend.hpp
[variogram-calculator]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/kriging/variogram_calculator.cpp
[variogram-builder]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_builder.hpp
[normal-score]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/normal_score_transformation.hpp
[variogram]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram.hpp
[weight-function]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/weight_function.hpp
[variogram-fitting]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting.hpp
[variogram-fitting-2d]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting_2d.hpp
[variogram-fitting-3d]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_fitting_3d.hpp
[cross-validate]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/cross_validate.hpp
[kdtree]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/kdtree.cpp
[distance-filter]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/point_cloud/distance_filter.hpp
[plane-estimator]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/plane_estimator.cpp
[normal-estimator]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/normal_estimator.cpp
[sdf-generator]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/sdf_data_generator.cpp
[isosurface]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/isosurface/isosurface.hpp
[rbf-field-25d]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/isosurface/rbf_field_function_25d.hpp
[mesh]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/isosurface/mesh.hpp
[common-io]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/common/io.hpp
[rbf-io]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/rbf/rbf_io.hpp
[variogram-set]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/kriging/variogram_set.hpp
[table]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/table.hpp
[conv]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/include/polatory/numeric/conv.hpp
[cli-commands]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/commands.hpp
[cli-main]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/main.cpp
[cli-create-model]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/create_model_command.cpp
[cli-fit]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/fit_command.cpp
[cli-fit-variogram]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/fit_model_to_variogram_command.cpp
[cli-extract-model]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/extract_model_command.cpp
[cli-cross-validate]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/cross_validate_command.cpp
[cli-estimate-normals]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/estimate_normals_command.cpp
[cli-evaluate]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/evaluate_command.cpp
[cli-isosurface]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/isosurface_command.cpp
[cli-normals-sdf]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/normals_to_sdf_command.cpp
[cli-show-model]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/show_model_command.cpp
[cli-show-variogram]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/show_variogram_command.cpp
[cli-surface-25d]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/surface_25d_command.cpp
[cli-unique]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/unique_command.cpp
[cli-variogram]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/cli/variogram_command.cpp
[model-options]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/examples/common/model_options.hpp
[make-model]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/examples/common/make_model.hpp
[python-cmake]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/python/CMakeLists.txt
[python-setup]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/setup.cfg
[python-binding]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/python/python_binding.cpp
[python-init]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/python/src/polatory/__init__.py
[python-test]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/python/tests/test.py
[test-cmake]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/CMakeLists.txt
[test-rbf]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/rbf/test_rbf.cpp
[test-evaluator]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/interpolation/test_evaluator.cpp
[test-operator]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/interpolation/test_operator.cpp
[test-fitter]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/interpolation/test_fitter.cpp
[test-variogram]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/kriging/test_variogram_calculator.cpp
[test-detrend]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/test/kriging/test_detrend.cpp
[benchmark-sh]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/benchmark.sh
[benchmark-points]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/points.cpp
[benchmark-sim]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/benchmark/simulate.R
[random-points]: https://github.com/polatory/polatory/blob/4a30beb08053fb339ce899e255be4b6d3f74aa0c/src/point_cloud/random_points.cpp
[eigen-storage]: https://libeigen.gitlab.io/eigen/docs-3.3/group__TopicStorageOrders.html
[ceres-modeling]: https://ceres-solver.readthedocs.io/latest/nnls_modeling.html
[ceres-solving]: https://ceres-solver.readthedocs.io/latest/nnls_solving.html
[scalfmm-docs]: https://solverstack.gitlabpages.inria.fr/ScalFMM/quickstart.html
[ras-paper]: https://epubs.siam.org/doi/10.1137/S1064827599361771
[carr]: https://www.cs.jhu.edu/~misha/Fall05/Papers/carr01.pdf
[treece]: https://www.sciencedirect.com/science/article/abs/pii/S009784939900076X
