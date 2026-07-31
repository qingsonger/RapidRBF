use rapidrbf_rust_public_api_prototype::contract::compile_walkthrough;
use rapidrbf_rust_public_api_prototype::explorer::{Action, DesignVariant, ExplorerState, reduce};
use std::io::{self, Write};

const BOLD: &str = "\x1b[1m";
const DIM: &str = "\x1b[2m";
const RESET: &str = "\x1b[0m";

fn main() {
    if let Err(error) = compile_walkthrough() {
        eprintln!("The compileable contract walkthrough failed: {error}");
        std::process::exit(1);
    }

    let mut state = ExplorerState::default();
    loop {
        render(&state);
        let mut input = String::new();
        match io::stdin().read_line(&mut input) {
            Ok(0) => break,
            Ok(_) => {}
            Err(error) => {
                eprintln!("Could not read input: {error}");
                break;
            }
        }
        let Some(key) = input.trim().chars().next() else {
            continue;
        };
        if key.eq_ignore_ascii_case(&'q') {
            break;
        }
        if let Some(action) = action_for(key) {
            state = reduce(state, action);
        }
    }
}

fn action_for(key: char) -> Option<Action> {
    Some(match key.to_ascii_lowercase() {
        '1' => Action::Select(DesignVariant::MinimalEnvelope),
        '2' => Action::Select(DesignVariant::ExtensiblePlan),
        '3' => Action::Select(DesignVariant::StudyFacade),
        '4' => Action::Select(DesignVariant::DomainWorkflowHybrid),
        'm' => Action::BuildModel,
        'f' => Action::FitOrdinary,
        'i' => Action::FitIncremental,
        'c' => Action::FitInequality,
        'e' => Action::EvaluateValues,
        'g' => Action::EvaluateValuesAndGradients,
        'k' => Action::RunVariogram,
        'p' => Action::RunPointCloud,
        's' => Action::ExtractSurface,
        'w' => Action::SavePortable,
        'l' => Action::ImportLegacy,
        'x' => Action::ForceFailedRefit,
        'r' => Action::Reset,
        _ => return None,
    })
}

fn render(state: &ExplorerState) {
    print!("\x1b[2J\x1b[H");
    println!("{BOLD}PROTOTYPE — RapidRBF Rust public interface{RESET}");
    println!(
        "{DIM}No numerical implementation; all outcomes are deterministic mock state.{RESET}\n"
    );

    println!("{BOLD}Selected design{RESET}");
    println!("  {}", state.variant.name());
    println!("  Interface : {}", state.variant.interface());
    println!("  Depth     : {}", state.variant.depth());
    println!("  Seam      : {}\n", state.variant.seam());

    println!("{BOLD}Domain state{RESET}");
    println!("  Model              : {}", state.model.unwrap_or("none"));
    println!(
        "  Interpolant<3>     : {}",
        state
            .interpolant_identity
            .map(|id| format!(
                "id={id} · {}",
                state.interpolant_provenance.unwrap_or("unknown")
            ))
            .unwrap_or_else(|| "none".to_owned())
    );
    println!(
        "  Previously retained: {}",
        state
            .preserved_identity
            .map(|id| format!("id={id} (still reusable)"))
            .unwrap_or_else(|| "none".to_owned())
    );
    println!(
        "  Artifact           : {}\n",
        state.artifact.unwrap_or("none")
    );

    println!("{BOLD}Last transition{RESET}");
    println!("  Operation : {}", state.last_operation);
    println!("  Call      : {}", state.last_call);
    println!("  Outcome   : {}\n", state.outcome);

    println!("{BOLD}Normalized report{RESET}");
    println!("  Routing profile : {}", state.report.routing_profile);
    println!("  Workload class  : {}", state.report.workload_class);
    println!("  Requested       : {}", state.report.requested_accuracy);
    println!("  Achieved        : {}", state.report.achieved_accuracy);
    println!("  Resources       : {}", state.report.resources);
    println!("  Atomic publish  : {}\n", state.report.atomic_publication);

    println!("{BOLD}Designs{RESET}  [1] envelope  [2] plan  [3] study  [4] hybrid");
    println!("{BOLD}Model/Fit{RESET} [m] model  [f] ordinary  [i] incremental  [c] inequality");
    println!("{BOLD}Use{RESET}       [e] values  [g] +gradients  [k] variogram  [p] point cloud");
    println!("{BOLD}More{RESET}      [s] surface  [w] save  [l] legacy import  [x] failed refit");
    println!("{BOLD}Control{RESET}   [r] reset  [q] quit");
    print!("> ");
    let _ = io::stdout().flush();
}
