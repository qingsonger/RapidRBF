//! Exact, target-independent execution seam for the issue-42 candidate.
//!
//! This crate materializes only the binding and its preflight/control plane.
//! It deliberately does not execute either frozen feasibility factor.

use rapidrbf_faer_control::{with_observer, AbortKind, Decision, Event, EventKind, Observer};
use std::cell::Cell;
use std::panic::{catch_unwind, resume_unwind, AssertUnwindSafe};
use std::sync::atomic::{AtomicBool, Ordering};

pub const BINDING_SCHEMA: &str = "RapidRBF/InstrumentedFaerCandidateExecutionBinding/v1";
pub const FACTOR_HEALTH_PROFILE_SHA256: &str =
    "00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FactorRole {
    ProjectedB,
    CoarsePTop,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FactorShape {
    pub role: FactorRole,
    pub dimension: usize,
    pub rhs_columns: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ResourceGrant {
    pub transient_bytes: usize,
    pub retained_bytes: usize,
    pub compute_permits: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ResourceSchedule {
    shape: FactorShape,
    pub staged_matrix_bytes: usize,
    pub staged_matrix_alignment: usize,
    pub factor_auxiliary_bytes: usize,
    pub factor_auxiliary_alignment: usize,
    pub solver_stack_bytes: usize,
    pub solver_stack_alignment: usize,
    pub private_gemm_workspace_bytes: usize,
    pub private_gemm_workspace_alignment: usize,
    pub solve_rhs_bytes: usize,
    pub solve_rhs_alignment: usize,
    pub publication_bytes: usize,
    pub peak_transient_bytes: usize,
    pub retained_bytes: usize,
    pub required_compute_permits: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CheckpointKind {
    Pivot,
    Panel,
    Packing,
    MacroKernel,
    Solve,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CheckpointBound {
    pub kind: CheckpointKind,
    pub maximum_unpolled_work_units: usize,
    pub unit: &'static str,
    pub selected_path: &'static str,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PlanError {
    InvalidShape,
    ArithmeticOverflow,
    ResourceDenied,
    BindingMismatch,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExecutionError {
    ResourceDenied,
    Cancelled,
    ContractViolation,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ExecutionMetrics {
    pub transient_high_water_bytes: usize,
    pub transient_residue_bytes: usize,
    pub cumulative_reserved_bytes: usize,
    pub cumulative_released_bytes: usize,
    pub stack_carve_events: usize,
    pub stack_carved_bytes: usize,
    pub checkpoint_events: usize,
    pub backend_entries: usize,
    pub outer_compute_permits_live: usize,
    pub temporary_storage_cumulative_writes: usize,
    pub temporary_storage_residue_bytes: usize,
    pub temporary_storage_open_handles: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CandidateExecutionBinding {
    pub schema: &'static str,
    pub profile_sha256: &'static str,
    pub parallelism: &'static str,
    pub temporary_storage: &'static str,
}

impl CandidateExecutionBinding {
    pub const fn exact() -> Self {
        Self {
            schema: BINDING_SCHEMA,
            profile_sha256: FACTOR_HEALTH_PROFILE_SHA256,
            parallelism: "Par::Seq",
            temporary_storage: "denied-for-two-factor-feasibility",
        }
    }

    pub fn plan(&self, shape: FactorShape) -> Result<ResourceSchedule, PlanError> {
        if self.schema != BINDING_SCHEMA || self.profile_sha256 != FACTOR_HEALTH_PROFILE_SHA256 {
            return Err(PlanError::BindingMismatch);
        }
        if shape.dimension == 0 || shape.rhs_columns == 0 {
            return Err(PlanError::InvalidShape);
        }

        let n = shape.dimension;
        let f64_bytes = std::mem::size_of::<f64>();
        let usize_bytes = std::mem::size_of::<usize>();
        let matrix_elements = n.checked_mul(n).ok_or(PlanError::ArithmeticOverflow)?;
        let staged_matrix_bytes = matrix_elements
            .checked_mul(f64_bytes)
            .ok_or(PlanError::ArithmeticOverflow)?;
        let solve_rhs_bytes = n
            .checked_mul(shape.rhs_columns)
            .and_then(|value| value.checked_mul(f64_bytes))
            .ok_or(PlanError::ArithmeticOverflow)?;

        let factor_auxiliary_bytes = match shape.role {
            FactorRole::ProjectedB => n
                .checked_mul(f64_bytes + 2 * usize_bytes)
                .ok_or(PlanError::ArithmeticOverflow)?,
            FactorRole::CoarsePTop => n
                .checked_mul(4 * usize_bytes)
                .ok_or(PlanError::ArithmeticOverflow)?,
        };

        let (solver_stack_bytes, solver_stack_alignment) = exact_solver_stack_layout(shape)?;
        let (private_gemm_workspace_bytes, private_gemm_workspace_alignment) =
            exact_private_gemm_workspace_layout(shape.role);
        let publication_bytes = staged_matrix_bytes
            .checked_add(factor_auxiliary_bytes)
            .ok_or(PlanError::ArithmeticOverflow)?;

        // Factor and solve reuse the same staged matrix and stack.  The
        // private-gemm workspace can be live during either phase.  Publication
        // is atomic and swaps ownership of the staged factor, so it is not
        // double-counted in the transient peak.
        let peak_transient_bytes = staged_matrix_bytes
            .checked_add(factor_auxiliary_bytes)
            .and_then(|value| value.checked_add(solver_stack_bytes))
            .and_then(|value| value.checked_add(private_gemm_workspace_bytes))
            .and_then(|value| value.checked_add(solve_rhs_bytes))
            .ok_or(PlanError::ArithmeticOverflow)?;

        Ok(ResourceSchedule {
            shape,
            staged_matrix_bytes,
            staged_matrix_alignment: std::mem::align_of::<f64>(),
            factor_auxiliary_bytes,
            factor_auxiliary_alignment: std::mem::align_of::<usize>()
                .max(std::mem::align_of::<f64>()),
            solver_stack_bytes,
            solver_stack_alignment,
            private_gemm_workspace_bytes,
            private_gemm_workspace_alignment,
            solve_rhs_bytes,
            solve_rhs_alignment: std::mem::align_of::<f64>(),
            publication_bytes,
            peak_transient_bytes,
            retained_bytes: publication_bytes,
            required_compute_permits: 1,
        })
    }

    pub fn checkpoint_bounds(&self, shape: FactorShape) -> Result<[CheckpointBound; 5], PlanError> {
        if self.schema != BINDING_SCHEMA || self.profile_sha256 != FACTOR_HEALTH_PROFILE_SHA256 {
            return Err(PlanError::BindingMismatch);
        }
        if shape.dimension == 0 || shape.rhs_columns == 0 {
            return Err(PlanError::InvalidShape);
        }
        let n_squared = shape
            .dimension
            .checked_mul(shape.dimension)
            .ok_or(PlanError::ArithmeticOverflow)?;
        let solve_units = shape
            .dimension
            .checked_mul(shape.rhs_columns)
            .ok_or(PlanError::ArithmeticOverflow)?;
        let (packing_units, macro_kernel_units, matmul_path) = match shape.role {
            FactorRole::ProjectedB => selected_matmul_checkpoint_bounds(),
            FactorRole::CoarsePTop => (0, 0, "not applicable to 4x4 full-pivot LU"),
        };

        Ok([
            CheckpointBound {
                kind: CheckpointKind::Pivot,
                maximum_unpolled_work_units: n_squared,
                unit: "scalar pivot-search/update candidates",
                selected_path: match shape.role {
                    FactorRole::ProjectedB => "faer Bunch-Kaufman LDLT",
                    FactorRole::CoarsePTop => "faer full-pivot LU",
                },
            },
            CheckpointBound {
                kind: CheckpointKind::Panel,
                maximum_unpolled_work_units: match shape.role {
                    FactorRole::ProjectedB => n_squared,
                    FactorRole::CoarsePTop => 0,
                },
                unit: "scalar panel candidates (zero when path has no panel)",
                selected_path: match shape.role {
                    FactorRole::ProjectedB => "faer Bunch-Kaufman LDLT",
                    FactorRole::CoarsePTop => "not applicable",
                },
            },
            CheckpointBound {
                kind: CheckpointKind::Packing,
                maximum_unpolled_work_units: packing_units,
                unit: "scalar elements packed",
                selected_path: matmul_path,
            },
            CheckpointBound {
                kind: CheckpointKind::MacroKernel,
                maximum_unpolled_work_units: macro_kernel_units,
                unit: "scalar multiply-add contributions",
                selected_path: matmul_path,
            },
            CheckpointBound {
                kind: CheckpointKind::Solve,
                maximum_unpolled_work_units: solve_units,
                unit: "matrix elements in one recursive solve region",
                selected_path: match shape.role {
                    FactorRole::ProjectedB => "faer Bunch-Kaufman and triangular solve",
                    FactorRole::CoarsePTop => "faer full-pivot LU and triangular solve",
                },
            },
        ])
    }

    pub fn preflight(
        &self,
        schedule: ResourceSchedule,
        grant: ResourceGrant,
    ) -> Result<(), PlanError> {
        if self.plan(schedule.shape)? != schedule {
            return Err(PlanError::BindingMismatch);
        }
        if grant.compute_permits < schedule.required_compute_permits
            || grant.transient_bytes < schedule.peak_transient_bytes
            || grant.retained_bytes < schedule.retained_bytes
        {
            return Err(PlanError::ResourceDenied);
        }
        Ok(())
    }

    pub fn execute<T>(
        &self,
        schedule: ResourceSchedule,
        lease: &ExecutionLease,
        cancellation: &CancellationToken,
        operation: impl FnOnce() -> T,
    ) -> Result<T, ExecutionError> {
        self.preflight(schedule, lease.grant)
            .map_err(|_| ExecutionError::ResourceDenied)?;
        let permit = lease.acquire_one_permit()?;
        let base_transient = schedule
            .peak_transient_bytes
            .checked_sub(schedule.private_gemm_workspace_bytes)
            .ok_or(ExecutionError::ContractViolation)?;
        lease.reserve_base(base_transient)?;
        let observer = LeaseObserver {
            lease,
            cancellation,
        };
        let result = catch_unwind(AssertUnwindSafe(|| {
            with_observer(&observer, operation).map_err(map_abort)
        }));
        let cleanup = lease.release_base(base_transient);
        drop(permit);
        match (result, cleanup) {
            (_, Err(error)) => Err(error),
            (Ok(result), Ok(())) => result,
            (Err(payload), Ok(())) => resume_unwind(payload),
        }
    }
}

fn exact_solver_stack_layout(shape: FactorShape) -> Result<(usize, usize), PlanError> {
    use faer::Par;

    let request = match shape.role {
        FactorRole::ProjectedB => {
            faer::linalg::cholesky::lblt::factor::cholesky_in_place_scratch::<usize, f64>(
                shape.dimension,
                Par::Seq,
                Default::default(),
            )
        }
        FactorRole::CoarsePTop => {
            faer::linalg::lu::full_pivoting::factor::lu_in_place_scratch::<usize, f64>(
                shape.dimension,
                shape.dimension,
                Par::Seq,
                Default::default(),
            )
        }
    };
    let bytes = request
        .size_bytes()
        .checked_add(request.align_bytes().saturating_sub(1))
        .ok_or(PlanError::ArithmeticOverflow)?;
    Ok((bytes, request.align_bytes()))
}

#[cfg(target_arch = "x86_64")]
fn exact_private_gemm_workspace_layout(role: FactorRole) -> (usize, usize) {
    if role == FactorRole::CoarsePTop {
        // The frozen 4x4 full-pivot LU and its base-case solve never enter a
        // matrix-multiply backend.
        return (0, 1);
    }
    let layout = private_gemm_x86::workspace_layout(
        private_gemm_x86::DType::F64,
        if std::arch::is_x86_feature_detected!("avx512f") {
            private_gemm_x86::InstrSet::Avx512
        } else {
            private_gemm_x86::InstrSet::Avx256
        },
    );
    (layout.bytes, layout.align)
}

#[cfg(not(target_arch = "x86_64"))]
fn exact_private_gemm_workspace_layout(_role: FactorRole) -> (usize, usize) {
    (0, 1)
}

#[cfg(target_arch = "x86_64")]
fn selected_matmul_checkpoint_bounds() -> (usize, usize, &'static str) {
    // f64 AVX-512 is the largest selected x86 route:
    // pack: 48 rows * KC 512; kernel: 48 * 4 * KC 512.
    (48 * 512, 48 * 4 * 512, "private-gemm-x86 f64")
}

#[cfg(target_arch = "aarch64")]
fn selected_matmul_checkpoint_bounds() -> (usize, usize, &'static str) {
    // Apple arm64 f64 uses two SIMD lanes, MR_DIV_N=2, NR=2, KC=128.
    (0, 2 * 2 * 2 * 128, "faer generic Apple arm64 f64")
}

#[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
fn selected_matmul_checkpoint_bounds() -> (usize, usize, &'static str) {
    (0, 2 * 1 * 2 * 128, "faer generic scalar f64")
}

fn map_abort(abort: AbortKind) -> ExecutionError {
    match abort {
        AbortKind::ResourceDenied => ExecutionError::ResourceDenied,
        AbortKind::Cancelled => ExecutionError::Cancelled,
        AbortKind::ContractViolation => ExecutionError::ContractViolation,
    }
}

#[derive(Debug)]
pub struct ExecutionLease {
    grant: ResourceGrant,
    transient_limit: Cell<usize>,
    current_transient: Cell<usize>,
    high_water: Cell<usize>,
    cumulative_reserved: Cell<usize>,
    cumulative_released: Cell<usize>,
    permits: Cell<usize>,
    backend_entries: Cell<usize>,
    stack_carve_events: Cell<usize>,
    stack_carved_bytes: Cell<usize>,
    checkpoint_events: Cell<usize>,
}

impl ExecutionLease {
    pub fn new(grant: ResourceGrant) -> Self {
        Self {
            grant,
            transient_limit: Cell::new(grant.transient_bytes),
            current_transient: Cell::new(0),
            high_water: Cell::new(0),
            cumulative_reserved: Cell::new(0),
            cumulative_released: Cell::new(0),
            permits: Cell::new(0),
            backend_entries: Cell::new(0),
            stack_carve_events: Cell::new(0),
            stack_carved_bytes: Cell::new(0),
            checkpoint_events: Cell::new(0),
        }
    }

    pub fn grant(&self) -> ResourceGrant {
        self.grant
    }

    pub fn metrics(&self) -> ExecutionMetrics {
        ExecutionMetrics {
            transient_high_water_bytes: self.high_water.get(),
            transient_residue_bytes: self.current_transient.get(),
            cumulative_reserved_bytes: self.cumulative_reserved.get(),
            cumulative_released_bytes: self.cumulative_released.get(),
            stack_carve_events: self.stack_carve_events.get(),
            stack_carved_bytes: self.stack_carved_bytes.get(),
            checkpoint_events: self.checkpoint_events.get(),
            backend_entries: self.backend_entries.get(),
            outer_compute_permits_live: self.permits.get(),
            temporary_storage_cumulative_writes: 0,
            temporary_storage_residue_bytes: 0,
            temporary_storage_open_handles: 0,
        }
    }

    fn acquire_one_permit(&self) -> Result<PermitGuard<'_>, ExecutionError> {
        if self.permits.get() != 0 || self.current_transient.get() != 0 {
            return Err(ExecutionError::ContractViolation);
        }
        self.permits.set(1);
        Ok(PermitGuard { lease: self })
    }

    fn reserve_base(&self, bytes: usize) -> Result<(), ExecutionError> {
        if bytes > self.transient_limit.get() {
            return Err(ExecutionError::ResourceDenied);
        }
        let cumulative = self
            .cumulative_reserved
            .get()
            .checked_add(bytes)
            .ok_or(ExecutionError::ContractViolation)?;
        self.current_transient.set(bytes);
        self.high_water.set(self.high_water.get().max(bytes));
        self.cumulative_reserved.set(cumulative);
        Ok(())
    }

    fn release_base(&self, bytes: usize) -> Result<(), ExecutionError> {
        if self.current_transient.get() != bytes {
            return Err(ExecutionError::ContractViolation);
        }
        let cumulative = self
            .cumulative_released
            .get()
            .checked_add(bytes)
            .ok_or(ExecutionError::ContractViolation)?;
        self.current_transient.set(0);
        self.cumulative_released.set(cumulative);
        Ok(())
    }
}

struct PermitGuard<'a> {
    lease: &'a ExecutionLease,
}

impl Drop for PermitGuard<'_> {
    fn drop(&mut self) {
        self.lease.permits.set(0);
    }
}

#[derive(Debug, Default)]
pub struct CancellationToken {
    cancelled: AtomicBool,
}

impl CancellationToken {
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::Acquire)
    }
}

struct LeaseObserver<'a> {
    lease: &'a ExecutionLease,
    cancellation: &'a CancellationToken,
}

impl Observer for LeaseObserver<'_> {
    fn observe(&self, event: Event) -> Decision {
        match event.kind {
            EventKind::ReserveTransient => {
                let Some(next) = self.lease.current_transient.get().checked_add(event.bytes) else {
                    return Decision::Abort(AbortKind::ResourceDenied);
                };
                if next > self.lease.transient_limit.get() {
                    return Decision::Abort(AbortKind::ResourceDenied);
                }
                self.lease.current_transient.set(next);
                self.lease
                    .high_water
                    .set(self.lease.high_water.get().max(next));
                let Some(cumulative) = self
                    .lease
                    .cumulative_reserved
                    .get()
                    .checked_add(event.bytes)
                else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                self.lease.cumulative_reserved.set(cumulative);
            }
            EventKind::ReleaseTransient => {
                let Some(next) = self.lease.current_transient.get().checked_sub(event.bytes) else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                self.lease.current_transient.set(next);
                let Some(cumulative) = self
                    .lease
                    .cumulative_released
                    .get()
                    .checked_add(event.bytes)
                else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                self.lease.cumulative_released.set(cumulative);
            }
            EventKind::BackendEntry => {
                let Some(entries) = self.lease.backend_entries.get().checked_add(1) else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                self.lease.backend_entries.set(entries);
            }
            EventKind::Pivot
            | EventKind::Panel
            | EventKind::Packing
            | EventKind::MacroKernel
            | EventKind::Solve => {
                let Some(checkpoints) = self.lease.checkpoint_events.get().checked_add(1) else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                self.lease.checkpoint_events.set(checkpoints);
                if self.cancellation.cancelled.load(Ordering::Acquire) {
                    return Decision::Abort(AbortKind::Cancelled);
                }
            }
            EventKind::StackCarve => {
                let Some(events) = self.lease.stack_carve_events.get().checked_add(1) else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                let Some(bytes) = self.lease.stack_carved_bytes.get().checked_add(event.bytes)
                else {
                    return Decision::Abort(AbortKind::ContractViolation);
                };
                self.lease.stack_carve_events.set(events);
                self.lease.stack_carved_bytes.set(bytes);
            }
        }
        Decision::Continue
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn projected_b_plan_is_exact_and_n_minus_one_denies_before_entry() {
        let binding = CandidateExecutionBinding::exact();
        let shape = FactorShape {
            role: FactorRole::ProjectedB,
            dimension: 2_047,
            rhs_columns: 1,
        };
        let plan = binding.plan(shape).unwrap();
        assert_eq!(plan.required_compute_permits, 1);
        assert!(plan.private_gemm_workspace_bytes > 0 || !cfg!(target_arch = "x86_64"));
        let mut tampered = plan;
        tampered.peak_transient_bytes -= 1;
        assert_eq!(
            binding.preflight(
                tampered,
                ResourceGrant {
                    transient_bytes: plan.peak_transient_bytes,
                    retained_bytes: plan.retained_bytes,
                    compute_permits: 1,
                },
            ),
            Err(PlanError::BindingMismatch)
        );

        let lease = ExecutionLease::new(ResourceGrant {
            transient_bytes: plan.peak_transient_bytes - 1,
            retained_bytes: plan.retained_bytes,
            compute_permits: 1,
        });
        let cancellation = CancellationToken::default();
        let mut operation_called = false;
        let denied = binding.execute(plan, &lease, &cancellation, || operation_called = true);
        assert_eq!(denied, Err(ExecutionError::ResourceDenied));
        assert!(!operation_called);
        assert_eq!(lease.metrics(), ExecutionMetrics::default());
    }

    #[test]
    fn cancellation_is_typed_and_releases_the_outer_permit() {
        let binding = CandidateExecutionBinding::exact();
        let plan = binding
            .plan(FactorShape {
                role: FactorRole::CoarsePTop,
                dimension: 4,
                rhs_columns: 1,
            })
            .unwrap();
        let lease = ExecutionLease::new(ResourceGrant {
            transient_bytes: plan.peak_transient_bytes,
            retained_bytes: plan.retained_bytes,
            compute_permits: 1,
        });
        let cancellation = CancellationToken::default();
        cancellation.cancel();

        let result = binding.execute(plan, &lease, &cancellation, || {
            rapidrbf_faer_control::checkpoint(EventKind::Solve, 4);
        });
        assert_eq!(result, Err(ExecutionError::Cancelled));
        let metrics = lease.metrics();
        assert_eq!(metrics.outer_compute_permits_live, 0);
        assert_eq!(metrics.transient_residue_bytes, 0);
        assert_eq!(metrics.backend_entries, 0);
        assert_eq!(metrics.checkpoint_events, 1);
        assert_eq!(metrics.cumulative_reserved_bytes, plan.peak_transient_bytes);
        assert_eq!(metrics.cumulative_released_bytes, plan.peak_transient_bytes);
    }

    #[test]
    fn non_control_panic_still_releases_base_reservation_and_permit() {
        let binding = CandidateExecutionBinding::exact();
        let plan = binding
            .plan(FactorShape {
                role: FactorRole::CoarsePTop,
                dimension: 4,
                rhs_columns: 1,
            })
            .unwrap();
        let lease = ExecutionLease::new(ResourceGrant {
            transient_bytes: plan.peak_transient_bytes,
            retained_bytes: plan.retained_bytes,
            compute_permits: 1,
        });
        let cancellation = CancellationToken::default();
        let panic = catch_unwind(AssertUnwindSafe(|| {
            let _ = binding.execute(plan, &lease, &cancellation, || {
                panic!("non-control panic");
            });
        }));
        assert!(panic.is_err());
        let metrics = lease.metrics();
        assert_eq!(metrics.outer_compute_permits_live, 0);
        assert_eq!(metrics.transient_residue_bytes, 0);
        assert_eq!(metrics.cumulative_reserved_bytes, plan.peak_transient_bytes);
        assert_eq!(metrics.cumulative_released_bytes, plan.peak_transient_bytes);
        assert_eq!(metrics.backend_entries, 0);
    }
}
