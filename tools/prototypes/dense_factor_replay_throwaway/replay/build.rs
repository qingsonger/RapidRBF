use std::env;
use std::fs;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

const IMPORT_LIBRARIES: [(&str, &str); 3] = [
    (
        "mkl_intel_lp64_dll.lib",
        "487B430C0A2BCCA41DC40ABCAB8CBC18471701B621EFB850136F6D45821F5DB4",
    ),
    (
        "mkl_sequential_dll.lib",
        "3859198460BD0D04A617A7FECB9CEB9C18F7E8B14EBCB439A0EEBACA7B9D01B2",
    ),
    (
        "mkl_core_dll.lib",
        "110C0433D4665F8535174059D9042992CD88E566C7B2B13281FD776A7D46CC02",
    ),
];
const RUNTIME_LIBRARIES: [(&str, &str); 4] = [
    (
        "mkl_core.2.dll",
        "3E7EDB4328ABF430B62C7C75E33447042DC8033F0CC75910708FD3BB5F27C792",
    ),
    (
        "mkl_sequential.2.dll",
        "478FDA28A98021FB7F95B27B2876CAC7346D77C4A491003BA0F50BAF17B66FE3",
    ),
    (
        "mkl_def.2.dll",
        "0AFF76A9A8C4618C1F467BF08334EC3A93E92ADA04B62F31864C8F052BEA9745",
    ),
    (
        "mkl_avx2.2.dll",
        "CC85F0C3B1F0F02998A14923037873530645A77039E95A6A3FB90A7D01468D41",
    ),
];

fn main() {
    println!("cargo:rustc-check-cfg=cfg(rapidrbf_exact_mkl)");
    println!("cargo:rerun-if-env-changed=RAPIDRBF_MKL_ROOT");

    if env::var_os("CARGO_CFG_WINDOWS").is_none() {
        return;
    }

    let root = env::var_os("RAPIDRBF_MKL_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"D:\CODE\polatory\build\vcpkg_installed\x64-windows"));
    let lib = root.join("lib").join("intel64");
    let bin = root.join("bin");
    println!(
        "cargo:rustc-env=RAPIDRBF_MKL_CONFIGURED_ROOT={}",
        root.display()
    );
    println!(
        "cargo:rustc-env=RAPIDRBF_MKL_CONFIGURED_LIB={}",
        lib.display()
    );
    println!(
        "cargo:rustc-env=RAPIDRBF_MKL_CONFIGURED_BIN={}",
        bin.display()
    );

    let mut import_closure_present = true;
    for (name, expected) in IMPORT_LIBRARIES {
        import_closure_present &= verify_registered(&lib.join(name), expected);
    }
    let mut runtime_closure_present = true;
    for (name, expected) in RUNTIME_LIBRARIES {
        runtime_closure_present &= verify_registered(&bin.join(name), expected);
    }
    if !(import_closure_present && runtime_closure_present) {
        println!(
            "cargo:warning=exact oneMKL comparator disabled: missing frozen layered closure under {}",
            root.display()
        );
        return;
    }

    println!("cargo:rustc-cfg=rapidrbf_exact_mkl");
    println!("cargo:rustc-link-search=native={}", lib.display());
    println!("cargo:rustc-link-lib=dylib=mkl_intel_lp64_dll");
    println!("cargo:rustc-link-lib=dylib=mkl_sequential_dll");
    println!("cargo:rustc-link-lib=dylib=mkl_core_dll");

    // The import libraries are the exact layered LP64/sequential interface used by
    // frozen Polatory. Copy only the dispatcher closure beside this throwaway
    // executable so Windows can start it without mutating the user's global PATH.
    let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR"));
    let profile_dir = out_dir
        .ancestors()
        .nth(3)
        .expect("Cargo OUT_DIR has a profile ancestor");
    for (name, expected) in RUNTIME_LIBRARIES {
        copy_or_verify(&bin.join(name), &profile_dir.join(name), expected);
    }
}

fn verify_registered(path: &Path, expected: &str) -> bool {
    println!("cargo:rerun-if-changed={}", path.display());
    if !path.is_file() {
        return false;
    }
    let actual = sha256(path);
    assert!(
        actual.eq_ignore_ascii_case(expected),
        "frozen oneMKL artifact hash mismatch for {}: expected {expected}, found {actual}",
        path.display()
    );
    true
}

fn copy_or_verify(source: &Path, destination: &Path, expected: &str) {
    let destination_matches =
        destination.is_file() && sha256(destination).eq_ignore_ascii_case(expected);
    if !destination_matches {
        fs::copy(source, destination).unwrap_or_else(|error| {
            panic!(
                "failed to stage {} beside prototype executable at {}: {error}",
                source.display(),
                destination.display()
            )
        });
    }
    let staged = sha256(destination);
    assert!(
        staged.eq_ignore_ascii_case(expected),
        "staged oneMKL runtime hash mismatch for {}: expected {expected}, found {staged}",
        destination.display()
    );
}

fn sha256(path: &Path) -> String {
    let mut file = File::open(path)
        .unwrap_or_else(|error| panic!("cannot open {} for hashing: {error}", path.display()));
    let mut digest = Sha256::new();
    let mut buffer = vec![0_u8; 1024 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .unwrap_or_else(|error| panic!("cannot hash {}: {error}", path.display()));
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    format!("{:X}", digest.finalize())
}
