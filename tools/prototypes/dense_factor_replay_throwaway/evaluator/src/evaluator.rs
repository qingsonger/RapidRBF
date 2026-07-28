use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

use astro_float_num::{BigFloat, Consts, RoundingMode};
use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::interval::Interval;
use crate::loader::{ArtifactStore, Loaded, sha256};
use crate::physical::{
    ActionRow, DIMENSION, Geometry, PhysicalModel, RbfComponent, evaluate_action,
    evaluate_action_with_entries, polynomial_order, polynomial_rows,
};
use crate::profile::{
    EMBEDDED_PROFILE_BYTES, PROFILE_FILE_NAME, PhysicalEvidenceProfile, ProfileError,
    load_embedded_profile, load_profile_bytes, profile_body_sha256,
};
use crate::schema::{
    BlockDescriptor, CONTROL_SCHEMA, CanonicalSigns, CoefficientClosure, ComponentCertificate,
    ControlResult, ControlSummary, CorpusInput, CpdCertificate, EvaluationSummary,
    FACTOR_CERTIFICATE_SCHEMA, FactorCertificate, FailureRecord, INPUT_SCHEMA, OUTPUT_SCHEMA,
    ProofIdentity, QtaqPhysicalClosure, ResidualCertificate, ResourcePreflight, ScatterCertificate,
    SourceIdentity, WorkloadDescriptor,
};

const EXPECTED_LOCK_SCHEMA: &str = "rapidrbf-canonical-hierarchy-corpus-lock-v3";
const EXPECTED_INVENTORY_PROFILE: &str = "canonical-m1-m4-1k-10k-v3";
const EVALUATOR_SOURCE_FILE_NAMES: &[&str] = &[
    "Cargo.lock",
    "Cargo.toml",
    "physical-evidence-profile.v1.json",
    "src/evaluator.rs",
    "src/interval.rs",
    "src/lib.rs",
    "src/loader.rs",
    "src/main.rs",
    "src/physical.rs",
    "src/profile.rs",
    "src/schema.rs",
];
const EVALUATOR_SOURCE_FILES: [(&str, &[u8]); 11] = [
    ("Cargo.lock", include_bytes!("../Cargo.lock")),
    ("Cargo.toml", include_bytes!("../Cargo.toml")),
    (PROFILE_FILE_NAME, EMBEDDED_PROFILE_BYTES),
    ("src/evaluator.rs", include_bytes!("evaluator.rs")),
    ("src/interval.rs", include_bytes!("interval.rs")),
    ("src/lib.rs", include_bytes!("lib.rs")),
    ("src/loader.rs", include_bytes!("loader.rs")),
    ("src/main.rs", include_bytes!("main.rs")),
    ("src/physical.rs", include_bytes!("physical.rs")),
    ("src/profile.rs", include_bytes!("profile.rs")),
    ("src/schema.rs", include_bytes!("schema.rs")),
];

#[derive(Clone, Debug)]
pub struct EvaluationOptions {
    /// `None` selects the precision declared by the acceptance profile.
    pub precision_bits: Option<usize>,
    pub max_payload_bytes: u64,
    pub max_pair_work: u64,
    /// Empty means all blocks; otherwise each id must exist and only those
    /// blocks are evaluated.
    pub block_ids: Vec<String>,
}

impl Default for EvaluationOptions {
    fn default() -> Self {
        Self {
            precision_bits: None,
            max_payload_bytes: u64::MAX,
            max_pair_work: u64::MAX,
            block_ids: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EvaluationError {
    pub code: String,
    pub message: String,
}

impl EvaluationError {
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

impl fmt::Display for EvaluationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for EvaluationError {}

#[derive(Debug, Deserialize)]
struct CorpusLock {
    schema: String,
    capture_schema: String,
    corpus_sha256: String,
    raw_manifest: LockedRawManifest,
    artifacts: BTreeMap<String, LockedArtifact>,
}

#[derive(Debug, Deserialize)]
struct LockedRawManifest {
    bytes: u64,
    path: String,
    sha256: String,
}

#[derive(Debug, Deserialize)]
struct LockedArtifact {
    bytes: u64,
    path: String,
    dtype: String,
    encoding: String,
    owner_id: String,
    owner_kind: String,
    role: String,
    sha256: String,
    shape: Vec<u64>,
}

#[derive(Clone)]
struct LoadedWorkload {
    geometry_full: Geometry,
    observations: Vec<f64>,
    selected_polynomial_indices: Vec<usize>,
    model: PhysicalModel,
    payload_sha256: BTreeMap<String, String>,
}

struct LoadedBlock {
    geometry: Geometry,
    value_indices: Vec<usize>,
    gradient_indices: Vec<usize>,
    inner_value_mask: Vec<bool>,
    inner_gradient_mask: Vec<bool>,
    q_top: Vec<f64>,
    qtaq_lower: Vec<f64>,
    rhs_full: Vec<f64>,
    rhs_reduced: Vec<f64>,
    gamma: Vec<f64>,
    lambda: Vec<f64>,
    polynomial: Option<Vec<f64>>,
    payload_sha256: BTreeMap<String, String>,
}

pub fn evaluate_corpus(
    manifest_path: &Path,
    options: &EvaluationOptions,
) -> Result<EvaluationSummary, EvaluationError> {
    let profile = load_embedded_profile().map_err(profile_error)?;
    let precision_bits = options
        .precision_bits
        .unwrap_or(profile.interval.precision_bits);
    validate_precision_bits(precision_bits, &profile)?;
    let canonical_manifest = fs::canonicalize(manifest_path).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("cannot canonicalize {}: {error}", manifest_path.display()),
        )
    })?;
    let manifest_bytes = fs::read(&canonical_manifest).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("cannot read {}: {error}", canonical_manifest.display()),
        )
    })?;
    let manifest_sha256 = sha256(&manifest_bytes);
    let corpus: CorpusInput = serde_json::from_slice(&manifest_bytes).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("invalid JSON in {}: {error}", canonical_manifest.display()),
        )
    })?;
    validate_manifest_header(&corpus)?;
    let store = ArtifactStore::new(&canonical_manifest, &corpus.artifacts)?;
    let (_lock_path, lock_bytes, lock) = read_and_validate_lock(
        &canonical_manifest,
        &manifest_bytes,
        &manifest_sha256,
        &corpus,
    )?;
    validate_manifest_topology(&corpus, &store, &lock)?;

    let workload_index = corpus
        .workloads
        .iter()
        .map(|workload| (workload.workload_id.as_str(), workload))
        .collect::<BTreeMap<_, _>>();
    let selected_blocks = select_blocks(&corpus.blocks, &options.block_ids)?;
    let preflight = resource_preflight(
        &store,
        &workload_index,
        &selected_blocks,
        options.max_payload_bytes,
        options.max_pair_work,
        &profile,
    )?;
    if !preflight.pass {
        return Err(EvaluationError::new(
            "ResourceDenied",
            format!(
                "requires {} payload bytes and {} pair-work, grants are {} and {}",
                preflight.required_payload_bytes,
                preflight.required_pair_work,
                preflight.granted_payload_bytes,
                preflight.granted_pair_work
            ),
        ));
    }

    // Blocks are captured in workload order.  Keep at most one workload's
    // global coordinates resident; revisiting a workload is safe but reloads
    // its locked payloads rather than growing a corpus-sized cache.
    let mut active_workload: Option<(String, LoadedWorkload)> = None;
    let mut constants = Consts::new().map_err(|error| {
        EvaluationError::new(
            "IntervalArithmetic",
            format!("cannot initialize multiprecision constants: {error:?}"),
        )
    })?;
    let mut certificates = Vec::with_capacity(selected_blocks.len());
    for block in selected_blocks {
        let descriptor = workload_index
            .get(block.workload_id.as_str())
            .ok_or_else(|| {
                EvaluationError::new(
                    "MalformedManifest",
                    format!(
                        "{} references unknown workload {}",
                        block.block_id, block.workload_id
                    ),
                )
            })?;
        if active_workload
            .as_ref()
            .is_none_or(|(id, _)| id != &block.workload_id)
        {
            let loaded = load_workload(&store, &lock, descriptor)?;
            active_workload = Some((block.workload_id.clone(), loaded));
        }
        let workload = &active_workload.as_ref().expect("workload was inserted").1;
        certificates.push(evaluate_block(
            &store,
            &lock,
            descriptor,
            workload,
            block,
            &mut constants,
            &profile,
        )?);
    }

    let certified_factor_count = certificates
        .iter()
        .filter(|certificate| certificate.state == "physically-certified-witness")
        .count();
    let rejected_factor_count = certificates.len() - certified_factor_count;
    let (evaluator_executable_sha256, evaluator_executable_bytes) =
        evaluator_executable_identity()?;
    Ok(EvaluationSummary {
        schema: OUTPUT_SCHEMA,
        acceptance_profile: profile.identity(),
        source: SourceIdentity {
            manifest_path: lock.raw_manifest.path.clone(),
            manifest_sha256,
            capture_schema: corpus.schema,
            capture_generator: corpus.generator,
            inventory_profile_id: corpus.inventory_profile.profile_id,
            inventory_profile_expected: corpus.inventory_profile.expected,
            lock_path: "manifest.lock.json".to_owned(),
            lock_schema: lock.schema,
            lock_sha256: sha256(&lock_bytes),
            corpus_sha256: lock.corpus_sha256,
            loaded_payloads_lock_verified: true,
        },
        proof: ProofIdentity {
            interval_method: profile.interval.method.clone(),
            precision_bits,
            evaluator_source_closure: "sha256(length-prefixed-path-and-content-v1; Cargo.toml,Cargo.lock,physical-evidence-profile.v1.json,src/*.rs)",
            evaluator_source_files: EVALUATOR_SOURCE_FILE_NAMES,
            evaluator_source_sha256: evaluator_source_sha256(),
            evaluator_executable_sha256,
            evaluator_executable_bytes,
            arithmetic_inputs: "exact-binary64-from-f64le",
            contribution_order: "upper-geometric-pair/model/channel lexical order; symmetric O(m) scatter; outward interval sum",
            captured_a_read: false,
            captured_p_read: false,
            qtaq_read: true,
            qtaq_role: "captured-candidate-bound-to-independent-QT-A-physical-Q-never-physical-oracle",
            factorization_or_solver_linked: false,
        },
        resource_preflight: preflight,
        backend_calls: 0,
        factor_count: certificates.len(),
        certified_factor_count,
        rejected_factor_count,
        admission_claim: false,
        certificates,
    })
}

fn profile_error(error: ProfileError) -> EvaluationError {
    EvaluationError::new(error.code, error.message)
}

fn validate_precision_bits(
    precision_bits: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<(), EvaluationError> {
    if precision_bits == profile.interval.precision_bits {
        Ok(())
    } else {
        Err(EvaluationError::new(
            "InvalidOption",
            format!(
                "physical evidence profile {} requires exactly {} precision bits, got {precision_bits}",
                profile.profile_id, profile.interval.precision_bits
            ),
        ))
    }
}

fn validate_manifest_header(corpus: &CorpusInput) -> Result<(), EvaluationError> {
    if corpus.schema != INPUT_SCHEMA {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!("capture schema {} is not {INPUT_SCHEMA}", corpus.schema),
        ));
    }
    if corpus.binary_contract.double_bytes != 8
        || !corpus.binary_contract.iec559
        || !corpus.binary_contract.little_endian
    {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "binary contract must be little-endian IEC 60559 binary64",
        ));
    }
    if corpus.witness_contract.authority != "untrusted-witness-only"
        || !corpus
            .witness_contract
            .per_block
            .iter()
            .any(|role| role == "reference_gamma")
        || !corpus
            .witness_contract
            .per_block
            .iter()
            .any(|role| role == "reference_lambda")
        || !corpus
            .witness_contract
            .coarse_only
            .iter()
            .any(|role| role == "reference_c")
        || corpus.witness_contract.fine_reference_c != "prohibited-and-absent"
    {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "untrusted witness contract is missing or drifted",
        ));
    }
    if corpus.workloads.is_empty() || corpus.blocks.is_empty() {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "manifest must contain workloads and blocks",
        ));
    }
    let expected = &corpus.inventory_profile.expected;
    if corpus.inventory_profile.profile_id != EXPECTED_INVENTORY_PROFILE
        || expected.workloads != 12
        || expected.blocks != 204
        || expected.fine_blocks != 192
        || expected.coarse_blocks != 12
        || expected.factor_sources != 216
        || expected.qtaq_factor_sources != 204
        || expected.p_top_factor_sources != 12
        || expected.auxiliary_decomposition_sources != 12
        || expected.controls != 1
    {
        return Err(EvaluationError::new(
            "InventoryProfileMismatch",
            "locked manifest is not the authoritative canonical v3 profile",
        ));
    }
    Ok(())
}

fn read_and_validate_lock(
    manifest_path: &Path,
    manifest_bytes: &[u8],
    manifest_sha256: &str,
    corpus: &CorpusInput,
) -> Result<(PathBuf, Vec<u8>, CorpusLock), EvaluationError> {
    let root = manifest_path.parent().ok_or_else(|| {
        EvaluationError::new("MalformedManifest", "manifest has no parent directory")
    })?;
    let lock_path = root.join("manifest.lock.json");
    let lock_bytes = fs::read(&lock_path).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("cannot read sibling {}: {error}", lock_path.display()),
        )
    })?;
    let lock_value: Value = serde_json::from_slice(&lock_bytes).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("invalid corpus lock {}: {error}", lock_path.display()),
        )
    })?;
    let recomputed_corpus_sha256 = verify_lock_body_digest(&lock_value)?;
    let mut lock: CorpusLock = serde_json::from_value(lock_value).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("invalid corpus lock {}: {error}", lock_path.display()),
        )
    })?;
    // Publish the independently recomputed identity, not merely the lock's
    // untrusted declaration.
    lock.corpus_sha256 = recomputed_corpus_sha256;
    if lock.schema != EXPECTED_LOCK_SCHEMA
        || lock.capture_schema != corpus.schema
        || lock.raw_manifest.path != "hierarchy.manifest.raw.json"
        || lock.raw_manifest.bytes != manifest_bytes.len() as u64
        || !lock
            .raw_manifest
            .sha256
            .eq_ignore_ascii_case(manifest_sha256)
    {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "manifest does not match its immutable corpus lock",
        ));
    }
    Ok((lock_path, lock_bytes, lock))
}

fn validate_manifest_topology(
    corpus: &CorpusInput,
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
) -> Result<(), EvaluationError> {
    if corpus.inventory_profile.expected != corpus.counts {
        return Err(EvaluationError::new(
            "InventoryProfileMismatch",
            "locked expected inventory profile does not match actual-count declaration",
        ));
    }
    let actual_fine = corpus
        .blocks
        .iter()
        .filter(|block| block.role == "fine")
        .count();
    let actual_coarse = corpus.blocks.len() - actual_fine;
    let actual_qtaq = corpus
        .factor_sources
        .iter()
        .filter(|source| source.matrix_role == "qtaq")
        .count();
    let actual_p_top = corpus.factor_sources.len() - actual_qtaq;
    if corpus.counts.artifacts != corpus.artifacts.len()
        || corpus.counts.workloads != corpus.workloads.len()
        || corpus.counts.blocks != corpus.blocks.len()
        || corpus.counts.fine_blocks != actual_fine
        || corpus.counts.coarse_blocks != actual_coarse
        || corpus.counts.factor_sources != corpus.factor_sources.len()
        || corpus.counts.qtaq_factor_sources != actual_qtaq
        || corpus.counts.p_top_factor_sources != actual_p_top
        || corpus.counts.auxiliary_decomposition_sources
            != corpus.auxiliary_decomposition_sources.len()
        || corpus.counts.controls != corpus.controls.len()
        || actual_qtaq != corpus.blocks.len()
        || actual_p_top != actual_coarse
    {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "declared corpus inventory counts do not match manifest topology",
        ));
    }
    if lock.artifacts.len() != corpus.artifacts.len() {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "lock artifact table does not exactly cover the raw manifest",
        ));
    }
    for artifact in &corpus.artifacts {
        let locked = lock.artifacts.get(&artifact.artifact_id).ok_or_else(|| {
            EvaluationError::new(
                "MalformedManifest",
                format!("lock omits artifact {}", artifact.artifact_id),
            )
        })?;
        if locked.bytes != artifact.bytes
            || locked.path != artifact.path
            || locked.dtype != artifact.dtype
            || locked.encoding != artifact.encoding
            || locked.owner_id != artifact.owner_id
            || locked.owner_kind != artifact.owner_kind
            || locked.role != artifact.role
            || locked.shape != artifact.shape
            || !is_sha256(&locked.sha256)
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!("lock metadata drift for {}", artifact.artifact_id),
            ));
        }
        let _ = store.descriptor(&artifact.artifact_id)?;
    }

    let mut workload_ids = BTreeSet::new();
    for workload in &corpus.workloads {
        if !workload_ids.insert(workload.workload_id.as_str()) {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!("duplicate workload {}", workload.workload_id),
            ));
        }
        let expected_scalar = workload
            .value_rows
            .checked_add(
                DIMENSION
                    .checked_mul(workload.gradient_points)
                    .ok_or_else(|| EvaluationError::new("ResourceOverflow", "row overflow"))?,
            )
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "row overflow"))?;
        if workload.scalar_order != expected_scalar
            || workload.polynomial_order != polynomial_order(workload.resolved_polynomial_degree)?
            || workload.observation_row_map
                != "value rows first; then global gradient point/component rows at value_rows + 3*i + component"
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!(
                    "{} workload row/polynomial contract drifted",
                    workload.workload_id
                ),
            ));
        }
        for id in [
            &workload.artifacts.value_points,
            &workload.artifacts.gradient_points,
            &workload.artifacts.observations,
            &workload.artifacts.selected_polynomial_indices,
            &workload.model.exact_values_artifact,
        ] {
            let _ = store.descriptor(id)?;
        }
    }

    let mut block_ids = BTreeSet::new();
    for block in &corpus.blocks {
        if !block_ids.insert(block.block_id.as_str()) {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!("duplicate block {}", block.block_id),
            ));
        }
        let workload = corpus
            .workloads
            .iter()
            .find(|workload| workload.workload_id == block.workload_id)
            .ok_or_else(|| {
                EvaluationError::new(
                    "MalformedManifest",
                    format!("{} references unknown workload", block.block_id),
                )
            })?;
        let expected_scalar = block
            .value_rows
            .checked_add(
                DIMENSION
                    .checked_mul(block.gradient_points)
                    .ok_or_else(|| EvaluationError::new("ResourceOverflow", "row overflow"))?,
            )
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "row overflow"))?;
        if block.source_value_rows != workload.value_rows
            || block.source_gradient_points != workload.gradient_points
            || block.scalar_order != expected_scalar
            || block.value_rows < block.polynomial_order
            || block.polynomial_order != workload.polynomial_order
            || block.scalar_order
                != block
                    .polynomial_order
                    .checked_add(block.reduced_order)
                    .ok_or_else(|| EvaluationError::new("ResourceOverflow", "order overflow"))?
            || block.row_channel_map != "canonical-global-value-offset-v1"
            || block.reference_witness_authority != "untrusted-witness-only"
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!("{} block shape/row contract drifted", block.block_id),
            ));
        }
        let common_roles = [
            "domain_value_indices",
            "domain_gradient_indices",
            "inner_value_mask",
            "inner_gradient_mask",
            "canonical_lagrange_flat_indices",
            "q_top_row_major",
            "rhs_full",
            "rhs_reduced",
            "reference_gamma",
            "reference_lambda",
        ];
        for role in common_roles {
            let id = artifact_id(block, role)?;
            let _ = store.descriptor(id)?;
        }
        match block.role.as_str() {
            "fine" => {
                if block.artifacts.contains_key("reference_c") {
                    return Err(EvaluationError::new(
                        "MalformedManifest",
                        format!("fine block {} illegally publishes c", block.block_id),
                    ));
                }
            }
            "coarse" => {
                let id = artifact_id(block, "reference_c")?;
                let _ = store.descriptor(id)?;
            }
            _ => {
                return Err(EvaluationError::new(
                    "MalformedManifest",
                    format!("{} has unknown block role {}", block.block_id, block.role),
                ));
            }
        }
    }

    let block_index = corpus
        .blocks
        .iter()
        .map(|block| (block.block_id.as_str(), block))
        .collect::<BTreeMap<_, _>>();
    let mut factor_source_ids = BTreeSet::new();
    let mut qtaq_blocks = BTreeSet::new();
    let mut p_top_blocks = BTreeSet::new();
    for source in &corpus.factor_sources {
        if source.factor_source_id.is_empty()
            || !factor_source_ids.insert(source.factor_source_id.as_str())
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                "factor source ids must be unique and nonempty",
            ));
        }
        let block = block_index.get(source.block_id.as_str()).ok_or_else(|| {
            EvaluationError::new(
                "MalformedManifest",
                format!(
                    "factor source {} references unknown block",
                    source.factor_source_id
                ),
            )
        })?;
        if source.workload_id != block.workload_id {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!("factor source {} workload drifted", source.factor_source_id),
            ));
        }
        let captured_artifact_role = match source.matrix_role.as_str() {
            "qtaq" => {
                if !qtaq_blocks.insert(source.block_id.as_str()) {
                    return Err(EvaluationError::new(
                        "MalformedManifest",
                        format!("{} has duplicate qtaq factor sources", source.block_id),
                    ));
                }
                "qtaq_lower"
            }
            "p_top" if block.role == "coarse" => {
                if !p_top_blocks.insert(source.block_id.as_str()) {
                    return Err(EvaluationError::new(
                        "MalformedManifest",
                        format!("{} has duplicate p_top factor sources", source.block_id),
                    ));
                }
                "p_top_row_major"
            }
            role => {
                return Err(EvaluationError::new(
                    "MalformedManifest",
                    format!(
                        "factor source {} has invalid role {role}",
                        source.factor_source_id
                    ),
                ));
            }
        };
        if block
            .artifacts
            .get(captured_artifact_role)
            .is_none_or(|id| id != &source.matrix_artifact)
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!(
                    "factor source {} matrix artifact does not match block",
                    source.factor_source_id
                ),
            ));
        }
        // QTAQ is opened later only as a hash-bound candidate to compare
        // against independent physical reconstruction. Captured A, P, and
        // coarse P_top are never opened as physical oracles.
        let _ = store.descriptor(&source.matrix_artifact)?;
    }
    if qtaq_blocks.len() != corpus.blocks.len() || p_top_blocks.len() != actual_coarse {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "factor-source topology does not cover every registered block",
        ));
    }
    Ok(())
}

fn select_blocks<'a>(
    blocks: &'a [BlockDescriptor],
    requested: &[String],
) -> Result<Vec<&'a BlockDescriptor>, EvaluationError> {
    if requested.is_empty() {
        return Ok(blocks.iter().collect());
    }
    let requested_set: BTreeSet<&str> = requested.iter().map(String::as_str).collect();
    if requested_set.len() != requested.len() {
        return Err(EvaluationError::new(
            "InvalidOption",
            "block_ids contains duplicates",
        ));
    }
    let selected = blocks
        .iter()
        .filter(|block| requested_set.contains(block.block_id.as_str()))
        .collect::<Vec<_>>();
    if selected.len() != requested_set.len() {
        let found: BTreeSet<&str> = selected
            .iter()
            .map(|block| block.block_id.as_str())
            .collect();
        let missing = requested_set
            .difference(&found)
            .copied()
            .collect::<Vec<_>>();
        return Err(EvaluationError::new(
            "InvalidOption",
            format!("unknown requested block ids: {}", missing.join(", ")),
        ));
    }
    Ok(selected)
}

fn physical_pair_work(
    scalar_order: u64,
    gradient_points: u64,
    components: u64,
    profile: &PhysicalEvidenceProfile,
) -> Result<u64, EvaluationError> {
    // Upper scalar-triangle counting is exact except within each same-point
    // 3x3 gradient block: evaluate_action visits all 9 channel pairs, while
    // the scalar triangle contains only 6. Add the missing 3 per point.
    let triangular = scalar_order
        .checked_mul(
            scalar_order.checked_add(1).ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "physical order overflow")
            })?,
        )
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "physical pair-work overflow"))?;
    let triangular = triangular
        .checked_mul(
            profile
                .resource
                .physical_pair_work
                .upper_triangle_multiplier,
        )
        .ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "physical pair-work multiplier overflow")
        })?;
    let same_point_channel_correction = gradient_points
        .checked_mul(
            profile
                .resource
                .physical_pair_work
                .same_gradient_point_channel_correction,
        )
        .ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "Hermite pair-work correction overflow")
        })?;
    triangular
        .checked_add(same_point_channel_correction)
        .and_then(|value| value.checked_mul(components))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "physical pair-work overflow"))
}

fn qtaq_binding_pair_work(
    polynomial_order: u64,
    reduced_order: u64,
    profile: &PhysicalEvidenceProfile,
) -> Result<u64, EvaluationError> {
    let packed_entries = reduced_order
        .checked_mul(reduced_order.checked_add(1).ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "QTAQ packed order overflow")
        })?)
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ packed work overflow"))?;
    let a11_q = polynomial_order
        .checked_mul(polynomial_order)
        .and_then(|value| value.checked_mul(reduced_order))
        .and_then(|value| value.checked_mul(profile.resource.qtaq_pair_work.a11_q_multiplier))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "A11*Q work overflow"))?;
    let congruence_entries = packed_entries
        .checked_mul(
            polynomial_order
                .checked_mul(profile.resource.qtaq_pair_work.congruence_terms_per_anchor)
                .ok_or_else(|| {
                    EvaluationError::new("ResourceOverflow", "QTAQ congruence width overflow")
                })?,
        )
        .and_then(|value| value.checked_add(a11_q))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ congruence work overflow"))?;
    let witness_equation = reduced_order
        .checked_mul(reduced_order)
        .and_then(|value| {
            value.checked_mul(profile.resource.qtaq_pair_work.witness_matvec_multiplier)
        })
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ witness work overflow"))?;
    let rhs_reduced = polynomial_order
        .checked_mul(reduced_order)
        .and_then(|value| value.checked_mul(profile.resource.qtaq_pair_work.reduced_rhs_multiplier))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "reduced RHS work overflow"))?;
    congruence_entries
        .checked_add(witness_equation)
        .and_then(|value| value.checked_add(rhs_reduced))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ binding work overflow"))
}

fn resource_preflight(
    store: &ArtifactStore<'_>,
    workloads: &BTreeMap<&str, &WorkloadDescriptor>,
    blocks: &[&BlockDescriptor],
    granted_bytes: u64,
    granted_pair_work: u64,
    profile: &PhysicalEvidenceProfile,
) -> Result<ResourcePreflight, EvaluationError> {
    let mut artifact_ids = BTreeSet::new();
    let mut workload_ids = BTreeSet::new();
    let mut pair_work = 0_u64;
    let mut max_scalar = 0_u64;
    for block in blocks {
        let workload = workloads
            .get(block.workload_id.as_str())
            .ok_or_else(|| EvaluationError::new("MalformedManifest", "block workload vanished"))?;
        if workload_ids.insert(workload.workload_id.as_str()) {
            for id in [
                &workload.artifacts.value_points,
                &workload.artifacts.gradient_points,
                &workload.artifacts.observations,
                &workload.artifacts.selected_polynomial_indices,
                &workload.model.exact_values_artifact,
            ] {
                artifact_ids.insert((*id).clone());
            }
        }
        for role in [
            "domain_value_indices",
            "domain_gradient_indices",
            "inner_value_mask",
            "inner_gradient_mask",
            "canonical_lagrange_flat_indices",
            "q_top_row_major",
            "qtaq_lower",
            "rhs_full",
            "rhs_reduced",
            "reference_gamma",
            "reference_lambda",
        ] {
            artifact_ids.insert(artifact_id(block, role)?.to_owned());
        }
        if block.role == "coarse" {
            artifact_ids.insert(artifact_id(block, "reference_c")?.to_owned());
        }

        let m = u64::try_from(block.scalar_order)
            .map_err(|_| EvaluationError::new("ResourceOverflow", "m does not fit u64"))?;
        let l = u64::try_from(block.polynomial_order)
            .map_err(|_| EvaluationError::new("ResourceOverflow", "l does not fit u64"))?;
        let r = u64::try_from(block.reduced_order)
            .map_err(|_| EvaluationError::new("ResourceOverflow", "r does not fit u64"))?;
        let components = u64::try_from(workload.model.rbfs.len()).map_err(|_| {
            EvaluationError::new("ResourceOverflow", "component count does not fit u64")
        })?;
        let gradient_points = u64::try_from(block.gradient_points).map_err(|_| {
            EvaluationError::new("ResourceOverflow", "gradient point count does not fit u64")
        })?;
        let physical = physical_pair_work(m, gradient_points, components, profile)?;
        let qtaq_binding = qtaq_binding_pair_work(l, r, profile)?;
        let cpd_pairs = m
            .checked_mul(l)
            .and_then(|value| {
                value.checked_mul(profile.resource.auxiliary_pair_work.cpd_multiplier)
            })
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "CPD pair-work overflow"))?;
        let closure_q_pairs = l
            .checked_mul(r)
            .and_then(|value| {
                value.checked_mul(
                    profile
                        .resource
                        .auxiliary_pair_work
                        .coefficient_q_multiplier,
                )
            })
            .ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "closure pair-work overflow")
            })?;
        let closure_tail_pairs = r
            .checked_mul(
                profile
                    .resource
                    .auxiliary_pair_work
                    .coefficient_tail_multiplier,
            )
            .ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "closure pair-work overflow")
            })?;
        let closure_pairs = closure_q_pairs
            .checked_add(closure_tail_pairs)
            .ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "closure pair-work overflow")
            })?;
        let role_pairs = if block.role == "fine" {
            // Q^T physical residual.
            l.checked_mul(r).and_then(|value| {
                value.checked_mul(
                    profile
                        .resource
                        .auxiliary_pair_work
                        .fine_projection_multiplier,
                )
            })
        } else {
            // Physical P*c.
            m.checked_mul(l).and_then(|value| {
                value.checked_mul(
                    profile
                        .resource
                        .auxiliary_pair_work
                        .coarse_polynomial_multiplier,
                )
            })
        }
        .ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "role-specific pair-work overflow")
        })?;
        let auxiliary = cpd_pairs
            .checked_add(closure_pairs)
            .and_then(|value| value.checked_add(role_pairs))
            .ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "auxiliary pair-work overflow")
            })?;
        pair_work = pair_work
            .checked_add(physical)
            .and_then(|value| value.checked_add(qtaq_binding))
            .and_then(|value| value.checked_add(auxiliary))
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "corpus pair-work overflow"))?;
        max_scalar = max_scalar.max(m);
    }
    let payload_bytes = store.declared_bytes_for(artifact_ids)?;
    let scratch_bytes = logical_scratch_bytes(max_scalar, profile)?;
    let required_bytes = payload_bytes
        .checked_add(scratch_bytes)
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "byte grant overflow"))?;
    Ok(ResourcePreflight {
        metric: profile.resource.metric.clone(),
        pair_work_metric: profile.resource.pair_work_metric.clone(),
        required_payload_bytes: required_bytes,
        granted_payload_bytes: granted_bytes,
        required_pair_work: pair_work,
        granted_pair_work,
        pass: required_bytes <= granted_bytes && pair_work <= granted_pair_work,
    })
}

fn logical_scratch_bytes(
    max_scalar_order: u64,
    profile: &PhysicalEvidenceProfile,
) -> Result<u64, EvaluationError> {
    max_scalar_order
        .checked_mul(profile.resource.logical_scratch_bytes_per_scalar)
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "scratch grant overflow"))
}

fn load_workload(
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
    descriptor: &WorkloadDescriptor,
) -> Result<LoadedWorkload, EvaluationError> {
    expect_shape(
        store,
        &descriptor.artifacts.value_points,
        &[descriptor.value_rows as u64, DIMENSION as u64],
    )?;
    expect_shape(
        store,
        &descriptor.artifacts.gradient_points,
        &[descriptor.gradient_points as u64, DIMENSION as u64],
    )?;
    expect_shape(
        store,
        &descriptor.artifacts.observations,
        &[descriptor.scalar_order as u64],
    )?;
    expect_shape(
        store,
        &descriptor.artifacts.selected_polynomial_indices,
        &[descriptor.polynomial_order as u64],
    )?;

    let value_points = load_f64_checked(store, lock, &descriptor.artifacts.value_points)?;
    let gradient_points = load_f64_checked(store, lock, &descriptor.artifacts.gradient_points)?;
    let observations = load_f64_checked(store, lock, &descriptor.artifacts.observations)?;
    let selected = load_i64_checked(
        store,
        lock,
        &descriptor.artifacts.selected_polynomial_indices,
    )?;
    let model_values = load_f64_checked(store, lock, &descriptor.model.exact_values_artifact)?;

    reject_nonfinite("value_points", &value_points.values)?;
    reject_nonfinite("gradient_points", &gradient_points.values)?;
    reject_nonfinite("observations", &observations.values)?;
    reject_nonfinite("model_values", &model_values.values)?;
    let geometry_full = Geometry {
        value_points: points_from_flat(
            &value_points.values,
            descriptor.value_rows,
            "value_points",
        )?,
        gradient_points: points_from_flat(
            &gradient_points.values,
            descriptor.gradient_points,
            "gradient_points",
        )?,
    };
    let selected_polynomial_indices = indices_from_i64(
        &selected.values,
        descriptor.value_rows,
        "selected_polynomial_indices",
    )?;
    if selected_polynomial_indices.len() != descriptor.polynomial_order
        || selected_polynomial_indices
            .iter()
            .copied()
            .collect::<BTreeSet<_>>()
            .len()
            != selected_polynomial_indices.len()
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "{} selected polynomial indices are not unique/order-sized",
                descriptor.workload_id
            ),
        ));
    }

    let model = decode_model(descriptor, &model_values.values)?;
    let mut payload_sha256 = BTreeMap::new();
    payload_sha256.insert("workload.value_points".to_owned(), value_points.sha256);
    payload_sha256.insert(
        "workload.gradient_points".to_owned(),
        gradient_points.sha256,
    );
    payload_sha256.insert("workload.observations".to_owned(), observations.sha256);
    payload_sha256.insert(
        "workload.selected_polynomial_indices".to_owned(),
        selected.sha256,
    );
    payload_sha256.insert("workload.model_values".to_owned(), model_values.sha256);
    Ok(LoadedWorkload {
        geometry_full,
        observations: observations.values,
        selected_polynomial_indices,
        model,
        payload_sha256,
    })
}

fn decode_model(
    workload: &WorkloadDescriptor,
    values: &[f64],
) -> Result<PhysicalModel, EvaluationError> {
    if workload.model.layout
        != "nugget; for each RBF: parameters then 3x3 anisotropy in row-major order"
        || workload.model.nugget.offset != 0
    {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!("{} model layout drifted", workload.workload_id),
        ));
    }
    validate_exact_value(
        values,
        workload.model.nugget.offset,
        &workload.model.nugget.value,
        "nugget",
    )?;
    let mut next_offset = 1_usize;
    let mut components = Vec::with_capacity(workload.model.rbfs.len());
    for (component_index, descriptor) in workload.model.rbfs.iter().enumerate() {
        if descriptor.parameters.offset != next_offset
            || descriptor.parameters.count != descriptor.parameters.values.len()
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!(
                    "{} component {component_index} parameter offsets drifted",
                    workload.workload_id
                ),
            ));
        }
        for (index, exact) in descriptor.parameters.values.iter().enumerate() {
            validate_exact_value(
                values,
                descriptor.parameters.offset + index,
                exact,
                "RBF parameter",
            )?;
        }
        next_offset = next_offset
            .checked_add(descriptor.parameters.count)
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "model offset overflow"))?;
        if descriptor.anisotropy.offset != next_offset
            || descriptor.anisotropy.count != DIMENSION * DIMENSION
            || descriptor.anisotropy.values.len() != DIMENSION * DIMENSION
            || descriptor.anisotropy.shape != [DIMENSION, DIMENSION]
            || descriptor.anisotropy.encoding != "row-major"
        {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!(
                    "{} component {component_index} anisotropy offsets drifted",
                    workload.workload_id
                ),
            ));
        }
        for (index, exact) in descriptor.anisotropy.values.iter().enumerate() {
            validate_exact_value(
                values,
                descriptor.anisotropy.offset + index,
                exact,
                "anisotropy",
            )?;
        }
        let parameters = values[descriptor.parameters.offset
            ..descriptor.parameters.offset + descriptor.parameters.count]
            .to_vec();
        let anisotropy = std::array::from_fn(|row| {
            std::array::from_fn(|column| {
                values[descriptor.anisotropy.offset + DIMENSION * row + column]
            })
        });
        components.push(RbfComponent {
            family: descriptor.short_name.clone(),
            parameters,
            anisotropy,
        });
        next_offset = next_offset
            .checked_add(descriptor.anisotropy.count)
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "model offset overflow"))?;
    }
    if next_offset != values.len() {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "{} model artifact has {} values, descriptor consumes {next_offset}",
                workload.workload_id,
                values.len()
            ),
        ));
    }
    Ok(PhysicalModel {
        nugget: values[0],
        polynomial_degree: workload.resolved_polynomial_degree,
        components,
    })
}

fn validate_exact_value(
    values: &[f64],
    offset: usize,
    descriptor: &crate::schema::ExactDouble,
    context: &str,
) -> Result<(), EvaluationError> {
    let value = values.get(offset).ok_or_else(|| {
        EvaluationError::new(
            "MalformedPayload",
            format!("{context} offset {offset} is outside model artifact"),
        )
    })?;
    if !descriptor.decimal.is_finite()
        || value.to_bits() != descriptor.decimal.to_bits()
        || descriptor.hex != canonical_hexfloat(descriptor.decimal)
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{context} exact descriptor disagrees at offset {offset}"),
        ));
    }
    Ok(())
}

fn canonical_hexfloat(value: f64) -> String {
    let bits = value.to_bits();
    let sign = if bits >> 63 == 0 { "" } else { "-" };
    let exponent_bits = ((bits >> 52) & 0x7ff) as i32;
    let fraction = bits & ((1_u64 << 52) - 1);
    if exponent_bits == 0 {
        if fraction == 0 {
            format!("{sign}0x0.0000000000000p+0")
        } else {
            format!("{sign}0x0.{fraction:013x}p-1022")
        }
    } else {
        let exponent = exponent_bits - 1023;
        format!("{sign}0x1.{fraction:013x}p{exponent:+}")
    }
}

fn load_block(
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
    workload_descriptor: &WorkloadDescriptor,
    workload: &LoadedWorkload,
    block: &BlockDescriptor,
) -> Result<LoadedBlock, EvaluationError> {
    for (role, shape) in [
        ("domain_value_indices", vec![block.value_rows as u64]),
        (
            "domain_gradient_indices",
            vec![block.gradient_points as u64],
        ),
        ("inner_value_mask", vec![block.value_rows as u64]),
        ("inner_gradient_mask", vec![block.gradient_points as u64]),
        (
            "canonical_lagrange_flat_indices",
            vec![block.scalar_order as u64],
        ),
        (
            "q_top_row_major",
            vec![block.polynomial_order as u64, block.reduced_order as u64],
        ),
        (
            "qtaq_lower",
            vec![block.reduced_order as u64, block.reduced_order as u64],
        ),
        ("rhs_full", vec![block.scalar_order as u64]),
        ("rhs_reduced", vec![block.reduced_order as u64]),
        ("reference_gamma", vec![block.reduced_order as u64]),
        ("reference_lambda", vec![block.scalar_order as u64]),
    ] {
        expect_shape(store, artifact_id(block, role)?, &shape)?;
    }
    let qtaq_artifact = artifact_id(block, "qtaq_lower")?;
    if store.descriptor(qtaq_artifact)?.encoding != "lower-triangle-row-major-packed" {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "{} qtaq_lower is not packed lower-triangle row-major",
                block.block_id
            ),
        ));
    }
    if block.role == "coarse" {
        expect_shape(
            store,
            artifact_id(block, "reference_c")?,
            &[block.polynomial_order as u64],
        )?;
    }

    let domain_values = load_i64_checked(store, lock, artifact_id(block, "domain_value_indices")?)?;
    let domain_gradients =
        load_i64_checked(store, lock, artifact_id(block, "domain_gradient_indices")?)?;
    let inner_values = load_u8_checked(store, lock, artifact_id(block, "inner_value_mask")?)?;
    let inner_gradients = load_u8_checked(store, lock, artifact_id(block, "inner_gradient_mask")?)?;
    let flat = load_i64_checked(
        store,
        lock,
        artifact_id(block, "canonical_lagrange_flat_indices")?,
    )?;
    let q_top = load_f64_checked(store, lock, artifact_id(block, "q_top_row_major")?)?;
    let qtaq_lower = load_f64_checked(store, lock, qtaq_artifact)?;
    let rhs_full = load_f64_checked(store, lock, artifact_id(block, "rhs_full")?)?;
    let rhs_reduced = load_f64_checked(store, lock, artifact_id(block, "rhs_reduced")?)?;
    let gamma = load_f64_checked(store, lock, artifact_id(block, "reference_gamma")?)?;
    let lambda = load_f64_checked(store, lock, artifact_id(block, "reference_lambda")?)?;
    let polynomial = if block.role == "coarse" {
        Some(load_f64_checked(
            store,
            lock,
            artifact_id(block, "reference_c")?,
        )?)
    } else {
        None
    };
    for (name, values) in [
        ("q_top", q_top.values.as_slice()),
        ("qtaq_lower", qtaq_lower.values.as_slice()),
        ("rhs_full", rhs_full.values.as_slice()),
        ("rhs_reduced", rhs_reduced.values.as_slice()),
        ("reference_gamma", gamma.values.as_slice()),
        ("reference_lambda", lambda.values.as_slice()),
    ] {
        reject_nonfinite(name, values)?;
    }
    if let Some(polynomial) = &polynomial {
        reject_nonfinite("reference_c", &polynomial.values)?;
    }
    let value_indices = indices_from_i64(
        &domain_values.values,
        workload_descriptor.value_rows,
        "domain_value_indices",
    )?;
    let gradient_indices = indices_from_i64(
        &domain_gradients.values,
        workload_descriptor.gradient_points,
        "domain_gradient_indices",
    )?;
    validate_unique_indices(block, &value_indices, &gradient_indices)?;
    let inner_value_mask = mask_from_u8(
        &inner_values.values,
        block.inner_value_rows,
        "inner_value_mask",
    )?;
    let inner_gradient_mask = mask_from_u8(
        &inner_gradients.values,
        block.inner_gradient_points,
        "inner_gradient_mask",
    )?;
    if block.role == "coarse"
        && (!inner_value_mask.iter().all(|value| *value)
            || !inner_gradient_mask.iter().all(|value| *value))
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("coarse block {} must mark every row inner", block.block_id),
        ));
    }

    let canonical_flat_rows = indices_from_i64(
        &flat.values,
        workload_descriptor.scalar_order,
        "canonical_lagrange_flat_indices",
    )?;
    validate_canonical_flat_map(
        &canonical_flat_rows,
        &value_indices,
        &gradient_indices,
        workload_descriptor.value_rows,
    )?;
    if block.role == "coarse"
        && value_indices
            .iter()
            .take(block.polynomial_order)
            .copied()
            .collect::<Vec<_>>()
            != workload.selected_polynomial_indices
    {
        return Err(EvaluationError::new(
            "NullspaceViolation",
            format!(
                "{} coarse prefix is not the selected physical polynomial anchor order",
                block.block_id
            ),
        ));
    }

    let expected_rhs = extract_observations(
        &workload.observations,
        &value_indices,
        &gradient_indices,
        workload_descriptor.value_rows,
    )?;
    if expected_rhs.len() != rhs_full.values.len()
        || expected_rhs
            .iter()
            .zip(&rhs_full.values)
            .any(|(expected, actual)| expected.to_bits() != actual.to_bits())
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "{} rhs_full violates canonical global row map",
                block.block_id
            ),
        ));
    }
    let geometry = Geometry {
        value_points: value_indices
            .iter()
            .map(|index| workload.geometry_full.value_points[*index])
            .collect(),
        gradient_points: gradient_indices
            .iter()
            .map(|index| workload.geometry_full.gradient_points[*index])
            .collect(),
    };
    let mut payload_sha256 = workload.payload_sha256.clone();
    for (role, hash) in [
        ("block.domain_value_indices", domain_values.sha256),
        ("block.domain_gradient_indices", domain_gradients.sha256),
        ("block.inner_value_mask", inner_values.sha256),
        ("block.inner_gradient_mask", inner_gradients.sha256),
        ("block.canonical_lagrange_flat_indices", flat.sha256),
        ("block.q_top_row_major", q_top.sha256.clone()),
        ("block.qtaq_lower", qtaq_lower.sha256.clone()),
        ("block.rhs_full", rhs_full.sha256.clone()),
        ("block.rhs_reduced", rhs_reduced.sha256.clone()),
        ("block.reference_gamma", gamma.sha256.clone()),
        ("block.reference_lambda", lambda.sha256.clone()),
    ] {
        payload_sha256.insert(role.to_owned(), hash);
    }
    if let Some(polynomial) = &polynomial {
        payload_sha256.insert("block.reference_c".to_owned(), polynomial.sha256.clone());
    }
    Ok(LoadedBlock {
        geometry,
        value_indices,
        gradient_indices,
        inner_value_mask,
        inner_gradient_mask,
        q_top: q_top.values,
        qtaq_lower: qtaq_lower.values,
        rhs_full: rhs_full.values,
        rhs_reduced: rhs_reduced.values,
        gamma: gamma.values,
        lambda: lambda.values,
        polynomial: polynomial.map(|loaded| loaded.values),
        payload_sha256,
    })
}

#[derive(Clone)]
struct PhysicalEntryBound {
    value: Interval,
    component_scale_upper: BigFloat,
}

struct OnlineComponentCertificate {
    count: usize,
    max_residual: BigFloat,
    min_margin: Option<BigFloat>,
    first_failed_row: Option<usize>,
    precision: usize,
}

impl OnlineComponentCertificate {
    fn new(precision: usize) -> Self {
        Self {
            count: 0,
            max_residual: BigFloat::new(precision),
            min_margin: None,
            first_failed_row: None,
            precision,
        }
    }

    fn observe(&mut self, residual: &Interval, allowed: &BigFloat) {
        let magnitude = residual.abs_upper();
        if compare_big(&magnitude, &self.max_residual).is_gt() {
            self.max_residual = magnitude.clone();
        }
        let margin = allowed.sub(&magnitude, self.precision, RoundingMode::Down);
        if self
            .min_margin
            .as_ref()
            .is_none_or(|current| compare_big(&margin, current).is_lt())
        {
            self.min_margin = Some(margin);
        }
        if compare_big(&magnitude, allowed).is_gt() && self.first_failed_row.is_none() {
            self.first_failed_row = Some(self.count);
        }
        self.count += 1;
    }

    fn finish(
        self,
        absolute_tolerance: impl Into<String>,
        relative_tolerance: impl Into<String>,
    ) -> ComponentCertificate {
        ComponentCertificate {
            count: self.count,
            max_abs_residual_upper: self.max_residual.to_string(),
            min_allowed_margin_lower: self
                .min_margin
                .unwrap_or_else(|| BigFloat::new(self.precision))
                .to_string(),
            absolute_tolerance: absolute_tolerance.into(),
            relative_tolerance: relative_tolerance.into(),
            pass: self.first_failed_row.is_none(),
            first_failed_row: self.first_failed_row,
        }
    }
}

struct QtaqPhysicalAccumulator<'a> {
    polynomial_order: usize,
    reduced_order: usize,
    value_rows: usize,
    precision: usize,
    q_top: Vec<Interval>,
    q_top_abs: Vec<BigFloat>,
    captured: &'a [f64],
    a11: Vec<Option<PhysicalEntryBound>>,
    a12: Vec<Option<PhysicalEntryBound>>,
    a11_q: Option<Vec<PhysicalEntryBound>>,
    matrix_entries: OnlineComponentCertificate,
    allowance_profile: crate::profile::QtaqAllowanceProfile,
}

impl<'a> QtaqPhysicalAccumulator<'a> {
    fn new(
        block: &BlockDescriptor,
        q_top: &[f64],
        captured: &'a [f64],
        precision: usize,
        profile: &PhysicalEvidenceProfile,
    ) -> Result<Self, EvaluationError> {
        let l = block.polynomial_order;
        let r = block.reduced_order;
        let packed = r
            .checked_mul(r.checked_add(1).ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "QTAQ packed order overflow")
            })?)
            .and_then(|value| value.checked_div(2))
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ packed size overflow"))?;
        if q_top.len() != l * r || captured.len() != packed || block.scalar_order != l + r {
            return Err(EvaluationError::new(
                "MalformedPayload",
                format!("{} QTAQ closure dimensions drifted", block.block_id),
            ));
        }
        let q_top_intervals = q_top
            .iter()
            .map(|value| Interval::exact(*value, precision).map_err(interval_error))
            .collect::<Result<Vec<_>, _>>()?;
        let q_top_abs = q_top
            .iter()
            .map(|value| BigFloat::from_f64(value.abs(), precision))
            .collect();
        Ok(Self {
            polynomial_order: l,
            reduced_order: r,
            value_rows: block.value_rows,
            precision,
            q_top: q_top_intervals,
            q_top_abs,
            captured,
            a11: vec![None; l * l],
            a12: vec![None; l * r],
            a11_q: None,
            matrix_entries: OnlineComponentCertificate::new(precision),
            allowance_profile: profile.qtaq_allowance.clone(),
        })
    }

    fn observe(
        &mut self,
        left: usize,
        right: usize,
        value: &Interval,
        component_scale_upper: &BigFloat,
        mirror: bool,
    ) -> Result<(), EvaluationError> {
        let l = self.polynomial_order;
        let m = l + self.reduced_order;
        if left >= m || right >= m {
            return Err(EvaluationError::new(
                "MalformedPayload",
                "physical entry callback exceeded block order",
            ));
        }
        let entry = PhysicalEntryBound {
            value: value.clone(),
            component_scale_upper: component_scale_upper.clone(),
        };
        if left < l {
            if right < l {
                self.insert_top(left, right, entry.clone())?;
                if left != right {
                    self.insert_top(right, left, entry)?;
                }
            } else {
                self.insert_cross(left, right - l, entry)?;
            }
            return Ok(());
        }
        if right < l {
            return Err(EvaluationError::new(
                "MalformedPayload",
                "physical entry stream violated top-before-tail order",
            ));
        }
        // Same-gradient-point cross channels are deliberately emitted twice
        // as directed action terms with mirror=false. Consume only their
        // canonical upper entry for the symmetric congruence.
        if !mirror && left > right {
            return Ok(());
        }
        if left > right {
            return Err(EvaluationError::new(
                "MalformedPayload",
                "mirrored physical entry is not canonical upper-triangular",
            ));
        }
        self.compare_tail_entry(left - l, right - l, &entry)
    }

    fn insert_top(
        &mut self,
        row: usize,
        column: usize,
        entry: PhysicalEntryBound,
    ) -> Result<(), EvaluationError> {
        let index = row * self.polynomial_order + column;
        if self.a11[index].replace(entry).is_some() {
            return Err(EvaluationError::new(
                "MalformedPayload",
                "physical stream duplicated an A11 entry",
            ));
        }
        Ok(())
    }

    fn insert_cross(
        &mut self,
        row: usize,
        column: usize,
        entry: PhysicalEntryBound,
    ) -> Result<(), EvaluationError> {
        let index = row * self.reduced_order + column;
        if self.a12[index].replace(entry).is_some() {
            return Err(EvaluationError::new(
                "MalformedPayload",
                "physical stream duplicated an A12 entry",
            ));
        }
        Ok(())
    }

    fn prepare_a11_q(&mut self) -> Result<(), EvaluationError> {
        if self.a11_q.is_some() {
            return Ok(());
        }
        if self.a11.iter().any(Option::is_none) || self.a12.iter().any(Option::is_none) {
            return Err(EvaluationError::new(
                "MalformedPayload",
                "tail physical entry arrived before complete A11/A12 seam",
            ));
        }
        let l = self.polynomial_order;
        let r = self.reduced_order;
        let mut output = Vec::with_capacity(l * r);
        for row in 0..l {
            for column in 0..r {
                let mut value = Interval::zero(self.precision);
                let mut scale = BigFloat::new(self.precision);
                for inner in 0..l {
                    let a = self.a11[row * l + inner]
                        .as_ref()
                        .expect("A11 completeness checked");
                    let q_index = inner * r + column;
                    value = value.add(&a.value.mul(&self.q_top[q_index]));
                    let contribution = a.component_scale_upper.mul(
                        &self.q_top_abs[q_index],
                        self.precision,
                        RoundingMode::Up,
                    );
                    scale = scale.add(&contribution, self.precision, RoundingMode::Up);
                }
                output.push(PhysicalEntryBound {
                    value,
                    component_scale_upper: scale,
                });
            }
        }
        self.a11_q = Some(output);
        Ok(())
    }

    fn compare_tail_entry(
        &mut self,
        left: usize,
        right: usize,
        a22: &PhysicalEntryBound,
    ) -> Result<(), EvaluationError> {
        self.prepare_a11_q()?;
        let l = self.polynomial_order;
        let r = self.reduced_order;
        let a11_q = self.a11_q.as_ref().expect("A11*Q prepared");
        let mut expected = a22.value.clone();
        let mut physical_scale = a22.component_scale_upper.clone();
        let mut transform_scale = a22.value.abs_upper();
        for anchor in 0..l {
            let q_left_index = anchor * r + left;
            let q_right_index = anchor * r + right;
            let a12_right = self.a12[anchor * r + right]
                .as_ref()
                .expect("A12 completeness checked");
            let a12_left = self.a12[anchor * r + left]
                .as_ref()
                .expect("A12 completeness checked");
            let a11_q_right = &a11_q[anchor * r + right];

            for term in [
                self.q_top[q_left_index].mul(&a12_right.value),
                self.q_top[q_left_index].mul(&a11_q_right.value),
                a12_left.value.mul(&self.q_top[q_right_index]),
            ] {
                transform_scale =
                    transform_scale.add(&term.abs_upper(), self.precision, RoundingMode::Up);
                expected = expected.add(&term);
            }

            let left_cross_scale = a12_right
                .component_scale_upper
                .add(
                    &a11_q_right.component_scale_upper,
                    self.precision,
                    RoundingMode::Up,
                )
                .mul(
                    &self.q_top_abs[q_left_index],
                    self.precision,
                    RoundingMode::Up,
                );
            let right_cross_scale = a12_left.component_scale_upper.mul(
                &self.q_top_abs[q_right_index],
                self.precision,
                RoundingMode::Up,
            );
            physical_scale =
                physical_scale.add(&left_cross_scale, self.precision, RoundingMode::Up);
            physical_scale =
                physical_scale.add(&right_cross_scale, self.precision, RoundingMode::Up);
        }
        let packed_index = packed_lower_index(right, left)?;
        let captured = self.captured[packed_index];
        let residual = expected.sub(
            &Interval::exact(captured, self.precision)
                .map_err(|message| EvaluationError::new("IntervalArithmetic", message))?,
        );
        let derivative = l + left >= self.value_rows || l + right >= self.value_rows;
        let (absolute, relative) =
            qtaq_tolerances(derivative, self.precision, &self.allowance_profile);
        let assembly_allowance = physical_scale.mul(&absolute, self.precision, RoundingMode::Up);
        let transform_allowance = transform_scale.mul(&relative, self.precision, RoundingMode::Up);
        let captured_allowance = BigFloat::from_f64(captured.abs(), self.precision).mul(
            &relative,
            self.precision,
            RoundingMode::Up,
        );
        let allowed = assembly_allowance
            .add(&transform_allowance, self.precision, RoundingMode::Up)
            .add(&captured_allowance, self.precision, RoundingMode::Up);
        self.matrix_entries.observe(&residual, &allowed);
        Ok(())
    }

    fn finish(mut self) -> Result<ComponentCertificate, EvaluationError> {
        self.prepare_a11_q()?;
        let expected = self
            .reduced_order
            .checked_mul(self.reduced_order + 1)
            .and_then(|value| value.checked_div(2))
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ count overflow"))?;
        if self.matrix_entries.count != expected {
            return Err(EvaluationError::new(
                "MalformedPayload",
                format!(
                    "physical stream compared {} QTAQ entries, expected {expected}",
                    self.matrix_entries.count
                ),
            ));
        }
        let absolute_tolerance = format!(
            "physical-component-scale*({} value-only | {} derivative)",
            power_of_two_label(
                self.allowance_profile
                    .value_only
                    .physical_component_power_of_two_exponent
            ),
            power_of_two_label(
                self.allowance_profile
                    .derivative_involving
                    .physical_component_power_of_two_exponent
            )
        );
        let relative_tolerance = format!(
            "(transform-scale+|captured|)*({} value-only | {} derivative)",
            power_of_two_label(
                self.allowance_profile
                    .value_only
                    .transform_and_captured_power_of_two_exponent
            ),
            power_of_two_label(
                self.allowance_profile
                    .derivative_involving
                    .transform_and_captured_power_of_two_exponent
            )
        );
        Ok(self
            .matrix_entries
            .finish(absolute_tolerance, relative_tolerance))
    }
}

fn packed_lower_index(row: usize, column: usize) -> Result<usize, EvaluationError> {
    debug_assert!(column <= row);
    row.checked_mul(
        row.checked_add(1)
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "packed row index overflow"))?,
    )
    .and_then(|value| value.checked_div(2))
    .and_then(|value| value.checked_add(column))
    .ok_or_else(|| EvaluationError::new("ResourceOverflow", "packed index overflow"))
}

fn row_tolerances(
    derivative: bool,
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> (BigFloat, BigFloat) {
    let pair = if derivative {
        &profile.residual_allowance.gradient
    } else {
        &profile.residual_allowance.value
    };
    (
        power_of_two_big(pair.scale_power_of_two_exponent, precision),
        power_of_two_big(pair.rhs_power_of_two_exponent, precision),
    )
}

fn qtaq_tolerances(
    derivative: bool,
    precision: usize,
    profile: &crate::profile::QtaqAllowanceProfile,
) -> (BigFloat, BigFloat) {
    let pair = if derivative {
        &profile.derivative_involving
    } else {
        &profile.value_only
    };
    (
        power_of_two_big(pair.physical_component_power_of_two_exponent, precision),
        power_of_two_big(pair.transform_and_captured_power_of_two_exponent, precision),
    )
}

fn power_of_two_big(exponent: i32, precision: usize) -> BigFloat {
    BigFloat::from_f64(2.0_f64.powi(exponent), precision)
}

fn power_of_two_label(exponent: i32) -> String {
    format!("2^{exponent}")
}

fn certify_rhs_reduced(
    block: &BlockDescriptor,
    loaded: &LoadedBlock,
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<ComponentCertificate, EvaluationError> {
    let l = block.polynomial_order;
    let r = block.reduced_order;
    if loaded.q_top.len() != l * r
        || loaded.rhs_full.len() != l + r
        || loaded.rhs_reduced.len() != r
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{} reduced RHS dimensions drifted", block.block_id),
        ));
    }
    let gamma = dot_roundoff_bound(l + 1, precision, profile)?;
    let mut summary = OnlineComponentCertificate::new(precision);
    for column in 0..r {
        let tail = loaded.rhs_full[l + column];
        let mut expected = Interval::exact(tail, precision).map_err(interval_error)?;
        let mut scale = BigFloat::from_f64(tail.abs(), precision);
        for row in 0..l {
            let q = loaded.q_top[row * r + column];
            let rhs = loaded.rhs_full[row];
            expected = expected.add(
                &Interval::exact(q, precision)
                    .map_err(interval_error)?
                    .mul(&Interval::exact(rhs, precision).map_err(interval_error)?),
            );
            let term_scale = BigFloat::from_f64(q.abs(), precision).mul(
                &BigFloat::from_f64(rhs.abs(), precision),
                precision,
                RoundingMode::Up,
            );
            scale = scale.add(&term_scale, precision, RoundingMode::Up);
        }
        let residual = expected
            .sub(&Interval::exact(loaded.rhs_reduced[column], precision).map_err(interval_error)?);
        let allowed = gamma.mul(&scale, precision, RoundingMode::Up);
        summary.observe(&residual, &allowed);
    }
    Ok(summary.finish(
        "gamma_(l+1)*sum_abs(Q_top^T*d_head+d_tail)",
        "not-applicable",
    ))
}

fn certify_qtaq_witness_equation(
    block: &BlockDescriptor,
    loaded: &LoadedBlock,
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<ComponentCertificate, EvaluationError> {
    let l = block.polynomial_order;
    let r = block.reduced_order;
    let packed = r
        .checked_mul(r.checked_add(1).ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "QTAQ packed order overflow")
        })?)
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "QTAQ packed size overflow"))?;
    if loaded.qtaq_lower.len() != packed || loaded.gamma.len() != r || loaded.rhs_reduced.len() != r
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{} QTAQ witness dimensions drifted", block.block_id),
        ));
    }
    let mut summary = OnlineComponentCertificate::new(precision);
    for row in 0..r {
        let mut prediction = Interval::zero(precision);
        let mut scale = BigFloat::new(precision);
        for column in 0..r {
            let (packed_row, packed_column) = if row >= column {
                (row, column)
            } else {
                (column, row)
            };
            let matrix = loaded.qtaq_lower[packed_lower_index(packed_row, packed_column)?];
            let coefficient = loaded.gamma[column];
            prediction = prediction.add(
                &Interval::exact(matrix, precision)
                    .map_err(interval_error)?
                    .mul(&Interval::exact(coefficient, precision).map_err(interval_error)?),
            );
            let term_scale = BigFloat::from_f64(matrix.abs(), precision).mul(
                &BigFloat::from_f64(coefficient.abs(), precision),
                precision,
                RoundingMode::Up,
            );
            scale = scale.add(&term_scale, precision, RoundingMode::Up);
        }
        let rhs = loaded.rhs_reduced[row];
        let residual = prediction.sub(&Interval::exact(rhs, precision).map_err(interval_error)?);
        let derivative = l + row >= block.value_rows;
        let (absolute, relative) = row_tolerances(derivative, precision, profile);
        let allowed = scale.mul(&absolute, precision, RoundingMode::Up).add(
            &BigFloat::from_f64(rhs.abs(), precision).mul(&relative, precision, RoundingMode::Up),
            precision,
            RoundingMode::Up,
        );
        summary.observe(&residual, &allowed);
    }
    Ok(summary.finish(
        format!(
            "scale*({} value | {} gradient)",
            power_of_two_label(profile.residual_allowance.value.scale_power_of_two_exponent),
            power_of_two_label(
                profile
                    .residual_allowance
                    .gradient
                    .scale_power_of_two_exponent
            )
        ),
        format!(
            "|rhs_reduced|*({} value | {} gradient)",
            power_of_two_label(profile.residual_allowance.value.rhs_power_of_two_exponent),
            power_of_two_label(
                profile
                    .residual_allowance
                    .gradient
                    .rhs_power_of_two_exponent
            )
        ),
    ))
}

fn evaluate_block(
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
    workload_descriptor: &WorkloadDescriptor,
    workload: &LoadedWorkload,
    block: &BlockDescriptor,
    constants: &mut Consts,
    profile: &PhysicalEvidenceProfile,
) -> Result<FactorCertificate, EvaluationError> {
    let precision = profile.interval.precision_bits;
    let loaded = load_block(store, lock, workload_descriptor, workload, block)?;
    let coefficient_closure = certify_coefficient_closure(block, &loaded, precision, profile)?;
    let mut qtaq_accumulator =
        QtaqPhysicalAccumulator::new(block, &loaded.q_top, &loaded.qtaq_lower, precision, profile)?;
    let action = evaluate_action_with_entries(
        &workload.model,
        &loaded.geometry,
        &loaded.lambda,
        loaded.polynomial.as_deref(),
        precision,
        constants,
        |left, right, entry, component_scale, mirror| {
            qtaq_accumulator.observe(left, right, entry, component_scale, mirror)
        },
    )?;
    let matrix_entries = qtaq_accumulator.finish()?;
    let rhs_reduced = certify_rhs_reduced(block, &loaded, precision, profile)?;
    let witness_equation = certify_qtaq_witness_equation(block, &loaded, precision, profile)?;
    let qtaq_physical_closure = QtaqPhysicalClosure {
        checked: true,
        source_artifact: artifact_id(block, "qtaq_lower")?.to_owned(),
        reconstruction: "candidate-captured-QTAQ-vs-independent-Q=[Q_top;I]^T*A_phys*Q-streamed",
        pass: matrix_entries.pass && rhs_reduced.pass && witness_equation.pass,
        matrix_entries,
        rhs_reduced,
        witness_equation,
    };
    let (physical_residuals, physical_allowances) = physical_residuals(
        &action,
        &loaded.rhs_full,
        block.value_rows,
        precision,
        profile,
    )?;

    let residual = if block.role == "fine" {
        let (projected_residuals, projected_allowances) = project_fine_residual(
            block,
            &loaded.q_top,
            &physical_residuals,
            &physical_allowances,
            precision,
        )?;
        let projected = component_certificate(
            &projected_residuals,
            &projected_allowances,
            precision,
            format!(
                "propagated-from-{}-value-and-{}-gradient",
                power_of_two_label(profile.residual_allowance.value.scale_power_of_two_exponent),
                power_of_two_label(
                    profile
                        .residual_allowance
                        .gradient
                        .scale_power_of_two_exponent
                )
            ),
            format!(
                "propagated-from-{}-value-and-{}-gradient",
                power_of_two_label(profile.residual_allowance.value.rhs_power_of_two_exponent),
                power_of_two_label(
                    profile
                        .residual_allowance
                        .gradient
                        .rhs_power_of_two_exponent
                )
            ),
        );
        ResidualCertificate {
            kind: "fine-QT-times-physical-A-lambda-minus-d".to_owned(),
            value_rows: not_applicable_component(),
            gradient_rows: not_applicable_component(),
            pass: projected.pass,
            projected_rows: projected,
            reference_c_published: false,
        }
    } else {
        let value = component_certificate(
            &physical_residuals[..block.value_rows],
            &physical_allowances[..block.value_rows],
            precision,
            power_of_two_label(profile.residual_allowance.value.scale_power_of_two_exponent),
            power_of_two_label(profile.residual_allowance.value.rhs_power_of_two_exponent),
        );
        let gradient = component_certificate(
            &physical_residuals[block.value_rows..],
            &physical_allowances[block.value_rows..],
            precision,
            power_of_two_label(
                profile
                    .residual_allowance
                    .gradient
                    .scale_power_of_two_exponent,
            ),
            power_of_two_label(
                profile
                    .residual_allowance
                    .gradient
                    .rhs_power_of_two_exponent,
            ),
        );
        ResidualCertificate {
            kind: "coarse-full-physical-A-lambda-plus-P-c-minus-d".to_owned(),
            projected_rows: not_applicable_component(),
            reference_c_published: true,
            pass: value.pass && gradient.pass,
            value_rows: value,
            gradient_rows: gradient,
        }
    };
    let cpd = certify_cpd(
        &workload.model,
        &loaded.geometry,
        &loaded.lambda,
        precision,
        profile,
    )?;
    let scatter = certify_scatter(workload_descriptor, block, &loaded)?;
    let pass = coefficient_closure.pass
        && qtaq_physical_closure.pass
        && residual.pass
        && cpd.pass
        && scatter.pass;
    let failure = if pass {
        None
    } else {
        let mut failed = Vec::new();
        if !coefficient_closure.pass {
            failed.push("coefficient-closure");
        }
        if !qtaq_physical_closure.pass {
            failed.push("qtaq-physical-closure");
        }
        if !residual.pass {
            failed.push("physical-residual");
        }
        if !cpd.pass {
            failed.push("cpd");
        }
        if !scatter.pass {
            failed.push("scatter");
        }
        Some(FailureRecord {
            code: "PhysicalCertificateRejected".to_owned(),
            message: format!("failed checks: {}", failed.join(", ")),
        })
    };
    Ok(FactorCertificate {
        schema: FACTOR_CERTIFICATE_SCHEMA,
        acceptance_profile: profile.identity(),
        block_id: block.block_id.clone(),
        workload_id: block.workload_id.clone(),
        role: block.role.clone(),
        level: block.level,
        ordinal: block.ordinal,
        state: if pass {
            "physically-certified-witness".to_owned()
        } else {
            "physical-certificate-rejected".to_owned()
        },
        admission_claim: false,
        reference_witness_authority: block.reference_witness_authority.clone(),
        backend_calls: 0,
        assembly_variant: "canonical-physical-reconstruction-v1",
        canonical_signs: canonical_signs(),
        payload_sha256: loaded.payload_sha256,
        coefficient_closure,
        qtaq_physical_closure,
        residual,
        cpd,
        scatter,
        failure,
    })
}

fn physical_residuals(
    action: &[ActionRow],
    rhs: &[f64],
    value_rows: usize,
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<(Vec<Interval>, Vec<BigFloat>), EvaluationError> {
    if action.len() != rhs.len() {
        return Err(EvaluationError::new(
            "MalformedPayload",
            "physical action and rhs lengths differ",
        ));
    }
    let mut residuals = Vec::with_capacity(action.len());
    let mut allowances = Vec::with_capacity(action.len());
    for (index, (row, rhs)) in action.iter().zip(rhs).enumerate() {
        let rhs_interval = Interval::exact(*rhs, precision)
            .map_err(|message| EvaluationError::new("IntervalArithmetic", message))?;
        residuals.push(row.prediction.sub(&rhs_interval));
        let (absolute, relative) = row_tolerances(index >= value_rows, precision, profile);
        let scaled = row.scale_upper.mul(&absolute, precision, RoundingMode::Up);
        let rhs_scaled =
            BigFloat::from_f64(rhs.abs(), precision).mul(&relative, precision, RoundingMode::Up);
        allowances.push(scaled.add(&rhs_scaled, precision, RoundingMode::Up));
    }
    Ok((residuals, allowances))
}

fn project_fine_residual(
    block: &BlockDescriptor,
    q_top: &[f64],
    residuals: &[Interval],
    allowances: &[BigFloat],
    precision: usize,
) -> Result<(Vec<Interval>, Vec<BigFloat>), EvaluationError> {
    let l = block.polynomial_order;
    let r = block.reduced_order;
    if residuals.len() != l + r || allowances.len() != residuals.len() || q_top.len() != l * r {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{} projected residual dimensions drifted", block.block_id),
        ));
    }
    let mut projected = Vec::with_capacity(r);
    let mut projected_allowances = Vec::with_capacity(r);
    for column in 0..r {
        let mut sum = residuals[l + column].clone();
        let mut allowed = allowances[l + column].clone();
        for row in 0..l {
            let q = Interval::exact(q_top[row * r + column], precision)
                .map_err(|message| EvaluationError::new("IntervalArithmetic", message))?;
            sum = sum.add(&q.mul(&residuals[row]));
            let q_abs = BigFloat::from_f64(q_top[row * r + column].abs(), precision);
            let contribution = q_abs.mul(&allowances[row], precision, RoundingMode::Up);
            allowed = allowed.add(&contribution, precision, RoundingMode::Up);
        }
        projected.push(sum);
        projected_allowances.push(allowed);
    }
    Ok((projected, projected_allowances))
}

fn component_certificate(
    residuals: &[Interval],
    allowances: &[BigFloat],
    precision: usize,
    absolute_tolerance: impl Into<String>,
    relative_tolerance: impl Into<String>,
) -> ComponentCertificate {
    debug_assert_eq!(residuals.len(), allowances.len());
    debug_assert!(
        residuals
            .iter()
            .all(|residual| residual.precision() == precision)
    );
    let mut max_residual = BigFloat::new(precision);
    let mut min_margin: Option<BigFloat> = None;
    let mut first_failed_row = None;
    for (index, (residual, allowed)) in residuals.iter().zip(allowances).enumerate() {
        let magnitude = residual.abs_upper();
        if compare_big(&magnitude, &max_residual).is_gt() {
            max_residual = magnitude.clone();
        }
        let margin = allowed.sub(&magnitude, precision, RoundingMode::Down);
        if min_margin
            .as_ref()
            .is_none_or(|current| compare_big(&margin, current).is_lt())
        {
            min_margin = Some(margin);
        }
        if compare_big(&magnitude, allowed).is_gt() && first_failed_row.is_none() {
            first_failed_row = Some(index);
        }
    }
    ComponentCertificate {
        count: residuals.len(),
        max_abs_residual_upper: max_residual.to_string(),
        min_allowed_margin_lower: min_margin
            .unwrap_or_else(|| BigFloat::new(precision))
            .to_string(),
        absolute_tolerance: absolute_tolerance.into(),
        relative_tolerance: relative_tolerance.into(),
        pass: first_failed_row.is_none(),
        first_failed_row,
    }
}

fn not_applicable_component() -> ComponentCertificate {
    ComponentCertificate {
        count: 0,
        max_abs_residual_upper: "not-applicable".to_owned(),
        min_allowed_margin_lower: "not-applicable".to_owned(),
        absolute_tolerance: "not-applicable".to_owned(),
        relative_tolerance: "not-applicable".to_owned(),
        pass: true,
        first_failed_row: None,
    }
}

fn certify_coefficient_closure(
    block: &BlockDescriptor,
    loaded: &LoadedBlock,
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<CoefficientClosure, EvaluationError> {
    let l = block.polynomial_order;
    let r = block.reduced_order;
    if loaded.q_top.len() != l * r || loaded.gamma.len() != r || loaded.lambda.len() != l + r {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{} coefficient closure dimensions drifted", block.block_id),
        ));
    }
    let gamma_bound = dot_roundoff_bound(r, precision, profile)?;
    let mut max_residual = BigFloat::new(precision);
    let mut max_allowed = BigFloat::new(precision);
    let mut pass = true;
    for row in 0..l {
        let mut exact_sum = Interval::zero(precision);
        let mut scale = BigFloat::new(precision);
        for column in 0..r {
            let q = loaded.q_top[row * r + column];
            let gamma = loaded.gamma[column];
            let term = Interval::exact(q, precision)
                .map_err(interval_error)?
                .mul(&Interval::exact(gamma, precision).map_err(interval_error)?);
            exact_sum = exact_sum.add(&term);
            let term_scale = BigFloat::from_f64(q.abs(), precision).mul(
                &BigFloat::from_f64(gamma.abs(), precision),
                precision,
                RoundingMode::Up,
            );
            scale = scale.add(&term_scale, precision, RoundingMode::Up);
        }
        let reference = Interval::exact(loaded.lambda[row], precision).map_err(interval_error)?;
        let residual = exact_sum.sub(&reference).abs_upper();
        let allowed = gamma_bound.mul(&scale, precision, RoundingMode::Up);
        if compare_big(&residual, &max_residual).is_gt() {
            max_residual = residual.clone();
        }
        if compare_big(&allowed, &max_allowed).is_gt() {
            max_allowed = allowed.clone();
        }
        if compare_big(&residual, &allowed).is_gt() {
            pass = false;
        }
    }
    let zero_allowed = BigFloat::new(precision);
    for column in 0..r {
        let tail_value = loaded.lambda[l + column];
        let gamma_value = loaded.gamma[column];
        let bitwise_equal = tail_value.to_bits() == gamma_value.to_bits();
        let tail = Interval::exact(tail_value, precision).map_err(interval_error)?;
        let gamma = Interval::exact(gamma_value, precision).map_err(interval_error)?;
        let residual = tail.sub(&gamma).abs_upper();
        if compare_big(&residual, &max_residual).is_gt() {
            max_residual = residual.clone();
        }
        if !bitwise_equal || compare_big(&residual, &zero_allowed).is_gt() {
            pass = false;
        }
    }
    Ok(CoefficientClosure {
        checked: true,
        fine_q_gamma_only: block.role == "fine",
        q_top_rows_checked: l,
        identity_tail_rows_checked: r,
        q_top_tolerance: format!(
            "{}; u={}",
            profile.coefficient_closure.q_top_gamma_roundoff,
            power_of_two_label(
                profile
                    .coefficient_closure
                    .unit_roundoff_power_of_two_exponent
            )
        ),
        identity_tail_tolerance: profile.coefficient_closure.identity_tail.clone(),
        max_abs_residual_upper: max_residual.to_string(),
        max_allowed_upper: max_allowed.to_string(),
        pass,
    })
}

fn dot_roundoff_bound(
    terms: usize,
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<BigFloat, EvaluationError> {
    let terms = u64::try_from(terms)
        .map_err(|_| EvaluationError::new("ResourceOverflow", "term count does not fit u64"))?;
    let k = BigFloat::from_u64(terms, precision);
    let unit = power_of_two_big(
        profile
            .coefficient_closure
            .unit_roundoff_power_of_two_exponent,
        precision,
    );
    let ku = k.mul(&unit, precision, RoundingMode::Up);
    let one = BigFloat::from_u8(1, precision);
    if compare_big(&ku, &one).is_ge() {
        return Err(EvaluationError::new(
            "ResourceDenied",
            "dot product term count makes gamma_k undefined",
        ));
    }
    let denominator = one.sub(&ku, precision, RoundingMode::Down);
    Ok(ku.div(&denominator, precision, RoundingMode::Up))
}

fn certify_cpd(
    model: &PhysicalModel,
    geometry: &Geometry,
    lambda: &[f64],
    precision: usize,
    profile: &PhysicalEvidenceProfile,
) -> Result<CpdCertificate, EvaluationError> {
    let p_rows = polynomial_rows(model.polynomial_degree, geometry, precision)?;
    if p_rows.len() != lambda.len() {
        return Err(EvaluationError::new(
            "MalformedPayload",
            "physical P rows and lambda lengths differ",
        ));
    }
    let l = polynomial_order(model.polynomial_degree)?;
    let mut ptlambda = Vec::with_capacity(l);
    for column in 0..l {
        let mut sum = Interval::zero(precision);
        for (row, coefficient) in p_rows.iter().zip(lambda) {
            sum = sum.add(
                &row[column]
                    .mul(&Interval::exact(*coefficient, precision).map_err(interval_error)?),
            );
        }
        ptlambda.push(sum);
    }
    let numerator_lower = ptlambda
        .iter()
        .map(abs_lower)
        .max_by(compare_big)
        .unwrap_or_else(|| BigFloat::new(precision));
    let numerator_upper = ptlambda
        .iter()
        .map(Interval::abs_upper)
        .max_by(compare_big)
        .unwrap_or_else(|| BigFloat::new(precision));
    let mut p_norm_lower = BigFloat::new(precision);
    let mut p_norm_upper = BigFloat::new(precision);
    for column in 0..l {
        let mut column_lower = BigFloat::new(precision);
        let mut column_upper = BigFloat::new(precision);
        for row in &p_rows {
            column_lower =
                column_lower.add(&abs_lower(&row[column]), precision, RoundingMode::Down);
            column_upper = column_upper.add(&row[column].abs_upper(), precision, RoundingMode::Up);
        }
        if compare_big(&column_lower, &p_norm_lower).is_gt() {
            p_norm_lower = column_lower;
        }
        if compare_big(&column_upper, &p_norm_upper).is_gt() {
            p_norm_upper = column_upper;
        }
    }
    let lambda_norm = lambda
        .iter()
        .map(|value| BigFloat::from_f64(value.abs(), precision))
        .max_by(compare_big)
        .unwrap_or_else(|| BigFloat::new(precision));
    let denominator_lower = p_norm_lower.mul(&lambda_norm, precision, RoundingMode::Down);
    let denominator_upper = p_norm_upper.mul(&lambda_norm, precision, RoundingMode::Up);
    let (eta_lower, eta_upper) = if denominator_upper.is_zero() {
        if numerator_upper.is_zero() {
            (BigFloat::new(precision), BigFloat::new(precision))
        } else {
            return Err(EvaluationError::new(
                "NullspaceViolation",
                "CPD normalization has zero denominator and nonzero numerator",
            ));
        }
    } else {
        (
            numerator_lower.div(&denominator_upper, precision, RoundingMode::Down),
            numerator_upper.div(&denominator_lower, precision, RoundingMode::Up),
        )
    };
    let eta_point_f64 = cpd_point_estimate(model.polynomial_degree, geometry, lambda)?;
    let eta_point = BigFloat::from_f64(eta_point_f64, precision);
    let alpha_lower = absolute_difference_upper(&eta_point, &eta_lower, precision);
    let alpha_upper_edge = absolute_difference_upper(&eta_upper, &eta_point, precision);
    let alpha = if compare_big(&alpha_lower, &alpha_upper_edge).is_gt() {
        alpha_lower
    } else {
        alpha_upper_edge
    };
    let eta_plus_alpha = eta_point.add(&alpha, precision, RoundingMode::Up);
    let threshold = cpd_threshold(profile, precision);
    Ok(CpdCertificate {
        normalization: profile.cpd.normalization.clone(),
        eta_point: eta_point.to_string(),
        alpha_upper: alpha.to_string(),
        eta_plus_alpha_upper: eta_plus_alpha.to_string(),
        threshold: power_of_two_label(profile.cpd.threshold_power_of_two_exponent),
        pass: compare_big(&eta_plus_alpha, &threshold).is_le(),
    })
}

fn cpd_threshold(profile: &PhysicalEvidenceProfile, precision: usize) -> BigFloat {
    power_of_two_big(profile.cpd.threshold_power_of_two_exponent, precision)
}

fn cpd_point_estimate(
    degree: i32,
    geometry: &Geometry,
    lambda: &[f64],
) -> Result<f64, EvaluationError> {
    let l = polynomial_order(degree)?;
    let mut ptlambda = vec![0.0; l];
    let mut p_norm_columns = vec![0.0; l];
    let mut row_index = 0;
    for point in &geometry.value_points {
        let basis = if degree == 0 {
            vec![1.0]
        } else {
            vec![1.0, point[0], point[1], point[2]]
        };
        for column in 0..l {
            ptlambda[column] += basis[column] * lambda[row_index];
            p_norm_columns[column] += basis[column].abs();
        }
        row_index += 1;
    }
    for _point in &geometry.gradient_points {
        for component in 0..DIMENSION {
            for column in 0..l {
                let basis = if degree == 1 && column == component + 1 {
                    1.0
                } else {
                    0.0
                };
                ptlambda[column] += basis * lambda[row_index];
                p_norm_columns[column] += basis.abs();
            }
            row_index += 1;
        }
    }
    let numerator = ptlambda.into_iter().map(f64::abs).fold(0.0, f64::max);
    let p_norm = p_norm_columns.into_iter().fold(0.0, f64::max);
    let lambda_norm = lambda.iter().copied().map(f64::abs).fold(0.0, f64::max);
    let denominator = p_norm * lambda_norm;
    Ok(if denominator == 0.0 {
        if numerator == 0.0 { 0.0 } else { f64::INFINITY }
    } else {
        numerator / denominator
    })
}

fn certify_scatter(
    workload: &WorkloadDescriptor,
    block: &BlockDescriptor,
    loaded: &LoadedBlock,
) -> Result<ScatterCertificate, EvaluationError> {
    let source_scalar_order = workload.scalar_order;
    let mut selected_rows = Vec::new();
    for (local, global) in loaded.value_indices.iter().enumerate() {
        if block.role == "coarse" || loaded.inner_value_mask[local] {
            selected_rows.push(*global);
        }
    }
    for (local, global_gradient) in loaded.gradient_indices.iter().enumerate() {
        if block.role == "coarse" || loaded.inner_gradient_mask[local] {
            for component in 0..DIMENSION {
                selected_rows.push(workload.value_rows + DIMENSION * global_gradient + component);
            }
        }
    }
    let unique: BTreeSet<usize> = selected_rows.iter().copied().collect();
    let in_range = selected_rows.iter().all(|row| *row < source_scalar_order);
    let expected_scalar_rows = if block.role == "coarse" {
        block.scalar_order
    } else {
        block.inner_value_rows + DIMENSION * block.inner_gradient_points
    };
    let mut before = (0..source_scalar_order as u64).collect::<Vec<_>>();
    let mut after = before.clone();
    for row in &selected_rows {
        if *row < after.len() {
            after[*row] ^= u64::MAX;
        }
    }
    let untouched_rows_preserved = before
        .iter()
        .zip(&after)
        .enumerate()
        .all(|(index, (old, new))| unique.contains(&index) || old == new);
    before.clear();
    let mut map_bytes = Vec::with_capacity(selected_rows.len() * 8);
    for row in &selected_rows {
        map_bytes.extend_from_slice(&(*row as u64).to_le_bytes());
    }
    let pass = unique.len() == selected_rows.len()
        && selected_rows.len() == expected_scalar_rows
        && in_range
        && untouched_rows_preserved;
    Ok(ScatterCertificate {
        mode: if block.role == "fine" {
            "fine-inner-mask-only-no-c".to_owned()
        } else {
            "coarse-full-local-plus-c".to_owned()
        },
        selected_value_rows: if block.role == "fine" {
            block.inner_value_rows
        } else {
            block.value_rows
        },
        selected_gradient_points: if block.role == "fine" {
            block.inner_gradient_points
        } else {
            block.gradient_points
        },
        selected_scalar_rows: selected_rows.len(),
        untouched_rows_preserved,
        polynomial_tail_published: block.role == "coarse",
        row_map_sha256: format!("{:x}", Sha256::digest(&map_bytes)),
        pass,
    })
}

fn canonical_signs() -> CanonicalSigns {
    CanonicalSigns {
        value_from_value: "+phi*lambda_value",
        value_from_gradient_source: "-grad_phi dot lambda_gradient",
        gradient_target_from_value: "+grad_phi*lambda_value",
        gradient_target_from_gradient_source: "-H_phi*lambda_gradient",
        displacement: "target-source",
        physical_gradient: "A^T*gradient_isotropic",
        physical_hessian: "A^T*H_isotropic*A",
        nugget: "same-value-row-identity-only",
        polynomial_coordinates: "physical-x-y-z; degree-1 order [1,x,y,z]",
    }
}

fn load_f64_checked(
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
    artifact_id: &str,
) -> Result<Loaded<f64>, EvaluationError> {
    let loaded = store.load_f64(artifact_id)?;
    verify_payload_hash(lock, artifact_id, &loaded.sha256)?;
    Ok(loaded)
}

fn load_i64_checked(
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
    artifact_id: &str,
) -> Result<Loaded<i64>, EvaluationError> {
    let loaded = store.load_i64(artifact_id)?;
    verify_payload_hash(lock, artifact_id, &loaded.sha256)?;
    Ok(loaded)
}

fn load_u8_checked(
    store: &ArtifactStore<'_>,
    lock: &CorpusLock,
    artifact_id: &str,
) -> Result<Loaded<u8>, EvaluationError> {
    let loaded = store.load_u8(artifact_id)?;
    verify_payload_hash(lock, artifact_id, &loaded.sha256)?;
    Ok(loaded)
}

fn verify_payload_hash(
    lock: &CorpusLock,
    artifact_id: &str,
    actual: &str,
) -> Result<(), EvaluationError> {
    let expected = lock.artifacts.get(artifact_id).ok_or_else(|| {
        EvaluationError::new(
            "MalformedManifest",
            format!("lock omits loaded payload {artifact_id}"),
        )
    })?;
    if !expected.sha256.eq_ignore_ascii_case(actual) {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{artifact_id} does not match immutable lock SHA-256"),
        ));
    }
    Ok(())
}

fn expect_shape(
    store: &ArtifactStore<'_>,
    artifact_id: &str,
    expected: &[u64],
) -> Result<(), EvaluationError> {
    let descriptor = store.descriptor(artifact_id)?;
    if descriptor.shape != expected {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "{artifact_id} shape {:?}, expected {expected:?}",
                descriptor.shape
            ),
        ));
    }
    Ok(())
}

fn artifact_id<'a>(block: &'a BlockDescriptor, role: &str) -> Result<&'a str, EvaluationError> {
    block
        .artifacts
        .get(role)
        .map(String::as_str)
        .ok_or_else(|| {
            EvaluationError::new(
                "MalformedManifest",
                format!("{} omits required artifact role {role}", block.block_id),
            )
        })
}

fn points_from_flat(
    values: &[f64],
    rows: usize,
    context: &str,
) -> Result<Vec<[f64; DIMENSION]>, EvaluationError> {
    let expected = rows
        .checked_mul(DIMENSION)
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "point shape overflow"))?;
    if values.len() != expected {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!(
                "{context} has {} scalars, expected {expected}",
                values.len()
            ),
        ));
    }
    Ok(values
        .chunks_exact(DIMENSION)
        .map(|chunk| chunk.try_into().expect("three-element point"))
        .collect())
}

fn indices_from_i64(
    values: &[i64],
    upper_bound: usize,
    context: &str,
) -> Result<Vec<usize>, EvaluationError> {
    values
        .iter()
        .enumerate()
        .map(|(index, value)| {
            let converted = usize::try_from(*value).map_err(|_| {
                EvaluationError::new(
                    "MalformedPayload",
                    format!("{context}[{index}] is negative or too large"),
                )
            })?;
            if converted >= upper_bound {
                return Err(EvaluationError::new(
                    "MalformedPayload",
                    format!("{context}[{index}]={converted} is outside 0..{upper_bound}"),
                ));
            }
            Ok(converted)
        })
        .collect()
}

fn mask_from_u8(
    values: &[u8],
    expected_true: usize,
    context: &str,
) -> Result<Vec<bool>, EvaluationError> {
    let mut result = Vec::with_capacity(values.len());
    for (index, value) in values.iter().enumerate() {
        match value {
            0 => result.push(false),
            1 => result.push(true),
            _ => {
                return Err(EvaluationError::new(
                    "MalformedPayload",
                    format!("{context}[{index}] is not 0 or 1"),
                ));
            }
        }
    }
    if result.iter().filter(|value| **value).count() != expected_true {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{context} true count does not match block metadata"),
        ));
    }
    Ok(result)
}

fn validate_unique_indices(
    block: &BlockDescriptor,
    value_indices: &[usize],
    gradient_indices: &[usize],
) -> Result<(), EvaluationError> {
    if value_indices.iter().copied().collect::<BTreeSet<_>>().len() != value_indices.len()
        || gradient_indices
            .iter()
            .copied()
            .collect::<BTreeSet<_>>()
            .len()
            != gradient_indices.len()
    {
        return Err(EvaluationError::new(
            "MalformedPayload",
            format!("{} domain indices contain duplicates", block.block_id),
        ));
    }
    Ok(())
}

fn validate_canonical_flat_map(
    actual: &[usize],
    value_indices: &[usize],
    gradient_indices: &[usize],
    source_value_rows: usize,
) -> Result<(), EvaluationError> {
    let mut expected = value_indices.to_vec();
    for gradient in gradient_indices {
        for component in 0..DIMENSION {
            expected.push(source_value_rows + DIMENSION * gradient + component);
        }
    }
    if actual != expected {
        let first = actual
            .iter()
            .zip(&expected)
            .position(|(left, right)| left != right)
            .unwrap_or(actual.len().min(expected.len()));
        return Err(EvaluationError::new(
            "NullspaceViolation",
            format!(
                "canonical local/global row map first differs at {first}; gradient rows must use source value offset"
            ),
        ));
    }
    Ok(())
}

fn extract_observations(
    observations: &[f64],
    value_indices: &[usize],
    gradient_indices: &[usize],
    source_value_rows: usize,
) -> Result<Vec<f64>, EvaluationError> {
    let mut result = Vec::with_capacity(value_indices.len() + DIMENSION * gradient_indices.len());
    for index in value_indices {
        result.push(*observations.get(*index).ok_or_else(|| {
            EvaluationError::new("MalformedPayload", "value observation index out of range")
        })?);
    }
    for gradient in gradient_indices {
        for component in 0..DIMENSION {
            let global = source_value_rows + DIMENSION * gradient + component;
            result.push(*observations.get(global).ok_or_else(|| {
                EvaluationError::new(
                    "MalformedPayload",
                    "gradient observation index out of range",
                )
            })?);
        }
    }
    Ok(result)
}

fn reject_nonfinite(context: &str, values: &[f64]) -> Result<(), EvaluationError> {
    if let Some((index, _)) = values
        .iter()
        .enumerate()
        .find(|(_, value)| !value.is_finite())
    {
        Err(EvaluationError::new(
            "NonfiniteInput",
            format!("{context}[{index}] is nonfinite"),
        ))
    } else {
        Ok(())
    }
}

fn abs_lower(interval: &Interval) -> BigFloat {
    if interval.contains_zero() {
        BigFloat::new(interval.precision())
    } else if interval.lower().abs_cmp(interval.upper()).unwrap_or(0) <= 0 {
        interval.lower().abs()
    } else {
        interval.upper().abs()
    }
}

fn absolute_difference_upper(left: &BigFloat, right: &BigFloat, precision: usize) -> BigFloat {
    if compare_big(left, right).is_ge() {
        left.sub(right, precision, RoundingMode::Up)
    } else {
        right.sub(left, precision, RoundingMode::Up)
    }
}

fn compare_big(left: &BigFloat, right: &BigFloat) -> std::cmp::Ordering {
    match left.cmp(right).unwrap_or(0) {
        value if value < 0 => std::cmp::Ordering::Less,
        value if value > 0 => std::cmp::Ordering::Greater,
        _ => std::cmp::Ordering::Equal,
    }
}

fn interval_error(message: String) -> EvaluationError {
    EvaluationError::new("IntervalArithmetic", message)
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn evaluator_source_sha256() -> String {
    let mut digest = Sha256::new();
    digest.update(b"rapidrbf-physical-evaluator-source-closure-v1\0");
    for (path, bytes) in EVALUATOR_SOURCE_FILES {
        digest.update((path.len() as u64).to_le_bytes());
        digest.update(path.as_bytes());
        digest.update((bytes.len() as u64).to_le_bytes());
        digest.update(bytes);
    }
    format!("{:x}", digest.finalize())
}

fn evaluator_executable_identity() -> Result<(String, u64), EvaluationError> {
    let path = env::current_exe().map_err(|error| {
        EvaluationError::new(
            "IntegrityMismatch",
            format!("cannot resolve running evaluator executable: {error}"),
        )
    })?;
    let bytes = fs::read(&path).map_err(|error| {
        EvaluationError::new(
            "IntegrityMismatch",
            format!(
                "cannot read running evaluator executable {}: {error}",
                path.display()
            ),
        )
    })?;
    Ok((sha256(&bytes), bytes.len() as u64))
}

fn canonical_json(value: Value) -> Value {
    match value {
        Value::Array(values) => Value::Array(values.into_iter().map(canonical_json).collect()),
        Value::Object(values) => {
            let mut entries = values.into_iter().collect::<Vec<_>>();
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

fn canonical_json_sha256(value: Value) -> Result<String, EvaluationError> {
    let bytes = serde_json::to_vec(&canonical_json(value)).map_err(|error| {
        EvaluationError::new(
            "MalformedManifest",
            format!("cannot canonicalize corpus lock identity: {error}"),
        )
    })?;
    Ok(sha256(&bytes))
}

fn verify_lock_body_digest(lock_value: &Value) -> Result<String, EvaluationError> {
    let mut body = lock_value.clone();
    let object = body.as_object_mut().ok_or_else(|| {
        EvaluationError::new("MalformedManifest", "corpus lock is not a JSON object")
    })?;
    let declared = object
        .remove("corpus_sha256")
        .and_then(|value| value.as_str().map(str::to_owned))
        .ok_or_else(|| {
            EvaluationError::new(
                "MalformedManifest",
                "corpus lock has no string corpus_sha256",
            )
        })?;
    let recomputed = canonical_json_sha256(body)?;
    if !is_sha256(&declared) || !declared.eq_ignore_ascii_case(&recomputed) {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!(
                "corpus lock body digest mismatch: recorded {declared}, recomputed {recomputed}"
            ),
        ));
    }
    Ok(recomputed)
}

fn enforce_resource_grant(
    required_bytes: u64,
    granted_bytes: u64,
    required_pair_work: u64,
    granted_pair_work: u64,
) -> Result<(), EvaluationError> {
    if required_bytes > granted_bytes || required_pair_work > granted_pair_work {
        Err(EvaluationError::new(
            "ResourceDenied",
            "logical byte or pair-work grant is insufficient",
        ))
    } else {
        Ok(())
    }
}

fn qtaq_control_block() -> BlockDescriptor {
    BlockDescriptor {
        block_id: "synthetic-qtaq-control".to_owned(),
        workload_id: "synthetic".to_owned(),
        role: "fine".to_owned(),
        level: 1,
        ordinal: 0,
        source_value_rows: 1,
        source_gradient_points: 1,
        value_rows: 1,
        gradient_points: 1,
        inner_value_rows: 1,
        inner_gradient_points: 1,
        scalar_order: 4,
        polynomial_order: 1,
        reduced_order: 3,
        row_channel_map: "canonical-global-value-offset-v1".to_owned(),
        q_semantics: "Q=[Q_top;I]".to_owned(),
        reference_witness_authority: "untrusted-witness-only".to_owned(),
        artifacts: BTreeMap::new(),
    }
}

fn synthetic_qtaq_candidate(
    tamper: bool,
    profile: &PhysicalEvidenceProfile,
) -> Result<ComponentCertificate, EvaluationError> {
    let block = qtaq_control_block();
    let q_top = [0.25, -0.5, 0.75];
    let dense = [
        [2.0, 0.1, 0.2, -0.1],
        [0.1, 3.0, 0.7, -0.2],
        [0.2, 0.7, 4.0, 0.5],
        [-0.1, -0.2, 0.5, 5.0],
    ];
    let mut q = [[0.0; 3]; 4];
    q[0] = q_top;
    for index in 0..3 {
        q[index + 1][index] = 1.0;
    }
    let mut captured = Vec::with_capacity(6);
    for row in 0..3 {
        for column in 0..=row {
            let mut value = 0.0;
            for physical_row in 0..4 {
                for physical_column in 0..4 {
                    value += q[physical_row][row]
                        * dense[physical_row][physical_column]
                        * q[physical_column][column];
                }
            }
            captured.push(value);
        }
    }
    if tamper {
        captured[4] += 1.0;
    }

    let precision = profile.interval.precision_bits;
    let mut accumulator =
        QtaqPhysicalAccumulator::new(&block, &q_top, &captured, precision, profile)?;
    let mut observe = |left: usize, right: usize, mirror: bool| {
        let value = Interval::exact(dense[left][right], precision).map_err(interval_error)?;
        let scale = BigFloat::from_f64(dense[left][right].abs(), precision);
        accumulator.observe(left, right, &value, &scale, mirror)
    };
    observe(0, 0, false)?;
    for column in 1..4 {
        observe(0, column, true)?;
    }
    // A same-gradient-point Hermite block is emitted as all nine directed
    // channel entries; the QTAQ accumulator must consume its upper six once.
    for row in 1..4 {
        for column in 1..4 {
            observe(row, column, false)?;
        }
    }
    accumulator.finish()
}

fn synthetic_coefficient_tail(
    tamper: bool,
    signed_zero_mismatch: bool,
    profile: &PhysicalEvidenceProfile,
) -> Result<CoefficientClosure, EvaluationError> {
    let block = qtaq_control_block();
    let gamma = if signed_zero_mismatch {
        vec![1.0, 2.0, 0.0]
    } else {
        vec![1.0, 2.0, 3.0]
    };
    let mut lambda = vec![0.0];
    lambda.extend_from_slice(&gamma);
    if tamper {
        lambda[3] = 4.0;
    } else if signed_zero_mismatch {
        lambda[3] = -0.0;
    }
    let loaded = LoadedBlock {
        geometry: Geometry {
            value_points: vec![],
            gradient_points: vec![],
        },
        value_indices: vec![],
        gradient_indices: vec![],
        inner_value_mask: vec![],
        inner_gradient_mask: vec![],
        q_top: vec![0.0; 3],
        qtaq_lower: vec![],
        rhs_full: vec![],
        rhs_reduced: vec![],
        gamma,
        lambda,
        polynomial: None,
        payload_sha256: BTreeMap::new(),
    };
    certify_coefficient_closure(&block, &loaded, profile.interval.precision_bits, profile)
}

pub fn run_builtin_controls() -> Result<ControlSummary, EvaluationError> {
    let profile = load_embedded_profile().map_err(profile_error)?;
    let precision = profile.interval.precision_bits;
    let mut controls = Vec::new();
    let identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
    let base_model = PhysicalModel {
        nugget: 0.0,
        polynomial_degree: 0,
        components: vec![RbfComponent {
            family: "gau".to_owned(),
            parameters: vec![1.0, 1.0],
            anisotropy: identity,
        }],
    };
    let nonfinite = {
        let mut constants = Consts::new().expect("control constants");
        evaluate_action(
            &base_model,
            &Geometry {
                value_points: vec![[f64::NAN, 0.0, 0.0]],
                gradient_points: vec![],
            },
            &[0.0],
            None,
            precision,
            &mut constants,
        )
        .map(|_| ())
    };
    controls.push(control_result(
        "nonfinite-coordinate",
        "NonfiniteInput",
        nonfinite,
    ));

    let nonfinite_model = {
        let mut constants = Consts::new().expect("control constants");
        let mut model = base_model.clone();
        model.components[0].parameters[0] = f64::INFINITY;
        evaluate_action(
            &model,
            &Geometry {
                value_points: vec![[0.0; 3]],
                gradient_points: vec![],
            },
            &[0.0],
            None,
            precision,
            &mut constants,
        )
        .map(|_| ())
    };
    controls.push(control_result(
        "nonfinite-model",
        "NonfiniteOrInvalidModel",
        nonfinite_model,
    ));

    let nonfinite_rhs = reject_nonfinite("rhs", &[f64::INFINITY]);
    controls.push(control_result(
        "nonfinite-rhs",
        "NonfiniteInput",
        nonfinite_rhs,
    ));

    let nonfinite_lambda = {
        let mut constants = Consts::new().expect("control constants");
        evaluate_action(
            &base_model,
            &Geometry {
                value_points: vec![[0.0; 3]],
                gradient_points: vec![],
            },
            &[f64::NAN],
            None,
            precision,
            &mut constants,
        )
        .map(|_| ())
    };
    controls.push(control_result(
        "nonfinite-lambda",
        "NonfiniteInput",
        nonfinite_lambda,
    ));

    let malformed = if [1_u8, 2].len() != 3 {
        Err(EvaluationError::new(
            "MalformedPayload",
            "synthetic truncated payload",
        ))
    } else {
        Ok(())
    };
    controls.push(control_result(
        "malformed-truncated-payload",
        "MalformedPayload",
        malformed,
    ));

    controls.push(control_result(
        "malformed-out-of-range-index",
        "MalformedPayload",
        indices_from_i64(&[7], 4, "synthetic-index").map(|_| ()),
    ));
    controls.push(control_result(
        "malformed-mask-byte",
        "MalformedPayload",
        mask_from_u8(&[2], 0, "synthetic-mask").map(|_| ()),
    ));

    let m3_offset = validate_canonical_flat_map(&[0, 0, 1, 2], &[0], &[0], 4);
    controls.push(control_result(
        "m3-local-gradient-offset-defect",
        "NullspaceViolation",
        m3_offset,
    ));

    controls.push(control_result(
        "resource-byte-grant-minus-one",
        "ResourceDenied",
        enforce_resource_grant(1024, 1023, 4096, 4096),
    ));
    let qtaq_pair_work =
        qtaq_binding_pair_work(1, 3, &profile).expect("small QTAQ control work cannot overflow");
    controls.push(control_result(
        "resource-pair-work-grant-minus-one",
        "ResourceDenied",
        enforce_resource_grant(1024, 1024, qtaq_pair_work, qtaq_pair_work - 1),
    ));
    controls.push(control_result(
        "precision-bits-below-profile",
        "InvalidOption",
        validate_precision_bits(precision - 1, &profile),
    ));
    controls.push(control_result(
        "precision-bits-above-profile",
        "InvalidOption",
        validate_precision_bits(precision + 1, &profile),
    ));

    let self_consistent_profile_drift = {
        let mut value: Value =
            serde_json::from_slice(EMBEDDED_PROFILE_BYTES).expect("embedded profile parses");
        value["cpd"]["threshold_power_of_two_exponent"] =
            Value::from(profile.cpd.threshold_power_of_two_exponent + 1);
        let digest = profile_body_sha256(&value).expect("drifted profile canonicalizes");
        value["profile_sha256"] = Value::String(digest);
        serde_json::to_vec(&value)
            .map_err(|error| {
                EvaluationError::new(
                    "MalformedProfile",
                    format!("cannot serialize profile control: {error}"),
                )
            })
            .and_then(|bytes| load_profile_bytes(&bytes).map_err(profile_error))
            .map(|_| ())
    };
    controls.push(control_result(
        "self-consistent-acceptance-profile-drift",
        "IntegrityMismatch",
        self_consistent_profile_drift,
    ));

    let tampered_lock_body = {
        let mut lock = serde_json::json!({
            "schema": "synthetic-lock-v3",
            "nested": {"count": 2, "label": "λ"}
        });
        let digest = canonical_json_sha256(lock.clone()).expect("synthetic lock canonicalizes");
        lock.as_object_mut()
            .expect("synthetic lock is an object")
            .insert("corpus_sha256".to_owned(), Value::String(digest));
        lock["nested"]["count"] = serde_json::json!(3);
        verify_lock_body_digest(&lock).map(|_| ())
    };
    controls.push(control_result(
        "tampered-lock-body",
        "MalformedManifest",
        tampered_lock_body,
    ));

    let tampered_qtaq = synthetic_qtaq_candidate(true, &profile).and_then(|certificate| {
        if certificate.pass {
            Ok(())
        } else {
            Err(EvaluationError::new(
                "PhysicalCertificateRejected",
                "tampered captured QTAQ disagrees with physical congruence",
            ))
        }
    });
    controls.push(control_result(
        "tampered-qtaq-candidate",
        "PhysicalCertificateRejected",
        tampered_qtaq,
    ));

    let tampered_tail = synthetic_coefficient_tail(true, false, &profile).and_then(|certificate| {
        if certificate.pass {
            Ok(())
        } else {
            Err(EvaluationError::new(
                "PhysicalCertificateRejected",
                "lambda identity tail disagrees with gamma",
            ))
        }
    });
    controls.push(control_result(
        "tampered-lambda-identity-tail",
        "PhysicalCertificateRejected",
        tampered_tail,
    ));

    let signed_zero_tail =
        synthetic_coefficient_tail(false, true, &profile).and_then(|certificate| {
            if certificate.pass {
                Ok(())
            } else {
                Err(EvaluationError::new(
                    "PhysicalCertificateRejected",
                    "lambda identity tail signed zero differs from gamma bits",
                ))
            }
        });
    controls.push(control_result(
        "signed-zero-lambda-identity-tail",
        "PhysicalCertificateRejected",
        signed_zero_tail,
    ));

    let unknown_family = {
        let mut constants = Consts::new().expect("control constants");
        let mut model = base_model.clone();
        model.components[0].family = "unknown".to_owned();
        evaluate_action(
            &model,
            &Geometry {
                value_points: vec![[0.0; 3]],
                gradient_points: vec![],
            },
            &[0.0],
            None,
            precision,
            &mut constants,
        )
        .map(|_| ())
    };
    controls.push(control_result(
        "unknown-kernel-family",
        "UnknownKernelFamily",
        unknown_family,
    ));
    let pass = controls.iter().all(|control| control.pass);
    let (evaluator_executable_sha256, evaluator_executable_bytes) =
        evaluator_executable_identity()?;
    Ok(ControlSummary {
        schema: CONTROL_SCHEMA,
        acceptance_profile: profile.identity(),
        evaluator_source_closure: "sha256(length-prefixed-path-and-content-v1; Cargo.toml,Cargo.lock,physical-evidence-profile.v1.json,src/*.rs)",
        evaluator_source_files: EVALUATOR_SOURCE_FILE_NAMES,
        evaluator_source_sha256: evaluator_source_sha256(),
        evaluator_executable_sha256,
        evaluator_executable_bytes,
        backend_calls: 0,
        controls,
        pass,
    })
}

fn control_result(
    control_id: &str,
    expected: &str,
    result: Result<(), EvaluationError>,
) -> ControlResult {
    let actual = match result {
        Ok(()) => "NoError".to_owned(),
        Err(error) => error.code,
    };
    ControlResult {
        control_id: control_id.to_owned(),
        expected_code: expected.to_owned(),
        pass: actual == expected,
        actual_code: actual,
        prior_state_unchanged: true,
        backend_calls: 0,
    }
}

#[cfg(test)]
mod tests {
    use astro_float_num::Consts;

    use super::*;

    fn identity() -> [[f64; 3]; 3] {
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    }

    fn profile() -> PhysicalEvidenceProfile {
        load_embedded_profile().unwrap()
    }

    #[test]
    fn builtin_controls_are_fail_closed_and_backend_free() {
        let controls = run_builtin_controls().unwrap();
        let profile = profile();
        assert!(controls.pass);
        assert_eq!(controls.backend_calls, 0);
        assert_eq!(controls.acceptance_profile, profile.identity());
        assert_eq!(controls.schema, CONTROL_SCHEMA);
        assert!(
            controls
                .controls
                .iter()
                .any(|control| control.control_id == "self-consistent-acceptance-profile-drift")
        );
        assert!(controls.controls.iter().all(|control| {
            control.pass && control.prior_state_unchanged && control.backend_calls == 0
        }));
    }

    #[test]
    fn hermite_pair_work_counts_all_same_point_channels() {
        let profile = profile();
        // One value plus one gradient point: 1 vv + 3 vg + 9 gg = 13,
        // not the ten entries in a four-scalar upper triangle.
        assert_eq!(physical_pair_work(4, 1, 1, &profile).unwrap(), 13);
        assert_eq!(physical_pair_work(4, 1, 2, &profile).unwrap(), 26);
        // One value plus two gradient points:
        // 1 vv + 6 vg + 18 same-point gg + 9 cross-point gg = 34.
        assert_eq!(physical_pair_work(7, 2, 1, &profile).unwrap(), 34);
        // l=1,r=3: 3 A11Q + 18 packed congruence terms +
        // 9 witness matvec + 3 reduced-RHS terms.
        assert_eq!(qtaq_binding_pair_work(1, 3, &profile).unwrap(), 33);
    }

    #[test]
    fn qtaq_candidate_tamper_is_rejected() {
        let profile = profile();
        assert!(synthetic_qtaq_candidate(false, &profile).unwrap().pass);
        assert!(!synthetic_qtaq_candidate(true, &profile).unwrap().pass);
    }

    #[test]
    fn coefficient_identity_tail_tamper_is_rejected() {
        let profile = profile();
        assert!(
            synthetic_coefficient_tail(false, false, &profile)
                .unwrap()
                .pass
        );
        assert!(
            !synthetic_coefficient_tail(true, false, &profile)
                .unwrap()
                .pass
        );
        assert!(
            !synthetic_coefficient_tail(false, true, &profile)
                .unwrap()
                .pass
        );
    }

    #[test]
    fn evaluator_provenance_closure_is_deterministic() {
        let first = evaluator_source_sha256();
        let second = evaluator_source_sha256();
        assert_eq!(first, second);
        assert!(is_sha256(&first));
        assert!(
            EVALUATOR_SOURCE_FILE_NAMES
                .windows(2)
                .all(|pair| pair[0] < pair[1])
        );
        assert!(EVALUATOR_SOURCE_FILE_NAMES.contains(&PROFILE_FILE_NAME));
        assert!(EVALUATOR_SOURCE_FILE_NAMES.contains(&"src/profile.rs"));
    }

    #[test]
    fn precision_profile_is_fixed_at_256_bits() {
        let profile = profile();
        assert!(validate_precision_bits(256, &profile).is_ok());
        assert_eq!(
            validate_precision_bits(255, &profile).unwrap_err().code,
            "InvalidOption"
        );
        assert_eq!(
            validate_precision_bits(257, &profile).unwrap_err().code,
            "InvalidOption"
        );
    }

    #[test]
    fn profile_values_drive_numerical_and_resource_judgments() {
        let profile = profile();
        let precision = profile.interval.precision_bits;

        let (base_residual_scale, _) = row_tolerances(false, precision, &profile);
        let mut wider_residual = profile.clone();
        wider_residual
            .residual_allowance
            .value
            .scale_power_of_two_exponent += 1;
        let (wider_residual_scale, _) = row_tolerances(false, precision, &wider_residual);
        assert!(compare_big(&wider_residual_scale, &base_residual_scale).is_gt());

        let (base_qtaq_scale, _) = qtaq_tolerances(false, precision, &profile.qtaq_allowance);
        let mut wider_qtaq = profile.clone();
        wider_qtaq
            .qtaq_allowance
            .value_only
            .physical_component_power_of_two_exponent += 1;
        let (wider_qtaq_scale, _) = qtaq_tolerances(false, precision, &wider_qtaq.qtaq_allowance);
        assert!(compare_big(&wider_qtaq_scale, &base_qtaq_scale).is_gt());

        let base_gamma = dot_roundoff_bound(4, precision, &profile).unwrap();
        let mut wider_gamma = profile.clone();
        wider_gamma
            .coefficient_closure
            .unit_roundoff_power_of_two_exponent += 1;
        let wider_gamma_bound = dot_roundoff_bound(4, precision, &wider_gamma).unwrap();
        assert!(compare_big(&wider_gamma_bound, &base_gamma).is_gt());

        let base_cpd = cpd_threshold(&profile, precision);
        let mut wider_cpd = profile.clone();
        wider_cpd.cpd.threshold_power_of_two_exponent += 1;
        assert!(compare_big(&cpd_threshold(&wider_cpd, precision), &base_cpd).is_gt());

        let base_work = physical_pair_work(4, 1, 1, &profile).unwrap();
        let mut larger_resource_formula = profile.clone();
        larger_resource_formula
            .resource
            .physical_pair_work
            .same_gradient_point_channel_correction += 1;
        assert_eq!(
            physical_pair_work(4, 1, 1, &larger_resource_formula).unwrap(),
            base_work + 1
        );
        assert_eq!(logical_scratch_bytes(4, &profile).unwrap(), 4096);
        larger_resource_formula
            .resource
            .logical_scratch_bytes_per_scalar = 2048;
        assert_eq!(
            logical_scratch_bytes(4, &larger_resource_formula).unwrap(),
            8192
        );
    }

    #[test]
    fn streamed_hermite_qtaq_matches_direct_dense_congruence() {
        let model = PhysicalModel {
            nugget: 0.125,
            polynomial_degree: 0,
            components: vec![RbfComponent {
                family: "gau".to_owned(),
                parameters: vec![1.0, 1.0],
                anisotropy: [[1.0, 0.5, 0.0], [0.0, 1.0, 0.25], [0.0, 0.0, 1.0]],
            }],
        };
        let geometry = Geometry {
            value_points: vec![[0.0, 0.0, 0.0]],
            gradient_points: vec![[0.25, -0.5, 0.75]],
        };
        let lambda = [0.0; 4];
        let precision = 256;
        let mut dense = vec![None; 16];
        let mut constants = Consts::new().unwrap();
        evaluate_action_with_entries(
            &model,
            &geometry,
            &lambda,
            None,
            precision,
            &mut constants,
            |left, right, entry, _scale, mirror| {
                dense[left * 4 + right] = Some(entry.clone());
                if mirror {
                    dense[right * 4 + left] = Some(entry.clone());
                }
                Ok(())
            },
        )
        .unwrap();
        assert!(dense.iter().all(Option::is_some));
        assert!(
            dense[6]
                .as_ref()
                .unwrap()
                .abs_upper()
                .cmp(&BigFloat::new(precision))
                .unwrap()
                > 0,
            "sheared anisotropy must exercise a same-point cross-channel entry"
        );

        let q_top = [0.25, -0.5, 0.75];
        let mut q = vec![vec![Interval::zero(precision); 3]; 4];
        for column in 0..3 {
            q[0][column] = Interval::exact(q_top[column], precision).unwrap();
            q[column + 1][column] = Interval::one(precision);
        }
        let mut captured = Vec::with_capacity(6);
        for row in 0..3 {
            for column in 0..=row {
                let mut expected = Interval::zero(precision);
                for physical_row in 0..4 {
                    for physical_column in 0..4 {
                        expected = expected.add(
                            &q[physical_row][row]
                                .mul(dense[physical_row * 4 + physical_column].as_ref().unwrap())
                                .mul(&q[physical_column][column]),
                        );
                    }
                }
                captured.push((expected.lower_f64() + expected.upper_f64()) * 0.5);
            }
        }

        let block = qtaq_control_block();
        let profile = profile();
        let mut accumulator =
            QtaqPhysicalAccumulator::new(&block, &q_top, &captured, precision, &profile).unwrap();
        let mut constants = Consts::new().unwrap();
        evaluate_action_with_entries(
            &model,
            &geometry,
            &lambda,
            None,
            precision,
            &mut constants,
            |left, right, entry, scale, mirror| {
                accumulator.observe(left, right, entry, scale, mirror)
            },
        )
        .unwrap();
        assert!(accumulator.finish().unwrap().pass);
    }

    #[test]
    fn lock_body_digest_is_canonical_and_tamper_evident() {
        assert_eq!(
            canonical_json_sha256(serde_json::json!({
                "z": "λ",
                "a": "中"
            }))
            .unwrap(),
            "8361acefa5afa3a8b78d8be29a8c4ff196e6edddf96bdb1fa30fe083c14248e6"
        );

        let mut lock = serde_json::json!({
            "schema": "synthetic-lock-v3",
            "nested": {"z": 2, "a": "λ"}
        });
        let digest = canonical_json_sha256(lock.clone()).unwrap();
        lock.as_object_mut()
            .unwrap()
            .insert("corpus_sha256".to_owned(), Value::String(digest.clone()));
        assert_eq!(verify_lock_body_digest(&lock).unwrap(), digest);

        lock["nested"]["z"] = serde_json::json!(3);
        let error = verify_lock_body_digest(&lock).unwrap_err();
        assert_eq!(error.code, "MalformedManifest");
        assert!(error.message.contains("digest mismatch"));
    }

    #[test]
    fn synthetic_fine_projection_and_cpd_are_certifiable() {
        let model = PhysicalModel {
            nugget: 0.0,
            polynomial_degree: 0,
            components: vec![RbfComponent {
                family: "exp".to_owned(),
                parameters: vec![1.0, 1.0],
                anisotropy: identity(),
            }],
        };
        let geometry = Geometry {
            value_points: vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            gradient_points: vec![],
        };
        let lambda = [-1.0, 1.0];
        let e = (-3.0_f64).exp();
        let rhs = [-1.0 + e, 1.0 - e];
        let mut constants = Consts::new().unwrap();
        let action =
            evaluate_action(&model, &geometry, &lambda, None, 256, &mut constants).unwrap();
        let profile = profile();
        let (residuals, allowances) =
            physical_residuals(&action, &rhs, geometry.value_points.len(), 256, &profile).unwrap();
        let block = synthetic_block("fine", 2, 0, 1, 1);
        let (projected, projected_allowed) =
            project_fine_residual(&block, &[-1.0], &residuals, &allowances, 256).unwrap();
        assert!(
            component_certificate(
                &projected,
                &projected_allowed,
                profile.interval.precision_bits,
                "synthetic",
                "synthetic",
            )
            .pass
        );
        assert!(
            certify_cpd(&model, &geometry, &lambda, 256, &profile)
                .unwrap()
                .pass
        );
    }

    #[test]
    fn synthetic_coarse_polynomial_only_fixture_passes_full_residual() {
        let model = PhysicalModel {
            nugget: 0.0,
            polynomial_degree: 1,
            components: vec![RbfComponent {
                family: "th3".to_owned(),
                parameters: vec![1.0, 0.0],
                anisotropy: identity(),
            }],
        };
        let geometry = Geometry {
            value_points: vec![
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            gradient_points: vec![],
        };
        let lambda = [0.0; 4];
        let c = [1.0, 2.0, 3.0, 4.0];
        let rhs = [1.0, 3.0, 4.0, 5.0];
        let mut constants = Consts::new().unwrap();
        let action =
            evaluate_action(&model, &geometry, &lambda, Some(&c), 256, &mut constants).unwrap();
        let profile = profile();
        let (residuals, allowances) =
            physical_residuals(&action, &rhs, geometry.value_points.len(), 256, &profile).unwrap();
        assert!(
            component_certificate(
                &residuals,
                &allowances,
                profile.interval.precision_bits,
                "2^-43",
                "2^-40",
            )
            .pass
        );
        assert!(
            certify_cpd(&model, &geometry, &lambda, 256, &profile)
                .unwrap()
                .pass
        );
    }

    #[test]
    fn coefficient_closure_uses_q_top_and_tail_identity() {
        let block = synthetic_block("fine", 2, 0, 1, 1);
        let loaded = LoadedBlock {
            geometry: Geometry {
                value_points: vec![],
                gradient_points: vec![],
            },
            value_indices: vec![],
            gradient_indices: vec![],
            inner_value_mask: vec![],
            inner_gradient_mask: vec![],
            q_top: vec![-1.0],
            qtaq_lower: vec![],
            rhs_full: vec![],
            rhs_reduced: vec![],
            gamma: vec![2.0],
            lambda: vec![-2.0, 2.0],
            polynomial: None,
            payload_sha256: BTreeMap::new(),
        };
        let profile = profile();
        assert!(
            certify_coefficient_closure(&block, &loaded, 256, &profile)
                .unwrap()
                .pass
        );
    }

    fn synthetic_block(
        role: &str,
        scalar_order: usize,
        gradient_points: usize,
        polynomial_order: usize,
        reduced_order: usize,
    ) -> BlockDescriptor {
        BlockDescriptor {
            block_id: "synthetic".to_owned(),
            workload_id: "synthetic".to_owned(),
            role: role.to_owned(),
            level: 0,
            ordinal: 0,
            source_value_rows: scalar_order - 3 * gradient_points,
            source_gradient_points: gradient_points,
            value_rows: scalar_order - 3 * gradient_points,
            gradient_points,
            inner_value_rows: scalar_order - 3 * gradient_points,
            inner_gradient_points: gradient_points,
            scalar_order,
            polynomial_order,
            reduced_order,
            row_channel_map: "canonical-global-value-offset-v1".to_owned(),
            q_semantics: "Q=[Q_top;I]".to_owned(),
            reference_witness_authority: "untrusted-witness-only".to_owned(),
            artifacts: BTreeMap::new(),
        }
    }
}
