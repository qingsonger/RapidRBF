from __future__ import annotations

import unittest
from fractions import Fraction
from unittest import mock

import numpy as np

import certify
import exact_rank


def _fraction_from_diagnostic(value: str) -> Fraction:
    numerator, denominator = value.split("/")
    return Fraction(int(numerator), int(denominator))


class ExactRankTests(unittest.TestCase):
    def test_midpoint_root_and_repeated_extremes_keep_closed_enclosures(
        self,
    ) -> None:
        # The exact Gram roots are 1 (twice) and 4 (twice).  Its strict initial
        # dyadic upper bound is 8, so the first greatest-root midpoint is
        # exactly 4; the least-root search later lands exactly on 1.  Sturm
        # variation at a root counts it at-or-below, making that midpoint the
        # closed upper endpoint.  Subsequent steps approach it from below.
        envelope = exact_rank.exact_ratio_envelope(
            np.diag([1.0, 1.0, 2.0, 2.0]),
            256,
        )
        diagnostics = envelope.diagnostics
        minimum = diagnostics["lambda_min_interval"]
        maximum = diagnostics["lambda_max_interval"]
        minimum_lower = _fraction_from_diagnostic(minimum["lower"])
        minimum_upper = _fraction_from_diagnostic(minimum["upper"])
        maximum_lower = _fraction_from_diagnostic(maximum["lower"])
        maximum_upper = _fraction_from_diagnostic(maximum["upper"])

        self.assertLess(minimum_lower, 1)
        self.assertEqual(minimum_upper, 1)
        self.assertLess(maximum_lower, 4)
        self.assertEqual(maximum_upper, 4)
        self.assertEqual(diagnostics["distinct_positive_gram_eigenvalues"], 2)
        self.assertLessEqual(envelope.lower, 0.5)
        self.assertGreaterEqual(envelope.upper, 0.5)

    def test_diagonal_exact_ratio_is_outward_and_nested_across_ladder(self) -> None:
        matrix = np.diag([1.0, 0.5, 2.0**-40])
        exact_ratio = Fraction(1, 2**40)
        previous_width: Fraction | None = None
        previous_lower = Fraction(0)
        previous_upper = Fraction(1)

        for bits in exact_rank.SUPPORTED_PRECISION_BITS:
            envelope = exact_rank.exact_ratio_envelope(matrix, bits)
            lower = Fraction.from_float(envelope.lower)
            upper = Fraction.from_float(envelope.upper)
            diagnostics = envelope.diagnostics
            width = _fraction_from_diagnostic(diagnostics["root_interval_width"])

            self.assertLessEqual(lower, exact_ratio)
            self.assertGreaterEqual(upper, exact_ratio)
            self.assertGreaterEqual(lower, previous_lower)
            self.assertLessEqual(upper, previous_upper)
            self.assertEqual(
                diagnostics["root_interval_width_relative_to_initial"],
                f"2^-{bits}",
            )
            if previous_width is not None:
                self.assertLess(width, previous_width)
            previous_width = width
            previous_lower = lower
            previous_upper = upper

        self.assertEqual(
            envelope.lower,
            float(np.nextafter(float(exact_ratio), -np.inf)),
        )
        self.assertLessEqual(
            envelope.upper,
            float(np.nextafter(float(exact_ratio), np.inf)),
        )
        self.assertEqual(envelope.authority, exact_rank.AUTHORITY)
        self.assertEqual(envelope.diagnostics["backend_invocations"], 0)

    def test_genuine_near_tau_checker_classifies_both_sides(self) -> None:
        tau = Fraction(1, 2**52)

        deficient_epsilon = Fraction(1, 2**50)
        deficient = np.array(
            [
                [1.0, 1.0],
                [1.0, float(Fraction(1) + deficient_epsilon)],
            ]
        )
        deficient_envelope = exact_rank.exact_ratio_envelope(deficient, 256)
        self.assertLessEqual(Fraction.from_float(deficient_envelope.upper), tau)
        self.assertTrue(self._exact_symmetric_ratio_at_most_tau(deficient_epsilon, tau))

        admitted_epsilon = Fraction(1, 2**49)
        admitted = np.array(
            [
                [1.0, 1.0],
                [1.0, float(Fraction(1) + admitted_epsilon)],
            ]
        )
        admitted_envelope = exact_rank.exact_ratio_envelope(admitted, 256)
        self.assertGreater(Fraction.from_float(admitted_envelope.lower), tau)
        self.assertFalse(self._exact_symmetric_ratio_at_most_tau(admitted_epsilon, tau))

    def test_real_power2_equilibrated_analytic_straddle_closes_exactly(self) -> None:
        # This is a genuine analytic straddle, not an injected RatioEnvelope.
        # One-pass power-of-two equilibration halves the second row.
        matrix = np.array(
            [
                [1.0, 1.0],
                [1.0, float.fromhex("0x1.0000000000006p+0")],
            ]
        )
        equilibrated, row_exponents, column_exponents = certify.equilibrate_power2(
            matrix
        )
        tau = certify.tau_rank(equilibrated.shape)
        analytic = certify.analytic_ratio_envelope(
            equilibrated,
            decision_tau=tau,
        )
        exact = exact_rank.exact_ratio_envelope(equilibrated, 256)

        self.assertEqual(row_exponents, [0, -1])
        self.assertEqual(column_exponents, [0, 0])
        self.assertEqual(certify.classify_ratio(analytic, tau), "straddle")
        self.assertEqual(analytic.lower, 0.0)
        self.assertGreater(analytic.upper, tau)
        self.assertGreater(exact.lower, tau)
        self.assertEqual(
            exact.lower.hex(),
            "0x1.3333333333331p-52",
        )
        self.assertEqual(
            exact.upper.hex(),
            "0x1.3333333333332p-52",
        )

    def test_exact_singular_gram_returns_zero_without_backend(self) -> None:
        envelope = exact_rank.exact_ratio_envelope(
            np.array([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]]),
            256,
        )
        self.assertEqual((envelope.lower, envelope.upper), (0.0, 0.0))
        self.assertFalse(envelope.diagnostics["exact_full_min_dimension_rank"])
        self.assertEqual(envelope.diagnostics["backend_invocations"], 0)

    def test_resource_denial_is_distinct_and_precedes_exact_materialization(
        self,
    ) -> None:
        limits = exact_rank.ExactRankLimits(max_min_dimension=2)
        with (
            mock.patch.object(
                exact_rank.np,
                "asarray",
                side_effect=AssertionError(
                    "binary64 copy occurred before exact-resource denial"
                ),
            ),
            self.assertRaises(exact_rank.ExactRankResourceDenied) as caught,
        ):
            exact_rank.exact_ratio_envelope(np.eye(3), 256, limits=limits)
        self.assertEqual(caught.exception.resource, "minimum_dimension")
        self.assertEqual(caught.exception.required, 3)
        self.assertEqual(caught.exception.limit, 2)

    def test_precision_request_is_normative(self) -> None:
        for invalid in (128, 256.0, True):
            with (
                self.subTest(invalid=invalid),
                self.assertRaises(exact_rank.ExactRankInputError),
            ):
                exact_rank.exact_ratio_envelope(np.eye(2), invalid)

    def test_non_array_subject_is_rejected_before_materialization(self) -> None:
        with self.assertRaises(exact_rank.ExactRankInputError):
            exact_rank.exact_ratio_envelope([[1.0]], 256)

    @staticmethod
    def _exact_symmetric_ratio_at_most_tau(epsilon: Fraction, tau: Fraction) -> bool:
        # For the positive-definite symmetric matrix in the test, the singular
        # ratio r obeys det / trace^2 = r / (1+r)^2.  The right-hand function is
        # increasing for 0 <= r <= 1, so this is an exact rational comparison.
        determinant_over_trace_squared = epsilon / (2 + epsilon) ** 2
        tau_transform = tau / (1 + tau) ** 2
        return determinant_over_trace_squared <= tau_transform


if __name__ == "__main__":
    unittest.main()
