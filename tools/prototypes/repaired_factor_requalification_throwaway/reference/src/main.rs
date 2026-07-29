//! THROWAWAY reference generator for RapidRBF issue 47.
//!
//! Question: can the frozen issue-41 binary64 systems be certified before
//! candidate entry under the issue-46 directed-rounding authority?
//!
//! The full-pivot factor and every reference center are derived only from the
//! frozen source and RHS bytes. The candidate binding is not an input. MPFR
//! outward bounds certify an approximate inverse and enclose each exact
//! frozen-system solution. This is decision evidence, not production code.

use dyn_stack::{MemBuffer, MemStack};
use faer::linalg::lu::full_pivoting;
use faer::linalg::matmul::matmul;
use faer::perm::PermRef;
use faer::prelude::ReborrowMut;
use faer::{Accum, MatMut, MatRef, Par};
use gmp_mpfr_sys::mpfr;
use qd::Quad;
use rug::float::Round;
use rug::ops::{AddAssignRound, AssignRound, DivAssignRound, MulAssignRound, SubAssignRound};
use rug::{Assign, Float};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::ffi::CStr;
use std::fs::{self, File};
use std::io::Write;
use std::mem::size_of;
use std::path::{Path, PathBuf};
use std::time::Instant;

const MANIFEST_SCHEMA: &str = "RapidRBF/ProjectedFactorReferenceManifest/v1";
const ISSUE41_PLAN_SCHEMA: &str = "RapidRBF/FactorQualificationPlan/v1";
const AUTHORITY_SHA256: &str = "c671a0a5cf4b48cd580a5c6e67a920bb24288e964036d5f3d216b3ad850168d6";
const REQUALIFICATION_PLAN_SHA256: &str =
    "3d948e6a3c5e824d84ac8abae8135bafbb9a052480361fe4589982bc8bfba829";
const ISSUE41_PLAN_SHA256: &str =
    "fef5f0b3e4d84e8af95505f3b822aded357631191a1e13226474adc985b964ce";
const ISSUE41_BUNDLE_SHA256: &str =
    "a3b6417e61a604ee568d7bb5fed0416ce5c726f0e529ca1f998a7bdb272e207a";
const RHS_COLUMNS: usize = 3;
const FAMILY_NAMES: [&str; RHS_COLUMNS] = ["operational", "constraint", "dynamic-range"];
const PRECISION_LADDER: [u32; 4] = [256, 512, 1024, 2048];
const MAX_REFINEMENT_STEPS: usize = 12;

#[derive(Debug)]
struct Args {
    issue_41_plan: PathBuf,
    authority_profile: PathBuf,
    requalification_plan: PathBuf,
    bundle_root: PathBuf,
    generator_closure_sha256: String,
    output: PathBuf,
    source_limit: Option<usize>,
}

#[derive(Clone, Deserialize)]
struct Issue41Plan {
    schema: String,
    plan_id: String,
    authority: Value,
    factor_sources: Vec<Source>,
}

#[derive(Clone, Deserialize)]
struct Source {
    ordinal: usize,
    factor_source_id: String,
    block_id: String,
    workload_id: String,
    role: String,
    dimension: usize,
    encoding: String,
    bytes: usize,
    sha256: String,
    bundle_path: String,
}

#[derive(Serialize)]
struct GeneratorIdentity {
    closure_sha256: String,
    algorithm: &'static str,
    pivoting: &'static str,
    matrix_product_enclosure: &'static str,
    mpfr_version: String,
    rug_version: &'static str,
    precision_ladder_bits: [u32; 4],
}

#[derive(Serialize)]
struct ManifestAuthority {
    authority_profile_sha256: &'static str,
    requalification_plan_sha256: &'static str,
    issue_41_plan_sha256: &'static str,
    issue_41_plan_id: String,
    issue_41_bundle_sha256: &'static str,
}

#[derive(Serialize)]
struct ReferenceManifest {
    schema: &'static str,
    disposition: String,
    authority: ManifestAuthority,
    generator: GeneratorIdentity,
    candidate_inputs_observed: bool,
    unique_matrix_payloads: usize,
    required_rhs_families_per_matrix: usize,
    certified_references: usize,
    indeterminate_references: usize,
    entries: Vec<ReferenceEntry>,
}

#[derive(Serialize)]
struct ReferenceEntry {
    first_ordinal: usize,
    logical_factor_source_ids: Vec<String>,
    block_ids: Vec<String>,
    workload_ids: Vec<String>,
    role: String,
    dimension: usize,
    source_sha256: String,
    source_bytes: usize,
    rhs: Vec<RhsReference>,
}

#[derive(Serialize)]
struct RhsReference {
    family: &'static str,
    rhs_sha256: String,
    status: String,
    precision_bits: u32,
    q_upper_hex: String,
    c_upper_hex: String,
    rho_upper_hex: String,
    scale_lower_hex: String,
    scale_upper_hex: String,
    relative_radius_upper_hex: String,
    solution_threshold_hex: String,
    reference_quality_limit_hex: String,
    center_sha256: String,
    center_hi_bits: Vec<String>,
    center_lo_bits: Vec<String>,
    enclosure_lower_bits: Vec<String>,
    enclosure_upper_bits: Vec<String>,
    enclosure_lower_mpfr_hex: Vec<String>,
    enclosure_upper_mpfr_hex: Vec<String>,
    refinement_correction_relative_inf: Vec<f64>,
}

struct FullLuFactor {
    matrix: Vec<f64>,
    row_perm: Vec<usize>,
    row_perm_inv: Vec<usize>,
    col_perm: Vec<usize>,
    col_perm_inv: Vec<usize>,
}

struct RefinedCenter {
    values: Vec<Quad>,
    correction_history: Vec<Vec<f64>>,
}

fn parse_args() -> Result<Args, String> {
    let mut issue_41_plan = None;
    let mut authority_profile = None;
    let mut requalification_plan = None;
    let mut bundle_root = None;
    let mut generator_closure_sha256 = None;
    let mut output = None;
    let mut source_limit = None;
    let mut arguments = env::args().skip(1);
    while let Some(argument) = arguments.next() {
        let value = arguments
            .next()
            .ok_or_else(|| format!("{argument} requires a value"))?;
        match argument.as_str() {
            "--issue-41-plan" => issue_41_plan = Some(PathBuf::from(value)),
            "--authority-profile" => authority_profile = Some(PathBuf::from(value)),
            "--requalification-plan" => requalification_plan = Some(PathBuf::from(value)),
            "--bundle-root" => bundle_root = Some(PathBuf::from(value)),
            "--generator-closure-sha256" => generator_closure_sha256 = Some(value),
            "--output" => output = Some(PathBuf::from(value)),
            "--source-limit" => {
                source_limit = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| "--source-limit must be an integer")?,
                )
            }
            _ => return Err(format!("unknown argument {argument}")),
        }
    }
    Ok(Args {
        issue_41_plan: issue_41_plan.ok_or("--issue-41-plan is required")?,
        authority_profile: authority_profile.ok_or("--authority-profile is required")?,
        requalification_plan: requalification_plan.ok_or("--requalification-plan is required")?,
        bundle_root: bundle_root.ok_or("--bundle-root is required")?,
        generator_closure_sha256: generator_closure_sha256
            .ok_or("--generator-closure-sha256 is required")?,
        output: output.ok_or("--output is required")?,
        source_limit,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn sha256_file(path: &Path) -> Result<String, String> {
    fs::read(path)
        .map(|bytes| sha256(&bytes))
        .map_err(|error| format!("read {}: {error}", path.display()))
}

fn update_f64s(digest: &mut Sha256, values: &[f64]) {
    for value in values {
        digest.update(value.to_bits().to_le_bytes());
    }
}

fn read_matrix(bundle_root: &Path, source: &Source) -> Result<Vec<f64>, String> {
    if source.bundle_path.contains("..") || Path::new(&source.bundle_path).is_absolute() {
        return Err(format!("unsafe source path {}", source.bundle_path));
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
    let mut matrix = vec![0.0_f64; n * n];
    match (source.role.as_str(), source.encoding.as_str()) {
        ("projected_b", "lower-triangle-row-major-packed") => {
            let expected = n
                .checked_mul(n + 1)
                .and_then(|value| value.checked_div(2))
                .and_then(|value| value.checked_mul(size_of::<f64>()))
                .ok_or("projected source size overflow")?;
            if bytes.len() != expected {
                return Err(format!("{} packed shape differs", source.factor_source_id));
            }
            let mut cursor = 0;
            for row in 0..n {
                for column in 0..=row {
                    let offset = cursor * size_of::<f64>();
                    let value = f64::from_le_bytes(bytes[offset..offset + 8].try_into().unwrap());
                    matrix[row + column * n] = value;
                    matrix[column + row * n] = value;
                    cursor += 1;
                }
            }
        }
        ("coarse_p_top", "row-major") => {
            if bytes.len() != n * n * size_of::<f64>() {
                return Err(format!(
                    "{} row-major shape differs",
                    source.factor_source_id
                ));
            }
            for row in 0..n {
                for column in 0..n {
                    let offset = (row * n + column) * size_of::<f64>();
                    matrix[row + column * n] =
                        f64::from_le_bytes(bytes[offset..offset + 8].try_into().unwrap());
                }
            }
        }
        _ => {
            return Err(format!(
                "{} role or encoding differs",
                source.factor_source_id
            ))
        }
    }
    if matrix.iter().any(|value| !value.is_finite()) {
        return Err(format!(
            "{} contains a non-finite value",
            source.factor_source_id
        ));
    }
    Ok(matrix)
}

fn declared_solutions(n: usize) -> Vec<f64> {
    let mut values = vec![0.0; n * RHS_COLUMNS];
    for row in 0..n {
        values[row] = 1.0 + (row % 17) as f64 / 17.0;
        values[row + n] = if row % 2 == 0 { 1.0 } else { -1.0 };
        let sign = if row % 2 == 0 { 1.0 } else { -1.0 };
        values[row + 2 * n] = sign * 2.0_f64.powi((row % 21) as i32 - 10);
    }
    values
}

fn manufactured_rhs(matrix: &[f64], solutions: &[f64], n: usize) -> Vec<f64> {
    let mut rhs = vec![0.0; n * RHS_COLUMNS];
    for family in 0..RHS_COLUMNS {
        let offset = family * n;
        for row in 0..n {
            let mut sum = 0.0;
            for column in 0..n {
                sum += matrix[row + column * n] * solutions[offset + column];
            }
            rhs[offset + row] = sum;
        }
    }
    rhs
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

fn quad_abs(value: Quad) -> f64 {
    (value.0 + value.1).abs()
}

fn quad_residual(matrix: &[f64], rhs: &[f64], solution: &[Quad], n: usize) -> Vec<Quad> {
    let mut residual = vec![Quad::ZERO; n * RHS_COLUMNS];
    for family in 0..RHS_COLUMNS {
        let offset = family * n;
        for row in 0..n {
            let mut action = Quad::ZERO;
            for column in 0..n {
                action = action.add_accurate(
                    Quad::from_f64(matrix[row + column * n]).mul(solution[offset + column]),
                );
            }
            residual[offset + row] = Quad::from_f64(rhs[offset + row]).sub_accurate(action);
        }
    }
    residual
}

fn refine_centers(matrix: &[f64], rhs: &[f64], factor: &FullLuFactor, n: usize) -> RefinedCenter {
    let initial = solve_full_lu(factor, rhs, n, RHS_COLUMNS);
    let mut values: Vec<Quad> = initial.into_iter().map(Quad::from_f64).collect();
    let mut histories = vec![Vec::new(); RHS_COLUMNS];
    for _ in 0..MAX_REFINEMENT_STEPS {
        let residual = quad_residual(matrix, rhs, &values, n);
        let residual_f64: Vec<f64> = residual.iter().map(|value| value.0 + value.1).collect();
        let correction = solve_full_lu(factor, &residual_f64, n, RHS_COLUMNS);
        let mut all_done = true;
        for family in 0..RHS_COLUMNS {
            let offset = family * n;
            let mut correction_inf = 0.0_f64;
            let mut center_inf = 0.0_f64;
            for row in 0..n {
                correction_inf = correction_inf.max(correction[offset + row].abs());
                center_inf = center_inf.max(quad_abs(values[offset + row]));
                values[offset + row] =
                    values[offset + row].add_accurate(Quad::from_f64(correction[offset + row]));
            }
            let relative = correction_inf / center_inf.max(1.0);
            histories[family].push(relative);
            all_done &= relative <= 8.0 * Quad::EPSILON.0.abs();
        }
        if all_done {
            break;
        }
    }
    RefinedCenter {
        values,
        correction_history: histories,
    }
}

fn inverse_from_factor(factor: &FullLuFactor, n: usize) -> Vec<f64> {
    let mut identity = vec![0.0; n * n];
    for index in 0..n {
        identity[index + index * n] = 1.0;
    }
    solve_full_lu(factor, &identity, n, n)
}

fn multiply(left: &[f64], right: &[f64], n: usize) -> Vec<f64> {
    let mut product = vec![0.0; n * n];
    matmul(
        MatMut::from_column_major_slice_mut(&mut product, n, n),
        Accum::Replace,
        MatRef::from_column_major_slice(left, n, n),
        MatRef::from_column_major_slice(right, n, n),
        1.0,
        Par::Seq,
    );
    product
}

fn upward_gamma(operations: usize, precision: u32) -> Float {
    let mut numerator = Float::with_val(precision, operations);
    numerator.mul_assign_round(Float::with_val(precision, 2.0_f64.powi(-53)), Round::Up);
    let mut denominator = Float::with_val(precision, 1);
    denominator.sub_assign_round(&numerator, Round::Down);
    numerator.div_assign_round(denominator, Round::Up);
    numerator
}

fn inflate_nonnegative(value: f64, operations: usize, precision: u32) -> Float {
    let gamma = upward_gamma(operations, precision);
    let mut denominator = Float::with_val(precision, 1);
    denominator.sub_assign_round(&gamma, Round::Down);
    let mut result = Float::with_val(precision, value);
    result.div_assign_round(denominator, Round::Up);
    result
}

fn inverse_certificate(
    matrix: &[f64],
    inverse: &[f64],
    product: &[f64],
    n: usize,
    precision: u32,
) -> Result<(Float, Float), String> {
    let mut matrix_row_upper = vec![0.0_f64; n];
    for row in 0..n {
        let mut observed = 0.0;
        for column in 0..n {
            observed += matrix[row + column * n].abs();
        }
        matrix_row_upper[row] =
            inflate_nonnegative(observed, n.saturating_add(4), precision).to_f64_round(Round::Up);
    }

    let mut q_upper = Float::with_val(precision, 0);
    let mut inverse_norm_upper = Float::with_val(precision, 0);
    let matrix_product_gamma = upward_gamma(4 * n + 64, precision);
    for row in 0..n {
        let mut center_residual_sum = 0.0;
        let mut inverse_row_sum = 0.0;
        let mut absolute_product_sum = 0.0;
        for column in 0..n {
            let expected = if row == column { 1.0 } else { 0.0 };
            center_residual_sum += (expected - product[row + column * n]).abs();
            inverse_row_sum += inverse[row + column * n].abs();
            absolute_product_sum += inverse[row + column * n].abs() * matrix_row_upper[column];
        }
        let center_upper = inflate_nonnegative(center_residual_sum, n + 4, precision);
        let inverse_row_upper = inflate_nonnegative(inverse_row_sum, n + 4, precision);
        let absolute_product_upper =
            inflate_nonnegative(absolute_product_sum, 2 * n + 8, precision);
        let mut product_error = absolute_product_upper;
        product_error.mul_assign_round(&matrix_product_gamma, Round::Up);
        let diagonal = product[row + row * n].abs();
        let mut diagonal_rounding = Float::with_val(precision, 1.0 + diagonal);
        diagonal_rounding
            .mul_assign_round(Float::with_val(precision, 2.0_f64.powi(-53)), Round::Up);
        let mut row_upper = center_upper;
        row_upper.add_assign_round(product_error, Round::Up);
        row_upper.add_assign_round(diagonal_rounding, Round::Up);
        if row_upper > q_upper {
            q_upper = row_upper;
        }
        if inverse_row_upper > inverse_norm_upper {
            inverse_norm_upper = inverse_row_upper;
        }
    }
    if !q_upper.is_finite() || !inverse_norm_upper.is_finite() {
        return Err("inverse certificate produced a non-finite bound".to_owned());
    }
    Ok((q_upper, inverse_norm_upper))
}

fn exact_center_float(value: Quad, precision: u32) -> Float {
    let mut result = Float::with_val(precision, value.0);
    result.add_assign_round(value.1, Round::Nearest);
    result
}

fn residual_upper(
    matrix: &[f64],
    rhs: &[f64],
    center: &[Quad],
    n: usize,
    family: usize,
    precision: u32,
) -> Float {
    let center_mpfr: Vec<Float> = center
        .iter()
        .copied()
        .map(|value| exact_center_float(value, precision))
        .collect();
    let mut maximum = Float::with_val(precision, 0);
    let mut coefficient = Float::new(precision);
    let mut product = Float::new(precision);
    for row in 0..n {
        let mut action_lower = Float::with_val(precision, 0);
        let mut action_upper = Float::with_val(precision, 0);
        for column in 0..n {
            coefficient.assign(matrix[row + column * n]);
            product.assign_round(&coefficient * &center_mpfr[column], Round::Nearest);
            action_lower.add_assign_round(&product, Round::Down);
            action_upper.add_assign_round(&product, Round::Up);
        }
        let mut lower = Float::with_val(precision, rhs[family * n + row]);
        lower.sub_assign_round(&action_upper, Round::Down);
        let mut upper = Float::with_val(precision, rhs[family * n + row]);
        upper.sub_assign_round(&action_lower, Round::Up);
        lower.abs_mut();
        upper.abs_mut();
        let candidate = if lower > upper { lower } else { upper };
        if candidate > maximum {
            maximum = candidate;
        }
    }
    maximum
}

fn float_hex(value: &Float) -> String {
    value.to_string_radix(16, None)
}

fn bits(value: f64) -> String {
    format!("{:016x}", value.to_bits())
}

fn center_sha256(center: &[Quad]) -> String {
    let mut digest = Sha256::new();
    for value in center {
        digest.update(value.0.to_bits().to_le_bytes());
        digest.update(value.1.to_bits().to_le_bytes());
    }
    format!("{:x}", digest.finalize())
}

fn certify_family(
    matrix: &[f64],
    rhs: &[f64],
    center: &[Quad],
    history: Vec<f64>,
    inverse_norm_upper: &Float,
    q_upper: &Float,
    n: usize,
    family: usize,
) -> RhsReference {
    let mut selected = None;
    for precision in PRECISION_LADDER {
        let residual = residual_upper(matrix, rhs, center, n, family, precision);
        let mut c_upper = Float::with_val(precision, inverse_norm_upper);
        c_upper.mul_assign_round(residual, Round::Up);
        let mut one_minus_q = Float::with_val(precision, 1);
        one_minus_q.sub_assign_round(q_upper, Round::Down);
        if one_minus_q <= 0 {
            continue;
        }
        let mut rho_upper = c_upper.clone();
        rho_upper.div_assign_round(&one_minus_q, Round::Up);

        let center_mpfr: Vec<Float> = center
            .iter()
            .copied()
            .map(|value| exact_center_float(value, precision))
            .collect();
        let mut center_norm = Float::with_val(precision, 0);
        for value in &center_mpfr {
            let mut absolute = value.clone();
            absolute.abs_mut();
            if absolute > center_norm {
                center_norm = absolute;
            }
        }
        let mut solution_norm_lower = center_norm.clone();
        solution_norm_lower.sub_assign_round(&rho_upper, Round::Down);
        if solution_norm_lower < 1 {
            solution_norm_lower.assign(1);
        }
        let mut solution_norm_upper = center_norm;
        solution_norm_upper.add_assign_round(&rho_upper, Round::Up);
        if solution_norm_upper < 1 {
            solution_norm_upper.assign(1);
        }

        let mut relative_radius = rho_upper.clone();
        relative_radius.div_assign_round(&solution_norm_lower, Round::Up);
        let threshold_f64 = n as f64 * 2.0_f64.powi(-45);
        let threshold = Float::with_val(precision, threshold_f64);
        let mut quality_limit = threshold.clone();
        quality_limit.div_assign_round(64, Round::Down);
        if relative_radius <= quality_limit {
            let mut lower_bits = Vec::with_capacity(n);
            let mut upper_bits = Vec::with_capacity(n);
            let mut lower_hex = Vec::with_capacity(n);
            let mut upper_hex = Vec::with_capacity(n);
            for value in &center_mpfr {
                let mut lower = value.clone();
                lower.sub_assign_round(&rho_upper, Round::Down);
                let mut upper = value.clone();
                upper.add_assign_round(&rho_upper, Round::Up);
                lower_bits.push(bits(lower.to_f64_round(Round::Down)));
                upper_bits.push(bits(upper.to_f64_round(Round::Up)));
                lower_hex.push(float_hex(&lower));
                upper_hex.push(float_hex(&upper));
            }
            selected = Some(RhsReference {
                family: FAMILY_NAMES[family],
                rhs_sha256: {
                    let start = family * n;
                    let mut digest = Sha256::new();
                    update_f64s(&mut digest, &rhs[start..start + n]);
                    format!("{:x}", digest.finalize())
                },
                status: "CERTIFIED_REFERENCE".to_owned(),
                precision_bits: precision,
                q_upper_hex: float_hex(q_upper),
                c_upper_hex: float_hex(&c_upper),
                rho_upper_hex: float_hex(&rho_upper),
                scale_lower_hex: float_hex(&solution_norm_lower),
                scale_upper_hex: float_hex(&solution_norm_upper),
                relative_radius_upper_hex: float_hex(&relative_radius),
                solution_threshold_hex: float_hex(&threshold),
                reference_quality_limit_hex: float_hex(&quality_limit),
                center_sha256: center_sha256(center),
                center_hi_bits: center.iter().map(|value| bits(value.0)).collect(),
                center_lo_bits: center.iter().map(|value| bits(value.1)).collect(),
                enclosure_lower_bits: lower_bits,
                enclosure_upper_bits: upper_bits,
                enclosure_lower_mpfr_hex: lower_hex,
                enclosure_upper_mpfr_hex: upper_hex,
                refinement_correction_relative_inf: history.clone(),
            });
            break;
        }
    }

    selected.unwrap_or_else(|| RhsReference {
        family: FAMILY_NAMES[family],
        rhs_sha256: {
            let start = family * n;
            let mut digest = Sha256::new();
            update_f64s(&mut digest, &rhs[start..start + n]);
            format!("{:x}", digest.finalize())
        },
        status: "REFERENCE_INDETERMINATE".to_owned(),
        precision_bits: 2048,
        q_upper_hex: float_hex(q_upper),
        c_upper_hex: "unresolved".to_owned(),
        rho_upper_hex: "unresolved".to_owned(),
        scale_lower_hex: "unresolved".to_owned(),
        scale_upper_hex: "unresolved".to_owned(),
        relative_radius_upper_hex: "unresolved".to_owned(),
        solution_threshold_hex: float_hex(&Float::with_val(2048, n as f64 * 2.0_f64.powi(-45))),
        reference_quality_limit_hex: "unresolved".to_owned(),
        center_sha256: center_sha256(center),
        center_hi_bits: Vec::new(),
        center_lo_bits: Vec::new(),
        enclosure_lower_bits: Vec::new(),
        enclosure_upper_bits: Vec::new(),
        enclosure_lower_mpfr_hex: Vec::new(),
        enclosure_upper_mpfr_hex: Vec::new(),
        refinement_correction_relative_inf: history,
    })
}

fn mpfr_version() -> String {
    unsafe {
        CStr::from_ptr(mpfr::get_version())
            .to_string_lossy()
            .into_owned()
    }
}

fn run() -> Result<(), String> {
    let args = parse_args()?;
    if args.output.exists() {
        return Err(format!("output must be absent: {}", args.output.display()));
    }
    if sha256_file(&args.authority_profile)? != AUTHORITY_SHA256 {
        return Err("authority profile SHA-256 differs".to_owned());
    }
    if sha256_file(&args.requalification_plan)? != REQUALIFICATION_PLAN_SHA256 {
        return Err("requalification plan SHA-256 differs".to_owned());
    }
    if sha256_file(&args.issue_41_plan)? != ISSUE41_PLAN_SHA256 {
        return Err("issue-41 plan SHA-256 differs".to_owned());
    }
    let plan_bytes =
        fs::read(&args.issue_41_plan).map_err(|error| format!("read plan: {error}"))?;
    let plan: Issue41Plan =
        serde_json::from_slice(&plan_bytes).map_err(|error| format!("parse plan: {error}"))?;
    if plan.schema != ISSUE41_PLAN_SCHEMA
        || plan.factor_sources.len() != 216
        || plan.authority["candidate_binding"]["binding_sha256"]
            != "1cd16d8c0ef14f01849af440df53a64b06dbaf0adcd46ac6926b0625634785e6"
    {
        return Err("issue-41 plan identity differs".to_owned());
    }

    let mut grouped: BTreeMap<String, Vec<Source>> = BTreeMap::new();
    for source in plan.factor_sources {
        grouped
            .entry(source.sha256.clone())
            .or_default()
            .push(source);
    }
    let mut groups: Vec<Vec<Source>> = grouped.into_values().collect();
    groups.sort_by_key(|sources| sources.iter().map(|source| source.ordinal).min().unwrap());
    if let Some(limit) = args.source_limit {
        groups.truncate(limit);
    }

    let started = Instant::now();
    let mut entries = Vec::with_capacity(groups.len());
    for (index, sources) in groups.iter().enumerate() {
        let first = sources.iter().min_by_key(|source| source.ordinal).unwrap();
        eprintln!(
            "reference {}/{} ordinal={} dimension={} source={}",
            index + 1,
            groups.len(),
            first.ordinal,
            first.dimension,
            first.sha256
        );
        let matrix = read_matrix(&args.bundle_root, first)?;
        let n = first.dimension;
        let declared = declared_solutions(n);
        let rhs = manufactured_rhs(&matrix, &declared, n);
        let factor = factor_full_lu(&matrix, n);
        let refined = refine_centers(&matrix, &rhs, &factor, n);
        let inverse = inverse_from_factor(&factor, n);
        let product = multiply(&inverse, &matrix, n);
        let (q_upper, inverse_norm_upper) =
            inverse_certificate(&matrix, &inverse, &product, n, 256)?;
        let mut references = Vec::with_capacity(RHS_COLUMNS);
        for family in 0..RHS_COLUMNS {
            references.push(certify_family(
                &matrix,
                &rhs,
                &refined.values[family * n..(family + 1) * n],
                refined.correction_history[family].clone(),
                &inverse_norm_upper,
                &q_upper,
                n,
                family,
            ));
        }
        entries.push(ReferenceEntry {
            first_ordinal: first.ordinal,
            logical_factor_source_ids: sources
                .iter()
                .map(|source| source.factor_source_id.clone())
                .collect(),
            block_ids: sources
                .iter()
                .map(|source| source.block_id.clone())
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect(),
            workload_ids: sources
                .iter()
                .map(|source| source.workload_id.clone())
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect(),
            role: first.role.clone(),
            dimension: n,
            source_sha256: first.sha256.clone(),
            source_bytes: first.bytes,
            rhs: references,
        });
    }
    let certified = entries
        .iter()
        .flat_map(|entry| &entry.rhs)
        .filter(|rhs| rhs.status == "CERTIFIED_REFERENCE")
        .count();
    let total = entries.len() * RHS_COLUMNS;
    let complete = args.source_limit.is_none() && entries.len() == 179 && certified == 179 * 3;
    let manifest = ReferenceManifest {
        schema: MANIFEST_SCHEMA,
        disposition: if complete {
            "CERTIFIED_REFERENCE".to_owned()
        } else if args.source_limit.is_some() && certified == total {
            "CERTIFIED_REFERENCE_DIAGNOSTIC_SUBSET".to_owned()
        } else {
            "REFERENCE_SET_INCOMPLETE_UNJUDGED".to_owned()
        },
        authority: ManifestAuthority {
            authority_profile_sha256: AUTHORITY_SHA256,
            requalification_plan_sha256: REQUALIFICATION_PLAN_SHA256,
            issue_41_plan_sha256: ISSUE41_PLAN_SHA256,
            issue_41_plan_id: plan.plan_id,
            issue_41_bundle_sha256: ISSUE41_BUNDLE_SHA256,
        },
        generator: GeneratorIdentity {
            closure_sha256: args.generator_closure_sha256,
            algorithm: "candidate-independent faer full-pivot LU center and inverse with MPFR-directed Banach enclosure",
            pivoting: "complete row-and-column pivoting; deterministic faer 0.24.4 Par::Seq closure",
            matrix_product_enclosure: "faer binary64 center plus MPFR-evaluated Higham gamma bound over absolute products",
            mpfr_version: mpfr_version(),
            rug_version: "1.30.0",
            precision_ladder_bits: PRECISION_LADDER,
        },
        candidate_inputs_observed: false,
        unique_matrix_payloads: entries.len(),
        required_rhs_families_per_matrix: RHS_COLUMNS,
        certified_references: certified,
        indeterminate_references: total - certified,
        entries,
    };
    let bytes = serde_json::to_vec_pretty(&manifest)
        .map_err(|error| format!("serialize reference manifest: {error}"))?;
    let mut output =
        File::create_new(&args.output).map_err(|error| format!("create output: {error}"))?;
    output
        .write_all(&bytes)
        .and_then(|_| output.write_all(b"\n"))
        .and_then(|_| output.sync_all())
        .map_err(|error| format!("write output: {error}"))?;
    println!(
        "{} matrices={} references={}/{} elapsed_seconds={:.3} sha256={}",
        manifest.disposition,
        manifest.unique_matrix_payloads,
        certified,
        total,
        started.elapsed().as_secs_f64(),
        sha256_file(&args.output)?
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("reference generation failed: {error}");
        std::process::exit(2);
    }
}
