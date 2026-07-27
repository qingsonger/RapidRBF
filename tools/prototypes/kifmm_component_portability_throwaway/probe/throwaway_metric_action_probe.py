"""Throwaway scalar-radial action decomposition probe.

This checks only the algebra proposed for a future kifmm fork. It deliberately
does not import or execute kifmm. Agreement can support the mapping identity;
it cannot establish FMM semantics, approximation accuracy, or certification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path


SCHEMA = "rapidrbf-kifmm-metric-action-probe/v1"
BETA = 0.37


def mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(a * b for a, b in zip(row, vector)) for row in matrix]


def mat_t_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [
        sum(matrix[row][column] * vector[row] for row in range(len(matrix)))
        for column in range(len(matrix[0]))
    ]


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def subtract(left: list[float], right: list[float]) -> list[float]:
    return [a - b for a, b in zip(left, right)]


def gaussian(
    displacement: list[float],
) -> tuple[float, list[float], list[list[float]]]:
    radius_squared = dot(displacement, displacement)
    value = math.exp(-BETA * radius_squared)
    gradient = [-2.0 * BETA * coordinate * value for coordinate in displacement]
    hessian = []
    for row, row_value in enumerate(displacement):
        hessian_row = []
        for column, column_value in enumerate(displacement):
            diagonal = -2.0 * BETA if row == column else 0.0
            hessian_row.append(
                (4.0 * BETA * BETA * row_value * column_value + diagonal)
                * value
            )
        hessian.append(hessian_row)
    return value, gradient, hessian


def coordinates(dimension: int, count: int, offset: float) -> list[list[float]]:
    points = []
    for index in range(count):
        points.append(
            [
                (
                    math.sin((index + 1) * (axis + 2) * 0.37 + offset)
                    + 0.13 * index
                    - 0.19 * axis
                )
                for axis in range(dimension)
            ]
        )
    return points


def scalar_weights(count: int) -> list[float]:
    return [
        math.cos((index + 1) * 0.43) - 0.11 * (index % 3)
        for index in range(count)
    ]


def vector_weights(dimension: int, count: int) -> list[list[float]]:
    return [
        [
            math.sin((index + 2) * (axis + 1) * 0.29)
            + 0.07 * (index - axis)
            for axis in range(dimension)
        ]
        for index in range(count)
    ]


def anisotropies(dimension: int) -> tuple[tuple[str, list[list[float]]], ...]:
    identity = [
        [1.0 if row == column else 0.0 for column in range(dimension)]
        for row in range(dimension)
    ]
    if dimension == 1:
        return (
            ("identity", identity),
            ("diagonal", [[1.7]]),
        )
    if dimension == 2:
        return (
            ("identity", identity),
            ("diagonal", [[1.4, 0.0], [0.0, 0.8]]),
            ("shear", [[1.2, 0.35], [0.1, 0.9]]),
        )
    return (
        ("identity", identity),
        ("diagonal", [[1.3, 0.0, 0.0], [0.0, 0.9, 0.0], [0.0, 0.0, 1.1]]),
        ("shear", [[1.1, 0.2, 0.0], [0.05, 0.95, 0.15], [0.0, 0.1, 1.05]]),
    )


def embed_metric(
    matrix: list[list[float]],
    point: list[float],
    origin: list[float],
) -> list[float]:
    metric = mat_vec(matrix, subtract(point, origin))
    return metric + [0.0] * (3 - len(metric))


def canonical_outputs(
    action: str,
    matrix: list[list[float]],
    sources: list[list[float]],
    targets: list[list[float]],
    scalar: list[float],
    vectors: list[list[float]],
) -> list[list[float]]:
    output_dimension = 1 if action in {"A", "F"} else len(matrix)
    outputs = [[0.0] * output_dimension for _ in targets]
    for target_index, target in enumerate(targets):
        for source_index, source in enumerate(sources):
            metric_displacement = mat_vec(matrix, subtract(target, source))
            value, gradient_metric, hessian_metric = gaussian(metric_displacement)
            if action == "A":
                outputs[target_index][0] += value * scalar[source_index]
            elif action == "F":
                physical_gradient = mat_t_vec(matrix, gradient_metric)
                outputs[target_index][0] -= dot(
                    physical_gradient, vectors[source_index]
                )
            elif action == "FT":
                physical_gradient = mat_t_vec(matrix, gradient_metric)
                for component in range(output_dimension):
                    outputs[target_index][component] += (
                        physical_gradient[component] * scalar[source_index]
                    )
            else:
                metric_weight = mat_vec(matrix, vectors[source_index])
                contracted = [
                    dot(row, metric_weight) for row in hessian_metric
                ]
                physical = mat_t_vec(matrix, contracted)
                for component in range(output_dimension):
                    outputs[target_index][component] -= physical[component]
    return outputs


def adapter_outputs(
    action: str,
    matrix: list[list[float]],
    sources: list[list[float]],
    targets: list[list[float]],
    scalar: list[float],
    vectors: list[list[float]],
) -> list[list[float]]:
    dimension = len(matrix)
    output_dimension = 1 if action in {"A", "F"} else dimension
    origin = [
        min(point[axis] for point in sources + targets)
        for axis in range(dimension)
    ]
    metric_sources = [
        embed_metric(matrix, point, origin) for point in sources
    ]
    metric_targets = [
        embed_metric(matrix, point, origin) for point in targets
    ]
    metric_vectors = [mat_vec(matrix, vector) for vector in vectors]
    outputs = [[0.0] * output_dimension for _ in targets]

    for target_index, target in enumerate(metric_targets):
        if action == "A":
            outputs[target_index][0] = sum(
                gaussian(subtract(target, source))[0] * scalar[source_index]
                for source_index, source in enumerate(metric_sources)
            )
            continue

        if action == "FT":
            metric_gradient = [0.0] * dimension
            for source_index, source in enumerate(metric_sources):
                gradient = gaussian(subtract(target, source))[1]
                for component in range(dimension):
                    metric_gradient[component] += (
                        gradient[component] * scalar[source_index]
                    )
            outputs[target_index] = mat_t_vec(matrix, metric_gradient)
            continue

        if action == "F":
            diagonal_contraction = 0.0
            for rhs in range(dimension):
                rhs_gradient_component = sum(
                    gaussian(subtract(target, source))[1][rhs]
                    * metric_vectors[source_index][rhs]
                    for source_index, source in enumerate(metric_sources)
                )
                diagonal_contraction += rhs_gradient_component
            outputs[target_index][0] = -diagonal_contraction
            continue

        metric_contraction = [0.0] * dimension
        for rhs in range(dimension):
            rhs_hessian = [[0.0] * dimension for _ in range(dimension)]
            for source_index, source in enumerate(metric_sources):
                hessian = gaussian(subtract(target, source))[2]
                charge = metric_vectors[source_index][rhs]
                for row in range(dimension):
                    for column in range(dimension):
                        rhs_hessian[row][column] += hessian[row][column] * charge
            for row in range(dimension):
                metric_contraction[row] += rhs_hessian[row][rhs]
        outputs[target_index] = [
            -value for value in mat_t_vec(matrix, metric_contraction)
        ]
    return outputs


def max_abs_difference(
    left: list[list[float]], right: list[list[float]]
) -> float:
    return max(
        abs(a - b)
        for left_row, right_row in zip(left, right)
        for a, b in zip(left_row, right_row)
    )


def max_abs(values: list[list[float]]) -> float:
    return max(abs(value) for row in values for value in row)


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper()


def run() -> dict[str, object]:
    rows = []
    for dimension in (1, 2, 3):
        sources = coordinates(dimension, 11, 0.17)
        scalar = scalar_weights(len(sources))
        vectors = vector_weights(dimension, len(sources))
        for geometry in ("cross", "self"):
            targets = (
                coordinates(dimension, 7, 0.83)
                if geometry == "cross"
                else [point[:] for point in sources]
            )
            for anisotropy, matrix in anisotropies(dimension):
                for action in ("A", "F", "FT", "H"):
                    canonical = canonical_outputs(
                        action, matrix, sources, targets, scalar, vectors
                    )
                    adapter = adapter_outputs(
                        action, matrix, sources, targets, scalar, vectors
                    )
                    error = max_abs_difference(canonical, adapter)
                    scale = max(max_abs(canonical), 1.0)
                    rows.append(
                        {
                            "action": action,
                            "adapter_shape": {
                                "rhs": dimension if action in {"F", "H"} else 1,
                                "target_derivative_order": (
                                    2 if action == "H" else 1 if action in {"F", "FT"} else 0
                                ),
                            },
                            "anisotropy": anisotropy,
                            "dimension": dimension,
                            "geometry": geometry,
                            "max_abs_error": format(error, ".17e"),
                            "relative_to_output_scale": format(error / scale, ".17e"),
                        }
                    )

    maximum = max(float(row["max_abs_error"]) for row in rows)
    if maximum > 2.0e-13:
        raise RuntimeError(f"mapping identity exceeded throwaway guard: {maximum}")

    return {
        "schema": SCHEMA,
        "authority": (
            "Throwaway algebraic mapping evidence only; not kifmm execution, "
            "accepted harness evidence, a sound certificate, or Auto qualification."
        ),
        "kernel": {"family": "Gaussian", "beta": BETA},
        "host": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
        },
        "source_sha256": source_sha256(),
        "summary": {
            "maximum_max_abs_error": format(maximum, ".17e"),
            "rows": len(rows),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.dumps(run(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
