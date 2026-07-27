use faer::{Mat, RowRef};
use ferreus_bbfmm::{FmmParams, FmmTree, KernelFunction, M2LCompressionType};

#[derive(Clone, Copy, Debug)]
struct Gaussian;

impl KernelFunction for Gaussian {
    fn evaluate(&self, target: RowRef<f64>, source: RowRef<f64>) -> f64 {
        gaussian_parts(target, source).0
    }

    fn evaluate_value_gradient(
        &self,
        target: RowRef<f64>,
        source: RowRef<f64>,
        gradient_out: &mut [f64],
    ) -> Option<f64> {
        let (value, displacement) = gaussian_parts(target, source);
        for (gradient, delta) in gradient_out.iter_mut().zip(displacement) {
            *gradient = -2.0 * delta * value;
        }
        Some(value)
    }
}

#[derive(Clone, Copy, Debug)]
struct GaussianGradientComponent {
    axis: usize,
}

impl KernelFunction for GaussianGradientComponent {
    fn evaluate(&self, target: RowRef<f64>, source: RowRef<f64>) -> f64 {
        let (value, displacement) = gaussian_parts(target, source);
        -2.0 * displacement[self.axis] * value
    }

    fn evaluate_value_gradient(
        &self,
        target: RowRef<f64>,
        source: RowRef<f64>,
        gradient_out: &mut [f64],
    ) -> Option<f64> {
        let (value, displacement) = gaussian_parts(target, source);
        for (output_axis, gradient) in gradient_out.iter_mut().enumerate() {
            let diagonal = if output_axis == self.axis { 2.0 } else { 0.0 };
            *gradient =
                (4.0 * displacement[output_axis] * displacement[self.axis] - diagonal) * value;
        }
        Some(-2.0 * displacement[self.axis] * value)
    }
}

fn gaussian_parts(target: RowRef<f64>, source: RowRef<f64>) -> (f64, Vec<f64>) {
    let displacement: Vec<f64> = target
        .iter()
        .zip(source.iter())
        .map(|(target, source)| target - source)
        .collect();
    let squared_radius: f64 = displacement.iter().map(|value| value * value).sum();
    ((-squared_radius).exp(), displacement)
}

fn transform(dim: usize) -> Vec<Vec<f64>> {
    match dim {
        1 => vec![vec![1.3]],
        2 => vec![vec![1.2, 0.35], vec![0.0, 0.8]],
        3 => vec![
            vec![1.2, 0.30, -0.10],
            vec![0.0, 0.90, 0.25],
            vec![0.0, 0.0, 1.10],
        ],
        _ => unreachable!(),
    }
}

fn source_coordinate(index: usize, axis: usize) -> f64 {
    let value = (index * (37 + 11 * axis) + 17 * axis + 13) % 997;
    -0.8 + 1.6 * value as f64 / 996.0
}

fn target_coordinate(index: usize, axis: usize) -> f64 {
    let value = (index * (53 + 7 * axis) + 29 * axis + 101) % 991;
    -0.75 + 1.5 * value as f64 / 990.0
}

fn scalar_weight(index: usize) -> f64 {
    ((index * 19 + 7) as f64 * 0.37).sin() * (1.0 + (index % 5) as f64 * 0.2)
}

fn physical_vector_weight(index: usize, axis: usize) -> f64 {
    let sign = if (index + axis) % 2 == 0 { 1.0 } else { -1.0 };
    sign * (((index + 3) * (axis + 2)) as f64 * 0.23).cos()
        * (1.0 + axis as f64 * 0.4)
}

fn transform_points(points: &Mat<f64>, transform: &[Vec<f64>]) -> Mat<f64> {
    Mat::from_fn(points.nrows(), points.ncols(), |row, output_axis| {
        (0..points.ncols())
            .map(|input_axis| transform[output_axis][input_axis] * points[(row, input_axis)])
            .sum()
    })
}

fn metric_vector_weights(
    source_count: usize,
    dim: usize,
    transform: &[Vec<f64>],
) -> Mat<f64> {
    Mat::from_fn(source_count, dim, |row, output_axis| {
        (0..dim)
            .map(|input_axis| {
                transform[output_axis][input_axis]
                    * physical_vector_weight(row, input_axis)
            })
            .sum()
    })
}

fn physical_output(metric_output: &[f64], transform: &[Vec<f64>]) -> Vec<f64> {
    let dim = metric_output.len();
    (0..dim)
        .map(|physical_axis| {
            (0..dim)
                .map(|metric_axis| transform[metric_axis][physical_axis] * metric_output[metric_axis])
                .sum()
        })
        .collect()
}

fn tree_extents(sources: &Mat<f64>, targets: &Mat<f64>) -> Vec<f64> {
    let dim = sources.ncols();
    let mut lower = vec![f64::INFINITY; dim];
    let mut upper = vec![f64::NEG_INFINITY; dim];
    for points in [sources, targets] {
        for row in points.row_iter() {
            for axis in 0..dim {
                lower[axis] = lower[axis].min(row[axis]);
                upper[axis] = upper[axis].max(row[axis]);
            }
        }
    }
    for axis in 0..dim {
        lower[axis] -= 0.05;
        upper[axis] += 0.05;
    }
    lower.extend(upper);
    lower
}

fn max_abs_diff(left: &Mat<f64>, right: &Mat<f64>) -> f64 {
    assert_eq!(left.shape(), right.shape());
    let mut maximum: f64 = 0.0;
    for row in 0..left.nrows() {
        for column in 0..left.ncols() {
            maximum = maximum.max((left[(row, column)] - right[(row, column)]).abs());
        }
    }
    maximum
}

fn run_case(dim: usize, self_geometry: bool, force_far_field: bool) {
    let source_count = 128;
    let target_count = if self_geometry { source_count } else { 83 };
    let physical_sources =
        Mat::from_fn(source_count, dim, |row, axis| source_coordinate(row, axis));
    let physical_targets = if self_geometry {
        physical_sources.clone()
    } else {
        Mat::from_fn(target_count, dim, |row, axis| target_coordinate(row, axis))
    };
    let transform = transform(dim);
    let sources = transform_points(&physical_sources, &transform);
    let targets = transform_points(&physical_targets, &transform);
    let extents = tree_extents(&sources, &targets);
    let scalar_weights = Mat::from_fn(source_count, 1, |row, _| scalar_weight(row));
    let vector_weights = metric_vector_weights(source_count, dim, &transform);

    let params = FmmParams {
        max_points_per_cell: if force_far_field { 4 } else { source_count + 1 },
        compression_type: M2LCompressionType::None,
        epsilon: 0.0,
        eval_chunk_size: 64,
    };
    let mut radial_tree = FmmTree::new(
        sources.clone(),
        8,
        Gaussian,
        false,
        false,
        Some(extents.clone()),
        Some(params),
    );
    radial_tree.set_weights(&scalar_weights.as_ref());
    let (candidate_a, candidate_ft_metric) = radial_tree
        .evaluate_with_gradients(&scalar_weights.as_ref(), &targets)
        .unwrap();

    let mut radial_vector_tree = FmmTree::new(
        sources.clone(),
        8,
        Gaussian,
        false,
        false,
        Some(extents.clone()),
        Some(params),
    );
    radial_vector_tree.set_weights(&vector_weights.as_ref());
    let (_, radial_vector_gradients) = radial_vector_tree
        .evaluate_with_gradients(&vector_weights.as_ref(), &targets)
        .unwrap();
    let candidate_f_radial_rhs_unsigned = Mat::from_fn(target_count, 1, |target, _| {
        (0..dim)
            .map(|axis| radial_vector_gradients[(target, axis * dim + axis)])
            .sum::<f64>()
    });
    // Canonical F is the fixed negative displacement-gradient row.
    let candidate_f_radial_rhs = Mat::from_fn(target_count, 1, |target, _| {
        -candidate_f_radial_rhs_unsigned[(target, 0)]
    });

    let mut candidate_f_unsigned: Mat<f64> = Mat::zeros(target_count, 1);
    let mut candidate_h_metric = Mat::zeros(target_count, dim);
    for source_axis in 0..dim {
        let component_weights =
            Mat::from_fn(source_count, 1, |row, _| vector_weights[(row, source_axis)]);
        let mut component_tree = FmmTree::new(
            sources.clone(),
            8,
            GaussianGradientComponent { axis: source_axis },
            false,
            false,
            Some(extents.clone()),
            Some(params),
        );
        component_tree.set_weights(&component_weights.as_ref());
        let (values, gradients) = component_tree
            .evaluate_with_gradients(&component_weights.as_ref(), &targets)
            .unwrap();
        for target in 0..target_count {
            candidate_f_unsigned[(target, 0)] += values[(target, 0)];
            for output_axis in 0..dim {
                candidate_h_metric[(target, output_axis)] += gradients[(target, output_axis)];
            }
        }
    }
    let candidate_f = Mat::from_fn(target_count, 1, |target, _| {
        -candidate_f_unsigned[(target, 0)]
    });

    let mut direct_a = Mat::zeros(target_count, 1);
    let mut direct_ft_metric = Mat::zeros(target_count, dim);
    let mut direct_f_unsigned: Mat<f64> = Mat::zeros(target_count, 1);
    let mut direct_h_metric = Mat::zeros(target_count, dim);
    for target in 0..target_count {
        for source in 0..source_count {
            let (value, displacement) = gaussian_parts(targets.row(target), sources.row(source));
            direct_a[(target, 0)] += value * scalar_weights[(source, 0)];
            for output_axis in 0..dim {
                let gradient = -2.0 * displacement[output_axis] * value;
                direct_ft_metric[(target, output_axis)] +=
                    gradient * scalar_weights[(source, 0)];
                direct_f_unsigned[(target, 0)] +=
                    gradient * vector_weights[(source, output_axis)];
                for source_axis in 0..dim {
                    let diagonal = if output_axis == source_axis { 2.0 } else { 0.0 };
                    let hessian = (4.0
                        * displacement[output_axis]
                        * displacement[source_axis]
                        - diagonal)
                        * value;
                    direct_h_metric[(target, output_axis)] +=
                        hessian * vector_weights[(source, source_axis)];
                }
            }
        }
    }
    let direct_f = Mat::from_fn(target_count, 1, |target, _| {
        -direct_f_unsigned[(target, 0)]
    });

    let candidate_ft = Mat::from_fn(target_count, dim, |target, physical_axis| {
        let metric: Vec<f64> = (0..dim)
            .map(|metric_axis| candidate_ft_metric[(target, metric_axis)])
            .collect();
        physical_output(&metric, &transform)[physical_axis]
    });
    let direct_ft = Mat::from_fn(target_count, dim, |target, physical_axis| {
        let metric: Vec<f64> = (0..dim)
            .map(|metric_axis| direct_ft_metric[(target, metric_axis)])
            .collect();
        physical_output(&metric, &transform)[physical_axis]
    });
    let candidate_h = Mat::from_fn(target_count, dim, |target, physical_axis| {
        let metric: Vec<f64> = (0..dim)
            .map(|metric_axis| candidate_h_metric[(target, metric_axis)])
            .collect();
        -physical_output(&metric, &transform)[physical_axis]
    });
    let direct_h = Mat::from_fn(target_count, dim, |target, physical_axis| {
        let metric: Vec<f64> = (0..dim)
            .map(|metric_axis| direct_h_metric[(target, metric_axis)])
            .collect();
        -physical_output(&metric, &transform)[physical_axis]
    });

    let mut f_sign_witness_target = 0;
    for target in 1..target_count {
        if direct_f_unsigned[(target, 0)].abs()
            > direct_f_unsigned[(f_sign_witness_target, 0)].abs()
        {
            f_sign_witness_target = target;
        }
    }
    let f_candidate_unsigned_witness =
        candidate_f_radial_rhs_unsigned[(f_sign_witness_target, 0)];
    let f_candidate_canonical_witness =
        candidate_f_radial_rhs[(f_sign_witness_target, 0)];
    let f_direct_unsigned_witness = direct_f_unsigned[(f_sign_witness_target, 0)];
    let f_direct_canonical_witness = direct_f[(f_sign_witness_target, 0)];
    assert!(f_direct_unsigned_witness.abs() > 0.0);
    assert_eq!(
        f_candidate_canonical_witness,
        -f_candidate_unsigned_witness
    );
    assert_eq!(f_direct_canonical_witness, -f_direct_unsigned_witness);
    assert!(f_candidate_canonical_witness * f_direct_canonical_witness > 0.0);

    println!(
        "{{\"dimension\":{dim},\"geometry\":\"{}\",\"route\":\"{}\",\"A_error\":{:.17e},\"FT_error\":{:.17e},\"F_external_sign\":-1,\"F_sign_witness_target\":{},\"F_candidate_unsigned_witness\":{:.17e},\"F_candidate_canonical_witness\":{:.17e},\"F_direct_unsigned_witness\":{:.17e},\"F_direct_canonical_witness\":{:.17e},\"F_radial_multi_rhs_error\":{:.17e},\"F_scalar_component_hack_error\":{:.17e},\"H_component_control_external_sign\":-1,\"H_scalar_component_hack_error\":{:.17e}}}",
        if self_geometry { "self" } else { "cross" },
        if force_far_field { "symmetry-reduced-far-field" } else { "near-field-control" },
        max_abs_diff(&candidate_a, &direct_a),
        max_abs_diff(&candidate_ft, &direct_ft),
        f_sign_witness_target,
        f_candidate_unsigned_witness,
        f_candidate_canonical_witness,
        f_direct_unsigned_witness,
        f_direct_canonical_witness,
        max_abs_diff(&candidate_f_radial_rhs, &direct_f),
        max_abs_diff(&candidate_f, &direct_f),
        max_abs_diff(&candidate_h, &direct_h),
    );
}

fn main() {
    for dimension in 1..=3 {
        run_case(dimension, false, false);
        run_case(dimension, true, false);
        run_case(dimension, false, true);
        run_case(dimension, true, true);
    }
}
