//! Controller-only native thread helper for the Issue 51 preflight.

use std::env;
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Barrier};
use std::thread;
use std::time::Duration;

fn value(arguments: &[String], name: &str) -> String {
    let index = arguments
        .iter()
        .position(|item| item == name)
        .unwrap_or_else(|| panic!("missing {name}"));
    arguments
        .get(index + 1)
        .unwrap_or_else(|| panic!("missing value for {name}"))
        .clone()
}

fn main() {
    let arguments: Vec<String> = env::args().collect();
    let threads: usize = value(&arguments, "--threads").parse().unwrap();
    let entry = PathBuf::from(value(&arguments, "--entry"));
    let release = PathBuf::from(value(&arguments, "--release"));
    assert!(threads >= 1 && !entry.exists() && !release.exists());

    let barrier = Arc::new(Barrier::new(threads));
    let mut workers = Vec::new();
    for _ in 1..threads {
        let worker_barrier = Arc::clone(&barrier);
        let worker_release = release.clone();
        workers.push(thread::spawn(move || {
            worker_barrier.wait();
            while !worker_release.exists() {
                thread::sleep(Duration::from_millis(1));
            }
        }));
    }
    barrier.wait();
    fs::write(
        &entry,
        format!(
            "{{\"schema\":\"RapidRBF/ControllerOnlyHelperEntry/v1\",\
             \"requested_live_threads\":{threads}}}\n"
        ),
    )
    .unwrap();
    while !release.exists() {
        thread::sleep(Duration::from_millis(1));
    }
    for worker in workers {
        worker.join().unwrap();
    }
}
