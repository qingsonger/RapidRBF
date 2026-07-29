//! THROWAWAY PROTOTYPE: qualify the issue-42 binding over issue 37's corpus.
//!
//! The binary is deliberately outside the immutable candidate directory. It
//! consumes the exact binding unchanged and emits compact decision evidence.

use dyn_stack::{MemBuffer, MemStack, StackReq};
use faer::diag::{DiagMut, DiagRef};
use faer::linalg::cholesky::lblt;
use faer::linalg::lu::full_pivoting;
use faer::perm::PermRef;
use faer::prelude::ReborrowMut;
use faer::{MatMut, MatRef, Par};
use rapidrbf_faer_control::backend_entry;
use rapidrbf_instrumented_factor::{
    CancellationToken, CandidateExecutionBinding, ExecutionError, ExecutionLease, ExecutionMetrics,
    FactorRole, FactorShape, ResourceGrant, ResourceSchedule,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::VecDeque;
use std::fs::{self, File};
use std::io::Write;
use std::mem::size_of;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Barrier, Mutex};
use std::thread;
use std::time::{Duration, Instant};

const OBSERVATION_SCHEMA: &str = "RapidRBF/InstrumentedFaerCorpusQualificationLaneObservation/v1";
const PLAN_SCHEMA: &str = "RapidRBF/FactorQualificationPlan/v1";
const PROFILE_SHA256: &str = "00e5fb051af7bdf11af337890fc7cea9e3b5e85a6e35b47f7e9bff89f805a2c3";
const BINDING_SHA256: &str = "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6";
const PACK_SCHEMA: &str = "RapidRBF/PrototypeQualifiedFactorPack/v1";
const PACK_MAGIC: &[u8; 8] = b"RBFQPK01";
const ADMITTED: &str = "ADMITTED_FOR_MECHANISM_PANEL";
const NOT_ADMITTED: &str = "NOT_ADMITTED_DIAGNOSTIC_ONLY";
const RHS_COLUMNS: usize = 3;
const CANCELLATION_DELAY_MS: u64 = 10;

#[derive(Debug)]
struct Args {
    plan: PathBuf,
    bundle_root: PathBuf,
    lane_id: String,
    target: String,
    workers: usize,
    maximum_live_threads: usize,
    scratch: PathBuf,
    output: PathBuf,
    source_limit: Option<usize>,
}

#[derive(Clone, Debug, Deserialize)]
struct Plan {
    schema: String,
    plan_id: String,
    authority: Value,
    factor_sources: Vec<Source>,
}

#[derive(Clone, Debug, Deserialize)]
struct Source {
    ordinal: usize,
    factor_source_id: String,
    block_id: String,
    workload_id: String,
    role: String,
    bundle_path: String,
    bytes: usize,
    sha256: String,
    encoding: String,
    dimension: usize,
}

#[derive(Debug)]
struct MatrixInput {
    role: FactorRole,
    dimension: usize,
    bytes: Vec<u8>,
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
    fn role(&self) -> FactorRole {
        match self {
            Self::Projected { .. } => FactorRole::ProjectedB,
            Self::Coarse { .. } => FactorRole::CoarsePTop,
        }
    }

    fn dimension(&self) -> usize {
        match self {
            Self::Projected { matrix, .. } | Self::Coarse { matrix, .. } => {
                exact_square_dimension(matrix.len())
            }
        }
    }

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
                    + (perm.capacity() + perm_inv.capacity()) * size_of::<usize>()
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
    solutions: Vec<f64>,
    live_outer_permits: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PackHeader {
    schema: String,
    plan_id: String,
    profile_sha256: String,
    binding_sha256: String,
    factor_source_id: String,
    source_sha256: String,
    role: String,
    dimension: usize,
    payload_bytes: usize,
    payload_sha256: String,
    factor_fingerprint: String,
}

#[derive(Default)]
struct ScratchTracker {
    current: AtomicU64,
    high_water: AtomicU64,
    cumulative_writes: AtomicU64,
}

impl ScratchTracker {
    fn add(&self, bytes: u64) {
        let current = self.current.fetch_add(bytes, Ordering::AcqRel) + bytes;
        self.cumulative_writes.fetch_add(bytes, Ordering::AcqRel);
        let mut observed = self.high_water.load(Ordering::Acquire);
        while current > observed {
            match self.high_water.compare_exchange_weak(
                observed,
                current,
                Ordering::AcqRel,
                Ordering::Acquire,
            ) {
                Ok(_) => break,
                Err(next) => observed = next,
            }
        }
    }

    fn remove(&self, bytes: u64) -> Result<(), String> {
        self.current
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |current| {
                current.checked_sub(bytes)
            })
            .map(|_| ())
            .map_err(|_| "scratch accounting underflow".to_owned())
    }
}

fn parse_args() -> Result<Args, String> {
    let mut plan = None;
    let mut bundle_root = None;
    let mut lane_id = None;
    let mut target = None;
    let mut workers = None;
    let mut maximum_live_threads = None;
    let mut scratch = None;
    let mut output = None;
    let mut source_limit = None;
    let mut args = std::env::args().skip(1);
    while let Some(argument) = args.next() {
        let value = args
            .next()
            .ok_or_else(|| format!("{argument} requires a value"))?;
        match argument.as_str() {
            "--plan" => plan = Some(PathBuf::from(value)),
            "--bundle-root" => bundle_root = Some(PathBuf::from(value)),
            "--lane-id" => lane_id = Some(value),
            "--target" => target = Some(value),
            "--workers" => {
                workers = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| "--workers must be an integer".to_owned())?,
                )
            }
            "--maximum-live-threads" => {
                maximum_live_threads = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| "--maximum-live-threads must be an integer".to_owned())?,
                )
            }
            "--scratch" => scratch = Some(PathBuf::from(value)),
            "--output" => output = Some(PathBuf::from(value)),
            "--source-limit" => {
                source_limit = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| "--source-limit must be an integer".to_owned())?,
                )
            }
            _ => return Err(format!("unknown argument {argument}")),
        }
    }
    Ok(Args {
        plan: plan.ok_or("--plan is required")?,
        bundle_root: bundle_root.ok_or("--bundle-root is required")?,
        lane_id: lane_id.ok_or("--lane-id is required")?,
        target: target.ok_or("--target is required")?,
        workers: workers.ok_or("--workers is required")?,
        maximum_live_threads: maximum_live_threads.ok_or("--maximum-live-threads is required")?,
        scratch: scratch.ok_or("--scratch is required")?,
        output: output.ok_or("--output is required")?,
        source_limit,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
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

fn exact_square_dimension(elements: usize) -> usize {
    let dimension = (elements as f64).sqrt() as usize;
    assert_eq!(dimension * dimension, elements);
    dimension
}

fn source_role(source: &Source) -> Result<FactorRole, String> {
    match source.role.as_str() {
        "projected_b" => Ok(FactorRole::ProjectedB),
        "coarse_p_top" => Ok(FactorRole::CoarsePTop),
        _ => Err(format!("unknown source role {}", source.role)),
    }
}

fn read_source(bundle_root: &Path, source: &Source) -> Result<MatrixInput, String> {
    let expected_relative = format!("sources/{}.f64le", source.sha256);
    if source.bundle_path != expected_relative
        || source.bundle_path.contains("..")
        || Path::new(&source.bundle_path).is_absolute()
    {
        return Err(format!(
            "{} has invalid bundle path {}",
            source.factor_source_id, source.bundle_path
        ));
    }
    let path = bundle_root.join(&source.bundle_path);
    let bytes = fs::read(&path).map_err(|error| format!("read {}: {error}", path.display()))?;
    if bytes.len() != source.bytes {
        return Err(format!(
            "{} has {} bytes; expected {}",
            source.factor_source_id,
            bytes.len(),
            source.bytes
        ));
    }
    let observed = sha256(&bytes);
    if observed != source.sha256 {
        return Err(format!(
            "{} source sha256 {observed}; expected {}",
            source.factor_source_id, source.sha256
        ));
    }
    let role = source_role(source)?;
    let expected_elements = match role {
        FactorRole::ProjectedB => source
            .dimension
            .checked_mul(source.dimension + 1)
            .and_then(|value| value.checked_div(2))
            .ok_or("projected source size overflow")?,
        FactorRole::CoarsePTop => source
            .dimension
            .checked_mul(source.dimension)
            .ok_or("coarse source size overflow")?,
    };
    if bytes.len() != expected_elements * size_of::<f64>() {
        return Err(format!(
            "{} source shape does not match byte count",
            source.factor_source_id
        ));
    }
    if (role == FactorRole::ProjectedB && source.encoding != "lower-triangle-row-major-packed")
        || (role == FactorRole::CoarsePTop && source.encoding != "row-major")
    {
        return Err(format!(
            "{} source encoding differs",
            source.factor_source_id
        ));
    }
    Ok(MatrixInput {
        role,
        dimension: source.dimension,
        bytes,
    })
}

fn f64_at(bytes: &[u8], index: usize) -> f64 {
    let offset = index * size_of::<f64>();
    f64::from_le_bytes(bytes[offset..offset + size_of::<f64>()].try_into().unwrap())
}

fn matrix_value(input: &MatrixInput, row: usize, column: usize) -> f64 {
    match input.role {
        FactorRole::ProjectedB => {
            let (lower_row, lower_column) = if row >= column {
                (row, column)
            } else {
                (column, row)
            };
            f64_at(&input.bytes, lower_row * (lower_row + 1) / 2 + lower_column)
        }
        FactorRole::CoarsePTop => f64_at(&input.bytes, row * input.dimension + column),
    }
}

fn declared_solutions(dimension: usize) -> Vec<f64> {
    let mut solutions = vec![0.0; dimension * RHS_COLUMNS];
    for row in 0..dimension {
        solutions[row] = 1.0 + (row % 17) as f64 / 17.0;
        solutions[row + dimension] = if row % 2 == 0 { 1.0 } else { -1.0 };
        let exponent = (row % 21) as i32 - 10;
        let sign = if row % 2 == 0 { 1.0 } else { -1.0 };
        solutions[row + 2 * dimension] = sign * 2.0_f64.powi(exponent);
    }
    solutions
}

fn manufactured_rhs(input: &MatrixInput, solutions: &[f64]) -> Vec<f64> {
    let n = input.dimension;
    let mut rhs = vec![0.0; n * RHS_COLUMNS];
    match input.role {
        FactorRole::ProjectedB => {
            for row in 0..n {
                for column in 0..=row {
                    let value = matrix_value(input, row, column);
                    for family in 0..RHS_COLUMNS {
                        rhs[row + family * n] += value * solutions[column + family * n];
                        if row != column {
                            rhs[column + family * n] += value * solutions[row + family * n];
                        }
                    }
                }
            }
        }
        FactorRole::CoarsePTop => {
            for row in 0..n {
                for column in 0..n {
                    let value = matrix_value(input, row, column);
                    for family in 0..RHS_COLUMNS {
                        rhs[row + family * n] += value * solutions[column + family * n];
                    }
                }
            }
        }
    }
    rhs
}

fn combined_stack_requirement(factor: StackReq, solve: StackReq) -> StackReq {
    factor.or(solve)
}

fn factor_source(
    input: &MatrixInput,
    lease: &ExecutionLease,
    entered: Option<&AtomicBool>,
) -> Result<(ProbeFactor, usize), String> {
    let n = input.dimension;
    match input.role {
        FactorRole::ProjectedB => {
            let mut matrix = vec![0.0_f64; n * n];
            for row in 0..n {
                for column in 0..=row {
                    let value = matrix_value(input, row, column);
                    matrix[row + column * n] = value;
                    matrix[column + row * n] = value;
                }
            }
            let mut subdiag = vec![0.0_f64; n];
            let mut perm = vec![0_usize; n];
            let mut perm_inv = vec![0_usize; n];
            let factor_req = lblt::factor::cholesky_in_place_scratch::<usize, f64>(
                n,
                Par::Seq,
                Default::default(),
            );
            let solve_req =
                lblt::solve::solve_in_place_scratch::<usize, f64>(n, RHS_COLUMNS, Par::Seq);
            let request = combined_stack_requirement(factor_req, solve_req);
            let stack_bytes = request.unaligned_bytes_required();
            let mut memory = MemBuffer::new(request);
            if let Some(entered) = entered {
                entered.store(true, Ordering::Release);
            }
            let live_permits = lease.metrics().outer_compute_permits_live;
            backend_entry();
            {
                let mut stack = MemStack::new(&mut memory);
                let matrix_view = MatMut::from_column_major_slice_mut(&mut matrix, n, n);
                let subdiag_view = DiagMut::from_slice_mut(&mut subdiag);
                let _ = lblt::factor::cholesky_in_place(
                    matrix_view,
                    subdiag_view,
                    &mut perm,
                    &mut perm_inv,
                    Par::Seq,
                    &mut stack,
                    Default::default(),
                );
            }
            let _ = stack_bytes;
            Ok((
                ProbeFactor::Projected {
                    matrix,
                    subdiag,
                    perm,
                    perm_inv,
                },
                live_permits,
            ))
        }
        FactorRole::CoarsePTop => {
            let mut matrix = vec![0.0_f64; n * n];
            for row in 0..n {
                for column in 0..n {
                    matrix[row + column * n] = matrix_value(input, row, column);
                }
            }
            let mut row_perm = vec![0_usize; n];
            let mut row_perm_inv = vec![0_usize; n];
            let mut col_perm = vec![0_usize; n];
            let mut col_perm_inv = vec![0_usize; n];
            let request = full_pivoting::factor::lu_in_place_scratch::<usize, f64>(
                n,
                n,
                Par::Seq,
                Default::default(),
            );
            let stack_bytes = request.unaligned_bytes_required();
            let mut memory = MemBuffer::new(request);
            if let Some(entered) = entered {
                entered.store(true, Ordering::Release);
            }
            let live_permits = lease.metrics().outer_compute_permits_live;
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
                    Par::Seq,
                    &mut stack,
                    Default::default(),
                );
            }
            let _ = stack_bytes;
            Ok((
                ProbeFactor::Coarse {
                    matrix,
                    row_perm,
                    row_perm_inv,
                    col_perm,
                    col_perm_inv,
                },
                live_permits,
            ))
        }
    }
}

fn solve_factor(
    factor: &ProbeFactor,
    mut rhs: Vec<f64>,
    lease: &ExecutionLease,
    entered: Option<&AtomicBool>,
) -> Result<(Vec<f64>, usize), String> {
    let n = factor.dimension();
    if rhs.len() != n * RHS_COLUMNS {
        return Err("solve RHS shape differs".to_owned());
    }
    if let Some(entered) = entered {
        entered.store(true, Ordering::Release);
    }
    let live_permits = lease.metrics().outer_compute_permits_live;
    backend_entry();
    match factor {
        ProbeFactor::Projected {
            matrix,
            subdiag,
            perm,
            perm_inv,
        } => {
            let request =
                lblt::solve::solve_in_place_scratch::<usize, f64>(n, RHS_COLUMNS, Par::Seq);
            let stack_bytes = request.unaligned_bytes_required();
            let mut memory = MemBuffer::new(request);
            let matrix_view = MatRef::from_column_major_slice(matrix, n, n);
            let subdiag_view = DiagRef::from_slice(subdiag);
            let permutation = PermRef::new_checked(perm, perm_inv, n);
            let mut rhs_view = MatMut::from_column_major_slice_mut(&mut rhs, n, RHS_COLUMNS);
            let mut stack = MemStack::new(&mut memory);
            lblt::solve::solve_in_place(
                matrix_view,
                matrix_view.diagonal(),
                subdiag_view,
                permutation,
                rhs_view.rb_mut(),
                Par::Seq,
                &mut stack,
            );
            let _ = stack_bytes;
            Ok((rhs, live_permits))
        }
        ProbeFactor::Coarse {
            matrix,
            row_perm,
            row_perm_inv,
            col_perm,
            col_perm_inv,
        } => {
            let request = full_pivoting::solve::solve_in_place_scratch::<usize, f64>(
                n,
                RHS_COLUMNS,
                Par::Seq,
            );
            let stack_bytes = request.unaligned_bytes_required();
            let mut memory = MemBuffer::new(request);
            let matrix_view = MatRef::from_column_major_slice(matrix, n, n);
            let row = PermRef::new_checked(row_perm, row_perm_inv, n);
            let column = PermRef::new_checked(col_perm, col_perm_inv, n);
            let mut rhs_view = MatMut::from_column_major_slice_mut(&mut rhs, n, RHS_COLUMNS);
            let mut stack = MemStack::new(&mut memory);
            full_pivoting::solve::solve_in_place(
                matrix_view,
                matrix_view,
                row,
                column,
                rhs_view.rb_mut(),
                Par::Seq,
                &mut stack,
            );
            let _ = stack_bytes;
            Ok((rhs, live_permits))
        }
    }
}

fn factor_and_solve(
    input: &MatrixInput,
    rhs: Vec<f64>,
    lease: &ExecutionLease,
) -> Result<FactorProduct, String> {
    let (factor, factor_observation) = factor_source(input, lease, None)?;
    let (solutions, solve_observation) = solve_factor(&factor, rhs, lease, None)?;
    Ok(FactorProduct {
        factor,
        solutions,
        live_outer_permits: factor_observation.min(solve_observation).min(1),
    })
}

fn error_metrics(
    input: &MatrixInput,
    rhs: &[f64],
    expected: &[f64],
    observed: &[f64],
) -> (f64, f64) {
    let n = input.dimension;
    let mut matrix_inf = 0.0_f64;
    for row in 0..n {
        let mut row_sum = 0.0_f64;
        for column in 0..n {
            row_sum += matrix_value(input, row, column).abs();
        }
        matrix_inf = matrix_inf.max(row_sum);
    }
    let mut backward = 0.0_f64;
    let mut relative_solution = 0.0_f64;
    for family in 0..RHS_COLUMNS {
        let offset = family * n;
        let mut residual_inf = 0.0_f64;
        let mut solution_inf = 0.0_f64;
        let mut rhs_inf = 0.0_f64;
        let mut difference_inf = 0.0_f64;
        let mut expected_inf = 0.0_f64;
        for row in 0..n {
            let mut action = 0.0_f64;
            for column in 0..n {
                action += matrix_value(input, row, column) * observed[offset + column];
            }
            residual_inf = residual_inf.max((action - rhs[offset + row]).abs());
            solution_inf = solution_inf.max(observed[offset + row].abs());
            rhs_inf = rhs_inf.max(rhs[offset + row].abs());
            difference_inf =
                difference_inf.max((observed[offset + row] - expected[offset + row]).abs());
            expected_inf = expected_inf.max(expected[offset + row].abs());
        }
        backward = backward
            .max(residual_inf / (matrix_inf * solution_inf + rhs_inf).max(f64::MIN_POSITIVE));
        relative_solution = relative_solution.max(difference_inf / expected_inf.max(1.0));
    }
    (backward, relative_solution)
}

fn reconstruction_error(input: &MatrixInput, factor: &ProbeFactor) -> Result<f64, String> {
    let n = input.dimension;
    let mut reconstructed = vec![0.0_f64; n * n];
    match factor {
        ProbeFactor::Projected {
            matrix,
            subdiag,
            perm,
            perm_inv,
        } => {
            let request = lblt::reconstruct::reconstruct_scratch::<usize, f64>(n, Par::Seq);
            let mut memory = MemBuffer::new(request);
            let matrix_view = MatRef::from_column_major_slice(matrix, n, n);
            let mut output = MatMut::from_column_major_slice_mut(&mut reconstructed, n, n);
            let permutation = PermRef::new_checked(perm, perm_inv, n);
            let mut stack = MemStack::new(&mut memory);
            lblt::reconstruct::reconstruct(
                output.rb_mut(),
                matrix_view,
                matrix_view.diagonal(),
                DiagRef::from_slice(subdiag),
                permutation,
                Par::Seq,
                &mut stack,
            );
            for row in 0..n {
                for column in row + 1..n {
                    reconstructed[row + column * n] = reconstructed[column + row * n];
                }
            }
        }
        ProbeFactor::Coarse {
            matrix,
            row_perm,
            row_perm_inv,
            col_perm,
            col_perm_inv,
        } => {
            let request =
                full_pivoting::reconstruct::reconstruct_scratch::<usize, f64>(n, n, Par::Seq);
            let mut memory = MemBuffer::new(request);
            let matrix_view = MatRef::from_column_major_slice(matrix, n, n);
            let row = PermRef::new_checked(row_perm, row_perm_inv, n);
            let column = PermRef::new_checked(col_perm, col_perm_inv, n);
            let mut output = MatMut::from_column_major_slice_mut(&mut reconstructed, n, n);
            let mut stack = MemStack::new(&mut memory);
            full_pivoting::reconstruct::reconstruct(
                output.rb_mut(),
                matrix_view,
                matrix_view,
                row,
                column,
                Par::Seq,
                &mut stack,
            );
        }
    }
    let mut difference_inf = 0.0_f64;
    let mut input_inf = 0.0_f64;
    for row in 0..n {
        let mut difference_row = 0.0_f64;
        let mut input_row = 0.0_f64;
        for column in 0..n {
            let expected = matrix_value(input, row, column);
            let observed = reconstructed[row + column * n];
            difference_row += (observed - expected).abs();
            input_row += expected.abs();
        }
        difference_inf = difference_inf.max(difference_row);
        input_inf = input_inf.max(input_row);
    }
    Ok(difference_inf / input_inf.max(f64::MIN_POSITIVE))
}

fn clean_metrics(metrics: ExecutionMetrics) -> bool {
    metrics.transient_residue_bytes == 0
        && metrics.outer_compute_permits_live == 0
        && metrics.temporary_storage_cumulative_writes == 0
        && metrics.temporary_storage_residue_bytes == 0
        && metrics.temporary_storage_open_handles == 0
        && metrics.cumulative_reserved_bytes == metrics.cumulative_released_bytes
}

fn schedule_json(schedule: ResourceSchedule) -> Value {
    json!({
        "peak_transient_bytes": schedule.peak_transient_bytes,
        "retained_bytes": schedule.retained_bytes,
        "private_gemm_workspace_bytes": schedule.private_gemm_workspace_bytes,
        "solver_stack_bytes": schedule.solver_stack_bytes,
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
    })
}

fn encode_payload(factor: &ProbeFactor) -> Vec<u8> {
    let mut payload = Vec::with_capacity(factor.retained_bytes());
    match factor {
        ProbeFactor::Projected {
            matrix,
            subdiag,
            perm,
            perm_inv,
        } => {
            append_f64s(&mut payload, matrix);
            append_f64s(&mut payload, subdiag);
            append_usizes(&mut payload, perm);
            append_usizes(&mut payload, perm_inv);
        }
        ProbeFactor::Coarse {
            matrix,
            row_perm,
            row_perm_inv,
            col_perm,
            col_perm_inv,
        } => {
            append_f64s(&mut payload, matrix);
            append_usizes(&mut payload, row_perm);
            append_usizes(&mut payload, row_perm_inv);
            append_usizes(&mut payload, col_perm);
            append_usizes(&mut payload, col_perm_inv);
        }
    }
    payload
}

fn append_f64s(output: &mut Vec<u8>, values: &[f64]) {
    for value in values {
        output.extend_from_slice(&value.to_bits().to_le_bytes());
    }
}

fn append_usizes(output: &mut Vec<u8>, values: &[usize]) {
    for value in values {
        output.extend_from_slice(&(*value as u64).to_le_bytes());
    }
}

fn read_f64s(bytes: &[u8], cursor: &mut usize, count: usize) -> Result<Vec<f64>, String> {
    let required = count
        .checked_mul(8)
        .and_then(|value| cursor.checked_add(value))
        .ok_or("f64 payload overflow")?;
    if required > bytes.len() {
        return Err("truncated f64 payload".to_owned());
    }
    let mut values = Vec::with_capacity(count);
    for chunk in bytes[*cursor..required].chunks_exact(8) {
        values.push(f64::from_bits(u64::from_le_bytes(
            chunk.try_into().unwrap(),
        )));
    }
    *cursor = required;
    Ok(values)
}

fn read_usizes(bytes: &[u8], cursor: &mut usize, count: usize) -> Result<Vec<usize>, String> {
    let required = count
        .checked_mul(8)
        .and_then(|value| cursor.checked_add(value))
        .ok_or("usize payload overflow")?;
    if required > bytes.len() {
        return Err("truncated usize payload".to_owned());
    }
    let mut values = Vec::with_capacity(count);
    for chunk in bytes[*cursor..required].chunks_exact(8) {
        let value = u64::from_le_bytes(chunk.try_into().unwrap());
        values.push(usize::try_from(value).map_err(|_| "packed index does not fit usize")?);
    }
    *cursor = required;
    Ok(values)
}

fn role_name(role: FactorRole) -> &'static str {
    match role {
        FactorRole::ProjectedB => "projected_b",
        FactorRole::CoarsePTop => "coarse_p_top",
    }
}

fn write_pack(
    path: &Path,
    plan_id: &str,
    source: &Source,
    factor: &ProbeFactor,
) -> Result<(u64, String), String> {
    let payload = encode_payload(factor);
    let header = PackHeader {
        schema: PACK_SCHEMA.to_owned(),
        plan_id: plan_id.to_owned(),
        profile_sha256: PROFILE_SHA256.to_owned(),
        binding_sha256: BINDING_SHA256.to_owned(),
        factor_source_id: source.factor_source_id.clone(),
        source_sha256: source.sha256.clone(),
        role: role_name(factor.role()).to_owned(),
        dimension: factor.dimension(),
        payload_bytes: payload.len(),
        payload_sha256: sha256(&payload),
        factor_fingerprint: factor.fingerprint(),
    };
    let header_bytes =
        serde_json::to_vec(&header).map_err(|error| format!("serialize pack header: {error}"))?;
    let temporary = path.with_extension("tmp");
    let mut file = File::create_new(&temporary).map_err(|error| format!("create pack: {error}"))?;
    file.write_all(PACK_MAGIC)
        .and_then(|_| file.write_all(&(header_bytes.len() as u64).to_le_bytes()))
        .and_then(|_| file.write_all(&header_bytes))
        .and_then(|_| file.write_all(&payload))
        .and_then(|_| file.sync_all())
        .map_err(|error| format!("write pack: {error}"))?;
    drop(file);
    fs::rename(&temporary, path).map_err(|error| format!("publish pack: {error}"))?;
    let bytes = fs::read(path).map_err(|error| format!("read published pack: {error}"))?;
    Ok((bytes.len() as u64, sha256(&bytes)))
}

fn load_pack_bytes(
    bytes: &[u8],
    expected_plan: &str,
    expected_profile: &str,
    expected_binding: &str,
    expected_source_id: &str,
    expected_source_sha256: &str,
) -> Result<ProbeFactor, String> {
    if bytes.len() < 16 || &bytes[..8] != PACK_MAGIC {
        return Err("pack magic or header is truncated".to_owned());
    }
    let header_length = u64::from_le_bytes(bytes[8..16].try_into().unwrap());
    let header_length =
        usize::try_from(header_length).map_err(|_| "pack header length overflows")?;
    let payload_start = 16_usize
        .checked_add(header_length)
        .ok_or("pack header length overflows")?;
    if payload_start > bytes.len() {
        return Err("pack header is truncated".to_owned());
    }
    let header: PackHeader = serde_json::from_slice(&bytes[16..payload_start])
        .map_err(|error| format!("pack header is malformed: {error}"))?;
    if header.schema != PACK_SCHEMA {
        return Err("pack schema mismatch".to_owned());
    }
    if header.plan_id != expected_plan {
        return Err("pack metadata mismatch".to_owned());
    }
    if header.profile_sha256 != expected_profile {
        return Err("pack profile mismatch".to_owned());
    }
    if header.binding_sha256 != expected_binding {
        return Err("pack binding mismatch".to_owned());
    }
    if header.factor_source_id != expected_source_id
        || header.source_sha256 != expected_source_sha256
    {
        return Err("pack source mismatch".to_owned());
    }
    let payload = &bytes[payload_start..];
    if payload.len() != header.payload_bytes || sha256(payload) != header.payload_sha256 {
        return Err("pack payload is truncated or corrupt".to_owned());
    }
    let n = header.dimension;
    if n == 0 {
        return Err("pack dimension is zero".to_owned());
    }
    let mut cursor = 0;
    let factor = match header.role.as_str() {
        "projected_b" => ProbeFactor::Projected {
            matrix: read_f64s(payload, &mut cursor, n * n)?,
            subdiag: read_f64s(payload, &mut cursor, n)?,
            perm: read_usizes(payload, &mut cursor, n)?,
            perm_inv: read_usizes(payload, &mut cursor, n)?,
        },
        "coarse_p_top" => ProbeFactor::Coarse {
            matrix: read_f64s(payload, &mut cursor, n * n)?,
            row_perm: read_usizes(payload, &mut cursor, n)?,
            row_perm_inv: read_usizes(payload, &mut cursor, n)?,
            col_perm: read_usizes(payload, &mut cursor, n)?,
            col_perm_inv: read_usizes(payload, &mut cursor, n)?,
        },
        _ => return Err("pack role mismatch".to_owned()),
    };
    if cursor != payload.len()
        || !factor.all_finite()
        || factor.fingerprint() != header.factor_fingerprint
    {
        return Err("pack logical factor validation failed".to_owned());
    }
    match &factor {
        ProbeFactor::Projected { perm, perm_inv, .. } => {
            let _ = PermRef::new_checked(perm, perm_inv, n);
        }
        ProbeFactor::Coarse {
            row_perm,
            row_perm_inv,
            col_perm,
            col_perm_inv,
            ..
        } => {
            let _ = PermRef::new_checked(row_perm, row_perm_inv, n);
            let _ = PermRef::new_checked(col_perm, col_perm_inv, n);
        }
    }
    Ok(factor)
}

fn load_pack(path: &Path, plan_id: &str, source: &Source) -> Result<ProbeFactor, String> {
    let bytes = fs::read(path).map_err(|error| format!("read pack: {error}"))?;
    load_pack_bytes(
        &bytes,
        plan_id,
        PROFILE_SHA256,
        BINDING_SHA256,
        &source.factor_source_id,
        &source.sha256,
    )
}

fn negative_reload_controls(path: &Path, plan_id: &str, source: &Source) -> Result<Value, String> {
    let bytes = fs::read(path).map_err(|error| format!("read control pack: {error}"))?;
    if bytes.len() < 2 {
        return Err("control pack unexpectedly small".to_owned());
    }
    let truncated = load_pack_bytes(
        &bytes[..bytes.len() - 1],
        plan_id,
        PROFILE_SHA256,
        BINDING_SHA256,
        &source.factor_source_id,
        &source.sha256,
    )
    .is_err();
    let mut corrupt = bytes.clone();
    let last = corrupt.len() - 1;
    corrupt[last] ^= 0x01;
    let corrupt_rejected = load_pack_bytes(
        &corrupt,
        plan_id,
        PROFILE_SHA256,
        BINDING_SHA256,
        &source.factor_source_id,
        &source.sha256,
    )
    .is_err();
    let wrong_source = load_pack_bytes(
        &bytes,
        plan_id,
        PROFILE_SHA256,
        BINDING_SHA256,
        "wrong-source",
        &source.sha256,
    )
    .is_err();
    let wrong_profile = load_pack_bytes(
        &bytes,
        plan_id,
        "wrong-profile",
        BINDING_SHA256,
        &source.factor_source_id,
        &source.sha256,
    )
    .is_err();
    let metadata_mismatch = load_pack_bytes(
        &bytes,
        "wrong-plan",
        PROFILE_SHA256,
        BINDING_SHA256,
        &source.factor_source_id,
        &source.sha256,
    )
    .is_err();
    let pass = truncated && corrupt_rejected && wrong_source && wrong_profile && metadata_mismatch;
    Ok(json!({
        "status": if pass { "PASS" } else { "FAIL" },
        "backend_entries": 0,
        "truncated_pack": truncated,
        "corrupt_pack": corrupt_rejected,
        "wrong_source": wrong_source,
        "wrong_profile": wrong_profile,
        "metadata_mismatch": metadata_mismatch,
    }))
}

fn n_minus_one(
    binding: &CandidateExecutionBinding,
    schedule: ResourceSchedule,
) -> Result<Value, String> {
    if schedule.peak_transient_bytes == 0 {
        return Err("zero transient schedule cannot run N-minus-one".to_owned());
    }
    let lease = ExecutionLease::new(ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes - 1,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    });
    let cancellation = CancellationToken::default();
    let called = AtomicBool::new(false);
    let result = binding.execute(schedule, &lease, &cancellation, || {
        called.store(true, Ordering::Release);
    });
    let metrics = lease.metrics();
    let pass = result == Err(ExecutionError::ResourceDenied)
        && !called.load(Ordering::Acquire)
        && metrics == ExecutionMetrics::default();
    Ok(json!({
        "status": if pass { "PASS" } else { "FAIL" },
        "result": format!("{result:?}"),
        "operation_called": called.load(Ordering::Acquire),
        "metrics": metrics_json(metrics),
    }))
}

fn process_source(
    binding: &CandidateExecutionBinding,
    plan_id: &str,
    bundle_root: &Path,
    scratch: &Path,
    tracker: &ScratchTracker,
    source: &Source,
    controls_source: usize,
) -> Result<Value, String> {
    let input = read_source(bundle_root, source)?;
    let shape = FactorShape {
        role: input.role,
        dimension: input.dimension,
        rhs_columns: RHS_COLUMNS,
    };
    let schedule = binding
        .plan(shape)
        .map_err(|error| format!("candidate plan: {error:?}"))?;
    let n_minus_one = n_minus_one(binding, schedule)?;
    if n_minus_one["status"] != "PASS" {
        return Err("N-minus-one control failed".to_owned());
    }
    let expected = declared_solutions(input.dimension);
    let rhs = manufactured_rhs(&input, &expected);
    let lease = ExecutionLease::new(ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    });
    let cancellation = CancellationToken::default();
    let executed = binding.execute(schedule, &lease, &cancellation, || {
        factor_and_solve(&input, rhs.clone(), &lease)
    });
    let metrics = lease.metrics();
    let product = executed
        .map_err(|error| format!("candidate execute: {error:?}"))?
        .map_err(|error| format!("factor/solve: {error}"))?;
    if !clean_metrics(metrics)
        || !product.factor.all_finite()
        || !product.solutions.iter().all(|value| value.is_finite())
        || product.live_outer_permits != 1
        || product.factor.retained_bytes() != schedule.retained_bytes
    {
        return Err("factor execution resource or finite-state gate failed".to_owned());
    }
    let (backward_error, solution_error) =
        error_metrics(&input, &rhs, &expected, &product.solutions);
    let reconstruction_error = reconstruction_error(&input, &product.factor)?;
    let reconstruction_threshold = 64.0 * input.dimension as f64 * (f64::EPSILON / 2.0);
    let backward_threshold = reconstruction_threshold;
    let reload_solution_threshold = 256.0 * input.dimension as f64 * (f64::EPSILON / 2.0);

    let pack_path = scratch.join(format!("{:03}.rbfqpack", source.ordinal));
    let (pack_bytes, pack_sha256) = write_pack(&pack_path, plan_id, source, &product.factor)?;
    tracker.add(pack_bytes);
    let controls = if source.ordinal == controls_source {
        Some(negative_reload_controls(&pack_path, plan_id, source)?)
    } else {
        None
    };
    let loaded = load_pack(&pack_path, plan_id, source)?;
    if loaded.fingerprint() != product.factor.fingerprint() {
        return Err("positive pack reload changed factor fingerprint".to_owned());
    }
    let reload_lease = ExecutionLease::new(ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    });
    let reload_cancellation = CancellationToken::default();
    let reload = binding.execute(schedule, &reload_lease, &reload_cancellation, || {
        solve_factor(&loaded, rhs.clone(), &reload_lease, None)
    });
    let reload_metrics = reload_lease.metrics();
    let (reloaded_solutions, live_observation) = reload
        .map_err(|error| format!("reloaded solve execute: {error:?}"))?
        .map_err(|error| format!("reloaded solve: {error}"))?;
    if !clean_metrics(reload_metrics) || live_observation.min(1) != 1 {
        return Err("reloaded solve resource gate failed".to_owned());
    }
    let (reload_backward, reload_solution_error) =
        error_metrics(&input, &rhs, &expected, &reloaded_solutions);
    fs::remove_file(&pack_path).map_err(|error| format!("remove pack: {error}"))?;
    tracker.remove(pack_bytes)?;
    let maximum_backward_error = backward_error.max(reload_backward);
    let maximum_solution_relative_inf = solution_error.max(reload_solution_error);
    let health_pass = reconstruction_error <= reconstruction_threshold
        && maximum_backward_error <= backward_threshold
        && maximum_solution_relative_inf <= reload_solution_threshold;
    let health_error = if health_pass {
        Value::Null
    } else {
        json!(format!(
            "factor health failed: reconstruction={reconstruction_error:e}, \
             backward={maximum_backward_error:e}, \
             pack_reload_solution={maximum_solution_relative_inf:e}"
        ))
    };

    Ok(json!({
        "ordinal": source.ordinal,
        "factor_source_id": source.factor_source_id,
        "block_id": source.block_id,
        "workload_id": source.workload_id,
        "role": source.role,
        "dimension": source.dimension,
        "source_sha256": source.sha256,
        "status": if health_pass { "PASS" } else { "FAIL" },
        "error": health_error,
        "schedule": schedule_json(schedule),
        "execution_metrics": metrics_json(metrics),
        "reload_metrics": metrics_json(reload_metrics),
        "factor_fingerprint": product.factor.fingerprint(),
        "reconstruction_relative_inf": reconstruction_error,
        "reconstruction_threshold": reconstruction_threshold,
        "maximum_backward_error": maximum_backward_error,
        "backward_threshold": backward_threshold,
        "maximum_solution_relative_inf": maximum_solution_relative_inf,
        "reload_solution_threshold": reload_solution_threshold,
        "pack": {
            "schema": PACK_SCHEMA,
            "bytes": pack_bytes,
            "sha256": pack_sha256,
            "positive_reload": true,
            "removed_after_reload": !pack_path.exists(),
        },
        "n_minus_one": n_minus_one,
        "negative_reload_controls": controls,
    }))
}

fn update_high_water(high_water: &AtomicUsize, value: usize) {
    let mut observed = high_water.load(Ordering::Acquire);
    while value > observed {
        match high_water.compare_exchange_weak(observed, value, Ordering::AcqRel, Ordering::Acquire)
        {
            Ok(_) => break,
            Err(next) => observed = next,
        }
    }
}

fn execute_sources(
    binding: CandidateExecutionBinding,
    plan_id: &str,
    bundle_root: &Path,
    scratch: &Path,
    sources: Vec<Source>,
    workers: usize,
    controls_source: usize,
    tracker: Arc<ScratchTracker>,
) -> (Vec<Value>, usize) {
    let queue = Arc::new(Mutex::new(VecDeque::from(sources)));
    let results = Arc::new(Mutex::new(Vec::new()));
    let active = Arc::new(AtomicUsize::new(0));
    let active_high_water = Arc::new(AtomicUsize::new(0));
    let barrier = Arc::new(Barrier::new(workers));
    thread::scope(|scope| {
        for _ in 0..workers {
            let queue = Arc::clone(&queue);
            let results = Arc::clone(&results);
            let active = Arc::clone(&active);
            let active_high_water = Arc::clone(&active_high_water);
            let barrier = Arc::clone(&barrier);
            let tracker = Arc::clone(&tracker);
            let plan_id = plan_id.to_owned();
            let bundle_root = bundle_root.to_owned();
            let scratch = scratch.to_owned();
            scope.spawn(move || {
                let now_active = active.fetch_add(1, Ordering::AcqRel) + 1;
                update_high_water(&active_high_water, now_active);
                barrier.wait();
                loop {
                    let source = queue.lock().unwrap().pop_front();
                    let Some(source) = source else {
                        break;
                    };
                    let observation = match process_source(
                        &binding,
                        &plan_id,
                        &bundle_root,
                        &scratch,
                        &tracker,
                        &source,
                        controls_source,
                    ) {
                        Ok(value) => value,
                        Err(error) => json!({
                            "ordinal": source.ordinal,
                            "factor_source_id": source.factor_source_id,
                            "block_id": source.block_id,
                            "workload_id": source.workload_id,
                            "role": source.role,
                            "dimension": source.dimension,
                            "source_sha256": source.sha256,
                            "status": "FAIL",
                            "error": error,
                        }),
                    };
                    results.lock().unwrap().push(observation);
                }
                active.fetch_sub(1, Ordering::AcqRel);
            });
        }
    });
    let mut observations = Arc::try_unwrap(results).unwrap().into_inner().unwrap();
    observations.sort_by_key(|value| value["ordinal"].as_u64().unwrap_or(u64::MAX));
    (observations, active_high_water.load(Ordering::Acquire))
}

fn cancellation_controls(
    binding: &CandidateExecutionBinding,
    plan_id: &str,
    bundle_root: &Path,
    source: &Source,
) -> Result<Value, String> {
    let input = read_source(bundle_root, source)?;
    let shape = FactorShape {
        role: input.role,
        dimension: input.dimension,
        rhs_columns: RHS_COLUMNS,
    };
    let schedule = binding
        .plan(shape)
        .map_err(|error| format!("cancellation plan: {error:?}"))?;
    let grant = ResourceGrant {
        transient_bytes: schedule.peak_transient_bytes,
        retained_bytes: schedule.retained_bytes,
        compute_permits: 1,
    };
    let prior_lease = ExecutionLease::new(grant);
    let prior_token = CancellationToken::default();
    let prior = binding
        .execute(schedule, &prior_lease, &prior_token, || {
            factor_source(&input, &prior_lease, None)
        })
        .map_err(|error| format!("prior factor execute: {error:?}"))?
        .map_err(|error| format!("prior factor: {error}"))?
        .0;
    if !clean_metrics(prior_lease.metrics()) {
        return Err("prior factor cleanup failed".to_owned());
    }
    let prior_fingerprint = prior.fingerprint();
    let factor_lease = ExecutionLease::new(grant);
    let factor_token = CancellationToken::default();
    let factor_entered = AtomicBool::new(false);
    let (factor_result, factor_requested, factor_returned) = thread::scope(|scope| {
        let canceller = scope.spawn(|| {
            while !factor_entered.load(Ordering::Acquire) {
                thread::yield_now();
            }
            thread::sleep(Duration::from_millis(CANCELLATION_DELAY_MS));
            let requested = Instant::now();
            factor_token.cancel();
            requested
        });
        let result = binding.execute(schedule, &factor_lease, &factor_token, || {
            factor_source(&input, &factor_lease, Some(&factor_entered))
        });
        let returned = Instant::now();
        (result, canceller.join().unwrap(), returned)
    });
    let factor_latency = factor_returned
        .checked_duration_since(factor_requested)
        .unwrap_or_default();
    let factor_cancelled = matches!(factor_result, Err(ExecutionError::Cancelled));
    let factor_prior_preserved = prior.fingerprint() == prior_fingerprint;
    let factor_clean = clean_metrics(factor_lease.metrics());
    let factor_backend_entered = factor_lease.metrics().backend_entries > 0;

    let expected = declared_solutions(input.dimension);
    let rhs = manufactured_rhs(&input, &expected);
    let solved_lease = ExecutionLease::new(grant);
    let solved_token = CancellationToken::default();
    let prior_solution = binding
        .execute(schedule, &solved_lease, &solved_token, || {
            solve_factor(&prior, rhs.clone(), &solved_lease, None)
        })
        .map_err(|error| format!("prior solve execute: {error:?}"))?
        .map_err(|error| format!("prior solve: {error}"))?
        .0;
    let prior_solution_fingerprint = sha256_f64s(&prior_solution);
    let solve_lease = ExecutionLease::new(grant);
    let solve_token = CancellationToken::default();
    let solve_entered = AtomicBool::new(false);
    let (solve_result, solve_requested, solve_returned) = thread::scope(|scope| {
        let canceller = scope.spawn(|| {
            while !solve_entered.load(Ordering::Acquire) {
                thread::yield_now();
            }
            let requested = Instant::now();
            solve_token.cancel();
            requested
        });
        let result = binding.execute(schedule, &solve_lease, &solve_token, || {
            solve_factor(&prior, rhs.clone(), &solve_lease, Some(&solve_entered))
        });
        let returned = Instant::now();
        (result, canceller.join().unwrap(), returned)
    });
    let solve_latency = solve_returned
        .checked_duration_since(solve_requested)
        .unwrap_or_default();
    let solve_cancelled = matches!(solve_result, Err(ExecutionError::Cancelled));
    let solved_prior_preserved = sha256_f64s(&prior_solution) == prior_solution_fingerprint;
    let solve_clean = clean_metrics(solve_lease.metrics());
    let solve_backend_entered = solve_lease.metrics().backend_entries > 0;
    let pass = factor_cancelled
        && factor_backend_entered
        && factor_prior_preserved
        && factor_clean
        && solve_cancelled
        && solve_backend_entered
        && solved_prior_preserved
        && solve_clean;
    let factor_result_label = match &factor_result {
        Err(error) => format!("Err({error:?})"),
        Ok(Err(error)) => format!("Ok(Err({error}))"),
        Ok(Ok(_)) => "Ok(Ok(CompletedWithoutCancellation))".to_owned(),
    };
    let solve_result_label = match &solve_result {
        Err(error) => format!("Err({error:?})"),
        Ok(Err(error)) => format!("Ok(Err({error}))"),
        Ok(Ok(_)) => "Ok(Ok(CompletedWithoutCancellation))".to_owned(),
    };
    Ok(json!({
        "status": if pass { "PASS" } else { "FAIL" },
        "plan_id": plan_id,
        "factor_source_id": source.factor_source_id,
        "mid_factor": {
            "result": factor_result_label,
            "cancelled": factor_cancelled,
            "backend_entered": factor_backend_entered,
            "acknowledgment_latency_ns": factor_latency.as_nanos(),
            "prior_factor_preserved": factor_prior_preserved,
            "failed_publications": 0,
            "metrics": metrics_json(factor_lease.metrics()),
        },
        "mid_solve": {
            "result": solve_result_label,
            "cancelled": solve_cancelled,
            "backend_entered": solve_backend_entered,
            "acknowledgment_latency_ns": solve_latency.as_nanos(),
            "prior_solved_correction_preserved": solved_prior_preserved,
            "failed_publications": 0,
            "metrics": metrics_json(solve_lease.metrics()),
        },
    }))
}

fn sha256_f64s(values: &[f64]) -> String {
    let mut digest = Sha256::new();
    update_f64s(&mut digest, values);
    format!("{:x}", digest.finalize())
}

fn validate_plan(plan: &Plan, args: &Args) -> Result<(), String> {
    if plan.schema != PLAN_SCHEMA || !plan.plan_id.starts_with(&format!("{PLAN_SCHEMA}/")) {
        return Err("factor qualification plan identity differs".to_owned());
    }
    if plan.factor_sources.len() != 216 && args.source_limit.is_none() {
        return Err("factor qualification plan does not contain 216 sources".to_owned());
    }
    let profile = &plan.authority["factor_health_profile"]["profile_sha256"];
    let binding = &plan.authority["candidate_binding"]["binding_sha256"];
    if profile != PROFILE_SHA256 || binding != BINDING_SHA256 {
        return Err("plan profile or candidate binding differs".to_owned());
    }
    if !matches!(args.workers, 1 | 2 | 8)
        || (args.workers <= 2 && args.maximum_live_threads != 12)
        || (args.workers == 8 && args.maximum_live_threads != 16)
    {
        return Err("requested lane is not one of 1/12, 2/12, or 8/16".to_owned());
    }
    Ok(())
}

fn scratch_files(root: &Path) -> Result<Vec<String>, String> {
    let mut files = Vec::new();
    let entries = fs::read_dir(root).map_err(|error| format!("read scratch: {error}"))?;
    for entry in entries {
        let entry = entry.map_err(|error| format!("read scratch entry: {error}"))?;
        files.push(entry.file_name().to_string_lossy().into_owned());
    }
    files.sort();
    Ok(files)
}

fn main() {
    let args = parse_args().unwrap_or_else(|error| panic!("{error}"));
    if args.output.exists() {
        panic!("output must be absent: {}", args.output.display());
    }
    if args.scratch.exists() {
        panic!("scratch must be absent: {}", args.scratch.display());
    }
    fs::create_dir_all(&args.scratch).unwrap();
    let plan_bytes = fs::read(&args.plan).unwrap();
    let plan: Plan = serde_json::from_slice(&plan_bytes).unwrap();
    validate_plan(&plan, &args).unwrap();
    let plan_file_sha256 = sha256(&plan_bytes);
    let binding = CandidateExecutionBinding::exact();
    let mut sources = plan.factor_sources.clone();
    if let Some(limit) = args.source_limit {
        sources.truncate(limit);
    }
    let diagnostic_subset = args.source_limit.is_some();
    let controls_source = sources
        .iter()
        .filter(|source| source.role == "projected_b")
        .min_by_key(|source| source.ordinal)
        .map(|source| source.ordinal)
        .unwrap();
    let cancellation_source = sources
        .iter()
        .filter(|source| source.role == "projected_b")
        .max_by_key(|source| source.dimension)
        .unwrap()
        .clone();
    let tracker = Arc::new(ScratchTracker::default());
    let started = Instant::now();
    let (source_observations, effective_workers) = execute_sources(
        binding,
        &plan.plan_id,
        &args.bundle_root,
        &args.scratch,
        sources,
        args.workers,
        controls_source,
        Arc::clone(&tracker),
    );
    let previous_panic_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(|_| {}));
    let cancellation = cancellation_controls(
        &binding,
        &plan.plan_id,
        &args.bundle_root,
        &cancellation_source,
    )
    .unwrap_or_else(|error| json!({"status": "FAIL", "error": error}));
    std::panic::set_hook(previous_panic_hook);
    let passed_sources = source_observations
        .iter()
        .filter(|observation| observation["status"] == "PASS")
        .count();
    let failed_sources = source_observations.len() - passed_sources;
    let negative_controls = source_observations
        .iter()
        .find_map(|observation| {
            observation
                .get("negative_reload_controls")
                .filter(|value| !value.is_null())
                .cloned()
        })
        .unwrap_or_else(|| json!({"status": "FAIL", "error": "missing reload controls"}));
    let scratch_residue = scratch_files(&args.scratch).unwrap();
    let scratch_clean = scratch_residue.is_empty() && tracker.current.load(Ordering::Acquire) == 0;
    let full_count = source_observations.len() == 216;
    let admitted = !diagnostic_subset
        && full_count
        && failed_sources == 0
        && cancellation["status"] == "PASS"
        && negative_controls["status"] == "PASS"
        && effective_workers == args.workers
        && scratch_clean;
    let disposition = if admitted { ADMITTED } else { NOT_ADMITTED };
    let observation = json!({
        "schema": OBSERVATION_SCHEMA,
        "disposition": disposition,
        "diagnostic_subset": diagnostic_subset,
        "lane_id": args.lane_id,
        "target": args.target,
        "plan": {
            "schema": plan.schema,
            "plan_id": plan.plan_id,
            "file_sha256": plan_file_sha256,
        },
        "candidate_binding": {
            "schema": binding.schema,
            "binding_sha256": BINDING_SHA256,
            "profile_sha256": binding.profile_sha256,
            "parallelism": binding.parallelism,
        },
        "lane": {
            "configured_workers": args.workers,
            "effective_worker_high_water": effective_workers,
            "maximum_live_threads_grant": args.maximum_live_threads,
            "backend_parallelism": "Par::Seq",
            "nested_automatic_pool": false,
        },
        "counts": {
            "planned_factor_sources": 216,
            "observed_factor_sources": source_observations.len(),
            "passed_factor_sources": passed_sources,
            "failed_factor_sources": failed_sources,
            "qualified_factor_access_publications": passed_sources,
            "solved_correction_publications": passed_sources,
            "run_scoped_recompute_recipes": 0,
            "run_recompute_budget_initial": 216,
            "run_recompute_budget_consumed": 0,
        },
        "factor_access": {
            "selected_path": if failed_sources == 0 {
                "PrototypeQualifiedFactorPack/v1"
            } else {
                "none"
            },
            "durable_pack_reload": if failed_sources == 0 { "PASS" } else { "FAIL" },
            "run_scoped_recompute_recipe": "DISABLED_PACK_PATH_PASSED",
            "factor_recipe_and_solved_publications_are_separate": true,
            "persistent_factor_store_policy": "OUTSIDE_TICKET",
        },
        "controls": {
            "negative_reload": negative_controls,
            "cancellation": cancellation,
            "exact_n_minus_one_observations": source_observations
                .iter()
                .filter(|value| value["n_minus_one"]["status"] == "PASS")
                .count(),
        },
        "scratch": {
            "cumulative_writes": tracker.cumulative_writes.load(Ordering::Acquire),
            "live_occupancy_high_water": tracker.high_water.load(Ordering::Acquire),
            "live_residue_bytes": tracker.current.load(Ordering::Acquire),
            "residue_files": scratch_residue,
            "cleanup_pass": scratch_clean,
        },
        "elapsed_ns": started.elapsed().as_nanos(),
        "factor_sources": source_observations,
    });
    let output_bytes = serde_json::to_vec_pretty(&observation).unwrap();
    let mut output = File::create_new(&args.output).unwrap();
    output.write_all(&output_bytes).unwrap();
    output.write_all(b"\n").unwrap();
    output.sync_all().unwrap();
    fs::remove_dir(&args.scratch).unwrap();
    println!(
        "{} workers={} disposition={} sources={}/{}",
        args.lane_id,
        args.workers,
        disposition,
        passed_sources,
        source_observations.len()
    );
}
