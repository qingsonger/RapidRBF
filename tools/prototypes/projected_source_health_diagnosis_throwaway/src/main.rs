//! THROWAWAY PROTOTYPE: diagnose issue-41 projected-source forward-health failures.
//!
//! The program consumes only hash-verified issue-41 source bytes. It compares
//! the exact candidate LDLT route with byte round-trip, symmetric equilibration,
//! an independent full-pivot LU route, and double-double-residual refinement.

use dyn_stack::{MemBuffer, MemStack};
use faer::diag::{DiagMut, DiagRef};
use faer::linalg::cholesky::lblt;
use faer::linalg::lu::full_pivoting;
use faer::perm::PermRef;
use faer::prelude::ReborrowMut;
use faer::{MatMut, MatRef, Par};
use qd::Quad;
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::mem::size_of;
use std::path::{Path, PathBuf};

const OUTPUT_SCHEMA: &str = "RapidRBF/ProjectedSourceHealthDiagnosisEvidence/v1";
const DIAGNOSIS_SCHEMA: &str = "RapidRBF/ProjectedSourceHealthDiagnosisPlan/v1";
const ISSUE_41_PLAN_SCHEMA: &str = "RapidRBF/FactorQualificationPlan/v1";
const RHS_COLUMNS: usize = 3;
const FAMILY_NAMES: [&str; RHS_COLUMNS] = ["operational", "constraint", "dynamic-range"];
const MAX_REFINEMENT_STEPS: usize = 12;

#[derive(Debug)]
struct Args {
    diagnosis_plan: PathBuf,
    issue_41_plan: PathBuf,
    bundle_root: PathBuf,
    output: PathBuf,
}

#[derive(Debug, Deserialize)]
struct DiagnosisPlan {
    schema: String,
    authorities: serde_json::Value,
    samples: Vec<Sample>,
}

#[derive(Clone, Debug, Deserialize)]
struct Sample {
    ordinal: usize,
    category: String,
    workload_id: String,
    dimension: usize,
    source_sha256: String,
    archived_status: String,
    archived_solution_relative_inf: f64,
    solution_threshold: f64,
}

#[derive(Debug, Deserialize)]
struct Issue41Plan {
    schema: String,
    plan_id: String,
    factor_sources: Vec<Source>,
}

#[derive(Clone, Debug, Deserialize)]
struct Source {
    ordinal: usize,
    factor_source_id: String,
    workload_id: String,
    role: String,
    bundle_path: String,
    bytes: usize,
    sha256: String,
    encoding: String,
    dimension: usize,
}

#[derive(Clone, Debug)]
struct LbltFactor {
    matrix: Vec<f64>,
    subdiag: Vec<f64>,
    perm: Vec<usize>,
    perm_inv: Vec<usize>,
}

#[derive(Clone, Debug)]
struct FullLuFactor {
    matrix: Vec<f64>,
    row_perm: Vec<usize>,
    row_perm_inv: Vec<usize>,
    col_perm: Vec<usize>,
    col_perm_inv: Vec<usize>,
}

#[derive(Debug, Serialize)]
struct FamilyMetrics {
    family: &'static str,
    backward_error: f64,
    declared_solution_relative_inf: f64,
}

#[derive(Debug, Serialize)]
struct RouteMetrics {
    maximum_backward_error: f64,
    maximum_declared_solution_relative_inf: f64,
    families: Vec<FamilyMetrics>,
}

#[derive(Debug, Serialize)]
struct RefinementSummary {
    steps: usize,
    correction_relative_inf_history: Vec<f64>,
    backward_error_history: Vec<f64>,
    maximum_backward_error: f64,
    maximum_declared_solution_relative_inf: f64,
}

#[derive(Debug)]
struct RefinedSolution {
    values: Vec<Quad>,
    summary: RefinementSummary,
}

fn parse_args() -> Result<Args, String> {
    let mut diagnosis_plan = None;
    let mut issue_41_plan = None;
    let mut bundle_root = None;
    let mut output = None;
    let mut args = std::env::args().skip(1);
    while let Some(argument) = args.next() {
        let value = args
            .next()
            .ok_or_else(|| format!("{argument} requires a value"))?;
        match argument.as_str() {
            "--diagnosis-plan" => diagnosis_plan = Some(PathBuf::from(value)),
            "--issue-41-plan" => issue_41_plan = Some(PathBuf::from(value)),
            "--bundle-root" => bundle_root = Some(PathBuf::from(value)),
            "--output" => output = Some(PathBuf::from(value)),
            _ => return Err(format!("unknown argument {argument}")),
        }
    }
    Ok(Args {
        diagnosis_plan: diagnosis_plan.ok_or("--diagnosis-plan is required")?,
        issue_41_plan: issue_41_plan.ok_or("--issue-41-plan is required")?,
        bundle_root: bundle_root.ok_or("--bundle-root is required")?,
        output: output.ok_or("--output is required")?,
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

fn read_projected_matrix(bundle_root: &Path, source: &Source) -> Result<Vec<f64>, String> {
    if source.role != "projected_b"
        || source.encoding != "lower-triangle-row-major-packed"
        || source.bundle_path.contains("..")
        || Path::new(&source.bundle_path).is_absolute()
    {
        return Err(format!(
            "{} is not a valid projected diagnosis source",
            source.factor_source_id
        ));
    }
    let path = bundle_root.join(&source.bundle_path);
    let bytes = fs::read(&path).map_err(|error| format!("read {}: {error}", path.display()))?;
    if bytes.len() != source.bytes || sha256(&bytes) != source.sha256 {
        return Err(format!(
            "{} source bytes or SHA-256 differ",
            source.factor_source_id
        ));
    }
    let n = source.dimension;
    let expected = n
        .checked_mul(n + 1)
        .and_then(|value| value.checked_div(2))
        .and_then(|value| value.checked_mul(size_of::<f64>()))
        .ok_or("projected source size overflow")?;
    if bytes.len() != expected {
        return Err(format!(
            "{} packed source shape differs",
            source.factor_source_id
        ));
    }
    let mut matrix = vec![0.0_f64; n * n];
    let mut cursor = 0;
    for row in 0..n {
        for column in 0..=row {
            let offset = cursor * size_of::<f64>();
            let value =
                f64::from_le_bytes(bytes[offset..offset + size_of::<f64>()].try_into().unwrap());
            matrix[row + column * n] = value;
            matrix[column + row * n] = value;
            cursor += 1;
        }
    }
    Ok(matrix)
}

fn declared_solutions(n: usize) -> Vec<f64> {
    let mut solutions = vec![0.0; n * RHS_COLUMNS];
    for row in 0..n {
        solutions[row] = 1.0 + (row % 17) as f64 / 17.0;
        solutions[row + n] = if row % 2 == 0 { 1.0 } else { -1.0 };
        let exponent = (row % 21) as i32 - 10;
        let sign = if row % 2 == 0 { 1.0 } else { -1.0 };
        solutions[row + 2 * n] = sign * 2.0_f64.powi(exponent);
    }
    solutions
}

fn manufactured_rhs_f64(matrix: &[f64], solutions: &[f64], n: usize) -> Vec<f64> {
    let mut rhs = vec![0.0; n * RHS_COLUMNS];
    for family in 0..RHS_COLUMNS {
        let offset = family * n;
        for row in 0..n {
            let mut sum = 0.0_f64;
            for column in 0..n {
                sum += matrix[row + column * n] * solutions[offset + column];
            }
            rhs[offset + row] = sum;
        }
    }
    rhs
}

fn exact_rhs_quad(matrix: &[f64], solutions: &[f64], n: usize) -> Vec<Quad> {
    let mut rhs = vec![Quad::ZERO; n * RHS_COLUMNS];
    for family in 0..RHS_COLUMNS {
        let offset = family * n;
        for row in 0..n {
            let mut sum = Quad::ZERO;
            for column in 0..n {
                let product = Quad::from_f64(matrix[row + column * n])
                    .mul(Quad::from_f64(solutions[offset + column]));
                sum = sum.add_accurate(product);
            }
            rhs[offset + row] = sum;
        }
    }
    rhs
}

fn factor_lblt(matrix: &[f64], n: usize) -> LbltFactor {
    let mut factor = matrix.to_vec();
    let mut subdiag = vec![0.0_f64; n];
    let mut perm = vec![0_usize; n];
    let mut perm_inv = vec![0_usize; n];
    let request =
        lblt::factor::cholesky_in_place_scratch::<usize, f64>(n, Par::Seq, Default::default());
    let mut memory = MemBuffer::new(request);
    let mut stack = MemStack::new(&mut memory);
    let matrix_view = MatMut::from_column_major_slice_mut(&mut factor, n, n);
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
    LbltFactor {
        matrix: factor,
        subdiag,
        perm,
        perm_inv,
    }
}

fn solve_lblt(factor: &LbltFactor, rhs: &[f64], n: usize, columns: usize) -> Vec<f64> {
    let mut solution = rhs.to_vec();
    let request = lblt::solve::solve_in_place_scratch::<usize, f64>(n, columns, Par::Seq);
    let mut memory = MemBuffer::new(request);
    let mut stack = MemStack::new(&mut memory);
    let matrix = MatRef::from_column_major_slice(&factor.matrix, n, n);
    let permutation = PermRef::new_checked(&factor.perm, &factor.perm_inv, n);
    let mut solution_view = MatMut::from_column_major_slice_mut(&mut solution, n, columns);
    lblt::solve::solve_in_place(
        matrix,
        matrix.diagonal(),
        DiagRef::from_slice(&factor.subdiag),
        permutation,
        solution_view.rb_mut(),
        Par::Seq,
        &mut stack,
    );
    solution
}

fn factor_full_lu(matrix: &[f64], n: usize) -> FullLuFactor {
    let mut factor = matrix.to_vec();
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
    let mut memory = MemBuffer::new(request);
    let mut stack = MemStack::new(&mut memory);
    let matrix_view = MatMut::from_column_major_slice_mut(&mut factor, n, n);
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
    FullLuFactor {
        matrix: factor,
        row_perm,
        row_perm_inv,
        col_perm,
        col_perm_inv,
    }
}

fn solve_full_lu(factor: &FullLuFactor, rhs: &[f64], n: usize, columns: usize) -> Vec<f64> {
    let mut solution = rhs.to_vec();
    let request = full_pivoting::solve::solve_in_place_scratch::<usize, f64>(n, columns, Par::Seq);
    let mut memory = MemBuffer::new(request);
    let mut stack = MemStack::new(&mut memory);
    let matrix = MatRef::from_column_major_slice(&factor.matrix, n, n);
    let row = PermRef::new_checked(&factor.row_perm, &factor.row_perm_inv, n);
    let column = PermRef::new_checked(&factor.col_perm, &factor.col_perm_inv, n);
    let mut solution_view = MatMut::from_column_major_slice_mut(&mut solution, n, columns);
    full_pivoting::solve::solve_in_place(
        matrix,
        matrix,
        row,
        column,
        solution_view.rb_mut(),
        Par::Seq,
        &mut stack,
    );
    solution
}

fn matrix_inf(matrix: &[f64], n: usize) -> f64 {
    let mut maximum = 0.0_f64;
    for row in 0..n {
        let mut sum = 0.0_f64;
        for column in 0..n {
            sum += matrix[row + column * n].abs();
        }
        maximum = maximum.max(sum);
    }
    maximum
}

fn route_metrics(
    matrix: &[f64],
    rhs: &[f64],
    declared: &[f64],
    observed: &[f64],
    n: usize,
) -> RouteMetrics {
    let matrix_norm = matrix_inf(matrix, n);
    let mut families = Vec::new();
    let mut maximum_backward = 0.0_f64;
    let mut maximum_solution = 0.0_f64;
    for (family, name) in FAMILY_NAMES.iter().enumerate() {
        let offset = family * n;
        let mut residual_inf = 0.0_f64;
        let mut solution_inf = 0.0_f64;
        let mut rhs_inf = 0.0_f64;
        let mut difference_inf = 0.0_f64;
        let mut expected_inf = 0.0_f64;
        for row in 0..n {
            let mut action = 0.0_f64;
            for column in 0..n {
                action += matrix[row + column * n] * observed[offset + column];
            }
            residual_inf = residual_inf.max((action - rhs[offset + row]).abs());
            solution_inf = solution_inf.max(observed[offset + row].abs());
            rhs_inf = rhs_inf.max(rhs[offset + row].abs());
            difference_inf =
                difference_inf.max((observed[offset + row] - declared[offset + row]).abs());
            expected_inf = expected_inf.max(declared[offset + row].abs());
        }
        let backward = residual_inf / (matrix_norm * solution_inf + rhs_inf).max(f64::MIN_POSITIVE);
        let solution = difference_inf / expected_inf.max(1.0);
        maximum_backward = maximum_backward.max(backward);
        maximum_solution = maximum_solution.max(solution);
        families.push(FamilyMetrics {
            family: name,
            backward_error: backward,
            declared_solution_relative_inf: solution,
        });
    }
    RouteMetrics {
        maximum_backward_error: maximum_backward,
        maximum_declared_solution_relative_inf: maximum_solution,
        families,
    }
}

fn quad_abs(value: Quad) -> f64 {
    (value.0 + value.1).abs()
}

fn quad_residual(
    matrix: &[f64],
    rhs: &[Quad],
    solution: &[Quad],
    n: usize,
    columns: usize,
) -> Vec<Quad> {
    let mut residual = vec![Quad::ZERO; n * columns];
    for family in 0..columns {
        let offset = family * n;
        for row in 0..n {
            let mut action = Quad::ZERO;
            for column in 0..n {
                let product =
                    Quad::from_f64(matrix[row + column * n]).mul(solution[offset + column]);
                action = action.add_accurate(product);
            }
            residual[offset + row] = rhs[offset + row].sub_accurate(action);
        }
    }
    residual
}

fn quad_backward(matrix: &[f64], rhs: &[Quad], solution: &[Quad], n: usize, columns: usize) -> f64 {
    let residual = quad_residual(matrix, rhs, solution, n, columns);
    let matrix_norm = matrix_inf(matrix, n);
    let mut maximum = 0.0_f64;
    for family in 0..columns {
        let offset = family * n;
        let mut residual_inf = 0.0_f64;
        let mut solution_inf = 0.0_f64;
        let mut rhs_inf = 0.0_f64;
        for row in 0..n {
            residual_inf = residual_inf.max(quad_abs(residual[offset + row]));
            solution_inf = solution_inf.max(quad_abs(solution[offset + row]));
            rhs_inf = rhs_inf.max(quad_abs(rhs[offset + row]));
        }
        maximum = maximum
            .max(residual_inf / (matrix_norm * solution_inf + rhs_inf).max(f64::MIN_POSITIVE));
    }
    maximum
}

fn quad_solution_relative(observed: &[Quad], expected: &[f64], n: usize, columns: usize) -> f64 {
    let mut maximum = 0.0_f64;
    for family in 0..columns {
        let offset = family * n;
        let mut difference_inf = 0.0_f64;
        let mut expected_inf = 0.0_f64;
        for row in 0..n {
            let difference =
                observed[offset + row].sub_accurate(Quad::from_f64(expected[offset + row]));
            difference_inf = difference_inf.max(quad_abs(difference));
            expected_inf = expected_inf.max(expected[offset + row].abs());
        }
        maximum = maximum.max(difference_inf / expected_inf.max(1.0));
    }
    maximum
}

fn quad_agreement(lhs: &[Quad], rhs: &[Quad], n: usize, columns: usize) -> f64 {
    let mut maximum = 0.0_f64;
    for family in 0..columns {
        let offset = family * n;
        let mut difference_inf = 0.0_f64;
        let mut scale_inf = 0.0_f64;
        for row in 0..n {
            difference_inf =
                difference_inf.max(quad_abs(lhs[offset + row].sub_accurate(rhs[offset + row])));
            scale_inf = scale_inf.max(quad_abs(lhs[offset + row]));
            scale_inf = scale_inf.max(quad_abs(rhs[offset + row]));
        }
        maximum = maximum.max(difference_inf / scale_inf.max(1.0));
    }
    maximum
}

fn refine<F>(
    matrix: &[f64],
    rhs: &[Quad],
    initial: &[f64],
    declared: &[f64],
    n: usize,
    columns: usize,
    solve_correction: F,
) -> RefinedSolution
where
    F: Fn(&[f64], usize) -> Vec<f64>,
{
    let mut solution: Vec<Quad> = initial.iter().copied().map(Quad::from_f64).collect();
    let mut correction_history = Vec::new();
    let mut backward_history = vec![quad_backward(matrix, rhs, &solution, n, columns)];
    for _ in 0..MAX_REFINEMENT_STEPS {
        let residual = quad_residual(matrix, rhs, &solution, n, columns);
        let residual_f64: Vec<f64> = residual.iter().map(|value| value.0 + value.1).collect();
        let correction = solve_correction(&residual_f64, columns);
        let mut correction_inf = 0.0_f64;
        let mut solution_inf = 0.0_f64;
        for (value, update) in solution.iter_mut().zip(correction.iter().copied()) {
            correction_inf = correction_inf.max(update.abs());
            solution_inf = solution_inf.max(quad_abs(*value));
            *value = value.add_accurate(Quad::from_f64(update));
        }
        let relative_correction = correction_inf / solution_inf.max(1.0);
        correction_history.push(relative_correction);
        let backward = quad_backward(matrix, rhs, &solution, n, columns);
        backward_history.push(backward);
        if relative_correction <= 8.0 * Quad::EPSILON.0.abs()
            || backward == 0.0
            || (backward_history.len() >= 3
                && backward >= backward_history[backward_history.len() - 2]
                && relative_correction <= f64::EPSILON)
        {
            break;
        }
    }
    let summary = RefinementSummary {
        steps: correction_history.len(),
        correction_relative_inf_history: correction_history,
        backward_error_history: backward_history,
        maximum_backward_error: quad_backward(matrix, rhs, &solution, n, columns),
        maximum_declared_solution_relative_inf: quad_solution_relative(
            &solution, declared, n, columns,
        ),
    };
    RefinedSolution {
        values: solution,
        summary,
    }
}

fn lblt_fingerprint(factor: &LbltFactor) -> String {
    let mut digest = Sha256::new();
    digest.update(b"projected_b\0");
    update_f64s(&mut digest, &factor.matrix);
    update_f64s(&mut digest, &factor.subdiag);
    update_usizes(&mut digest, &factor.perm);
    update_usizes(&mut digest, &factor.perm_inv);
    format!("{:x}", digest.finalize())
}

fn serialize_lblt(factor: &LbltFactor) -> Vec<u8> {
    let mut bytes = Vec::new();
    for values in [&factor.matrix, &factor.subdiag] {
        for value in values {
            bytes.extend_from_slice(&value.to_bits().to_le_bytes());
        }
    }
    for values in [&factor.perm, &factor.perm_inv] {
        for value in values {
            bytes.extend_from_slice(&(*value as u64).to_le_bytes());
        }
    }
    bytes
}

fn deserialize_lblt(bytes: &[u8], n: usize) -> Result<LbltFactor, String> {
    let f64_count = n * n + n;
    let usize_count = 2 * n;
    let expected = (f64_count + usize_count) * 8;
    if bytes.len() != expected {
        return Err("serialized LDLT payload length differs".to_owned());
    }
    let mut cursor = 0;
    let mut read_f64 = |count: usize| {
        let mut values = Vec::with_capacity(count);
        for _ in 0..count {
            let value = f64::from_bits(u64::from_le_bytes(
                bytes[cursor..cursor + 8].try_into().unwrap(),
            ));
            cursor += 8;
            values.push(value);
        }
        values
    };
    let matrix = read_f64(n * n);
    let subdiag = read_f64(n);
    let mut read_usize = |count: usize| -> Result<Vec<usize>, String> {
        let mut values = Vec::with_capacity(count);
        for _ in 0..count {
            let value = u64::from_le_bytes(bytes[cursor..cursor + 8].try_into().unwrap());
            cursor += 8;
            values.push(usize::try_from(value).map_err(|_| "serialized index does not fit usize")?);
        }
        Ok(values)
    };
    let perm = read_usize(n)?;
    let perm_inv = read_usize(n)?;
    Ok(LbltFactor {
        matrix,
        subdiag,
        perm,
        perm_inv,
    })
}

fn bitwise_equal(lhs: &[f64], rhs: &[f64]) -> bool {
    lhs.len() == rhs.len()
        && lhs
            .iter()
            .zip(rhs)
            .all(|(left, right)| left.to_bits() == right.to_bits())
}

fn equilibrate(matrix: &[f64], n: usize) -> (Vec<f64>, Vec<f64>) {
    let mut scale = vec![1.0_f64; n];
    for row in 0..n {
        let mut row_max = 0.0_f64;
        for column in 0..n {
            row_max = row_max.max(matrix[row + column * n].abs());
        }
        if row_max > 0.0 {
            scale[row] = row_max.sqrt().recip();
        }
    }
    let mut scaled = vec![0.0_f64; n * n];
    for row in 0..n {
        for column in 0..n {
            scaled[row + column * n] = scale[row] * matrix[row + column * n] * scale[column];
        }
    }
    (scaled, scale)
}

fn solve_scaled_lblt(
    factor: &LbltFactor,
    scale: &[f64],
    rhs: &[f64],
    n: usize,
    columns: usize,
) -> Vec<f64> {
    let mut scaled_rhs = rhs.to_vec();
    for family in 0..columns {
        for row in 0..n {
            scaled_rhs[row + family * n] *= scale[row];
        }
    }
    let mut solution = solve_lblt(factor, &scaled_rhs, n, columns);
    for family in 0..columns {
        for row in 0..n {
            solution[row + family * n] *= scale[row];
        }
    }
    solution
}

fn main() {
    if let Err(error) = real_main() {
        panic!("{error}");
    }
}

fn real_main() -> Result<(), String> {
    let args = parse_args()?;
    if args.output.exists() {
        return Err(format!("output must be absent: {}", args.output.display()));
    }
    let diagnosis_bytes =
        fs::read(&args.diagnosis_plan).map_err(|error| format!("read diagnosis plan: {error}"))?;
    let diagnosis: DiagnosisPlan = serde_json::from_slice(&diagnosis_bytes)
        .map_err(|error| format!("parse diagnosis plan: {error}"))?;
    if diagnosis.schema != DIAGNOSIS_SCHEMA {
        return Err("diagnosis plan schema differs".to_owned());
    }
    let issue_41_bytes =
        fs::read(&args.issue_41_plan).map_err(|error| format!("read issue-41 plan: {error}"))?;
    let issue_41: Issue41Plan = serde_json::from_slice(&issue_41_bytes)
        .map_err(|error| format!("parse issue-41 plan: {error}"))?;
    if issue_41.schema != ISSUE_41_PLAN_SCHEMA || issue_41.factor_sources.len() != 216 {
        return Err("issue-41 plan identity or inventory differs".to_owned());
    }
    let sources: BTreeMap<usize, Source> = issue_41
        .factor_sources
        .into_iter()
        .map(|source| (source.ordinal, source))
        .collect();

    let mut observations = Vec::new();
    let mut all_failed_authority_witnesses = true;
    let mut pass_control_closed = true;
    let mut all_roundtrips_exact = true;
    for sample in &diagnosis.samples {
        let source = sources
            .get(&sample.ordinal)
            .ok_or_else(|| format!("missing source ordinal {}", sample.ordinal))?;
        if source.dimension != sample.dimension
            || source.sha256 != sample.source_sha256
            || source.workload_id != sample.workload_id
        {
            return Err(format!("sample {} metadata differs", sample.ordinal));
        }
        let n = source.dimension;
        let matrix = read_projected_matrix(&args.bundle_root, source)?;
        let declared = declared_solutions(n);
        let frozen_rhs = manufactured_rhs_f64(&matrix, &declared, n);
        let frozen_rhs_quad: Vec<Quad> = frozen_rhs.iter().copied().map(Quad::from_f64).collect();
        let exact_rhs = exact_rhs_quad(&matrix, &declared, n);
        let declared_quad: Vec<Quad> = declared.iter().copied().map(Quad::from_f64).collect();
        let frozen_rhs_rounding_backward =
            quad_backward(&matrix, &frozen_rhs_quad, &declared_quad, n, RHS_COLUMNS);
        let exact_rhs_declared_backward =
            quad_backward(&matrix, &exact_rhs, &declared_quad, n, RHS_COLUMNS);

        let candidate = factor_lblt(&matrix, n);
        let candidate_fingerprint = lblt_fingerprint(&candidate);
        let candidate_solution = solve_lblt(&candidate, &frozen_rhs, n, RHS_COLUMNS);
        let candidate_metrics =
            route_metrics(&matrix, &frozen_rhs, &declared, &candidate_solution, n);

        let serialized = serialize_lblt(&candidate);
        let reloaded = deserialize_lblt(&serialized, n)?;
        let reloaded_solution = solve_lblt(&reloaded, &frozen_rhs, n, RHS_COLUMNS);
        let roundtrip_factor_exact = candidate_fingerprint == lblt_fingerprint(&reloaded);
        let roundtrip_solution_exact = bitwise_equal(&candidate_solution, &reloaded_solution);
        all_roundtrips_exact &= roundtrip_factor_exact && roundtrip_solution_exact;

        let candidate_refined = refine(
            &matrix,
            &frozen_rhs_quad,
            &candidate_solution,
            &declared,
            n,
            RHS_COLUMNS,
            |residual, columns| solve_lblt(&candidate, residual, n, columns),
        );

        let full_lu = factor_full_lu(&matrix, n);
        let full_lu_solution = solve_full_lu(&full_lu, &frozen_rhs, n, RHS_COLUMNS);
        let full_lu_metrics = route_metrics(&matrix, &frozen_rhs, &declared, &full_lu_solution, n);
        let full_lu_refined = refine(
            &matrix,
            &frozen_rhs_quad,
            &full_lu_solution,
            &declared,
            n,
            RHS_COLUMNS,
            |residual, columns| solve_full_lu(&full_lu, residual, n, columns),
        );

        let (scaled_matrix, scale) = equilibrate(&matrix, n);
        let scaled_factor = factor_lblt(&scaled_matrix, n);
        let scaled_solution =
            solve_scaled_lblt(&scaled_factor, &scale, &frozen_rhs, n, RHS_COLUMNS);
        let scaled_metrics = route_metrics(&matrix, &frozen_rhs, &declared, &scaled_solution, n);
        let scaled_refined = refine(
            &matrix,
            &frozen_rhs_quad,
            &scaled_solution,
            &declared,
            n,
            RHS_COLUMNS,
            |residual, columns| solve_scaled_lblt(&scaled_factor, &scale, residual, n, columns),
        );

        let reference_agreement = quad_agreement(
            &candidate_refined.values,
            &full_lu_refined.values,
            n,
            RHS_COLUMNS,
        );
        let reference_declared_error = candidate_refined
            .summary
            .maximum_declared_solution_relative_inf
            .max(
                full_lu_refined
                    .summary
                    .maximum_declared_solution_relative_inf,
            );
        let best_route_declared_error = candidate_refined
            .summary
            .maximum_declared_solution_relative_inf
            .min(
                full_lu_refined
                    .summary
                    .maximum_declared_solution_relative_inf,
            )
            .min(
                scaled_refined
                    .summary
                    .maximum_declared_solution_relative_inf,
            );
        let backward_threshold = 64.0 * n as f64 * (f64::EPSILON / 2.0);
        let reference_agreement_limit = sample.solution_threshold / 16.0;
        let independent_reference_closed = reference_agreement <= reference_agreement_limit
            && candidate_refined.summary.maximum_backward_error <= backward_threshold
            && full_lu_refined.summary.maximum_backward_error <= backward_threshold;
        let authority_defect_witness = sample.archived_status == "FAIL"
            && independent_reference_closed
            && reference_declared_error > sample.solution_threshold;
        let candidate_local_remedy_pass = best_route_declared_error <= sample.solution_threshold;
        if sample.archived_status == "FAIL" {
            all_failed_authority_witnesses &= authority_defect_witness;
        } else {
            pass_control_closed &= independent_reference_closed
                && reference_declared_error <= sample.solution_threshold;
        }
        let directional_amplification = if frozen_rhs_rounding_backward > 0.0 {
            reference_declared_error / frozen_rhs_rounding_backward
        } else {
            f64::INFINITY
        };

        observations.push(json!({
            "ordinal": sample.ordinal,
            "category": sample.category,
            "workload_id": sample.workload_id,
            "dimension": n,
            "source_sha256": source.sha256,
            "factor_source_id": source.factor_source_id,
            "archived": {
                "status": sample.archived_status,
                "maximum_declared_solution_relative_inf": sample.archived_solution_relative_inf,
                "solution_threshold": sample.solution_threshold,
            },
            "frozen_rhs": {
                "construction": "issue-41 ordered binary64 matrix-times-declared-solution",
                "declared_solution_double_double_backward_error": frozen_rhs_rounding_backward,
                "exact_double_double_rhs_declared_solution_backward_error": exact_rhs_declared_backward,
                "directional_forward_amplification": directional_amplification,
            },
            "candidate_lblt": {
                "factor_fingerprint": candidate_fingerprint,
                "metrics": candidate_metrics,
                "double_double_refined": candidate_refined.summary,
            },
            "serialization_roundtrip": {
                "payload_bytes": serialized.len(),
                "payload_sha256": sha256(&serialized),
                "factor_fingerprint_bit_exact": roundtrip_factor_exact,
                "solution_bit_exact": roundtrip_solution_exact,
            },
            "full_pivot_lu": {
                "metrics": full_lu_metrics,
                "double_double_refined": full_lu_refined.summary,
            },
            "symmetric_max_equilibrated_lblt": {
                "metrics": scaled_metrics,
                "double_double_refined": scaled_refined.summary,
            },
            "independent_reference": {
                "lblt_full_pivot_lu_relative_agreement": reference_agreement,
                "agreement_limit": reference_agreement_limit,
                "closed": independent_reference_closed,
                "declared_solution_relative_inf": reference_declared_error,
            },
            "judgment": {
                "authority_defect_witness": authority_defect_witness,
                "candidate_local_remedy_pass": candidate_local_remedy_pass,
            },
        }));
    }

    let disposition =
        if all_failed_authority_witnesses && pass_control_closed && all_roundtrips_exact {
            "HEALTH_AUTHORITY_DEFECT_PROVEN"
        } else if observations.iter().all(|observation| {
            observation["archived"]["status"] != "FAIL"
                || observation["judgment"]["candidate_local_remedy_pass"] == true
        }) {
            "CORRECTABLE_WITH_NEW_BINDING"
        } else {
            "REQUIRES_REPLACEMENT_DENSE_PATH"
        };
    let evidence = json!({
        "schema": OUTPUT_SCHEMA,
        "disposition": disposition,
        "diagnosis_plan": {
            "file_sha256": sha256(&diagnosis_bytes),
            "schema": diagnosis.schema,
        },
        "issue_41_plan": {
            "file_sha256": sha256(&issue_41_bytes),
            "plan_id": issue_41.plan_id,
        },
        "bound_authorities": diagnosis.authorities,
        "method": {
            "candidate_route": "exact issue-41 low-level faer Bunch-Kaufman LDLT",
            "serialization_probe": "bit-exact owned component byte round-trip",
            "candidate_local_probes": [
                "symmetric max equilibration",
                "double-double-residual iterative refinement"
            ],
            "independent_route": "faer full-pivot LU with distinct row and column permutations",
            "reference": "two f64 factors with 105-bit double-double residual and solution accumulation",
            "maximum_refinement_steps": MAX_REFINEMENT_STEPS,
        },
        "closure": {
            "all_failed_samples_prove_authority_defect": all_failed_authority_witnesses,
            "passing_control_closes": pass_control_closed,
            "all_serialization_roundtrips_bit_exact": all_roundtrips_exact,
            "representative_subset_is_corpus_admission": false,
        },
        "observations": observations,
    });
    let encoded = serde_json::to_vec_pretty(&evidence)
        .map_err(|error| format!("encode evidence: {error}"))?;
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("create output parent: {error}"))?;
    }
    fs::write(&args.output, [&encoded[..], b"\n"].concat())
        .map_err(|error| format!("write output: {error}"))?;
    println!(
        "{} samples={} disposition={}",
        OUTPUT_SCHEMA,
        diagnosis.samples.len(),
        disposition
    );
    Ok(())
}
