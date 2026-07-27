"""Freeze source facts for the throwaway ScalFMM3 C-ABI decision lab."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


POLATORY_REVISION = "4a30beb08053fb339ce899e255be4b6d3f74aa0c"
SCALFMM_REVISION = "0be3d74f17adb28adec7004f712f693ac8ee9901"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def tree_observation(root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "little"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "little"))
        digest.update(content)
    return {
        "root": str(root.resolve()),
        "file_count": len(files),
        "tree_sha256": digest.hexdigest().upper(),
    }


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def count(text: str, needle: str) -> int:
    return text.count(needle)


def scan_native_surface(root: Path) -> dict[str, int]:
    suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
    source_files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in suffixes
        and ".git" not in path.parts
    )
    c_linkage_markers = 0
    export_markers = 0
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        c_linkage_markers += text.count('extern "C"')
        export_markers += text.count("dllexport")
        export_markers += text.count('visibility("default")')
    return {
        "scanned_public_core_source_files": len(source_files),
        "c_linkage_markers": c_linkage_markers,
        "export_markers": export_markers,
    }


def scan_terms(roots: list[Path], terms: tuple[str, ...]) -> dict[str, object]:
    suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
    source_files = sorted(
        {
            path
            for root in roots
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in suffixes
        }
    )
    counts = {term: 0 for term in terms}
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in terms:
            counts[term] += text.count(term)
    return {
        "scanned_source_files": len(source_files),
        "search_terms": list(terms),
        "match_counts": counts,
        "total_matches": sum(counts.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--polatory-root",
        type=Path,
        default=Path(r"D:\CODE\polatory"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.polatory_root.resolve()
    scalfmm = root / "build" / "scalfmm" / "src" / "scalfmm"

    files = {
        "factory": root / "src" / "fmm" / "make_fmm_evaluator.cpp",
        "evaluator": root / "src" / "fmm" / "fmm_evaluator.hpp",
        "symmetric_evaluator": root / "src" / "fmm" / "fmm_symmetric_evaluator.hpp",
        "estimator": root / "src" / "fmm" / "fmm_accuracy_estimator.hpp",
        "scalfmm_cmake": scalfmm / "CMakeLists.txt",
        "scalfmm_manifest": scalfmm / "vcpkg.json",
        "scalfmm_license": scalfmm / "LICENCE",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in files.items()}

    polatory_revision = git(root, "rev-parse", "HEAD")
    scalfmm_revision = git(scalfmm, "rev-parse", "HEAD")
    if polatory_revision != POLATORY_REVISION:
        raise SystemExit(f"unexpected Polatory revision: {polatory_revision}")
    if scalfmm_revision != SCALFMM_REVISION:
        raise SystemExit(f"unexpected ScalFMM revision: {scalfmm_revision}")

    factory = texts["factory"]
    evaluator = texts["evaluator"]
    symmetric = texts["symmetric_evaluator"]
    estimator = texts["estimator"]
    cmake = texts["scalfmm_cmake"]
    manifest = json.loads(texts["scalfmm_manifest"])
    license_text = texts["scalfmm_license"]
    native_surface = scan_native_surface(scalfmm / "include" / "scalfmm")
    source_header_tree = tree_observation(scalfmm / "include" / "scalfmm")
    installed_header_tree = tree_observation(
        root / "build" / "scalfmm" / "install" / "include" / "scalfmm"
    )
    cancellation_scan = scan_terms(
        [
            root / "include" / "polatory" / "fmm",
            root / "src" / "fmm",
            scalfmm / "include" / "scalfmm",
        ],
        ("cancel", "stop_token", "stop_requested", "deadline"),
    )

    facts = {
        "polatory_revision": polatory_revision,
        "scalfmm_revision": scalfmm_revision,
        "factory": {
            "dimensions_explicitly_instantiated": [
                dim
                for dim in (1, 2, 3)
                if f"make_fmm_evaluator<{dim}>" in factory
            ],
            "action_factories": {
                "A": count(factory, "make_fmm_evaluator"),
                "F": count(factory, "make_fmm_gradient_evaluator"),
                "FT": count(factory, "make_fmm_gradient_transpose_evaluator"),
                "H": count(factory, "make_fmm_hessian_evaluator"),
            },
            "family_case_count_per_factory": factory.split(
                "template FmmGenericEvaluatorPtr<1>", maxsplit=1
            )[0].count("CASE("),
        },
        "mutable_legacy_evaluator": {
            "has_set_source_points": "void set_source_points" in evaluator,
            "has_set_target_points": "void set_target_points" in evaluator,
            "has_set_weights": "void set_weights" in evaluator,
            "releases_cross_trees_after_evaluate": (
                "src_tree_.reset(nullptr);" in evaluator
                and "trg_tree_.reset(nullptr);" in evaluator
            ),
            "releases_symmetric_tree_after_evaluate": (
                "tree_.reset(nullptr);" in symmetric
            ),
            "weight_change_warning_present": (
                "If weights are changed significantly" in evaluator
            ),
        },
        "accuracy_estimator": {
            "maximum_sampled_targets": 10_000
            if "kMaxTargetSize = 10000" in estimator
            else None,
            "uses_deterministic_shuffle": (
                "std::mt19937 gen;" in estimator
                and "std::shuffle" in estimator
            ),
            "compares_sampled_absolute_error": (
                "absolute_error<Eigen::Infinity>" in estimator
            ),
        },
        "cancellation": {
            **cancellation_scan,
        },
        "native_surface": {
            "scalfmm_target_is_interface": (
                "add_library(${CMAKE_PROJECT_NAME} INTERFACE)" in cmake
            ),
            **native_surface,
            "declared_core_libraries": (
                "BLAS LAPACK FFTW OpenMP"
                if "set(CORE_LIBRARIES BLAS LAPACK FFTW OpenMP)" in cmake
                else None
            ),
        },
        "compiled_header_provenance": {
            "source_checkout": source_header_tree,
            "installed_include": installed_header_tree,
            "trees_match": (
                source_header_tree["file_count"]
                == installed_header_tree["file_count"]
                and source_header_tree["tree_sha256"]
                == installed_header_tree["tree_sha256"]
            ),
        },
        "distribution": {
            "manifest_dependencies": manifest["dependencies"],
            "license_marker": (
                "CeCILL-C" if "CeCILL-C" in license_text else "UNEXPECTED"
            ),
            "tier_one_platforms_observed": ["windows-x86_64"],
        },
        "source_sha256": {
            name: sha256(path) for name, path in sorted(files.items())
        },
    }

    checks = {
        "frozen_revisions": (
            polatory_revision == POLATORY_REVISION
            and scalfmm_revision == SCALFMM_REVISION
        ),
        "dimensions_1_to_3": (
            facts["factory"]["dimensions_explicitly_instantiated"] == [1, 2, 3]
        ),
        "four_action_factories": all(
            value > 0 for value in facts["factory"]["action_factories"].values()
        ),
        "mutable_setter_surface": all(
            facts["mutable_legacy_evaluator"][key]
            for key in (
                "has_set_source_points",
                "has_set_target_points",
                "has_set_weights",
            )
        ),
        "sampled_estimator_shape": (
            facts["accuracy_estimator"]["maximum_sampled_targets"] == 10_000
            and facts["accuracy_estimator"]["uses_deterministic_shuffle"]
            and facts["accuracy_estimator"]["compares_sampled_absolute_error"]
        ),
        "no_cancellation_symbols_in_scanned_surfaces": (
            facts["cancellation"]["total_matches"] == 0
        ),
        "new_compiled_shim_required": (
            facts["native_surface"]["scalfmm_target_is_interface"]
            and facts["native_surface"]["c_linkage_markers"] == 0
            and facts["native_surface"]["export_markers"] == 0
        ),
        "installed_headers_match_source_checkout": (
            facts["compiled_header_provenance"]["trees_match"]
        ),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise SystemExit(f"source assertions failed: {failed}")

    result = {
        "schema": "rapidrbf-scalfmm3-source-observation/v1",
        "question": (
            "What does the frozen source prove or leave missing for a narrow "
            "private C ABI?"
        ),
        "checks": checks,
        "facts": facts,
        "limits": [
            "Source structure is not runtime behavior.",
            "Factory coverage is not semantic or numerical acceptance.",
            "Negative symbol scans are source-inspected interpretations, not formal proofs of absence.",
            "The sampled estimator shape alone is not a complete-batch certification analysis.",
            "Vendored external modules are excluded from the public ScalFMM C-surface scan.",
            "License inventory is engineering evidence, not legal advice.",
        ],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
