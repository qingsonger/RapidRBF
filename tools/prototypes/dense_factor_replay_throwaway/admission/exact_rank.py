"""Exact-dyadic spectral-ratio enclosures for rank-straddle checking.

The checker treats every finite binary64 input as its exact dyadic value.  It
forms the smaller exact Gram matrix without calling a numerical linear-algebra
backend, computes its characteristic polynomial over ``Fraction``, removes
repeated factors, and uses a Sturm chain to isolate the least and greatest
eigenvalues in dyadic intervals.  The returned binary64 endpoints are rounded
outward by exact comparisons, so they enclose ``sigma_min / sigma_max``.

This module is intentionally resource-bounded.  The normal admission path only
calls it after the inexpensive binary64 authority genuinely straddles the rank
threshold; callers must map ``ExactRankResourceDenied`` to their stable
fail-closed evidence state.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Any

import numpy as np

SUPPORTED_PRECISION_BITS = (256, 512, 1024, 2048)
AUTHORITY = "exact-dyadic-gram-sturm-outward-v1"
_ONE_BINARY64_BITS = 0x3FF0000000000000


class ExactRankError(RuntimeError):
    """Base class for exact-rank checker failures."""


class ExactRankInputError(ExactRankError):
    """The requested precision or binary64 subject is invalid."""


class ExactRankEvidenceError(ExactRankError):
    """An exact invariant unexpectedly failed to close."""


class ExactRankResourceDenied(ExactRankError):
    """The exact checker would exceed a declared resource limit."""

    def __init__(self, resource: str, required: int, limit: int):
        self.resource = resource
        self.required = required
        self.limit = limit
        super().__init__(f"{resource} requires {required}, exceeding limit {limit}")


@dataclass(frozen=True)
class ExactRankLimits:
    """Auditable logical limits applied before exact materialization."""

    max_min_dimension: int = 8
    max_matrix_elements: int = 100_000
    max_gram_term_products: int = 1_000_000
    max_bisection_iterations: int = 2048


@dataclass(frozen=True)
class ExactRatioEnvelope:
    """A binary64 outward enclosure and its exact-checker diagnostics."""

    lower: float
    upper: float
    authority: str
    precision_bits: int
    diagnostics: dict[str, Any]


Polynomial = tuple[Fraction, ...]
RationalMatrix = list[list[Fraction]]


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _matrix_binary64_digest(matrix: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(b"RapidRBF/exact-rank-binary64-matrix/v1\0")
    digest.update(struct.pack("<QQ", int(matrix.shape[0]), int(matrix.shape[1])))
    for value in matrix.flat:
        digest.update(struct.pack("<d", float(value)))
    return digest.hexdigest()


def _exact_sequence_digest(values: tuple[Fraction, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"RapidRBF/exact-rank-rational-sequence/v1\0")
    for value in values:
        for component in (value.numerator, value.denominator):
            payload = str(component).encode("ascii")
            digest.update(len(payload).to_bytes(8, "little"))
            digest.update(payload)
    return digest.hexdigest()


def _trim(polynomial: list[Fraction] | Polynomial) -> Polynomial:
    result = list(polynomial)
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    return tuple(result or [Fraction(0)])


def _is_zero_polynomial(polynomial: Polynomial) -> bool:
    return len(polynomial) == 1 and polynomial[0] == 0


def _derivative(polynomial: Polynomial) -> Polynomial:
    if len(polynomial) <= 1:
        return (Fraction(0),)
    return _trim(
        [Fraction(index) * coefficient for index, coefficient in enumerate(polynomial)][
            1:
        ]
    )


def _polynomial_divmod(
    dividend: Polynomial, divisor: Polynomial
) -> tuple[Polynomial, Polynomial]:
    if _is_zero_polynomial(divisor):
        raise ZeroDivisionError("polynomial division by zero")
    remainder = list(dividend)
    quotient = [Fraction(0)] * max(1, len(dividend) - len(divisor) + 1)
    divisor_degree = len(divisor) - 1
    divisor_lead = divisor[-1]
    while (
        not (len(remainder) == 1 and remainder[0] == 0)
        and len(remainder) - 1 >= divisor_degree
    ):
        shift = len(remainder) - len(divisor)
        factor = remainder[-1] / divisor_lead
        quotient[shift] += factor
        for index, coefficient in enumerate(divisor):
            remainder[index + shift] -= factor * coefficient
        remainder = list(_trim(remainder))
    return _trim(quotient), _trim(remainder)


def _monic(polynomial: Polynomial) -> Polynomial:
    if _is_zero_polynomial(polynomial):
        return polynomial
    leading = polynomial[-1]
    return tuple(value / leading for value in polynomial)


def _positive_scale_normalize(polynomial: Polynomial) -> Polynomial:
    if _is_zero_polynomial(polynomial):
        return polynomial
    magnitude = abs(polynomial[-1])
    return tuple(value / magnitude for value in polynomial)


def _polynomial_gcd(left: Polynomial, right: Polynomial) -> Polynomial:
    while not _is_zero_polynomial(right):
        _quotient, remainder = _polynomial_divmod(left, right)
        left, right = right, remainder
    return _monic(left)


def _square_free_part(polynomial: Polynomial) -> Polynomial:
    divisor = _polynomial_gcd(polynomial, _derivative(polynomial))
    quotient, remainder = _polynomial_divmod(polynomial, divisor)
    if not _is_zero_polynomial(remainder):
        raise ExactRankEvidenceError("square-free polynomial division was not exact")
    return _monic(quotient)


def _sturm_chain(polynomial: Polynomial) -> tuple[Polynomial, ...]:
    square_free = _square_free_part(polynomial)
    sequence = [
        _positive_scale_normalize(square_free),
        _positive_scale_normalize(_derivative(square_free)),
    ]
    if _is_zero_polynomial(sequence[-1]):
        return (sequence[0],)
    while True:
        _quotient, remainder = _polynomial_divmod(sequence[-2], sequence[-1])
        if _is_zero_polynomial(remainder):
            break
        negated = tuple(-value for value in remainder)
        sequence.append(_positive_scale_normalize(negated))
    return tuple(sequence)


def _evaluate(polynomial: Polynomial, argument: Fraction) -> Fraction:
    result = Fraction(0)
    for coefficient in reversed(polynomial):
        result = result * argument + coefficient
    return result


def _sign_variations(sequence: tuple[Polynomial, ...], argument: Fraction) -> int:
    signs: list[int] = []
    for polynomial in sequence:
        value = _evaluate(polynomial, argument)
        if value != 0:
            signs.append(1 if value > 0 else -1)
    return sum(left != right for left, right in pairwise(signs))


def _identity(size: int) -> RationalMatrix:
    return [
        [Fraction(int(row == column)) for column in range(size)] for row in range(size)
    ]


def _matrix_product(left: RationalMatrix, right: RationalMatrix) -> RationalMatrix:
    size = len(left)
    return [
        [
            sum(
                (left[row][inner] * right[inner][column] for inner in range(size)),
                Fraction(0),
            )
            for column in range(size)
        ]
        for row in range(size)
    ]


def _characteristic_polynomial(matrix: RationalMatrix) -> Polynomial:
    """Return ``det(x I - matrix)`` with coefficients in ascending order."""

    size = len(matrix)
    b_matrix = _identity(size)
    descending = [Fraction(1)]
    for order in range(1, size + 1):
        product = _matrix_product(matrix, b_matrix)
        coefficient = (
            -sum((product[index][index] for index in range(size)), Fraction(0)) / order
        )
        descending.append(coefficient)
        for index in range(size):
            product[index][index] += coefficient
        b_matrix = product
    return _trim(tuple(reversed(descending)))


def _exact_smaller_gram(matrix: np.ndarray) -> tuple[RationalMatrix, str]:
    rows, columns = (int(value) for value in matrix.shape)
    if rows >= columns:
        dimension = columns
        outer_dimension = rows
        orientation = "A_transpose_A"

        def vector_at(index: int) -> list[Fraction]:
            return [
                Fraction.from_float(float(matrix[index, component]))
                for component in range(dimension)
            ]

    else:
        dimension = rows
        outer_dimension = columns
        orientation = "A_A_transpose"

        def vector_at(index: int) -> list[Fraction]:
            return [
                Fraction.from_float(float(matrix[component, index]))
                for component in range(dimension)
            ]

    gram = [[Fraction(0) for _column in range(dimension)] for _row in range(dimension)]
    for outer_index in range(outer_dimension):
        vector = vector_at(outer_index)
        for row in range(dimension):
            for column in range(row, dimension):
                gram[row][column] += vector[row] * vector[column]
    for row in range(dimension):
        for column in range(row):
            gram[row][column] = gram[column][row]
    return gram, orientation


def _strict_dyadic_upper(value: Fraction) -> Fraction:
    if value <= 0:
        raise ExactRankEvidenceError("positive spectral upper bound required")
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    candidate = (
        Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)
    )
    while candidate <= value:
        candidate *= 2
    while candidate / 2 > value:
        candidate /= 2
    return candidate


def _gershgorin_upper(matrix: RationalMatrix) -> Fraction:
    return max(
        (sum((abs(value) for value in row), Fraction(0)) for row in matrix),
        default=Fraction(0),
    )


def _isolate_extreme(
    sturm: tuple[Polynomial, ...],
    upper: Fraction,
    total_distinct_roots: int,
    iterations: int,
    *,
    greatest: bool,
) -> tuple[Fraction, Fraction]:
    zero_variations = _sign_variations(sturm, Fraction(0))
    lower = Fraction(0)
    higher = upper
    target_count = total_distinct_roots if greatest else 1
    for _iteration in range(iterations):
        midpoint = (lower + higher) / 2
        roots_at_or_below = zero_variations - _sign_variations(sturm, midpoint)
        if roots_at_or_below >= target_count:
            higher = midpoint
        else:
            lower = midpoint
    return lower, higher


def _binary64_from_bits(bits: int) -> float:
    return struct.unpack(">d", bits.to_bytes(8, "big"))[0]


def _sqrt_binary64_outward(value: Fraction) -> tuple[float, float]:
    """Enclose an exact nonnegative rational square root in binary64."""

    if value < 0:
        raise ExactRankEvidenceError("cannot enclose a negative square root")
    if value == 0:
        return 0.0, 0.0
    if value >= 1:
        return 1.0, 1.0

    lower_bits = 0
    upper_bits = _ONE_BINARY64_BITS
    while lower_bits < upper_bits:
        midpoint_bits = (lower_bits + upper_bits + 1) // 2
        midpoint = _binary64_from_bits(midpoint_bits)
        midpoint_squared = Fraction.from_float(midpoint) ** 2
        if midpoint_squared <= value:
            lower_bits = midpoint_bits
        else:
            upper_bits = midpoint_bits - 1
    lower = _binary64_from_bits(lower_bits)
    lower_squared = Fraction.from_float(lower) ** 2
    if lower_squared == value:
        return lower, lower
    if lower_bits == _ONE_BINARY64_BITS:
        return lower, lower
    return lower, _binary64_from_bits(lower_bits + 1)


def _validate_resources(
    shape: tuple[int, int],
    precision_bits: int,
    limits: ExactRankLimits,
) -> tuple[int, int, int]:
    rows, columns = shape
    minimum_dimension = min(rows, columns)
    outer_dimension = max(rows, columns)
    matrix_elements = rows * columns
    gram_term_products = (
        outer_dimension * minimum_dimension * (minimum_dimension + 1) // 2
    )
    resources = (
        ("minimum_dimension", minimum_dimension, limits.max_min_dimension),
        ("matrix_elements", matrix_elements, limits.max_matrix_elements),
        (
            "gram_term_products",
            gram_term_products,
            limits.max_gram_term_products,
        ),
        (
            "bisection_iterations",
            precision_bits,
            limits.max_bisection_iterations,
        ),
    )
    for resource, required, limit in resources:
        if required > limit:
            raise ExactRankResourceDenied(resource, required, limit)
    return minimum_dimension, outer_dimension, gram_term_products


def exact_ratio_envelope(
    matrix: np.ndarray,
    precision_bits: int,
    *,
    limits: ExactRankLimits | None = None,
) -> ExactRatioEnvelope:
    """Return an exact-dyadic outward spectral-ratio enclosure.

    ``precision_bits`` is the number of exact dyadic bisections applied to each
    extreme Gram eigenvalue.  Thus each root interval has width exactly
    ``initial_dyadic_upper * 2**-precision_bits`` before its endpoints are
    propagated to the ratio.
    """

    if (
        type(precision_bits) is not int
        or precision_bits not in SUPPORTED_PRECISION_BITS
    ):
        raise ExactRankInputError(
            f"precision_bits must be one of {SUPPORTED_PRECISION_BITS}"
        )
    if not isinstance(matrix, np.ndarray):
        raise ExactRankInputError(
            "rank subject must be a NumPy array with a preflight-visible shape"
        )
    if matrix.ndim != 2 or min(matrix.shape, default=0) == 0:
        raise ExactRankInputError("rank subject must be a nonempty matrix")

    effective_limits = limits or ExactRankLimits()
    minimum_dimension, outer_dimension, gram_term_products = _validate_resources(
        (int(matrix.shape[0]), int(matrix.shape[1])),
        precision_bits,
        effective_limits,
    )
    subject = np.asarray(matrix, dtype=np.float64, order="C")
    if not all(math.isfinite(float(value)) for value in subject.flat):
        raise ExactRankInputError("rank subject contains NaN or infinity")
    input_digest = _matrix_binary64_digest(subject)
    gram, orientation = _exact_smaller_gram(subject)
    characteristic = _characteristic_polynomial(gram)
    polynomial_digest = _exact_sequence_digest(characteristic)
    base_diagnostics: dict[str, Any] = {
        "checker": AUTHORITY,
        "exact_input_model": "each finite binary64 value is its exact dyadic rational",
        "matrix_binary64_sha256": input_digest,
        "gram_orientation": orientation,
        "minimum_dimension": minimum_dimension,
        "outer_dimension": outer_dimension,
        "matrix_elements": int(subject.size),
        "gram_term_products": gram_term_products,
        "characteristic_polynomial_sha256": polynomial_digest,
        "characteristic_polynomial_coefficient_order": "ascending",
        "resource_limits": {
            "max_min_dimension": effective_limits.max_min_dimension,
            "max_matrix_elements": effective_limits.max_matrix_elements,
            "max_gram_term_products": effective_limits.max_gram_term_products,
            "max_bisection_iterations": effective_limits.max_bisection_iterations,
        },
        "backend_invocations": 0,
    }

    if characteristic[0] == 0:
        return ExactRatioEnvelope(
            lower=0.0,
            upper=0.0,
            authority=AUTHORITY,
            precision_bits=precision_bits,
            diagnostics={
                **base_diagnostics,
                "exact_full_min_dimension_rank": False,
                "decision": "exact Gram determinant is zero",
            },
        )

    sturm = _sturm_chain(characteristic)
    square_free_degree = len(_square_free_part(characteristic)) - 1
    gershgorin = _gershgorin_upper(gram)
    dyadic_upper = _strict_dyadic_upper(gershgorin)
    zero_variations = _sign_variations(sturm, Fraction(0))
    upper_variations = _sign_variations(sturm, dyadic_upper)
    distinct_roots = zero_variations - upper_variations
    if distinct_roots != square_free_degree or distinct_roots <= 0:
        raise ExactRankEvidenceError(
            "Sturm root inventory did not close over the positive Gram spectrum"
        )

    minimum_lower, minimum_upper = _isolate_extreme(
        sturm,
        dyadic_upper,
        distinct_roots,
        precision_bits,
        greatest=False,
    )
    maximum_lower, maximum_upper = _isolate_extreme(
        sturm,
        dyadic_upper,
        distinct_roots,
        precision_bits,
        greatest=True,
    )
    ratio_squared_lower = min(minimum_lower / maximum_upper, Fraction(1))
    ratio_squared_upper = (
        Fraction(1)
        if maximum_lower == 0
        else min(minimum_upper / maximum_lower, Fraction(1))
    )
    if ratio_squared_lower > ratio_squared_upper:
        raise ExactRankEvidenceError("propagated ratio interval is inverted")
    ratio_lower, _unused_lower_ceiling = _sqrt_binary64_outward(ratio_squared_lower)
    _unused_upper_floor, ratio_upper = _sqrt_binary64_outward(ratio_squared_upper)
    if not (0.0 <= ratio_lower <= ratio_upper <= 1.0):
        raise ExactRankEvidenceError("binary64 ratio enclosure is invalid")

    root_width = dyadic_upper / (1 << precision_bits)
    diagnostics = {
        **base_diagnostics,
        "exact_full_min_dimension_rank": True,
        "sturm_sequence_length": len(sturm),
        "distinct_positive_gram_eigenvalues": distinct_roots,
        "gershgorin_upper_bound": _fraction_text(gershgorin),
        "strict_initial_dyadic_upper": _fraction_text(dyadic_upper),
        "bisection_iterations_per_extreme": precision_bits,
        "root_interval_width": _fraction_text(root_width),
        "root_interval_width_relative_to_initial": f"2^-{precision_bits}",
        "lambda_min_interval": {
            "lower": _fraction_text(minimum_lower),
            "upper": _fraction_text(minimum_upper),
        },
        "lambda_max_interval": {
            "lower": _fraction_text(maximum_lower),
            "upper": _fraction_text(maximum_upper),
        },
        "ratio_squared_interval": {
            "lower": _fraction_text(ratio_squared_lower),
            "upper": _fraction_text(ratio_squared_upper),
        },
        "binary64_endpoint_rounding": (
            "exact monotone bit-pattern search; lower rounded toward zero and "
            "upper rounded toward positive infinity"
        ),
    }
    return ExactRatioEnvelope(
        lower=ratio_lower,
        upper=ratio_upper,
        authority=AUTHORITY,
        precision_bits=precision_bits,
        diagnostics=diagnostics,
    )
