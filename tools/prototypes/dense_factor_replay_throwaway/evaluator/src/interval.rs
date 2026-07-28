use std::cmp::Ordering;

use astro_float_num::{BigFloat, Consts, RoundingMode};

/// Closed outward-rounded arbitrary-precision interval.
///
/// `astro-float-num` is a pure-Rust multiprecision implementation.  All
/// arithmetic is performed twice, toward negative and positive infinity.
/// Binary64 inputs are exact at every supported precision (>= 64 bits).
#[derive(Clone, Debug)]
pub struct Interval {
    lo: BigFloat,
    hi: BigFloat,
    precision: usize,
}

impl Interval {
    pub fn exact(value: f64, precision: usize) -> Result<Self, String> {
        if !value.is_finite() {
            return Err("nonfinite binary64 input".to_owned());
        }
        if precision < 64 {
            return Err("interval precision must be at least 64 bits".to_owned());
        }
        let exact = BigFloat::from_f64(value, precision);
        ensure_finite(&exact, "binary64 conversion")?;
        Ok(Self {
            lo: exact.clone(),
            hi: exact,
            precision,
        })
    }

    pub fn zero(precision: usize) -> Self {
        Self {
            lo: BigFloat::new(precision),
            hi: BigFloat::new(precision),
            precision,
        }
    }

    pub fn one(precision: usize) -> Self {
        let one = BigFloat::from_u8(1, precision);
        Self {
            lo: one.clone(),
            hi: one,
            precision,
        }
    }

    pub fn precision(&self) -> usize {
        self.precision
    }

    pub fn lower(&self) -> &BigFloat {
        &self.lo
    }

    pub fn upper(&self) -> &BigFloat {
        &self.hi
    }

    /// Decimal diagnostic conversion.  Admission decisions never use this.
    pub fn lower_f64(&self) -> f64 {
        self.lo.to_string().parse().unwrap_or(f64::NEG_INFINITY)
    }

    /// Decimal diagnostic conversion.  Admission decisions never use this.
    pub fn upper_f64(&self) -> f64 {
        self.hi.to_string().parse().unwrap_or(f64::INFINITY)
    }

    pub fn lower_decimal(&self) -> String {
        self.lo.to_string()
    }

    pub fn upper_decimal(&self) -> String {
        self.hi.to_string()
    }

    pub fn contains_zero(&self) -> bool {
        self.lo.cmp(&BigFloat::new(self.precision)).unwrap_or(0) <= 0
            && self.hi.cmp(&BigFloat::new(self.precision)).unwrap_or(0) >= 0
    }

    pub fn is_exact_zero(&self) -> bool {
        self.lo.is_zero() && self.hi.is_zero()
    }

    pub fn is_nonnegative(&self) -> bool {
        !self.lo.is_negative()
    }

    pub fn add(&self, rhs: &Self) -> Self {
        self.assert_same_precision(rhs);
        Self {
            lo: self.lo.add(&rhs.lo, self.precision, RoundingMode::Down),
            hi: self.hi.add(&rhs.hi, self.precision, RoundingMode::Up),
            precision: self.precision,
        }
    }

    pub fn sub(&self, rhs: &Self) -> Self {
        self.assert_same_precision(rhs);
        Self {
            lo: self.lo.sub(&rhs.hi, self.precision, RoundingMode::Down),
            hi: self.hi.sub(&rhs.lo, self.precision, RoundingMode::Up),
            precision: self.precision,
        }
    }

    pub fn neg(&self) -> Self {
        Self {
            lo: self.hi.neg(),
            hi: self.lo.neg(),
            precision: self.precision,
        }
    }

    pub fn mul(&self, rhs: &Self) -> Self {
        self.assert_same_precision(rhs);
        let zero = BigFloat::new(self.precision);
        let self_nonnegative = cmp(&self.lo, &zero) != Ordering::Less;
        let self_nonpositive = cmp(&self.hi, &zero) != Ordering::Greater;
        let rhs_nonnegative = cmp(&rhs.lo, &zero) != Ordering::Less;
        let rhs_nonpositive = cmp(&rhs.hi, &zero) != Ordering::Greater;
        let product =
            |left: &BigFloat, right: &BigFloat, rounding| left.mul(right, self.precision, rounding);
        let (lo, hi) = if self_nonnegative && rhs_nonnegative {
            (
                product(&self.lo, &rhs.lo, RoundingMode::Down),
                product(&self.hi, &rhs.hi, RoundingMode::Up),
            )
        } else if self_nonnegative && rhs_nonpositive {
            (
                product(&self.hi, &rhs.lo, RoundingMode::Down),
                product(&self.lo, &rhs.hi, RoundingMode::Up),
            )
        } else if self_nonpositive && rhs_nonnegative {
            (
                product(&self.lo, &rhs.hi, RoundingMode::Down),
                product(&self.hi, &rhs.lo, RoundingMode::Up),
            )
        } else if self_nonpositive && rhs_nonpositive {
            (
                product(&self.hi, &rhs.hi, RoundingMode::Down),
                product(&self.lo, &rhs.lo, RoundingMode::Up),
            )
        } else if rhs_nonnegative {
            (
                product(&self.lo, &rhs.hi, RoundingMode::Down),
                product(&self.hi, &rhs.hi, RoundingMode::Up),
            )
        } else if rhs_nonpositive {
            (
                product(&self.hi, &rhs.lo, RoundingMode::Down),
                product(&self.lo, &rhs.lo, RoundingMode::Up),
            )
        } else if self_nonnegative {
            (
                product(&self.hi, &rhs.lo, RoundingMode::Down),
                product(&self.hi, &rhs.hi, RoundingMode::Up),
            )
        } else if self_nonpositive {
            (
                product(&self.lo, &rhs.hi, RoundingMode::Down),
                product(&self.lo, &rhs.lo, RoundingMode::Up),
            )
        } else {
            (
                min_float([
                    product(&self.lo, &rhs.hi, RoundingMode::Down),
                    product(&self.hi, &rhs.lo, RoundingMode::Down),
                ]),
                max_float([
                    product(&self.lo, &rhs.lo, RoundingMode::Up),
                    product(&self.hi, &rhs.hi, RoundingMode::Up),
                ]),
            )
        };
        Self {
            lo,
            hi,
            precision: self.precision,
        }
    }

    pub fn square(&self) -> Self {
        if self.contains_zero() {
            let max_abs = if self.lo.abs_cmp(&self.hi).unwrap_or(0) >= 0 {
                self.lo.abs()
            } else {
                self.hi.abs()
            };
            Self {
                lo: BigFloat::new(self.precision),
                hi: max_abs.mul(&max_abs, self.precision, RoundingMode::Up),
                precision: self.precision,
            }
        } else {
            self.mul(self)
        }
    }

    pub fn div(&self, rhs: &Self) -> Result<Self, String> {
        if rhs.contains_zero() {
            return Err("interval division by an interval containing zero".to_owned());
        }
        self.assert_same_precision(rhs);
        let one = BigFloat::from_u8(1, self.precision);
        let reciprocal = Self {
            lo: one.div(&rhs.hi, self.precision, RoundingMode::Down),
            hi: one.div(&rhs.lo, self.precision, RoundingMode::Up),
            precision: self.precision,
        };
        Ok(self.mul(&reciprocal))
    }

    pub fn sqrt(&self) -> Result<Self, String> {
        if self.lo.is_negative() {
            return Err("sqrt of interval with negative lower endpoint".to_owned());
        }
        let lo = self.lo.sqrt(self.precision, RoundingMode::Down);
        let hi = self.hi.sqrt(self.precision, RoundingMode::Up);
        ensure_finite(&lo, "directed sqrt lower endpoint")?;
        ensure_finite(&hi, "directed sqrt upper endpoint")?;
        Ok(Self {
            lo,
            hi,
            precision: self.precision,
        })
    }

    pub fn exp(&self, constants: &mut Consts) -> Result<Self, String> {
        let lo = self.lo.exp(self.precision, RoundingMode::Down, constants);
        let hi = self.hi.exp(self.precision, RoundingMode::Up, constants);
        ensure_finite(&lo, "directed exp lower endpoint")?;
        ensure_finite(&hi, "directed exp upper endpoint")?;
        Ok(Self {
            lo,
            hi,
            precision: self.precision,
        })
    }

    pub fn abs_upper(&self) -> BigFloat {
        if self.lo.abs_cmp(&self.hi).unwrap_or(0) >= 0 {
            self.lo.abs()
        } else {
            self.hi.abs()
        }
    }

    pub fn abs_upper_f64(&self) -> f64 {
        self.abs_upper()
            .to_string()
            .parse()
            .unwrap_or(f64::INFINITY)
    }

    pub fn hull(values: &[Self]) -> Result<Self, String> {
        let first = values
            .first()
            .ok_or_else(|| "cannot form an interval hull of zero values".to_owned())?;
        let mut lo = first.lo.clone();
        let mut hi = first.hi.clone();
        for value in &values[1..] {
            first.assert_same_precision(value);
            if cmp(&value.lo, &lo) == Ordering::Less {
                lo = value.lo.clone();
            }
            if cmp(&value.hi, &hi) == Ordering::Greater {
                hi = value.hi.clone();
            }
        }
        Ok(Self {
            lo,
            hi,
            precision: first.precision,
        })
    }

    fn assert_same_precision(&self, rhs: &Self) {
        debug_assert_eq!(self.precision, rhs.precision);
    }
}

fn min_float<const N: usize>(values: [BigFloat; N]) -> BigFloat {
    values
        .into_iter()
        .min_by(cmp)
        .expect("four multiplication endpoints")
}

fn max_float<const N: usize>(values: [BigFloat; N]) -> BigFloat {
    values
        .into_iter()
        .max_by(cmp)
        .expect("four multiplication endpoints")
}

fn cmp(left: &BigFloat, right: &BigFloat) -> Ordering {
    match left.cmp(right).unwrap_or(0) {
        value if value < 0 => Ordering::Less,
        value if value > 0 => Ordering::Greater,
        _ => Ordering::Equal,
    }
}

fn ensure_finite(value: &BigFloat, context: &str) -> Result<(), String> {
    if value.is_nan() || value.is_inf() {
        Err(format!("{context} produced a nonfinite value"))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use astro_float_num::{BigFloat, Consts};

    use super::Interval;

    const P: usize = 256;

    #[test]
    fn binary64_is_exact_and_basic_operations_enclose() {
        let a = Interval::exact(0.1, P).unwrap();
        let b = Interval::exact(0.2, P).unwrap();
        let c = a.add(&b);
        let exact_sum = BigFloat::from_f64(0.1, P).add_full_prec(&BigFloat::from_f64(0.2, P));
        assert!(c.lower().cmp(&exact_sum).unwrap() <= 0);
        assert!(c.upper().cmp(&exact_sum).unwrap() >= 0);

        let product = c.mul(&Interval::exact(-3.0, P).unwrap());
        let exact_product = exact_sum.mul_full_prec(&BigFloat::from_f64(-3.0, P));
        assert!(product.lower().cmp(&exact_product).unwrap() <= 0);
        assert!(product.upper().cmp(&exact_product).unwrap() >= 0);
    }

    #[test]
    fn transcendental_operations_enclose_binary64_reference() {
        let two = Interval::exact(2.0, P).unwrap();
        let root = two.sqrt().unwrap();
        let binary64_root = 2.0_f64.sqrt();
        assert!(
            root.lower()
                .cmp(&BigFloat::from_f64(next_up(binary64_root), P))
                .unwrap()
                <= 0
        );
        assert!(
            root.upper()
                .cmp(&BigFloat::from_f64(next_down(binary64_root), P))
                .unwrap()
                >= 0
        );

        let mut constants = Consts::new().unwrap();
        let x = Interval::exact(-3.0, P).unwrap();
        let exponential = x.exp(&mut constants).unwrap();
        let binary64_exp = (-3.0_f64).exp();
        assert!(
            exponential
                .lower()
                .cmp(&BigFloat::from_f64(next_up(binary64_exp), P))
                .unwrap()
                <= 0
        );
        assert!(
            exponential
                .upper()
                .cmp(&BigFloat::from_f64(next_down(binary64_exp), P))
                .unwrap()
                >= 0
        );
    }

    #[test]
    fn sign_specialized_multiplication_encloses_all_endpoint_products() {
        let endpoints = [-3.0, -1.0, 0.0, 2.0, 5.0];
        for left_lo_index in 0..endpoints.len() {
            for left_hi_index in left_lo_index..endpoints.len() {
                for right_lo_index in 0..endpoints.len() {
                    for right_hi_index in right_lo_index..endpoints.len() {
                        let left = Interval {
                            lo: BigFloat::from_f64(endpoints[left_lo_index], P),
                            hi: BigFloat::from_f64(endpoints[left_hi_index], P),
                            precision: P,
                        };
                        let right = Interval {
                            lo: BigFloat::from_f64(endpoints[right_lo_index], P),
                            hi: BigFloat::from_f64(endpoints[right_hi_index], P),
                            precision: P,
                        };
                        let product = left.mul(&right);
                        for lhs in [endpoints[left_lo_index], endpoints[left_hi_index]] {
                            for rhs in [endpoints[right_lo_index], endpoints[right_hi_index]] {
                                let exact = BigFloat::from_f64(lhs, P)
                                    .mul_full_prec(&BigFloat::from_f64(rhs, P));
                                assert!(product.lower().cmp(&exact).unwrap() <= 0);
                                assert!(product.upper().cmp(&exact).unwrap() >= 0);
                            }
                        }
                    }
                }
            }
        }
    }

    fn next_up(value: f64) -> f64 {
        f64::from_bits(value.to_bits() + 1)
    }

    fn next_down(value: f64) -> f64 {
        f64::from_bits(value.to_bits() - 1)
    }
}
