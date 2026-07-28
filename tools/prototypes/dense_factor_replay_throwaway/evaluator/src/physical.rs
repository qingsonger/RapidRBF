use astro_float_num::{BigFloat, Consts, RoundingMode};

use crate::evaluator::EvaluationError;
use crate::interval::Interval;

pub const DIMENSION: usize = 3;

#[derive(Clone, Debug)]
pub struct PhysicalModel {
    pub nugget: f64,
    pub polynomial_degree: i32,
    pub components: Vec<RbfComponent>,
}

#[derive(Clone, Debug)]
pub struct RbfComponent {
    pub family: String,
    pub parameters: Vec<f64>,
    pub anisotropy: [[f64; DIMENSION]; DIMENSION],
}

#[derive(Clone, Debug)]
pub struct Geometry {
    pub value_points: Vec<[f64; DIMENSION]>,
    pub gradient_points: Vec<[f64; DIMENSION]>,
}

#[derive(Clone, Debug)]
pub struct ActionRow {
    pub prediction: Interval,
    pub scale_upper: BigFloat,
}

struct IntervalComponent {
    family: String,
    parameters: Vec<Interval>,
    anisotropy: [[Interval; DIMENSION]; DIMENSION],
}

struct KernelJet {
    value: Interval,
    gradient: Option<[Interval; DIMENSION]>,
    hessian: Option<[[Interval; DIMENSION]; DIMENSION]>,
}

type IsotropicJet = (
    Interval,
    Option<[Interval; DIMENSION]>,
    Option<[[Interval; DIMENSION]; DIMENSION]>,
);

#[derive(Clone, Copy, Eq, PartialEq)]
enum JetOrder {
    Value,
    Gradient,
    Hessian,
}

struct Accumulator {
    sum: Interval,
    scale_upper: BigFloat,
    precision: usize,
}

impl Accumulator {
    fn new(precision: usize) -> Self {
        Self {
            sum: Interval::zero(precision),
            scale_upper: BigFloat::new(precision),
            precision,
        }
    }

    fn add(&mut self, term: Interval) {
        let scale_upper = term.abs_upper();
        self.add_with_scale(term, scale_upper);
    }

    fn add_with_scale(&mut self, term: Interval, scale_upper: BigFloat) {
        self.scale_upper = self
            .scale_upper
            .add(&scale_upper, self.precision, RoundingMode::Up);
        self.sum = self.sum.add(&term);
    }

    fn finish(self) -> ActionRow {
        ActionRow {
            prediction: self.sum,
            scale_upper: self.scale_upper,
        }
    }
}

fn add_entry_component(
    entry: &mut Interval,
    scale_upper: &mut BigFloat,
    component: Interval,
    precision: usize,
) {
    *scale_upper = scale_upper.add(&component.abs_upper(), precision, RoundingMode::Up);
    *entry = entry.add(&component);
}

pub fn polynomial_order(degree: i32) -> Result<usize, EvaluationError> {
    match degree {
        0 => Ok(1),
        1 => Ok(4),
        _ => Err(EvaluationError::new(
            "UnsupportedPolynomialDegree",
            format!("only physical 3D degree 0/1 is supported, got {degree}"),
        )),
    }
}

pub fn evaluate_action(
    model: &PhysicalModel,
    geometry: &Geometry,
    lambda: &[f64],
    polynomial: Option<&[f64]>,
    precision: usize,
    constants: &mut Consts,
) -> Result<Vec<ActionRow>, EvaluationError> {
    evaluate_action_with_entries(
        model,
        geometry,
        lambda,
        polynomial,
        precision,
        constants,
        |_, _, _, _, _| Ok(()),
    )
}

pub fn evaluate_action_with_entries<F>(
    model: &PhysicalModel,
    geometry: &Geometry,
    lambda: &[f64],
    polynomial: Option<&[f64]>,
    precision: usize,
    constants: &mut Consts,
    mut entry_visitor: F,
) -> Result<Vec<ActionRow>, EvaluationError>
where
    F: FnMut(usize, usize, &Interval, &BigFloat, bool) -> Result<(), EvaluationError>,
{
    validate_model(model)?;
    let value_count = geometry.value_points.len();
    let gradient_count = geometry.gradient_points.len();
    let scalar_order = value_count
        .checked_add(gradient_count.checked_mul(DIMENSION).ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "gradient scalar order overflow")
        })?)
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "scalar order overflow"))?;
    if lambda.len() != scalar_order {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "reference_lambda has length {}, expected {scalar_order}",
                lambda.len()
            ),
        ));
    }
    reject_nonfinite("reference_lambda", lambda)?;
    for (index, point) in geometry
        .value_points
        .iter()
        .chain(&geometry.gradient_points)
        .enumerate()
    {
        reject_nonfinite(&format!("physical coordinate row {index}"), point)?;
    }

    let expected_polynomial = polynomial_order(model.polynomial_degree)?;
    let top_value_count = expected_polynomial.min(value_count);
    if let Some(coefficients) = polynomial {
        if coefficients.len() != expected_polynomial {
            return Err(EvaluationError::new(
                "MalformedPayload",
                format!(
                    "reference_c has length {}, expected {expected_polynomial}",
                    coefficients.len()
                ),
            ));
        }
        reject_nonfinite("reference_c", coefficients)?;
    }
    let needs_derivatives = gradient_count != 0;
    if needs_derivatives
        && model
            .components
            .iter()
            .any(|component| component.family == "exp")
    {
        return Err(EvaluationError::new(
            "UndefinedKernelDerivative",
            "exp is value-only and cannot be used with gradient rows",
        ));
    }

    let interval_components = model
        .components
        .iter()
        .map(|component| interval_component(component, precision))
        .collect::<Result<Vec<_>, _>>()?;
    let interval_value_points = geometry
        .value_points
        .iter()
        .map(|point| exact_point(point, precision))
        .collect::<Result<Vec<_>, _>>()?;
    let interval_gradient_points = geometry
        .gradient_points
        .iter()
        .map(|point| exact_point(point, precision))
        .collect::<Result<Vec<_>, _>>()?;
    let lambda_intervals = lambda
        .iter()
        .map(|value| Interval::exact(*value, precision).map_err(interval_error))
        .collect::<Result<Vec<_>, _>>()?;
    let polynomial_intervals = polynomial
        .map(|values| {
            values
                .iter()
                .map(|value| Interval::exact(*value, precision).map_err(interval_error))
                .collect::<Result<Vec<_>, _>>()
        })
        .transpose()?;
    let nugget = Interval::exact(model.nugget, precision).map_err(interval_error)?;

    // Reconstruct the symmetric physical operator by geometric blocks. The
    // first l scalar rows are the canonical polynomial anchors. Visit every
    // top/top and top/tail entry before tail/tail so a caller can stream the
    // Q=[Q_top;I] congruence using only O(l*m) scratch.
    let mut accumulators = (0..scalar_order)
        .map(|_| Accumulator::new(precision))
        .collect::<Vec<_>>();

    let mut emit_entry = |left: usize,
                          right: usize,
                          entry: Interval,
                          entry_scale: BigFloat,
                          mirror: bool|
     -> Result<(), EvaluationError> {
        let right_coefficient = &lambda_intervals[right];
        let right_scale = entry_scale.mul(
            &BigFloat::from_f64(lambda[right].abs(), precision),
            precision,
            RoundingMode::Up,
        );
        accumulators[left].add_with_scale(entry.mul(right_coefficient), right_scale);
        if mirror {
            let left_scale = entry_scale.mul(
                &BigFloat::from_f64(lambda[left].abs(), precision),
                precision,
                RoundingMode::Up,
            );
            accumulators[right].add_with_scale(entry.mul(&lambda_intervals[left]), left_scale);
        }
        entry_visitor(left, right, &entry, &entry_scale, mirror)
    };

    for left in 0..top_value_count {
        for right in left..value_count {
            let mut entry = Interval::zero(precision);
            let mut entry_scale = BigFloat::new(precision);
            for component in &interval_components {
                let jet = kernel_jet(
                    component,
                    &interval_value_points[left],
                    &interval_value_points[right],
                    JetOrder::Value,
                    constants,
                )?;
                add_entry_component(&mut entry, &mut entry_scale, jet.value, precision);
            }
            if left == right {
                add_entry_component(&mut entry, &mut entry_scale, nugget.clone(), precision);
            }
            emit_entry(left, right, entry, entry_scale, left != right)?;
        }
    }

    for (value_index, value_point) in interval_value_points
        .iter()
        .enumerate()
        .take(top_value_count)
    {
        for (gradient_index, gradient_point) in interval_gradient_points.iter().enumerate() {
            let mut entries = std::array::from_fn::<_, DIMENSION, _>(|_| Interval::zero(precision));
            let mut entry_scales =
                std::array::from_fn::<_, DIMENSION, _>(|_| BigFloat::new(precision));
            for component in &interval_components {
                let jet = kernel_jet(
                    component,
                    value_point,
                    gradient_point,
                    JetOrder::Gradient,
                    constants,
                )?;
                let gradient = jet.gradient.as_ref().expect("requested gradient jet");
                for (channel, gradient_entry) in gradient.iter().enumerate() {
                    let matrix_entry = gradient_entry.neg();
                    add_entry_component(
                        &mut entries[channel],
                        &mut entry_scales[channel],
                        matrix_entry,
                        precision,
                    );
                }
            }
            for channel in 0..DIMENSION {
                let gradient_row = value_count + DIMENSION * gradient_index + channel;
                emit_entry(
                    value_index,
                    gradient_row,
                    entries[channel].clone(),
                    entry_scales[channel].clone(),
                    true,
                )?;
            }
        }
    }

    for left in top_value_count..value_count {
        for right in left..value_count {
            let mut entry = Interval::zero(precision);
            let mut entry_scale = BigFloat::new(precision);
            for component in &interval_components {
                let jet = kernel_jet(
                    component,
                    &interval_value_points[left],
                    &interval_value_points[right],
                    JetOrder::Value,
                    constants,
                )?;
                add_entry_component(&mut entry, &mut entry_scale, jet.value, precision);
            }
            if left == right {
                add_entry_component(&mut entry, &mut entry_scale, nugget.clone(), precision);
            }
            emit_entry(left, right, entry, entry_scale, left != right)?;
        }
    }

    for (value_index, value_point) in interval_value_points
        .iter()
        .enumerate()
        .skip(top_value_count)
    {
        for (gradient_index, gradient_point) in interval_gradient_points.iter().enumerate() {
            let mut entries = std::array::from_fn::<_, DIMENSION, _>(|_| Interval::zero(precision));
            let mut entry_scales =
                std::array::from_fn::<_, DIMENSION, _>(|_| BigFloat::new(precision));
            for component in &interval_components {
                let jet = kernel_jet(
                    component,
                    value_point,
                    gradient_point,
                    JetOrder::Gradient,
                    constants,
                )?;
                let gradient = jet.gradient.as_ref().expect("requested gradient jet");
                for (channel, gradient_entry) in gradient.iter().enumerate() {
                    add_entry_component(
                        &mut entries[channel],
                        &mut entry_scales[channel],
                        gradient_entry.neg(),
                        precision,
                    );
                }
            }
            for channel in 0..DIMENSION {
                let gradient_row = value_count + DIMENSION * gradient_index + channel;
                emit_entry(
                    value_index,
                    gradient_row,
                    entries[channel].clone(),
                    entry_scales[channel].clone(),
                    true,
                )?;
            }
        }
    }

    for left_point in 0..gradient_count {
        for right_point in left_point..gradient_count {
            let mut entries = std::array::from_fn::<_, DIMENSION, _>(|_| {
                std::array::from_fn::<_, DIMENSION, _>(|_| Interval::zero(precision))
            });
            let mut entry_scales = std::array::from_fn::<_, DIMENSION, _>(|_| {
                std::array::from_fn::<_, DIMENSION, _>(|_| BigFloat::new(precision))
            });
            for component in &interval_components {
                let jet = kernel_jet(
                    component,
                    &interval_gradient_points[left_point],
                    &interval_gradient_points[right_point],
                    JetOrder::Hessian,
                    constants,
                )?;
                let hessian = jet.hessian.as_ref().expect("requested hessian jet");
                for (left_channel, hessian_row) in hessian.iter().enumerate() {
                    for (right_channel, hessian_entry) in hessian_row.iter().enumerate() {
                        let matrix_entry = hessian_entry.neg();
                        add_entry_component(
                            &mut entries[left_channel][right_channel],
                            &mut entry_scales[left_channel][right_channel],
                            matrix_entry,
                            precision,
                        );
                    }
                }
            }
            for left_channel in 0..DIMENSION {
                let left_row = value_count + DIMENSION * left_point + left_channel;
                for right_channel in 0..DIMENSION {
                    let right_row = value_count + DIMENSION * right_point + right_channel;
                    emit_entry(
                        left_row,
                        right_row,
                        entries[left_channel][right_channel].clone(),
                        entry_scales[left_channel][right_channel].clone(),
                        left_point != right_point,
                    )?;
                }
            }
        }
    }

    if let Some(coefficients) = &polynomial_intervals {
        for (row, point) in interval_value_points.iter().enumerate() {
            for (basis, coefficient) in polynomial_values(model.polynomial_degree, point)?
                .iter()
                .zip(coefficients)
            {
                accumulators[row].add(basis.mul(coefficient));
            }
        }
        for gradient_index in 0..gradient_count {
            for channel in 0..DIMENSION {
                let row = value_count + DIMENSION * gradient_index + channel;
                let derivative = polynomial_gradient(model.polynomial_degree, channel, precision)?;
                for (basis, coefficient) in derivative.iter().zip(coefficients) {
                    accumulators[row].add(basis.mul(coefficient));
                }
            }
        }
    }
    Ok(accumulators.into_iter().map(Accumulator::finish).collect())
}

pub fn polynomial_rows(
    degree: i32,
    geometry: &Geometry,
    precision: usize,
) -> Result<Vec<Vec<Interval>>, EvaluationError> {
    let order = polynomial_order(degree)?;
    let mut rows = Vec::with_capacity(
        geometry.value_points.len() + DIMENSION * geometry.gradient_points.len(),
    );
    for point in &geometry.value_points {
        rows.push(
            polynomial_values(degree, &exact_point(point, precision)?)?
                .into_iter()
                .take(order)
                .collect(),
        );
    }
    for _point in &geometry.gradient_points {
        for component in 0..DIMENSION {
            rows.push(
                polynomial_gradient(degree, component, precision)?
                    .into_iter()
                    .take(order)
                    .collect(),
            );
        }
    }
    Ok(rows)
}

fn validate_model(model: &PhysicalModel) -> Result<(), EvaluationError> {
    if !model.nugget.is_finite() || model.nugget < 0.0 {
        return Err(EvaluationError::new(
            "NonfiniteOrInvalidModel",
            "nugget must be finite and nonnegative",
        ));
    }
    let _ = polynomial_order(model.polynomial_degree)?;
    if model.components.is_empty() {
        return Err(EvaluationError::new(
            "NonfiniteOrInvalidModel",
            "model must contain at least one RBF component",
        ));
    }
    for component in &model.components {
        for row in &component.anisotropy {
            reject_nonfinite("anisotropy", row)?;
        }
        match component.family.as_str() {
            "th3" => {
                if component.parameters.len() != 2
                    || !component.parameters[0].is_finite()
                    || !component.parameters[1].is_finite()
                    || component.parameters[0] < 0.0
                    || component.parameters[1] < 0.0
                {
                    return Err(EvaluationError::new(
                        "NonfiniteOrInvalidModel",
                        "th3 requires finite nonnegative [scale,c]",
                    ));
                }
            }
            "gau" | "exp" => {
                if component.parameters.len() != 2
                    || !component.parameters[0].is_finite()
                    || !component.parameters[1].is_finite()
                    || component.parameters[0] < 0.0
                    || component.parameters[1] <= 0.0
                {
                    return Err(EvaluationError::new(
                        "NonfiniteOrInvalidModel",
                        format!(
                            "{} requires finite [partial_sill>=0,range>0]",
                            component.family
                        ),
                    ));
                }
            }
            family => {
                return Err(EvaluationError::new(
                    "UnknownKernelFamily",
                    format!("unsupported RBF family {family}"),
                ));
            }
        }
    }
    Ok(())
}

fn interval_component(
    component: &RbfComponent,
    precision: usize,
) -> Result<IntervalComponent, EvaluationError> {
    let parameters = component
        .parameters
        .iter()
        .map(|value| Interval::exact(*value, precision).map_err(interval_error))
        .collect::<Result<Vec<_>, _>>()?;
    let anisotropy = std::array::from_fn(|row| {
        std::array::from_fn(|column| {
            Interval::exact(component.anisotropy[row][column], precision)
                .expect("model was validated")
        })
    });
    Ok(IntervalComponent {
        family: component.family.clone(),
        parameters,
        anisotropy,
    })
}

fn kernel_jet(
    component: &IntervalComponent,
    target: &[Interval; DIMENSION],
    source: &[Interval; DIMENSION],
    order: JetOrder,
    constants: &mut Consts,
) -> Result<KernelJet, EvaluationError> {
    let precision = target[0].precision();
    let displacement: [Interval; DIMENSION] =
        std::array::from_fn(|index| target[index].sub(&source[index]));
    let transformed: [Interval; DIMENSION] = std::array::from_fn(|row| {
        let mut sum = Interval::zero(precision);
        for (column, value) in displacement.iter().enumerate() {
            sum = sum.add(&component.anisotropy[row][column].mul(value));
        }
        sum
    });
    let radius_squared = transformed
        .iter()
        .fold(Interval::zero(precision), |sum, value| {
            sum.add(&value.square())
        });

    let (value, iso_gradient, iso_hessian) = match component.family.as_str() {
        "th3" => th3_jet(&component.parameters, &transformed, &radius_squared, order)?,
        "gau" => gau_jet(
            &component.parameters,
            &transformed,
            &radius_squared,
            order,
            constants,
        )?,
        "exp" => exp_value(&component.parameters, &radius_squared, order, constants)?,
        family => {
            return Err(EvaluationError::new(
                "UnknownKernelFamily",
                format!("unsupported RBF family {family}"),
            ));
        }
    };

    if order == JetOrder::Value {
        return Ok(KernelJet {
            value,
            gradient: None,
            hessian: None,
        });
    }
    let iso_gradient = iso_gradient.expect("derivative kernel supplies gradient");
    let gradient = std::array::from_fn(|physical| {
        let mut sum = Interval::zero(precision);
        for (iso, iso_entry) in iso_gradient.iter().enumerate() {
            sum = sum.add(&component.anisotropy[iso][physical].mul(iso_entry));
        }
        sum
    });
    if order == JetOrder::Gradient {
        return Ok(KernelJet {
            value,
            gradient: Some(gradient),
            hessian: None,
        });
    }
    let iso_hessian = iso_hessian.expect("Hessian kernel supplies hessian");
    let hessian = std::array::from_fn(|left| {
        std::array::from_fn(|right| {
            let mut sum = Interval::zero(precision);
            for (iso_left, iso_row) in iso_hessian.iter().enumerate() {
                for (iso_right, iso_entry) in iso_row.iter().enumerate() {
                    let term = component.anisotropy[iso_left][left]
                        .mul(iso_entry)
                        .mul(&component.anisotropy[iso_right][right]);
                    sum = sum.add(&term);
                }
            }
            sum
        })
    });
    Ok(KernelJet {
        value,
        gradient: Some(gradient),
        hessian: Some(hessian),
    })
}

fn th3_jet(
    parameters: &[Interval],
    transformed: &[Interval; DIMENSION],
    radius_squared: &Interval,
    order: JetOrder,
) -> Result<IsotropicJet, EvaluationError> {
    let precision = radius_squared.precision();
    let scale = &parameters[0];
    let c_squared = parameters[1].square();
    let q_squared = radius_squared.add(&c_squared);
    let q = q_squared.sqrt().map_err(interval_error)?;
    let value = scale.mul(&q_squared).mul(&q);
    if order == JetOrder::Value {
        return Ok((value, None, None));
    }
    if q.is_exact_zero() {
        return Ok((
            value,
            Some(std::array::from_fn(|_| Interval::zero(precision))),
            (order == JetOrder::Hessian).then(|| {
                std::array::from_fn(|_| std::array::from_fn(|_| Interval::zero(precision)))
            }),
        ));
    }
    let three = Interval::exact(3.0, precision).map_err(interval_error)?;
    let factor = three.mul(scale);
    let gradient = std::array::from_fn(|index| factor.mul(&q).mul(&transformed[index]));
    if order == JetOrder::Gradient {
        return Ok((value, Some(gradient), None));
    }
    let hessian = std::array::from_fn(|row| {
        std::array::from_fn(|column| {
            let base = if row == column {
                q.clone()
            } else {
                Interval::zero(precision)
            };
            let ratio = if q.contains_zero() {
                // q >= |u_i| and q >= |u_j|, so |u_i u_j / q| <= q.
                Interval::hull(&[q.neg(), q.clone()]).expect("two-value hull")
            } else {
                transformed[row]
                    .mul(&transformed[column])
                    .div(&q)
                    .expect("q excludes zero")
            };
            factor.mul(&base.add(&ratio))
        })
    });
    Ok((value, Some(gradient), Some(hessian)))
}

fn gau_jet(
    parameters: &[Interval],
    transformed: &[Interval; DIMENSION],
    radius_squared: &Interval,
    order: JetOrder,
    constants: &mut Consts,
) -> Result<IsotropicJet, EvaluationError> {
    let precision = radius_squared.precision();
    let three = Interval::exact(3.0, precision).map_err(interval_error)?;
    let two = Interval::exact(2.0, precision).map_err(interval_error)?;
    let four = Interval::exact(4.0, precision).map_err(interval_error)?;
    let beta = three.div(&parameters[1].square()).map_err(interval_error)?;
    let exponent = beta.mul(radius_squared).neg();
    let value = parameters[0].mul(&exponent.exp(constants).map_err(interval_error)?);
    if order == JetOrder::Value {
        return Ok((value, None, None));
    }
    let minus_two_beta_phi = two.mul(&beta).mul(&value).neg();
    let gradient = std::array::from_fn(|index| minus_two_beta_phi.mul(&transformed[index]));
    if order == JetOrder::Gradient {
        return Ok((value, Some(gradient), None));
    }
    let positive = four.mul(&beta.square()).mul(&value);
    let hessian = std::array::from_fn(|row| {
        std::array::from_fn(|column| {
            let diagonal = if row == column {
                minus_two_beta_phi.clone()
            } else {
                Interval::zero(precision)
            };
            diagonal.add(&positive.mul(&transformed[row]).mul(&transformed[column]))
        })
    });
    Ok((value, Some(gradient), Some(hessian)))
}

fn exp_value(
    parameters: &[Interval],
    radius_squared: &Interval,
    order: JetOrder,
    constants: &mut Consts,
) -> Result<IsotropicJet, EvaluationError> {
    if order != JetOrder::Value {
        return Err(EvaluationError::new(
            "UndefinedKernelDerivative",
            "exp is value-only",
        ));
    }
    let precision = radius_squared.precision();
    let radius = radius_squared.sqrt().map_err(interval_error)?;
    let three = Interval::exact(3.0, precision).map_err(interval_error)?;
    let exponent = three
        .mul(&radius)
        .div(&parameters[1])
        .map_err(interval_error)?
        .neg();
    let value = parameters[0].mul(&exponent.exp(constants).map_err(interval_error)?);
    Ok((value, None, None))
}

fn polynomial_values(
    degree: i32,
    point: &[Interval; DIMENSION],
) -> Result<[Interval; 4], EvaluationError> {
    let precision = point[0].precision();
    match degree {
        0 => Ok([
            Interval::one(precision),
            Interval::zero(precision),
            Interval::zero(precision),
            Interval::zero(precision),
        ]),
        1 => Ok([
            Interval::one(precision),
            point[0].clone(),
            point[1].clone(),
            point[2].clone(),
        ]),
        _ => Err(EvaluationError::new(
            "UnsupportedPolynomialDegree",
            format!("unsupported polynomial degree {degree}"),
        )),
    }
}

fn polynomial_gradient(
    degree: i32,
    component: usize,
    precision: usize,
) -> Result<[Interval; 4], EvaluationError> {
    match degree {
        0 => Ok(std::array::from_fn(|_| Interval::zero(precision))),
        1 => Ok(std::array::from_fn(|basis| {
            if basis == component + 1 {
                Interval::one(precision)
            } else {
                Interval::zero(precision)
            }
        })),
        _ => Err(EvaluationError::new(
            "UnsupportedPolynomialDegree",
            format!("unsupported polynomial degree {degree}"),
        )),
    }
}

fn exact_point(
    point: &[f64; DIMENSION],
    precision: usize,
) -> Result<[Interval; DIMENSION], EvaluationError> {
    Ok(std::array::from_fn(|index| {
        Interval::exact(point[index], precision).expect("coordinates were validated")
    }))
}

fn reject_nonfinite(name: &str, values: &[f64]) -> Result<(), EvaluationError> {
    if let Some((index, _)) = values
        .iter()
        .enumerate()
        .find(|(_, value)| !value.is_finite())
    {
        Err(EvaluationError::new(
            "NonfiniteInput",
            format!("{name}[{index}] is nonfinite"),
        ))
    } else {
        Ok(())
    }
}

fn interval_error(message: String) -> EvaluationError {
    EvaluationError::new("IntervalArithmetic", message)
}

#[cfg(test)]
mod tests {
    use astro_float_num::Consts;

    use super::{Geometry, PhysicalModel, RbfComponent, evaluate_action};

    const P: usize = 256;

    fn identity() -> [[f64; 3]; 3] {
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    }

    #[test]
    fn nugget_uses_value_row_identity_not_coordinate_equality() {
        let model = PhysicalModel {
            nugget: 0.25,
            polynomial_degree: 0,
            components: vec![RbfComponent {
                family: "gau".to_owned(),
                parameters: vec![1.0, 1.0],
                anisotropy: identity(),
            }],
        };
        let geometry = Geometry {
            value_points: vec![[0.0; 3], [0.0; 3]],
            gradient_points: vec![],
        };
        let mut constants = Consts::new().unwrap();
        let rows =
            evaluate_action(&model, &geometry, &[1.0, 0.0], None, P, &mut constants).unwrap();
        let difference = rows[0].prediction.sub(&rows[1].prediction);
        assert!(difference.lower_f64() <= 0.25);
        assert!(difference.upper_f64() >= 0.25);
        assert!(difference.lower_f64() > 0.249_999_999_999);
    }

    #[test]
    fn canonical_source_gradient_sign_is_negative() {
        let model = PhysicalModel {
            nugget: 0.0,
            polynomial_degree: 0,
            components: vec![RbfComponent {
                family: "gau".to_owned(),
                parameters: vec![1.0, 1.0],
                anisotropy: identity(),
            }],
        };
        let geometry = Geometry {
            value_points: vec![[1.0, 0.0, 0.0]],
            gradient_points: vec![[0.0, 0.0, 0.0]],
        };
        let mut constants = Consts::new().unwrap();
        let rows = evaluate_action(
            &model,
            &geometry,
            &[0.0, 1.0, 0.0, 0.0],
            None,
            P,
            &mut constants,
        )
        .unwrap();
        // g_x at d=(1,0,0) is negative for the Gaussian; the canonical
        // value<-source-gradient sign negates it.
        assert!(rows[0].prediction.lower_f64() > 0.0);
    }

    #[test]
    fn physical_anisotropy_gradient_matches_closed_form_direction() {
        let model = PhysicalModel {
            nugget: 0.0,
            polynomial_degree: 0,
            components: vec![RbfComponent {
                family: "gau".to_owned(),
                parameters: vec![1.0, 1.0],
                anisotropy: [[2.0, 0.5, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            }],
        };
        let geometry = Geometry {
            value_points: vec![[0.0, 0.0, 0.0]],
            gradient_points: vec![[1.0, 0.0, 0.0]],
        };
        let mut constants = Consts::new().unwrap();
        let rows = evaluate_action(
            &model,
            &geometry,
            &[1.0, 0.0, 0.0, 0.0],
            None,
            P,
            &mut constants,
        )
        .unwrap();
        // Gradient target rows are x,y,z. A shear couples x displacement
        // into the physical y derivative, so both x and y are nonzero.
        assert!(rows[1].prediction.upper_f64() < 0.0);
        assert!(rows[2].prediction.upper_f64() < 0.0);
    }

    #[test]
    fn th3_zero_radius_derivative_limit_is_exact_zero() {
        let model = PhysicalModel {
            nugget: 0.0,
            polynomial_degree: 1,
            components: vec![RbfComponent {
                family: "th3".to_owned(),
                parameters: vec![1.0, 0.0],
                anisotropy: identity(),
            }],
        };
        let geometry = Geometry {
            value_points: vec![[0.25, -0.5, 0.75]],
            gradient_points: vec![[0.25, -0.5, 0.75]],
        };
        let mut constants = Consts::new().unwrap();
        let rows = evaluate_action(
            &model,
            &geometry,
            &[1.0, 2.0, 3.0, 4.0],
            None,
            P,
            &mut constants,
        )
        .unwrap();
        assert!(rows.iter().all(|row| row.prediction.is_exact_zero()));
    }
}
