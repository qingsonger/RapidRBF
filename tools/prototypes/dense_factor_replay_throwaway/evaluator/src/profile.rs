use std::collections::BTreeMap;
use std::fmt;

use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::schema::PhysicalEvidenceProfileIdentity;

pub(crate) const PROFILE_FILE_NAME: &str = "physical-evidence-profile.v1.json";
pub(crate) const PINNED_PROFILE_SHA256: &str =
    "cf64f2b26e2a3f4844a5c63027deb5bd4e1f856f0c7f45d4d2afdcccbff724a1";
pub(crate) const EMBEDDED_PROFILE_BYTES: &[u8] =
    include_bytes!("../physical-evidence-profile.v1.json");

const EXPECTED_SCHEMA: &str = "RapidRBF/PhysicalEvidenceProfile/v1";
const EXPECTED_PROFILE_ID: &str = "canonical-hierarchy-physical-evidence-v1";

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PhysicalEvidenceProfile {
    pub schema: String,
    pub profile_id: String,
    pub profile_sha256: String,
    pub interval: IntervalProfile,
    pub residual_allowance: ResidualAllowanceProfile,
    pub qtaq_allowance: QtaqAllowanceProfile,
    pub coefficient_closure: CoefficientClosureProfile,
    pub cpd: CpdProfile,
    pub resource: ResourceProfile,
}

impl PhysicalEvidenceProfile {
    pub(crate) fn identity(&self) -> PhysicalEvidenceProfileIdentity {
        PhysicalEvidenceProfileIdentity {
            schema: self.schema.clone(),
            profile_id: self.profile_id.clone(),
            profile_sha256: self.profile_sha256.clone(),
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct IntervalProfile {
    pub method: String,
    pub precision_bits: usize,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct ResidualAllowanceProfile {
    pub value: TolerancePair,
    pub gradient: TolerancePair,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct TolerancePair {
    pub scale_power_of_two_exponent: i32,
    pub rhs_power_of_two_exponent: i32,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct QtaqAllowanceProfile {
    pub value_only: QtaqTolerancePair,
    pub derivative_involving: QtaqTolerancePair,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct QtaqTolerancePair {
    pub physical_component_power_of_two_exponent: i32,
    pub transform_and_captured_power_of_two_exponent: i32,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct CoefficientClosureProfile {
    pub q_top_gamma_roundoff: String,
    pub unit_roundoff_power_of_two_exponent: i32,
    pub identity_tail: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct CpdProfile {
    pub normalization: String,
    pub threshold_power_of_two_exponent: i32,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct ResourceProfile {
    pub metric: String,
    pub pair_work_metric: String,
    pub logical_scratch_bytes_per_scalar: u64,
    pub physical_pair_work: PhysicalPairWorkProfile,
    pub qtaq_pair_work: QtaqPairWorkProfile,
    pub auxiliary_pair_work: AuxiliaryPairWorkProfile,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PhysicalPairWorkProfile {
    pub upper_triangle_multiplier: u64,
    pub same_gradient_point_channel_correction: u64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct QtaqPairWorkProfile {
    pub a11_q_multiplier: u64,
    pub congruence_terms_per_anchor: u64,
    pub witness_matvec_multiplier: u64,
    pub reduced_rhs_multiplier: u64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct AuxiliaryPairWorkProfile {
    pub cpd_multiplier: u64,
    pub coefficient_q_multiplier: u64,
    pub coefficient_tail_multiplier: u64,
    pub fine_projection_multiplier: u64,
    pub coarse_polynomial_multiplier: u64,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct ProfileError {
    pub code: &'static str,
    pub message: String,
}

impl ProfileError {
    fn malformed(message: impl Into<String>) -> Self {
        Self {
            code: "MalformedProfile",
            message: message.into(),
        }
    }

    fn integrity(message: impl Into<String>) -> Self {
        Self {
            code: "IntegrityMismatch",
            message: message.into(),
        }
    }
}

impl fmt::Display for ProfileError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

pub(crate) fn load_embedded_profile() -> Result<PhysicalEvidenceProfile, ProfileError> {
    load_profile_bytes(EMBEDDED_PROFILE_BYTES)
}

pub(crate) fn load_profile_bytes(bytes: &[u8]) -> Result<PhysicalEvidenceProfile, ProfileError> {
    let value: Value = serde_json::from_slice(bytes)
        .map_err(|error| ProfileError::malformed(format!("invalid profile JSON: {error}")))?;
    let recomputed = profile_body_sha256(&value)?;
    let profile: PhysicalEvidenceProfile = serde_json::from_value(value)
        .map_err(|error| ProfileError::malformed(format!("invalid profile shape: {error}")))?;
    validate_profile(&profile, &recomputed)?;
    Ok(profile)
}

fn validate_profile(
    profile: &PhysicalEvidenceProfile,
    recomputed_sha256: &str,
) -> Result<(), ProfileError> {
    if profile.schema != EXPECTED_SCHEMA || profile.profile_id != EXPECTED_PROFILE_ID {
        return Err(ProfileError::integrity(format!(
            "profile identity drifted: schema={}, profile_id={}",
            profile.schema, profile.profile_id
        )));
    }
    if !is_sha256(&profile.profile_sha256)
        || !profile
            .profile_sha256
            .eq_ignore_ascii_case(recomputed_sha256)
    {
        return Err(ProfileError::integrity(format!(
            "profile body digest mismatch: recorded {}, recomputed {recomputed_sha256}",
            profile.profile_sha256
        )));
    }
    if !recomputed_sha256.eq_ignore_ascii_case(PINNED_PROFILE_SHA256) {
        return Err(ProfileError::integrity(format!(
            "self-consistent profile drift rejected: pinned {PINNED_PROFILE_SHA256}, recomputed {recomputed_sha256}"
        )));
    }
    if profile.interval.method != "pure-rust-directed-rounding-astro-float-num-v0.3.6"
        || profile.interval.precision_bits < 64
        || profile.interval.precision_bits > 16_384
    {
        return Err(ProfileError::malformed(
            "unsupported interval method or precision",
        ));
    }
    for exponent in [
        profile.residual_allowance.value.scale_power_of_two_exponent,
        profile.residual_allowance.value.rhs_power_of_two_exponent,
        profile
            .residual_allowance
            .gradient
            .scale_power_of_two_exponent,
        profile
            .residual_allowance
            .gradient
            .rhs_power_of_two_exponent,
        profile
            .qtaq_allowance
            .value_only
            .physical_component_power_of_two_exponent,
        profile
            .qtaq_allowance
            .value_only
            .transform_and_captured_power_of_two_exponent,
        profile
            .qtaq_allowance
            .derivative_involving
            .physical_component_power_of_two_exponent,
        profile
            .qtaq_allowance
            .derivative_involving
            .transform_and_captured_power_of_two_exponent,
        profile
            .coefficient_closure
            .unit_roundoff_power_of_two_exponent,
        profile.cpd.threshold_power_of_two_exponent,
    ] {
        if !(-1074..=1023).contains(&exponent) {
            return Err(ProfileError::malformed(format!(
                "power-of-two exponent {exponent} is outside binary64 range"
            )));
        }
    }
    if profile.coefficient_closure.q_top_gamma_roundoff != "gamma-k-binary64-v1"
        || profile.coefficient_closure.identity_tail != "exact-binary64-identity"
        || profile.cpd.normalization != "infinity-norm-ratio-with-zero-over-zero-equals-zero-v1"
    {
        return Err(ProfileError::malformed(
            "unsupported coefficient-closure or CPD rule",
        ));
    }
    let resource_values = [
        profile.resource.logical_scratch_bytes_per_scalar,
        profile
            .resource
            .physical_pair_work
            .upper_triangle_multiplier,
        profile
            .resource
            .physical_pair_work
            .same_gradient_point_channel_correction,
        profile.resource.qtaq_pair_work.a11_q_multiplier,
        profile.resource.qtaq_pair_work.congruence_terms_per_anchor,
        profile.resource.qtaq_pair_work.witness_matvec_multiplier,
        profile.resource.qtaq_pair_work.reduced_rhs_multiplier,
        profile.resource.auxiliary_pair_work.cpd_multiplier,
        profile
            .resource
            .auxiliary_pair_work
            .coefficient_q_multiplier,
        profile
            .resource
            .auxiliary_pair_work
            .coefficient_tail_multiplier,
        profile
            .resource
            .auxiliary_pair_work
            .fine_projection_multiplier,
        profile
            .resource
            .auxiliary_pair_work
            .coarse_polynomial_multiplier,
    ];
    if resource_values.contains(&0)
        || profile.resource.metric.is_empty()
        || profile.resource.pair_work_metric.is_empty()
    {
        return Err(ProfileError::malformed(
            "resource metrics and multipliers must be nonzero",
        ));
    }
    Ok(())
}

pub(crate) fn profile_body_sha256(profile: &Value) -> Result<String, ProfileError> {
    let mut body = profile.clone();
    let object = body
        .as_object_mut()
        .ok_or_else(|| ProfileError::malformed("profile is not a JSON object"))?;
    object
        .remove("profile_sha256")
        .ok_or_else(|| ProfileError::malformed("profile has no profile_sha256"))?;
    let bytes = serde_json::to_vec(&canonical_json(body)).map_err(|error| {
        ProfileError::malformed(format!("cannot canonicalize profile: {error}"))
    })?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn canonical_json(value: Value) -> Value {
    match value {
        Value::Array(values) => Value::Array(values.into_iter().map(canonical_json).collect()),
        Value::Object(values) => {
            let entries = values.into_iter().collect::<BTreeMap<_, _>>();
            Value::Object(
                entries
                    .into_iter()
                    .map(|(key, value)| (key, canonical_json(value)))
                    .collect(),
            )
        }
        scalar => scalar,
    }
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_profile_is_canonical_and_pinned() {
        let profile = load_embedded_profile().unwrap();
        assert_eq!(profile.profile_sha256, PINNED_PROFILE_SHA256);
        assert_eq!(
            profile_body_sha256(
                &serde_json::from_slice(EMBEDDED_PROFILE_BYTES).expect("embedded JSON")
            )
            .unwrap(),
            PINNED_PROFILE_SHA256
        );
    }

    #[test]
    fn self_consistent_semantic_drift_is_rejected_by_pin() {
        let mut value: Value =
            serde_json::from_slice(EMBEDDED_PROFILE_BYTES).expect("embedded JSON");
        value["cpd"]["threshold_power_of_two_exponent"] = Value::from(-31);
        let digest = profile_body_sha256(&value).unwrap();
        value["profile_sha256"] = Value::String(digest);
        let bytes = serde_json::to_vec(&value).unwrap();
        let error = load_profile_bytes(&bytes).unwrap_err();
        assert_eq!(error.code, "IntegrityMismatch");
        assert!(error.message.contains("self-consistent profile drift"));
    }
}
