//! Independent physical-space evaluator for the throwaway hierarchy corpus.
//!
//! This crate intentionally has no dependency on Polatory, Eigen, or any
//! factorization/solver backend.  It reconstructs only the mathematical
//! operator described by the successor capture manifest.

pub mod evaluator;
pub mod interval;
mod loader;
mod physical;
mod profile;
pub mod schema;

pub use evaluator::{EvaluationError, EvaluationOptions, evaluate_corpus, run_builtin_controls};
pub use schema::{CorpusInput, EvaluationSummary};
