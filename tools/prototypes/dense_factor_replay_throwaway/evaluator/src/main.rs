use std::env;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{self, ExitCode};

use rapidrbf_physical_factor_evaluator::{
    EvaluationOptions, evaluate_corpus, run_builtin_controls,
};
use serde::Serialize;
use serde_json::json;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!(
                "{}",
                serde_json::to_string_pretty(&json!({
                    "schema": "rapidrbf-independent-physical-evaluator-error-v1",
                    "error": message,
                    "backend_calls": 0
                }))
                .expect("error JSON serializes")
            );
            ExitCode::from(2)
        }
    }
}

fn run() -> Result<(), String> {
    let mut arguments = env::args().skip(1);
    let command = arguments.next().unwrap_or_else(|| "help".to_owned());
    match command.as_str() {
        "evaluate" => run_evaluate(arguments.collect()),
        "controls" => run_controls(arguments.collect()),
        "help" | "--help" | "-h" => {
            print_help();
            Ok(())
        }
        other => Err(format!("unknown command {other}; use --help")),
    }
}

fn run_evaluate(arguments: Vec<String>) -> Result<(), String> {
    let mut manifest = None;
    let mut output = None;
    let mut certificate_directory = None;
    let mut options = EvaluationOptions::default();
    let mut index = 0;
    while index < arguments.len() {
        match arguments[index].as_str() {
            "--output" => output = Some(PathBuf::from(take_value(&arguments, &mut index)?)),
            "--cert-dir" => {
                certificate_directory = Some(PathBuf::from(take_value(&arguments, &mut index)?))
            }
            "--block" => options.block_ids.push(take_value(&arguments, &mut index)?),
            "--precision-bits" => {
                options.precision_bits = Some(parse_number(
                    "--precision-bits",
                    &take_value(&arguments, &mut index)?,
                )?)
            }
            "--max-payload-bytes" => {
                options.max_payload_bytes =
                    parse_number("--max-payload-bytes", &take_value(&arguments, &mut index)?)?
            }
            "--max-pair-work" => {
                options.max_pair_work =
                    parse_number("--max-pair-work", &take_value(&arguments, &mut index)?)?
            }
            argument if argument.starts_with('-') => {
                return Err(format!("unknown evaluate option {argument}"));
            }
            argument => {
                if manifest.replace(PathBuf::from(argument)).is_some() {
                    return Err("evaluate accepts exactly one manifest path".to_owned());
                }
            }
        }
        index += 1;
    }
    let manifest = manifest.ok_or_else(|| "evaluate requires a manifest path".to_owned())?;
    let summary = evaluate_corpus(&manifest, &options)
        .map_err(|error| format!("{}: {}", error.code, error.message))?;

    let certificate_directory = certificate_directory.or_else(|| {
        output
            .as_ref()
            .map(|path| default_certificate_directory(path.as_path()))
    });
    let mut certificates_written = 0_usize;
    if let Some(directory) = &certificate_directory {
        fs::create_dir_all(directory)
            .map_err(|error| format!("cannot create {}: {error}", directory.display()))?;
        for certificate in &summary.certificates {
            let filename = format!("{}.json", safe_filename(&certificate.block_id));
            write_json(&directory.join(filename), certificate)?;
            certificates_written += 1;
        }
    }
    let summary_emitted;
    if let Some(output) = output {
        write_json(&output, &summary)?;
        summary_emitted = true;
    } else {
        println!(
            "{}",
            serde_json::to_string_pretty(&summary)
                .map_err(|error| format!("cannot serialize summary: {error}"))?
        );
        summary_emitted = true;
    }
    certification_outcome(
        summary.rejected_factor_count,
        summary.factor_count,
        summary_emitted,
        certificates_written,
    )
}

fn run_controls(arguments: Vec<String>) -> Result<(), String> {
    let mut output = None;
    let mut index = 0;
    while index < arguments.len() {
        match arguments[index].as_str() {
            "--output" => output = Some(PathBuf::from(take_value(&arguments, &mut index)?)),
            argument => return Err(format!("unknown controls option {argument}")),
        }
        index += 1;
    }
    let controls =
        run_builtin_controls().map_err(|error| format!("{}: {}", error.code, error.message))?;
    if let Some(output) = output {
        write_json(&output, &controls)?;
    } else {
        println!(
            "{}",
            serde_json::to_string_pretty(&controls)
                .map_err(|error| format!("cannot serialize controls: {error}"))?
        );
    }
    if controls.pass {
        Ok(())
    } else {
        Err("one or more built-in controls failed".to_owned())
    }
}

fn take_value(arguments: &[String], index: &mut usize) -> Result<String, String> {
    *index += 1;
    arguments
        .get(*index)
        .cloned()
        .ok_or_else(|| "option is missing its value".to_owned())
}

fn parse_number<T>(name: &str, value: &str) -> Result<T, String>
where
    T: std::str::FromStr,
{
    value
        .parse()
        .map_err(|_| format!("{name} requires a nonnegative integer"))
}

fn write_json(path: &Path, value: &impl Serialize) -> Result<(), String> {
    if let Some(parent) = path.parent()
        && !parent.as_os_str().is_empty()
    {
        fs::create_dir_all(parent)
            .map_err(|error| format!("cannot create {}: {error}", parent.display()))?;
    }
    let bytes = serde_json::to_vec_pretty(value)
        .map_err(|error| format!("cannot serialize {}: {error}", path.display()))?;
    if path.exists() {
        return Err(format!(
            "refusing to overwrite existing diagnostic {}",
            path.display()
        ));
    }
    let filename = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| format!("diagnostic path has no UTF-8 filename: {}", path.display()))?;
    let temporary = path.with_file_name(format!(".{filename}.{}.atomic-write", process::id()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)
        .map_err(|error| format!("cannot create {}: {error}", temporary.display()))?;
    if let Err(error) = file.write_all(&bytes).and_then(|()| file.sync_all()) {
        drop(file);
        let _ = fs::remove_file(&temporary);
        return Err(format!("cannot write {}: {error}", path.display()));
    }
    drop(file);
    fs::rename(&temporary, path).map_err(|error| {
        let _ = fs::remove_file(&temporary);
        format!("cannot atomically publish {}: {error}", path.display())
    })
}

fn certification_outcome(
    rejected_factor_count: usize,
    factor_count: usize,
    summary_emitted: bool,
    certificates_written: usize,
) -> Result<(), String> {
    if rejected_factor_count == 0 {
        Ok(())
    } else {
        Err(format!(
            "PhysicalCertificateRejected: {rejected_factor_count} of {factor_count} factors rejected; diagnostics_written={summary_emitted}; certificates_written={certificates_written}; backend_calls=0"
        ))
    }
}

fn default_certificate_directory(summary: &Path) -> PathBuf {
    let parent = summary.parent().unwrap_or_else(|| Path::new(""));
    let stem = summary
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("physical-evaluator");
    parent.join(format!("{stem}.certificates"))
}

fn safe_filename(block_id: &str) -> String {
    block_id
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || character == '-' || character == '_' {
                character
            } else {
                '_'
            }
        })
        .collect()
}

fn print_help() {
    println!(
        "rapidrbf-physical-factor-evaluator

USAGE:
  rapidrbf-physical-factor-evaluator evaluate <hierarchy.manifest.raw.json>
      [--output <summary.json>] [--cert-dir <directory>]
      [--block <block-id>]... [--precision-bits <256>]
      [--max-payload-bytes <bytes>] [--max-pair-work <count>]
  rapidrbf-physical-factor-evaluator controls [--output <controls.json>]

The evaluator never reads captured A or P artifacts and makes zero solver or
factor-backend calls. Captured QTAQ is hash-checked and read only as a candidate
for comparison with independent physical reconstruction, never as its oracle.
Every output has admission_claim=false."
    );
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicUsize, Ordering};

    use super::*;

    static TEMP_SEQUENCE: AtomicUsize = AtomicUsize::new(0);

    #[test]
    fn rejected_evaluation_preserves_written_diagnostics_and_is_nonzero() {
        let sequence = TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let directory = env::temp_dir().join(format!(
            "rapidrbf-physical-evaluator-rejection-test-{}-{sequence}",
            process::id()
        ));
        fs::create_dir(&directory).unwrap();
        let summary = directory.join("summary.json");
        let certificate = directory.join("certificate.json");
        write_json(
            &summary,
            &json!({"rejected_factor_count": 1, "backend_calls": 0}),
        )
        .unwrap();
        write_json(
            &certificate,
            &json!({"state": "physical-certificate-rejected", "backend_calls": 0}),
        )
        .unwrap();

        let error = certification_outcome(1, 1, true, 1).unwrap_err();
        assert!(error.contains("PhysicalCertificateRejected"));
        assert!(error.contains("diagnostics_written=true"));
        assert!(error.contains("backend_calls=0"));
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&fs::read(&summary).unwrap()).unwrap()["rejected_factor_count"],
            1
        );
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&fs::read(&certificate).unwrap()).unwrap()
                ["state"],
            "physical-certificate-rejected"
        );

        fs::remove_file(summary).unwrap();
        fs::remove_file(certificate).unwrap();
        fs::remove_dir(directory).unwrap();
    }
}
