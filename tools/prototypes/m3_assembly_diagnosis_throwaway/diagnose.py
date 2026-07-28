#!/usr/bin/env python3
"""Independent high-precision adjudication of the issue-35 M3 row-map signal."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from array import array
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA = "rapidrbf-m3-assembly-diagnosis-v1"
CORPUS_SHA256 = "ac282ee95062b4463d2e0a0c0ca83da454660e0e5048fa79ea3a07da280ef26e"
POLATORY_COMMIT = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"
PANEL = "M3-HERMITE-COMPOSITE"
ROLES = ("max-order-fine", "level0-coarse")
VARIANTS = ("canonical", "frozen-literal")
CPD_LIMIT = Decimal(2) ** Decimal(-32)
SHARED_PAYLOADS = (
    "a_lower",
    "p_row_major",
    "rhs_full",
    "domain_value_indices",
    "domain_gradient_indices",
    "polynomial_p_top",
)
EXPECTED_DIVERGENT_PAYLOADS = (
    "lagrange_flat_indices",
    "q_top_row_major",
    "b_lower",
    "rhs_reduced",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the locked M3 corpus, audit the frozen Polatory row-map "
            "source, and independently recompute the structural and augmented "
            "residual evidence at high precision."
        )
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="locked v2 corpus directory containing manifest.raw.json",
    )
    parser.add_argument(
        "--polatory-source",
        type=Path,
        required=True,
        help=f"clean Polatory checkout at {POLATORY_COMMIT}",
    )
    parser.add_argument("--precision", type=int, default=80)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def referenced_payloads(manifest: dict[str, Any]) -> set[str]:
    referenced: set[str] = set()
    for index, record in enumerate(manifest.get("records", [])):
        files = record.get("files")
        if not isinstance(files, dict) or not files:
            raise RuntimeError(
                f"manifest record {record.get('record_id', index)!r} has no files"
            )
        for logical_name, relative in files.items():
            if not isinstance(logical_name, str) or not isinstance(relative, str):
                raise RuntimeError(
                    f"manifest record {record.get('record_id', index)!r} "
                    "contains a non-string file entry"
                )
            candidate = Path(relative)
            if (
                candidate.is_absolute()
                or ".." in candidate.parts
                or candidate.as_posix() != relative
            ):
                raise RuntimeError(f"unsafe manifest payload path: {relative!r}")
            referenced.add(relative)
    return referenced


def verify_locked_corpus(
    root: Path, manifest: dict[str, Any], lock: dict[str, Any]
) -> dict[str, Any]:
    if lock.get("schema") != "rapidrbf-dense-factor-corpus-lock-v2":
        raise RuntimeError(f"unsupported corpus lock schema: {lock.get('schema')}")
    recorded_digest = lock.get("corpus_sha256", "").lower()
    lock_body = {key: value for key, value in lock.items() if key != "corpus_sha256"}
    recomputed_digest = canonical_sha256(lock_body)
    if recorded_digest != CORPUS_SHA256 or recomputed_digest != CORPUS_SHA256:
        raise RuntimeError(
            "corpus lock identity mismatch: "
            f"recorded={recorded_digest}, recomputed={recomputed_digest}, "
            f"expected={CORPUS_SHA256}"
        )

    referenced = referenced_payloads(manifest)
    expected_files = {"manifest.raw.json", *referenced}
    if lock.get("capture_schema") != manifest.get("schema"):
        raise RuntimeError("corpus lock capture schema does not match its manifest")
    if lock.get("record_count") != len(manifest.get("records", [])):
        raise RuntimeError("corpus lock record count does not match its manifest")
    if lock.get("referenced_payload_count") != len(referenced):
        raise RuntimeError("corpus lock payload count does not match its manifest")
    entries = lock.get("files")
    if not isinstance(entries, dict):
        raise RuntimeError("corpus lock has no file table")
    if set(entries) != expected_files:
        raise RuntimeError("corpus lock file table does not exactly cover its manifest")

    actual_files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"locked corpus contains a symlink: {path}")
        if path.is_file():
            actual_files.add(path.relative_to(root).as_posix())
    expected_actual_files = {*expected_files, "manifest.lock.json"}
    if actual_files != expected_actual_files:
        missing = sorted(expected_actual_files - actual_files)
        extra = sorted(actual_files - expected_actual_files)
        raise RuntimeError(
            f"locked corpus closure mismatch: missing={missing}, extra={extra}"
        )

    total_bytes = 0
    for relative, expected in sorted(entries.items()):
        path = root / relative
        stat = path.stat()
        if stat.st_size != expected["bytes"]:
            raise RuntimeError(
                f"locked size mismatch for {relative}: "
                f"{stat.st_size} != {expected['bytes']}"
            )
        actual_sha = sha256_file(path)
        if actual_sha != expected["sha256"]:
            raise RuntimeError(
                f"locked SHA-256 mismatch for {relative}: "
                f"{actual_sha} != {expected['sha256']}"
            )
        total_bytes += stat.st_size

    return {
        "schema": lock["schema"],
        "corpus_sha256": recorded_digest,
        "lock_body_sha256_recomputed": recomputed_digest,
        "verified_file_count": len(entries),
        "verified_bytes": total_bytes,
        "record_count": lock["record_count"],
        "referenced_payload_count": lock["referenced_payload_count"],
        "exact_manifest_coverage": True,
        "exact_directory_closure": True,
        "symlinks_rejected": True,
        "all_locked_files_verified": True,
    }


def load_array(path: Path, typecode: str) -> array:
    values = array(typecode)
    values.frombytes(path.read_bytes())
    if sys.byteorder != "little":
        values.byteswap()
    return values


def require_length(values: Sequence[Any], expected: int, label: str) -> None:
    if len(values) != expected:
        raise RuntimeError(f"{label} has {len(values)} elements; expected {expected}")


def decimal_string(value: Decimal) -> str:
    return format(value, ".24E")


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("Infinity") if numerator != 0 else Decimal(0)
    return numerator / denominator


def lower_value(packed: Sequence[float], row: int, column: int) -> float:
    if column > row:
        row, column = column, row
    return packed[row * (row + 1) // 2 + column]


def matrix_inf_norm_decimal(
    packed_lower: Sequence[float], order: int, precision: int
) -> Decimal:
    with localcontext() as context:
        context.prec = precision
        maximum = Decimal(0)
        for row in range(order):
            row_sum = sum(
                (
                    abs(Decimal.from_float(lower_value(packed_lower, row, column)))
                    for column in range(order)
                ),
                Decimal(0),
            )
            maximum = max(maximum, row_sum)
        return +maximum


def rectangular_inf_norm_decimal(
    values: Sequence[float], rows: int, columns: int, precision: int
) -> Decimal:
    with localcontext() as context:
        context.prec = precision
        return +max(
            (
                sum(
                    (
                        abs(Decimal.from_float(values[row * columns + column]))
                        for column in range(columns)
                    ),
                    Decimal(0),
                )
                for row in range(rows)
            ),
            default=Decimal(0),
        )


def transpose(matrix: Sequence[Sequence[Decimal]]) -> list[list[Decimal]]:
    return [list(column) for column in zip(*matrix, strict=True)]


def decimal_inverse_and_determinant(
    matrix: Sequence[Sequence[Decimal]], precision: int
) -> tuple[list[list[Decimal]], Decimal]:
    order = len(matrix)
    with localcontext() as context:
        context.prec = precision
        work = [[+value for value in row] for row in matrix]
        inverse = [
            [Decimal(1) if row == column else Decimal(0) for column in range(order)]
            for row in range(order)
        ]
        determinant = Decimal(1)
        sign = 1
        for column in range(order):
            pivot = max(range(column, order), key=lambda row: abs(work[row][column]))
            if work[pivot][column] == 0:
                raise RuntimeError("P_top is exactly singular in the decimal oracle")
            if pivot != column:
                work[column], work[pivot] = work[pivot], work[column]
                inverse[column], inverse[pivot] = inverse[pivot], inverse[column]
                sign *= -1
            pivot_value = work[column][column]
            determinant *= pivot_value
            work[column] = [value / pivot_value for value in work[column]]
            inverse[column] = [value / pivot_value for value in inverse[column]]
            for row in range(order):
                if row == column:
                    continue
                multiplier = work[row][column]
                if multiplier == 0:
                    continue
                work[row] = [
                    value - multiplier * pivot_entry
                    for value, pivot_entry in zip(
                        work[row], work[column], strict=True
                    )
                ]
                inverse[row] = [
                    value - multiplier * pivot_entry
                    for value, pivot_entry in zip(
                        inverse[row], inverse[column], strict=True
                    )
                ]
        return inverse, +(determinant if sign > 0 else -determinant)


def jacobi_eigenvalues_symmetric(matrix: Sequence[Sequence[float]]) -> list[float]:
    work = [list(row) for row in matrix]
    order = len(work)
    for _ in range(100):
        row, column = max(
            (
                (row, column)
                for row in range(order)
                for column in range(row + 1, order)
            ),
            key=lambda pair: abs(work[pair[0]][pair[1]]),
        )
        off_diagonal = work[row][column]
        if abs(off_diagonal) <= 1.0e-30:
            break
        tau = (work[column][column] - work[row][row]) / (2.0 * off_diagonal)
        tangent = math.copysign(
            1.0 / (abs(tau) + math.sqrt(1.0 + tau * tau)), tau
        )
        cosine = 1.0 / math.sqrt(1.0 + tangent * tangent)
        sine = tangent * cosine
        diagonal_row = work[row][row]
        diagonal_column = work[column][column]
        work[row][row] = (
            cosine * cosine * diagonal_row
            - 2.0 * sine * cosine * off_diagonal
            + sine * sine * diagonal_column
        )
        work[column][column] = (
            sine * sine * diagonal_row
            + 2.0 * sine * cosine * off_diagonal
            + cosine * cosine * diagonal_column
        )
        work[row][column] = work[column][row] = 0.0
        for other in range(order):
            if other in (row, column):
                continue
            old_row = work[other][row]
            old_column = work[other][column]
            work[other][row] = work[row][other] = (
                cosine * old_row - sine * old_column
            )
            work[other][column] = work[column][other] = (
                sine * old_row + cosine * old_column
            )
    return sorted(work[index][index] for index in range(order))


def p_top_rank_diagnostic(
    p_full: Sequence[float], scalar_order: int, polynomial_order: int, precision: int
) -> tuple[dict[str, Any], list[list[Decimal]]]:
    p_top_decimal = [
        [
            Decimal.from_float(p_full[row * polynomial_order + column])
            for column in range(polynomial_order)
        ]
        for row in range(polynomial_order)
    ]
    inverse_transpose, determinant_transpose = decimal_inverse_and_determinant(
        transpose(p_top_decimal), precision
    )
    p_top_float = [
        [
            p_full[row * polynomial_order + column]
            for column in range(polynomial_order)
        ]
        for row in range(polynomial_order)
    ]
    gram = [
        [
            math.fsum(
                p_top_float[row][left] * p_top_float[row][right]
                for row in range(polynomial_order)
            )
            for right in range(polynomial_order)
        ]
        for left in range(polynomial_order)
    ]
    eigenvalues = jacobi_eigenvalues_symmetric(gram)
    singular_values = [math.sqrt(max(value, 0.0)) for value in eigenvalues]
    singular_ratio = singular_values[0] / singular_values[-1]
    tau_rank = polynomial_order * 2.0**-53
    conservative_parent_order_tau = max(scalar_order, polynomial_order) * 2.0**-53
    return (
        {
            "matrix": "local P_top",
            "order": polynomial_order,
            "decimal_precision": precision,
            "determinant_from_binary64_values": decimal_string(
                determinant_transpose
            ),
            "diagnostic_singular_values": singular_values,
            "diagnostic_sigma_min_over_sigma_max": singular_ratio,
            "tau_rank": tau_rank,
            "distance_above_tau_factor": singular_ratio / tau_rank,
            "conservative_parent_order_tau": conservative_parent_order_tau,
            "distance_above_conservative_parent_order_tau_factor": (
                singular_ratio / conservative_parent_order_tau
            ),
            "rank_boundary_disposition": (
                "far above both the 4x4 tau_rank and the more conservative parent "
                "scalar-order diagnostic; not a formal production "
                "scaled/equilibrated rank certificate"
            ),
        },
        inverse_transpose,
    )


def payload_sha(
    lock: dict[str, Any], record: dict[str, Any], payload_name: str
) -> str:
    relative = record["files"][payload_name]
    return lock["files"][relative]["sha256"]


def compare_payload_identity(
    lock: dict[str, Any],
    canonical: dict[str, Any],
    literal: dict[str, Any],
) -> dict[str, Any]:
    shared = {
        name: payload_sha(lock, canonical, name) == payload_sha(lock, literal, name)
        for name in SHARED_PAYLOADS
    }
    divergent = {
        name: payload_sha(lock, canonical, name) != payload_sha(lock, literal, name)
        for name in EXPECTED_DIVERGENT_PAYLOADS
    }
    return {
        "shared_payloads": shared,
        "expected_divergent_payloads": divergent,
        "shared_inputs_all_byte_equal": all(shared.values()),
        "assembly_outputs_all_byte_different": all(divergent.values()),
    }


def row_map_audit(
    root: Path, record: dict[str, Any], variant: str
) -> dict[str, Any]:
    scalar_order = record["scalar_order"]
    local_value_rows = record["value_rows"]
    source_value_rows = record["source_value_rows"]
    gradient_rows = record["gradient_rows"]
    flat = load_array(root / record["files"]["lagrange_flat_indices"], "q")
    point_indices = load_array(root / record["files"]["domain_value_indices"], "q")
    gradient_indices = load_array(
        root / record["files"]["domain_gradient_indices"], "q"
    )
    require_length(flat, scalar_order, f"{variant} flat row map")
    require_length(point_indices, local_value_rows, f"{variant} value indices")
    require_length(gradient_indices, gradient_rows, f"{variant} gradient indices")

    expected_global = list(point_indices)
    expected_local = list(point_indices)
    for index in gradient_indices:
        for component in range(3):
            expected_global.append(source_value_rows + 3 * index + component)
            expected_local.append(local_value_rows + 3 * index + component)

    actual = list(flat)
    actual_tail = actual[local_value_rows:]
    expected_global_tail = expected_global[local_value_rows:]
    deltas = [
        actual_value - expected_value
        for actual_value, expected_value in zip(
            actual_tail, expected_global_tail, strict=True
        )
    ]
    expected_offset = source_value_rows if variant == "canonical" else local_value_rows
    return {
        "variant": record["assembly_variant"],
        "source_value_rows": source_value_rows,
        "local_value_rows": local_value_rows,
        "gradient_rows": gradient_rows,
        "gradient_scalar_rows": 3 * gradient_rows,
        "expected_offset_for_variant": expected_offset,
        "matches_global_row_map": actual == expected_global,
        "matches_frozen_local_row_map": actual == expected_local,
        "gradient_rows_mismatching_global_map": sum(delta != 0 for delta in deltas),
        "unique_gradient_index_deltas_from_global": sorted(set(deltas)),
        "literal_selected_rows_still_inside_value_block": sum(
            index < source_value_rows for index in actual_tail
        ),
        "literal_selected_rows_inside_gradient_block": sum(
            index >= source_value_rows for index in actual_tail
        ),
    }


def vector_inf_norm_decimal(values: Iterable[Decimal]) -> Decimal:
    return max((abs(value) for value in values), default=Decimal(0))


def analyze_variant(
    root: Path,
    record: dict[str, Any],
    p_full: Sequence[float],
    a_lower: Sequence[float],
    rhs_full: Sequence[float],
    p_transpose_inf: Decimal,
    a_inf: Decimal,
    p_inf: Decimal,
    inverse_p_top_transpose: Sequence[Sequence[Decimal]],
    precision: int,
) -> dict[str, Any]:
    scalar_order = record["scalar_order"]
    polynomial_order = record["polynomial_order"]
    reduced_order = record["reduced_order"]
    q_top = load_array(root / record["files"]["q_top_row_major"], "d")
    rhs_reduced = load_array(root / record["files"]["rhs_reduced"], "d")
    reduced_solution = load_array(
        root / record["files"]["eigen_solution_reduced"], "d"
    )
    lambda_values = load_array(
        root / record["files"]["eigen_solution_lambda"], "d"
    )
    polynomial_solution = load_array(
        root / record["files"]["eigen_solution_polynomial"], "d"
    )
    require_length(
        q_top,
        polynomial_order * reduced_order,
        f"{record['record_id']} Q_top",
    )
    require_length(rhs_reduced, reduced_order, f"{record['record_id']} reduced RHS")
    require_length(
        reduced_solution, reduced_order, f"{record['record_id']} reduced solution"
    )
    require_length(lambda_values, scalar_order, f"{record['record_id']} lambda")
    require_length(
        polynomial_solution,
        polynomial_order,
        f"{record['record_id']} polynomial solution",
    )

    with localcontext() as context:
        context.prec = precision
        p_decimal = [Decimal.from_float(value) for value in p_full]
        q_decimal = [Decimal.from_float(value) for value in q_top]
        rhs_decimal = [Decimal.from_float(value) for value in rhs_full]
        reduced_rhs_decimal = [Decimal.from_float(value) for value in rhs_reduced]
        gamma_decimal = [Decimal.from_float(value) for value in reduced_solution]
        lambda_decimal = [Decimal.from_float(value) for value in lambda_values]
        polynomial_decimal = [
            Decimal.from_float(value) for value in polynomial_solution
        ]

        q_oracle_max_abs_error = Decimal(0)
        ptq_component_max = Decimal(0)
        ptq_row_sums = [Decimal(0) for _ in range(polynomial_order)]
        rhs_closure_max = Decimal(0)
        for column in range(reduced_order):
            oracle_rhs = [
                -p_decimal[(polynomial_order + column) * polynomial_order + basis]
                for basis in range(polynomial_order)
            ]
            oracle_column = [
                sum(
                    (
                        inverse_p_top_transpose[row][basis] * oracle_rhs[basis]
                        for basis in range(polynomial_order)
                    ),
                    Decimal(0),
                )
                for row in range(polynomial_order)
            ]
            for row in range(polynomial_order):
                actual_q = q_decimal[row * reduced_order + column]
                q_oracle_max_abs_error = max(
                    q_oracle_max_abs_error, abs(actual_q - oracle_column[row])
                )

            for basis in range(polynomial_order):
                moment = p_decimal[
                    (polynomial_order + column) * polynomial_order + basis
                ]
                moment += sum(
                    (
                        p_decimal[row * polynomial_order + basis]
                        * q_decimal[row * reduced_order + column]
                        for row in range(polynomial_order)
                    ),
                    Decimal(0),
                )
                absolute = abs(moment)
                ptq_component_max = max(ptq_component_max, absolute)
                ptq_row_sums[basis] += absolute

            reconstructed_rhs = rhs_decimal[polynomial_order + column]
            reconstructed_rhs += sum(
                (
                    q_decimal[row * reduced_order + column] * rhs_decimal[row]
                    for row in range(polynomial_order)
                ),
                Decimal(0),
            )
            rhs_closure_max = max(
                rhs_closure_max,
                abs(reconstructed_rhs - reduced_rhs_decimal[column]),
            )

        q_inf = max(
            Decimal(1),
            max(
                (
                    sum(
                        (
                            abs(q_decimal[row * reduced_order + column])
                            for column in range(reduced_order)
                        ),
                        Decimal(0),
                    )
                    for row in range(polynomial_order)
                ),
                default=Decimal(0),
            ),
        )
        ptq_inf = max(ptq_row_sums, default=Decimal(0))
        normalized_ptq = ratio(ptq_inf, p_transpose_inf * q_inf)

        cpd_moments = [
            sum(
                (
                    p_decimal[row * polynomial_order + basis]
                    * lambda_decimal[row]
                    for row in range(scalar_order)
                ),
                Decimal(0),
            )
            for basis in range(polynomial_order)
        ]
        lambda_inf = vector_inf_norm_decimal(lambda_decimal)
        eta_cpd = ratio(vector_inf_norm_decimal(cpd_moments), p_transpose_inf * lambda_inf)

        lambda_top_closure = Decimal(0)
        for row in range(polynomial_order):
            reconstructed = sum(
                (
                    q_decimal[row * reduced_order + column] * gamma_decimal[column]
                    for column in range(reduced_order)
                ),
                Decimal(0),
            )
            lambda_top_closure = max(
                lambda_top_closure, abs(reconstructed - lambda_decimal[row])
            )
        lambda_tail_bit_equal = all(
            lambda_values[polynomial_order + index] == reduced_solution[index]
            for index in range(reduced_order)
        )

        residual_inf = Decimal(0)
        residual_row = -1
        for row in range(scalar_order):
            a_lambda = sum(
                (
                    Decimal.from_float(lower_value(a_lower, row, column))
                    * lambda_decimal[column]
                    for column in range(scalar_order)
                ),
                Decimal(0),
            )
            p_c = sum(
                (
                    p_decimal[row * polynomial_order + basis]
                    * polynomial_decimal[basis]
                    for basis in range(polynomial_order)
                ),
                Decimal(0),
            )
            residual = abs(a_lambda + p_c - rhs_decimal[row])
            if residual > residual_inf:
                residual_inf = residual
                residual_row = row

        c_inf = vector_inf_norm_decimal(polynomial_decimal)
        d_inf = vector_inf_norm_decimal(rhs_decimal)
        alpha = ratio(
            residual_inf,
            a_inf * lambda_inf + p_inf * c_inf + d_inf,
        )

    return {
        "record_id": record["record_id"],
        "assembly_variant": record["assembly_variant"],
        "assembly_authority_before_adjudication": record["assembly_authority"],
        "decimal_precision": precision,
        "solution_source": "frozen Eigen capture from the locked binary64 corpus",
        "direct_nullspace_oracle": {
            "construction": (
                "Q=[-(P_top^T)^-1 P_tail^T; I], derived only from the local P"
            ),
            "q_top_max_abs_error": decimal_string(q_oracle_max_abs_error),
            "ptq_max_abs_component": decimal_string(ptq_component_max),
            "ptq_inf_norm": decimal_string(ptq_inf),
            "normalized_ptq_inf": decimal_string(normalized_ptq),
            "q_has_exact_structural_identity_tail": True,
            "q_structural_column_rank": reduced_order,
        },
        "reduced_rhs_closure": {
            "formula": "Q^T d using the captured Q and full RHS",
            "max_abs_error": decimal_string(rhs_closure_max),
        },
        "lambda_reconstruction": {
            "q_gamma_top_max_abs_error": decimal_string(lambda_top_closure),
            "identity_tail_bit_equal": lambda_tail_bit_equal,
        },
        "high_precision_external_reconstruction": {
            "augmented_residual_inf": decimal_string(residual_inf),
            "augmented_residual_max_row": residual_row,
            "normalized_augmented_alpha": decimal_string(alpha),
            "pt_lambda_components": [
                decimal_string(value) for value in cpd_moments
            ],
            "eta_cpd": decimal_string(eta_cpd),
            "two_pow_minus_32_limit": decimal_string(CPD_LIMIT),
            "eta_cpd_below_limit_before_external_evaluator_uncertainty": (
                eta_cpd <= CPD_LIMIT
            ),
            "acceptance_disposition": (
                "diagnostic only; external evaluator uncertainty and publication "
                "witnesses are not materialized"
            ),
        },
        "frozen_eigen_factor_diagnostic": record["frozen_eigen_baseline"],
        "_numeric": {
            "q_top_max_abs_error": q_oracle_max_abs_error,
            "ptq_max_abs_component": ptq_component_max,
            "normalized_ptq_inf": normalized_ptq,
            "alpha": alpha,
            "eta_cpd": eta_cpd,
            "rhs_closure_max": rhs_closure_max,
            "lambda_top_closure": lambda_top_closure,
            "lambda_tail_bit_equal": lambda_tail_bit_equal,
        },
    }


def audit_source(polatory: Path) -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "-C", str(polatory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(polatory), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if revision != POLATORY_COMMIT:
        raise RuntimeError(f"Polatory is at {revision}; expected {POLATORY_COMMIT}")
    if dirty:
        raise RuntimeError("Polatory source checkout is not clean")

    relative_paths = {
        "fine": Path("include/polatory/preconditioner/fine_grid.hpp"),
        "coarse": Path("include/polatory/preconditioner/coarse_grid.hpp"),
        "ras": Path("include/polatory/preconditioner/ras_preconditioner.hpp"),
        "monomial": Path("include/polatory/polynomial/monomial_basis.hpp"),
    }
    source_files: dict[str, Any] = {}
    for name, relative in relative_paths.items():
        path = polatory / relative
        lines = path.read_text(encoding="utf-8").splitlines()
        source_files[name] = {
            "path": relative.as_posix(),
            "sha256": sha256_file(path),
            "_lines": lines,
        }

    def occurrences(name: str, fragment: str) -> list[int]:
        return [
            index + 1
            for index, line in enumerate(source_files[name]["_lines"])
            if fragment in line
        ]

    local_offset_fragment = "flat_indices.push_back(mu_ + kDim * i + j);"
    full_lagrange_fragment = (
        "lagrange_p_ = lagrange_basis.evaluate(points_, grad_points_);"
    )
    facts = {
        "fine_local_offset_lines": occurrences("fine", local_offset_fragment),
        "coarse_local_offset_lines": occurrences("coarse", local_offset_fragment),
        "full_lagrange_matrix_lines": occurrences("ras", full_lagrange_fragment),
        "fine_local_mu_definition_lines": occurrences(
            "fine", "mu_(static_cast<Index>(point_idcs_.size()))"
        ),
        "coarse_local_mu_definition_lines": occurrences(
            "coarse", "mu_(static_cast<Index>(point_idcs_.size()))"
        ),
        "ras_full_mu_definition_lines": occurrences("ras", "mu_(points.rows())"),
        "point_major_gradient_storage_lines": occurrences(
            "monomial", "auto i_x = mu + 3 * i;"
        ),
    }
    for value in facts.values():
        if not value:
            raise RuntimeError("expected frozen Polatory source expression was not found")

    for details in source_files.values():
        details.pop("_lines")
    return {
        "commit": revision,
        "clean_checkout": True,
        "files": source_files,
        "facts": facts,
        "interpretation": (
            "RasPreconditioner builds lagrange_p_ over all value rows followed by "
            "point-major gradient rows, while FineGrid and CoarseGrid index its "
            "gradient portion from their local value-row count mu_."
        ),
    }


def strip_internal_numeric(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_internal_numeric(item)
            for key, item in value.items()
            if not key.startswith("_")
        }
    if isinstance(value, list):
        return [strip_internal_numeric(item) for item in value]
    return value


def main() -> int:
    args = parse_args()
    if args.precision < 50:
        raise SystemExit("--precision must be at least 50 decimal digits")

    corpus = args.corpus.resolve(strict=True)
    polatory = args.polatory_source.resolve(strict=True)
    manifest = json.loads((corpus / "manifest.raw.json").read_text(encoding="utf-8"))
    lock = json.loads((corpus / "manifest.lock.json").read_text(encoding="utf-8"))
    if manifest.get("polatory_commit") != POLATORY_COMMIT:
        raise RuntimeError(
            f"manifest Polatory commit {manifest.get('polatory_commit')} "
            f"does not equal {POLATORY_COMMIT}"
        )
    closure = verify_locked_corpus(corpus, manifest, lock)
    source = audit_source(polatory)
    records = {record["record_id"]: record for record in manifest["records"]}

    role_results: dict[str, Any] = {}
    for role in ROLES:
        canonical = records[f"{PANEL}-{role}-canonical"]
        literal = records[f"{PANEL}-{role}-frozen-literal"]
        identity = compare_payload_identity(lock, canonical, literal)
        if not identity["shared_inputs_all_byte_equal"]:
            raise RuntimeError(f"{role} canonical/literal source inputs differ")

        scalar_order = canonical["scalar_order"]
        polynomial_order = canonical["polynomial_order"]
        reduced_order = canonical["reduced_order"]
        if (
            scalar_order != literal["scalar_order"]
            or polynomial_order != literal["polynomial_order"]
            or reduced_order != literal["reduced_order"]
        ):
            raise RuntimeError(f"{role} canonical/literal shapes differ")

        p_full = load_array(corpus / canonical["files"]["p_row_major"], "d")
        a_lower = load_array(corpus / canonical["files"]["a_lower"], "d")
        rhs_full = load_array(corpus / canonical["files"]["rhs_full"], "d")
        captured_p_top = load_array(
            corpus / canonical["files"]["polynomial_p_top"], "d"
        )
        require_length(
            p_full, scalar_order * polynomial_order, f"{role} local P"
        )
        require_length(
            a_lower, scalar_order * (scalar_order + 1) // 2, f"{role} local A"
        )
        require_length(rhs_full, scalar_order, f"{role} full RHS")
        require_length(
            captured_p_top,
            polynomial_order * polynomial_order,
            f"{role} captured P_top",
        )
        if list(captured_p_top) != list(p_full[: polynomial_order * polynomial_order]):
            raise RuntimeError(f"{role} captured P_top does not match local P prefix")
        identity["p_top_payload_matches_local_p_prefix"] = True

        rank, inverse_p_top_transpose = p_top_rank_diagnostic(
            p_full, scalar_order, polynomial_order, args.precision
        )
        a_inf = matrix_inf_norm_decimal(a_lower, scalar_order, args.precision)
        p_inf = rectangular_inf_norm_decimal(
            p_full, scalar_order, polynomial_order, args.precision
        )
        with localcontext() as context:
            context.prec = args.precision
            p_transpose_inf = max(
                (
                    sum(
                        (
                            abs(
                                Decimal.from_float(
                                    p_full[row * polynomial_order + column]
                                )
                            )
                            for row in range(scalar_order)
                        ),
                        Decimal(0),
                    )
                    for column in range(polynomial_order)
                ),
                default=Decimal(0),
            )

        variants: dict[str, Any] = {}
        for variant, record in (
            ("canonical", canonical),
            ("frozen_literal", literal),
        ):
            variants[variant] = analyze_variant(
                corpus,
                record,
                p_full,
                a_lower,
                rhs_full,
                p_transpose_inf,
                a_inf,
                p_inf,
                inverse_p_top_transpose,
                args.precision,
            )

        canonical_numeric = variants["canonical"]["_numeric"]
        literal_numeric = variants["frozen_literal"]["_numeric"]
        q_error_ratio = ratio(
            literal_numeric["q_top_max_abs_error"],
            canonical_numeric["q_top_max_abs_error"],
        )
        ptq_ratio = ratio(
            literal_numeric["ptq_max_abs_component"],
            canonical_numeric["ptq_max_abs_component"],
        )
        alpha_ratio = ratio(
            literal_numeric["alpha"], canonical_numeric["alpha"]
        )
        eta_ratio = ratio(
            literal_numeric["eta_cpd"], canonical_numeric["eta_cpd"]
        )
        comparison = {
            "q_oracle_error_ratio_literal_over_canonical": decimal_string(
                q_error_ratio
            ),
            "ptq_component_ratio_literal_over_canonical": decimal_string(
                ptq_ratio
            ),
            "augmented_alpha_ratio_literal_over_canonical": decimal_string(
                alpha_ratio
            ),
            "eta_cpd_ratio_literal_over_canonical": decimal_string(
                eta_ratio
            ),
        }
        row_maps = {
            "canonical": row_map_audit(corpus, canonical, "canonical"),
            "frozen_literal": row_map_audit(
                corpus, literal, "frozen-literal"
            ),
        }
        # These gates make every claimed causal discriminator executable. Their
        # bounds detect the issue-35 signal; they are not acceptance thresholds.
        gates = {
            "shared_source_inputs_are_byte_equal": identity[
                "shared_inputs_all_byte_equal"
            ],
            "expected_assembly_outputs_are_byte_different": identity[
                "assembly_outputs_all_byte_different"
            ],
            "captured_p_top_matches_local_p_prefix": identity[
                "p_top_payload_matches_local_p_prefix"
            ],
            "canonical_row_map_is_global": row_maps["canonical"][
                "matches_global_row_map"
            ],
            "literal_row_map_is_local_not_global": (
                row_maps["frozen_literal"]["matches_frozen_local_row_map"]
                and not row_maps["frozen_literal"]["matches_global_row_map"]
            ),
            "canonical_q_matches_direct_oracle": (
                canonical_numeric["q_top_max_abs_error"] < Decimal("1e-12")
            ),
            "literal_q_disagrees_with_direct_oracle": (
                literal_numeric["q_top_max_abs_error"] > Decimal("1e-3")
            ),
            "canonical_ptq_is_roundoff_scale": (
                canonical_numeric["ptq_max_abs_component"] < Decimal("1e-12")
            ),
            "literal_ptq_is_order_one": (
                literal_numeric["ptq_max_abs_component"] > Decimal("1e-3")
            ),
            "augmented_matrix_residual_gap_is_reconstructed": (
                canonical_numeric["alpha"] < Decimal("1e-12")
                and literal_numeric["alpha"] > Decimal("1e-12")
                and alpha_ratio > Decimal("1e6")
            ),
            "cpd_gap_is_reconstructed": (
                canonical_numeric["eta_cpd"] <= CPD_LIMIT
                and literal_numeric["eta_cpd"] > CPD_LIMIT
                and eta_ratio > Decimal("1e10")
            ),
            "both_reduced_rhs_payloads_close": (
                canonical_numeric["rhs_closure_max"] < Decimal("1e-12")
                and literal_numeric["rhs_closure_max"] < Decimal("1e-12")
            ),
            "both_lambda_payloads_close": (
                canonical_numeric["lambda_top_closure"] < Decimal("1e-10")
                and literal_numeric["lambda_top_closure"] < Decimal("1e-10")
                and canonical_numeric["lambda_tail_bit_equal"]
                and literal_numeric["lambda_tail_bit_equal"]
            ),
            "p_top_is_far_from_rank_boundary": (
                rank["distance_above_conservative_parent_order_tau_factor"] > 1.0e6
            ),
        }
        failed_gates = sorted(name for name, passed in gates.items() if not passed)
        if failed_gates:
            raise RuntimeError(
                f"{role} adjudication gates failed: {', '.join(failed_gates)}"
            )
        role_results[role] = {
            "shape": {
                "scalar_order": scalar_order,
                "polynomial_order": polynomial_order,
                "reduced_order": reduced_order,
                "value_rows": canonical["value_rows"],
                "gradient_rows": canonical["gradient_rows"],
            },
            "payload_identity": identity,
            "row_map": row_maps,
            "semantic_rank_adjudication": {
                "p_top": rank,
                "q": (
                    "both stored representations have an exact structural identity "
                    "tail and therefore algebraic full column rank"
                ),
                "canonical_q_semantics": (
                    "the direct local-P oracle confirms the polynomial-nullspace "
                    "construction to binary64 roundoff"
                ),
                "frozen_literal_q_semantics": (
                    "algebraic column rank cannot repair P^T Q != 0; the "
                    "representation is semantically inadmissible before B factorization"
                ),
                "formal_qtaq_rank_certificate": "EVIDENCE_MISSING",
                "factor_health_profile": "EVIDENCE_MISSING",
                "scope": (
                    "this ticket adjudicates representation authority, not "
                    "production factor-path admission"
                ),
            },
            "variants": variants,
            "comparison": comparison,
            "adjudication_gates": gates,
            "all_adjudication_gates_satisfied": True,
            "adjudication_gate_role": (
                "falsifiable diagnosis invariants; not numerical acceptance "
                "thresholds"
            ),
        }

    if not all(
        result["all_adjudication_gates_satisfied"]
        for result in role_results.values()
    ):
        raise RuntimeError("independent evidence did not support the adjudication")

    hypothesis_results = {
        "H1_local_vs_global_gradient_offset": {
            "result": "SUPPORTED",
            "evidence": (
                "source, locked row indices, direct local-P Q oracle, P^T Q, "
                "augmented residual, and CPD residual all agree"
            ),
        },
        "H2_replay_matrix_residual_implementation_bug": {
            "result": "FALSIFIED",
            "evidence": (
                f"{args.precision}-digit standard-library reconstruction from raw "
                "A/P/d/lambda/c reproduces the matrix-residual gap independently; "
                "this does not replace the still-missing external value/gradient "
                "evaluator"
            ),
        },
        "H3_rank_boundary_or_binary64_roundoff": {
            "result": "FALSIFIED_AS_CAUSE",
            "evidence": (
                "P_top is far above tau_rank, both Q forms have structural full "
                "column rank, and the literal P^T Q defect remains order one at "
                f"{args.precision} decimal digits; formal Q^T A Q production rank "
                "certification remains separately missing"
            ),
        },
        "H4_reduced_rhs_mapping_only": {
            "result": "FALSIFIED",
            "evidence": (
                "P^T Q fails independently of any RHS, while each stored reduced "
                "RHS closes against its own Q and full RHS"
            ),
        },
        "H5_capture_misread_full_lagrange_layout": {
            "result": "FALSIFIED",
            "evidence": (
                "frozen source constructs lagrange_p_ over all value rows followed "
                "by point-major gradient rows; the literal map selects from local mu_"
            ),
        },
    }

    summary = {
        "schema": SCHEMA,
        "diagnosis_state": "ADJUDICATED",
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "precision_decimal_digits": args.precision,
        "locked_corpus": closure,
        "frozen_polatory_source": source,
        "roles": role_results,
        "hypothesis_results": hypothesis_results,
        "root_cause": (
            "Frozen Polatory FineGrid and CoarseGrid use the local domain value-row "
            "count mu_ as the gradient-row offset into a full lagrange_p_ matrix. "
            "In mixed-Hermite domains this selects unrelated global value/gradient "
            "rows, so the resulting Q is not a basis for null(P^T)."
        ),
        "adjudication": {
            "downstream_m3_representation_authority": "canonical-row-channel-map",
            "canonical_rule": (
                "all local value rows, followed by point-major gradient rows "
                "selected at source_value_rows + 3*global_gradient_index + component"
            ),
            "frozen_literal_disposition": (
                "diagnostic-only confirmed legacy internal assembly-defect fixture; "
                "must not supply factors or expected semantics to the mechanism panel"
            ),
            "dense_factor_substrate_disposition": (
                "not causal; the representation split exists before factorization"
            ),
            "public_intentional_difference_record": (
                "NOT_APPLICABLE_TO_THE_INTERNAL_REPRESENTATION_ALONE; no registered "
                "public outcome difference is established here. If validation "
                "observes one, it remains unadjudicated until the validation program "
                "materializes a narrow, human-approved "
                "IntentionalDifferenceAdjudication/v1 record"
            ),
            "production_factor_admission": (
                "still EVIDENCE_MISSING pending formal Q^T A Q semantic-rank "
                "certificate, FactorHealthProfile, external evaluator/publication "
                "witnesses, and bounded resource/thread ownership"
            ),
        },
    }
    public_summary = strip_internal_numeric(summary)
    encoded = json.dumps(public_summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
