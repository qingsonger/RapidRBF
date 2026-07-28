use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const INPUT_SCHEMA: &str = "rapidrbf-canonical-hierarchy-admission-corpus-v3";
pub const OUTPUT_SCHEMA: &str = "rapidrbf-independent-physical-evaluator-v2";
pub const FACTOR_CERTIFICATE_SCHEMA: &str = "rapidrbf-independent-physical-factor-certificate-v2";
pub const CONTROL_SCHEMA: &str = "rapidrbf-independent-physical-evaluator-controls-v2";

#[derive(Clone, Debug, Deserialize)]
pub struct CorpusInput {
    pub schema: String,
    pub generator: String,
    pub binary_contract: BinaryContract,
    pub witness_contract: WitnessContract,
    pub inventory_profile: InventoryProfile,
    pub counts: CorpusCounts,
    pub artifacts: Vec<ArtifactDescriptor>,
    pub workloads: Vec<WorkloadDescriptor>,
    pub blocks: Vec<BlockDescriptor>,
    pub factor_sources: Vec<FactorSourceDescriptor>,
    pub auxiliary_decomposition_sources: Vec<Value>,
    pub controls: Vec<Value>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct CorpusCounts {
    pub artifacts: usize,
    pub workloads: usize,
    pub blocks: usize,
    pub fine_blocks: usize,
    pub coarse_blocks: usize,
    pub factor_sources: usize,
    pub qtaq_factor_sources: usize,
    pub p_top_factor_sources: usize,
    pub auxiliary_decomposition_sources: usize,
    pub controls: usize,
}

#[derive(Clone, Debug, Deserialize)]
pub struct InventoryProfile {
    pub profile_id: String,
    pub expected: CorpusCounts,
}

#[derive(Clone, Debug, Deserialize)]
pub struct BinaryContract {
    pub double_bytes: u64,
    pub iec559: bool,
    pub little_endian: bool,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WitnessContract {
    pub authority: String,
    pub per_block: Vec<String>,
    pub coarse_only: Vec<String>,
    pub fine_reference_c: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ArtifactDescriptor {
    pub artifact_id: String,
    pub owner_kind: String,
    pub owner_id: String,
    pub role: String,
    pub path: String,
    pub dtype: String,
    pub byte_order: String,
    pub encoding: String,
    pub shape: Vec<u64>,
    pub stored_elements: u64,
    pub bytes: u64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WorkloadDescriptor {
    pub workload_id: String,
    pub panel_id: String,
    pub case_id: String,
    pub value_rows: usize,
    pub gradient_points: usize,
    pub scalar_order: usize,
    pub observation_row_map: String,
    pub requested_polynomial_degree: Value,
    pub resolved_polynomial_degree: i32,
    pub polynomial_order: usize,
    pub artifacts: WorkloadArtifacts,
    pub model: ModelDescriptor,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WorkloadArtifacts {
    pub value_points: String,
    pub gradient_points: String,
    pub observations: String,
    pub selected_polynomial_indices: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ModelDescriptor {
    pub exact_values_artifact: String,
    pub layout: String,
    pub nugget: OffsetScalar,
    pub rbfs: Vec<RbfDescriptor>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OffsetScalar {
    pub offset: usize,
    pub value: ExactDouble,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ExactDouble {
    pub decimal: f64,
    pub hex: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct RbfDescriptor {
    pub short_name: String,
    pub parameters: OffsetVector,
    pub anisotropy: OffsetMatrix,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OffsetVector {
    pub offset: usize,
    pub count: usize,
    pub values: Vec<ExactDouble>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OffsetMatrix {
    pub offset: usize,
    pub count: usize,
    pub shape: Vec<usize>,
    pub encoding: String,
    pub values: Vec<ExactDouble>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct BlockDescriptor {
    pub block_id: String,
    pub workload_id: String,
    pub role: String,
    pub level: i32,
    pub ordinal: usize,
    pub source_value_rows: usize,
    pub source_gradient_points: usize,
    pub value_rows: usize,
    pub gradient_points: usize,
    pub inner_value_rows: usize,
    pub inner_gradient_points: usize,
    pub scalar_order: usize,
    pub polynomial_order: usize,
    pub reduced_order: usize,
    pub row_channel_map: String,
    pub q_semantics: String,
    pub reference_witness_authority: String,
    pub artifacts: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct FactorSourceDescriptor {
    pub factor_source_id: String,
    pub block_id: String,
    pub workload_id: String,
    pub matrix_role: String,
    pub matrix_artifact: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct EvaluationSummary {
    pub schema: &'static str,
    pub acceptance_profile: PhysicalEvidenceProfileIdentity,
    pub source: SourceIdentity,
    pub proof: ProofIdentity,
    pub resource_preflight: ResourcePreflight,
    pub backend_calls: u64,
    pub factor_count: usize,
    pub certified_factor_count: usize,
    pub rejected_factor_count: usize,
    pub admission_claim: bool,
    pub certificates: Vec<FactorCertificate>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct PhysicalEvidenceProfileIdentity {
    pub schema: String,
    pub profile_id: String,
    pub profile_sha256: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct SourceIdentity {
    pub manifest_path: String,
    pub manifest_sha256: String,
    pub capture_schema: String,
    pub capture_generator: String,
    pub inventory_profile_id: String,
    pub inventory_profile_expected: CorpusCounts,
    pub lock_path: String,
    pub lock_schema: String,
    pub lock_sha256: String,
    pub corpus_sha256: String,
    pub loaded_payloads_lock_verified: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ProofIdentity {
    pub interval_method: String,
    pub precision_bits: usize,
    pub evaluator_source_closure: &'static str,
    pub evaluator_source_files: &'static [&'static str],
    pub evaluator_source_sha256: String,
    pub evaluator_executable_sha256: String,
    pub evaluator_executable_bytes: u64,
    pub arithmetic_inputs: &'static str,
    pub contribution_order: &'static str,
    pub captured_a_read: bool,
    pub captured_p_read: bool,
    pub qtaq_read: bool,
    pub qtaq_role: &'static str,
    pub factorization_or_solver_linked: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ResourcePreflight {
    pub metric: String,
    pub pair_work_metric: String,
    pub required_payload_bytes: u64,
    pub granted_payload_bytes: u64,
    pub required_pair_work: u64,
    pub granted_pair_work: u64,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct FactorCertificate {
    pub schema: &'static str,
    pub acceptance_profile: PhysicalEvidenceProfileIdentity,
    pub block_id: String,
    pub workload_id: String,
    pub role: String,
    pub level: i32,
    pub ordinal: usize,
    pub state: String,
    pub admission_claim: bool,
    pub reference_witness_authority: String,
    pub backend_calls: u64,
    pub assembly_variant: &'static str,
    pub canonical_signs: CanonicalSigns,
    pub payload_sha256: BTreeMap<String, String>,
    pub coefficient_closure: CoefficientClosure,
    pub qtaq_physical_closure: QtaqPhysicalClosure,
    pub residual: ResidualCertificate,
    pub cpd: CpdCertificate,
    pub scatter: ScatterCertificate,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure: Option<FailureRecord>,
}

#[derive(Clone, Debug, Serialize)]
pub struct CanonicalSigns {
    pub value_from_value: &'static str,
    pub value_from_gradient_source: &'static str,
    pub gradient_target_from_value: &'static str,
    pub gradient_target_from_gradient_source: &'static str,
    pub displacement: &'static str,
    pub physical_gradient: &'static str,
    pub physical_hessian: &'static str,
    pub nugget: &'static str,
    pub polynomial_coordinates: &'static str,
}

#[derive(Clone, Debug, Serialize)]
pub struct CoefficientClosure {
    pub checked: bool,
    pub fine_q_gamma_only: bool,
    pub q_top_rows_checked: usize,
    pub identity_tail_rows_checked: usize,
    pub q_top_tolerance: String,
    pub identity_tail_tolerance: String,
    pub max_abs_residual_upper: String,
    pub max_allowed_upper: String,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct QtaqPhysicalClosure {
    pub checked: bool,
    pub source_artifact: String,
    pub reconstruction: &'static str,
    pub matrix_entries: ComponentCertificate,
    pub rhs_reduced: ComponentCertificate,
    pub witness_equation: ComponentCertificate,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ResidualCertificate {
    pub kind: String,
    pub value_rows: ComponentCertificate,
    pub gradient_rows: ComponentCertificate,
    pub projected_rows: ComponentCertificate,
    pub reference_c_published: bool,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ComponentCertificate {
    pub count: usize,
    pub max_abs_residual_upper: String,
    pub min_allowed_margin_lower: String,
    pub absolute_tolerance: String,
    pub relative_tolerance: String,
    pub pass: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub first_failed_row: Option<usize>,
}

#[derive(Clone, Debug, Serialize)]
pub struct CpdCertificate {
    pub normalization: String,
    pub eta_point: String,
    pub alpha_upper: String,
    pub eta_plus_alpha_upper: String,
    pub threshold: String,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ScatterCertificate {
    pub mode: String,
    pub selected_value_rows: usize,
    pub selected_gradient_points: usize,
    pub selected_scalar_rows: usize,
    pub untouched_rows_preserved: bool,
    pub polynomial_tail_published: bool,
    pub row_map_sha256: String,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct FailureRecord {
    pub code: String,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct ControlSummary {
    pub schema: &'static str,
    pub acceptance_profile: PhysicalEvidenceProfileIdentity,
    pub evaluator_source_closure: &'static str,
    pub evaluator_source_files: &'static [&'static str],
    pub evaluator_source_sha256: String,
    pub evaluator_executable_sha256: String,
    pub evaluator_executable_bytes: u64,
    pub backend_calls: u64,
    pub controls: Vec<ControlResult>,
    pub pass: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ControlResult {
    pub control_id: String,
    pub expected_code: String,
    pub actual_code: String,
    pub prior_state_unchanged: bool,
    pub backend_calls: u64,
    pub pass: bool,
}
