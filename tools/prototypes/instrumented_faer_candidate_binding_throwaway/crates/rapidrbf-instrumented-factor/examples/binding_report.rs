use rapidrbf_instrumented_factor::{CandidateExecutionBinding, FactorRole, FactorShape};

fn report(role: FactorRole, role_name: &str, dimension: usize) {
    let binding = CandidateExecutionBinding::exact();
    let shape = FactorShape {
        role,
        dimension,
        rhs_columns: 1,
    };
    let plan = binding
        .plan(shape)
        .expect("frozen factor plan must fit usize");
    let checkpoints = binding
        .checkpoint_bounds(shape)
        .expect("frozen checkpoint plan must fit usize");
    println!("{role_name} n={dimension}");
    println!("  resource_schedule={plan:#?}");
    println!("  checkpoint_bounds={checkpoints:#?}");
}

fn main() {
    // Planning only: this example never enters either factor backend.
    report(FactorRole::ProjectedB, "projected_b", 2_047);
    report(FactorRole::CoarsePTop, "coarse_p_top", 4);
    println!("backend_calls=0");
}
