use crate::{
    AttemptContext, attach_full_correction, attempt_base, backward_error, finite_number,
    source_resource_ledger, vector_finite,
};
use serde_json::{Value, json};
#[cfg(all(windows, rapidrbf_exact_mkl))]
use sha2::{Digest, Sha256};

const DEFAULT_MKL_ROOT: &str = r"D:\CODE\polatory\build\vcpkg_installed\x64-windows";
const MKL_ROOT: &str = match option_env!("RAPIDRBF_MKL_CONFIGURED_ROOT") {
    Some(path) => path,
    None => DEFAULT_MKL_ROOT,
};
const MKL_LIB: &str = match option_env!("RAPIDRBF_MKL_CONFIGURED_LIB") {
    Some(path) => path,
    None => r"D:\CODE\polatory\build\vcpkg_installed\x64-windows\lib\intel64",
};
const MKL_BIN: &str = match option_env!("RAPIDRBF_MKL_CONFIGURED_BIN") {
    Some(path) => path,
    None => r"D:\CODE\polatory\build\vcpkg_installed\x64-windows\bin",
};
#[cfg(all(windows, rapidrbf_exact_mkl))]
const EXPECTED_MKL_VERSION: &str = "Intel(R) oneAPI Math Kernel Library Version 2023.0-Product Build 20221128 for Intel(R) 64 architecture applications";

#[cfg(all(windows, rapidrbf_exact_mkl))]
unsafe extern "C" {
    fn LAPACKE_dsytrf_work(
        matrix_layout: i32,
        uplo: i8,
        n: i32,
        a: *mut f64,
        lda: i32,
        ipiv: *mut i32,
        work: *mut f64,
        lwork: i32,
    ) -> i32;
    fn LAPACKE_dsytrs_work(
        matrix_layout: i32,
        uplo: i8,
        n: i32,
        nrhs: i32,
        a: *const f64,
        lda: i32,
        ipiv: *const i32,
        b: *mut f64,
        ldb: i32,
    ) -> i32;
    fn LAPACKE_dgetrf_work(
        matrix_layout: i32,
        m: i32,
        n: i32,
        a: *mut f64,
        lda: i32,
        ipiv: *mut i32,
    ) -> i32;
    fn LAPACKE_dgetrs_work(
        matrix_layout: i32,
        trans: i8,
        n: i32,
        nrhs: i32,
        a: *const f64,
        lda: i32,
        ipiv: *const i32,
        b: *mut f64,
        ldb: i32,
    ) -> i32;
    fn MKL_Set_Dynamic(value: i32);
    fn MKL_Set_Num_Threads_Local(value: i32) -> i32;
    fn MKL_Get_Max_Threads() -> i32;
    fn MKL_Get_Version_String(buffer: *mut i8, length: i32);
    fn MKL_Mem_Stat(buffers: *mut i32) -> i64;
    fn MKL_Peak_Mem_Usage(reset: i32) -> i64;
    fn MKL_Free_Buffers();
}

pub fn run(context: &AttemptContext) -> Value {
    #[cfg(all(windows, rapidrbf_exact_mkl))]
    {
        run_exact(context)
    }
    #[cfg(not(all(windows, rapidrbf_exact_mkl)))]
    {
        evidence_missing(context)
    }
}

#[cfg(not(all(windows, rapidrbf_exact_mkl)))]
fn evidence_missing(context: &AttemptContext) -> Value {
    let mut result = attempt_base(context, "onemkl-lp64-sequential");
    result["backend_version"] = json!("2023.0.0#2 (requested frozen coordinate)");
    result["attempt_state"] = json!("EVIDENCE_MISSING");
    result["factor"] = json!({
        "status": "NOT_RUN",
        "pivot_diagnostics": null,
        "reconstruction_relative_inf": null,
        "reconstruction_status": "EVIDENCE_MISSING"
    });
    result["solve"] = json!({
        "status": "NOT_RUN",
        "reduced_backward_error": null
    });
    result["packing"] = json!({
        "capability": "EVIDENCE_MISSING",
        "roundtrip_tested": false,
        "packed_bytes": null
    });
    result["resources"] = json!({
        "retained_bytes": null,
        "transient_peak_delta_bytes": null,
        "temp_storage_bytes": null,
        "thread_ownership": "NOT_MATERIALIZED: no caller concurrency lease is implemented",
        "caller_thread_lease_materialized": false,
        "requested_threads": 1,
        "observed_threads": null
    });
    result["artifact_closure"] = json!({
        "state": "EVIDENCE_MISSING",
        "coordinates": {
            "version": "oneMKL 2023.0.0#2",
            "interface": "LP64",
            "threading": "sequential",
            "root": MKL_ROOT,
            "lib": MKL_LIB,
            "bin": MKL_BIN
        },
        "notes": "build did not find the exact frozen layered import/runtime closure"
    });
    result["diagnostics"] = json!([
        "No backend rank is inferred.",
        "No substitute BLAS/LAPACK implementation was silently used."
    ]);
    result
}

#[cfg(all(windows, rapidrbf_exact_mkl))]
fn run_exact(context: &AttemptContext) -> Value {
    const COL_MAJOR: i32 = 102;
    const LOWER: i8 = b'L' as i8;
    const NO_TRANSPOSE: i8 = b'N' as i8;
    const PEAK_DISABLE: i32 = 0;
    const PEAK_ENABLE: i32 = 1;
    const PEAK_RESET: i32 = -1;
    const PEAK_QUERY: i32 = 2;

    let mut result = attempt_base(context, "onemkl-lp64-sequential");
    let n = context.n;
    if n > i32::MAX as usize {
        result["attempt_state"] = json!("EVIDENCE_MISSING");
        result["diagnostics"] = json!(["matrix order exceeds frozen LP64 lapack_int"]);
        return result;
    }

    let mut version_buffer = vec![0_i8; 256];
    let previous_local_threads;
    unsafe {
        MKL_Set_Dynamic(0);
        previous_local_threads = MKL_Set_Num_Threads_Local(1);
        MKL_Get_Version_String(version_buffer.as_mut_ptr(), version_buffer.len() as i32);
    }
    let version_length = version_buffer
        .iter()
        .position(|&byte| byte == 0)
        .unwrap_or(version_buffer.len());
    let version_bytes: Vec<u8> = version_buffer[..version_length]
        .iter()
        .map(|&byte| byte as u8)
        .collect();
    let backend_version = String::from_utf8_lossy(&version_bytes).trim().to_owned();
    result["backend_version"] = json!(&backend_version);
    if backend_version != EXPECTED_MKL_VERSION {
        unsafe {
            MKL_Free_Buffers();
            MKL_Set_Num_Threads_Local(previous_local_threads);
        }
        result["attempt_state"] = json!("EVIDENCE_MISSING");
        result["factor"] = json!({
            "status": "NOT_RUN: exact oneMKL runtime version gate failed",
            "pivot_diagnostics": null,
            "reconstruction_relative_inf": null,
            "reconstruction_status": "EVIDENCE_MISSING"
        });
        result["solve"] = json!({
            "status": "NOT_RUN",
            "reduced_backward_error": null
        });
        result["packing"] = json!({
            "capability": "NOT_RUN",
            "roundtrip_tested": false,
            "packed_bytes": null
        });
        result["resources"] = json!({
            "retained_bytes": null,
            "transient_peak_delta_bytes": null,
            "temp_storage_bytes": 0,
            "thread_ownership": "NOT_MATERIALIZED: runtime rejected before factorization",
            "caller_thread_lease_materialized": false,
            "requested_threads": 1,
            "observed_threads": null
        });
        result["artifact_closure"] = json!({
            "state": "RUNTIME_VERSION_MISMATCH",
            "coordinates": {
                "expected_runtime_version": EXPECTED_MKL_VERSION,
                "observed_runtime_version": backend_version,
                "interface": "LP64",
                "threading": "sequential",
                "root": MKL_ROOT,
                "lib": MKL_LIB,
                "bin": MKL_BIN
            },
            "notes": "registered files were hash-gated at build time, but the loaded runtime identity did not match"
        });
        result["diagnostics"] = json!([
            "No LAPACK entry point was called after the exact runtime-version gate failed.",
            "No substitute BLAS/LAPACK implementation was accepted."
        ]);
        return result;
    }

    let (peak_enable_status, peak_reset_status) = unsafe {
        (
            MKL_Peak_Mem_Usage(PEAK_ENABLE),
            MKL_Peak_Mem_Usage(PEAK_RESET),
        )
    };

    // LAPACKE's column-major entry point gets a complete private copy. The
    // corpus remains row-major and immutable in AttemptContext.
    let mut factor = vec![0.0; n * n];
    for row in 0..n {
        for column in 0..n {
            factor[column * n + row] = context.b[row * n + column];
        }
    }
    let mut pivots = vec![0_i32; n];
    let mut work_query = [0.0_f64; 1];
    let query_info = unsafe {
        LAPACKE_dsytrf_work(
            COL_MAJOR,
            LOWER,
            n as i32,
            factor.as_mut_ptr(),
            n as i32,
            pivots.as_mut_ptr(),
            work_query.as_mut_ptr(),
            -1,
        )
    };
    let lwork = if query_info == 0 && work_query[0].is_finite() {
        work_query[0].ceil().max(1.0).min(i32::MAX as f64) as i32
    } else {
        1
    };
    let mut workspace = vec![0.0_f64; lwork as usize];
    let factor_info = unsafe {
        LAPACKE_dsytrf_work(
            COL_MAJOR,
            LOWER,
            n as i32,
            factor.as_mut_ptr(),
            n as i32,
            pivots.as_mut_ptr(),
            workspace.as_mut_ptr(),
            lwork,
        )
    };

    let primary_factor_finite = vector_finite(&factor);
    let mut active_factor_finite = primary_factor_finite;
    let mut solution = context.rhs.clone();
    let mut route = "dsytrf/dsytrs";
    let mut solve_info = if factor_info == 0 && primary_factor_finite {
        unsafe {
            LAPACKE_dsytrs_work(
                COL_MAJOR,
                LOWER,
                n as i32,
                1,
                factor.as_ptr(),
                n as i32,
                pivots.as_ptr(),
                solution.as_mut_ptr(),
                n as i32,
            )
        }
    } else {
        i32::MIN
    };

    // A concrete LAPACK failure or non-finite solve is a stable failure gate.
    // The LU attempt receives a new copy of A and RHS, never the dsytrf buffer.
    let mut fallback_info = None;
    let mut fallback_pivots = Vec::new();
    if factor_info != 0 || solve_info != 0 || !vector_finite(&solution) {
        route = "fresh-dgetrf/dgetrs-fallback";
        factor = vec![0.0; n * n];
        for row in 0..n {
            for column in 0..n {
                factor[column * n + row] = context.b[row * n + column];
            }
        }
        solution.clone_from(&context.rhs);
        fallback_pivots = vec![0_i32; n];
        let lu_info = unsafe {
            LAPACKE_dgetrf_work(
                COL_MAJOR,
                n as i32,
                n as i32,
                factor.as_mut_ptr(),
                n as i32,
                fallback_pivots.as_mut_ptr(),
            )
        };
        active_factor_finite = vector_finite(&factor);
        fallback_info = Some(lu_info);
        solve_info = if lu_info == 0 && active_factor_finite {
            unsafe {
                LAPACKE_dgetrs_work(
                    COL_MAJOR,
                    NO_TRANSPOSE,
                    n as i32,
                    1,
                    factor.as_ptr(),
                    n as i32,
                    fallback_pivots.as_ptr(),
                    solution.as_mut_ptr(),
                    n as i32,
                )
            }
        } else {
            i32::MIN
        };
    }

    let active_factor_info = fallback_info.unwrap_or(factor_info);
    let solution_values_finite = vector_finite(&solution);
    let solution_usable = active_factor_info == 0
        && active_factor_finite
        && solve_info == 0
        && solution_values_finite;
    let residual = if solution_usable {
        Some(backward_error(&context.b, &solution, &context.rhs, n))
    } else {
        None
    };
    let mut one_by_one = 0_usize;
    let mut two_by_two = 0_usize;
    let mut cursor = 0;
    while cursor < pivots.len() {
        if pivots[cursor] > 0 {
            one_by_one += 1;
            cursor += 1;
        } else if cursor + 1 < pivots.len() && pivots[cursor + 1] == pivots[cursor] {
            two_by_two += 1;
            cursor += 2;
        } else {
            cursor += 1;
        }
    }
    let fallback_row_swaps = fallback_pivots
        .iter()
        .enumerate()
        .filter(|(index, pivot)| **pivot != (*index as i32 + 1))
        .count();
    let packing_capability = if fallback_info.is_some() {
        "full-column-major-combined-LU-plus-IPIV"
    } else {
        "lower-triangle-BK-factor-plus-IPIV; dsytrs requires full-n-by-n unpack"
    };
    let (packed_bytes, packed_hash) = if !active_factor_finite {
        (None, None)
    } else if fallback_info.is_some() {
        (
            Some(
                n.saturating_mul(n)
                    .saturating_mul(8)
                    .saturating_add(n.saturating_mul(4)),
            ),
            Some(native_factor_bytes_hash(
                factor.iter().copied(),
                fallback_pivots.iter().copied(),
            )),
        )
    } else {
        (
            Some(
                n.saturating_mul(n + 1)
                    .saturating_div(2)
                    .saturating_mul(8)
                    .saturating_add(n.saturating_mul(4)),
            ),
            Some(native_factor_bytes_hash(
                (0..n).flat_map(|column| {
                    let factor_ref = &factor;
                    (column..n).map(move |row| factor_ref[column * n + row])
                }),
                pivots.iter().copied(),
            )),
        )
    };

    let mut buffers_before_free = 0_i32;
    let (mkl_live_before_free, mkl_peak_before_free, max_threads) = unsafe {
        (
            MKL_Mem_Stat(&mut buffers_before_free),
            MKL_Peak_Mem_Usage(PEAK_QUERY),
            MKL_Get_Max_Threads(),
        )
    };
    let mut buffers_after_free = 0_i32;
    let (mkl_live_after_free, mkl_peak_after_free, peak_disable_status) = unsafe {
        MKL_Free_Buffers();
        let live = MKL_Mem_Stat(&mut buffers_after_free);
        let peak = MKL_Peak_Mem_Usage(PEAK_QUERY);
        let disable = MKL_Peak_Mem_Usage(PEAK_DISABLE);
        (live, peak, disable)
    };
    unsafe {
        MKL_Set_Num_Threads_Local(previous_local_threads);
    }

    let attempt_state = if !active_factor_finite || (solve_info == 0 && !solution_values_finite) {
        "COLLECTED_NONFINITE"
    } else if active_factor_info != 0 || solve_info != 0 {
        "COLLECTED_BACKEND_ERROR"
    } else {
        "COLLECTED"
    };
    result["attempt_state"] = json!(attempt_state);
    result["finite_gate"] = json!({
        "input": true,
        "factor": active_factor_finite,
        "primary_bk_factor": primary_factor_finite,
        "active_factor": active_factor_finite,
        "solution": solution_usable,
        "solution_values_finite": solution_values_finite
    });
    result["factor"] = json!({
        "status": {
            "route": route,
            "dsytrf_info": factor_info,
            "fallback_dgetrf_info": fallback_info,
            "active_factor_info": active_factor_info,
            "primary_bk_factor_finite": primary_factor_finite,
            "active_factor_finite": active_factor_finite,
            "workspace_query_info": query_info
        },
        "pivot_diagnostics": {
            "primary_bk": {
                "encoding": "LAPACK_DSYTRF_IPIV",
                "one_by_one_blocks": one_by_one,
                "two_by_two_blocks": two_by_two,
                "raw_count": pivots.len()
            },
            "active_fallback_lu": if fallback_info.is_some() {
                json!({
                    "encoding": "LAPACK_DGETRF_ROW_IPIV",
                    "factor_finite": active_factor_finite,
                    "row_swap_entries": fallback_row_swaps,
                    "raw_count": fallback_pivots.len()
                })
            } else {
                Value::Null
            },
            "semantic_rank_authority": false
        },
        "reconstruction_relative_inf": null,
        "reconstruction_status": "EVIDENCE_MISSING: independent active LAPACK packed-factor reconstruction not materialized"
    });
    result["solve"] = json!({
        "status": {
            "route": route,
            "lapack_info": solve_info,
            "finite": solution_values_finite,
            "usable": solution_usable
        },
        "reduced_backward_error": residual.map(finite_number)
    });
    result["packing"] = json!({
        "capability": packing_capability,
        "eligibility": if active_factor_finite {
            "ELIGIBLE_FINITE_ACTIVE_FACTOR"
        } else {
            "REJECTED_NONFINITE_ACTIVE_FACTOR"
        },
        "rejection_reason": if active_factor_finite {
            Value::Null
        } else {
            json!("active LAPACK factor buffer contains NaN or Inf")
        },
        "roundtrip_tested": false,
        "packed_bytes": packed_bytes,
        "byte_encoding": "f64 little-endian values followed by i32 little-endian LAPACK IPIV",
        "component_sha256": packed_hash
    });
    result["resources"] = json!({
        "source_immutable_bytes": source_resource_ledger(context),
        "factor_retained_bytes": n.saturating_mul(n).saturating_mul(8)
            .saturating_add(n.saturating_mul(4)),
        "retained_bytes": n.saturating_mul(n).saturating_mul(8)
            .saturating_add(n.saturating_mul(4)),
        "transient_peak_delta_bytes": nonnegative_mkl_bytes(mkl_peak_before_free),
        "transient_peak_measurement": "oneMKL allocator diagnostic only; excludes Rust-owned pristine/factor vectors",
        "mkl_peak_control": {
            "enable_status": peak_enable_status,
            "reset_status": peak_reset_status,
            "query_before_free_bytes": nonnegative_mkl_bytes(mkl_peak_before_free),
            "query_after_free_bytes": nonnegative_mkl_bytes(mkl_peak_after_free),
            "disable_status": peak_disable_status,
            "missing_sentinel": -1
        },
        "memory_scratch_bytes": (lwork as usize).saturating_mul(8),
        "packed_solve_unpack_scratch_bytes": n.saturating_mul(n).saturating_mul(8),
        "temp_storage_bytes": 0,
        "temp_storage_writes": 0,
        "temp_storage_residue_bytes": 0,
        "mkl_allocator_before_free": {
            "live_bytes": nonnegative_mkl_bytes(mkl_live_before_free),
            "buffers": buffers_before_free
        },
        "mkl_allocator_after_free": {
            "live_bytes": nonnegative_mkl_bytes(mkl_live_after_free),
            "buffers": buffers_after_free
        },
        "thread_ownership": "MKL local thread limit requested; no caller concurrency lease is implemented",
        "caller_thread_lease_materialized": false,
        "requested_threads": 1,
        "backend_effective_threads": max_threads,
        "observed_threads": crate::observed_thread_count(),
        "backend_reported_max_threads": max_threads,
        "maximum_live_threads": "EVIDENCE_MISSING"
    });
    result["artifact_closure"] = json!({
        "state": "PACKAGING_COUNTEREXAMPLE",
        "coordinates": {
            "version": "oneMKL 2023.0.0#2",
            "runtime_version": EXPECTED_MKL_VERSION,
            "interface": "LP64",
            "threading": "sequential",
            "root": MKL_ROOT,
            "lib": MKL_LIB,
            "bin": MKL_BIN
        },
        "notes": "exact layered comparator only; runtime dispatch closure and provenance remain outside tier-one acceptance"
    });
    result["diagnostics"] = json!([
        "Fresh original A/RHS is used for the LU fallback.",
        "IPIV/factor info is diagnostic only and never supplies semantic rank.",
        "Factor reconstruction is explicitly missing; solve residual alone is not factor publication.",
        "MKL_Set_Num_Threads_Local(1) is a backend-local limit, not a caller-owned concurrency lease."
    ]);
    attach_full_correction(&mut result, context, solution_usable.then_some(&solution));
    result
}

#[cfg(all(windows, rapidrbf_exact_mkl))]
fn native_factor_bytes_hash(
    floating: impl IntoIterator<Item = f64>,
    pivots: impl IntoIterator<Item = i32>,
) -> String {
    let mut digest = Sha256::new();
    for value in floating {
        digest.update(value.to_le_bytes());
    }
    for pivot in pivots {
        digest.update(pivot.to_le_bytes());
    }
    format!("{:x}", digest.finalize())
}

#[cfg(all(windows, rapidrbf_exact_mkl))]
fn nonnegative_mkl_bytes(value: i64) -> Option<u64> {
    u64::try_from(value).ok()
}
