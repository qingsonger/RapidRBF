#!/usr/bin/env python3
"""Throwaway semantic admission gate for the canonical hierarchy corpus.

NumPy's SVD and inverse routines are witness proposers only.  Every decision
made at binary64 is checked against explicit analytic roundoff envelopes.  A
precision-ladder provider may supply stronger outward envelopes; the prototype
fails closed when such a provider is absent.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from threadpoolctl import threadpool_info

import exact_rank

SCHEMA = "rapidrbf-canonical-hierarchy-admission-corpus-v3"
REPORT_SCHEMA = "RapidRBF/HierarchyAdmissionReport/v1"
PROFILE_SCHEMA = "RapidRBF/RankScalingProfile/v1"
CANONICAL_PROFILE_HASH = (
    "8d60d932464e04c1ce052ecf33acc93f6e72d424ba05d1af7e40cf69b456731e"
)
UNIT_ROUNDOFF = 2.0**-53
MIN_SUBNORMAL = 2.0**-1074
Q_LIMIT = Fraction(1, 2**32)
EXPECTED_EXCLUSIONS = {
    "M3-HERMITE-COMPOSITE-max-order-fine-frozen-literal",
    "M3-HERMITE-COMPOSITE-level0-coarse-frozen-literal",
}
EXPECTED_BLOCK_ARTIFACTS = {
    "domain_value_indices",
    "domain_gradient_indices",
    "inner_value_mask",
    "inner_gradient_mask",
    "canonical_lagrange_flat_indices",
    "a_lower",
    "p_row_major",
    "q_top_row_major",
    "qtaq_lower",
    "rhs_full",
    "rhs_reduced",
}
REFERENCE_BLOCK_ARTIFACTS = {"reference_gamma", "reference_lambda"}
EXPECTED_WORKLOAD_ARTIFACTS = {
    "value_points",
    "gradient_points",
    "observations",
    "selected_polynomial_indices",
}
GENERATOR_EXCLUSION = (
    "polatory::polynomial::UnisolventPointSet<3>::100-random-trial-full-pivot-lu"
)
FAILURE_ORDER = (
    "MalformedCorpus",
    "ResourceDenied",
    "IntegrityMismatch",
    "NonFinite",
    "RankDeficient",
    "IndeterminateRank",
    "NullspaceViolation",
    "EVIDENCE_MISSING",
)


class CorpusError(RuntimeError):
    """A stable admission failure."""

    def __init__(self, state: str, reason: str):
        super().__init__(reason)
        self.state = state
        self.reason = reason


class PrecisionResourceDenied(RuntimeError):
    """A ladder provider could not continue after a genuine straddle."""


class PrecisionAuthorityUnavailable(RuntimeError):
    """The installed ladder authority failed to produce a valid enclosure."""


@dataclass(frozen=True)
class RatioEnvelope:
    lower: float
    upper: float
    authority: str
    precision_bits: int
    diagnostics: Mapping[str, Any] | None = None

    def validate(self) -> None:
        if (
            math.isnan(self.lower)
            or math.isnan(self.upper)
            or self.lower < 0.0
            or self.upper < self.lower
        ):
            raise CorpusError(
                "EVIDENCE_MISSING",
                f"invalid outward ratio envelope [{self.lower}, {self.upper}]",
            )


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def json_safe(value: Any) -> Any:
    """Replace diagnostic infinities with stable JSON strings."""

    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def os_error_identity(error: OSError) -> str:
    details = [type(error).__name__]
    if error.errno is not None:
        details.append(f"errno={error.errno}")
    winerror = getattr(error, "winerror", None)
    if winerror is not None:
        details.append(f"winerror={winerror}")
    return ", ".join(details)


def profile_digest(profile: Mapping[str, Any]) -> str:
    body = dict(profile)
    body.pop("profile_hash", None)
    return sha256_bytes(canonical_json(body))


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    try:
        snapshot = json.loads(canonical_json(profile))
    except (TypeError, ValueError) as exc:
        raise CorpusError(
            "MalformedCorpus",
            f"rank profile cannot be materialized as canonical JSON: {exc}",
        ) from exc
    if not isinstance(snapshot, dict):
        raise CorpusError("MalformedCorpus", "rank profile root must be an object")
    if snapshot.get("schema") != PROFILE_SCHEMA:
        raise CorpusError("MalformedCorpus", "unexpected rank profile schema")
    try:
        expected = profile_digest(snapshot)
    except (TypeError, ValueError) as exc:
        raise CorpusError(
            "MalformedCorpus", f"rank profile is not canonical JSON data: {exc}"
        ) from exc
    if snapshot.get("profile_hash") != expected:
        raise CorpusError(
            "IntegrityMismatch",
            f"rank profile hash mismatch: expected {expected}, "
            f"found {snapshot.get('profile_hash')!r}",
        )
    if expected != CANONICAL_PROFILE_HASH:
        raise CorpusError(
            "IntegrityMismatch",
            "rank profile is self-consistent but is not the pinned canonical "
            f"profile: expected {CANONICAL_PROFILE_HASH}, found {expected}",
        )
    return snapshot


def read_profile_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CorpusError(
            "MalformedCorpus",
            f"cannot read rank profile ({os_error_identity(exc)})",
        ) from exc


def load_profile_bytes(payload: bytes) -> dict[str, Any]:
    try:
        decoded = payload.decode("utf-8")
        profile = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusError(
            "MalformedCorpus", f"cannot decode rank profile: {exc}"
        ) from exc
    if not isinstance(profile, dict):
        raise CorpusError("MalformedCorpus", "rank profile root must be an object")
    return validate_profile(profile)


def load_profile(path: Path) -> dict[str, Any]:
    return load_profile_bytes(read_profile_bytes(path))


def _length_prefixed_source_closure(
    profile_path: Path,
    profile_payload: bytes | None = None,
) -> dict[str, Any]:
    """Bind every executable admission input without leaking host paths."""

    root = Path(__file__).resolve().parent
    logical_sources: list[tuple[str, Path, bytes | None]] = [
        ("certify.py", root / "certify.py", None),
        ("exact_rank.py", root / "exact_rank.py", None),
        ("pyproject.toml", root / "pyproject.toml", None),
        ("rank-scaling-profile.v1.json", profile_path, profile_payload),
        ("uv.lock", root / "uv.lock", None),
    ]
    records: list[dict[str, Any]] = []
    framed = bytearray()
    for logical_path, source_path, captured_payload in logical_sources:
        if captured_payload is None:
            try:
                payload = source_path.read_bytes()
            except OSError as exc:
                raise CorpusError(
                    "EVIDENCE_MISSING",
                    "cannot read certifier source input "
                    f"{logical_path} ({os_error_identity(exc)})",
                ) from exc
        else:
            payload = captured_payload
        path_bytes = logical_path.encode("utf-8")
        framed.extend(len(path_bytes).to_bytes(8, "little"))
        framed.extend(path_bytes)
        framed.extend(len(payload).to_bytes(8, "little"))
        framed.extend(payload)
        records.append(
            {
                "path": logical_path,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    return {
        "algorithm": "sha256-length-prefixed-path-and-payload-v1",
        "sha256": sha256_bytes(bytes(framed)),
        "files": records,
    }


def _numpy_runtime_identity() -> dict[str, Any]:
    """Return stable BLAS identity fields, excluding wheel build paths."""

    try:
        configuration = np.show_config(mode="dicts")
    except (AttributeError, RuntimeError, TypeError) as exc:
        raise CorpusError(
            "EVIDENCE_MISSING",
            f"cannot inspect NumPy build configuration ({type(exc).__name__})",
        ) from exc
    if not isinstance(configuration, Mapping):
        raise CorpusError(
            "EVIDENCE_MISSING",
            "NumPy build configuration did not return an object",
        )
    dependencies = configuration.get("Build Dependencies", {})
    if not isinstance(dependencies, Mapping):
        raise CorpusError(
            "EVIDENCE_MISSING",
            "NumPy build dependencies did not return an object",
        )
    blas = dependencies.get("blas", {})
    lapack = dependencies.get("lapack", {})

    def selected(value: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise CorpusError(
                "EVIDENCE_MISSING",
                "NumPy BLAS/LAPACK build identity did not return an object",
            )
        return {
            key: value.get(key)
            for key in (
                "name",
                "found",
                "version",
                "detection method",
                "openblas configuration",
            )
        }

    return {
        "numpy_version": np.__version__,
        "blas": selected(blas),
        "lapack": selected(lapack),
        "simd_extensions": configuration.get("SIMD Extensions", {}),
    }


def _loaded_threadpool_identity() -> list[dict[str, Any]]:
    """Bind the BLAS binaries actually loaded by this process."""

    try:
        probe = np.array([[MIN_SUBNORMAL]], dtype=np.float64) @ np.array(
            [[1.0]], dtype=np.float64
        )
        controller_items = threadpool_info()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CorpusError(
            "EVIDENCE_MISSING",
            f"cannot inspect loaded threadpool runtime ({type(exc).__name__})",
        ) from exc
    if float(probe[0, 0]) != MIN_SUBNORMAL:
        raise CorpusError(
            "EVIDENCE_MISSING",
            "BLAS runtime probe did not preserve the minimum subnormal",
        )
    records: list[dict[str, Any]] = []
    if not isinstance(controller_items, list):
        raise CorpusError(
            "EVIDENCE_MISSING",
            "threadpool controller inventory did not return a list",
        )
    for item in controller_items:
        if not isinstance(item, Mapping):
            raise CorpusError(
                "EVIDENCE_MISSING",
                "threadpool controller record is not an object",
            )
        filepath_value = item.get("filepath")
        binary: dict[str, Any] | None = None
        if filepath_value:
            filepath = Path(str(filepath_value))
            try:
                payload = filepath.read_bytes()
            except OSError as exc:
                raise CorpusError(
                    "EVIDENCE_MISSING",
                    "cannot hash an actually loaded threadpool binary "
                    f"{filepath.name} ({os_error_identity(exc)})",
                ) from exc
            binary = {
                "basename": filepath.name,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        records.append(
            {
                "user_api": item.get("user_api"),
                "internal_api": item.get("internal_api"),
                "prefix": item.get("prefix"),
                "num_threads": item.get("num_threads"),
                "version": item.get("version"),
                "threading_layer": item.get("threading_layer"),
                "architecture": item.get("architecture"),
                "binary": binary,
            }
        )
    records.sort(
        key=lambda item: (
            str(item["user_api"]),
            str(item["internal_api"]),
            str((item["binary"] or {}).get("basename")),
        )
    )
    return records


def execution_provenance(
    profile_path: Path, profile_payload: bytes | None = None
) -> dict[str, Any]:
    thread_variables = (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "BLIS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
    try:
        threadpoolctl_version = distribution_version("threadpoolctl")
    except PackageNotFoundError as exc:
        raise CorpusError(
            "EVIDENCE_MISSING",
            "the pinned threadpoolctl runtime is unavailable",
        ) from exc
    return {
        "source_closure": _length_prefixed_source_closure(
            profile_path, profile_payload
        ),
        "runtime": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "python_compiler": platform.python_compiler(),
            "threadpoolctl_version": threadpoolctl_version,
            "system": platform.system(),
            "system_release": platform.release(),
            "system_version": platform.version(),
            "machine": platform.machine(),
            "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
            "byteorder": sys.byteorder,
            "binary64": {
                "radix": sys.float_info.radix,
                "mantissa_bits": sys.float_info.mant_dig,
                "minimum_subnormal_binary64_hex": MIN_SUBNORMAL.hex(),
            },
            **_numpy_runtime_identity(),
            "loaded_threadpools": _loaded_threadpool_identity(),
            "thread_environment": {
                name: os.environ.get(name) for name in thread_variables
            },
        },
    }


def validate_execution_coordinate(
    profile: Mapping[str, Any], provenance: Mapping[str, Any]
) -> None:
    try:
        expected = profile["execution_coordinate"]
        expected_environment = expected["required_thread_environment"]
        expected_blas = expected["required_loaded_blas"]
        expected_numpy_blas = expected["required_numpy_blas_build"]
        runtime = provenance["runtime"]
        observed_environment = runtime["thread_environment"]
        loaded_threadpools = runtime["loaded_threadpools"]
        observed_numpy_blas = runtime["blas"]
    except (KeyError, TypeError) as exc:
        raise CorpusError(
            "IntegrityMismatch",
            f"pinned execution-coordinate profile is malformed: {exc}",
        ) from exc
    for name, expected_value in expected_environment.items():
        observed = observed_environment.get(name)
        if observed != expected_value:
            raise CorpusError(
                "EVIDENCE_MISSING",
                f"runtime thread coordinate requires {name}={expected_value}, "
                f"found {observed!r}",
            )
    for key in ("name", "found", "version"):
        if observed_numpy_blas.get(key) != expected_numpy_blas.get(key):
            raise CorpusError(
                "EVIDENCE_MISSING",
                "NumPy BLAS build coordinate mismatch for "
                f"{key}: expected {expected_numpy_blas.get(key)!r}, "
                f"found {observed_numpy_blas.get(key)!r}",
            )
    blas_controllers = [
        item for item in loaded_threadpools if item.get("user_api") == "blas"
    ]
    matching = [
        item
        for item in blas_controllers
        if all(
            item.get(key) == expected_blas[key]
            for key in ("user_api", "internal_api", "prefix", "version")
        )
        and isinstance(item.get("binary"), Mapping)
        and item["binary"].get("basename") == expected_blas["binary_basename"]
        and item["binary"].get("sha256") == expected_blas["binary_sha256"]
    ]
    if len(matching) != 1 or len(blas_controllers) != 1:
        raise CorpusError(
            "EVIDENCE_MISSING",
            "the unique loaded BLAS controller does not match the pinned "
            "NumPy/OpenBLAS runtime",
        )
    try:
        required_threads = int(expected_blas["num_threads"])
        observed_threads = int(matching[0]["num_threads"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusError(
            "EVIDENCE_MISSING",
            "loaded BLAS controller has no valid thread count",
        ) from exc
    if observed_threads != required_threads:
        raise CorpusError(
            "EVIDENCE_MISSING",
            f"loaded {expected_blas['internal_api']} runtime does not use "
            f"{required_threads} threads",
        )


def publish_text_fresh(path: Path, text: str) -> None:
    """Publish a same-directory, fsynced file without ever replacing a target."""

    parent = path.parent
    if not parent.is_dir():
        raise OSError(f"output directory does not exist: {parent}")
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary_path = Path(temporary_name)
    published = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            os.rename(temporary_path, path)
        else:
            os.link(temporary_path, path)
        published = True
        if os.name != "nt":
            directory_descriptor = os.open(parent, os.O_RDONLY)
            try:
                try:
                    os.fsync(directory_descriptor)
                except OSError:
                    path.unlink()
                    published = False
                    raise
            finally:
                os.close(directory_descriptor)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            if not published:
                raise


def _gamma(operation_count: int) -> float:
    if operation_count <= 0:
        return 0.0
    q = operation_count * UNIT_ROUNDOFF
    if not q < 1.0:
        raise CorpusError(
            "EVIDENCE_MISSING",
            f"roundoff model does not close for {operation_count} operations",
        )
    return q / (1.0 - q)


def _validate_binary64_environment() -> None:
    info = sys.float_info
    if (
        info.radix != 2
        or info.mant_dig != 53
        or info.max_exp != 1024
        or info.min_exp != -1021
    ):
        raise CorpusError(
            "EVIDENCE_MISSING", "runtime is not an IEEE-754 binary64 environment"
        )
    zero = np.float64(0.0)
    one = np.float64(1.0)
    minimum = np.nextafter(zero, one)
    if (
        float(minimum) != MIN_SUBNORMAL
        or one + np.float64(2.0**-53) != one
        or one - np.float64(2.0**-54) != one
        or minimum * one != minimum
        or (np.array([[minimum]]) @ np.array([[one]]))[0, 0] != minimum
    ):
        raise CorpusError(
            "EVIDENCE_MISSING",
            "round-to-nearest or gradual-underflow assumption is not observable",
        )


def _up(value: float) -> float:
    return float(np.nextafter(np.float64(value), np.float64(math.inf)))


def _down_nonnegative(value: float) -> float:
    if value <= 0.0:
        return 0.0
    return max(
        0.0,
        float(np.nextafter(np.float64(value), np.float64(-math.inf))),
    )


def _subtract_down_nonnegative(left: float, right: float) -> float:
    return _down_nonnegative(left - right)


def _divide_down_nonnegative(numerator: float, denominator: float) -> float:
    if numerator <= 0.0:
        return 0.0
    if denominator <= 0.0:
        raise CorpusError("EVIDENCE_MISSING", "nonpositive outward denominator")
    return _down_nonnegative(numerator / denominator)


def _fraction_to_float_lower(value: Fraction) -> float:
    rounded = float(value)
    if math.isinf(rounded):
        rounded = sys.float_info.max
    if Fraction.from_float(rounded) > value:
        rounded = float(np.nextafter(np.float64(rounded), np.float64(-math.inf)))
    return rounded


def _sum_abs_upper(matrix: np.ndarray, axis: int) -> np.ndarray:
    terms = matrix.shape[axis]
    summed = np.sum(np.abs(matrix), axis=axis, dtype=np.float64)
    gamma = _gamma(max(0, terms - 1))
    underflow = terms * MIN_SUBNORMAL
    upper = np.nextafter(summed / (1.0 - gamma), np.float64(math.inf))
    upper = np.nextafter(upper + underflow, np.float64(math.inf))
    return upper


def _matrix_norm_upper(matrix: np.ndarray) -> float:
    if matrix.size == 0:
        return 0.0
    norm_one = float(np.max(_sum_abs_upper(matrix, axis=0)))
    norm_inf = float(np.max(_sum_abs_upper(matrix, axis=1)))
    return _up(math.sqrt(_up(norm_one * norm_inf)))


def _abs_interval_norm2(
    lower_abs: np.ndarray, upper_abs: np.ndarray
) -> tuple[float, float]:
    """Bounds the Euclidean norm from componentwise absolute-value bounds."""

    count = int(lower_abs.size)
    if count == 0:
        return 0.0, 0.0
    lower_flat = np.ravel(lower_abs).astype(np.float64, copy=False)
    upper_flat = np.ravel(upper_abs).astype(np.float64, copy=False)
    upper_dot = float(np.dot(upper_flat, upper_flat))
    gamma = _gamma(2 * count + 1)
    underflow = (2 * count + 1) * MIN_SUBNORMAL
    upper_sum = _up(upper_dot / (1.0 - gamma))
    upper_sum = _up(upper_sum + underflow)
    norm_upper = _up(math.sqrt(_up(upper_sum)))

    lower_dot = float(np.dot(lower_flat, lower_flat))
    lower_sum_upper = _up(lower_dot / (1.0 - gamma))
    lower_error = _up(gamma * lower_sum_upper)
    lower_error = _up(lower_error + underflow)
    lower_sum = _subtract_down_nonnegative(lower_dot, lower_error)
    norm_lower = _down_nonnegative(math.sqrt(lower_sum))
    return norm_lower, norm_upper


def _matmul_outward(
    left: np.ndarray, right: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (computed product, absolute error upper bound).

    The bound treats each finite input as its exact dyadic value.  It covers at
    most k products and k-1 additions per dot product, and separately inflates
    the rounded absolute-product sum used by the error calculation.
    """

    if left.ndim != 2 or right.ndim != 2 or left.shape[1] != right.shape[0]:
        raise CorpusError("MalformedCorpus", "invalid matrix multiplication shapes")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise CorpusError("NonFinite", "non-finite matrix reached analytic checker")
    k = left.shape[1]
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        product = left @ right
        sum_hat = np.abs(left) @ np.abs(right)
    if not np.all(np.isfinite(product)) or not np.all(np.isfinite(sum_hat)):
        raise CorpusError("EVIDENCE_MISSING", "binary64 checker overflowed")
    gamma = _gamma(2 * k + 1)
    underflow = (2 * k + 1) * MIN_SUBNORMAL
    sum_upper = np.nextafter(sum_hat / (1.0 - gamma), np.float64(math.inf))
    sum_upper = np.nextafter(sum_upper + underflow, np.float64(math.inf))
    error = np.nextafter(gamma * sum_upper, np.float64(math.inf))
    error = np.nextafter(error + underflow, np.float64(math.inf))
    return product, error


def _matvec_norm_envelope(
    matrix: np.ndarray, vector: np.ndarray
) -> tuple[float, float]:
    product, error = _matmul_outward(matrix, vector.reshape((-1, 1)))
    absolute = np.abs(product[:, 0])
    error_flat = error[:, 0]
    lower_abs = np.maximum(0.0, absolute - error_flat)
    lower_abs = np.nextafter(lower_abs, np.float64(-math.inf))
    lower_abs = np.maximum(0.0, lower_abs)
    upper_abs = np.nextafter(absolute + error_flat, np.float64(math.inf))
    return _abs_interval_norm2(lower_abs, upper_abs)


def _vector_norm_envelope(vector: np.ndarray) -> tuple[float, float]:
    absolute = np.abs(vector)
    return _abs_interval_norm2(absolute, absolute)


def analytic_ratio_envelope(
    matrix: np.ndarray, decision_tau: float | None = None
) -> RatioEnvelope:
    """Certify a singular-value ratio envelope using candidate witnesses."""

    _validate_binary64_environment()
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or min(matrix.shape) == 0:
        raise CorpusError("MalformedCorpus", "rank subject must be a nonempty matrix")
    if not np.all(np.isfinite(matrix)):
        raise CorpusError("NonFinite", "rank subject contains NaN or infinity")
    if np.count_nonzero(matrix) == 0:
        return RatioEnvelope(
            0.0,
            0.0,
            "exact-zero-dyadic",
            53,
            {"checker": "exact-zero"},
        )
    zero_row = bool(np.any(np.all(matrix == 0.0, axis=1)))
    zero_column = bool(np.any(np.all(matrix == 0.0, axis=0)))
    structurally_singular = (zero_row and matrix.shape[0] <= matrix.shape[1]) or (
        zero_column and matrix.shape[1] <= matrix.shape[0]
    )
    if structurally_singular:
        return RatioEnvelope(
            0.0,
            0.0,
            "exact-zero-row-or-column-dyadic",
            53,
            {
                "checker": "exact structural singularity",
                "zero_row": zero_row,
                "zero_column": zero_column,
                "nonzero_matrix": True,
            },
        )

    try:
        if matrix.shape[0] == matrix.shape[1]:
            left_inverse = np.linalg.inv(matrix)
        else:
            left_inverse = np.linalg.pinv(matrix)
    except np.linalg.LinAlgError:
        left_inverse = None

    sigma_max_upper = _matrix_norm_upper(matrix)
    if sigma_max_upper == 0.0:
        return RatioEnvelope(0.0, 0.0, "analytic-outward-f64", 53)

    sigma_min_lower = 0.0
    delta_upper = math.inf
    inverse_norm_upper = math.inf
    if left_inverse is not None and np.all(np.isfinite(left_inverse)):
        if matrix.shape[0] >= matrix.shape[1]:
            candidate_identity, product_error = _matmul_outward(left_inverse, matrix)
        else:
            candidate_identity, product_error = _matmul_outward(matrix, left_inverse)
        identity = np.eye(candidate_identity.shape[0], dtype=np.float64)
        residual_abs_upper = np.nextafter(
            np.abs(identity - candidate_identity) + product_error,
            np.float64(math.inf),
        )
        delta_upper = _matrix_norm_upper(residual_abs_upper)
        inverse_norm_upper = _matrix_norm_upper(left_inverse)
        if delta_upper < 1.0 and inverse_norm_upper > 0.0:
            sigma_min_lower = _divide_down_nonnegative(
                _subtract_down_nonnegative(1.0, delta_upper),
                inverse_norm_upper,
            )

    ratio_lower = _divide_down_nonnegative(sigma_min_lower, sigma_max_upper)
    if decision_tau is not None and ratio_lower > decision_tau:
        envelope = RatioEnvelope(
            ratio_lower,
            1.0,
            "left-or-right-inverse-analytic-outward-v1",
            53,
            {
                "witness_proposer": "binary64 inverse or pseudoinverse",
                "singular_vector_proposer_skipped": True,
                "delta_upper": delta_upper,
                "inverse_norm_upper": inverse_norm_upper,
                "sigma_min_lower": sigma_min_lower,
                "sigma_max_upper": sigma_max_upper,
            },
        )
        envelope.validate()
        return envelope

    try:
        _u, singular_values, vh = np.linalg.svd(matrix, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise CorpusError(
            "EVIDENCE_MISSING", f"SVD witness proposer failed: {exc}"
        ) from exc
    if not np.all(np.isfinite(singular_values)) or not np.all(np.isfinite(vh)):
        raise CorpusError("EVIDENCE_MISSING", "SVD proposer returned non-finite data")

    v_min = np.asarray(vh[-1, :], dtype=np.float64)
    v_max = np.asarray(vh[0, :], dtype=np.float64)
    v_min_lower, _v_min_upper = _vector_norm_envelope(v_min)
    _v_max_lower, v_max_upper = _vector_norm_envelope(v_max)
    _min_image_lower, min_image_upper = _matvec_norm_envelope(matrix, v_min)
    max_image_lower, _max_image_upper = _matvec_norm_envelope(matrix, v_max)

    sigma_min_upper = (
        math.inf if v_min_lower == 0.0 else _up(min_image_upper / v_min_lower)
    )
    sigma_max_lower = (
        0.0
        if v_max_upper == 0.0
        else _divide_down_nonnegative(max_image_lower, v_max_upper)
    )
    ratio_upper = (
        math.inf if sigma_max_lower == 0.0 else _up(sigma_min_upper / sigma_max_lower)
    )
    envelope = RatioEnvelope(
        ratio_lower,
        ratio_upper,
        "left-inverse-and-singular-witness-analytic-outward-v1",
        53,
        {
            "svd_proposer_ratio": float(singular_values[-1] / singular_values[0]),
            "delta_upper": delta_upper,
            "left_inverse_norm_upper": inverse_norm_upper,
            "sigma_min_lower": sigma_min_lower,
            "sigma_min_upper": sigma_min_upper,
            "sigma_max_lower": sigma_max_lower,
            "sigma_max_upper": sigma_max_upper,
        },
    )
    envelope.validate()
    return envelope


def tau_rank(shape: Sequence[int]) -> float:
    return max(int(shape[0]), int(shape[1])) * UNIT_ROUNDOFF


def classify_ratio(envelope: RatioEnvelope, tau: float) -> str:
    envelope.validate()
    if envelope.lower > tau:
        return "Admitted"
    if envelope.upper <= tau:
        return "RankDeficient"
    return "straddle"


def drive_precision_ladder(
    initial: RatioEnvelope,
    tau: float,
    ladder_bits: Sequence[int],
    provider: Callable[[int], RatioEnvelope] | None,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Apply the normative straddle state machine."""

    steps: list[dict[str, Any]] = []

    def record(envelope: RatioEnvelope) -> str:
        classification = classify_ratio(envelope, tau)
        width = (
            math.inf
            if math.isinf(envelope.upper)
            else (
                0.0
                if envelope.upper == envelope.lower
                else _up(envelope.upper - envelope.lower)
            )
        )
        steps.append(
            {
                "precision_bits": envelope.precision_bits,
                "authority": envelope.authority,
                "lower": envelope.lower,
                "lower_binary64_hex": float(envelope.lower).hex(),
                "upper": envelope.upper,
                "upper_binary64_hex": float(envelope.upper).hex(),
                "width": width,
                "width_binary64_hex": float(width).hex(),
                "tau_rank": tau,
                "tau_rank_binary64_hex": float(tau).hex(),
                "classification": classification,
                "diagnostics": envelope.diagnostics,
            }
        )
        return classification

    classification = record(initial)
    if classification != "straddle":
        return classification, steps, None
    if provider is None:
        return (
            "EVIDENCE_MISSING",
            steps,
            "precision ladder authority is not installed",
        )

    for bits in ladder_bits:
        try:
            envelope = provider(int(bits))
        except PrecisionResourceDenied as exc:
            return (
                "EVIDENCE_MISSING",
                steps,
                (
                    "precision ladder resource authority was unavailable before "
                    "the required final narrow straddle completed: "
                    f"{exc}"
                ),
            )
        except PrecisionAuthorityUnavailable as exc:
            return (
                "EVIDENCE_MISSING",
                steps,
                (
                    "precision ladder checker failed before the required final "
                    f"narrow straddle completed: {exc}"
                ),
            )
        if envelope.precision_bits != int(bits):
            raise CorpusError(
                "EVIDENCE_MISSING",
                f"ladder provider returned {envelope.precision_bits} bits for {bits}",
            )
        classification = record(envelope)
        if classification != "straddle":
            return classification, steps, None

    final = steps[-1]
    if final["width"] > tau / 8.0:
        return (
            "EVIDENCE_MISSING",
            steps,
            "2048-bit straddle envelope is wider than tau_rank/8",
        )
    return "IndeterminateRank", steps, "threshold remains inside final envelope"


def _ceil_log2_positive(value: float) -> int:
    mantissa, exponent = math.frexp(value)
    return exponent - 1 if mantissa == 0.5 else exponent


def equilibrate_power2(matrix: np.ndarray) -> tuple[np.ndarray, list[int], list[int]]:
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2:
        raise CorpusError("MalformedCorpus", "equilibration requires a matrix")
    if not np.all(np.isfinite(matrix)):
        raise CorpusError("NonFinite", "non-finite rank subject")
    row_exponents: list[int] = []
    scaled = matrix.copy()
    for row in range(scaled.shape[0]):
        maximum = float(np.max(np.abs(scaled[row, :])))
        exponent = 0 if maximum == 0.0 else -_ceil_log2_positive(maximum)
        row_exponents.append(exponent)
        scaled[row, :] = np.ldexp(scaled[row, :], exponent)
    column_exponents: list[int] = []
    for column in range(scaled.shape[1]):
        maximum = float(np.max(np.abs(scaled[:, column])))
        exponent = 0 if maximum == 0.0 else -_ceil_log2_positive(maximum)
        column_exponents.append(exponent)
        scaled[:, column] = np.ldexp(scaled[:, column], exponent)
    if not np.all(np.isfinite(scaled)):
        raise CorpusError("NonFinite", "power-of-two equilibration overflowed")
    scaled[scaled == 0.0] = 0.0
    return scaled, row_exponents, column_exponents


def exact_precision_provider(
    matrix: np.ndarray, profile: Mapping[str, Any]
) -> Callable[[int], RatioEnvelope]:
    """Install the pinned exact-dyadic authority for a genuine straddle."""

    try:
        checker = profile["rank_rule"]["precision_checker"]
        limits_value = checker["resource_limits"]
        supported_bits = tuple(
            int(value) for value in checker["supported_precision_bits"]
        )
        limits = exact_rank.ExactRankLimits(
            max_min_dimension=int(limits_value["max_min_dimension"]),
            max_matrix_elements=int(limits_value["max_matrix_elements"]),
            max_gram_term_products=int(limits_value["max_gram_term_products"]),
            max_bisection_iterations=int(limits_value["max_bisection_iterations"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusError(
            "IntegrityMismatch",
            f"pinned precision-checker profile is malformed: {exc}",
        ) from exc
    ladder_bits = tuple(
        int(value) for value in profile["rank_rule"]["precision_ladder_bits"]
    )
    if (
        checker.get("profile") != exact_rank.AUTHORITY
        or supported_bits != exact_rank.SUPPORTED_PRECISION_BITS
        or ladder_bits != supported_bits
    ):
        raise CorpusError(
            "IntegrityMismatch",
            "pinned precision-checker identity or ladder does not match its "
            "executed implementation",
        )

    def provide(precision_bits: int) -> RatioEnvelope:
        try:
            exact = exact_rank.exact_ratio_envelope(
                matrix, precision_bits, limits=limits
            )
        except exact_rank.ExactRankResourceDenied as exc:
            raise PrecisionResourceDenied(str(exc)) from exc
        except exact_rank.ExactRankError as exc:
            raise PrecisionAuthorityUnavailable(str(exc)) from exc
        return RatioEnvelope(
            lower=exact.lower,
            upper=exact.upper,
            authority=exact.authority,
            precision_bits=exact.precision_bits,
            diagnostics=exact.diagnostics,
        )

    return provide


def rank_certificate(
    certificate_id: str,
    subject: str,
    matrix: np.ndarray,
    profile: Mapping[str, Any],
    *,
    max_resource_units: int | None = None,
    provider: Callable[[int], RatioEnvelope] | None = None,
) -> dict[str, Any]:
    profile = validate_profile(profile)
    matrix = np.asarray(matrix, dtype=np.float64)
    subject_units = int(matrix.size)
    minimum_dimension = int(min(matrix.shape)) if matrix.ndim == 2 else 0
    proposer_units = int(3 * matrix.size + 2 * minimum_dimension**2)
    checker_units = int(8 * matrix.size + 4 * minimum_dimension**2)
    required_units = subject_units + proposer_units + checker_units
    base = {
        "certificate_id": certificate_id,
        "subject": subject,
        "shape": list(matrix.shape),
        "backend_invocations": 0,
        "resource": {
            "required_logical_units": required_units,
            "subject_logical_units": subject_units,
            "proposer_logical_units": proposer_units,
            "checker_logical_units": checker_units,
            "limit_logical_units": max_resource_units,
        },
    }
    if max_resource_units is not None and required_units > max_resource_units:
        return {
            **base,
            "state": "ResourceDenied",
            "reason": "resource preflight denied before rank checking",
            "steps": [],
        }
    if not np.all(np.isfinite(matrix)):
        return {
            **base,
            "state": "NonFinite",
            "reason": "rank subject contains NaN or infinity",
            "steps": [],
        }
    try:
        equilibrated, row_exp, column_exp = equilibrate_power2(matrix)
        tau = tau_rank(equilibrated.shape)
        initial = analytic_ratio_envelope(equilibrated, decision_tau=tau)
        effective_provider = (
            provider
            if provider is not None
            else exact_precision_provider(equilibrated, profile)
        )
        state, steps, reason = drive_precision_ladder(
            initial,
            tau,
            profile["rank_rule"]["precision_ladder_bits"],
            effective_provider,
        )
        return {
            **base,
            "state": state,
            "reason": reason,
            "tau_rank": tau,
            "tau_rank_binary64_hex": float(tau).hex(),
            "equilibration": {
                "profile": profile["equilibration"]["profile"],
                "row_exponents": row_exp,
                "column_exponents": column_exp,
            },
            "steps": steps,
        }
    except CorpusError as exc:
        return {
            **base,
            "state": exc.state,
            "reason": exc.reason,
            "steps": [],
        }


def preflight_rank_subjects(
    subjects: Sequence[tuple[str, str, Sequence[int]]],
    max_resource_units: int | None,
) -> None:
    """Deny from locked shapes before any rank-subject array is materialized."""

    if max_resource_units is None:
        return
    for certificate_id, subject, shape_value in subjects:
        shape = tuple(shape_value)
        if len(shape) != 2 or any(
            not isinstance(dimension, int) or dimension < 0 for dimension in shape
        ):
            raise CorpusError(
                "MalformedCorpus",
                f"{certificate_id} has invalid locked rank shape {shape_value!r}",
            )
        subject_units = math.prod(shape)
        minimum_dimension = min(shape)
        proposer_units = 3 * subject_units + 2 * minimum_dimension**2
        checker_units = 8 * subject_units + 4 * minimum_dimension**2
        required_units = subject_units + proposer_units + checker_units
        if required_units > max_resource_units:
            raise CorpusError(
                "ResourceDenied",
                "rank resource preflight denied from locked metadata before "
                f"payload materialization: {certificate_id}/{subject} requires "
                f"{required_units} logical units, limit is {max_resource_units}",
            )


def _fraction_power_of_two(exponent: int) -> Fraction:
    return Fraction(2**exponent, 1) if exponent >= 0 else Fraction(1, 2 ** (-exponent))


def _ceil_log2_fraction(value: Fraction) -> int:
    if value <= 0:
        raise ValueError("positive fraction required")
    estimate = value.numerator.bit_length() - value.denominator.bit_length()
    power = _fraction_power_of_two(estimate)
    return estimate if value <= power else estimate + 1


def coordinate_transform(
    value_points: np.ndarray, gradient_points: np.ndarray
) -> dict[str, Any]:
    all_points = np.vstack((value_points, gradient_points))
    if all_points.ndim != 2 or all_points.shape[1] != 3 or all_points.shape[0] == 0:
        raise CorpusError(
            "MalformedCorpus", "workload coordinates must be nonempty Nx3"
        )
    if not np.all(np.isfinite(all_points)):
        raise CorpusError("NonFinite", "workload coordinates contain NaN or infinity")
    centers: list[Fraction] = []
    scales: list[Fraction] = []
    for axis in range(3):
        exact = [Fraction.from_float(float(item)) for item in all_points[:, axis]]
        center = (min(exact) + max(exact)) / 2
        radius = max(abs(item - center) for item in exact)
        scale = (
            Fraction(1)
            if radius == 0
            else _fraction_power_of_two(_ceil_log2_fraction(radius))
        )
        centers.append(center)
        scales.append(scale)
    return {
        "centers": centers,
        "scales": scales,
        "center_exact": [_fraction_text(value) for value in centers],
        "scale_exact": [_fraction_text(value) for value in scales],
        "center_hex": [float(value).hex() for value in centers],
        "scale_hex": [float(value).hex() for value in scales],
    }


def build_polynomial_matrix(
    degree: int,
    value_points: np.ndarray,
    gradient_points: np.ndarray,
    transform: Mapping[str, Any] | None,
) -> np.ndarray:
    if degree not in (0, 1):
        raise CorpusError("MalformedCorpus", f"unsupported polynomial degree {degree}")
    columns = 1 if degree == 0 else 4
    result = np.zeros(
        (value_points.shape[0] + 3 * gradient_points.shape[0], columns),
        dtype=np.float64,
    )
    result[: value_points.shape[0], 0] = 1.0
    if degree == 0:
        return result
    if transform is None:
        centers = [Fraction(0), Fraction(0), Fraction(0)]
        scales = [Fraction(1), Fraction(1), Fraction(1)]
    else:
        centers = transform["centers"]
        scales = transform["scales"]
    for row, point in enumerate(value_points):
        for axis in range(3):
            exact = (Fraction.from_float(float(point[axis])) - centers[axis]) / scales[
                axis
            ]
            result[row, axis + 1] = float(exact)
    offset = value_points.shape[0]
    for gradient in range(gradient_points.shape[0]):
        for component in range(3):
            result[offset + 3 * gradient + component, component + 1] = float(
                Fraction(1, 1) / scales[component]
            )
    result[result == 0.0] = 0.0
    return result


def _require_exact_f64(actual: np.ndarray, expected: np.ndarray, label: str) -> None:
    if actual.shape != expected.shape:
        raise CorpusError(
            "MalformedCorpus",
            f"{label} shape {actual.shape} does not match {expected.shape}",
        )
    if not np.array_equal(actual.view(np.uint64), expected.view(np.uint64)):
        mismatch = np.argwhere(actual.view(np.uint64) != expected.view(np.uint64))[0]
        raise CorpusError(
            "IntegrityMismatch",
            f"{label} differs from canonical physical monomial at {tuple(mismatch)}",
        )


def _fraction_matrix_inverse(matrix: np.ndarray) -> list[list[Fraction]]:
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise CorpusError("MalformedCorpus", "exact inverse requires square matrix")
    n = matrix.shape[0]
    augmented: list[list[Fraction]] = []
    for row in range(n):
        augmented.append(
            [Fraction.from_float(float(matrix[row, column])) for column in range(n)]
            + [Fraction(int(row == column), 1) for column in range(n)]
        )
    for column in range(n):
        pivot = next((row for row in range(column, n) if augmented[row][column]), None)
        if pivot is None:
            raise CorpusError("RankDeficient", "P_top is exactly singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    left - factor * right
                    for left, right in zip(augmented[row], augmented[column])
                ]
    return [row[n:] for row in augmented]


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def q_nullspace_certificate(
    block_id: str,
    p_matrix: np.ndarray,
    q_top: np.ndarray,
    flat_indices: np.ndarray,
    domain_values: np.ndarray,
    domain_gradients: np.ndarray,
    source_value_rows: int,
) -> dict[str, Any]:
    base = {
        "certificate_id": f"q-nullspace:{block_id}",
        "block_id": block_id,
        "backend_invocations": 0,
    }
    if not np.all(np.isfinite(p_matrix)) or not np.all(np.isfinite(q_top)):
        return {**base, "state": "NonFinite", "reason": "P or Q_top is non-finite"}
    m, l = p_matrix.shape
    r = m - l
    if r <= 0 or q_top.shape != (l, r):
        return {
            **base,
            "state": "MalformedCorpus",
            "reason": f"Q_top shape {q_top.shape} is not {(l, r)}",
        }
    expected_flat = list(map(int, domain_values))
    for index in map(int, domain_gradients):
        expected_flat.extend(
            source_value_rows + 3 * index + component for component in range(3)
        )
    if list(map(int, flat_indices)) != expected_flat:
        return {
            **base,
            "state": "MalformedCorpus",
            "reason": "canonical global Lagrange row map does not match domain indices",
        }

    try:
        p_top = p_matrix[:l, :]
        p_tail = p_matrix[l:, :]
        inverse_transpose = _fraction_matrix_inverse(p_top.T)
        for row in range(l):
            for column in range(l):
                exact_product = sum(
                    Fraction.from_float(float(p_top[item, row]))
                    * inverse_transpose[item][column]
                    for item in range(l)
                )
                if exact_product != Fraction(int(row == column), 1):
                    raise CorpusError(
                        "EVIDENCE_MISSING",
                        "exact rational P_top inverse verification failed",
                    )
        digest = hashlib.sha256()
        max_difference = Fraction(0)
        # Q* column j is -(P_top^T)^-1 times P_tail[j,:]^T.
        for column in range(r):
            tail = [
                Fraction.from_float(float(p_tail[column, item])) for item in range(l)
            ]
            qstar_column: list[Fraction] = []
            for row in range(l):
                qstar = -sum(
                    inverse_transpose[row][item] * tail[item] for item in range(l)
                )
                qstar_column.append(qstar)
                digest.update(_fraction_text(qstar).encode("ascii"))
                digest.update(b"\n")
                captured = Fraction.from_float(float(q_top[row, column]))
                max_difference = max(max_difference, abs(captured - qstar))
            for polynomial_column in range(l):
                exact_residual = tail[polynomial_column] + sum(
                    Fraction.from_float(float(p_top[top, polynomial_column]))
                    * qstar_column[top]
                    for top in range(l)
                )
                if exact_residual:
                    raise CorpusError(
                        "EVIDENCE_MISSING",
                        "exact rational P^T Qstar verification failed",
                    )

        # Exact-dyadic residual of the captured Q.  This is stronger than the
        # operational f64 envelope and avoids mistaking rounded zero for proof.
        residual_inf = Fraction(0)
        for row in range(l):
            row_sum = Fraction(0)
            for column in range(r):
                residual = Fraction.from_float(float(p_tail[column, row]))
                for top in range(l):
                    residual += Fraction.from_float(
                        float(p_top[top, row])
                    ) * Fraction.from_float(float(q_top[top, column]))
                row_sum += abs(residual)
            residual_inf = max(residual_inf, row_sum)
        p_transpose_norm_inf = max(
            sum(
                Fraction.from_float(abs(float(p_matrix[row, column])))
                for row in range(m)
            )
            for column in range(l)
        )
        q_norm_inf = max(
            Fraction(1),
            max(
                sum(Fraction.from_float(abs(float(item))) for item in q_top[row, :])
                for row in range(l)
            ),
        )
        denominator = p_transpose_norm_inf * q_norm_inf
        eta = Fraction(0) if residual_inf == 0 else residual_inf / denominator

        product, error = _matmul_outward(p_top.T, q_top)
        candidate = product + p_tail.T
        operational_entry_upper = np.nextafter(
            np.abs(candidate) + error, np.float64(math.inf)
        )
        operational_upper = float(
            np.max(_sum_abs_upper(operational_entry_upper, axis=1))
        )
        denominator_lower = _fraction_to_float_lower(denominator)
        operational_eta_upper = (
            math.inf
            if denominator_lower == 0.0
            else _up(operational_upper / denominator_lower)
        )
        state = "Admitted" if eta <= Q_LIMIT else "NullspaceViolation"
        return {
            **base,
            "state": state,
            "reason": None
            if state == "Admitted"
            else "captured Q exceeds CPD-level residual bound",
            "shape": [m, r],
            "canonical_row_map": "source_value_rows + 3*global_gradient_index + component",
            "qstar_exact_proof": {
                "formula": "[-(P_top^T)^-1 P_tail^T; I]",
                "rational_stream_sha256": digest.hexdigest(),
                "rational_stream_order": "Q_top columns, then rows",
                "p_transpose_qstar_exact_zero": True,
                "identity_tail_structural_rank": r,
                "captured_bit_equality_required": False,
            },
            "captured_q": {
                "authority": "exact-dyadic-rational-normalized-residual",
                "exact_dyadic_eta": _fraction_text(eta),
                "limit": "1/4294967296",
                "operational_analytic_eta_upper": operational_eta_upper,
                "operational_analytic_eta_is_authority": False,
                "max_abs_difference_from_qstar": _fraction_text(max_difference),
            },
        }
    except CorpusError as exc:
        return {**base, "state": exc.state, "reason": exc.reason}


class Corpus:
    """Validated and hash-bound view of a raw hierarchy capture."""

    def __init__(
        self,
        manifest_path: Path,
        *,
        production: bool,
        inventory: Mapping[str, Any] | None = None,
    ):
        self.path = manifest_path.resolve()
        try:
            self.raw_manifest = self.path.read_bytes()
            self.manifest = json.loads(self.raw_manifest)
        except (OSError, json.JSONDecodeError) as exc:
            raise CorpusError(
                "MalformedCorpus", f"cannot read manifest: {exc}"
            ) from exc
        if not isinstance(self.manifest, dict):
            raise CorpusError("MalformedCorpus", "manifest root must be an object")
        self.root = self.path.parent
        self.production = production
        self.expected_inventory = inventory
        if production and inventory is None:
            raise CorpusError(
                "MalformedCorpus", "production validation requires frozen inventory"
            )
        self.artifacts: dict[str, dict[str, Any]] = {}
        self.artifact_paths: dict[str, Path] = {}
        self.artifact_digests: dict[str, str] = {}
        self.artifact_locks: list[dict[str, Any]] = []
        self.workloads: dict[str, dict[str, Any]] = {}
        self.blocks: dict[str, dict[str, Any]] = {}
        self.factor_sources: dict[str, dict[str, Any]] = {}
        self.lock: dict[str, Any] | None = None
        self.corpus_sha256: str | None = None
        self._validate()

    @staticmethod
    def _unique(records: Any, key: str, label: str) -> dict[str, dict[str, Any]]:
        if not isinstance(records, list):
            raise CorpusError("MalformedCorpus", f"{label} must be an array")
        result: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get(key), str):
                raise CorpusError("MalformedCorpus", f"{label} entry lacks {key}")
            identifier = record[key]
            if identifier in result:
                raise CorpusError(
                    "MalformedCorpus", f"duplicate {label} id {identifier}"
                )
            result[identifier] = record
        return result

    def _validate(self) -> None:
        m = self.manifest
        if m.get("schema") != SCHEMA:
            raise CorpusError(
                "MalformedCorpus", f"unexpected manifest schema {m.get('schema')!r}"
            )
        binary = m.get("binary_contract")
        if binary != {"double_bytes": 8, "iec559": True, "little_endian": True}:
            raise CorpusError(
                "MalformedCorpus", "binary contract is not IEEE-754 little-endian f64"
            )
        assembly = m.get("assembly", {})
        expected_map = (
            "values at global value index; gradients at "
            "source_value_rows + 3*global_gradient_index + component"
        )
        if assembly.get("row_channel_map") != expected_map:
            raise CorpusError(
                "MalformedCorpus", "canonical global row map is not frozen"
            )

        self.artifacts = self._unique(m.get("artifacts"), "artifact_id", "artifacts")
        self.workloads = self._unique(m.get("workloads"), "workload_id", "workloads")
        self.blocks = self._unique(m.get("blocks"), "block_id", "blocks")
        self.factor_sources = self._unique(
            m.get("factor_sources"), "factor_source_id", "factor_sources"
        )
        self._validate_counts()
        self._validate_exclusions()
        self._validate_assertions()
        self._load_immutable_lock()
        self._lock_artifacts()
        self._validate_references()

    def _validate_counts(self) -> None:
        counts = self.manifest.get("counts")
        if not isinstance(counts, dict):
            raise CorpusError("MalformedCorpus", "counts object is missing")
        actual = {
            "artifacts": len(self.artifacts),
            "workloads": len(self.workloads),
            "blocks": len(self.blocks),
            "fine_blocks": sum(
                block.get("role") == "fine" for block in self.blocks.values()
            ),
            "coarse_blocks": sum(
                block.get("role") == "coarse" for block in self.blocks.values()
            ),
            "factor_sources": len(self.factor_sources),
            "qtaq_factor_sources": sum(
                factor.get("matrix_role") == "qtaq"
                for factor in self.factor_sources.values()
            ),
            "p_top_factor_sources": sum(
                factor.get("matrix_role") == "p_top"
                for factor in self.factor_sources.values()
            ),
            "auxiliary_decomposition_sources": len(
                self.manifest.get("auxiliary_decomposition_sources", [])
            ),
            "controls": len(self.manifest.get("controls", [])),
        }
        for key, value in actual.items():
            if counts.get(key) != value:
                raise CorpusError(
                    "MalformedCorpus",
                    f"counts.{key} is {counts.get(key)!r}, actual is {value}",
                )
        if self.production:
            inventory_profile = self.manifest.get("inventory_profile")
            if (
                not isinstance(inventory_profile, dict)
                or inventory_profile.get("profile_id")
                != self.expected_inventory["capture_inventory_profile_id"]
                or inventory_profile.get("expected") != counts
            ):
                raise CorpusError(
                    "MalformedCorpus", "capture inventory profile does not bind counts"
                )
            expected = {
                "workloads": self.expected_inventory["workload_count"],
                "blocks": self.expected_inventory["block_count"],
                "fine_blocks": self.expected_inventory["fine_block_count"],
                "coarse_blocks": self.expected_inventory["coarse_block_count"],
                "factor_sources": self.expected_inventory[
                    "carried_factor_source_count"
                ],
                "qtaq_factor_sources": self.expected_inventory[
                    "qtaq_factor_source_count"
                ],
                "p_top_factor_sources": self.expected_inventory[
                    "p_top_factor_source_count"
                ],
                "auxiliary_decomposition_sources": self.expected_inventory[
                    "generator_auxiliary_p_top_count"
                ],
                "controls": self.expected_inventory["control_count"],
            }
            if "artifact_count" in self.expected_inventory:
                expected["artifacts"] = self.expected_inventory["artifact_count"]
            for key, value in expected.items():
                if actual[key] != value:
                    raise CorpusError(
                        "MalformedCorpus",
                        f"canonical inventory requires {key}={value}, got {actual[key]}",
                    )

    def _validate_exclusions(self) -> None:
        exclusions = self.manifest.get("exclusions")
        if not isinstance(exclusions, list):
            raise CorpusError("MalformedCorpus", "exclusions must be an array")
        identifiers = {
            item.get("record_id") for item in exclusions if isinstance(item, dict)
        }
        expected = (
            EXPECTED_EXCLUSIONS | {GENERATOR_EXCLUSION}
            if self.production
            else EXPECTED_EXCLUSIONS
        )
        if identifiers != expected:
            raise CorpusError(
                "MalformedCorpus", "frozen-literal M3 exclusion set drifted"
            )
        active_ids = set(self.blocks) | set(self.factor_sources) | set(self.artifacts)
        if any("frozen-literal" in identifier for identifier in active_ids):
            raise CorpusError(
                "MalformedCorpus", "excluded M3 literal leaked into active corpus"
            )

    def _validate_assertions(self) -> None:
        assertions = self.manifest.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise CorpusError("MalformedCorpus", "capture assertions are missing")
        for assertion in assertions:
            if not isinstance(assertion, dict) or assertion.get("passed") is not True:
                raise CorpusError(
                    "MalformedCorpus", "a raw-capture assertion did not pass"
                )
            if assertion.get("expected") != assertion.get("actual"):
                raise CorpusError("MalformedCorpus", "assertion values disagree")

    def _load_immutable_lock(self) -> None:
        lock_path = self.root / "manifest.lock.json"
        if not lock_path.exists():
            if self.production:
                raise CorpusError(
                    "IntegrityMismatch", "production corpus lacks manifest.lock.json"
                )
            return
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CorpusError(
                "IntegrityMismatch", f"cannot read immutable lock: {exc}"
            ) from exc
        if (
            not isinstance(lock, dict)
            or lock.get("schema") != "rapidrbf-canonical-hierarchy-corpus-lock-v3"
            or lock.get("hash_algorithm") != "sha256"
            or lock.get("capture_schema") != SCHEMA
        ):
            raise CorpusError("IntegrityMismatch", "immutable lock schema drifted")
        declared_corpus = lock.get("corpus_sha256")
        body = dict(lock)
        body.pop("corpus_sha256", None)
        actual_corpus = sha256_bytes(canonical_json(body))
        if declared_corpus != actual_corpus:
            raise CorpusError("IntegrityMismatch", "corpus lock body hash mismatch")
        raw = lock.get("raw_manifest")
        if (
            not isinstance(raw, dict)
            or raw.get("path") != self.path.name
            or raw.get("bytes") != len(self.raw_manifest)
            or raw.get("sha256") != sha256_bytes(self.raw_manifest)
        ):
            raise CorpusError(
                "IntegrityMismatch", "raw manifest does not match corpus lock"
            )
        if lock.get("counts") != self.manifest.get("counts"):
            raise CorpusError(
                "IntegrityMismatch", "locked inventory differs from raw manifest"
            )
        locked_artifacts = lock.get("artifacts")
        if not isinstance(locked_artifacts, dict) or set(locked_artifacts) != set(
            self.artifacts
        ):
            raise CorpusError("IntegrityMismatch", "locked artifact inventory drifted")
        self.lock = lock
        self.corpus_sha256 = actual_corpus

    def _lock_artifacts(self) -> None:
        dtype_size = {"f64": 8, "i64": 8, "u8": 1}
        root = self.root.resolve()
        for identifier, artifact in self.artifacts.items():
            dtype = artifact.get("dtype")
            shape = artifact.get("shape")
            encoding = artifact.get("encoding")
            if dtype not in dtype_size or not isinstance(shape, list):
                raise CorpusError(
                    "MalformedCorpus", f"invalid metadata for {identifier}"
                )
            if any(not isinstance(item, int) or item < 0 for item in shape):
                raise CorpusError("MalformedCorpus", f"invalid shape for {identifier}")
            logical = math.prod(shape)
            if encoding == "lower-triangle-row-major-packed":
                if len(shape) != 2 or shape[0] != shape[1]:
                    raise CorpusError(
                        "MalformedCorpus", f"invalid packed shape for {identifier}"
                    )
                expected_stored = shape[0] * (shape[0] + 1) // 2
            else:
                expected_stored = logical
            if artifact.get("stored_elements") != expected_stored:
                raise CorpusError(
                    "MalformedCorpus", f"stored element count drift for {identifier}"
                )
            expected_bytes = expected_stored * dtype_size[dtype]
            if artifact.get("bytes") != expected_bytes:
                raise CorpusError(
                    "MalformedCorpus", f"byte count drift for {identifier}"
                )
            if dtype == "u8":
                expected_order = "not-applicable"
            else:
                expected_order = "little"
            if artifact.get("byte_order") != expected_order:
                raise CorpusError(
                    "MalformedCorpus", f"byte order drift for {identifier}"
                )
            relative_text = artifact.get("path")
            if not isinstance(relative_text, str):
                raise CorpusError("MalformedCorpus", f"path missing for {identifier}")
            pure = PurePosixPath(relative_text)
            if pure.is_absolute() or ".." in pure.parts:
                raise CorpusError(
                    "MalformedCorpus", f"unsafe artifact path for {identifier}"
                )
            path = (root / Path(*pure.parts)).resolve()
            try:
                path.relative_to(root)
                size = path.stat().st_size
            except (ValueError, OSError) as exc:
                raise CorpusError(
                    "IntegrityMismatch", f"cannot materialize {identifier}: {exc}"
                ) from exc
            if size != expected_bytes:
                raise CorpusError(
                    "IntegrityMismatch",
                    f"{identifier} expected {expected_bytes} bytes, got {size}",
                )
            digest_state = hashlib.sha256()
            try:
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest_state.update(chunk)
            except OSError as exc:
                raise CorpusError(
                    "IntegrityMismatch", f"cannot hash {identifier}: {exc}"
                ) from exc
            digest = digest_state.hexdigest()
            locked = self.lock["artifacts"][identifier] if self.lock else None
            if locked is not None:
                for key in (
                    "bytes",
                    "dtype",
                    "encoding",
                    "owner_id",
                    "owner_kind",
                    "path",
                    "role",
                    "shape",
                ):
                    if locked.get(key) != artifact.get(key):
                        raise CorpusError(
                            "IntegrityMismatch",
                            f"locked metadata mismatch for {identifier}/{key}",
                        )
            declared = locked.get("sha256") if locked else artifact.get("sha256")
            if declared is not None and declared != digest:
                raise CorpusError(
                    "IntegrityMismatch", f"sha256 mismatch for {identifier}"
                )
            self.artifact_paths[identifier] = path
            self.artifact_digests[identifier] = digest
            self.artifact_locks.append(
                {
                    "artifact_id": identifier,
                    "path": relative_text,
                    "bytes": size,
                    "sha256": digest,
                }
            )

    def _validate_references(self) -> None:
        for workload_id, workload in self.workloads.items():
            refs = workload.get("artifacts")
            if not isinstance(refs, dict) or set(refs) != EXPECTED_WORKLOAD_ARTIFACTS:
                raise CorpusError(
                    "MalformedCorpus", f"workload artifact set drift for {workload_id}"
                )
            for role, identifier in refs.items():
                artifact = self.artifacts.get(identifier)
                if (
                    artifact is None
                    or artifact.get("owner_kind") != "workload"
                    or artifact.get("owner_id") != workload_id
                    or artifact.get("role") != role
                ):
                    raise CorpusError(
                        "MalformedCorpus", f"bad {role} reference for {workload_id}"
                    )
            value_rows = workload.get("value_rows")
            gradient_points = workload.get("gradient_points")
            polynomial_order = workload.get("polynomial_order")
            degree = workload.get("resolved_polynomial_degree")
            if (
                not all(
                    isinstance(item, int) and item >= 0
                    for item in (value_rows, gradient_points, polynomial_order)
                )
                or degree not in (0, 1)
                or polynomial_order != (1 if degree == 0 else 4)
                or workload.get("scalar_order") != value_rows + 3 * gradient_points
            ):
                raise CorpusError(
                    "MalformedCorpus", f"workload dimensions drift for {workload_id}"
                )
            self._require_artifact_contract(
                refs["value_points"], "f64", [value_rows, 3], "row-major"
            )
            self._require_artifact_contract(
                refs["gradient_points"],
                "f64",
                [gradient_points, 3],
                "row-major",
            )
            self._require_artifact_contract(
                refs["observations"],
                "f64",
                [workload["scalar_order"]],
                "contiguous",
            )
            self._require_artifact_contract(
                refs["selected_polynomial_indices"],
                "i64",
                [polynomial_order],
                "contiguous",
            )
            model = workload.get("model")
            model_artifact_id = (
                model.get("exact_values_artifact") if isinstance(model, dict) else None
            )
            if self.production:
                model_artifact = self.artifacts.get(model_artifact_id)
                if (
                    model_artifact is None
                    or model_artifact.get("owner_kind") != "workload"
                    or model_artifact.get("owner_id") != workload_id
                    or model_artifact.get("role") != "model_values"
                ):
                    raise CorpusError(
                        "MalformedCorpus",
                        f"bad model_values reference for {workload_id}",
                    )
                if (
                    len(model_artifact.get("shape", [])) != 1
                    or model_artifact.get("dtype") != "f64"
                    or model_artifact.get("encoding") != "contiguous"
                ):
                    raise CorpusError(
                        "MalformedCorpus",
                        f"model_values shape contract drift for {workload_id}",
                    )

        coarse_by_workload: dict[str, int] = {
            identifier: 0 for identifier in self.workloads
        }
        for block_id, block in self.blocks.items():
            workload_id = block.get("workload_id")
            if workload_id not in self.workloads or block.get("role") not in {
                "fine",
                "coarse",
            }:
                raise CorpusError(
                    "MalformedCorpus", f"invalid block lineage for {block_id}"
                )
            refs = block.get("artifacts")
            expected = set(EXPECTED_BLOCK_ARTIFACTS)
            if self.production:
                expected |= REFERENCE_BLOCK_ARTIFACTS
            if block.get("role") == "coarse":
                expected.add("p_top_row_major")
                if self.production:
                    expected.add("reference_c")
                coarse_by_workload[workload_id] += 1
            if not isinstance(refs, dict) or set(refs) != expected:
                raise CorpusError(
                    "MalformedCorpus", f"block artifact set drift for {block_id}"
                )
            for role, identifier in refs.items():
                artifact = self.artifacts.get(identifier)
                if (
                    artifact is None
                    or artifact.get("owner_kind") != "block"
                    or artifact.get("owner_id") != block_id
                    or artifact.get("role") != role
                ):
                    raise CorpusError(
                        "MalformedCorpus", f"bad {role} reference for {block_id}"
                    )
            if block.get("row_channel_map") != "canonical-global-value-offset-v1":
                raise CorpusError("MalformedCorpus", f"row map drift for {block_id}")
            self._validate_block_artifact_contract(block_id, block)
        if any(value != 1 for value in coarse_by_workload.values()):
            raise CorpusError(
                "MalformedCorpus", "each workload must have exactly one coarse block"
            )

        qtaq_blocks: set[str] = set()
        ptop_blocks: set[str] = set()
        for factor_id, factor in self.factor_sources.items():
            block_id = factor.get("block_id")
            block = self.blocks.get(block_id)
            if block is None or factor.get("workload_id") != block.get("workload_id"):
                raise CorpusError(
                    "MalformedCorpus", f"invalid factor lineage for {factor_id}"
                )
            role = factor.get("matrix_role")
            artifact_id = factor.get("matrix_artifact")
            expected_role = "qtaq_lower" if role == "qtaq" else "p_top_row_major"
            if role not in {"qtaq", "p_top"}:
                raise CorpusError(
                    "MalformedCorpus", f"unknown factor role for {factor_id}"
                )
            if artifact_id != block["artifacts"].get(expected_role):
                raise CorpusError(
                    "MalformedCorpus", f"factor artifact drift for {factor_id}"
                )
            if (
                factor.get("semantic_admission")
                != "certificate-required-before-backend-selection"
            ):
                raise CorpusError(
                    "MalformedCorpus", f"factor admission marker drift for {factor_id}"
                )
            if role == "qtaq":
                if factor.get("expected_rank") != block.get("reduced_order"):
                    raise CorpusError(
                        "MalformedCorpus", f"QTAQ expected rank drift for {factor_id}"
                    )
                if block_id in qtaq_blocks:
                    raise CorpusError(
                        "MalformedCorpus", f"duplicate QTAQ factor for {block_id}"
                    )
                qtaq_blocks.add(block_id)
            else:
                if factor.get("expected_rank") != block.get("polynomial_order"):
                    raise CorpusError(
                        "MalformedCorpus", f"P_top expected rank drift for {factor_id}"
                    )
                if block.get("role") != "coarse" or block_id in ptop_blocks:
                    raise CorpusError(
                        "MalformedCorpus", f"P_top is not coarse-only for {factor_id}"
                    )
                ptop_blocks.add(block_id)
        if qtaq_blocks != set(self.blocks):
            raise CorpusError(
                "MalformedCorpus", "every block must have one QTAQ factor source"
            )
        expected_ptop = {
            identifier
            for identifier, block in self.blocks.items()
            if block["role"] == "coarse"
        }
        if ptop_blocks != expected_ptop:
            raise CorpusError(
                "MalformedCorpus", "coarse-only P_top factor inventory drifted"
            )

        if self.production:
            self._validate_lineage_and_auxiliary(expected_ptop)
            for workload_id, workload in self.workloads.items():
                block_records = [
                    block
                    for block in self.blocks.values()
                    if block["workload_id"] == workload_id
                ]
                scale_id = workload.get("scale_id")
                if scale_id == "1k":
                    expected_total = self.expected_inventory["blocks_per_1k_workload"]
                    expected_fine = self.expected_inventory[
                        "fine_blocks_per_1k_workload"
                    ]
                elif scale_id == "10k":
                    expected_total = self.expected_inventory["blocks_per_10k_workload"]
                    expected_fine = self.expected_inventory[
                        "fine_blocks_per_10k_workload"
                    ]
                else:
                    raise CorpusError(
                        "MalformedCorpus", f"unknown hierarchy scale for {workload_id}"
                    )
                if (
                    len(block_records) != expected_total
                    or sum(block["role"] == "fine" for block in block_records)
                    != expected_fine
                ):
                    raise CorpusError(
                        "MalformedCorpus",
                        f"hierarchy inventory drift for {workload_id}",
                    )

    def _validate_lineage_and_auxiliary(self, coarse_blocks: set[str]) -> None:
        witness = self.manifest.get("witness_contract")
        if (
            not isinstance(witness, dict)
            or witness.get("authority") != "untrusted-witness-only"
            or set(witness.get("per_block", [])) != REFERENCE_BLOCK_ARTIFACTS
            or witness.get("coarse_only") != ["reference_c"]
            or witness.get("fine_reference_c") != "prohibited-and-absent"
        ):
            raise CorpusError("MalformedCorpus", "untrusted witness contract drifted")

        controls = self.manifest.get("controls")
        expected_controls = set(self.expected_inventory["m4_control_ids"])
        if (
            not isinstance(controls, list)
            or {item.get("control_id") for item in controls} != expected_controls
        ):
            raise CorpusError("MalformedCorpus", "M4 control lineage drifted")
        for control in controls:
            control_id = control["control_id"]
            base = control.get("base_fixture")
            mutation = control.get("mutation")
            if (
                control.get("control_kind") != "rank-invalid-negative"
                or control.get("expected_disposition") != "RankDeficient"
                or control.get("admission_phase") != "pre-backend"
                or control.get("backend_calls") != 0
                or control.get("workload_count_contribution") != 0
                or control.get("block_count_contribution") != 0
                or control.get("factor_source_count_contribution") != 0
                or not isinstance(base, dict)
                or not isinstance(mutation, dict)
            ):
                raise CorpusError(
                    "MalformedCorpus", f"control contract drift for {control_id}"
                )
            workload = self.workloads.get(base.get("workload_id"))
            if (
                workload is None
                or workload.get("fixture_id") != base.get("fixture_id")
                or base.get("coordinate_artifact")
                != workload["artifacts"]["value_points"]
                or base.get("hash_binding") != "required immutable-lock entry"
                or mutation.get("recipe")
                != (
                    "copy the source coordinate row bit-for-bit over the "
                    "destination coordinate row"
                )
            ):
                raise CorpusError(
                    "MalformedCorpus", f"control base/mutation drift for {control_id}"
                )
            destination = mutation.get("destination_row")
            source = mutation.get("source_row")
            if (
                not isinstance(destination, int)
                or not isinstance(source, int)
                or destination == source
                or not 0 <= destination < workload["value_rows"]
                or not 0 <= source < workload["value_rows"]
            ):
                raise CorpusError(
                    "MalformedCorpus", f"control row indices drift for {control_id}"
                )
            recipe_artifact_id = mutation.get("recipe_artifact")
            mutated_artifact_id = mutation.get("mutated_coordinate_artifact")
            for artifact_id, role in (
                (recipe_artifact_id, "duplicate_coordinate_mutation"),
                (mutated_artifact_id, "mutated_value_points"),
            ):
                artifact = self.artifacts.get(artifact_id)
                if (
                    artifact is None
                    or artifact.get("owner_kind") != "control"
                    or artifact.get("owner_id") != control_id
                    or artifact.get("role") != role
                ):
                    raise CorpusError(
                        "MalformedCorpus",
                        f"control artifact lineage drift for {control_id}/{role}",
                    )
            self._require_artifact_contract(
                recipe_artifact_id, "i64", [2], "contiguous"
            )
            self._require_artifact_contract(
                mutated_artifact_id,
                "f64",
                [workload["value_rows"], 3],
                "row-major",
            )
        lineage = self.manifest.get("lineage", {}).get("m4_positive_selection", {})
        selected = {
            (item.get("case_id"), item.get("fixture_id"))
            for item in lineage.get("selected_fixtures", [])
        }
        expected_selected = {
            (workload.get("case_id"), workload.get("fixture_id"))
            for workload in self.workloads.values()
            if workload.get("panel_id") == "M4-GEOMETRY-FAILURE"
        }
        if selected != expected_selected:
            raise CorpusError(
                "MalformedCorpus", "M4 positive-selection lineage drifted"
            )

        auxiliary = self.manifest.get("auxiliary_decomposition_sources")
        if not isinstance(auxiliary, list) or len(auxiliary) != len(self.workloads):
            raise CorpusError(
                "MalformedCorpus", "auxiliary decomposition inventory drifted"
            )
        seen_workloads: set[str] = set()
        for source in auxiliary:
            workload_id = source.get("workload_id")
            coarse = next(
                (
                    block
                    for block_id, block in self.blocks.items()
                    if block_id in coarse_blocks and block["workload_id"] == workload_id
                ),
                None,
            )
            if (
                workload_id in seen_workloads
                or coarse is None
                or source.get("matrix_artifact")
                != coarse["artifacts"]["p_top_row_major"]
                or source.get("classification") != "non-carried-generator-auxiliary"
                or source.get("issue_38_handoff") is not False
            ):
                raise CorpusError(
                    "MalformedCorpus", "invalid auxiliary decomposition lineage"
                )
            seen_workloads.add(workload_id)

    def _require_artifact_contract(
        self,
        artifact_id: str,
        dtype: str,
        shape: Sequence[int],
        encoding: str,
    ) -> None:
        artifact = self.artifacts[artifact_id]
        if (
            artifact.get("dtype") != dtype
            or artifact.get("shape") != list(shape)
            or artifact.get("encoding") != encoding
        ):
            raise CorpusError(
                "MalformedCorpus", f"artifact contract drift for {artifact_id}"
            )

    def _validate_block_artifact_contract(
        self, block_id: str, block: Mapping[str, Any]
    ) -> None:
        workload = self.workloads[block["workload_id"]]
        value_rows = block.get("value_rows")
        gradient_points = block.get("gradient_points")
        scalar_order = block.get("scalar_order")
        polynomial_order = block.get("polynomial_order")
        reduced_order = block.get("reduced_order")
        inner_value_rows = block.get("inner_value_rows")
        inner_gradient_points = block.get("inner_gradient_points")
        if (
            not all(
                isinstance(item, int) and item >= 0
                for item in (
                    value_rows,
                    gradient_points,
                    scalar_order,
                    polynomial_order,
                    reduced_order,
                    inner_value_rows,
                    inner_gradient_points,
                )
            )
            or scalar_order != value_rows + 3 * gradient_points
            or reduced_order != scalar_order - polynomial_order
            or block.get("source_value_rows") != workload.get("value_rows")
            or block.get("source_gradient_points") != workload.get("gradient_points")
            or inner_value_rows > value_rows
            or inner_gradient_points > gradient_points
        ):
            raise CorpusError(
                "MalformedCorpus", f"block dimensions drift for {block_id}"
            )
        refs = block["artifacts"]
        contracts = {
            "domain_value_indices": ("i64", [value_rows], "contiguous"),
            "domain_gradient_indices": ("i64", [gradient_points], "contiguous"),
            "inner_value_mask": (
                "u8",
                [value_rows],
                "boolean-mask" if self.production else "contiguous",
            ),
            "inner_gradient_mask": (
                "u8",
                [gradient_points],
                "boolean-mask" if self.production else "contiguous",
            ),
            "canonical_lagrange_flat_indices": (
                "i64",
                [scalar_order],
                "contiguous",
            ),
            "a_lower": (
                "f64",
                [scalar_order, scalar_order],
                "lower-triangle-row-major-packed",
            ),
            "p_row_major": (
                "f64",
                [scalar_order, polynomial_order],
                "row-major",
            ),
            "q_top_row_major": (
                "f64",
                [polynomial_order, reduced_order],
                "row-major",
            ),
            "qtaq_lower": (
                "f64",
                [reduced_order, reduced_order],
                "lower-triangle-row-major-packed",
            ),
            "rhs_full": ("f64", [scalar_order], "contiguous"),
            "rhs_reduced": ("f64", [reduced_order], "contiguous"),
        }
        if self.production:
            contracts.update(
                {
                    "reference_gamma": (
                        "f64",
                        [reduced_order],
                        "contiguous",
                    ),
                    "reference_lambda": (
                        "f64",
                        [scalar_order],
                        "contiguous",
                    ),
                }
            )
        if block["role"] == "coarse":
            contracts["p_top_row_major"] = (
                "f64",
                [polynomial_order, polynomial_order],
                "row-major",
            )
            if self.production:
                contracts["reference_c"] = (
                    "f64",
                    [polynomial_order],
                    "contiguous",
                )
        for role, (dtype, shape, encoding) in contracts.items():
            self._require_artifact_contract(refs[role], dtype, shape, encoding)

    def array(self, artifact_id: str) -> np.ndarray:
        artifact = self.artifacts[artifact_id]
        dtype = {"f64": "<f8", "i64": "<i8", "u8": "u1"}[artifact["dtype"]]
        try:
            payload = self.artifact_paths[artifact_id].read_bytes()
        except OSError as exc:
            raise CorpusError(
                "IntegrityMismatch", f"cannot reload {artifact_id}: {exc}"
            ) from exc
        if sha256_bytes(payload) != self.artifact_digests[artifact_id]:
            raise CorpusError(
                "IntegrityMismatch",
                f"{artifact_id} changed after immutable-lock validation",
            )
        vector = np.frombuffer(payload, dtype=dtype)
        shape = tuple(artifact["shape"])
        if artifact["encoding"] == "lower-triangle-row-major-packed":
            n = shape[0]
            matrix = np.empty((n, n), dtype=np.float64)
            cursor = 0
            for row in range(n):
                count = row + 1
                matrix[row, :count] = vector[cursor : cursor + count]
                matrix[:count, row] = vector[cursor : cursor + count]
                cursor += count
            return matrix
        return vector.reshape(shape).copy()


def _aggregate_state(states: Iterable[str]) -> str:
    state_set = set(states)
    if state_set == {"Admitted"} or not state_set:
        return "Admitted"
    for state in FAILURE_ORDER:
        if state in state_set:
            return state
    return "EVIDENCE_MISSING"


def _validate_indices(values: np.ndarray, upper_bound: int, label: str) -> np.ndarray:
    values = np.asarray(values)
    if (
        values.ndim != 1
        or values.dtype.kind != "i"
        or np.any(values < 0)
        or np.any(values >= upper_bound)
        or len(np.unique(values)) != values.size
    ):
        raise CorpusError(
            "MalformedCorpus", f"{label} is not a unique in-range index vector"
        )
    return values


def _validate_boolean_mask(values: np.ndarray, expected_true: int, label: str) -> None:
    values = np.asarray(values)
    if (
        values.ndim != 1
        or not np.all((values == 0) | (values == 1))
        or int(np.sum(values, dtype=np.int64)) != expected_true
    ):
        raise CorpusError("MalformedCorpus", f"{label} boolean/count contract drifted")


def certify_materialized_controls(corpus: Corpus) -> list[dict[str, Any]]:
    certificates: list[dict[str, Any]] = []
    for control in corpus.manifest.get("controls", []):
        control_id = control["control_id"]
        base = control["base_fixture"]
        mutation = control["mutation"]
        base_points = corpus.array(base["coordinate_artifact"])
        mutated_points = corpus.array(mutation["mutated_coordinate_artifact"])
        recipe = corpus.array(mutation["recipe_artifact"])
        workload = corpus.workloads[base["workload_id"]]
        selected_artifact = workload["artifacts"]["selected_polynomial_indices"]
        model_artifact = workload["model"]["exact_values_artifact"]
        model_values = corpus.array(model_artifact)
        selected_polynomial_indices = _validate_indices(
            corpus.array(selected_artifact),
            int(workload["value_rows"]),
            f"{control_id}/selected_polynomial_indices",
        )
        destination = int(mutation["destination_row"])
        source = int(mutation["source_row"])
        certificate = {
            "certificate_id": f"control:{control_id}",
            "control_id": control_id,
            "subject": "projected-duplicate-coordinate-tail-direction",
            "expected_disposition": "RankDeficient",
            "backend_invocations": 0,
            "source_artifacts": [
                base["coordinate_artifact"],
                mutation["recipe_artifact"],
                mutation["mutated_coordinate_artifact"],
                selected_artifact,
                model_artifact,
            ],
        }
        if not np.all(np.isfinite(base_points)) or not np.all(
            np.isfinite(mutated_points)
        ):
            certificates.append(
                {
                    **certificate,
                    "state": "NonFinite",
                    "reason": "materialized control coordinates are non-finite",
                }
            )
            continue
        expected_recipe = np.array([destination, source], dtype=np.int64)
        expected_mutated = base_points.copy()
        expected_mutated[destination, :] = base_points[source, :]
        originally_distinct = not np.array_equal(
            base_points[destination, :].view(np.uint64),
            base_points[source, :].view(np.uint64),
        )
        recipe_matches = np.array_equal(recipe, expected_recipe)
        mutation_matches = np.array_equal(
            mutated_points.view(np.uint64), expected_mutated.view(np.uint64)
        )
        duplicate_is_exact = np.array_equal(
            mutated_points[destination, :].view(np.uint64),
            mutated_points[source, :].view(np.uint64),
        )
        anchors = set(map(int, selected_polynomial_indices))
        rows_are_non_polynomial_anchors = (
            destination not in anchors and source not in anchors
        )
        zero_nugget_ordinary_value_control = bool(
            int(workload["gradient_points"]) == 0
            and model_values.size > 0
            and model_values[0].view(np.uint64) == np.float64(0.0).view(np.uint64)
        )
        matched = (
            originally_distinct
            and recipe_matches
            and mutation_matches
            and duplicate_is_exact
            and rows_are_non_polynomial_anchors
            and zero_nugget_ordinary_value_control
        )
        certificates.append(
            {
                **certificate,
                "state": "Admitted" if matched else "IntegrityMismatch",
                "reason": (
                    None
                    if matched
                    else "materialized duplicate-row control does not match its recipe"
                ),
                "observed_disposition": (
                    "RankDeficient" if matched else "IntegrityMismatch"
                ),
                "authority": "exact-binary64-duplicate-coordinate-rank-control",
                "proof": (
                    "the exact difference of the duplicate non-anchor value rows "
                    "is a nonzero polynomial-nullspace tail direction annihilated "
                    "by the zero-nugget duplicate-row kernel and projected operator"
                ),
                "ratio_envelope": {
                    "lower": 0.0,
                    "lower_binary64_hex": (0.0).hex(),
                    "upper": 0.0,
                    "upper_binary64_hex": (0.0).hex(),
                },
                "checks": {
                    "base_rows_originally_distinct": originally_distinct,
                    "recipe_artifact_matches": recipe_matches,
                    "only_declared_row_mutated": mutation_matches,
                    "duplicate_row_bit_exact": duplicate_is_exact,
                    "source_and_destination_are_non_polynomial_anchors": (
                        rows_are_non_polynomial_anchors
                    ),
                    "selected_polynomial_indices": sorted(anchors),
                    "ordinary_values_and_exact_zero_nugget": (
                        zero_nugget_ordinary_value_control
                    ),
                },
            }
        )
    return certificates


def certify_corpus(
    manifest_path: Path,
    profile: Mapping[str, Any],
    *,
    production: bool = True,
    max_resource_units: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    profile = validate_profile(profile)
    corpus = Corpus(
        manifest_path,
        production=production,
        inventory=profile["inventory"] if production else None,
    )
    rank_subjects: list[tuple[str, str, Sequence[int]]] = []
    for block_id, block in sorted(corpus.blocks.items()):
        refs = block["artifacts"]
        rank_subjects.extend(
            (
                (
                    f"rank:{block_id}:P",
                    "P",
                    corpus.artifacts[refs["p_row_major"]]["shape"],
                ),
                (
                    f"rank:{block_id}:QTAQ",
                    "QTAQ",
                    corpus.artifacts[refs["qtaq_lower"]]["shape"],
                ),
            )
        )
        if block["role"] == "coarse":
            rank_subjects.append(
                (
                    f"rank:{block_id}:P_TOP",
                    "P_TOP",
                    corpus.artifacts[refs["p_top_row_major"]]["shape"],
                )
            )
    preflight_rank_subjects(rank_subjects, max_resource_units)

    rank_certificates: list[dict[str, Any]] = []
    q_certificates: list[dict[str, Any]] = []
    control_certificates = certify_materialized_controls(corpus) if production else []

    for workload_id in sorted(corpus.workloads):
        if progress:
            progress(f"workload {workload_id}: validating coordinates")
        workload = corpus.workloads[workload_id]
        value_points = corpus.array(workload["artifacts"]["value_points"])
        gradient_points = corpus.array(workload["artifacts"]["gradient_points"])
        _validate_indices(
            corpus.array(workload["artifacts"]["selected_polynomial_indices"]),
            int(workload["value_rows"]),
            f"{workload_id}/selected_polynomial_indices",
        )
        transform = coordinate_transform(value_points, gradient_points)
        degree = int(workload.get("resolved_polynomial_degree"))
        workload_blocks = sorted(
            (
                block
                for block in corpus.blocks.values()
                if block["workload_id"] == workload_id
            ),
            key=lambda item: item["block_id"],
        )
        for block in workload_blocks:
            block_id = block["block_id"]
            if progress:
                progress(f"block {block_id}: certifying")
            refs = block["artifacts"]
            value_indices = _validate_indices(
                corpus.array(refs["domain_value_indices"]),
                int(workload["value_rows"]),
                f"{block_id}/domain_value_indices",
            )
            gradient_indices = _validate_indices(
                corpus.array(refs["domain_gradient_indices"]),
                int(workload["gradient_points"]),
                f"{block_id}/domain_gradient_indices",
            )
            _validate_boolean_mask(
                corpus.array(refs["inner_value_mask"]),
                int(block["inner_value_rows"]),
                f"{block_id}/inner_value_mask",
            )
            _validate_boolean_mask(
                corpus.array(refs["inner_gradient_mask"]),
                int(block["inner_gradient_points"]),
                f"{block_id}/inner_gradient_mask",
            )
            local_values = value_points[value_indices]
            local_gradients = gradient_points[gradient_indices]
            physical_p = build_polynomial_matrix(
                degree, local_values, local_gradients, None
            )
            captured_p = corpus.array(refs["p_row_major"])
            try:
                _require_exact_f64(captured_p, physical_p, f"{block_id}/P")
                scaled_p = build_polynomial_matrix(
                    degree, local_values, local_gradients, transform
                )
                p_certificate = rank_certificate(
                    f"rank:{block_id}:P",
                    "P",
                    scaled_p,
                    profile,
                    max_resource_units=max_resource_units,
                )
                p_certificate["source_artifact"] = refs["p_row_major"]
                p_certificate["coordinate_transform"] = {
                    "profile": profile["coordinate_scaling"]["profile"],
                    "center_exact": transform["center_exact"],
                    "scale_exact": transform["scale_exact"],
                    "center_hex": transform["center_hex"],
                    "scale_hex": transform["scale_hex"],
                }
            except CorpusError as exc:
                p_certificate = {
                    "certificate_id": f"rank:{block_id}:P",
                    "subject": "P",
                    "source_artifact": refs["p_row_major"],
                    "state": exc.state,
                    "reason": exc.reason,
                    "backend_invocations": 0,
                }
            rank_certificates.append(p_certificate)

            qtaq = corpus.array(refs["qtaq_lower"])
            qtaq_certificate = rank_certificate(
                f"rank:{block_id}:QTAQ",
                "QTAQ",
                qtaq,
                profile,
                max_resource_units=max_resource_units,
            )
            qtaq_certificate["source_artifact"] = refs["qtaq_lower"]
            qtaq_certificate["coordinate_scaling"] = "not-applied-to-kernel-semantics"
            rank_certificates.append(qtaq_certificate)

            if block["role"] == "coarse":
                captured_ptop = corpus.array(refs["p_top_row_major"])
                expected_physical_ptop = physical_p[: physical_p.shape[1], :]
                try:
                    _require_exact_f64(
                        captured_ptop,
                        expected_physical_ptop,
                        f"{block_id}/P_top",
                    )
                    scaled_ptop = scaled_p[: scaled_p.shape[1], :]
                    ptop_certificate = rank_certificate(
                        f"rank:{block_id}:P_TOP",
                        "P_TOP",
                        scaled_ptop,
                        profile,
                        max_resource_units=max_resource_units,
                    )
                    ptop_certificate["source_artifact"] = refs["p_top_row_major"]
                    ptop_certificate["coordinate_transform"] = {
                        "profile": profile["coordinate_scaling"]["profile"],
                        "center_exact": transform["center_exact"],
                        "scale_exact": transform["scale_exact"],
                        "center_hex": transform["center_hex"],
                        "scale_hex": transform["scale_hex"],
                    }
                except CorpusError as exc:
                    ptop_certificate = {
                        "certificate_id": f"rank:{block_id}:P_TOP",
                        "subject": "P_TOP",
                        "source_artifact": refs["p_top_row_major"],
                        "state": exc.state,
                        "reason": exc.reason,
                        "backend_invocations": 0,
                    }
                rank_certificates.append(ptop_certificate)

            q_certificates.append(
                q_nullspace_certificate(
                    block_id,
                    captured_p,
                    corpus.array(refs["q_top_row_major"]),
                    corpus.array(refs["canonical_lagrange_flat_indices"]),
                    value_indices,
                    gradient_indices,
                    int(block["source_value_rows"]),
                )
            )
            if progress:
                progress(
                    f"block {block_id}: "
                    f"P={p_certificate['state']} "
                    f"QTAQ={qtaq_certificate['state']} "
                    f"Q={q_certificates[-1]['state']}"
                )

    expected_rank = (
        int(profile["inventory"]["rank_certificate_count"])
        if production
        else len(corpus.blocks) * 2
        + sum(block["role"] == "coarse" for block in corpus.blocks.values())
    )
    expected_q = (
        int(profile["inventory"]["q_certificate_count"])
        if production
        else len(corpus.blocks)
    )
    if len(rank_certificates) != expected_rank or len(q_certificates) != expected_q:
        raise CorpusError("MalformedCorpus", "certificate inventory did not close")
    if production and len(control_certificates) != int(
        profile["inventory"]["control_count"]
    ):
        raise CorpusError(
            "MalformedCorpus", "control certificate inventory did not close"
        )
    states = [
        item["state"]
        for item in rank_certificates + q_certificates + control_certificates
    ]
    backend_invocations = sum(
        int(item.get("backend_invocations", 0))
        for item in rank_certificates + q_certificates + control_certificates
    )
    if backend_invocations != 0:
        raise CorpusError(
            "IntegrityMismatch", "semantic admission invoked a forbidden backend"
        )
    state_counts = dict(collections.Counter(states))
    return {
        "schema": REPORT_SCHEMA,
        "profile": {
            "profile_id": profile["profile_id"],
            "profile_hash": profile["profile_hash"],
        },
        "manifest": {
            "path": corpus.path.name,
            "sha256": sha256_bytes(corpus.raw_manifest),
            "corpus_sha256": corpus.corpus_sha256,
            "schema": corpus.manifest["schema"],
            "mode": "production" if production else "synthetic-self-test",
        },
        "state": _aggregate_state(states),
        "state_counts": state_counts,
        "backend_invocations": backend_invocations,
        "inventory": {
            "workloads": len(corpus.workloads),
            "blocks": len(corpus.blocks),
            "factor_sources": len(corpus.factor_sources),
            "artifact_locks": len(corpus.artifact_locks),
            "rank_certificates": len(rank_certificates),
            "q_certificates": len(q_certificates),
            "control_certificates": len(control_certificates),
        },
        "artifact_lock": corpus.artifact_locks,
        "rank_certificates": rank_certificates,
        "q_certificates": q_certificates,
        "control_certificates": control_certificates,
    }


def inspect_inventory(
    manifest_path: Path, profile: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate and hash-lock production inventory without claiming semantics."""

    profile = validate_profile(profile)
    corpus = Corpus(manifest_path, production=True, inventory=profile["inventory"])
    return {
        "schema": REPORT_SCHEMA,
        "profile": {
            "profile_id": profile["profile_id"],
            "profile_hash": profile["profile_hash"],
        },
        "manifest": {
            "path": corpus.path.name,
            "sha256": sha256_bytes(corpus.raw_manifest),
            "corpus_sha256": corpus.corpus_sha256,
            "schema": corpus.manifest["schema"],
            "mode": "production-inventory-only",
        },
        "state": "EVIDENCE_MISSING",
        "reason": "inventory-only mode does not materialize semantic certificates",
        "inventory_validation": "Admitted",
        "backend_invocations": 0,
        "inventory": {
            "workloads": len(corpus.workloads),
            "blocks": len(corpus.blocks),
            "factor_sources": len(corpus.factor_sources),
            "artifact_locks": len(corpus.artifact_locks),
            "rank_certificates_required": profile["inventory"][
                "rank_certificate_count"
            ],
            "q_certificates_required": profile["inventory"]["q_certificate_count"],
            "control_certificates_required": profile["inventory"]["control_count"],
        },
        "artifact_lock": corpus.artifact_locks,
    }


def _artifact_record(
    root: Path,
    artifacts: list[dict[str, Any]],
    owner_kind: str,
    owner_id: str,
    role: str,
    array: np.ndarray,
    encoding: str = "row-major",
) -> str:
    artifact_id = f"{owner_kind}:{owner_id}:{role}"
    relative = PurePosixPath("fixture") / owner_id / f"{role}.bin"
    path = root / Path(*relative.parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    if array.dtype == np.float64:
        dtype = "f64"
        raw = np.asarray(array, dtype="<f8")
    elif array.dtype == np.int64:
        dtype = "i64"
        raw = np.asarray(array, dtype="<i8")
    elif array.dtype == np.uint8:
        dtype = "u8"
        raw = array
    else:
        raise ValueError(array.dtype)
    if encoding == "lower-triangle-row-major-packed":
        stored = np.array(
            [
                raw[row, column]
                for row in range(raw.shape[0])
                for column in range(row + 1)
            ],
            dtype=raw.dtype,
        )
    else:
        stored = raw.ravel(order="C")
    path.write_bytes(stored.tobytes())
    artifacts.append(
        {
            "artifact_id": artifact_id,
            "owner_kind": owner_kind,
            "owner_id": owner_id,
            "role": role,
            "path": relative.as_posix(),
            "dtype": dtype,
            "byte_order": "not-applicable" if dtype == "u8" else "little",
            "encoding": encoding,
            "shape": list(array.shape),
            "stored_elements": int(stored.size),
            "bytes": int(stored.nbytes),
            "sha256": sha256_bytes(stored.tobytes()),
        }
    )
    return artifact_id


def make_synthetic_manifest(root: Path) -> Path:
    """Materialize a tiny, explicitly non-production corpus."""

    artifacts: list[dict[str, Any]] = []
    workload_id = "SYNTHETIC-1K"
    block_id = f"{workload_id}-level-0-coarse-000"
    workload_refs = {
        "value_points": _artifact_record(
            root,
            artifacts,
            "workload",
            workload_id,
            "value_points",
            np.array([[0.0, 0.0, 0.0], [0.5, 0.25, 0.75], [1.0, 1.0, 1.0]]),
        ),
        "gradient_points": _artifact_record(
            root,
            artifacts,
            "workload",
            workload_id,
            "gradient_points",
            np.empty((0, 3), dtype=np.float64),
        ),
        "observations": _artifact_record(
            root,
            artifacts,
            "workload",
            workload_id,
            "observations",
            np.array([1.0, 2.0, 3.0]),
            "contiguous",
        ),
        "selected_polynomial_indices": _artifact_record(
            root,
            artifacts,
            "workload",
            workload_id,
            "selected_polynomial_indices",
            np.array([0], dtype=np.int64),
            "contiguous",
        ),
    }
    model_values_artifact = _artifact_record(
        root,
        artifacts,
        "workload",
        workload_id,
        "model_values",
        np.array([0.0]),
        "contiguous",
    )
    p = np.ones((3, 1), dtype=np.float64)
    qtop = np.array([[-1.0, -1.0]], dtype=np.float64)
    qtaq = np.array([[2.0, 1.0], [1.0, 2.0]], dtype=np.float64)
    block_arrays: dict[str, tuple[np.ndarray, str]] = {
        "domain_value_indices": (np.array([0, 1, 2], dtype=np.int64), "contiguous"),
        "domain_gradient_indices": (np.array([], dtype=np.int64), "contiguous"),
        "inner_value_mask": (np.array([1, 1, 1], dtype=np.uint8), "contiguous"),
        "inner_gradient_mask": (np.array([], dtype=np.uint8), "contiguous"),
        "canonical_lagrange_flat_indices": (
            np.array([0, 1, 2], dtype=np.int64),
            "contiguous",
        ),
        "a_lower": (np.eye(3, dtype=np.float64), "lower-triangle-row-major-packed"),
        "p_row_major": (p, "row-major"),
        "q_top_row_major": (qtop, "row-major"),
        "qtaq_lower": (qtaq, "lower-triangle-row-major-packed"),
        "rhs_full": (np.array([1.0, 2.0, 3.0]), "contiguous"),
        "rhs_reduced": (np.array([1.0, 2.0]), "contiguous"),
        "p_top_row_major": (np.ones((1, 1)), "row-major"),
    }
    block_refs = {
        role: _artifact_record(
            root, artifacts, "block", block_id, role, array, encoding
        )
        for role, (array, encoding) in block_arrays.items()
    }
    manifest = {
        "schema": SCHEMA,
        "generator": "admission-synthetic-self-test",
        "evidence": "non-authoritative synthetic self-test only",
        "binary_contract": {
            "double_bytes": 8,
            "iec559": True,
            "little_endian": True,
        },
        "assembly": {
            "row_channel_map": (
                "values at global value index; gradients at "
                "source_value_rows + 3*global_gradient_index + component"
            )
        },
        "counts": {
            "artifacts": len(artifacts),
            "workloads": 1,
            "blocks": 1,
            "fine_blocks": 0,
            "coarse_blocks": 1,
            "factor_sources": 2,
            "qtaq_factor_sources": 1,
            "p_top_factor_sources": 1,
            "auxiliary_decomposition_sources": 0,
            "controls": 0,
        },
        "artifacts": artifacts,
        "workloads": [
            {
                "workload_id": workload_id,
                "panel_id": "SYNTHETIC",
                "case_id": "SYNTHETIC/1K",
                "scale_id": "1k",
                "value_rows": 3,
                "gradient_points": 0,
                "scalar_order": 3,
                "resolved_polynomial_degree": 0,
                "polynomial_order": 1,
                "artifacts": workload_refs,
                "model": {"exact_values_artifact": model_values_artifact},
            }
        ],
        "blocks": [
            {
                "block_id": block_id,
                "workload_id": workload_id,
                "role": "coarse",
                "level": 0,
                "ordinal": 0,
                "source_value_rows": 3,
                "source_gradient_points": 0,
                "value_rows": 3,
                "gradient_points": 0,
                "inner_value_rows": 3,
                "inner_gradient_points": 0,
                "scalar_order": 3,
                "polynomial_order": 1,
                "reduced_order": 2,
                "row_channel_map": "canonical-global-value-offset-v1",
                "q_semantics": "Q=[Q_top;I]",
                "artifacts": block_refs,
            }
        ],
        "factor_sources": [
            {
                "factor_source_id": f"factor:{block_id}:qtaq",
                "block_id": block_id,
                "workload_id": workload_id,
                "matrix_role": "qtaq",
                "matrix_artifact": block_refs["qtaq_lower"],
                "factorization": "symmetric-ldlt",
                "use_site": "synthetic",
                "expected_rank": 2,
                "semantic_admission": "certificate-required-before-backend-selection",
            },
            {
                "factor_source_id": f"factor:{block_id}:p-top",
                "block_id": block_id,
                "workload_id": workload_id,
                "matrix_role": "p_top",
                "matrix_artifact": block_refs["p_top_row_major"],
                "factorization": "full-pivot-lu",
                "use_site": "synthetic",
                "expected_rank": 1,
                "semantic_admission": "certificate-required-before-backend-selection",
            },
        ],
        "auxiliary_decomposition_sources": [],
        "controls": [],
        "exclusions": [
            {"record_id": identifier, "reason": "excluded"}
            for identifier in sorted(EXPECTED_EXCLUSIONS)
        ],
        "assertions": [
            {
                "assertion_id": "synthetic-inventory",
                "expected": 1,
                "actual": 1,
                "passed": True,
            }
        ],
    }
    path = root / "hierarchy.manifest.raw.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def self_test_controls(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    profile = validate_profile(profile)
    controls: list[dict[str, Any]] = []

    exact_failure = rank_certificate(
        "control:exact-rank-failure",
        "CONTROL",
        np.diag([1.0, 0.0]),
        profile,
    )
    controls.append(exact_failure)

    genuine_straddle_matrix = np.array(
        [
            [1.0, 1.0],
            [1.0, float.fromhex("0x1.0000000000006p+0")],
        ],
        dtype=np.float64,
    )
    genuine_ladder = rank_certificate(
        "control:genuine-exact-precision-ladder",
        "CONTROL",
        genuine_straddle_matrix,
        profile,
    )
    controls.append(genuine_ladder)

    tau = tau_rank((4, 4))
    initial = RatioEnvelope(
        tau - tau / 16,
        tau + tau / 16,
        "hash-bound-control-envelope",
        53,
    )

    def straddle_provider(bits: int) -> RatioEnvelope:
        half_width = tau / 32
        return RatioEnvelope(
            tau - half_width,
            tau + half_width,
            "hash-bound-control-envelope",
            bits,
        )

    state, steps, reason = drive_precision_ladder(
        initial,
        tau,
        profile["rank_rule"]["precision_ladder_bits"],
        straddle_provider,
    )
    controls.append(
        {
            "certificate_id": "control:true-final-straddle",
            "subject": "CONTROL",
            "state": state,
            "reason": reason,
            "tau_rank": tau,
            "tau_rank_binary64_hex": float(tau).hex(),
            "steps": steps,
            "backend_invocations": 0,
        }
    )
    controls.append(
        rank_certificate(
            "control:nonfinite",
            "CONTROL",
            np.array([[math.nan]]),
            profile,
        )
    )
    try:
        preflight_rank_subjects(
            [("control:resource-preflight", "CONTROL", (2, 2))],
            1,
        )
        resource_state = "EVIDENCE_MISSING"
        resource_reason = "resource control unexpectedly passed metadata preflight"
    except CorpusError as exc:
        resource_state = exc.state
        resource_reason = exc.reason
    controls.append(
        {
            "certificate_id": "control:resource-preflight",
            "subject": "CONTROL",
            "shape": [2, 2],
            "state": resource_state,
            "reason": resource_reason,
            "backend_invocations": 0,
        }
    )

    def denied_provider(_bits: int) -> RatioEnvelope:
        raise PrecisionResourceDenied

    state, steps, reason = drive_precision_ladder(
        initial,
        tau,
        profile["rank_rule"]["precision_ladder_bits"],
        denied_provider,
    )
    controls.append(
        {
            "certificate_id": "control:resource-after-straddle",
            "subject": "CONTROL",
            "state": state,
            "reason": reason,
            "tau_rank": tau,
            "tau_rank_binary64_hex": float(tau).hex(),
            "steps": steps,
            "backend_invocations": 0,
        }
    )
    try:
        analytic_ratio_envelope(np.array([1.0]))
        malformed_state = "EVIDENCE_MISSING"
        malformed_reason = "malformed control unexpectedly reached the checker"
    except CorpusError as exc:
        malformed_state = exc.state
        malformed_reason = exc.reason
    controls.append(
        {
            "certificate_id": "control:malformed",
            "subject": "CONTROL",
            "state": malformed_state,
            "reason": malformed_reason,
            "backend_invocations": 0,
        }
    )
    with tempfile.TemporaryDirectory(prefix="rapidrbf-profile-control-") as temporary:
        bad_profile = dict(profile)
        bad_profile["profile_hash"] = "0" * 64
        bad_profile_path = Path(temporary) / "bad-profile.json"
        bad_profile_path.write_text(
            json.dumps(bad_profile, indent=2) + "\n", encoding="utf-8"
        )
        try:
            load_profile(bad_profile_path)
            integrity_state = "EVIDENCE_MISSING"
            integrity_reason = "bad profile unexpectedly passed its hash lock"
        except CorpusError as exc:
            integrity_state = exc.state
            integrity_reason = exc.reason
    controls.append(
        {
            "certificate_id": "control:integrity",
            "subject": "CONTROL",
            "state": integrity_state,
            "reason": integrity_reason,
            "backend_invocations": 0,
        }
    )
    with tempfile.TemporaryDirectory(
        prefix="rapidrbf-profile-semantic-drift-control-"
    ) as temporary:
        drifted_profile = json.loads(json.dumps(profile))
        drifted_profile["rank_rule"]["tau_rank"] = "0.99"
        drifted_profile["profile_hash"] = profile_digest(drifted_profile)
        drifted_profile_path = Path(temporary) / "self-consistent-drift.json"
        drifted_profile_path.write_text(
            json.dumps(drifted_profile, indent=2) + "\n", encoding="utf-8"
        )
        try:
            load_profile(drifted_profile_path)
            drift_state = "EVIDENCE_MISSING"
            drift_reason = (
                "self-consistent semantic profile drift unexpectedly passed "
                "the pinned canonical lock"
            )
        except CorpusError as exc:
            drift_state = exc.state
            drift_reason = exc.reason
    controls.append(
        {
            "certificate_id": "control:semantic-profile-drift",
            "subject": "CONTROL",
            "state": drift_state,
            "reason": drift_reason,
            "backend_invocations": 0,
        }
    )
    expected = {
        "control:exact-rank-failure": "RankDeficient",
        "control:genuine-exact-precision-ladder": "Admitted",
        "control:true-final-straddle": "IndeterminateRank",
        "control:nonfinite": "NonFinite",
        "control:resource-preflight": "ResourceDenied",
        "control:resource-after-straddle": "EVIDENCE_MISSING",
        "control:malformed": "MalformedCorpus",
        "control:integrity": "IntegrityMismatch",
        "control:semantic-profile-drift": "IntegrityMismatch",
    }
    for control in controls:
        identifier = control["certificate_id"]
        if (
            control["state"] != expected[identifier]
            or control["backend_invocations"] != 0
        ):
            raise AssertionError(
                f"{identifier}: expected {expected[identifier]}/0 backend calls, "
                f"got {control['state']}/{control['backend_invocations']}"
            )
    genuine_steps = genuine_ladder["steps"]
    if (
        [step["precision_bits"] for step in genuine_steps] != [53, 256]
        or genuine_steps[0]["classification"] != "straddle"
        or genuine_steps[1]["authority"] != exact_rank.AUTHORITY
        or genuine_steps[1]["classification"] != "Admitted"
    ):
        raise AssertionError(
            "genuine exact precision-ladder control did not execute the "
            "53 -> 256-bit production authority path"
        )
    return controls


def run_self_test(profile: Mapping[str, Any]) -> dict[str, Any]:
    profile = validate_profile(profile)
    controls = self_test_controls(profile)
    with tempfile.TemporaryDirectory(prefix="rapidrbf-admission-") as temporary:
        manifest_path = make_synthetic_manifest(Path(temporary))
        report = certify_corpus(manifest_path, profile, production=False)
    if report["state"] != "Admitted":
        raise AssertionError(f"synthetic corpus did not admit: {report['state']}")
    report["controls"] = controls
    return report


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).with_name("rank-scaling-profile.v1.json"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="hash and validate production inventory without semantic closure",
    )
    parser.add_argument("--max-resource-units", type=int)
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.output is not None and args.output.exists():
        print(
            "cannot publish admission output: target already exists",
            file=sys.stderr,
        )
        return 2
    if args.output is not None and not args.output.parent.is_dir():
        print(
            "cannot publish admission output: output directory does not exist",
            file=sys.stderr,
        )
        return 2
    provenance: dict[str, Any] | None = None
    try:
        profile_payload = read_profile_bytes(args.profile)
        provenance = execution_provenance(args.profile, profile_payload)
        profile = load_profile_bytes(profile_payload)
        if not args.self_test and args.manifest is None:
            raise CorpusError("MalformedCorpus", "provide --self-test or --manifest")
        validate_execution_coordinate(profile, provenance)
        if args.self_test:
            report = run_self_test(profile)
        elif args.manifest is not None and args.inventory_only:
            report = inspect_inventory(args.manifest, profile)
        elif args.manifest is not None:
            report = certify_corpus(
                args.manifest,
                profile,
                production=True,
                max_resource_units=args.max_resource_units,
                progress=(
                    (lambda message: print(message, file=sys.stderr, flush=True))
                    if args.progress
                    else None
                ),
            )
    except CorpusError as exc:
        report = {
            "schema": REPORT_SCHEMA,
            "state": exc.state,
            "reason": exc.reason,
            "backend_invocations": 0,
        }
    if provenance is not None:
        report["execution"] = provenance
    text = (
        json.dumps(json_safe(report), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    if args.output:
        try:
            publish_text_fresh(args.output, text)
        except OSError as exc:
            print(f"cannot publish admission output: {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    return 0 if report["state"] == "Admitted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
