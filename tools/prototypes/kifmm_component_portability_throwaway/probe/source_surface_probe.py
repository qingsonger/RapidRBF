"""Assert and summarize the frozen kifmm component/portability source surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SCHEMA = "rapidrbf-kifmm-source-surface-probe/v1"
KIFMM_REVISION = "d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068"
GREEN_KERNELS_REVISION = "ed83120e5e74972fb0f21593b1f8f5047b6eefac"
RLST_REVISION = "33bd9a6339f2aa60076b74b6ed020473a81b1eb6"
SOURCE_FILES = {
    "fftw-src/build.rs": ("kifmm", "fftw-src/build.rs"),
    "fftw-sys/Cargo.toml": ("kifmm", "fftw-sys/Cargo.toml"),
    "fftw-sys/build.rs": ("kifmm", "fftw-sys/build.rs"),
    "green-kernels/src/traits.rs": ("green-kernels", "src/traits.rs"),
    "green-kernels/src/types.rs": ("green-kernels", "src/types.rs"),
    "kifmm/Cargo.toml": ("kifmm", "kifmm/Cargo.toml"),
    "kifmm/builder/single_node.rs": (
        "kifmm",
        "kifmm/src/fmm/builder/single_node.rs",
    ),
    "kifmm/metadata/single_node/metadata.rs": (
        "kifmm",
        "kifmm/src/fmm/field_translation/metadata/single_node/metadata.rs",
    ),
    "kifmm/source_to_target/fft/single_node.rs": (
        "kifmm",
        "kifmm/src/fmm/field_translation/source_to_target/fft/single_node.rs",
    ),
    "rlst/Cargo.toml": ("rlst", "Cargo.toml"),
    "rlst/build.rs": ("rlst", "build.rs"),
}
EXPECTED_SOURCE_SHA256 = {
    "fftw-src/build.rs": "CAAD18408316D8C2AECBAF25B730D7FEBA21F402848C6BDC870AAB9300965AA4",
    "fftw-sys/Cargo.toml": "574CB89885528A3EA03E6F57EBFC23DD0BD5C2570A46C03F3CEFB01EB5BA4C3E",
    "fftw-sys/build.rs": "01F72157A195B74DD9ABC1EAFD1A8BD5B65420CB0D76B45CE6A9AA4481DF0958",
    "green-kernels/src/traits.rs": "DA596089617F668AA9FDEA12576F8CB8857C002A1D4855B07ACB453302E29605",
    "green-kernels/src/types.rs": "85C5E62903EA122724A483809879F4287FC3149E99790301BFBA8D1ABB3917F6",
    "kifmm/Cargo.toml": "843FCCA07D566ED7FF8D66FE3EBEFFBE96BEC88ABC992961DBDB672FCB806B93",
    "kifmm/builder/single_node.rs": "CAF5616C87452D1AC8BDB7107D2B60E8298B72DE14723C09502F7419B853B727",
    "kifmm/metadata/single_node/metadata.rs": "A24C69981FE3BE927ECD2AB1900ED23AB9927FAF1C197BBFD912ED2E0C01B913",
    "kifmm/source_to_target/fft/single_node.rs": "846E3AB8F606F99582890B560F5FD4AE304635A21899342946D3E20CDAB1AE59",
    "rlst/Cargo.toml": "70EA9BA9BE640A13D377AB6B57ED6E0D24784B84304E22910F665493516C8A3C",
    "rlst/build.rs": "CD3341427B57CD198AA82087579025789FD62C9F6C157A7188CEAD87D61A870F",
}


def git_bytes(directory: Path, *arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(directory), *arguments],
    )


def git(directory: Path, *arguments: str) -> str:
    return git_bytes(directory, *arguments).decode("utf-8").strip()


def blob_bytes(directory: Path, relative: str) -> bytes:
    return git_bytes(directory, "show", f"HEAD:{relative}")


def read(directory: Path, relative: str) -> str:
    return blob_bytes(directory, relative).decode("utf-8")


def sha256(directory: Path, relative: str) -> str:
    return hashlib.sha256(blob_bytes(directory, relative)).hexdigest().upper()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise RuntimeError(f"{label}: missing expected fragment {fragment!r}")


def rust_core(kifmm: Path) -> str:
    chunks = []
    paths = git(
        kifmm,
        "ls-tree",
        "-r",
        "--name-only",
        "HEAD",
        "kifmm/src",
    ).splitlines()
    for relative in paths:
        if not relative.endswith(".rs") or Path(relative).name == "bindings.rs":
            continue
        chunks.append(read(kifmm, relative))
    return "\n".join(chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kifmm", type=Path, required=True)
    parser.add_argument("--green-kernels", type=Path, required=True)
    parser.add_argument("--rlst", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    kifmm = args.kifmm.resolve()
    green = args.green_kernels.resolve()
    rlst = args.rlst.resolve()

    revisions = {
        "kifmm": git(kifmm, "rev-parse", "HEAD"),
        "green-kernels": git(green, "rev-parse", "HEAD"),
        "rlst": git(rlst, "rev-parse", "HEAD"),
    }
    expected = {
        "kifmm": KIFMM_REVISION,
        "green-kernels": GREEN_KERNELS_REVISION,
        "rlst": RLST_REVISION,
    }
    if revisions != expected:
        raise RuntimeError(f"revision mismatch: {revisions!r}")

    repositories = {
        "kifmm": kifmm,
        "green-kernels": green,
        "rlst": rlst,
    }
    tracked_changes = {
        name: git(path, "status", "--porcelain=v1", "--untracked-files=no")
        for name, path in repositories.items()
    }
    tracked_changes = {
        name: status for name, status in tracked_changes.items() if status
    }
    if tracked_changes:
        raise RuntimeError(
            "tracked checkout changes are not allowed: "
            f"{tracked_changes!r}"
        )

    source_sha256 = {
        label: sha256(repositories[repository], relative)
        for label, (repository, relative) in SOURCE_FILES.items()
    }
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        mismatches = {
            label: {
                "expected": EXPECTED_SOURCE_SHA256.get(label),
                "actual": actual,
            }
            for label, actual in source_sha256.items()
            if actual != EXPECTED_SOURCE_SHA256.get(label)
        }
        raise RuntimeError(f"canonical source blob mismatch: {mismatches!r}")

    manifest = read(kifmm, "kifmm/Cargo.toml")
    builder = read(kifmm, "kifmm/src/fmm/builder/single_node.rs")
    metadata = read(
        kifmm,
        "kifmm/src/fmm/field_translation/metadata/single_node/metadata.rs",
    )
    eval_types = read(green, "src/types.rs")
    kernel_trait = read(green, "src/traits.rs")
    fftw_build = read(kifmm, "fftw-src/build.rs")
    fftw_sys_manifest = read(kifmm, "fftw-sys/Cargo.toml")
    fftw_sys_build = read(kifmm, "fftw-sys/build.rs")
    charge_handler = read(kifmm, "kifmm/src/fmm/charge_handler/single_node.rs")
    fft_matrix = read(
        kifmm,
        "kifmm/src/fmm/field_translation/source_to_target/fft/single_node.rs",
    )
    helpers = read(kifmm, "kifmm/src/fmm/helpers/single_node.rs")
    errors = read(kifmm, "kifmm/src/traits/types.rs")
    rlst_manifest = read(rlst, "Cargo.toml")
    rlst_build = read(rlst, "build.rs")
    core = rust_core(kifmm)

    require(manifest, 'green-kernels = { git = "https://github.com/skailasa/green-kernels" }', "moving green-kernels")
    require(manifest, 'branch="tmp"', "moving rlst")
    require(
        manifest,
        'kifmm-fftw-sys = { path = "../fftw-sys" }',
        "unconditional FFTW dependency",
    )
    require(builder, "let dim = 3;", "hard-coded dimension")
    require(metadata, "GreenKernelEvalType::Value => 1", "value output width")
    require(
        metadata,
        "GreenKernelEvalType::ValueDeriv => self.dim + 1",
        "gradient output width",
    )
    require(eval_types, "ValueDeriv", "closed evaluation enum")
    require(kernel_trait, "fn domain_component_count(&self) -> usize;", "domain count trait")
    require(
        kernel_trait,
        "fn range_component_count(&self, eval_type: GreenKernelEvalType) -> usize;",
        "range count trait",
    )
    require(fftw_build, 'connect("ftp.fftw.org:21")', "plain FTP download")
    require(fftw_build, 'simple_retr("fftw-3.3.9.zip")', "FFTW version")
    require(fftw_build, 'Command::new(canonicalize(src_dir.join("configure"))', "Unix configure")
    require(fftw_build, 'Command::new("make")', "Unix make")
    require(
        fftw_build,
        'println!("cargo:rustc-link-lib=static=fftw3")',
        "static FFTW link",
    )
    require(
        fftw_build,
        'println!("cargo:rustc-link-lib=static=fftw3f")',
        "static FFTWF link",
    )
    require(
        fftw_sys_manifest,
        'kifmm-fftw-src = { path = "../fftw-src" }',
        "FFTW source dependency",
    )
    require(fftw_sys_manifest, 'bindgen = "0.69.4"', "bindgen dependency")
    require(
        fftw_sys_build,
        "let bindings = bindgen::Builder::default()",
        "bindgen invocation",
    )
    require(charge_handler, "fn attach_charges_ordered", "weight reuse")
    require(charge_handler, "self.clear().unwrap();", "clear-before-weight-reuse")
    require(
        fft_matrix,
        "M2L unimplemented for matrix input with FFT field translations",
        "FFT matrix RHS rejection",
    )
    require(
        helpers,
        "pub(crate) fn homogenous_kernel_scale",
        "homogeneous scaling",
    )
    require(errors, "pub enum FmmError", "error algebra")
    require(rlst_manifest, 'blas = "0.22"', "BLAS dependency")
    require(rlst_manifest, 'lapack = "0.19"', "LAPACK dependency")
    require(rlst_build, 'cargo:rustc-link-lib=dylib=blas', "Linux BLAS link")
    require(core, "Laplace3dKernel", "Laplace metadata specialization")
    require(core, "Helmholtz3dKernel", "Helmholtz metadata specialization")

    eval_variants = [
        line.strip().rstrip(",")
        for line in eval_types.splitlines()
        if line.strip() in {"Value,", "ValueDeriv,"}
    ]
    if eval_variants != ["Value", "ValueDeriv"]:
        raise RuntimeError(f"unexpected evaluation enum: {eval_variants!r}")

    component_core_references = {
        "domain_component_count": core.count("domain_component_count"),
        "range_component_count": core.count("range_component_count"),
    }
    if component_core_references != {
        "domain_component_count": 0,
        "range_component_count": 0,
    }:
        raise RuntimeError(
            f"component methods unexpectedly reached KiFMM core: {component_core_references}"
        )

    lock_tracked = bool(git(kifmm, "ls-files", "Cargo.lock"))
    if lock_tracked:
        raise RuntimeError("frozen source unexpectedly tracks Cargo.lock")

    report = {
        "schema": SCHEMA,
        "authority": (
            "Throwaway frozen-source evidence only; not runtime semantics, "
            "accepted harness evidence, a sound certificate, or Auto qualification."
        ),
        "revisions": revisions,
        "hash_basis": "SHA-256 of canonical HEAD Git blobs",
        "source_sha256": source_sha256,
        "facts": {
            "cargo_lock_tracked": lock_tracked,
            "component_method_references_in_kifmm_core_excluding_bindings": component_core_references,
            "eval_modes": ["Value", "ValueDeriv"],
            "fftw": {
                "download": "plain FTP fftw-3.3.9.zip without a declared digest",
                "link": "unconditional static fftw3 and fftw3f",
                "toolchain": "configure + make + bindgen/libclang",
            },
            "kernel_metadata_specializations": [
                "Laplace3dKernel",
                "Helmholtz3dKernel",
            ],
            "fft_matrix_rhs_supported": False,
            "homogeneous_scale_shape": "fixed 2^-level helper; custom RBF fork must use non-homogeneous per-level metadata",
            "native_dimension": 3,
            "operational_token_counts": {
                "cancel": core.lower().count("cancel"),
                "deadline": core.lower().count("deadline"),
                "thread_pool_builder": core.count("ThreadPoolBuilder"),
            },
            "sequential_weight_reuse": True,
            "target_hessian_eval_mode": False,
        },
    }
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
