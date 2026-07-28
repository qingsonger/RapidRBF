use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Component, Path, PathBuf};

use sha2::{Digest, Sha256};

use crate::evaluator::EvaluationError;
use crate::schema::ArtifactDescriptor;

#[derive(Clone, Debug)]
pub struct Loaded<T> {
    pub values: Vec<T>,
    pub sha256: String,
}

pub struct ArtifactStore<'a> {
    root: PathBuf,
    artifacts: BTreeMap<&'a str, &'a ArtifactDescriptor>,
}

impl<'a> ArtifactStore<'a> {
    pub fn new(
        manifest_path: &Path,
        descriptors: &'a [ArtifactDescriptor],
    ) -> Result<Self, EvaluationError> {
        let root = manifest_path
            .parent()
            .ok_or_else(|| {
                EvaluationError::new("MalformedManifest", "manifest has no parent directory")
            })?
            .to_owned();
        let mut artifacts = BTreeMap::new();
        for descriptor in descriptors {
            validate_descriptor(descriptor)?;
            if artifacts
                .insert(descriptor.artifact_id.as_str(), descriptor)
                .is_some()
            {
                return Err(EvaluationError::new(
                    "MalformedManifest",
                    format!("duplicate artifact id {}", descriptor.artifact_id),
                ));
            }
        }
        Ok(Self { root, artifacts })
    }

    pub fn descriptor(&self, artifact_id: &str) -> Result<&'a ArtifactDescriptor, EvaluationError> {
        self.artifacts.get(artifact_id).copied().ok_or_else(|| {
            EvaluationError::new(
                "MalformedManifest",
                format!("unknown artifact id {artifact_id}"),
            )
        })
    }

    pub fn declared_bytes_for(
        &self,
        artifact_ids: impl IntoIterator<Item = String>,
    ) -> Result<u64, EvaluationError> {
        let unique: BTreeSet<String> = artifact_ids.into_iter().collect();
        unique.into_iter().try_fold(0_u64, |total, id| {
            let descriptor = self.descriptor(&id)?;
            total.checked_add(descriptor.bytes).ok_or_else(|| {
                EvaluationError::new(
                    "ResourceOverflow",
                    "declared artifact byte count overflowed u64",
                )
            })
        })
    }

    pub fn load_f64(&self, artifact_id: &str) -> Result<Loaded<f64>, EvaluationError> {
        let descriptor = self.descriptor(artifact_id)?;
        if descriptor.dtype != "f64" {
            return Err(type_error(descriptor, "f64"));
        }
        let bytes = self.read_exact(descriptor)?;
        let mut values = Vec::with_capacity(bytes.len() / 8);
        for chunk in bytes.chunks_exact(8) {
            values.push(f64::from_bits(u64::from_le_bytes(
                chunk.try_into().expect("eight-byte chunk"),
            )));
        }
        Ok(Loaded {
            values,
            sha256: sha256(&bytes),
        })
    }

    pub fn load_i64(&self, artifact_id: &str) -> Result<Loaded<i64>, EvaluationError> {
        let descriptor = self.descriptor(artifact_id)?;
        if descriptor.dtype != "i64" {
            return Err(type_error(descriptor, "i64"));
        }
        let bytes = self.read_exact(descriptor)?;
        let mut values = Vec::with_capacity(bytes.len() / 8);
        for chunk in bytes.chunks_exact(8) {
            values.push(i64::from_le_bytes(
                chunk.try_into().expect("eight-byte chunk"),
            ));
        }
        Ok(Loaded {
            values,
            sha256: sha256(&bytes),
        })
    }

    pub fn load_u8(&self, artifact_id: &str) -> Result<Loaded<u8>, EvaluationError> {
        let descriptor = self.descriptor(artifact_id)?;
        if descriptor.dtype != "u8" {
            return Err(type_error(descriptor, "u8"));
        }
        let bytes = self.read_exact(descriptor)?;
        Ok(Loaded {
            values: bytes.clone(),
            sha256: sha256(&bytes),
        })
    }

    fn read_exact(&self, descriptor: &ArtifactDescriptor) -> Result<Vec<u8>, EvaluationError> {
        let relative = safe_relative_path(&descriptor.path)?;
        let path = self.root.join(relative);
        let metadata = fs::metadata(&path).map_err(|error| {
            EvaluationError::new(
                "MalformedPayload",
                format!("cannot stat {}: {error}", path.display()),
            )
        })?;
        if !metadata.is_file() || metadata.len() != descriptor.bytes {
            return Err(EvaluationError::new(
                "MalformedPayload",
                format!(
                    "{} has {} bytes, manifest declares {}",
                    path.display(),
                    metadata.len(),
                    descriptor.bytes
                ),
            ));
        }
        let bytes = fs::read(&path).map_err(|error| {
            EvaluationError::new(
                "MalformedPayload",
                format!("cannot read {}: {error}", path.display()),
            )
        })?;
        if bytes.len() as u64 != descriptor.bytes {
            return Err(EvaluationError::new(
                "MalformedPayload",
                format!("short read from {}", path.display()),
            ));
        }
        Ok(bytes)
    }
}

fn validate_descriptor(descriptor: &ArtifactDescriptor) -> Result<(), EvaluationError> {
    if descriptor.artifact_id.is_empty()
        || descriptor.owner_kind.is_empty()
        || descriptor.owner_id.is_empty()
        || descriptor.role.is_empty()
    {
        return Err(EvaluationError::new(
            "MalformedManifest",
            "artifact identity fields must be nonempty",
        ));
    }
    if descriptor.dtype != "f64" && descriptor.dtype != "i64" && descriptor.dtype != "u8" {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!(
                "{} has unsupported dtype {}",
                descriptor.artifact_id, descriptor.dtype
            ),
        ));
    }
    let element_bytes = if descriptor.dtype == "u8" { 1 } else { 8 };
    let expected_bytes = descriptor
        .stored_elements
        .checked_mul(element_bytes)
        .ok_or_else(|| EvaluationError::new("ResourceOverflow", "artifact byte count overflow"))?;
    if descriptor.bytes != expected_bytes {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!(
                "{} byte count does not match dtype and stored_elements",
                descriptor.artifact_id
            ),
        ));
    }
    if descriptor.dtype == "u8" {
        if descriptor.byte_order != "not-applicable" {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!("{} has invalid u8 byte order", descriptor.artifact_id),
            ));
        }
    } else if descriptor.byte_order != "little" {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!("{} is not little endian", descriptor.artifact_id),
        ));
    }

    let shape_product = descriptor.shape.iter().try_fold(1_u64, |product, extent| {
        product.checked_mul(*extent).ok_or_else(|| {
            EvaluationError::new("ResourceOverflow", "artifact shape product overflow")
        })
    })?;
    let expected_elements = if descriptor.encoding == "lower-triangle-row-major-packed" {
        if descriptor.shape.len() != 2 || descriptor.shape[0] != descriptor.shape[1] {
            return Err(EvaluationError::new(
                "MalformedManifest",
                format!(
                    "{} packed lower shape is not square",
                    descriptor.artifact_id
                ),
            ));
        }
        descriptor.shape[0]
            .checked_mul(descriptor.shape[0].checked_add(1).ok_or_else(|| {
                EvaluationError::new("ResourceOverflow", "packed lower shape overflow")
            })?)
            .and_then(|value| value.checked_div(2))
            .ok_or_else(|| EvaluationError::new("ResourceOverflow", "packed lower size overflow"))?
    } else {
        shape_product
    };
    if descriptor.stored_elements != expected_elements {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!(
                "{} shape/encoding does not match stored_elements",
                descriptor.artifact_id
            ),
        ));
    }
    let _ = safe_relative_path(&descriptor.path)?;
    Ok(())
}

fn safe_relative_path(path: &str) -> Result<PathBuf, EvaluationError> {
    let candidate = Path::new(path);
    if candidate.is_absolute() || path.is_empty() {
        return Err(EvaluationError::new(
            "MalformedManifest",
            format!("artifact path is not a safe relative path: {path}"),
        ));
    }
    let mut result = PathBuf::new();
    for component in candidate.components() {
        match component {
            Component::Normal(value) => result.push(value),
            _ => {
                return Err(EvaluationError::new(
                    "MalformedManifest",
                    format!("artifact path escapes corpus root: {path}"),
                ));
            }
        }
    }
    Ok(result)
}

fn type_error(descriptor: &ArtifactDescriptor, expected: &str) -> EvaluationError {
    EvaluationError::new(
        "MalformedPayload",
        format!(
            "{} has dtype {}, expected {expected}",
            descriptor.artifact_id, descriptor.dtype
        ),
    )
}

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
