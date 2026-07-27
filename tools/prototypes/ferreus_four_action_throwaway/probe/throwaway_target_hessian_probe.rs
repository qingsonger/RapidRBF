//! THROWAWAY PROTOTYPE.
//!
//! Question: can scalar radial M2L plus D right-hand sides and target Hessians
//! reproduce the RapidRBF H contraction for a nonsymmetric metric shear?

use faer::{Mat, RowRef};
use ferreus_bbfmm::{FmmParams, FmmTree, KernelFunction, M2LCompressionType};

const ALPHA: f64 = 0.45;
const INTERPOLATION_ORDER: usize = 7;
const SOURCE_COUNT: usize = 96;
const CROSS_TARGET_COUNT: usize = 57;

#[derive(Clone, Copy)]
struct Gaussian {
    alpha: f64,
}

impl Gaussian {
    fn value_and_delta(&self, target: RowRef<f64>, source: RowRef<f64>) -> (f64, [f64; 3]) {
        let mut delta = [0.0; 3];
        let mut radius_squared = 0.0;
        for (axis, (target_value, source_value)) in target.iter().zip(source.iter()).enumerate() {
            delta[axis] = target_value - source_value;
            radius_squared += delta[axis] * delta[axis];
        }
        ((-self.alpha * radius_squared).exp(), delta)
    }
}

impl KernelFunction for Gaussian {
    fn evaluate(&self, target: RowRef<f64>, source: RowRef<f64>) -> f64 {
        self.value_and_delta(target, source).0
    }

    fn evaluate_value_gradient(
        &self,
        target: RowRef<f64>,
        source: RowRef<f64>,
        gradient_out: &mut [f64],
    ) -> Option<f64> {
        let (value, delta) = self.value_and_delta(target, source);
        for axis in 0..gradient_out.len() {
            gradient_out[axis] = -2.0 * self.alpha * value * delta[axis];
        }
        Some(value)
    }

    fn evaluate_value_gradient_hessian(
        &self,
        target: RowRef<f64>,
        source: RowRef<f64>,
        gradient_out: &mut [f64],
        hessian_out: &mut [f64],
    ) -> Option<f64> {
        let dimensions = gradient_out.len();
        let (value, delta) = self.value_and_delta(target, source);
        for row in 0..dimensions {
            gradient_out[row] = -2.0 * self.alpha * value * delta[row];
            for column in 0..dimensions {
                hessian_out[row * dimensions + column] = value
                    * (4.0 * self.alpha * self.alpha * delta[row] * delta[column]
                        - if row == column { 2.0 * self.alpha } else { 0.0 });
            }
        }
        Some(value)
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("question=scalar radial M2L + D RHS + uniform P2P/L2P target Hessians => RapidRBF H?");
    println!(
        "alpha={ALPHA} interpolation_order={INTERPOLATION_ORDER} sources={SOURCE_COUNT} cross_targets={CROSS_TARGET_COUNT}"
    );
    println!(
        "dim,mode,targets,depth,v_entries,m2l_refs,tensor_max_abs,tensor_rel_l2,H_max_abs,H_rel_l2,H_ref_max"
    );

    for dimensions in 1..=3 {
        let shear = shear_matrix(dimensions);
        if dimensions > 1 {
            assert!(shear[1] != shear[dimensions], "shear must be nonsymmetric");
        }
        println!("A{dimensions}={shear:?}");

        let physical_sources = halton_points(SOURCE_COUNT, dimensions, 1);
        let physical_cross_targets =
            halton_points(CROSS_TARGET_COUNT, dimensions, SOURCE_COUNT + 137);
        let metric_sources = transform_points(&physical_sources, &shear);
        let metric_cross_targets = transform_points(&physical_cross_targets, &shear);
        let physical_weights = physical_vector_weights(SOURCE_COUNT, dimensions);
        let metric_weights = transform_points(&physical_weights, &shear);
        let extents = union_extents(&metric_sources, &metric_cross_targets);

        for (mode, max_points_per_cell) in [("near", SOURCE_COUNT + 1), ("far", 2_usize)] {
            let params = FmmParams {
                max_points_per_cell,
                compression_type: M2LCompressionType::None,
                epsilon: 1.0e-14,
                eval_chunk_size: 32,
            };
            let mut tree = FmmTree::new(
                metric_sources.clone(),
                INTERPOLATION_ORDER,
                Gaussian { alpha: ALPHA },
                false,
                false,
                Some(extents.clone()),
                Some(params),
            );
            tree.set_weights(&metric_weights.as_ref());

            for (target_kind, targets) in
                [("self", &metric_sources), ("cross", &metric_cross_targets)]
            {
                let (_, _, fmm_hessians) =
                    tree.evaluate_with_hessians(&metric_weights.as_ref(), targets)?;
                let (depth, v_entries, m2l_refs) = tree.prototype_interaction_stats();

                if mode == "near" {
                    assert_eq!(v_entries, 0, "near-only case unexpectedly used a V-list");
                    assert_eq!(
                        m2l_refs, 0,
                        "near-only case unexpectedly precomputed M2L operators"
                    );
                } else {
                    assert!(depth >= 2, "far case did not refine");
                    assert!(v_entries > 0, "far case did not build V-list interactions");
                    assert!(m2l_refs > 0, "far case did not precompute M2L operators");
                }

                let direct_hessians =
                    direct_metric_hessians(targets, &metric_sources, &metric_weights, ALPHA);
                let fmm_h = contract_rapidrbf_h(&fmm_hessians, &shear, dimensions);
                let direct_h = contract_rapidrbf_h(&direct_hessians, &shear, dimensions);

                let tensor_error = compare(&fmm_hessians, &direct_hessians);
                let h_error = compare(&fmm_h, &direct_h);
                println!(
                    "{dimensions},{mode}-{target_kind},{},{depth},{v_entries},{m2l_refs},{:.6e},{:.6e},{:.6e},{:.6e},{:.6e}",
                    targets.nrows(),
                    tensor_error.max_absolute,
                    tensor_error.relative_l2,
                    h_error.max_absolute,
                    h_error.relative_l2,
                    h_error.reference_max
                );

                if mode == "near" {
                    assert!(
                        tensor_error.max_absolute < 2.0e-12 && h_error.max_absolute < 2.0e-12,
                        "near-only Hessian path is not direct-sum accurate"
                    );
                } else {
                    assert!(
                        tensor_error.relative_l2 < 2.0e-2 && h_error.relative_l2 < 2.0e-2,
                        "far-field Hessian interpolation error exceeds the prototype bound"
                    );
                }
            }
        }
    }

    println!("PASS");
    Ok(())
}

fn shear_matrix(dimensions: usize) -> Vec<f64> {
    match dimensions {
        1 => vec![1.3],
        2 => vec![1.2, 0.35, -0.15, 0.9],
        3 => vec![1.1, 0.25, -0.1, 0.05, 0.9, 0.3, 0.0, -0.12, 1.2],
        _ => unreachable!(),
    }
}

fn halton_points(count: usize, dimensions: usize, offset: usize) -> Mat<f64> {
    let primes = [2_usize, 3, 5];
    Mat::from_fn(count, dimensions, |row, column| {
        1.6 * radical_inverse(row + offset, primes[column]) - 0.8
    })
}

fn radical_inverse(mut index: usize, base: usize) -> f64 {
    let mut result = 0.0;
    let mut factor = 1.0 / base as f64;
    while index > 0 {
        result += (index % base) as f64 * factor;
        index /= base;
        factor /= base as f64;
    }
    result
}

fn physical_vector_weights(count: usize, dimensions: usize) -> Mat<f64> {
    Mat::from_fn(count, dimensions, |row, column| {
        let phase = (row + 1) as f64 * (column + 2) as f64;
        (0.65 * (0.37 * phase).sin() + 0.35 * (0.19 * phase + 0.4).cos()) / count as f64
    })
}

fn transform_points(points: &Mat<f64>, transform: &[f64]) -> Mat<f64> {
    let dimensions = points.ncols();
    Mat::from_fn(points.nrows(), dimensions, |row, output_axis| {
        (0..dimensions)
            .map(|input_axis| {
                transform[output_axis * dimensions + input_axis] * points[(row, input_axis)]
            })
            .sum()
    })
}

fn union_extents(first: &Mat<f64>, second: &Mat<f64>) -> Vec<f64> {
    let dimensions = first.ncols();
    let mut lower = vec![f64::INFINITY; dimensions];
    let mut upper = vec![f64::NEG_INFINITY; dimensions];

    for points in [first, second] {
        for row in 0..points.nrows() {
            for axis in 0..dimensions {
                lower[axis] = lower[axis].min(points[(row, axis)]);
                upper[axis] = upper[axis].max(points[(row, axis)]);
            }
        }
    }

    lower.extend(upper);
    lower
}

fn direct_metric_hessians(
    targets: &Mat<f64>,
    sources: &Mat<f64>,
    metric_weights: &Mat<f64>,
    alpha: f64,
) -> Mat<f64> {
    let dimensions = sources.ncols();
    let components = dimensions * dimensions;
    let mut result = Mat::<f64>::zeros(targets.nrows(), dimensions * components);
    let mut delta = [0.0; 3];

    for target_index in 0..targets.nrows() {
        for source_index in 0..sources.nrows() {
            let mut radius_squared = 0.0;
            for axis in 0..dimensions {
                delta[axis] = targets[(target_index, axis)] - sources[(source_index, axis)];
                radius_squared += delta[axis] * delta[axis];
            }
            let value = (-alpha * radius_squared).exp();

            for row in 0..dimensions {
                for column in 0..dimensions {
                    let kernel_hessian = value
                        * (4.0 * alpha * alpha * delta[row] * delta[column]
                            - if row == column { 2.0 * alpha } else { 0.0 });
                    for rhs in 0..dimensions {
                        result[(target_index, rhs * components + row * dimensions + column)] +=
                            kernel_hessian * metric_weights[(source_index, rhs)];
                    }
                }
            }
        }
    }

    result
}

fn contract_rapidrbf_h(
    metric_hessians: &Mat<f64>,
    transform: &[f64],
    dimensions: usize,
) -> Mat<f64> {
    let components = dimensions * dimensions;
    Mat::from_fn(
        metric_hessians.nrows(),
        dimensions,
        |target, output_axis| {
            let mut result = 0.0;
            for metric_row in 0..dimensions {
                let mut divergence_gradient = 0.0;
                for rhs in 0..dimensions {
                    divergence_gradient +=
                        metric_hessians[(target, rhs * components + metric_row * dimensions + rhs)];
                }
                result -= transform[metric_row * dimensions + output_axis] * divergence_gradient;
            }
            result
        },
    )
}

struct ErrorMetrics {
    max_absolute: f64,
    relative_l2: f64,
    reference_max: f64,
}

fn compare(actual: &Mat<f64>, reference: &Mat<f64>) -> ErrorMetrics {
    assert_eq!(actual.shape(), reference.shape());
    let mut max_absolute: f64 = 0.0;
    let mut reference_max: f64 = 0.0;
    let mut error_squared = 0.0;
    let mut reference_squared = 0.0;

    for row in 0..actual.nrows() {
        for column in 0..actual.ncols() {
            let error = actual[(row, column)] - reference[(row, column)];
            max_absolute = max_absolute.max(error.abs());
            reference_max = reference_max.max(reference[(row, column)].abs());
            error_squared += error * error;
            reference_squared += reference[(row, column)] * reference[(row, column)];
        }
    }

    ErrorMetrics {
        max_absolute,
        relative_l2: error_squared.sqrt() / reference_squared.sqrt().max(f64::MIN_POSITIVE),
        reference_max,
    }
}
