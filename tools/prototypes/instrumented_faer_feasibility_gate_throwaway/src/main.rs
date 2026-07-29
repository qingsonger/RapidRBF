//! THROWAWAY PROTOTYPE: execute the frozen issue-44 two-factor gate.
//!
//! This binary is deliberately outside the immutable issue-42 candidate
//! directory. It consumes that binding unchanged, runs only the two frozen
//! factors, and emits one machine-readable observation for the Python wrapper.

use dyn_stack::{MemBuffer, MemStack, StackReq};
use faer::diag::{DiagMut, DiagRef};
use faer::linalg::cholesky::lblt;
use faer::linalg::lu::full_pivoting;
use faer::prelude::ReborrowMut;
use faer::{MatMut, MatRef, Par};
use rapidrbf_faer_control::{backend_entry, checkpoint, EventKind};
use rapidrbf_instrumented_factor::{
    CancellationToken, CandidateExecutionBinding, CheckpointBound, ExecutionError, ExecutionLease,
    ExecutionMetrics, FactorRole, FactorShape, ResourceGrant, ResourceSchedule,
};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs;
use std::mem::size_of;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};

const SCHEMA: &str = "rapidrbf-instrumented-faer-lane-observation-v1";
const PROJECTED_N: usize = 2_047;
const COARSE_N: usize = 4;
const PROJECTED_SHA256: &str = "e33319fe9a5f02a91bcf7410a784eccc1bded3e05628b59d1d7f0350614d7945";
const COARSE_SHA256: &str = "d8f2c6eda87764e279872463d89cbd344d53947ecffeb7bbc0e55cf90438679e";
const CANCELLATION_DELAY_MS: u64 = 10;
const FEASIBLE: &str = "FEASIBLE_FOR_216_FACTOR_QUALIFICATION";
const REJECTED: &str = "EVIDENCE_BACKED_REJECTED";
const UNJUDGED: &str = "UNJUDGED_EVIDENCE_MISSING";

#[derive(Debug)]
struct Args {
    projected_b: PathBuf,
    coarse_p_top: PathBuf,
    lane_id: String,
    target: String,
}

#[derive(Debug)]
enum ProbeFactor {
    Projected {
        matrix: Vec<f64>,
        subdiag: Vec<f64>,
        perm: Vec<usize>,
        perm_inv: Vec<usize>,
    },
    Coarse {
        matrix: Vec<f64>,
        row_perm: Vec<usize>,
        row_perm_inv: Vec<usize>,
        col_perm: Vec<usize>,
        col_perm_inv: Vec<usize>,
    },
}

impl ProbeFactor {
    fn retained_bytes(&self) -> usize {
        match self {
            Self::Projected {
                matrix,
                subdiag,
                perm,
                perm_inv,
            } => {
                matrix.capacity() * size_of::<f64>()
                    + subdiag.capacity() * size_of::<f64>()
                    + perm.capacity() * size_of::<usize>()
                    + perm_inv.capacity() * size_of::<usize>()
            }
            Self::Coarse {
                matrix,
                row_perm,
                row_perm_inv,
                col_perm,
                col_perm_inv,
            } => {
                matrix.capacity() * size_of::<f64>()
                    + (row_perm.capacity()
                        + row_perm_inv.capacity()
                        + col_perm.capacity()
                        + col_perm_inv.capacity())
                        * size_of::<usize>()
            }
        }
    }

    fn all_finite(&self) -> bool {
        match self {
            Self::Projected {
                matrix, subdiag, ..
            } => {
                matrix.iter().all(|value| value.is_finite())
                    && subdiag.iter().all(|value| value.is_finite())
            }
            Self::Coarse { matrix, .. } => matrix.iter().all(|value| value.is_finite()),
        }
    }

    fn fingerprint(&self) -> String {
        let mut digest = Sha256::new();
        match self {
            Self::Projected {
                matrix,
                subdiag,
                perm,
                perm_inv,
            } => {
                digest.update(b"projected_b\0");
                update_f64s(&mut digest, matrix);
                update_f64s(&mut digest, subdiag);
                update_usizes(&mut digest, perm);
                update_usizes(&mut digest, perm_inv);
            }
            Self::Coarse {
                matrix,
                row_perm,
                row_perm_inv,
                col_perm,
                col_perm_inv,
            } => {
                digest.update(b"coarse_p_top\0");
                update_f64s(&mut digest, matrix);
                update_usizes(&mut digest, row_perm);
                update_usizes(&mut digest, row_perm_inv);
                update_usizes(&mut digest, col_perm);
                update_usizes(&mut digest, col_perm_inv);
            }
        }
        format!("{:x}", digest.finalize())
    }
}

#[derive(Debug)]
struct FactorProduct {
    factor: ProbeFactor,
    backward_error: f64,
    threshold: f64,
    solution_finite: bool,
    live_outer_permits: usize,
    stack_requirement_bytes: usize,
}

fn update_f64s(digest: &mut Sha256, values: &[f64]) {
    for value in values {
        digest.update(value.to_bits().to_le_bytes());
    }
}

fn update_usizes(digest: &mut Sha256, values: &[usize]) {
    for value in values {
        digest.update((*value as u64).to_le_bytes());
    }
}

fn parse_args() -> Result<Args, String> {
    let mut projected_b = None;
    let mut coarse_p_top = None;
    let mut lane_id = None;
    let mut target = None;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        let value = args
            .next()
            .ok_or_else(|| format!("{arg} requires a value"))?;
        match arg.as_str() {
            "--projected-b" => projected_b = Some(PathBuf::from(value)),
            "--coarse-p-top" => coarse_p_top = Some(PathBuf::from(value)),
            "--lane-id" => lane_id = Some(value),
            "--target" => target = Some(value),
            _ => return Err(format!("unknown argument {arg}")),
        }
    }
    Ok(Args {
        projected_b: projected_b.ok_or("--projected-b is required")?,
        coarse_p_top: coarse_p_top.ok_or("--coarse-p-top is required")?,
        lane_id: lane_id.ok_or("--lane-id is required")?,
        target: target.ok_or("--target is required")?,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn read_exact(
    path: &Path,
    expected_bytes: usize,
    expected_sha256: &str,
) -> Result<Vec<u8>, String> {
    let bytes = fs::read(path).map_err(|error| format!("read {}: {error}", path.display()))?;
    if bytes.len() != expected_bytes {
        return Err(format!(
            "{} has {} bytes; expected {expected_bytes}",
            path.display(),
            bytes.len()
        ));
    }
    let observed = sha256(&bytes);
    if observed != expected_sha256 {
        return Err(format!(
            "{} sha256 {observed}; expected {expected_sha256}",
            path.display()
        ));
    }
    Ok(bytes)
}

fn f64_at(bytes: &[u8], index: usize) -> f64 {
    let offset = index * size_of::<f64>();
    f64::from_le_bytes(bytes[offset..offset + size_of::<f64>()].try_into().unwrap())
}

fn packed_lower_value(bytes: &[u8], row: usize, col: usize) -> f64 {
    let (lower_row, lower_col) = if row >= col { (row, col) } else { (col, row) };
    f64_at(bytes, lower_row * (lower_row + 1) / 2 + lower_col)
}

fn row_major_value(bytes: &[u8], n: usize, row: usize, col: usize) -> f64 {
    f64_at(bytes, row * n + col)
}

fn rhs_value(row: usize) -> f64 {
    1.0 + (row % 17) as f64 / 17.0
}

fn reduced_backward_error(role: FactorRole, input: &[u8], solution: &[f64], n: usize) -> f64 {
    let mut residual_inf = 0.0_f64;
    let mut matrix_inf = 0.0_f64;
    let mut solution_inf = 0.0_f64;
    let mut rhs_inf = 0.0_f64;
    for row in 0..n {
        let mut ax = 0.0_f64;
        let mut row_sum = 0.0_f64;
        for col in 0..n {
            let value = match role {
                FactorRole::ProjectedB => packed_lower_value(input, row, col),
                FactorRole::CoarsePTop => row_major_value(input, n, row, col),
            };
            ax += value * solution[col];
            row_sum += value.abs();
        }
        let rhs = rhs_value(row);
        residual_inf = residual_inf.max((ax - rhs).abs());
        matrix_inf = matrix_inf.max(row_sum);
        solution_inf = solution_inf.max(solution[row].abs());
        rhs_inf = rhs_inf.max(rhs.abs());
    }
    residual_inf / (matrix_inf * solution_inf + rhs_inf)
}

fn schedule_json(schedule: ResourceSchedule) -> Value {
    json!({
        "staged_matrix_bytes": schedule.staged_matrix_bytes,
        "staged_matrix_alignment": schedule.staged_matrix_alignment,
        "factor_auxiliary_bytes": schedule.factor_auxiliary_bytes,
        "factor_auxiliary_alignment": schedule.factor_auxiliary_alignment,
        "solver_stack_bytes": schedule.solver_stack_bytes,
        "solver_stack_alignment": schedule.solver_stack_alignment,
        "private_gemm_workspace_bytes": schedule.private_gemm_workspace_bytes,
        "private_gemm_workspace_alignment": schedule.private_gemm_workspace_alignment,
        "solve_rhs_bytes": schedule.solve_rhs_bytes,
        "solve_rhs_alignment": schedule.solve_rhs_alignment,
        "publication_bytes": schedule.publication_bytes,
        "peak_transient_bytes": schedule.peak_transient_bytes,
        "retained_bytes": schedule.retained_bytes,
        "required_compute_permits": schedule.required_compute_permits,
    })
}

fn metrics_json(metrics: ExecutionMetrics) -> Value {
    json!({
        "transient_high_water_bytes": metrics.transient_high_water_bytes,
        "transient_residue_bytes": metrics.transient_residue_bytes,
        "cumulative_reserved_bytes": metrics.cumulative_reserved_bytes,
        "cumulative_released_bytes": metrics.cumulative_released_bytes,
        "stack_carve_events": metrics.stack_carve_events,
        "stack_carved_bytes": metrics.stack_carved_bytes,
        "checkpoint_events": metrics.checkpoint_events,
        "backend_entries": metrics.backend_entries,
        "outer_compute_permits_live": metrics.outer_compute_permits_live,
        "temporary_storage_cumulative_writes": metrics.temporary_storage_cumulative_writes,
        "temporary_storage_residue_bytes": metrics.temporary_storage_residue_bytes,
        "temporary_storage_open_handles": metrics.temporary_storage_open_handles,
    })
}

fn checkpoint_json(bounds: [CheckpointBound; 5]) -> Value {
    Value::Array(
        bounds
            .iter()
            .map(|bound| {
                json!({
                    "kind": format!("{:?}", bound.kind),
                    "maximum_unpolled_work_units": bound.maximum_unpolled_work_units,
                    "unit": bound.unit,
                    "selected_path": bound.selected_path,
                })
            })
            .collect(),
    )
}

fn clean_metrics(metrics: ExecutionMetrics) -> bool {
    metrics.transient_residue_bytes == 0
        && metrics.outer_compute_permits_live == 0
        && metrics.temporary_storage_cumulative_writes == 0
        && metrics.temporary_storage_residue_bytes == 0
        && metrics.temporary_storage_open_handles == 0
        && metrics.cumulative_reserved_bytes == metrics.cumulative_released_bytes
}

fn combined_stack_requirement(factor: StackReq, solve: StackReq) -> StackReq {
    factor.or(solve)
}

fn permute_single_rhs_in_place(rhs: &mut [f64], forward: &[usize]) -> Result<(), String> {
    if rhs.len() != forward.len() {
        return Err("single-RHS permutation length mismatch".to_owned());
    }
    for (index, &mapped) in forward.iter().enumerate() {
        if mapped >= forward.len() {
            return Err(format!("permutation index {index} maps out of range"));
        }
        if forward.iter().filter(|&&value| value == mapped).count() != 1 {
            return Err(format!("permutation target {mapped} is not unique"));
        }
    }
    for start in 0..forward.len() {
        let mut cursor = forward[start];
        let mut leader = true;
        while cursor != start {
            if cursor < start {
                leader = false;
                break;
            }
            cursor = forward[cursor];
        }
        if !leader {
            continue;
        }
        let saved = rhs[start];
        let mut current = start;
        loop {
            let next = forward[current];
            if next == start {
                rhs[current] = saved;
                break;
            }
            rhs[current] = rhs[next];
            current = next;
        }
    }
    Ok(())
}

fn factor_projected(
    input: &[u8],
    lease: &ExecutionLease,
    entered: Option<&AtomicBool>,
) -> Result<FactorProduct, String> {
    let n = PROJECTED_N;
    let mut matrix = vec![0.0_f64; n * n];
    for row in 0..n {
        for col in 0..=row {
            let value = packed_lower_value(input, row, col);
            matrix[row + col * n] = value;
            matrix[col + row * n] = value;
        }
    }
    let mut subdiag = vec![0.0_f64; n];
    let mut perm = vec![0_usize; n];
    let mut perm_inv = vec![0_usize; n];
    let mut rhs = (0..n).map(rhs_value).collect::<Vec<_>>();
    let par = Par::Seq;
    let factor_req =
        lblt::factor::cholesky_in_place_scratch::<usize, f64>(n, par, Default::default());
    let solve_req = lblt::solve::solve_in_place_scratch::<usize, f64>(n, 1, par);
    let combined_req = combined_stack_requirement(factor_req, solve_req);
    let stack_requirement_bytes = combined_req.unaligned_bytes_required();
    let mut memory = MemBuffer::new(combined_req);

    if let Some(entered) = entered {
        entered.store(true, Ordering::Release);
    }
    let live_outer_permits = lease.metrics().outer_compute_permits_live;
    backend_entry();
    let (_, perm_ref) = {
        let mut stack = MemStack::new(&mut memory);
        let matrix_view = MatMut::from_column_major_slice_mut(&mut matrix, n, n);
        let subdiag_view = DiagMut::from_slice_mut(&mut subdiag);
        lblt::factor::cholesky_in_place(
            matrix_view,
            subdiag_view,
            &mut perm,
            &mut perm_inv,
            par,
            &mut stack,
            Default::default(),
        )
    };
    {
        let matrix_view = MatRef::from_column_major_slice(&matrix, n, n);
        let subdiag_view = DiagRef::from_slice(&subdiag);
        let mut rhs_view = MatMut::from_column_major_slice_mut(&mut rhs, n, 1);
        let mut stack = MemStack::new(&mut memory);
        lblt::solve::solve_in_place(
            matrix_view,
            matrix_view.diagonal(),
            subdiag_view,
            perm_ref,
            rhs_view.rb_mut(),
            par,
            &mut stack,
        );
    }
    let solution_finite = rhs.iter().all(|value| value.is_finite());
    let backward_error = reduced_backward_error(FactorRole::ProjectedB, input, &rhs, n);
    let threshold = 64.0 * n as f64 * (f64::EPSILON / 2.0);
    let factor = ProbeFactor::Projected {
        matrix,
        subdiag,
        perm,
        perm_inv,
    };
    Ok(FactorProduct {
        factor,
        backward_error,
        threshold,
        solution_finite,
        live_outer_permits,
        stack_requirement_bytes,
    })
}

fn factor_coarse(
    input: &[u8],
    lease: &ExecutionLease,
    entered: Option<&AtomicBool>,
) -> Result<FactorProduct, String> {
    let n = COARSE_N;
    let mut matrix = vec![0.0_f64; n * n];
    for row in 0..n {
        for col in 0..n {
            matrix[row + col * n] = row_major_value(input, n, row, col);
        }
    }
    let mut row_perm = vec![0_usize; n];
    let mut row_perm_inv = vec![0_usize; n];
    let mut col_perm = vec![0_usize; n];
    let mut col_perm_inv = vec![0_usize; n];
    let mut rhs = (0..n).map(rhs_value).collect::<Vec<_>>();
    let par = Par::Seq;
    let factor_req =
        full_pivoting::factor::lu_in_place_scratch::<usize, f64>(n, n, par, Default::default());
    let stack_requirement_bytes = factor_req.unaligned_bytes_required();
    let mut memory = MemBuffer::new(factor_req);

    if let Some(entered) = entered {
        entered.store(true, Ordering::Release);
    }
    let live_outer_permits = lease.metrics().outer_compute_permits_live;
    backend_entry();
    {
        let mut stack = MemStack::new(&mut memory);
        let matrix_view = MatMut::from_column_major_slice_mut(&mut matrix, n, n);
        let _ = full_pivoting::factor::lu_in_place(
            matrix_view,
            &mut row_perm,
            &mut row_perm_inv,
            &mut col_perm,
            &mut col_perm_inv,
            par,
            &mut stack,
            Default::default(),
        );
    }
    checkpoint(EventKind::Solve, n);
    permute_single_rhs_in_place(&mut rhs, &row_perm)?;
    {
        let matrix_view = MatRef::from_column_major_slice(&matrix, n, n);
        let mut rhs_view = MatMut::from_column_major_slice_mut(&mut rhs, n, 1);
        faer::linalg::triangular_solve::solve_unit_lower_triangular_in_place(
            matrix_view,
            rhs_view.rb_mut(),
            par,
        );
        faer::linalg::triangular_solve::solve_upper_triangular_in_place(
            matrix_view,
            rhs_view.rb_mut(),
            par,
        );
    }
    permute_single_rhs_in_place(&mut rhs, &col_perm_inv)?;
    let solution_finite = rhs.iter().all(|value| value.is_finite());
    let backward_error = reduced_backward_error(FactorRole::CoarsePTop, input, &rhs, n);
    let threshold = 64.0 * n as f64 * (f64::EPSILON / 2.0);
    let factor = ProbeFactor::Coarse {
        matrix,
        row_perm,
        row_perm_inv,
        col_perm,
        col_perm_inv,
    };
    Ok(FactorProduct {
        factor,
        backward_error,
        threshold,
        solution_finite,
        live_outer_permits,
        stack_requirement_bytes,
    })
}

fn success_observation(
    binding: &CandidateExecutionBinding,
    role: FactorRole,
    input: &[u8],
) -> (Value, Option<ProbeFactor>) {
    let (role_name, dimension) = match role {
        FactorRole::ProjectedB => ("projected_b", PROJECTED_N),
        FactorRole::CoarsePTop => ("coarse_p_top", COARSE_N),
    };
    let shape = FactorShape {
        role,
        dimension,
        rhs_columns: 1,
    };
    let schedule = match binding.plan(shape) {
        Ok(schedule) => schedule,
        Err(error) => {
            return (
                json!({"role": role_name, "status": "UNJUDGED", "error": format!("{error:?}")}),
                None,
            );
        }
    };
    let bounds = binding.checkpoint_bounds(shape).unwrap();
    let lease = ExecutionLease::new(ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    });
    let cancellation = CancellationToken::default();
    let result = catch_unwind(AssertUnwindSafe(|| {
        binding.execute(schedule, &lease, &cancellation, || match role {
            FactorRole::ProjectedB => factor_projected(input, &lease, None),
            FactorRole::CoarsePTop => factor_coarse(input, &lease, None),
        })
    }));
    let metrics = lease.metrics();
    let (status, error, product) = match result {
        Ok(Ok(Ok(product))) => ("COMPLETED", Value::Null, Some(product)),
        Ok(Ok(Err(error))) => ("REJECTED", json!(error), None),
        Ok(Err(error)) => ("REJECTED", json!(format!("{error:?}")), None),
        Err(_) => ("REJECTED", json!("non-control panic"), None),
    };
    let retained_bytes = product
        .as_ref()
        .map(|product| product.factor.retained_bytes())
        .unwrap_or(0);
    let factor_finite = product
        .as_ref()
        .is_some_and(|product| product.factor.all_finite());
    let solution_finite = product
        .as_ref()
        .is_some_and(|product| product.solution_finite);
    let backward_error = product.as_ref().map(|product| product.backward_error);
    let threshold = product.as_ref().map(|product| product.threshold);
    let stack_requirement_bytes = product
        .as_ref()
        .map(|product| product.stack_requirement_bytes);
    let fingerprint = product.as_ref().map(|product| product.factor.fingerprint());
    let live_outer_permits = product
        .as_ref()
        .map(|product| product.live_outer_permits)
        .unwrap_or(0);
    let passed = status == "COMPLETED"
        && factor_finite
        && solution_finite
        && backward_error
            .zip(threshold)
            .is_some_and(|(value, limit)| value.is_finite() && value <= limit)
        && retained_bytes == schedule.retained_bytes
        && stack_requirement_bytes == Some(schedule.solver_stack_bytes)
        && live_outer_permits == 1
        && metrics.transient_high_water_bytes == schedule.peak_transient_bytes
        && metrics.backend_entries > 0
        && metrics.checkpoint_events > 0
        && clean_metrics(metrics);
    let observation = json!({
        "role": role_name,
        "status": status,
        "passed": passed,
        "error": error,
        "schedule": schedule_json(schedule),
        "checkpoint_bounds": checkpoint_json(bounds),
        "metrics_after_execution": metrics_json(metrics),
        "factor_finite": factor_finite,
        "solution_finite": solution_finite,
        "reduced_backward_error": backward_error,
        "reduced_backward_error_threshold": threshold,
        "stack_requirement_bytes": stack_requirement_bytes,
        "private_retained_bytes_before_cleanup": retained_bytes,
        "factor_fingerprint_sha256": fingerprint,
        "outer_compute_permits_observed_inside_operation": live_outer_permits,
        "parallelism": "Par::Seq",
        "production_factor_publications": 0,
        "production_solve_publications": 0,
    });
    (observation, product.map(|product| product.factor))
}

fn n_minus_one_observation(binding: &CandidateExecutionBinding, role: FactorRole) -> Value {
    let (role_name, dimension) = match role {
        FactorRole::ProjectedB => ("projected_b", PROJECTED_N),
        FactorRole::CoarsePTop => ("coarse_p_top", COARSE_N),
    };
    let shape = FactorShape {
        role,
        dimension,
        rhs_columns: 1,
    };
    let schedule = binding.plan(shape).unwrap();
    let lease = ExecutionLease::new(ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes - 1,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    });
    let cancellation = CancellationToken::default();
    let operation_entered = AtomicBool::new(false);
    let result = binding.execute(schedule, &lease, &cancellation, || {
        operation_entered.store(true, Ordering::Release);
    });
    let metrics = lease.metrics();
    let passed = result == Err(ExecutionError::ResourceDenied)
        && !operation_entered.load(Ordering::Acquire)
        && metrics == ExecutionMetrics::default();
    json!({
        "role": role_name,
        "passed": passed,
        "grant_transient_bytes": schedule.peak_transient_bytes - 1,
        "required_transient_bytes": schedule.peak_transient_bytes,
        "result": format!("{result:?}"),
        "operation_entered": operation_entered.load(Ordering::Acquire),
        "metrics_after_denial": metrics_json(metrics),
        "failed_replacement_publications": 0,
    })
}

fn cancellation_observation(
    binding: &CandidateExecutionBinding,
    input: &[u8],
    prior: &ProbeFactor,
) -> Value {
    let role = FactorRole::ProjectedB;
    let shape = FactorShape {
        role,
        dimension: PROJECTED_N,
        rhs_columns: 1,
    };
    let schedule = binding.plan(shape).unwrap();
    let lease = ExecutionLease::new(ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    });
    let cancellation = CancellationToken::default();
    let entered = AtomicBool::new(false);
    let finished = AtomicBool::new(false);
    let prior_fingerprint_before = prior.fingerprint();
    let prior_retained_before = prior.retained_bytes();
    let mut acknowledgement_ns = None;
    let mut cancellation_requested = false;
    let result = thread::scope(|scope| {
        let canceller = scope.spawn(|| {
            while !entered.load(Ordering::Acquire) && !finished.load(Ordering::Acquire) {
                thread::yield_now();
            }
            if !entered.load(Ordering::Acquire) {
                return None;
            }
            thread::sleep(Duration::from_millis(CANCELLATION_DELAY_MS));
            let requested_at = Instant::now();
            cancellation.cancel();
            Some(requested_at)
        });
        let execution = catch_unwind(AssertUnwindSafe(|| {
            binding.execute(schedule, &lease, &cancellation, || {
                factor_projected(input, &lease, Some(&entered))
            })
        }));
        let returned_at = Instant::now();
        finished.store(true, Ordering::Release);
        let request = canceller.join().unwrap();
        if let Some(requested_at) = request {
            cancellation_requested = true;
            acknowledgement_ns = returned_at
                .checked_duration_since(requested_at)
                .map(|duration| duration.as_nanos() as u64);
        }
        execution
    });
    let metrics = lease.metrics();
    let prior_fingerprint_after = prior.fingerprint();
    let prior_retained_after = prior.retained_bytes();
    let result_name = match &result {
        Ok(Err(ExecutionError::Cancelled)) => "Cancelled",
        Ok(Ok(Err(_))) => "OperationRejected",
        Ok(Ok(Ok(_))) => "CompletedWithoutCancellation",
        Ok(Err(error)) => match error {
            ExecutionError::ResourceDenied => "ResourceDenied",
            ExecutionError::Cancelled => "Cancelled",
            ExecutionError::ContractViolation => "ContractViolation",
        },
        Err(_) => "NonControlPanic",
    };
    let passed = result_name == "Cancelled"
        && cancellation_requested
        && acknowledgement_ns.is_some()
        && entered.load(Ordering::Acquire)
        && metrics.backend_entries > 0
        && metrics.checkpoint_events > 0
        && clean_metrics(metrics)
        && prior_fingerprint_before == prior_fingerprint_after
        && prior_retained_before == prior_retained_after
        && prior_retained_before == schedule.retained_bytes;
    json!({
        "role": "projected_b",
        "passed": passed,
        "result": result_name,
        "request_delay_after_backend_signal_ms": CANCELLATION_DELAY_MS,
        "cancellation_requested": cancellation_requested,
        "acknowledgement_latency_ns": acknowledgement_ns,
        "backend_signal_observed": entered.load(Ordering::Acquire),
        "metrics_after_cancellation": metrics_json(metrics),
        "prior_state": {
            "role": "projected_b",
            "fingerprint_before": prior_fingerprint_before,
            "fingerprint_after": prior_fingerprint_after,
            "retained_bytes_before": prior_retained_before,
            "retained_bytes_after": prior_retained_after,
            "preserved": prior_fingerprint_before == prior_fingerprint_after
                && prior_retained_before == prior_retained_after,
        },
        "failed_replacement_publications": 0,
        "production_factor_publications": 0,
        "production_solve_publications": 0,
    })
}

fn main() {
    let args = match parse_args() {
        Ok(args) => args,
        Err(error) => {
            println!(
                "{}",
                serde_json::to_string(&json!({
                    "schema": SCHEMA,
                    "disposition": UNJUDGED,
                    "error": error,
                }))
                .unwrap()
            );
            std::process::exit(2);
        }
    };
    let projected = match read_exact(
        &args.projected_b,
        2_096_128 * size_of::<f64>(),
        PROJECTED_SHA256,
    ) {
        Ok(bytes) => bytes,
        Err(error) => {
            println!(
                "{}",
                serde_json::to_string(&json!({
                    "schema": SCHEMA,
                    "disposition": UNJUDGED,
                    "error": error,
                }))
                .unwrap()
            );
            std::process::exit(2);
        }
    };
    let coarse = match read_exact(
        &args.coarse_p_top,
        COARSE_N * COARSE_N * size_of::<f64>(),
        COARSE_SHA256,
    ) {
        Ok(bytes) => bytes,
        Err(error) => {
            println!(
                "{}",
                serde_json::to_string(&json!({
                    "schema": SCHEMA,
                    "disposition": UNJUDGED,
                    "error": error,
                }))
                .unwrap()
            );
            std::process::exit(2);
        }
    };

    faer::set_global_parallelism(Par::Seq);
    let binding = CandidateExecutionBinding::exact();
    let (projected_success, projected_factor) =
        success_observation(&binding, FactorRole::ProjectedB, &projected);
    let (coarse_success, coarse_factor) =
        success_observation(&binding, FactorRole::CoarsePTop, &coarse);
    let projected_n_minus_one = n_minus_one_observation(&binding, FactorRole::ProjectedB);
    let coarse_n_minus_one = n_minus_one_observation(&binding, FactorRole::CoarsePTop);
    let cancellation = projected_factor
        .as_ref()
        .map(|prior| cancellation_observation(&binding, &projected, prior))
        .unwrap_or_else(|| {
            json!({
                "role": "projected_b",
                "passed": false,
                "result": "PriorStateMissing",
                "failed_replacement_publications": 0,
            })
        });

    let successful_private_retained_before_cleanup = projected_factor
        .as_ref()
        .map(ProbeFactor::retained_bytes)
        .unwrap_or(0)
        + coarse_factor
            .as_ref()
            .map(ProbeFactor::retained_bytes)
            .unwrap_or(0);
    let all_checks = projected_success["passed"].as_bool().unwrap_or(false)
        && coarse_success["passed"].as_bool().unwrap_or(false)
        && projected_n_minus_one["passed"].as_bool().unwrap_or(false)
        && coarse_n_minus_one["passed"].as_bool().unwrap_or(false)
        && cancellation["passed"].as_bool().unwrap_or(false);
    let complete =
        projected_success["status"] != "UNJUDGED" && coarse_success["status"] != "UNJUDGED";
    drop(projected_factor);
    drop(coarse_factor);
    let successful_private_retained_after_cleanup = 0_usize;
    let cleanup_closed = successful_private_retained_after_cleanup == 0;
    let disposition = if all_checks && cleanup_closed {
        FEASIBLE
    } else if complete {
        REJECTED
    } else {
        UNJUDGED
    };
    let output = json!({
        "schema": SCHEMA,
        "lane_id": args.lane_id,
        "target": args.target,
        "binding": {
            "schema": binding.schema,
            "profile_sha256": binding.profile_sha256,
            "parallelism": binding.parallelism,
            "temporary_storage": binding.temporary_storage,
        },
        "input_identities": {
            "projected_b": {"bytes": projected.len(), "sha256": sha256(&projected)},
            "coarse_p_top": {"bytes": coarse.len(), "sha256": sha256(&coarse)},
        },
        "success": [projected_success, coarse_success],
        "n_minus_one": [projected_n_minus_one, coarse_n_minus_one],
        "cancellation": cancellation,
        "private_retention": {
            "bytes_before_cleanup": successful_private_retained_before_cleanup,
            "bytes_after_cleanup": successful_private_retained_after_cleanup,
            "cleanup_closed": cleanup_closed,
        },
        "temporary_storage_policy": {
            "policy": "denied",
            "candidate_files_created": 0,
            "candidate_bytes_written": 0,
            "candidate_open_handles_after_execution": 0,
        },
        "production_publication": {
            "validated_factor_count": 0,
            "solved_count": 0,
            "reason": "issue-44 is a feasibility gate; full 216-factor qualification remains delegated",
        },
        "global_parallelism": format!("{:?}", faer::get_global_parallelism()),
        "disposition": disposition,
    });
    println!("{}", serde_json::to_string(&output).unwrap());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frozen_stack_reuse_fits_the_candidate_schedule() {
        let binding = CandidateExecutionBinding::exact();
        for (role, dimension) in [
            (FactorRole::ProjectedB, PROJECTED_N),
            (FactorRole::CoarsePTop, COARSE_N),
        ] {
            let shape = FactorShape {
                role,
                dimension,
                rhs_columns: 1,
            };
            let factor = match role {
                FactorRole::ProjectedB => lblt::factor::cholesky_in_place_scratch::<usize, f64>(
                    dimension,
                    Par::Seq,
                    Default::default(),
                ),
                FactorRole::CoarsePTop => full_pivoting::factor::lu_in_place_scratch::<usize, f64>(
                    dimension,
                    dimension,
                    Par::Seq,
                    Default::default(),
                ),
            };
            let solve =
                match role {
                    FactorRole::ProjectedB => {
                        lblt::solve::solve_in_place_scratch::<usize, f64>(dimension, 1, Par::Seq)
                    }
                    FactorRole::CoarsePTop => full_pivoting::solve::solve_in_place_scratch::<
                        usize,
                        f64,
                    >(dimension, 1, Par::Seq),
                };
            let runner_requirement = match role {
                FactorRole::ProjectedB => factor.or(solve).unaligned_bytes_required(),
                FactorRole::CoarsePTop => factor.unaligned_bytes_required(),
            };
            assert_eq!(
                runner_requirement,
                binding.plan(shape).unwrap().solver_stack_bytes
            );
        }
    }

    #[test]
    fn single_rhs_permutation_matches_forward_semantics() {
        let mut values = vec![10.0, 20.0, 30.0, 40.0];
        permute_single_rhs_in_place(&mut values, &[2, 0, 3, 1]).unwrap();
        assert_eq!(values, vec![30.0, 10.0, 40.0, 20.0]);
    }

    #[test]
    fn frozen_input_sizes_match_the_selected_shapes() {
        assert_eq!(
            2_096_128 * size_of::<f64>(),
            PROJECTED_N * (PROJECTED_N + 1) / 2 * size_of::<f64>()
        );
        assert_eq!(
            COARSE_N * COARSE_N * size_of::<f64>(),
            128,
            "the coarse input is one 4x4 f64 matrix"
        );
    }

    #[test]
    fn one_byte_short_denial_never_enters_the_operation() {
        let binding = CandidateExecutionBinding::exact();
        for role in [FactorRole::ProjectedB, FactorRole::CoarsePTop] {
            let observation = n_minus_one_observation(&binding, role);
            assert_eq!(observation["passed"], true);
            assert_eq!(observation["operation_entered"], false);
        }
    }
}
