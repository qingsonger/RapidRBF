//! Pure reducer for the terminal explorer.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DesignVariant {
    MinimalEnvelope,
    ExtensiblePlan,
    StudyFacade,
    DomainWorkflowHybrid,
}

#[derive(Clone, Copy, Debug)]
pub enum Action {
    Select(DesignVariant),
    BuildModel,
    FitOrdinary,
    FitIncremental,
    FitInequality,
    EvaluateValues,
    EvaluateValuesAndGradients,
    RunVariogram,
    RunPointCloud,
    ExtractSurface,
    SavePortable,
    ImportLegacy,
    ForceFailedRefit,
    Reset,
}

#[derive(Clone, Debug)]
pub struct ExplorerState {
    pub variant: DesignVariant,
    pub model: Option<&'static str>,
    pub interpolant_identity: Option<u64>,
    pub interpolant_provenance: Option<&'static str>,
    pub preserved_identity: Option<u64>,
    pub artifact: Option<&'static str>,
    pub last_operation: &'static str,
    pub last_call: &'static str,
    pub outcome: &'static str,
    pub report: ReportState,
    next_identity: u64,
}

#[derive(Clone, Debug)]
pub struct ReportState {
    pub routing_profile: &'static str,
    pub workload_class: &'static str,
    pub requested_accuracy: &'static str,
    pub achieved_accuracy: &'static str,
    pub resources: &'static str,
    pub atomic_publication: bool,
}

impl DesignVariant {
    pub fn name(self) -> &'static str {
        match self {
            Self::MinimalEnvelope => "1 · Minimal Engine::run envelope",
            Self::ExtensiblePlan => "2 · Extensible public Plan",
            Self::StudyFacade => "3 · Common-caller Study facade",
            Self::DomainWorkflowHybrid => "4 · Recommended domain-workflow hybrid",
        }
    }

    pub fn interface(self) -> &'static str {
        match self {
            Self::MinimalEnvelope => "Engine::run(O: sealed Operation)",
            Self::ExtensiblePlan => "Engine::plan(O, control)?.execute()",
            Self::StudyFacade => "Study<D>.fit()/variogram()/geometry()",
            Self::DomainWorkflowHybrid => "DomainJob::run(&Context, CallControl)",
        }
    }

    pub fn depth(self) -> &'static str {
        match self {
            Self::MinimalEnvelope => "Highest shared execution leverage; wide operation vocabulary",
            Self::ExtensiblePlan => "High additive leverage; planning becomes public knowledge",
            Self::StudyFacade => "Excellent happy path; shallow for mixed domain lifetimes",
            Self::DomainWorkflowHybrid => {
                "Shared private engine plus discoverable domain interfaces"
            }
        }
    }

    pub fn seam(self) -> &'static str {
        match self {
            Self::MinimalEnvelope => "All extension sealed; custom certified fields excluded",
            Self::ExtensiblePlan => "Public Plan plus CertifiedField",
            Self::StudyFacade => "Private routes hidden behind Study jobs",
            Self::DomainWorkflowHybrid => "Private route adapters; public CertifiedField only",
        }
    }
}

impl Default for ExplorerState {
    fn default() -> Self {
        Self {
            variant: DesignVariant::DomainWorkflowHybrid,
            model: None,
            interpolant_identity: None,
            interpolant_provenance: None,
            preserved_identity: None,
            artifact: None,
            last_operation: "prototype.start",
            last_call: "Select a design or build a Model<3>.",
            outcome: "READY — compiled contract walkthrough passed",
            report: ReportState::idle(),
            next_identity: 1,
        }
    }
}

impl ReportState {
    fn idle() -> Self {
        Self {
            routing_profile: "RapidRBF/SolverRoutingProfile/v1",
            workload_class: "not planned",
            requested_accuracy: "DefaultAccuracyProfile/v1",
            achieved_accuracy: "not executed",
            resources: "4 workers · max 8 live threads · 512 MiB",
            atomic_publication: true,
        }
    }

    fn success(workload_class: &'static str, achieved_accuracy: &'static str) -> Self {
        Self {
            workload_class,
            achieved_accuracy,
            ..Self::idle()
        }
    }
}

pub fn reduce(mut state: ExplorerState, action: Action) -> ExplorerState {
    match action {
        Action::Select(variant) => {
            state.variant = variant;
            state.last_operation = "design.select";
            state.last_call = variant.interface();
            state.outcome = "DESIGN SELECTED — compare Depth, Locality, and Seam placement";
            state.report = ReportState::idle();
        }
        Action::BuildModel => {
            state.model = Some("Model<3> · th3(scale=1,c=0.1) · identity A · AUTO degree");
            state.last_operation = "model.build";
            state.last_call = "Model::<3>::builder().term(RbfTerm::th3(...)).build()?";
            state.outcome = "SUCCESS — canonical immutable Model<3>";
            state.report = ReportState::success("model-validation", "exact discrete semantics");
        }
        Action::FitOrdinary => fit(
            &mut state,
            "ordinary",
            "Fit::ordinary(&model, observations)",
        ),
        Action::FitIncremental => {
            fit(
                &mut state,
                "incremental",
                "Fit::incremental(&model, observations)",
            );
        }
        Action::FitInequality => {
            fit(
                &mut state,
                "inequality",
                "InequalityFit::new(&model, constraints)",
            );
        }
        Action::EvaluateValues => {
            evaluate(
                &mut state,
                "interpolation.evaluate_values",
                "interpolant.evaluate_values(targets).run(&context, &control)",
                "2^-28 value bound",
            );
        }
        Action::EvaluateValuesAndGradients => {
            evaluate(
                &mut state,
                "interpolation.evaluate_values_and_gradients",
                "interpolant.evaluate_values_and_gradients(targets).run(...)",
                "2^-24 value/gradient bound",
            );
        }
        Action::RunVariogram => {
            state.last_operation = "kriging.experimental_variogram";
            state.last_call = "ExperimentalVariogram::new(samples).lag_lattice(...).run(...)";
            state.outcome = "SUCCESS — logical VariogramSet<3>, exact membership/counts";
            state.report = ReportState::success("quadratic-pair variogram", "2^-28 bin means");
        }
        Action::RunPointCloud => {
            state.last_operation = "geometry.point_cloud_to_sdf";
            state.last_call = "PointCloudWorkflow::new(points).run(&context, &control)";
            state.outcome = "SUCCESS — explicit normal states + associated SDF samples";
            state.report = ReportState::success("point-cloud/SDF", "certified per-row outcomes");
        }
        Action::ExtractSurface => {
            if state.interpolant_identity.is_none() {
                missing_interpolant(&mut state, "geometry.extract_surface");
            } else {
                state.last_operation = "geometry.extract_surface";
                state.last_call =
                    "ExtractSurface::new(&field, bbox, level).run(&context, &control)";
                state.outcome = "SUCCESS — CertifiedField supplied values + cell enclosures";
                state.report = ReportState::success("certified-surface", "2^-20 geometry profile");
            }
        }
        Action::SavePortable => {
            if state.interpolant_identity.is_none() {
                missing_interpolant(&mut state, "artifact.save_portable");
            } else {
                state.artifact =
                    Some("logical Interpolant only · no backend plan/cache · atomic replace");
                state.last_operation = "artifact.save_portable";
                state.last_call =
                    "SavePortable::new(ArtifactRef::Interpolant(&fit), path).run(...)";
                state.outcome =
                    "SUCCESS — typed surface fixed; byte schema intentionally delegated";
                state.report = ReportState::success("logical-artifact", "schema ticket owns bytes");
            }
        }
        Action::ImportLegacy => {
            let new_identity = state.next_identity;
            state.next_identity += 1;
            state.preserved_identity = state.interpolant_identity;
            state.interpolant_identity = Some(new_identity);
            state.interpolant_provenance = Some("validated-legacy");
            state.last_operation = "artifact.import_legacy";
            state.last_call = "ImportLegacy::<3>::new(source, explicit_declaration).run(...)";
            state.outcome = "SUCCESS — exact logical state validated; fresh runtime plans required";
            state.report =
                ReportState::success("declared legacy layout", "CPD side certificate passed");
        }
        Action::ForceFailedRefit => {
            if let Some(identity) = state.interpolant_identity {
                state.preserved_identity = Some(identity);
                state.last_operation = "interpolation.fit";
                state.last_call =
                    "Fit::ordinary(...).warm_start(&prior).simulate_failure().run(...)";
                state.outcome = "FAILURE NotConverged — prior certified Interpolant unchanged";
                state.report =
                    ReportState::success("pre-execution-selected", "no result published");
            } else {
                missing_interpolant(&mut state, "interpolation.fit");
            }
        }
        Action::Reset => return ExplorerState::default(),
    }
    state
}

fn fit(state: &mut ExplorerState, provenance: &'static str, call: &'static str) {
    if state.model.is_none() {
        state.last_operation = "interpolation.fit";
        state.last_call = call;
        state.outcome = "FAILURE InvalidRequest — build Model<3> first";
        state.report = ReportState::success("validation", "no result published");
        return;
    }
    let new_identity = state.next_identity;
    state.next_identity += 1;
    state.preserved_identity = state.interpolant_identity;
    state.interpolant_identity = Some(new_identity);
    state.interpolant_provenance = Some(provenance);
    state.last_operation = "interpolation.fit";
    state.last_call = call;
    state.outcome = "SUCCESS — new immutable certified Interpolant<3>";
    state.report = ReportState::success(provenance, "complete external certificate");
}

fn evaluate(
    state: &mut ExplorerState,
    operation: &'static str,
    call: &'static str,
    achieved: &'static str,
) {
    if state.interpolant_identity.is_none() {
        missing_interpolant(state, operation);
        return;
    }
    state.last_operation = operation;
    state.last_call = call;
    state.outcome = "SUCCESS — atomic batch preserves target order and duplicates";
    state.report = ReportState::success("pre-execution-selected", achieved);
}

fn missing_interpolant(state: &mut ExplorerState, operation: &'static str) {
    state.last_operation = operation;
    state.last_call = "Requires an immutable fitted or validated-legacy Interpolant<3>.";
    state.outcome = "FAILURE InvalidRequest — no Interpolant<3> exists";
    state.report = ReportState::success("validation", "no result published");
}
