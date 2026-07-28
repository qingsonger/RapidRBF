//! THROWAWAY PROTOTYPE: replay frozen RapidRBF factor inputs through pinned
//! substrates. Backend health is evidence, never semantic rank authority.

mod native;

use std::alloc::{GlobalAlloc, Layout, System};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::sync::atomic::{AtomicU64, Ordering};

use faer::linalg::solvers::{Lblt as FaerLblt, Llt as FaerLlt, PartialPivLu as FaerLu};
use faer::prelude::{Mat as FaerMat, Par, Solve};
use nalgebra::{DMatrix, DVector};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

const OUTPUT_SCHEMA: &str = "rapidrbf-dense-factor-replay-v1";
const ATTEMPT_SCHEMA: &str = "rapidrbf-factor-attempt-v1";
const EXPECTED_CAPTURE_SCHEMA: &str = "rapidrbf-dense-factor-corpus-v1";
const EXPECTED_LOCK_SCHEMA: &str = "rapidrbf-dense-factor-corpus-lock-v2";
const BACKENDS: [&str; 3] = ["faer", "nalgebra", "mkl"];

struct TrackingAllocator;

static LIVE_ALLOCATED: AtomicU64 = AtomicU64::new(0);
static PEAK_ALLOCATED: AtomicU64 = AtomicU64::new(0);

#[global_allocator]
static ALLOCATOR: TrackingAllocator = TrackingAllocator;

unsafe impl GlobalAlloc for TrackingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let pointer = unsafe { System.alloc(layout) };
        if !pointer.is_null() {
            allocation_added(layout.size() as u64);
        }
        pointer
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let pointer = unsafe { System.alloc_zeroed(layout) };
        if !pointer.is_null() {
            allocation_added(layout.size() as u64);
        }
        pointer
    }

    unsafe fn dealloc(&self, pointer: *mut u8, layout: Layout) {
        unsafe { System.dealloc(pointer, layout) };
        LIVE_ALLOCATED.fetch_sub(layout.size() as u64, Ordering::Relaxed);
    }

    unsafe fn realloc(&self, pointer: *mut u8, old: Layout, new_size: usize) -> *mut u8 {
        let replacement = unsafe { System.realloc(pointer, old, new_size) };
        if !replacement.is_null() {
            if new_size >= old.size() {
                allocation_added((new_size - old.size()) as u64);
            } else {
                LIVE_ALLOCATED.fetch_sub((old.size() - new_size) as u64, Ordering::Relaxed);
            }
        }
        replacement
    }
}

fn allocation_added(bytes: u64) {
    let live = LIVE_ALLOCATED.fetch_add(bytes, Ordering::Relaxed) + bytes;
    let mut peak = PEAK_ALLOCATED.load(Ordering::Relaxed);
    while live > peak {
        match PEAK_ALLOCATED.compare_exchange_weak(peak, live, Ordering::Relaxed, Ordering::Relaxed)
        {
            Ok(_) => break,
            Err(observed) => peak = observed,
        }
    }
}

struct AllocationWindow {
    baseline: u64,
}

impl AllocationWindow {
    fn begin() -> Self {
        let baseline = LIVE_ALLOCATED.load(Ordering::Relaxed);
        PEAK_ALLOCATED.store(baseline, Ordering::Relaxed);
        Self { baseline }
    }

    fn peak_delta(&self) -> u64 {
        PEAK_ALLOCATED
            .load(Ordering::Relaxed)
            .saturating_sub(self.baseline)
    }
}

#[derive(Clone, Deserialize)]
struct CaptureManifest {
    schema: String,
    generator: String,
    polatory_commit: String,
    compiler: String,
    eigen_version: String,
    little_endian: bool,
    double_bytes: usize,
    records: Vec<CaptureRecord>,
}

#[derive(Clone, Deserialize, Serialize)]
struct LockedFile {
    bytes: u64,
    sha256: String,
}

#[derive(Deserialize)]
struct CorpusLock {
    schema: String,
    capture_schema: String,
    hash_algorithm: String,
    corpus_sha256: String,
    record_count: usize,
    referenced_payload_count: usize,
    files: BTreeMap<String, LockedFile>,
    generator_provenance: Value,
    native_artifacts: Value,
}

struct VerifiedCorpus {
    corpus_sha256: String,
    manifest_sha256: String,
    files: BTreeMap<String, LockedFile>,
}

#[derive(Clone, Deserialize)]
pub(crate) struct CaptureRecord {
    record_id: String,
    panel_id: String,
    case_id: String,
    role: String,
    assembly_variant: String,
    assembly_authority: String,
    matrix_kind: String,
    registered_rank_expectation: String,
    semantic_rank_state: String,
    scalar_order: usize,
    polynomial_order: usize,
    reduced_order: usize,
    files: BTreeMap<String, String>,
}

pub(crate) struct AttemptContext {
    record: CaptureRecord,
    manifest_dir: PathBuf,
    n: usize,
    b: Vec<f64>,
    rhs: Vec<f64>,
    a_full: Vec<f64>,
    p_full: Vec<f64>,
    q_top: Vec<f64>,
    rhs_full: Vec<f64>,
    p_top: Vec<f64>,
    b_sha256: String,
    rhs_sha256: String,
    corpus_sha256: String,
}

impl AttemptContext {
    fn load(
        manifest_path: &Path,
        record: CaptureRecord,
        corpus_sha256: String,
    ) -> Result<Self, String> {
        let manifest_dir = manifest_path
            .parent()
            .ok_or_else(|| "manifest has no parent directory".to_owned())?
            .to_owned();
        let n = record.reduced_order;
        let scalar = record.scalar_order;
        let polynomial = record.polynomial_order;
        if scalar != n.saturating_add(polynomial) {
            return Err(format!(
                "{} has scalar_order != reduced_order + polynomial_order",
                record.record_id
            ));
        }
        let b_path = record_file(&manifest_dir, &record, "b_lower")?;
        let rhs_path = record_file(&manifest_dir, &record, "rhs_reduced")?;
        let b_bytes = read_exact_file(&b_path, triangular_count(n).saturating_mul(8))?;
        let rhs_bytes = read_exact_file(&rhs_path, n.saturating_mul(8))?;
        let b_lower = decode_f64(&b_bytes)?;
        let b = expand_lower(&b_lower, n)?;
        let rhs = decode_f64(&rhs_bytes)?;

        let a_full = load_lower(&record_file(&manifest_dir, &record, "a_lower")?, scalar)?;
        let p_full = load_f64_count(
            &record_file(&manifest_dir, &record, "p_row_major")?,
            scalar.saturating_mul(polynomial),
        )?;
        let q_top = load_f64_count(
            &record_file(&manifest_dir, &record, "q_top_row_major")?,
            polynomial.saturating_mul(n),
        )?;
        let rhs_full = load_f64_count(&record_file(&manifest_dir, &record, "rhs_full")?, scalar)?;
        let p_top = load_f64_count(
            &record_file(&manifest_dir, &record, "polynomial_p_top")?,
            polynomial.saturating_mul(polynomial),
        )?;

        Ok(Self {
            record,
            manifest_dir,
            n,
            b,
            rhs,
            a_full,
            p_full,
            q_top,
            rhs_full,
            p_top,
            b_sha256: sha256_bytes(&b_bytes),
            rhs_sha256: sha256_bytes(&rhs_bytes),
            corpus_sha256,
        })
    }

    fn synthetic(control_id: &str, corpus_sha256: String) -> Result<Self, String> {
        let (b, rhs, semantic_rank_state) = match control_id {
            "M4-derived-exact-rank-fail" => (
                vec![
                    1.0, 0.0, 0.0, 0.0, //
                    0.0, 1.0, 0.0, 0.0, //
                    0.0, 0.0, 1.0, 0.0, //
                    0.0, 0.0, 0.0, 0.0,
                ],
                vec![1.0, 2.0, 3.0, 4.0],
                "rank_fail",
            ),
            "M4-derived-nan-matrix" => (
                vec![f64::NAN, 0.0, 0.0, 1.0],
                vec![1.0, 1.0],
                "preflight_nonfinite",
            ),
            "M4-derived-infinite-rhs" => (
                vec![1.0, 0.0, 0.0, 1.0],
                vec![f64::INFINITY, 1.0],
                "preflight_nonfinite",
            ),
            _ => return Err(format!("unknown derived control {control_id}")),
        };
        let n = rhs.len();
        let b_sha256 = sha256_f64(&b);
        let rhs_sha256 = sha256_f64(&rhs);
        Ok(Self {
            record: CaptureRecord {
                record_id: control_id.to_owned(),
                panel_id: "M4-DERIVED-CONTROL".to_owned(),
                case_id: control_id.to_owned(),
                role: "derived-control".to_owned(),
                assembly_variant: "not-applicable".to_owned(),
                assembly_authority: "diagnostic-force-replay-only".to_owned(),
                matrix_kind: "symmetric-derived-control".to_owned(),
                registered_rank_expectation: "not-applicable-derived-control".to_owned(),
                semantic_rank_state: semantic_rank_state.to_owned(),
                scalar_order: n,
                polynomial_order: 0,
                reduced_order: n,
                files: BTreeMap::new(),
            },
            manifest_dir: PathBuf::from("<synthetic-control>"),
            n,
            b: b.clone(),
            rhs: rhs.clone(),
            a_full: b,
            p_full: Vec::new(),
            q_top: Vec::new(),
            rhs_full: rhs,
            p_top: Vec::new(),
            b_sha256,
            rhs_sha256,
            corpus_sha256,
        })
    }
}

#[derive(Default)]
struct Options {
    manifest: Option<PathBuf>,
    output: Option<PathBuf>,
    backend: Option<String>,
    record: Option<String>,
    control: Option<String>,
    verified_corpus_sha256: Option<String>,
    worker: bool,
}

fn main() -> ExitCode {
    match real_main() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("dense-factor replay: {error}");
            ExitCode::from(2)
        }
    }
}

fn real_main() -> Result<(), String> {
    let arguments: Vec<String> = env::args().skip(1).collect();
    if arguments
        .iter()
        .any(|argument| argument == "-h" || argument == "--help")
    {
        println!("{}", usage());
        return Ok(());
    }
    let options = parse_options(arguments)?;
    let manifest_path = options
        .manifest
        .as_deref()
        .ok_or_else(usage)?
        .canonicalize()
        .map_err(|error| format!("cannot canonicalize manifest: {error}"))?;
    let (manifest, manifest_bytes) = read_manifest(&manifest_path)?;
    let verified_corpus =
        verify_locked_corpus(&manifest_path, &manifest, &manifest_bytes, !options.worker)?;

    if options.worker {
        let expected_corpus_sha256 = options
            .verified_corpus_sha256
            .as_deref()
            .ok_or_else(|| "worker requires --verified-corpus-sha256".to_owned())?;
        if expected_corpus_sha256 != verified_corpus.corpus_sha256 {
            return Err(format!(
                "worker corpus binding mismatch: parent verified {expected_corpus_sha256}, \
                 sibling lock verifies {}",
                verified_corpus.corpus_sha256
            ));
        }
        let backend = options
            .backend
            .as_deref()
            .ok_or_else(|| "worker requires --backend".to_owned())?;
        let context = if let Some(control_id) = options.control.as_deref() {
            AttemptContext::synthetic(control_id, verified_corpus.corpus_sha256.clone())?
        } else {
            let record_id = options
                .record
                .as_deref()
                .ok_or_else(|| "worker requires --record or --control".to_owned())?;
            let record = manifest
                .records
                .iter()
                .find(|record| record.record_id == record_id)
                .cloned()
                .ok_or_else(|| format!("unknown record {record_id}"))?;
            verify_record_payloads(
                manifest_path
                    .parent()
                    .ok_or_else(|| "manifest has no parent directory".to_owned())?,
                &record,
                &verified_corpus.files,
            )?;
            AttemptContext::load(
                &manifest_path,
                record,
                verified_corpus.corpus_sha256.clone(),
            )?
        };
        let attempt = catch_unwind(AssertUnwindSafe(|| run_backend(backend, &context)))
            .unwrap_or_else(|payload| panic_attempt(backend, &context, payload));
        println!(
            "{}",
            serde_json::to_string(&attempt)
                .map_err(|error| format!("cannot serialize worker result: {error}"))?
        );
        return Ok(());
    }

    let selected_backends: Vec<&str> = match options.backend.as_deref() {
        Some(backend) => {
            validate_backend(backend)?;
            vec![
                BACKENDS
                    .iter()
                    .copied()
                    .find(|candidate| *candidate == backend)
                    .expect("validated backend"),
            ]
        }
        None => BACKENDS.to_vec(),
    };
    let selected_records: Vec<&CaptureRecord> = manifest
        .records
        .iter()
        .filter(|record| {
            options
                .record
                .as_deref()
                .is_none_or(|selected| selected == record.record_id)
        })
        .collect();
    if selected_records.is_empty() {
        return Err(format!(
            "record filter {:?} matched no capture record",
            options.record
        ));
    }

    let executable =
        env::current_exe().map_err(|error| format!("cannot locate current executable: {error}"))?;
    let mut attempts = Vec::new();
    for record in selected_records {
        for backend in &selected_backends {
            attempts.push(spawn_worker(
                &executable,
                &manifest_path,
                &verified_corpus.corpus_sha256,
                backend,
                record,
            ));
        }
    }

    let summary = json!({
        "schema": OUTPUT_SCHEMA,
        "corpus": {
            "manifest_path": manifest_path,
            "sha256": verified_corpus.corpus_sha256,
            "corpus_sha256": verified_corpus.corpus_sha256,
            "manifest_sha256": verified_corpus.manifest_sha256,
            "lock_schema": EXPECTED_LOCK_SCHEMA,
            "capture_schema": manifest.schema,
            "generator": manifest.generator,
            "polatory_commit": manifest.polatory_commit,
            "compiler": manifest.compiler,
            "eigen_version": manifest.eigen_version,
            "record_count": manifest.records.len(),
            "m3_assembly_audit": m3_assembly_audit(&manifest_path, &manifest.records)
        },
        "policy": {
            "factor_health_profile": Value::Null,
            "selection": "UNJUDGED",
            "selection_reason": "FactorHealthProfile{id,hash} was not supplied",
            "semantic_rank_source": "NOT_INFERRED_FROM_BACKENDS",
            "backend_status_role": "factor-health/fallback diagnostic only",
            "parallelism": "one fresh worker process per backend/record; workers execute sequentially"
        },
        "attempts": attempts,
        "controls": derived_controls(
            &executable,
            &manifest_path,
            &verified_corpus.corpus_sha256
        )
    });
    let serialized = serde_json::to_string_pretty(&summary)
        .map_err(|error| format!("cannot serialize summary: {error}"))?;
    if let Some(output) = options.output {
        if let Some(parent) = output.parent().filter(|path| !path.as_os_str().is_empty()) {
            fs::create_dir_all(parent)
                .map_err(|error| format!("cannot create {}: {error}", parent.display()))?;
        }
        fs::write(&output, format!("{serialized}\n"))
            .map_err(|error| format!("cannot write {}: {error}", output.display()))?;
        println!(
            "{}",
            json!({
                "schema": OUTPUT_SCHEMA,
                "status": "written",
                "output": output,
                "attempt_count": summary["attempts"].as_array().map_or(0, Vec::len),
                "selection": "UNJUDGED"
            })
        );
    } else {
        println!("{serialized}");
    }
    Ok(())
}

fn parse_options(arguments: Vec<String>) -> Result<Options, String> {
    let mut options = Options::default();
    let mut cursor = 0;
    if arguments
        .first()
        .is_some_and(|argument| argument == "--worker")
    {
        options.worker = true;
        cursor += 1;
    }
    while cursor < arguments.len() {
        match arguments[cursor].as_str() {
            "--output" => {
                cursor += 1;
                options.output = Some(PathBuf::from(
                    arguments
                        .get(cursor)
                        .ok_or_else(|| "--output requires a path".to_owned())?,
                ));
            }
            "--backend" => {
                cursor += 1;
                let backend = arguments
                    .get(cursor)
                    .ok_or_else(|| "--backend requires a value".to_owned())?;
                validate_backend(backend)?;
                options.backend = Some(backend.clone());
            }
            "--record" => {
                cursor += 1;
                options.record = Some(
                    arguments
                        .get(cursor)
                        .ok_or_else(|| "--record requires a value".to_owned())?
                        .clone(),
                );
            }
            "--control" => {
                cursor += 1;
                options.control = Some(
                    arguments
                        .get(cursor)
                        .ok_or_else(|| "--control requires a value".to_owned())?
                        .clone(),
                );
            }
            "--verified-corpus-sha256" => {
                cursor += 1;
                options.verified_corpus_sha256 = Some(
                    arguments
                        .get(cursor)
                        .ok_or_else(|| "--verified-corpus-sha256 requires a digest".to_owned())?
                        .clone(),
                );
            }
            argument if argument.starts_with('-') => {
                return Err(format!("unknown option {argument}\n{}", usage()));
            }
            argument => {
                if options.manifest.is_some() {
                    return Err(format!("unexpected positional argument {argument}"));
                }
                options.manifest = Some(PathBuf::from(argument));
            }
        }
        cursor += 1;
    }
    Ok(options)
}

fn usage() -> String {
    "usage: rapidrbf-dense-factor-replay-throwaway [--worker] MANIFEST \
     [--output SUMMARY.json] [--backend faer|nalgebra|mkl] [--record RECORD_ID]"
        .to_owned()
}

fn validate_backend(backend: &str) -> Result<(), String> {
    if BACKENDS.contains(&backend) {
        Ok(())
    } else {
        Err(format!("unknown backend {backend}"))
    }
}

fn read_manifest(path: &Path) -> Result<(CaptureManifest, Vec<u8>), String> {
    let bytes =
        fs::read(path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
    let manifest: CaptureManifest = serde_json::from_slice(&bytes)
        .map_err(|error| format!("invalid manifest {}: {error}", path.display()))?;
    if manifest.schema != EXPECTED_CAPTURE_SCHEMA {
        return Err(format!(
            "capture schema {} is not {}",
            manifest.schema, EXPECTED_CAPTURE_SCHEMA
        ));
    }
    if !manifest.little_endian || manifest.double_bytes != 8 {
        return Err("capture is not little-endian IEC binary64".to_owned());
    }
    validate_capture_records(&manifest.records)?;
    Ok((manifest, bytes))
}

fn validate_capture_records(records: &[CaptureRecord]) -> Result<(), String> {
    if records.is_empty() {
        return Err("capture manifest has no records".to_owned());
    }
    let mut record_ids = BTreeSet::new();
    for record in records {
        if !record_ids.insert(record.record_id.as_str()) {
            return Err(format!("duplicate capture record id {}", record.record_id));
        }
        if !matches!(record.role.as_str(), "max-order-fine" | "level0-coarse") {
            return Err(format!(
                "{} has unsupported capture role {}",
                record.record_id, record.role
            ));
        }
        if record.matrix_kind != "symmetric_projected" {
            return Err(format!(
                "{} has unsupported matrix kind {}",
                record.record_id, record.matrix_kind
            ));
        }
        let expected = match record.assembly_variant.as_str() {
            "canonical-row-channel-map" => (
                "candidate-independent-canonical",
                "source-workload-full-rank-expectation",
                "certificate-missing",
            ),
            "frozen-literal-gradient-row-map" => (
                "research-only-frozen-compatibility",
                "none-research-only",
                "certificate-missing",
            ),
            other => {
                return Err(format!(
                    "{} has unsupported assembly variant {other}",
                    record.record_id
                ));
            }
        };
        let observed = (
            record.assembly_authority.as_str(),
            record.registered_rank_expectation.as_str(),
            record.semantic_rank_state.as_str(),
        );
        if observed != expected {
            return Err(format!(
                "{} has invalid assembly authority/rank contract tuple: \
                 ({}, {}, {}, {})",
                record.record_id,
                record.assembly_variant,
                record.assembly_authority,
                record.registered_rank_expectation,
                record.semantic_rank_state
            ));
        }
        if record.assembly_variant == "frozen-literal-gradient-row-map"
            && record.panel_id != "M3-HERMITE-COMPOSITE"
        {
            return Err(format!(
                "{} uses the research-only frozen literal variant outside M3",
                record.record_id
            ));
        }
        for relative in record.files.values() {
            validate_corpus_member(relative)?;
        }
    }
    Ok(())
}

fn verify_locked_corpus(
    manifest_path: &Path,
    manifest: &CaptureManifest,
    manifest_bytes: &[u8],
    verify_all_payloads: bool,
) -> Result<VerifiedCorpus, String> {
    let root = manifest_path
        .parent()
        .ok_or_else(|| "manifest has no parent directory".to_owned())?;
    if manifest_path.file_name().and_then(|name| name.to_str()) != Some("manifest.raw.json") {
        return Err("locked replay requires a manifest named manifest.raw.json".to_owned());
    }
    let lock_path = root.join("manifest.lock.json");
    let lock_bytes = fs::read(&lock_path)
        .map_err(|error| format!("cannot read sibling lock {}: {error}", lock_path.display()))?;
    let mut lock_value: Value = serde_json::from_slice(&lock_bytes)
        .map_err(|error| format!("invalid corpus lock {}: {error}", lock_path.display()))?;
    let lock: CorpusLock = serde_json::from_value(lock_value.clone())
        .map_err(|error| format!("invalid corpus lock {}: {error}", lock_path.display()))?;
    let lock_object = lock_value
        .as_object_mut()
        .ok_or_else(|| format!("corpus lock {} is not an object", lock_path.display()))?;
    let expected_lock_fields: BTreeSet<&str> = [
        "schema",
        "capture_schema",
        "hash_algorithm",
        "corpus_sha256",
        "record_count",
        "referenced_payload_count",
        "files",
        "generator_provenance",
        "native_artifacts",
    ]
    .into_iter()
    .collect();
    let observed_lock_fields: BTreeSet<&str> = lock_object.keys().map(String::as_str).collect();
    if observed_lock_fields != expected_lock_fields {
        return Err(format!(
            "corpus lock fields differ from the v2 contract; expected \
             {expected_lock_fields:?}, observed {observed_lock_fields:?}"
        ));
    }
    lock_object.remove("corpus_sha256");
    if lock.schema != EXPECTED_LOCK_SCHEMA {
        return Err(format!(
            "corpus lock schema {} is not {}",
            lock.schema, EXPECTED_LOCK_SCHEMA
        ));
    }
    if lock.capture_schema != manifest.schema {
        return Err(format!(
            "corpus lock capture schema {} does not match manifest {}",
            lock.capture_schema, manifest.schema
        ));
    }
    if lock.hash_algorithm != "sha256" {
        return Err(format!(
            "unsupported corpus lock hash algorithm {}",
            lock.hash_algorithm
        ));
    }
    if lock.record_count != manifest.records.len() {
        return Err(format!(
            "corpus lock record count {} does not match manifest {}",
            lock.record_count,
            manifest.records.len()
        ));
    }
    let provenance = lock
        .generator_provenance
        .as_object()
        .filter(|entries| !entries.is_empty())
        .ok_or_else(|| "corpus lock generator_provenance is empty or malformed".to_owned())?;
    for (name, identity) in provenance {
        let identity = identity
            .as_object()
            .ok_or_else(|| format!("generator provenance {name} is not an object"))?;
        let bytes = identity.get("bytes").and_then(Value::as_u64);
        let sha256 = identity.get("sha256").and_then(Value::as_str);
        if bytes.is_none() || sha256.is_none_or(|digest| !valid_sha256(digest)) {
            return Err(format!(
                "generator provenance {name} lacks a valid bytes/sha256 identity"
            ));
        }
    }
    if lock
        .native_artifacts
        .as_object()
        .is_none_or(serde_json::Map::is_empty)
    {
        return Err("corpus lock native_artifacts is empty or malformed".to_owned());
    }

    let mut referenced = BTreeSet::new();
    for record in &manifest.records {
        referenced.extend(record.files.values().cloned());
    }
    if lock.referenced_payload_count != referenced.len() {
        return Err(format!(
            "corpus lock payload count {} does not match manifest {}",
            lock.referenced_payload_count,
            referenced.len()
        ));
    }
    let mut expected_files = referenced;
    expected_files.insert("manifest.raw.json".to_owned());
    let locked_files: BTreeSet<String> = lock.files.keys().cloned().collect();
    if locked_files != expected_files {
        return Err(set_mismatch(
            "corpus lock file table does not exactly cover the manifest",
            &expected_files,
            &locked_files,
        ));
    }
    for relative in lock.files.keys() {
        validate_corpus_member(relative)?;
    }

    let canonical_digest_input = canonical_json(lock_value);
    let canonical_bytes = serde_json::to_vec(&canonical_digest_input)
        .map_err(|error| format!("cannot canonicalize corpus lock identity: {error}"))?;
    let recomputed_corpus_sha256 = sha256_bytes(&canonical_bytes);
    if !valid_sha256(&lock.corpus_sha256)
        || recomputed_corpus_sha256 != lock.corpus_sha256.to_ascii_lowercase()
    {
        return Err(format!(
            "corpus lock digest mismatch: recorded {}, recomputed {}",
            lock.corpus_sha256, recomputed_corpus_sha256
        ));
    }

    let manifest_identity = lock
        .files
        .get("manifest.raw.json")
        .expect("exact lock coverage checked");
    let manifest_sha256 = sha256_bytes(manifest_bytes);
    if manifest_identity.bytes != manifest_bytes.len() as u64
        || manifest_identity.sha256.to_ascii_lowercase() != manifest_sha256
    {
        return Err("manifest.raw.json does not match its sibling corpus lock".to_owned());
    }

    if verify_all_payloads {
        let mut expected_actual = expected_files;
        expected_actual.insert("manifest.lock.json".to_owned());
        let actual = collect_corpus_files(root)?;
        if actual != expected_actual {
            return Err(set_mismatch(
                "locked corpus contains missing or extra files",
                &expected_actual,
                &actual,
            ));
        }
        for (relative, identity) in &lock.files {
            let path = root.join(relative);
            let bytes = fs::read(&path)
                .map_err(|error| format!("cannot read locked file {}: {error}", path.display()))?;
            if bytes.len() as u64 != identity.bytes
                || sha256_bytes(&bytes) != identity.sha256.to_ascii_lowercase()
            {
                return Err(format!(
                    "locked corpus file was modified: {}",
                    path.display()
                ));
            }
        }
    }

    Ok(VerifiedCorpus {
        corpus_sha256: recomputed_corpus_sha256,
        manifest_sha256,
        files: lock.files,
    })
}

fn verify_record_payloads(
    root: &Path,
    record: &CaptureRecord,
    locked_files: &BTreeMap<String, LockedFile>,
) -> Result<(), String> {
    let mut unique = BTreeSet::new();
    unique.extend(record.files.values().map(String::as_str));
    for relative in unique {
        let identity = locked_files.get(relative).ok_or_else(|| {
            format!(
                "{} references {relative}, which is absent from the verified lock",
                record.record_id
            )
        })?;
        let path = root.join(relative);
        let bytes = fs::read(&path)
            .map_err(|error| format!("cannot read locked file {}: {error}", path.display()))?;
        if bytes.len() as u64 != identity.bytes
            || sha256_bytes(&bytes) != identity.sha256.to_ascii_lowercase()
        {
            return Err(format!(
                "worker record payload does not match verified corpus {}: {}",
                record.record_id,
                path.display()
            ));
        }
    }
    Ok(())
}

fn validate_corpus_member(relative: &str) -> Result<(), String> {
    if relative.is_empty()
        || relative.contains('\\')
        || relative.starts_with('/')
        || relative
            .split('/')
            .any(|part| part.is_empty() || part == "." || part == ".." || part.contains(':'))
    {
        Err(format!("unsafe corpus member path {relative:?}"))
    } else {
        Ok(())
    }
}

fn collect_corpus_files(root: &Path) -> Result<BTreeSet<String>, String> {
    fn visit(root: &Path, directory: &Path, output: &mut BTreeSet<String>) -> Result<(), String> {
        for entry in fs::read_dir(directory)
            .map_err(|error| format!("cannot enumerate {}: {error}", directory.display()))?
        {
            let entry = entry
                .map_err(|error| format!("cannot enumerate {}: {error}", directory.display()))?;
            let file_type = entry
                .file_type()
                .map_err(|error| format!("cannot inspect {}: {error}", entry.path().display()))?;
            if file_type.is_symlink() {
                return Err(format!(
                    "locked corpus contains a symlink: {}",
                    entry.path().display()
                ));
            }
            if file_type.is_dir() {
                visit(root, &entry.path(), output)?;
            } else if file_type.is_file() {
                let relative = entry
                    .path()
                    .strip_prefix(root)
                    .map_err(|_| format!("{} escapes corpus root", entry.path().display()))?
                    .to_string_lossy()
                    .replace('\\', "/");
                validate_corpus_member(&relative)?;
                output.insert(relative);
            }
        }
        Ok(())
    }

    let mut output = BTreeSet::new();
    visit(root, root, &mut output)?;
    Ok(output)
}

fn set_mismatch(message: &str, expected: &BTreeSet<String>, actual: &BTreeSet<String>) -> String {
    let missing: Vec<&str> = expected.difference(actual).map(String::as_str).collect();
    let extra: Vec<&str> = actual.difference(expected).map(String::as_str).collect();
    format!("{message}; missing={missing:?}; extra={extra:?}")
}

fn canonical_json(value: Value) -> Value {
    match value {
        Value::Array(values) => Value::Array(values.into_iter().map(canonical_json).collect()),
        Value::Object(values) => {
            let mut entries: Vec<(String, Value)> = values.into_iter().collect();
            entries.sort_by(|left, right| left.0.cmp(&right.0));
            let mut output = serde_json::Map::new();
            for (key, value) in entries {
                output.insert(key, canonical_json(value));
            }
            Value::Object(output)
        }
        scalar => scalar,
    }
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn spawn_worker(
    executable: &Path,
    manifest_path: &Path,
    corpus_sha256: &str,
    backend: &str,
    record: &CaptureRecord,
) -> Value {
    let output = Command::new(executable)
        .arg("--worker")
        .arg(manifest_path)
        .arg("--backend")
        .arg(backend)
        .arg("--record")
        .arg(&record.record_id)
        .arg("--verified-corpus-sha256")
        .arg(corpus_sha256)
        .env("OMP_NUM_THREADS", "1")
        .env("MKL_NUM_THREADS", "1")
        .env("MKL_DYNAMIC", "FALSE")
        .output();
    match output {
        Ok(output) if output.status.success() => {
            parse_bound_worker_attempt(&output.stdout, &record.record_id, backend, corpus_sha256)
                .unwrap_or_else(|error| {
                    missing_worker_attempt(backend, record, corpus_sha256, error)
                })
        }
        Ok(output) => missing_worker_attempt(
            backend,
            record,
            corpus_sha256,
            format!(
                "worker exit {:?}: {}",
                output.status.code(),
                String::from_utf8_lossy(&output.stderr).trim()
            ),
        ),
        Err(error) => missing_worker_attempt(
            backend,
            record,
            corpus_sha256,
            format!("cannot start worker: {error}"),
        ),
    }
}

fn spawn_control_worker(
    executable: &Path,
    manifest_path: &Path,
    corpus_sha256: &str,
    backend: &str,
    control_id: &str,
) -> Value {
    let output = Command::new(executable)
        .arg("--worker")
        .arg(manifest_path)
        .arg("--backend")
        .arg(backend)
        .arg("--control")
        .arg(control_id)
        .arg("--verified-corpus-sha256")
        .arg(corpus_sha256)
        .env("OMP_NUM_THREADS", "1")
        .env("MKL_NUM_THREADS", "1")
        .env("MKL_DYNAMIC", "FALSE")
        .output();
    match output {
        Ok(output) if output.status.success() => {
            parse_bound_worker_attempt(&output.stdout, control_id, backend, corpus_sha256)
                .unwrap_or_else(|error| {
                    missing_control_attempt(backend, control_id, corpus_sha256, error)
                })
        }
        Ok(output) => missing_control_attempt(
            backend,
            control_id,
            corpus_sha256,
            format!(
                "control worker exit {:?}: {}",
                output.status.code(),
                String::from_utf8_lossy(&output.stderr).trim()
            ),
        ),
        Err(error) => missing_control_attempt(
            backend,
            control_id,
            corpus_sha256,
            format!("cannot start control worker: {error}"),
        ),
    }
}

fn parse_bound_worker_attempt(
    bytes: &[u8],
    expected_record_id: &str,
    backend: &str,
    expected_corpus_sha256: &str,
) -> Result<Value, String> {
    let attempt: Value = serde_json::from_slice(bytes)
        .map_err(|error| format!("worker returned invalid JSON: {error}"))?;
    if attempt["schema"] != ATTEMPT_SCHEMA {
        return Err(format!(
            "worker attempt schema {:?} is not {ATTEMPT_SCHEMA}",
            attempt["schema"]
        ));
    }
    if attempt["record_id"] != expected_record_id {
        return Err(format!(
            "worker returned record {:?}; expected {expected_record_id}",
            attempt["record_id"]
        ));
    }
    let expected_backend = backend_display_name(backend);
    if attempt["backend"] != expected_backend {
        return Err(format!(
            "worker returned backend {:?}; expected {expected_backend}",
            attempt["backend"]
        ));
    }
    if attempt["input_identity"]["corpus_sha256"] != expected_corpus_sha256 {
        return Err("worker attempt is not bound to the parent-verified corpus digest".to_owned());
    }
    if attempt.get("collection_state").is_none() || attempt.get("factor_state").is_none() {
        return Err("worker attempt lacks collection_state or factor_state".to_owned());
    }
    Ok(attempt)
}

fn run_backend(backend: &str, context: &AttemptContext) -> Value {
    let mut result = if !matrix_finite(&context.b) || !vector_finite(&context.rhs) {
        let mut result = attempt_base(context, backend_display_name(backend));
        result["attempt_state"] = json!("REJECTED_NONFINITE");
        result["finite_gate"] = json!({
            "input": false,
            "factor": null,
            "solution": null
        });
        result["diagnostics"] =
            json!(["preflight rejected non-finite B/RHS before any factor call"]);
        result
    } else {
        match backend {
            "faer" => run_faer(context),
            "nalgebra" => run_nalgebra(context),
            "mkl" => native::run(context),
            _ => unreachable!("backend validated by CLI"),
        }
    };
    normalize_attempt_states(&mut result);
    result
}

fn backend_display_name(backend: &str) -> &str {
    match backend {
        "faer" => "faer",
        "nalgebra" => "nalgebra",
        "mkl" => "onemkl-lp64-sequential",
        other => other,
    }
}

fn normalize_attempt_states(result: &mut Value) {
    let observed = result["attempt_state"]
        .as_str()
        .unwrap_or("EVIDENCE_MISSING")
        .to_owned();
    let (collection_state, normalized_factor_state) = match observed.as_str() {
        "EVIDENCE_MISSING" => ("EVIDENCE_MISSING", "BackendUnavailable"),
        "PANIC" => ("COLLECTED", "ContractViolation"),
        "REJECTED_NONFINITE" => ("COLLECTED", "NOT_RUN"),
        "COLLECTED" => ("COLLECTED", "Factored"),
        "COLLECTED_NONFINITE" => ("COLLECTED", "NonFiniteOutput"),
        "COLLECTED_BACKEND_ERROR" | "COLLECTED_BACKEND_FAILURE" => (
            "COLLECTED",
            if positive_lapack_pivot_info(result) {
                "SingularPivot"
            } else {
                "NumericalBreakdown"
            },
        ),
        state if state.starts_with("COLLECTED") => ("COLLECTED", "NumericalBreakdown"),
        _ => ("EVIDENCE_MISSING", "ContractViolation"),
    };
    result["collection_state"] = json!(collection_state);
    result["factor_state"] = json!({
        "normalized": normalized_factor_state,
        "backend_observation": observed,
        "semantic_rank_authority": false
    });
}

fn positive_lapack_pivot_info(result: &Value) -> bool {
    [
        &result["factor"]["status"]["active_factor_info"],
        &result["factor"]["status"]["dsytrf_info"],
        &result["factor"]["status"]["fallback_dgetrf_info"],
        &result["solve"]["status"]["lapack_info"],
    ]
    .into_iter()
    .filter_map(|value| value.as_i64())
    .any(|info| info > 0)
}

fn run_faer(context: &AttemptContext) -> Value {
    faer::set_global_parallelism(Par::Seq);
    let window = AllocationWindow::begin();
    let n = context.n;
    let matrix = FaerMat::from_fn(n, n, |row, column| context.b[row * n + column]);
    let rhs = FaerMat::from_fn(n, 1, |row, _| context.rhs[row]);
    let factor = FaerLblt::<f64>::new(matrix.as_ref(), faer::Side::Lower);
    let mut route = "lblt";
    let mut solution_matrix = factor.solve(rhs.as_ref());
    let mut solution: Vec<f64> = (0..n).map(|row| solution_matrix[(row, 0)]).collect();
    let primary_solution_finite = vector_finite(&solution);

    // Public factor components let this prototype independently reconstruct
    // L B L^T and apply the inverse permutation. Do not call Lblt::reconstruct:
    // faer 0.24.4's high-level path does not use the separate B diagonal.
    let l = DMatrix::from_fn(n, n, |row, column| factor.L()[(row, column)]);
    let mut block = DMatrix::<f64>::zeros(n, n);
    let mut two_by_two = 0_usize;
    let mut min_block_magnitude = f64::INFINITY;
    let mut cursor = 0;
    while cursor < n {
        let diagonal = factor.B_diag()[cursor];
        block[(cursor, cursor)] = diagonal;
        if cursor + 1 < n && factor.B_subdiag()[cursor] != 0.0 {
            let off_diagonal = factor.B_subdiag()[cursor];
            let next_diagonal = factor.B_diag()[cursor + 1];
            block[(cursor, cursor + 1)] = off_diagonal;
            block[(cursor + 1, cursor)] = off_diagonal;
            block[(cursor + 1, cursor + 1)] = next_diagonal;
            min_block_magnitude =
                min_block_magnitude.min((diagonal * next_diagonal - off_diagonal.powi(2)).abs());
            two_by_two += 1;
            cursor += 2;
        } else {
            min_block_magnitude = min_block_magnitude.min(diagonal.abs());
            cursor += 1;
        }
    }
    let permuted = &l * &block * l.transpose();
    let (forward, inverse) = factor.P().arrays();
    let mut reconstructed = DMatrix::<f64>::zeros(n, n);
    for row in 0..n {
        for column in 0..n {
            reconstructed[(row, column)] = permuted[(inverse[row], inverse[column])];
        }
    }
    let reconstruction = relative_inf_error_nalgebra(&reconstructed, &context.b, n);
    let factor_finite =
        l.iter().all(|value| value.is_finite()) && block.iter().all(|value| value.is_finite());

    let mut fallback_used = false;
    if !factor_finite || !primary_solution_finite {
        fallback_used = true;
        route = "fresh-partial-piv-lu-fallback";
        let fresh_matrix = FaerMat::from_fn(n, n, |row, column| context.b[row * n + column]);
        let fresh_rhs = FaerMat::from_fn(n, 1, |row, _| context.rhs[row]);
        let fallback = FaerLu::<f64>::new(fresh_matrix.as_ref());
        solution_matrix = fallback.solve(fresh_rhs.as_ref());
        solution = (0..n).map(|row| solution_matrix[(row, 0)]).collect();
    }
    let solution_finite = vector_finite(&solution);
    let residual = solution_finite.then(|| backward_error(&context.b, &solution, &context.rhs, n));
    let nonidentity = forward
        .iter()
        .enumerate()
        .filter(|(index, value)| *index != **value)
        .count();
    let mut packed_l = Vec::with_capacity(triangular_count(n));
    for row in 0..n {
        for column in 0..=row {
            packed_l.push(factor.L()[(row, column)]);
        }
    }
    let packed_diag: Vec<f64> = (0..n).map(|index| factor.B_diag()[index]).collect();
    let packed_subdiag: Vec<f64> = (0..n).map(|index| factor.B_subdiag()[index]).collect();
    let packed_inverse: Vec<usize> = inverse.to_vec();
    let component_hash = factor_bytes_hash(
        packed_l
            .iter()
            .copied()
            .chain(packed_diag.iter().copied())
            .chain(packed_subdiag.iter().copied()),
        packed_inverse.iter().map(|&index| index as i64),
    );
    let roundtrip_solution = solve_faer_packed_components(
        &packed_l,
        &packed_diag,
        &packed_subdiag,
        &packed_inverse,
        &context.rhs,
    );
    let roundtrip_finite = roundtrip_solution
        .as_ref()
        .is_some_and(|values| vector_finite(values));
    let roundtrip_residual = roundtrip_solution
        .as_ref()
        .filter(|_| roundtrip_finite)
        .map(|values| backward_error(&context.b, values, &context.rhs, n));
    let roundtrip_solution_delta = roundtrip_solution
        .as_ref()
        .filter(|_| roundtrip_finite && solution_finite)
        .map(|values| {
            normalized(
                values
                    .iter()
                    .zip(&solution)
                    .fold(0.0_f64, |norm, (lhs, rhs)| norm.max((lhs - rhs).abs())),
                vector_inf_norm(&solution),
            )
        });
    let packed_bytes = triangular_count(n)
        .saturating_mul(8)
        .saturating_add(n.saturating_mul(16))
        .saturating_add(n.saturating_mul(std::mem::size_of::<usize>()));
    let llt_audit = {
        let fresh_matrix = FaerMat::from_fn(n, n, |row, column| context.b[row * n + column]);
        match FaerLlt::<f64>::new(fresh_matrix.as_ref(), faer::Side::Lower) {
            Ok(llt) => {
                let fresh_rhs = FaerMat::from_fn(n, 1, |row, _| context.rhs[row]);
                let llt_solution = llt.solve(fresh_rhs.as_ref());
                let values: Vec<f64> = (0..n).map(|row| llt_solution[(row, 0)]).collect();
                json!({
                    "status": "AUDIT_COLLECTED",
                    "constructor": "success",
                    "solution_finite": vector_finite(&values),
                    "reduced_backward_error": vector_finite(&values)
                        .then(|| finite_number(backward_error(&context.b, &values, &context.rhs, n))),
                    "independent_spd_certificate": "EVIDENCE_MISSING",
                    "selectable": false,
                    "reason": "LLT is audit-only without an independent SPD certificate"
                })
            }
            Err(_) => json!({
                "status": "AUDIT_COLLECTED",
                "constructor": "rejected",
                "solution_finite": Value::Null,
                "reduced_backward_error": Value::Null,
                "independent_spd_certificate": "EVIDENCE_MISSING",
                "selectable": false,
                "reason": "LLT is audit-only without an independent SPD certificate"
            }),
        }
    };
    let mut result = attempt_base(context, "faer");
    result["backend_version"] = json!("0.24.4");
    result["attempt_state"] = json!(if solution_finite {
        "COLLECTED"
    } else {
        "COLLECTED_NONFINITE"
    });
    result["finite_gate"] = json!({
        "input": true,
        "factor": factor_finite,
        "solution": solution_finite
    });
    result["factor"] = json!({
        "factor_role": "projected_symmetric_B",
        "status": {
            "route": route,
            "constructor_result": "high-level LBLT constructor has no Result status",
            "fallback_used": fallback_used
        },
        "pivot_diagnostics": {
            "permutation_entries": n,
            "nonidentity_permutation_entries": nonidentity,
            "two_by_two_blocks": two_by_two,
            "min_abs_1x1_value_or_2x2_determinant": finite_number(min_block_magnitude),
            "semantic_rank_authority": false
        },
        "reconstruction_relative_inf": finite_number(reconstruction),
        "reconstruction_status": "independent public L/B/P reconstruction; high-level reconstruct not called"
    });
    result["solve"] = json!({
        "status": {
            "route": route,
            "finite": solution_finite
        },
        "reduced_backward_error": residual.map(finite_number)
    });
    result["gated_llt"] = llt_audit;
    result["packing"] = json!({
        "capability": "owned-canonical-L-Bdiag-Bsubdiag-inverse-permutation",
        "roundtrip_tested": true,
        "roundtrip_solve_finite": roundtrip_finite,
        "roundtrip_reduced_backward_error": roundtrip_residual.map(finite_number),
        "roundtrip_solution_relative_inf": roundtrip_solution_delta.map(finite_number),
        "packed_bytes": packed_bytes,
        "component_sha256": component_hash
    });
    result["resources"] = json!({
        "source_immutable_bytes": source_resource_ledger(context),
        "factor_retained_bytes": n.saturating_mul(n).saturating_mul(8)
            .saturating_add(n.saturating_mul(16))
            .saturating_add(n.saturating_mul(2).saturating_mul(std::mem::size_of::<usize>())),
        "retained_bytes": n.saturating_mul(n).saturating_mul(8)
            .saturating_add(n.saturating_mul(16))
            .saturating_add(n.saturating_mul(2).saturating_mul(std::mem::size_of::<usize>())),
        "transient_peak_delta_bytes": window.peak_delta(),
        "transient_peak_measurement": "process-global Rust allocator diagnostic; includes verifier reconstruction allocations",
        "memory_scratch_bytes": null,
        "memory_scratch_status": "high-level scratch allocation is not exposed; allocator peak is measured",
        "temp_storage_bytes": 0,
        "temp_storage_writes": 0,
        "temp_storage_residue_bytes": 0,
        "thread_ownership": "PROCESS_GLOBAL_PINNED_SEQ",
        "caller_thread_lease_materialized": false,
        "requested_threads": 1,
        "backend_effective_threads": 1,
        "observed_threads": observed_thread_count(),
        "maximum_live_threads": "EVIDENCE_MISSING",
        "backend_parallelism": format!("{:?}", faer::get_global_parallelism())
    });
    result["artifact_closure"] = json!({
        "state": "PARTIAL",
        "coordinates": {"crate": "faer", "version": "0.24.4", "cargo_lock": true},
        "notes": "package is locked; tier-one target runtime/provenance closure is not asserted by this local replay"
    });
    result["diagnostics"] = json!([
        "Every route starts from a new A/RHS copy.",
        "faer high-level Lblt::reconstruct is intentionally bypassed.",
        "Factor health, pivots, and residuals do not supply semantic rank."
    ]);
    attach_full_correction(&mut result, context, solution_finite.then_some(&solution));
    result
}

fn run_nalgebra(context: &AttemptContext) -> Value {
    let window = AllocationWindow::begin();
    let n = context.n;
    let matrix = DMatrix::from_row_slice(n, n, &context.b);
    let rhs = DVector::from_vec(context.rhs.clone());
    let factor = nalgebra::linalg::LBLT::new(matrix);
    let mut route = "lblt";
    let mut solved = factor.solve(&rhs);
    let mut solution = solved
        .as_ref()
        .map(|value| value.iter().copied().collect::<Vec<_>>());

    let l_permuted = factor.l_permuted();
    let block = factor.d();
    let reconstructed = &l_permuted * &block * l_permuted.transpose();
    let reconstruction = relative_inf_error_nalgebra(&reconstructed, &context.b, n);
    let factor_finite = l_permuted.iter().all(|value| value.is_finite())
        && block.iter().all(|value| value.is_finite());
    let mut two_by_two = 0_usize;
    let mut cursor = 0;
    while cursor + 1 < n {
        if block[(cursor + 1, cursor)] != 0.0 {
            two_by_two += 1;
            cursor += 2;
        } else {
            cursor += 1;
        }
    }

    let primary_solution_finite = solution.as_ref().is_some_and(|value| vector_finite(value));
    let mut fallback_used = false;
    if !factor_finite || !primary_solution_finite {
        fallback_used = true;
        route = "fresh-partial-piv-lu-fallback";
        let fresh_matrix = DMatrix::from_row_slice(n, n, &context.b);
        let fresh_rhs = DVector::from_vec(context.rhs.clone());
        solved = fresh_matrix.lu().solve(&fresh_rhs);
        solution = solved.map(|value| value.iter().copied().collect());
    }
    let solution_finite = solution.as_ref().is_some_and(|value| vector_finite(value));
    let residual = solution
        .as_ref()
        .filter(|_| solution_finite)
        .map(|value| backward_error(&context.b, value, &context.rhs, n));
    let component_hash = factor_bytes_hash(
        l_permuted.iter().copied().chain(block.iter().copied()),
        std::iter::empty::<i64>(),
    );
    let mut result = attempt_base(context, "nalgebra");
    result["backend_version"] = json!("0.35.0");
    result["attempt_state"] = json!(if solution_finite {
        "COLLECTED"
    } else {
        "COLLECTED_BACKEND_FAILURE"
    });
    result["finite_gate"] = json!({
        "input": true,
        "factor": factor_finite,
        "solution": solution_finite
    });
    result["factor"] = json!({
        "factor_role": "projected_symmetric_B",
        "status": {
            "route": route,
            "lblt_solve_returned_some": primary_solution_finite,
            "fallback_used": fallback_used
        },
        "pivot_diagnostics": {
            "pivot_sequence": "PRIVATE_UNAVAILABLE",
            "zero_pivot": "PRIVATE_UNAVAILABLE",
            "two_by_two_blocks_visible_from_public_D": two_by_two,
            "semantic_rank_authority": false
        },
        "reconstruction_relative_inf": finite_number(reconstruction),
        "reconstruction_status": "public l_permuted * D * l_permuted^T"
    });
    result["solve"] = json!({
        "status": {
            "route": route,
            "finite": solution_finite,
            "option_is_some": solution.is_some()
        },
        "reduced_backward_error": residual.map(finite_number)
    });
    result["packing"] = json!({
        "capability": "RESIDENT_ONLY_UNMATERIALIZED_PRIVATE_PIVOTS",
        "roundtrip_tested": false,
        "packed_bytes": null,
        "public_reconstruction_component_sha256": component_hash
    });
    result["resources"] = json!({
        "source_immutable_bytes": source_resource_ledger(context),
        "factor_retained_bytes": null,
        "retained_bytes": null,
        "retained_lower_bound_bytes": n.saturating_mul(n).saturating_mul(8),
        "retained_status": "exact resident bytes blocked by private pivots/zero_pivot fields",
        "transient_peak_delta_bytes": window.peak_delta(),
        "transient_peak_measurement": "process-global Rust allocator diagnostic; includes public factor reconstruction allocations",
        "memory_scratch_bytes": null,
        "memory_scratch_status": "high-level allocation contract is not exposed",
        "temp_storage_bytes": 0,
        "temp_storage_writes": 0,
        "temp_storage_residue_bytes": 0,
        "thread_ownership": "NO_INJECTABLE_BACKEND_THREAD_LEASE",
        "caller_thread_lease_materialized": false,
        "requested_threads": 1,
        "backend_effective_threads": 1,
        "observed_threads": observed_thread_count(),
        "maximum_live_threads": "EVIDENCE_MISSING",
        "backend_parallelism": "nalgebra CPU path invoked without an external threaded BLAS"
    });
    result["artifact_closure"] = json!({
        "state": "BLOCKED_FOR_BOUNDED_SPILL",
        "coordinates": {"crate": "nalgebra", "version": "0.35.0", "cargo_lock": true},
        "notes": "solve/reconstruction evidence exists, but exact pivots and a stable packed factor are not public"
    });
    result["diagnostics"] = json!([
        "Every fallback starts from a new A/RHS copy.",
        "Private pivot and zero-pivot fields are reported missing, not guessed.",
        "Factor health, public D blocks, and residuals do not supply semantic rank."
    ]);
    attach_full_correction(
        &mut result,
        context,
        solution.as_ref().filter(|_| solution_finite),
    );
    result
}

pub(crate) fn attempt_base(context: &AttemptContext, backend: &str) -> Value {
    attempt_base_from_record(
        &context.record,
        backend,
        json!({
            "corpus_sha256": context.corpus_sha256,
            "b_lower_sha256": context.b_sha256,
            "rhs_reduced_sha256": context.rhs_sha256,
            "manifest_directory": context.manifest_dir
        }),
    )
}

fn attempt_base_from_record(record: &CaptureRecord, backend: &str, input_identity: Value) -> Value {
    json!({
        "schema": ATTEMPT_SCHEMA,
        "record_id": record.record_id,
        "panel_id": record.panel_id,
        "case_id": record.case_id,
        "role": record.role,
        "assembly_variant": record.assembly_variant,
        "assembly_authority": record.assembly_authority,
        "matrix_kind": record.matrix_kind,
        "registered_rank_expectation": record.registered_rank_expectation,
        "semantic_rank_state": record.semantic_rank_state,
        "semantic_admission": semantic_admission(record),
        "backend_rank": {
            "state": "NOT_EVALUATED",
            "source": "backend factor diagnostics are health evidence only",
            "semantic_authority": false
        },
        "backend": backend,
        "backend_version": Value::Null,
        "collection_state": "NOT_RUN",
        "factor_state": {
            "normalized": "NOT_RUN",
            "backend_observation": "UNJUDGED",
            "semantic_rank_authority": false
        },
        "attempt_state": "UNJUDGED",
        "input_identity": input_identity,
        "finite_gate": {
            "input": true,
            "factor": Value::Null,
            "solution": Value::Null
        },
        "factor": Value::Null,
        "solve": {
            "status": "NOT_RUN",
            "reduced_backward_error": Value::Null,
            "full_correction": Value::Null
        },
        "packing": Value::Null,
        "resources": Value::Null,
        "polynomial_factor": {
            "status": "NOT_RUN",
            "packing": "UNMATERIALIZED",
            "resources": Value::Null
        },
        "artifact_closure": Value::Null,
        "selection": "UNJUDGED",
        "selection_reason": "FactorHealthProfile{id,hash} absent",
        "publication": {
            "factor_stage": "UNJUDGED_NOT_PUBLISHED",
            "solve_stage": "UNJUDGED_NOT_PUBLISHED",
            "atomicity": "factor and each RHS remain private until their own complete certificate passes"
        },
        "diagnostics": []
    })
}

fn semantic_admission(record: &CaptureRecord) -> Value {
    match record.semantic_rank_state.as_str() {
        "certificate-missing" => json!({
            "state": "EVIDENCE_MISSING",
            "certificate_state": "certificate-missing",
            "registered_expectation": record.registered_rank_expectation,
            "assembly_authority": record.assembly_authority,
            "backend_rank_used": false,
            "execution_disposition":
                "DIAGNOSTIC_FORCE_REPLAY_DESPITE_MISSING_SEMANTIC_CERTIFICATE",
            "reason": "Stage 0 corpus contains no independent semantic rank certificate"
        }),
        "rank_fail" => json!({
            "state": "REJECTED",
            "certificate_state": "derived-control-oracle",
            "registered_expectation": record.registered_rank_expectation,
            "assembly_authority": record.assembly_authority,
            "backend_rank_used": false,
            "execution_disposition":
                "DIAGNOSTIC_FORCE_REPLAY_AFTER_RECORDED_PRE_ADMISSION_REJECTION",
            "reason": "deterministic exact-rank-fail control is rejected before backend selection"
        }),
        "preflight_nonfinite" => json!({
            "state": "NOT_EVALUATED",
            "certificate_state": "not-applicable-nonfinite-input",
            "registered_expectation": record.registered_rank_expectation,
            "assembly_authority": record.assembly_authority,
            "backend_rank_used": false,
            "execution_disposition": "REJECT_BEFORE_FACTOR",
            "reason": "non-finite input is rejected before factorization"
        }),
        other => json!({
            "state": "EVIDENCE_MISSING",
            "certificate_state": other,
            "registered_expectation": record.registered_rank_expectation,
            "assembly_authority": record.assembly_authority,
            "backend_rank_used": false,
            "execution_disposition": "DO_NOT_EXECUTE_WITHOUT_CONTRACT",
            "reason": "unrecognized semantic admission state"
        }),
    }
}

pub(crate) fn attach_full_correction(
    result: &mut Value,
    context: &AttemptContext,
    reduced_solution: Option<&Vec<f64>>,
) {
    let Some(reduced_solution) = reduced_solution else {
        result["solve"]["full_correction"] = json!({
            "status": "EVIDENCE_MISSING",
            "reason": "no finite reduced solution"
        });
        result["polynomial_factor"] = json!({
            "factor_role": "P_top polynomial recovery",
            "status": "NOT_RUN",
            "packing": "UNMATERIALIZED",
            "resources": null
        });
        return;
    };

    let scalar = context.record.scalar_order;
    let polynomial = context.record.polynomial_order;
    let reduced = context.record.reduced_order;
    if polynomial == 0 {
        let alpha = backward_error(&context.a_full, reduced_solution, &context.rhs_full, scalar);
        result["polynomial_factor"] = json!({
            "factor_role": "P_top polynomial recovery",
            "status": "NOT_APPLICABLE_POLYNOMIAL_ORDER_ZERO",
            "packing": "NOT_APPLICABLE",
            "resources": {
                "retained_bytes": 0,
                "temp_storage_bytes": 0
            }
        });
        result["solve"]["full_correction"] = json!({
            "status": "COLLECTED_DERIVED_CONTROL_WITHOUT_POLYNOMIAL",
            "captured_augmented_matrix_residual_alpha": finite_number(alpha),
            "cpd_orthogonality_eta": 0.0,
            "external_value_gradient_evaluator": "NOT_APPLICABLE_DERIVED_CONTROL",
            "evaluator_uncertainty": Value::Null,
            "certificate_judgment": "DIAGNOSTIC_ONLY_UNJUDGED"
        });
        return;
    }
    let mut lambda = vec![0.0_f64; scalar];
    for (row, value) in lambda.iter_mut().take(polynomial).enumerate() {
        *value = (0..reduced)
            .map(|column| context.q_top[row * reduced + column] * reduced_solution[column])
            .sum();
    }
    lambda[polynomial..].copy_from_slice(reduced_solution);

    let mut polynomial_rhs = vec![0.0_f64; polynomial];
    for (row, value) in polynomial_rhs.iter_mut().enumerate() {
        let a_lambda: f64 = (0..scalar)
            .map(|column| context.a_full[row * scalar + column] * lambda[column])
            .sum();
        *value = context.rhs_full[row] - a_lambda;
    }
    let p_top = DMatrix::from_row_slice(polynomial, polynomial, &context.p_top);
    let p_rhs = DVector::from_vec(polynomial_rhs);
    let p_factor = p_top.full_piv_lu();
    let invertible = p_factor.is_invertible();
    let polynomial_solution = p_factor.solve(&p_rhs);
    let diagnostic_rank_at_zero = p_factor
        .u()
        .diagonal()
        .iter()
        .filter(|value| **value != 0.0)
        .count();
    let c = polynomial_solution
        .as_ref()
        .map(|solution| solution.iter().copied().collect::<Vec<_>>());

    result["polynomial_factor"] = json!({
        "factor_role": "P_top polynomial recovery",
        "backend": "nalgebra FullPivLU common cross-backend certificate helper",
        "per_backend_native_factor_evidence": "EVIDENCE_MISSING",
        "status": {
            "solve_returned_some": c.is_some(),
            "is_invertible_exact_zero_gate": invertible,
            "diagnostic_rank_at_zero_epsilon": diagnostic_rank_at_zero,
            "semantic_rank_authority": false
        },
        "packing": {
            "capability": "UNMATERIALIZED",
            "roundtrip_tested": false,
            "packed_bytes": null
        },
        "resources": {
            "retained_lower_bound_bytes": polynomial.saturating_mul(polynomial).saturating_mul(8),
            "transient_bytes_modeled": polynomial.saturating_mul(polynomial).saturating_mul(16),
            "thread_ownership": "NO_INJECTABLE_BACKEND_THREAD_LEASE; worker process executes sequentially",
            "caller_thread_lease_materialized": false,
            "requested_threads": 1,
            "backend_effective_threads": 1
        }
    });

    let Some(c) = c else {
        result["solve"]["full_correction"] = json!({
            "status": "EVIDENCE_MISSING",
            "reason": "independent P_top FullPivLU recovery failed"
        });
        return;
    };
    let mut residual_inf = 0.0_f64;
    for row in 0..scalar {
        let a_lambda: f64 = (0..scalar)
            .map(|column| context.a_full[row * scalar + column] * lambda[column])
            .sum();
        let p_c: f64 = (0..polynomial)
            .map(|column| context.p_full[row * polynomial + column] * c[column])
            .sum();
        residual_inf = residual_inf.max((a_lambda + p_c - context.rhs_full[row]).abs());
    }
    let a_norm = matrix_inf_norm(&context.a_full, scalar);
    let p_norm = rectangular_inf_norm(&context.p_full, scalar, polynomial);
    let lambda_norm = vector_inf_norm(&lambda);
    let c_norm = vector_inf_norm(&c);
    let d_norm = vector_inf_norm(&context.rhs_full);
    let denominator = a_norm * lambda_norm + p_norm * c_norm + d_norm;
    let alpha = normalized(residual_inf, denominator);

    let mut pt_lambda_inf = 0.0_f64;
    let mut pt_inf = 0.0_f64;
    for column in 0..polynomial {
        let mut dot = 0.0;
        let mut row_sum = 0.0;
        for (row, &lambda_value) in lambda.iter().enumerate() {
            let value = context.p_full[row * polynomial + column];
            dot += value * lambda_value;
            row_sum += value.abs();
        }
        pt_lambda_inf = pt_lambda_inf.max(dot.abs());
        pt_inf = pt_inf.max(row_sum);
    }
    let eta_denominator = pt_inf * lambda_norm;
    let eta = normalized(pt_lambda_inf, eta_denominator);
    result["solve"]["full_correction"] = json!({
        "status": if vector_finite(&lambda) && vector_finite(&c) {
            "COLLECTED"
        } else {
            "COLLECTED_NONFINITE"
        },
        "captured_augmented_matrix_residual_alpha": finite_number(alpha),
        "cpd_orthogonality_eta": finite_number(eta),
        "cpd_zero_over_zero_rule": "0/0 := 0",
        "external_value_gradient_evaluator": "EVIDENCE_MISSING",
        "evaluator_uncertainty": Value::Null,
        "certificate_judgment": "INCOMPLETE_AND_UNJUDGED_WITHOUT_EXTERNAL_EVALUATOR_OR_FACTOR_HEALTH_PROFILE",
        "lambda_order": scalar,
        "polynomial_order": polynomial
    });
}

fn solve_faer_packed_components(
    lower_row_packed: &[f64],
    diagonal: &[f64],
    subdiagonal: &[f64],
    inverse_permutation: &[usize],
    rhs: &[f64],
) -> Option<Vec<f64>> {
    let n = diagonal.len();
    if lower_row_packed.len() != triangular_count(n)
        || subdiagonal.len() != n
        || inverse_permutation.len() != n
        || rhs.len() != n
    {
        return None;
    }
    let lower =
        |row: usize, column: usize| -> f64 { lower_row_packed[row * (row + 1) / 2 + column] };
    let mut work = vec![0.0_f64; n];
    for original in 0..n {
        let permuted = inverse_permutation[original];
        if permuted >= n {
            return None;
        }
        work[permuted] = rhs[original];
    }

    // L y = P b.
    for row in 0..n {
        let correction: f64 = (0..row)
            .map(|column| lower(row, column) * work[column])
            .sum();
        work[row] -= correction;
    }

    // B z = y, with the same 2x2 marker used by faer's public B_subdiag.
    let mut cursor = 0;
    while cursor < n {
        if cursor + 1 < n && subdiagonal[cursor] != 0.0 {
            let a = diagonal[cursor];
            let b = subdiagonal[cursor];
            let d = diagonal[cursor + 1];
            let determinant = a * d - b * b;
            if determinant == 0.0 || !determinant.is_finite() {
                return None;
            }
            let first = work[cursor];
            let second = work[cursor + 1];
            work[cursor] = (d * first - b * second) / determinant;
            work[cursor + 1] = (a * second - b * first) / determinant;
            cursor += 2;
        } else {
            if diagonal[cursor] == 0.0 || !diagonal[cursor].is_finite() {
                return None;
            }
            work[cursor] /= diagonal[cursor];
            cursor += 1;
        }
    }

    // L^T w = z.
    for row in (0..n).rev() {
        let correction: f64 = ((row + 1)..n)
            .map(|lower_row| lower(lower_row, row) * work[lower_row])
            .sum();
        work[row] -= correction;
    }

    let mut solution = vec![0.0_f64; n];
    for original in 0..n {
        solution[original] = work[inverse_permutation[original]];
    }
    Some(solution)
}

pub(crate) fn source_resource_ledger(context: &AttemptContext) -> Value {
    let scalar = context.record.scalar_order;
    let polynomial = context.record.polynomial_order;
    let reduced = context.record.reduced_order;
    json!({
        "b_lower_corpus_bytes": triangular_count(reduced).saturating_mul(8),
        "b_full_private_copy_bytes": reduced.saturating_mul(reduced).saturating_mul(8),
        "rhs_reduced_bytes": reduced.saturating_mul(8),
        "external_certificate": {
            "a_full_private_copy_bytes": scalar.saturating_mul(scalar).saturating_mul(8),
            "p_row_major_bytes": scalar.saturating_mul(polynomial).saturating_mul(8),
            "q_top_row_major_bytes": polynomial.saturating_mul(reduced).saturating_mul(8),
            "rhs_full_bytes": scalar.saturating_mul(8),
            "p_top_bytes": polynomial.saturating_mul(polynomial).saturating_mul(8)
        },
        "ownership": "immutable worker-private decoded corpus"
    })
}

fn panic_attempt(
    backend: &str,
    context: &AttemptContext,
    payload: Box<dyn std::any::Any + Send>,
) -> Value {
    let message = payload
        .downcast_ref::<&str>()
        .map(|value| (*value).to_owned())
        .or_else(|| payload.downcast_ref::<String>().cloned())
        .unwrap_or_else(|| "non-string panic payload".to_owned());
    let mut result = attempt_base(context, backend_display_name(backend));
    result["attempt_state"] = json!("PANIC");
    result["diagnostics"] = json!([message]);
    normalize_attempt_states(&mut result);
    result
}

fn missing_worker_attempt(
    backend: &str,
    record: &CaptureRecord,
    corpus_sha256: &str,
    diagnostic: String,
) -> Value {
    let mut result = attempt_base_from_record(
        record,
        backend_display_name(backend),
        json!({
            "corpus_sha256": corpus_sha256,
            "b_lower_sha256": Value::Null,
            "rhs_reduced_sha256": Value::Null,
            "manifest_directory": Value::Null
        }),
    );
    result["attempt_state"] = json!("EVIDENCE_MISSING");
    result["diagnostics"] = json!([diagnostic]);
    normalize_attempt_states(&mut result);
    result["factor_state"]["normalized"] = json!("ContractViolation");
    result
}

fn missing_control_attempt(
    backend: &str,
    control_id: &str,
    corpus_sha256: &str,
    diagnostic: String,
) -> Value {
    match AttemptContext::synthetic(control_id, corpus_sha256.to_owned()) {
        Ok(context) => {
            let mut result = attempt_base(&context, backend_display_name(backend));
            result["attempt_state"] = json!("EVIDENCE_MISSING");
            result["diagnostics"] = json!([diagnostic]);
            normalize_attempt_states(&mut result);
            result["factor_state"]["normalized"] = json!("ContractViolation");
            result
        }
        Err(error) => {
            let record = CaptureRecord {
                record_id: control_id.to_owned(),
                panel_id: "UNKNOWN-DERIVED-CONTROL".to_owned(),
                case_id: control_id.to_owned(),
                role: "derived-control".to_owned(),
                assembly_variant: "not-applicable".to_owned(),
                assembly_authority: "diagnostic-force-replay-only".to_owned(),
                matrix_kind: "unknown-derived-control".to_owned(),
                registered_rank_expectation: "not-applicable-derived-control".to_owned(),
                semantic_rank_state: "evidence-missing".to_owned(),
                scalar_order: 0,
                polynomial_order: 0,
                reduced_order: 0,
                files: BTreeMap::new(),
            };
            let mut result = attempt_base_from_record(
                &record,
                backend_display_name(backend),
                json!({
                    "corpus_sha256": corpus_sha256,
                    "b_lower_sha256": Value::Null,
                    "rhs_reduced_sha256": Value::Null,
                    "manifest_directory": Value::Null
                }),
            );
            result["attempt_state"] = json!("EVIDENCE_MISSING");
            result["diagnostics"] = json!([diagnostic, error]);
            normalize_attempt_states(&mut result);
            result["factor_state"]["normalized"] = json!("ContractViolation");
            result
        }
    }
}

fn m3_assembly_audit(manifest_path: &Path, records: &[CaptureRecord]) -> Vec<Value> {
    let Some(root) = manifest_path.parent() else {
        return Vec::new();
    };
    let mut output = Vec::new();
    for role in ["max-order-fine", "level0-coarse"] {
        let canonical = records.iter().find(|record| {
            record.panel_id == "M3-HERMITE-COMPOSITE"
                && record.role == role
                && record.assembly_variant == "canonical-row-channel-map"
        });
        let literal = records.iter().find(|record| {
            record.panel_id == "M3-HERMITE-COMPOSITE"
                && record.role == role
                && record.assembly_variant == "frozen-literal-gradient-row-map"
        });
        let (Some(canonical), Some(literal)) = (canonical, literal) else {
            output.push(json!({
                "role": role,
                "state": "EVIDENCE_MISSING",
                "semantic_verdict": "NONE"
            }));
            continue;
        };
        let pair = |key: &str| -> Value {
            let canonical_path = record_file(root, canonical, key).ok();
            let literal_path = record_file(root, literal, key).ok();
            match (
                canonical_path.and_then(|path| fs::read(path).ok()),
                literal_path.and_then(|path| fs::read(path).ok()),
            ) {
                (Some(canonical_bytes), Some(literal_bytes)) => json!({
                    "state": "COLLECTED",
                    "byte_equal": canonical_bytes == literal_bytes,
                    "canonical_sha256": sha256_bytes(&canonical_bytes),
                    "frozen_literal_sha256": sha256_bytes(&literal_bytes)
                }),
                _ => json!({"state": "EVIDENCE_MISSING"}),
            }
        };
        let b_lower = pair("b_lower");
        let rhs_reduced = pair("rhs_reduced");
        let all_comparisons_collected = [&b_lower, &rhs_reduced].iter().all(|comparison| {
            comparison["state"]
                .as_str()
                .is_some_and(|state| state.starts_with("COLLECTED"))
        });
        output.push(json!({
            "role": role,
            "state": if all_comparisons_collected {
                "COLLECTED_RESEARCH_ONLY"
            } else {
                "EVIDENCE_MISSING"
            },
            "b_lower": b_lower,
            "rhs_reduced": rhs_reduced,
            "semantic_verdict": "NONE",
            "note": "A mismatch is research evidence only; this replay does not label it a defect or adoption signal."
        }));
    }
    output
}

fn derived_controls(executable: &Path, manifest_path: &Path, corpus_sha256: &str) -> Vec<Value> {
    let tau = 4.0 * f64::EPSILON;
    let attempts = |control_id: &str| -> Vec<Value> {
        BACKENDS
            .iter()
            .map(|backend| {
                spawn_control_worker(
                    executable,
                    manifest_path,
                    corpus_sha256,
                    backend,
                    control_id,
                )
            })
            .collect()
    };
    vec![
        json!({
            "control_id": "M4-derived-exact-rank-fail",
            "matrix_diagonal": [1.0, 1.0, 1.0, 0.0],
            "tau_rank": tau,
            "oracle_ratio_interval": [0.0, 0.0],
            "semantic_expected_state": "RANK_FAIL",
            "semantic_admission_phase": "REJECT_BEFORE_BACKEND_SELECTION",
            "backend_replay_phase": "DIAGNOSTIC_FORCE_REPLAY_AFTER_RECORDED_PRE_ADMISSION_REJECTION",
            "execution_state": "EXECUTED_IN_FRESH_WORKERS",
            "attempts": attempts("M4-derived-exact-rank-fail"),
            "source": "deterministic derived control; not a captured registered matrix"
        }),
        json!({
            "control_id": "M4-derived-rank-straddle",
            "matrix_diagonal": [1.0, 1.0, 1.0, tau],
            "tau_rank": tau,
            "oracle_ratio_interval": [tau - tau / 16.0, tau + tau / 16.0],
            "semantic_expected_state": "INDETERMINATE_PENDING_PRECISION_LADDER",
            "backend_attempt": "NOT_RUN_PRE_ADMISSION",
            "execution_state": "DECLARED_NOT_EXECUTED_THROUGH_BACKENDS",
            "source": "deterministic derived control; interval intentionally straddles tau"
        }),
        json!({
            "control_id": "M4-derived-nan-matrix",
            "mutation": "B[0,0] = NaN",
            "expected_gate": "REJECTED_NONFINITE_BEFORE_FACTOR",
            "execution_state": "EXECUTED_IN_FRESH_WORKERS",
            "attempts": attempts("M4-derived-nan-matrix"),
            "backend_rank_inference": false
        }),
        json!({
            "control_id": "M4-derived-infinite-rhs",
            "mutation": "rhs[0] = +Inf",
            "expected_gate": "REJECTED_NONFINITE_BEFORE_FACTOR",
            "execution_state": "EXECUTED_IN_FRESH_WORKERS",
            "attempts": attempts("M4-derived-infinite-rhs"),
            "backend_rank_inference": false
        }),
    ]
}

fn record_file(root: &Path, record: &CaptureRecord, key: &str) -> Result<PathBuf, String> {
    let relative = record
        .files
        .get(key)
        .ok_or_else(|| format!("{} is missing file key {key}", record.record_id))?;
    let path = root.join(relative);
    if !path.starts_with(root) {
        return Err(format!("{} escapes corpus root", path.display()));
    }
    Ok(path)
}

fn read_exact_file(path: &Path, expected_bytes: usize) -> Result<Vec<u8>, String> {
    let bytes =
        fs::read(path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
    if bytes.len() != expected_bytes {
        return Err(format!(
            "{} has {} bytes; expected {expected_bytes}",
            path.display(),
            bytes.len()
        ));
    }
    Ok(bytes)
}

fn decode_f64(bytes: &[u8]) -> Result<Vec<f64>, String> {
    if !bytes.len().is_multiple_of(8) {
        return Err("binary64 payload length is not divisible by eight".to_owned());
    }
    Ok(bytes
        .chunks_exact(8)
        .map(|chunk| {
            f64::from_le_bytes([
                chunk[0], chunk[1], chunk[2], chunk[3], chunk[4], chunk[5], chunk[6], chunk[7],
            ])
        })
        .collect())
}

fn load_f64_count(path: &Path, count: usize) -> Result<Vec<f64>, String> {
    decode_f64(&read_exact_file(path, count.saturating_mul(8))?)
}

fn load_lower(path: &Path, order: usize) -> Result<Vec<f64>, String> {
    let lower = load_f64_count(path, triangular_count(order))?;
    expand_lower(&lower, order)
}

fn expand_lower(lower: &[f64], n: usize) -> Result<Vec<f64>, String> {
    if lower.len() != triangular_count(n) {
        return Err("lower triangle length does not match matrix order".to_owned());
    }
    let mut full = vec![0.0_f64; n.saturating_mul(n)];
    let mut cursor = 0;
    for row in 0..n {
        for column in 0..=row {
            let value = lower[cursor];
            full[row * n + column] = value;
            full[column * n + row] = value;
            cursor += 1;
        }
    }
    Ok(full)
}

fn triangular_count(n: usize) -> usize {
    n.saturating_mul(n.saturating_add(1)).saturating_div(2)
}

pub(crate) fn matrix_finite(matrix: &[f64]) -> bool {
    vector_finite(matrix)
}

pub(crate) fn vector_finite(vector: &[f64]) -> bool {
    vector.iter().all(|value| value.is_finite())
}

pub(crate) fn vector_inf_norm(vector: &[f64]) -> f64 {
    vector
        .iter()
        .fold(0.0_f64, |norm, value| norm.max(value.abs()))
}

pub(crate) fn matrix_inf_norm(matrix: &[f64], n: usize) -> f64 {
    rectangular_inf_norm(matrix, n, n)
}

fn rectangular_inf_norm(matrix: &[f64], rows: usize, columns: usize) -> f64 {
    (0..rows)
        .map(|row| {
            matrix[row * columns..(row + 1) * columns]
                .iter()
                .map(|value| value.abs())
                .sum::<f64>()
        })
        .fold(0.0_f64, f64::max)
}

pub(crate) fn backward_error(matrix: &[f64], x: &[f64], rhs: &[f64], n: usize) -> f64 {
    let mut residual_inf = 0.0_f64;
    for row in 0..n {
        let product: f64 = (0..n)
            .map(|column| matrix[row * n + column] * x[column])
            .sum();
        residual_inf = residual_inf.max((product - rhs[row]).abs());
    }
    normalized(
        residual_inf,
        matrix_inf_norm(matrix, n) * vector_inf_norm(x) + vector_inf_norm(rhs),
    )
}

fn normalized(numerator: f64, denominator: f64) -> f64 {
    if denominator == 0.0 {
        if numerator == 0.0 { 0.0 } else { f64::INFINITY }
    } else {
        numerator / denominator
    }
}

fn relative_inf_error_nalgebra(reconstructed: &DMatrix<f64>, original: &[f64], n: usize) -> f64 {
    let mut difference_norm = 0.0_f64;
    for row in 0..n {
        let row_sum: f64 = (0..n)
            .map(|column| (reconstructed[(row, column)] - original[row * n + column]).abs())
            .sum();
        difference_norm = difference_norm.max(row_sum);
    }
    normalized(difference_norm, matrix_inf_norm(original, n))
}

pub(crate) fn finite_number(value: f64) -> Value {
    if value.is_finite() {
        json!(value)
    } else if value.is_nan() {
        json!("NaN")
    } else if value.is_sign_positive() {
        json!("+Inf")
    } else {
        json!("-Inf")
    }
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn sha256_f64(values: &[f64]) -> String {
    factor_bytes_hash(values.iter().copied(), std::iter::empty::<i64>())
}

pub(crate) fn factor_bytes_hash(
    floating: impl IntoIterator<Item = f64>,
    pivots: impl IntoIterator<Item = i64>,
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

pub(crate) fn observed_thread_count() -> Option<usize> {
    // The backend control is explicit (Par::Seq / nalgebra without BLAS /
    // oneMKL local threads=1). A point-in-time OS thread count would include
    // Rust/runtime threads and would not prove a factor call's peak ownership.
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lower_triangle_round_trip() {
        let full = expand_lower(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 3).unwrap();
        assert_eq!(full, vec![1.0, 2.0, 4.0, 2.0, 3.0, 5.0, 4.0, 5.0, 6.0]);
    }

    #[test]
    fn backward_error_of_exact_diagonal_solve_is_zero() {
        let matrix = vec![2.0, 0.0, 0.0, 4.0];
        assert_eq!(backward_error(&matrix, &[3.0, 2.0], &[6.0, 8.0], 2), 0.0);
    }

    #[test]
    fn controls_keep_backend_rank_out_of_semantics() {
        let corpus = "0".repeat(64);
        let singular =
            AttemptContext::synthetic("M4-derived-exact-rank-fail", corpus.clone()).unwrap();
        assert_eq!(singular.record.semantic_rank_state, "rank_fail");
        let nan = AttemptContext::synthetic("M4-derived-nan-matrix", corpus).unwrap();
        let attempt = run_backend("faer", &nan);
        assert_eq!(attempt["attempt_state"], "REJECTED_NONFINITE");
        assert_eq!(attempt["collection_state"], "COLLECTED");
        assert_eq!(attempt["factor_state"]["normalized"], "NOT_RUN");
        assert_eq!(attempt["backend_rank"]["semantic_authority"], false);
        assert_eq!(singular.record.semantic_rank_state, "rank_fail");
        let singular_admission = semantic_admission(&singular.record);
        assert_eq!(
            singular_admission["execution_disposition"],
            "DIAGNOSTIC_FORCE_REPLAY_AFTER_RECORDED_PRE_ADMISSION_REJECTION"
        );
    }

    #[test]
    fn faer_owned_components_solve_after_permutation_reload() {
        // Permuted factor is diag(4, 2), while original A is diag(2, 4).
        let solved = solve_faer_packed_components(
            &[1.0, 0.0, 1.0],
            &[4.0, 2.0],
            &[0.0, 0.0],
            &[1, 0],
            &[6.0, 8.0],
        )
        .unwrap();
        assert_eq!(solved, vec![3.0, 2.0]);
    }

    #[test]
    fn corpus_digest_matches_python_canonical_json_contract() {
        let body = json!({
            "schema": "v2",
            "capture_schema": "x",
            "hash_algorithm": "sha256",
            "record_count": 1,
            "referenced_payload_count": 1,
            "files": {
                "z.bin": {"bytes": 8, "sha256": "ab".repeat(32)},
                "manifest.raw.json": {"bytes": 2, "sha256": "cd".repeat(32)}
            },
            "generator_provenance": {
                "capture.cpp": {"bytes": 1, "sha256": "ef".repeat(32)}
            },
            "native_artifacts": {"artifact": "native"}
        });
        let canonical = serde_json::to_vec(&canonical_json(body)).unwrap();
        assert_eq!(
            sha256_bytes(&canonical),
            "1e982a3e66e933fe27e1bd48c974bfdd716ee7bc83b8bd1fb1343b847ea80612"
        );
        let unicode = serde_json::to_vec(&canonical_json(json!({
            "z": "\u{03bb}",
            "a": "\u{4e2d}"
        })))
        .unwrap();
        assert_eq!(
            sha256_bytes(&unicode),
            "8361acefa5afa3a8b78d8be29a8c4ff196e6edddf96bdb1fa30fe083c14248e6"
        );
    }

    #[test]
    fn positive_lapack_info_maps_to_documented_singular_pivot_state() {
        let mut attempt = json!({
            "attempt_state": "COLLECTED_BACKEND_ERROR",
            "factor": {"status": {"active_factor_info": 7}},
            "solve": {"status": {"lapack_info": 0}}
        });
        normalize_attempt_states(&mut attempt);
        assert_eq!(attempt["collection_state"], "COLLECTED");
        assert_eq!(attempt["factor_state"]["normalized"], "SingularPivot");
    }
}
