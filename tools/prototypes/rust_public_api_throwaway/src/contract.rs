//! Compileable sketch of the recommended interface.
//!
//! The implementation below is deliberately fake. It exists to compile the
//! proposed shapes and let the terminal explorer exercise their state model.

use std::sync::atomic::{AtomicU64, Ordering};

pub mod execution {
    use super::{AtomicU64, Ordering};
    use std::num::NonZeroUsize;
    use std::path::PathBuf;

    #[derive(Debug)]
    pub struct Context {
        limits: ContextLimits,
        next_identity: AtomicU64,
    }

    #[derive(Clone, Debug)]
    pub struct ContextLimits {
        pub workers: NonZeroUsize,
        pub max_live_threads: NonZeroUsize,
        pub memory_bytes: u64,
        pub scratch_bytes: u64,
    }

    #[derive(Clone, Debug)]
    pub struct CallControl {
        pub grant: ResourceGrant,
        pub accuracy: ChannelAccuracy,
        pub deadline_millis: Option<u64>,
        pub cancellation: CancellationToken,
    }

    #[derive(Clone, Debug)]
    pub struct ResourceGrant {
        pub workers: NonZeroUsize,
        pub max_live_threads: NonZeroUsize,
        pub memory_bytes: u64,
        pub scratch_bytes: u64,
        pub scratch_root: Option<PathBuf>,
        pub max_iterations: u64,
        pub max_work: u64,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum Accuracy {
        DefaultV1,
        Absolute(PositiveF64),
    }

    #[derive(Clone, Copy, Debug)]
    pub struct ChannelAccuracy {
        pub values: Option<Accuracy>,
        pub gradients: Option<Accuracy>,
    }

    #[derive(Clone, Copy, Debug)]
    pub struct PositiveF64(f64);

    #[derive(Clone, Debug, Default)]
    pub struct CancellationToken {
        cancelled: bool,
    }

    #[derive(Clone, Debug)]
    pub struct Report {
        pub schema: &'static str,
        pub operation: &'static str,
        pub routing_profile: &'static str,
        pub workload_class: &'static str,
        pub requested_accuracy: &'static str,
        pub achieved_accuracy: Option<f64>,
        pub configured_workers: usize,
        pub effective_workers: usize,
        pub maximum_live_threads: usize,
        pub memory_high_water_bytes: u64,
        pub scratch_high_water_bytes: u64,
        pub work_used: u64,
        pub trace_truncated: bool,
    }

    #[derive(Clone, Debug)]
    pub struct Completed<T> {
        pub value: T,
        pub report: Report,
    }

    impl Context {
        pub fn new(limits: ContextLimits) -> Result<Self, &'static str> {
            if limits.workers > limits.max_live_threads {
                return Err("workers cannot exceed max_live_threads");
            }
            Ok(Self {
                limits,
                next_identity: AtomicU64::new(1),
            })
        }

        pub(crate) fn allocate_identity(&self) -> u64 {
            self.next_identity.fetch_add(1, Ordering::Relaxed)
        }

        pub(crate) fn report(
            &self,
            operation: &'static str,
            workload_class: &'static str,
            control: &CallControl,
            achieved_accuracy: Option<f64>,
            work_used: u64,
        ) -> Report {
            Report {
                schema: "RapidRBF/OperationReport/v1",
                operation,
                routing_profile: "RapidRBF/SolverRoutingProfile/v1",
                workload_class,
                requested_accuracy: match (control.accuracy.values, control.accuracy.gradients) {
                    (Some(Accuracy::Absolute(_)), Some(Accuracy::Absolute(_))) => {
                        "absolute(value,gradient)"
                    }
                    (Some(Accuracy::Absolute(_)), _) => "absolute(value)",
                    (_, Some(Accuracy::Absolute(_))) => "absolute(gradient)",
                    _ => "DefaultAccuracyProfile/v1",
                },
                achieved_accuracy,
                configured_workers: control.grant.workers.get(),
                effective_workers: control.grant.workers.get(),
                maximum_live_threads: control.grant.max_live_threads.get(),
                memory_high_water_bytes: control.grant.memory_bytes.min(16 * 1024 * 1024),
                scratch_high_water_bytes: 0,
                work_used,
                trace_truncated: false,
            }
        }

        pub fn limits(&self) -> &ContextLimits {
            &self.limits
        }
    }

    impl PositiveF64 {
        pub fn new(value: f64) -> Result<Self, &'static str> {
            if value.is_finite() && value > 0.0 {
                Ok(Self(value))
            } else {
                Err("expected a finite positive number")
            }
        }

        pub fn get(self) -> f64 {
            self.0
        }
    }

    impl CancellationToken {
        pub fn cancel(&mut self) {
            self.cancelled = true;
        }

        pub fn is_cancelled(&self) -> bool {
            self.cancelled
        }
    }

    impl CallControl {
        pub fn named_v1() -> Self {
            let workers = NonZeroUsize::new(4).expect("constant is non-zero");
            let max_live_threads = NonZeroUsize::new(8).expect("constant is non-zero");
            Self {
                grant: ResourceGrant {
                    workers,
                    max_live_threads,
                    memory_bytes: 512 * 1024 * 1024,
                    scratch_bytes: 2 * 1024 * 1024 * 1024,
                    scratch_root: None,
                    max_iterations: 2_000,
                    max_work: 10_000_000,
                },
                accuracy: ChannelAccuracy {
                    values: Some(Accuracy::DefaultV1),
                    gradients: None,
                },
                deadline_millis: None,
                cancellation: CancellationToken::default(),
            }
        }
    }
}

pub mod error {
    use super::execution::Report;

    #[derive(Clone, Debug)]
    pub struct Failure {
        pub kind: FailureKind,
        pub stage: Stage,
        pub original_index: Option<usize>,
        pub field_path: Option<&'static str>,
        pub report: Box<Report>,
    }

    #[derive(Clone, Debug)]
    #[non_exhaustive]
    pub enum FailureKind {
        InvalidRequest,
        ConflictingObservation,
        NoObservations,
        UndefinedDerivative,
        NumericalDomain,
        IndeterminateRank,
        UnidentifiableTrend,
        UnidentifiableAnisotropy,
        IncompatibleWarmStart,
        SelectionStalled,
        InfeasibleConstraints,
        NotConverged,
        AccuracyUnattainable,
        NumericalBreakdown,
        DegenerateLevelSet,
        TopologyUnresolved,
        RefinementFailed,
        SnapConflict,
        SnapIncomplete,
        MeshValidityFailed,
        UnsupportedLegacyLayout,
        MalformedLegacyArtifact,
        UnsupportedLegacyVariant,
        InvalidLegacyState,
        IoFailure,
        ResourceExhausted,
        Cancelled,
        DeadlineExceeded,
        InternalFailure,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum Stage {
        Validation,
        Planning,
        Admission,
        Execution,
        Certification,
        Publication,
    }
}

pub mod model {
    #[derive(Clone, Debug)]
    pub struct Model<const D: usize> {
        terms: Vec<RbfTerm<D>>,
        nugget: f64,
        polynomial: PolynomialChoice,
    }

    #[derive(Clone, Debug)]
    pub struct RbfTerm<const D: usize> {
        pub family: KernelFamily,
        pub parameters: KernelParameters,
        pub anisotropy: Anisotropy<D>,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum KernelFamily {
        Bh2,
        Bh3,
        Th2,
        Th3,
        Cub,
        Exp,
        Gau,
        Gc3,
        Gc5,
        Gc7,
        Gc9,
        Sph,
        Sp3,
        Sp5,
        Sp7,
        Sp9,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum KernelParameters {
        Polyharmonic { scale: f64, c: f64 },
        Covariance { psill: f64, range: f64 },
    }

    #[derive(Clone, Debug)]
    pub struct Anisotropy<const D: usize> {
        matrix: [[f64; D]; D],
    }

    #[derive(Clone, Copy, Debug)]
    pub enum PolynomialChoice {
        None,
        Auto,
        Degree(PolynomialDegree),
    }

    #[derive(Clone, Copy, Debug)]
    pub enum PolynomialDegree {
        Zero,
        One,
        Two,
    }

    #[derive(Debug)]
    pub struct ModelBuilder<const D: usize> {
        terms: Vec<RbfTerm<D>>,
        nugget: f64,
        polynomial: PolynomialChoice,
    }

    impl<const D: usize> Anisotropy<D> {
        pub fn identity() -> Self {
            let mut matrix = [[0.0; D]; D];
            for (index, row) in matrix.iter_mut().enumerate() {
                row[index] = 1.0;
            }
            Self { matrix }
        }

        pub fn try_new(matrix: [[f64; D]; D]) -> Result<Self, &'static str> {
            if !(1..=3).contains(&D) || matrix.iter().flatten().any(|v| !v.is_finite()) {
                return Err("anisotropy must be finite in dimension 1..=3");
            }
            Ok(Self { matrix })
        }

        pub fn matrix(&self) -> &[[f64; D]; D] {
            &self.matrix
        }
    }

    impl<const D: usize> RbfTerm<D> {
        pub fn polyharmonic(
            family: KernelFamily,
            scale: f64,
            c: f64,
            anisotropy: Anisotropy<D>,
        ) -> Result<Self, &'static str> {
            if !scale.is_finite() || scale < 0.0 || !c.is_finite() || c < 0.0 {
                return Err("polyharmonic parameters must be finite and non-negative");
            }
            Ok(Self {
                family,
                parameters: KernelParameters::Polyharmonic { scale, c },
                anisotropy,
            })
        }

        pub fn covariance(
            family: KernelFamily,
            psill: f64,
            range: f64,
            anisotropy: Anisotropy<D>,
        ) -> Result<Self, &'static str> {
            if !psill.is_finite() || psill < 0.0 || !range.is_finite() || range <= 0.0 {
                return Err("covariance psill must be non-negative and range positive");
            }
            Ok(Self {
                family,
                parameters: KernelParameters::Covariance { psill, range },
                anisotropy,
            })
        }
    }

    impl<const D: usize> Model<D> {
        pub fn builder() -> ModelBuilder<D> {
            ModelBuilder {
                terms: Vec::new(),
                nugget: 0.0,
                polynomial: PolynomialChoice::Auto,
            }
        }

        pub fn term_count(&self) -> usize {
            self.terms.len()
        }

        pub fn nugget(&self) -> f64 {
            self.nugget
        }

        pub fn polynomial(&self) -> PolynomialChoice {
            self.polynomial
        }
    }

    impl<const D: usize> ModelBuilder<D> {
        pub fn term(mut self, term: RbfTerm<D>) -> Self {
            self.terms.push(term);
            self
        }

        pub fn nugget(mut self, nugget: f64) -> Self {
            self.nugget = nugget;
            self
        }

        pub fn polynomial(mut self, polynomial: PolynomialChoice) -> Self {
            self.polynomial = polynomial;
            self
        }

        pub fn build(self) -> Result<Model<D>, &'static str> {
            if !(1..=3).contains(&D) {
                return Err("RapidRBF supports dimensions 1..=3");
            }
            if self.terms.is_empty() {
                return Err("a Model contains at least one RBF term");
            }
            if !self.nugget.is_finite() || self.nugget < 0.0 {
                return Err("nugget must be finite and non-negative");
            }
            Ok(Model {
                terms: self.terms,
                nugget: self.nugget,
                polynomial: self.polynomial,
            })
        }
    }
}

pub mod interpolation {
    use super::error::{Failure, FailureKind, Stage};
    use super::execution::{CallControl, Completed, Context};
    use super::model::Model;

    #[derive(Clone, Copy, Debug)]
    pub struct ValueObservation<const D: usize> {
        pub point: [f64; D],
        pub value: f64,
    }

    #[derive(Clone, Copy, Debug)]
    pub struct FullGradientObservation<const D: usize> {
        pub point: [f64; D],
        pub gradient: [f64; D],
    }

    #[derive(Clone, Copy, Debug)]
    pub struct ValueConstraint<const D: usize> {
        pub point: [f64; D],
        pub lower: Option<f64>,
        pub upper: Option<f64>,
    }

    #[derive(Clone, Copy, Debug)]
    pub struct ObservationsRef<'a, const D: usize> {
        pub values: &'a [ValueObservation<D>],
        pub full_gradients: &'a [FullGradientObservation<D>],
    }

    #[derive(Clone, Copy, Debug)]
    pub enum FitKind {
        Ordinary,
        Incremental,
    }

    #[derive(Clone, Copy, Debug)]
    pub struct FitTolerances {
        pub value: Option<f64>,
        pub gradient: Option<f64>,
        pub side_condition: f64,
        pub rank: f64,
    }

    #[derive(Clone, Debug)]
    pub struct Interpolant<const D: usize> {
        identity: u64,
        model: Model<D>,
        observations: usize,
        provenance: &'static str,
    }

    #[derive(Clone, Debug)]
    pub struct ValueBatch {
        pub values: Vec<f64>,
    }

    #[derive(Clone, Debug)]
    pub struct ValueGradientBatch<const D: usize> {
        pub values: Vec<f64>,
        pub gradients: Vec<[f64; D]>,
    }

    pub struct Fit<'a, const D: usize> {
        model: &'a Model<D>,
        observations: ObservationsRef<'a, D>,
        kind: FitKind,
        tolerances: FitTolerances,
        warm_start: Option<&'a Interpolant<D>>,
        simulate_failure: bool,
    }

    pub struct InequalityFit<'a, const D: usize> {
        model: &'a Model<D>,
        constraints: &'a [ValueConstraint<D>],
        value_tolerance: f64,
        kkt_tolerance: f64,
    }

    pub struct EvaluateValues<'a, const D: usize> {
        source: &'a Interpolant<D>,
        targets: &'a [[f64; D]],
    }

    pub struct EvaluateValuesAndGradients<'a, const D: usize> {
        source: &'a Interpolant<D>,
        targets: &'a [[f64; D]],
    }

    impl FitTolerances {
        pub fn named_v1() -> Self {
            Self {
                value: Some(2.0_f64.powi(-24)),
                gradient: Some(2.0_f64.powi(-20)),
                side_condition: 2.0_f64.powi(-24),
                rank: f64::EPSILON * 64.0,
            }
        }
    }

    impl<'a, const D: usize> Fit<'a, D> {
        pub fn ordinary(model: &'a Model<D>, observations: ObservationsRef<'a, D>) -> Self {
            Self {
                model,
                observations,
                kind: FitKind::Ordinary,
                tolerances: FitTolerances::named_v1(),
                warm_start: None,
                simulate_failure: false,
            }
        }

        pub fn incremental(model: &'a Model<D>, observations: ObservationsRef<'a, D>) -> Self {
            Self {
                kind: FitKind::Incremental,
                ..Self::ordinary(model, observations)
            }
        }

        pub fn tolerances(mut self, tolerances: FitTolerances) -> Self {
            self.tolerances = tolerances;
            self
        }

        pub fn warm_start(mut self, warm_start: &'a Interpolant<D>) -> Self {
            self.warm_start = Some(warm_start);
            self
        }

        pub fn simulate_failure(mut self) -> Self {
            self.simulate_failure = true;
            self
        }

        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<Interpolant<D>>, Failure> {
            let count = self.observations.values.len() + self.observations.full_gradients.len();
            let report = context.report(
                "interpolation.fit",
                match self.kind {
                    FitKind::Ordinary => "ordinary-or-value-dominated",
                    FitKind::Incremental => "incremental",
                },
                control,
                None,
                count as u64 * 10,
            );
            if count == 0 {
                return Err(Failure {
                    kind: FailureKind::NoObservations,
                    stage: Stage::Validation,
                    original_index: None,
                    field_path: Some("observations"),
                    report: Box::new(report),
                });
            }
            if self.simulate_failure {
                return Err(Failure {
                    kind: FailureKind::NotConverged,
                    stage: Stage::Certification,
                    original_index: None,
                    field_path: None,
                    report: Box::new(report),
                });
            }
            let provenance = match (self.kind, self.warm_start.is_some()) {
                (FitKind::Ordinary, false) => "ordinary",
                (FitKind::Ordinary, true) => "ordinary-warm",
                (FitKind::Incremental, false) => "incremental",
                (FitKind::Incremental, true) => "incremental-warm",
            };
            let _ = self.tolerances;
            Ok(Completed {
                value: Interpolant {
                    identity: context.allocate_identity(),
                    model: self.model.clone(),
                    observations: count,
                    provenance,
                },
                report,
            })
        }
    }

    impl<'a, const D: usize> InequalityFit<'a, D> {
        pub fn new(model: &'a Model<D>, constraints: &'a [ValueConstraint<D>]) -> Self {
            Self {
                model,
                constraints,
                value_tolerance: 2.0_f64.powi(-24),
                kkt_tolerance: 2.0_f64.powi(-24),
            }
        }

        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<Interpolant<D>>, Failure> {
            let report = context.report(
                "interpolation.fit_inequality",
                "inequality",
                control,
                None,
                self.constraints.len() as u64 * 20,
            );
            if self.constraints.is_empty() {
                return Err(Failure {
                    kind: FailureKind::NoObservations,
                    stage: Stage::Validation,
                    original_index: None,
                    field_path: Some("constraints"),
                    report: Box::new(report),
                });
            }
            let _ = (self.value_tolerance, self.kkt_tolerance);
            Ok(Completed {
                value: Interpolant {
                    identity: context.allocate_identity(),
                    model: self.model.clone(),
                    observations: self.constraints.len(),
                    provenance: "inequality",
                },
                report,
            })
        }
    }

    impl<const D: usize> Interpolant<D> {
        pub fn identity(&self) -> u64 {
            self.identity
        }

        pub fn model(&self) -> &Model<D> {
            &self.model
        }

        pub fn observation_count(&self) -> usize {
            self.observations
        }

        pub fn provenance(&self) -> &'static str {
            self.provenance
        }

        pub fn evaluate_values<'a>(&'a self, targets: &'a [[f64; D]]) -> EvaluateValues<'a, D> {
            EvaluateValues {
                source: self,
                targets,
            }
        }

        pub fn evaluate_values_and_gradients<'a>(
            &'a self,
            targets: &'a [[f64; D]],
        ) -> EvaluateValuesAndGradients<'a, D> {
            EvaluateValuesAndGradients {
                source: self,
                targets,
            }
        }
    }

    impl<const D: usize> EvaluateValues<'_, D> {
        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<ValueBatch>, Failure> {
            let _ = self.source;
            Ok(Completed {
                value: ValueBatch {
                    values: vec![0.0; self.targets.len()],
                },
                report: context.report(
                    "interpolation.evaluate_values",
                    "pre-execution-selected",
                    control,
                    Some(2.0_f64.powi(-28)),
                    self.targets.len() as u64,
                ),
            })
        }
    }

    impl<const D: usize> EvaluateValuesAndGradients<'_, D> {
        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<ValueGradientBatch<D>>, Failure> {
            let _ = self.source;
            Ok(Completed {
                value: ValueGradientBatch {
                    values: vec![0.0; self.targets.len()],
                    gradients: vec![[0.0; D]; self.targets.len()],
                },
                report: context.report(
                    "interpolation.evaluate_values_and_gradients",
                    "pre-execution-selected",
                    control,
                    Some(2.0_f64.powi(-24)),
                    self.targets.len() as u64 * (D as u64 + 1),
                ),
            })
        }
    }
}

pub mod kriging {
    use super::error::{Failure, FailureKind, Stage};
    use super::execution::{CallControl, Completed, Context};
    use super::interpolation::ValueObservation;

    #[derive(Clone, Debug)]
    pub struct VariogramSet<const D: usize> {
        pub dimension: usize,
        pub bins: usize,
        marker: std::marker::PhantomData<[[f64; D]; 0]>,
    }

    pub struct ExperimentalVariogram<'a, const D: usize> {
        samples: &'a [ValueObservation<D>],
        lag_width: f64,
        num_lags: usize,
    }

    impl<'a, const D: usize> ExperimentalVariogram<'a, D> {
        pub fn new(samples: &'a [ValueObservation<D>]) -> Self {
            Self {
                samples,
                lag_width: 1.0,
                num_lags: 10,
            }
        }

        pub fn lag_lattice(mut self, width: f64, num_lags: usize) -> Self {
            self.lag_width = width;
            self.num_lags = num_lags;
            self
        }

        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<VariogramSet<D>>, Failure> {
            let report = context.report(
                "kriging.experimental_variogram",
                "quadratic-pair",
                control,
                Some(2.0_f64.powi(-28)),
                (self.samples.len() * self.samples.len()) as u64,
            );
            if self.samples.len() < 2 {
                return Err(Failure {
                    kind: FailureKind::InvalidRequest,
                    stage: Stage::Validation,
                    original_index: None,
                    field_path: Some("samples"),
                    report: Box::new(report),
                });
            }
            let _ = self.lag_width;
            Ok(Completed {
                value: VariogramSet {
                    dimension: D,
                    bins: self.num_lags.min(self.samples.len()),
                    marker: std::marker::PhantomData,
                },
                report,
            })
        }
    }
}

pub mod geometry {
    use super::error::Failure;
    use super::execution::{CallControl, Completed, Context};
    use super::interpolation::Interpolant;

    #[derive(Clone, Debug)]
    pub struct FieldBatch<const D: usize> {
        pub values: Vec<f64>,
        pub gradients: Vec<[f64; D]>,
    }

    #[derive(Clone, Copy, Debug)]
    pub struct Cell<const D: usize> {
        pub min: [f64; D],
        pub max: [f64; D],
    }

    #[derive(Clone, Copy, Debug)]
    pub struct FieldEnclosure {
        pub value_min: f64,
        pub value_max: f64,
        pub gradient_norm_max: f64,
        pub evaluator_error: f64,
    }

    pub trait CertifiedField<const D: usize>: Send + Sync {
        fn evaluate(&self, points: &[[f64; D]]) -> Result<FieldBatch<D>, &'static str>;
        fn enclose(&self, cells: &[Cell<D>]) -> Result<Vec<FieldEnclosure>, &'static str>;
    }

    #[derive(Clone, Debug)]
    pub enum NormalState {
        Estimated([f64; 3]),
        UnresolvedNormal,
        RejectedNormal,
        AmbiguousOrientation,
    }

    #[derive(Clone, Debug)]
    pub struct SignedDistanceSampleSet {
        pub source_rows: usize,
        pub generated_rows: usize,
    }

    #[derive(Clone, Debug)]
    pub struct PointCloudResult {
        pub normals: Vec<NormalState>,
        pub sdf: SignedDistanceSampleSet,
    }

    #[derive(Clone, Debug)]
    pub enum SurfaceState {
        Surface(Mesh),
        Empty,
        Entire,
    }

    #[derive(Clone, Debug)]
    pub struct Mesh {
        pub vertices: Vec<[f64; 3]>,
        pub faces: Vec<[u32; 3]>,
    }

    pub struct PointCloudWorkflow<'a> {
        points: &'a [[f64; 3]],
    }

    pub struct ExtractSurface<'a> {
        field: &'a dyn CertifiedField<3>,
        bbox: Cell<3>,
        isovalue: f64,
    }

    impl<const D: usize> CertifiedField<D> for Interpolant<D> {
        fn evaluate(&self, points: &[[f64; D]]) -> Result<FieldBatch<D>, &'static str> {
            Ok(FieldBatch {
                values: vec![0.0; points.len()],
                gradients: vec![[0.0; D]; points.len()],
            })
        }

        fn enclose(&self, cells: &[Cell<D>]) -> Result<Vec<FieldEnclosure>, &'static str> {
            Ok(cells
                .iter()
                .map(|_| FieldEnclosure {
                    value_min: -1.0,
                    value_max: 1.0,
                    gradient_norm_max: 1.0,
                    evaluator_error: 2.0_f64.powi(-28),
                })
                .collect())
        }
    }

    impl<'a> PointCloudWorkflow<'a> {
        pub fn new(points: &'a [[f64; 3]]) -> Self {
            Self { points }
        }

        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<PointCloudResult>, Failure> {
            Ok(Completed {
                value: PointCloudResult {
                    normals: self
                        .points
                        .iter()
                        .map(|_| NormalState::Estimated([0.0, 0.0, 1.0]))
                        .collect(),
                    sdf: SignedDistanceSampleSet {
                        source_rows: self.points.len(),
                        generated_rows: self.points.len() * 3,
                    },
                },
                report: context.report(
                    "geometry.point_cloud_to_sdf",
                    "point-cloud",
                    control,
                    Some(2.0_f64.powi(-24)),
                    self.points.len() as u64 * 8,
                ),
            })
        }
    }

    impl<'a> ExtractSurface<'a> {
        pub fn new(field: &'a dyn CertifiedField<3>, bbox: Cell<3>, isovalue: f64) -> Self {
            Self {
                field,
                bbox,
                isovalue,
            }
        }

        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<SurfaceState>, Failure> {
            let _proof = self
                .field
                .enclose(&[self.bbox])
                .expect("prototype interpolant field supplies an enclosure");
            let _ = self.isovalue;
            Ok(Completed {
                value: SurfaceState::Surface(Mesh {
                    vertices: vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    faces: vec![[0, 1, 2]],
                }),
                report: context.report(
                    "geometry.extract_surface",
                    "certified-surface",
                    control,
                    Some(2.0_f64.powi(-20)),
                    64,
                ),
            })
        }
    }
}

pub mod artifact {
    use super::error::Failure;
    use super::execution::{CallControl, Completed, Context};
    use super::interpolation::Interpolant;
    use super::kriging::VariogramSet;
    use super::model::Model;
    use std::path::Path;

    pub enum ArtifactRef<'a, const D: usize> {
        Model(&'a Model<D>),
        Interpolant(&'a Interpolant<D>),
        VariogramSet(&'a VariogramSet<D>),
    }

    #[derive(Clone, Debug)]
    pub struct SaveReceipt {
        pub logical_kind: &'static str,
        pub schema_owner: &'static str,
        pub atomic_replace: bool,
    }

    pub struct SavePortable<'a, const D: usize> {
        artifact: ArtifactRef<'a, D>,
        destination: &'a Path,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum LegacyKind {
        Model,
        FittedInterpolant,
    }

    #[derive(Clone, Debug)]
    pub struct LegacyDeclaration {
        pub kind: LegacyKind,
        pub dimension: usize,
        pub layout_profile: &'static str,
    }

    impl<'a, const D: usize> SavePortable<'a, D> {
        pub fn new(artifact: ArtifactRef<'a, D>, destination: &'a Path) -> Self {
            Self {
                artifact,
                destination,
            }
        }

        pub fn run(
            self,
            context: &Context,
            control: &CallControl,
        ) -> Result<Completed<SaveReceipt>, Failure> {
            let logical_kind = match self.artifact {
                ArtifactRef::Model(_) => "Model",
                ArtifactRef::Interpolant(_) => "Interpolant",
                ArtifactRef::VariogramSet(_) => "VariogramSet",
            };
            let _ = self.destination;
            Ok(Completed {
                value: SaveReceipt {
                    logical_kind,
                    schema_owner: "portable artifact schema ticket",
                    atomic_replace: true,
                },
                report: context.report(
                    "artifact.save_portable",
                    "logical-artifact",
                    control,
                    None,
                    1,
                ),
            })
        }
    }
}

/// Executes every major workflow against the mock implementation. The terminal
/// calls this once so the displayed interface is known to be runnable.
pub fn compile_walkthrough() -> Result<(), String> {
    use artifact::{ArtifactRef, LegacyDeclaration, LegacyKind, SavePortable};
    use execution::{CallControl, Context, ContextLimits};
    use geometry::{Cell, ExtractSurface, PointCloudWorkflow};
    use interpolation::{Fit, ObservationsRef, ValueObservation};
    use kriging::ExperimentalVariogram;
    use model::{Anisotropy, KernelFamily, Model, RbfTerm};
    use std::num::NonZeroUsize;
    use std::path::Path;

    let context = Context::new(ContextLimits {
        workers: NonZeroUsize::new(4).expect("constant is non-zero"),
        max_live_threads: NonZeroUsize::new(8).expect("constant is non-zero"),
        memory_bytes: 512 * 1024 * 1024,
        scratch_bytes: 2 * 1024 * 1024 * 1024,
    })
    .map_err(str::to_owned)?;
    let control = CallControl::named_v1();
    let term = RbfTerm::polyharmonic(KernelFamily::Th3, 1.0, 0.1, Anisotropy::<3>::identity())
        .map_err(str::to_owned)?;
    let model = Model::<3>::builder()
        .term(term)
        .build()
        .map_err(str::to_owned)?;
    let values = [
        ValueObservation {
            point: [0.0, 0.0, 0.0],
            value: 0.0,
        },
        ValueObservation {
            point: [1.0, 0.0, 0.0],
            value: 1.0,
        },
    ];
    let observations = ObservationsRef {
        values: &values,
        full_gradients: &[],
    };
    let fitted = Fit::ordinary(&model, observations)
        .run(&context, &control)
        .map_err(|failure| format!("{failure:?}"))?
        .value;
    fitted
        .evaluate_values(&[[0.5, 0.0, 0.0]])
        .run(&context, &control)
        .map_err(|failure| format!("{failure:?}"))?;
    ExperimentalVariogram::new(&values)
        .run(&context, &control)
        .map_err(|failure| format!("{failure:?}"))?;
    PointCloudWorkflow::new(&[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        .run(&context, &control)
        .map_err(|failure| format!("{failure:?}"))?;
    ExtractSurface::new(
        &fitted,
        Cell {
            min: [0.0, 0.0, 0.0],
            max: [1.0, 1.0, 1.0],
        },
        0.0,
    )
    .run(&context, &control)
    .map_err(|failure| format!("{failure:?}"))?;
    SavePortable::new(
        ArtifactRef::Interpolant(&fitted),
        Path::new("PROTOTYPE-do-not-write.rrbf"),
    )
    .run(&context, &control)
    .map_err(|failure| format!("{failure:?}"))?;
    let _legacy = LegacyDeclaration {
        kind: LegacyKind::FittedInterpolant,
        dimension: 3,
        layout_profile: "polatory-native64-le-v1",
    };
    Ok(())
}
