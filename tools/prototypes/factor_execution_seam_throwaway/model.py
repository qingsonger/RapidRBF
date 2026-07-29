"""Pure state model for the throwaway factor-execution seam lab.

Question: which one concrete v1 factor-execution seam is plausible enough to
advance to full 216-factor qualification after the direct in-process stock
faer candidate remained diagnostic-only?

This module deliberately performs no I/O and no numerical factorization.  It
makes the competing interface, publication, resource, cancellation, and
prior-state contracts tangible.  The terminal adapter lives in ``tui.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class Candidate(StrEnum):
    IN_PROCESS = "in_process_instrumented_faer"
    PROCESS_WORKER = "process_isolated_faer_worker"
    REOPEN_SUBSTRATE = "reopen_dense_factor_substrate"


class Scenario(StrEnum):
    NORMAL = "normal"
    GRANT_MINUS_ONE = "grant_minus_one"
    CANCEL_MID_FACTOR = "cancel_mid_factor"
    CANCEL_MID_SOLVE = "cancel_mid_solve"
    RELOAD_CONTROLS = "reload_controls"
    DURABLE_PACK_ONLY_GAP = "durable_pack_only_gap"
    HIDDEN_ALLOCATION = "hidden_allocation"
    WORKER_CRASH = "worker_crash"
    STALE_REPLY = "stale_reply"
    SCRATCH_RESIDUE = "scratch_residue"
    REOPEN_CONTENDER = "reopen_contender"
    REOPEN_NO_PLAUSIBLE = "reopen_no_plausible"
    REOPEN_TIMEBOX_EXHAUSTED = "reopen_timebox_exhausted"


class Phase(StrEnum):
    READY = "READY"
    PREFLIGHT = "PREFLIGHT"
    PRIVATE_FACTOR = "PRIVATE_FACTOR"
    FACTOR_CHECK = "FACTOR_CHECK"
    FACTOR_READY = "FACTOR_READY"
    PRIVATE_SOLVE = "PRIVATE_SOLVE"
    SOLVE_CHECK = "SOLVE_CHECK"
    CLEANUP = "CLEANUP"
    TERMINAL = "TERMINAL"


class View(StrEnum):
    STATE = "state"
    INTERFACE = "interface"
    TRADEOFFS = "tradeoffs"


@dataclass(frozen=True)
class Contract:
    candidate: Candidate
    title: str
    verdict: str
    module: str
    interface: tuple[str, ...]
    seam: str
    resource_authority: str
    cancellation_authority: str
    distribution: str
    implementation_hides: tuple[str, ...]
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    next_probe: str


@dataclass(frozen=True)
class Frame:
    phase: Phase
    permit_lease: str
    execution: str
    private_draft: str
    published_state: str
    resource_state: str
    cancellation_state: str
    worker_state: str
    scratch_state: str
    outcome: str
    note: str
    published_correction: str = "SolvedCorrection(previous) - unchanged"
    published_recipe: str = "none"


@dataclass(frozen=True)
class LabState:
    candidate: Candidate = Candidate.IN_PROCESS
    scenario: Scenario = Scenario.NORMAL
    frame_index: int = 0
    view: View = View.STATE


CANDIDATES = tuple(Candidate)
SCENARIOS = tuple(Scenario)
VIEWS = tuple(View)
PRIOR_FACTOR = "ValidatedFactor(previous) - unchanged"
PRIOR_CORRECTION = "SolvedCorrection(previous) - unchanged"


CONTRACTS = {
    Candidate.IN_PROCESS: Contract(
        candidate=Candidate.IN_PROCESS,
        title="Instrumented in-process faer adapter",
        verdict="PLAUSIBLE NEXT PROBE - only with a narrow fork feasibility gate",
        module="RunScopedFactorModule",
        interface=(
            "factorize(source, FactorQualificationPlan, ExecutionLease, Cancellation)",
            "  -> QualifiedFactorAccess",
            "QualifiedFactorAccess = ValidatedFactor | RunScopedRecomputeRecipe",
            "reload(expected_identity, packed_bytes, plan, ExecutionLease, Cancellation)",
            "  -> ValidatedFactor",
            "ValidatedFactor.solve_certified(rhs, certificate_context,",
            "  ExecutionLease, Cancellation) -> SolvedCorrection",
            "RunScopedRecomputeRecipe.solve_certified(rhs, context,",
            "  RecomputeToken, ExecutionLease, Cancellation) -> SolvedCorrection",
            "RecomputeToken <- caller RunRecomputeBudget(plan_id, cap=216)",
        ),
        seam=(
            "The private module seam remains inside the Rust library; callers "
            "never see faer, private-gemm, scratch, or factor layouts."
        ),
        resource_authority=(
            "A caller-owned ExecutionLease grants an aligned arena, retained "
            "reservation, one outer permit, storage policy, and observers."
        ),
        cancellation_authority=(
            "The fork must poll a RapidRBF token at preregistered safe points "
            "with a work-unit bound plus qualified-host latency gate."
        ),
        distribution=(
            "Normal Rust library linkage on all tier-one targets; the patched "
            "source closure becomes part of the candidate identity."
        ),
        implementation_hides=(
            "patched faer/private-gemm/dyn-stack allocation plumbing",
            "fallible cancellation checkpoints and private-draft discard",
            "owned B/P_top packing, runtime witnesses, and atomic publication",
        ),
        strengths=(
            "smallest and deepest caller interface",
            "keeps the official Rust library self-contained",
            "avoids IPC, worker startup, and duplicate process accounting",
        ),
        risks=(
            "requires a maintained fork across more than one upstream crate",
            "every allocation route must enter the ExecutionLease allocation domain",
            "poll spacing must remain bounded without invalidating performance",
        ),
        next_probe=(
            "Before 216 factors: patch one worst-case B and one P_top path, "
            "then prove allocation closure, grant-minus-one, and cancellation "
            "latency on every tier-one target."
        ),
    ),
    Candidate.PROCESS_WORKER: Contract(
        candidate=Candidate.PROCESS_WORKER,
        title="Process-isolated faer worker",
        verdict="CONTAINMENT IS STRONG; V1 LIBRARY/DISTRIBUTION IS BLOCKED",
        module="FactorWorkerController",
        interface=(
            "factorize(source, FactorQualificationPlan, ExecutionLease, Cancellation)",
            "  -> QualifiedFactorAccess",
            "QualifiedFactorAccess = ValidatedFactor | RunScopedRecomputeRecipe",
            "reload(expected_identity, packed_bytes, plan, ExecutionLease, Cancellation)",
            "  -> ValidatedFactor",
            "ValidatedFactor.solve_certified(rhs, certificate_context,",
            "  ExecutionLease, Cancellation) -> SolvedCorrection",
            "RunScopedRecomputeRecipe.solve_certified(rhs, context,",
            "  RecomputeToken, ExecutionLease, Cancellation) -> SolvedCorrection",
            "RecomputeToken <- caller RunRecomputeBudget(plan_id, cap=216)",
            "bind request/reply to epoch, source, profile, binding_id, plan_id,",
            "  executable, and payload hash",
        ),
        seam=(
            "The Rust caller talks to a private worker protocol; platform "
            "adapters own spawn, quota, process-tree observation, kill, and reap."
        ),
        resource_authority=(
            "Exact sizing/allocator control plus controller-owned IPC, scratch, "
            "and a platform enclosure must account for and enforce the grant."
        ),
        cancellation_authority=(
            "Hard cancellation terminates and reaps the complete worker tree "
            "within a bound including cleanup/audit before publication."
        ),
        distribution=(
            "Requires a discoverable matching helper executable for Rust, CLI, "
            "and Python artifacts on all tier-one targets."
        ),
        implementation_hides=(
            "versioned wire protocol and private shared-memory/file transfer",
            "Windows Job Object, Linux cgroup, and macOS process adapters",
            "worker lifecycle, hard kill, reap, accounting, and residue cleanup",
        ),
        strengths=(
            "strong crash and hard-cancellation containment",
            "hidden backend allocations remain inside an observable process tree",
            "parent keeps prior ValidatedFactor state untouched",
        ),
        risks=(
            "four target adapters must meet one abstract obligation while "
            "retaining distinct native measurement semantics",
            "a helper binary is not an ordinary dependency artifact for stable "
            "Cargo library consumers",
            "IPC and process startup become production performance obligations",
        ),
        next_probe=(
            "Do not start 216 factors until a stable-Cargo helper distribution "
            "story, exact grant enforcement, and every tier-one process adapter "
            "close in writing and in a one-factor executable probe."
        ),
    ),
    Candidate.REOPEN_SUBSTRATE: Contract(
        candidate=Candidate.REOPEN_SUBSTRATE,
        title="Reopen the dense-factor substrate",
        verdict="CONTINGENCY ONLY - this is a search seam, not factor execution",
        module="DenseSubstrateAdmission",
        interface=(
            "screen(CandidateExecutionBinding, corpus, FactorHealthProfile, ResourceGrant)",
            "  -> CandidateDisposition",
            "never return ValidatedFactor or unblock the mechanism panel",
        ),
        seam=(
            "This seam evaluates candidate contracts before implementation; a "
            "selected substrate still needs a new concrete execution adapter."
        ),
        resource_authority=(
            "A candidate is rejected at screening unless it exposes a credible "
            "whole-call allocation and lane-control route."
        ),
        cancellation_authority=(
            "A candidate is rejected at screening unless bounded in-flight "
            "cancellation is native or a narrowly owned fork can add it."
        ),
        distribution=(
            "Search remains inside the existing tier-one artifact, licensing, "
            "and runtime-closure ceilings; it cannot widen v1."
        ),
        implementation_hides=(
            "a fixed shortlist and source/interface audits",
            "fail-fast screening against already frozen authority",
            "the handoff from one screened contender to its own adapter ticket",
        ),
        strengths=(
            "avoids committing to a faer fork if its two critical proofs fail",
            "keeps every existing semantic and resource gate unchanged",
            "can surface a substrate with a naturally better seam",
        ),
        risks=(
            "does not itself produce a factor-execution candidate",
            "repeats the already narrowed solver-stack dependency search",
            "can turn into unbounded search unless exit conditions are fixed",
        ),
        next_probe=(
            "Trigger only after both faer seams are evidence-backed rejected "
            "and pinned OxiBLAS 0.2.1 is structurally plausible; timebox that "
            "one CandidateFamily, then select it or record a v1 blocker."
        ),
    ),
}


def _ready(note: str) -> Frame:
    return Frame(
        phase=Phase.READY,
        permit_lease="available; caller still owns it",
        execution="not started",
        private_draft="none",
        published_state=PRIOR_FACTOR,
        resource_state="grant untouched; backend calls = 0",
        cancellation_state="armed; no request",
        worker_state="none",
        scratch_state="clean; 0 bytes; 0 handles",
        outcome="PENDING",
        note=note,
    )


def _terminal(
    *,
    outcome: str,
    note: str,
    resource: str,
    cancellation: str,
    worker: str = "none",
    scratch: str = "clean; 0 bytes; 0 handles",
    published: str = PRIOR_FACTOR,
    published_correction: str = PRIOR_CORRECTION,
    published_recipe: str = "none",
    permit: str = "released to caller",
) -> Frame:
    return Frame(
        phase=Phase.TERMINAL,
        permit_lease=permit,
        execution="finished; no live backend work",
        private_draft="discarded / inaccessible",
        published_state=published,
        resource_state=resource,
        cancellation_state=cancellation,
        worker_state=worker,
        scratch_state=scratch,
        outcome=outcome,
        note=note,
        published_correction=published_correction,
        published_recipe=published_recipe,
    )


REOPEN_ONLY_SCENARIOS = {
    Scenario.REOPEN_CONTENDER,
    Scenario.REOPEN_NO_PLAUSIBLE,
    Scenario.REOPEN_TIMEBOX_EXHAUSTED,
}


def _not_applicable_frames(candidate: Candidate, scenario: Scenario) -> tuple[Frame, ...]:
    start = _ready(f"{scenario.value} applies only to the substrate contingency.")
    return (
        start,
        _terminal(
            outcome="NOT_APPLICABLE",
            note=f"{candidate.value} is already a concrete execution adapter.",
            resource="factor grant untouched; backend calls = 0",
            cancellation="not exercised",
            permit="never acquired; still caller-owned",
        ),
    )


def _reload_control_frames(candidate: Candidate) -> tuple[Frame, ...]:
    worker = "never spawned" if candidate is Candidate.PROCESS_WORKER else "not applicable"
    start = _ready("Exercise packed-record rejection before any replacement is published.")
    truncated = Frame(
        phase=Phase.PREFLIGHT,
        permit_lease="not acquired; caller still owns it",
        execution="attempt 1/5: truncated envelope -> TruncatedRecord",
        private_draft="none",
        published_state=PRIOR_FACTOR,
        resource_state="envelope length checked; zero backend calls/allocations",
        cancellation_state="not exercised",
        worker_state=worker,
        scratch_state="clean; 0 bytes; 0 handles",
        outcome="TruncatedRecord",
        note="Reject structure before payload decode or lease construction.",
    )
    wrong_source = replace(
        truncated,
        execution="attempt 2/5: source identity mismatch -> WrongSource",
        outcome="WrongSource",
        note="The previous factor remains authoritative and directly reusable.",
    )
    wrong_profile = replace(
        truncated,
        execution="attempt 3/5: profile identity mismatch -> WrongProfile",
        outcome="WrongProfile",
        note="A record qualified under another health profile is not reusable.",
    )
    metadata_mismatch = replace(
        truncated,
        execution="attempt 4/5: shape/pivot metadata mismatch -> MetadataMismatch",
        outcome="MetadataMismatch",
        note="Logical factor metadata is checked before backend reload.",
    )
    corrupt = replace(
        truncated,
        execution="attempt 5/5: payload checksum mismatch -> CorruptRecord",
        outcome="CorruptRecord",
        note="No backend may reinterpret, repair, or partially reload the payload.",
    )
    terminal = _terminal(
        outcome="RELOAD_CONTROLS_REJECTED",
        note="All five stable reload controls preserved the prior factor.",
        resource="zero backend calls; zero committed bytes",
        cancellation="not exercised",
        worker=worker,
        permit="never acquired; still caller-owned",
    )
    return (
        start,
        truncated,
        wrong_source,
        wrong_profile,
        metadata_mismatch,
        corrupt,
        terminal,
    )


def _in_process_frames(scenario: Scenario) -> tuple[Frame, ...]:
    if scenario in REOPEN_ONLY_SCENARIOS:
        return _not_applicable_frames(Candidate.IN_PROCESS, scenario)
    if scenario is Scenario.RELOAD_CONTROLS:
        return _reload_control_frames(Candidate.IN_PROCESS)

    start = _ready("Production-shaped in-process module; patched source is the candidate.")
    preflight = Frame(
        phase=Phase.PREFLIGHT,
        permit_lease="held by call-scoped module",
        execution="inputs/profile/binding/plan/source closure validated",
        private_draft="none",
        published_state=PRIOR_FACTOR,
        resource_state="ExecutionLease reserved from exact validated shape",
        cancellation_state="token + checkpoint budget installed",
        worker_state="not applicable - same process",
        scratch_state="temporary storage denied; 0 bytes; 0 handles",
        outcome="PENDING",
        note="No backend entry until allocation routes and cancel topology match.",
    )

    if scenario is Scenario.GRANT_MINUS_ONE:
        sizing = Frame(
            phase=Phase.PREFLIGHT,
            permit_lease="not acquired; caller still owns it",
            execution="checked exact requirement N; offered grant is N-1",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="lease not constructed; zero allocations/backend calls",
            cancellation_state="not installed",
            worker_state="not applicable - same process",
            scratch_state="temporary storage untouched",
            outcome="ResourceDenied",
            note="Reject before permit acquisition, allocation, or backend entry.",
        )
        return (
            start,
            sizing,
            _terminal(
                outcome="ResourceDenied",
                note="One byte below the preflight requirement; backend calls remain zero.",
                resource="zero bytes committed; backend calls = 0",
                cancellation="not exercised",
                permit="never acquired; still caller-owned",
            ),
        )

    factorizing = Frame(
        phase=Phase.PRIVATE_FACTOR,
        permit_lease="one outer compute permit held; adapter fixed at Par::Seq",
        execution="patched faer factorization in progress",
        private_draft="private factor bytes; never caller-visible",
        published_state=PRIOR_FACTOR,
        resource_state="all allocations charged to ExecutionLease",
        cancellation_state="polling at registered safe points",
        worker_state="not applicable - same process",
        scratch_state="temporary storage denied; still zero",
        outcome="PENDING",
        note="A source change that bypasses the domain invalidates this candidate.",
    )

    if scenario is Scenario.CANCEL_MID_FACTOR:
        cancelling = replace(
            factorizing,
            cancellation_state="requested; waiting for bounded safe-point poll",
            note="The qualification must measure and pass the maximum poll latency.",
        )
        return (
            start,
            preflight,
            factorizing,
            cancelling,
            _terminal(
                outcome="Cancelled",
                note="Checkpoint acknowledged; private draft discarded; prior state reusable.",
                resource="ExecutionLease returned to zero live bytes",
                cancellation="acknowledged within the registered bound",
            ),
        )

    if scenario is Scenario.HIDDEN_ALLOCATION:
        violation = replace(
            factorizing,
            execution="unregistered TLS/heap route attempted",
            resource_state="allocation guard rejects route before committing bytes",
            outcome="CONTRACT VIOLATION",
            note="This is a candidate failure, not a larger implicit grant.",
        )
        return (
            start,
            preflight,
            factorizing,
            violation,
            _terminal(
                outcome="BackendContractUnavailable",
                note="Fail closed and disqualify this source closure; never publish.",
                resource="zero hidden bytes committed; violation retained as evidence",
                cancellation="not used to excuse resource failure",
            ),
        )

    if scenario is Scenario.WORKER_CRASH:
        crashed = replace(
            factorizing,
            execution="same-process abort/segfault",
            resource_state="caller process no longer has reliable control",
            cancellation_state="cannot recover a terminated caller",
            outcome="PROCESS LOSS",
            note="In-process depth does not provide crash containment.",
        )
        return (start, preflight, factorizing, crashed)

    if scenario is Scenario.STALE_REPLY:
        return (
            start,
            preflight,
            _terminal(
                outcome="NOT_APPLICABLE",
                note="There is no worker reply; source/profile identity is checked in-process.",
                resource="grant unused",
                cancellation="not exercised",
            ),
        )

    if scenario is Scenario.SCRATCH_RESIDUE:
        dirty = replace(
            factorizing,
            phase=Phase.CLEANUP,
            execution="backend attempted temporary storage before publication",
            scratch_state="unexpected file/write/open handle detected",
            outcome="BACKEND CONTRACT VIOLATION",
            note="This adapter's temporary-storage lease is deny-all.",
        )
        return (
            start,
            preflight,
            factorizing,
            dirty,
            _terminal(
                outcome="ContainmentFailure",
                note="Prior state remains; residue quarantines the attempt lease.",
                resource="memory high-water sealed; temp violation retained",
                cancellation="not a waiver",
                scratch="unexpected residue quarantined as failed-attempt evidence",
                permit="quarantined; not reusable",
            ),
        )

    factor_check = Frame(
        phase=Phase.FACTOR_CHECK,
        permit_lease="factor lease held through factor checks",
        execution="finiteness/reconstruction/metadata/pack-reload checks",
        private_draft="FactorReady(private); no solve result exists",
        published_state=PRIOR_FACTOR,
        resource_state="retained + transient + high-water accounted",
        cancellation_state="still honored before factor publication",
        worker_state="not applicable - same process",
        scratch_state="temporary storage remained zero",
        outcome="PENDING",
        note="FactorHealthProfile decides factor health; physical certificates do not.",
    )

    if scenario is Scenario.DURABLE_PACK_ONLY_GAP:
        durable_gap = replace(
            factor_check,
            execution="all factor gates pass except durable pack/reload",
            outcome="DURABLE_PACK_ONLY_GAP",
            note="The narrow preregistered recompute exception is now eligible.",
        )
        recipe = Frame(
            phase=Phase.FACTOR_READY,
            permit_lease="factor compute lease released; RetainedSourceLease recipe-owned",
            execution="QualifiedFactorAccess::RunScopedRecomputeRecipe returned",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="source lease accounted; RunRecomputeBudget remaining=216/216",
            cancellation_state="factor call complete",
            worker_state="not applicable - same process",
            scratch_state="temporary storage remained zero",
            outcome="RunScopedRecomputeRecipe",
            note="At most 216 recomputations across every recipe in this run.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_n_minus_one = Frame(
            phase=Phase.PREFLIGHT,
            permit_lease="not acquired; caller still owns compute permit",
            execution="recipe control computes exact N; offered N-1 -> ResourceDenied",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="zero backend calls; run token not issued; source lease accounted",
            cancellation_state="not installed",
            worker_state="not applicable - same process",
            scratch_state="temporary storage untouched",
            outcome="ResourceDenied(control)",
            note="The recipe cannot hide recomputation bytes behind its retained source.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_cancel = Frame(
            phase=Phase.PRIVATE_FACTOR,
            permit_lease="fresh control compute lease held",
            execution="run token 1/216 issued+consumed; recomputation cancellation requested",
            private_draft="private recomputed factor; never published",
            published_state=PRIOR_FACTOR,
            resource_state="control charged; RunRecomputeBudget remaining=215/216",
            cancellation_state="polling bounded factor safe points",
            worker_state="not applicable - same process",
            scratch_state="temporary storage remained zero",
            outcome="PENDING",
            note="A backend-entered failed attempt consumes the shared run token.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_cancelled = replace(
            recompute_cancel,
            phase=Phase.CLEANUP,
            permit_lease="control compute lease released; source lease recipe-owned",
            execution="cancellation acknowledged; private recomputed factor discarded",
            private_draft="none",
            resource_state="transient zero; RunRecomputeBudget remaining=215/216",
            cancellation_state="acknowledged within registered recompute bound",
            outcome="Cancelled(control)",
        )
        recompute_solve = Frame(
            phase=Phase.PRIVATE_SOLVE,
            permit_lease="fresh solve lease held",
            execution="run token 2/216 issued+consumed; recipe recomputes then solves",
            private_draft="private recomputed factor + correction",
            published_state=PRIOR_FACTOR,
            resource_state="recompute charged; RunRecomputeBudget remaining=214/216",
            cancellation_state="polling factor and solve safe points",
            worker_state="not applicable - same process",
            scratch_state="temporary storage remained zero",
            outcome="PENDING",
            note="The recipe is never named or cached as a packed factor.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_check = replace(
            recompute_solve,
            phase=Phase.SOLVE_CHECK,
            execution="recomputed correction passes independent certificates",
            private_draft="SolvedCorrection(private)",
            outcome="PENDING",
        )
        return (
            start,
            preflight,
            factorizing,
            factor_check,
            durable_gap,
            recipe,
            recompute_n_minus_one,
            recompute_cancel,
            recompute_cancelled,
            recompute_solve,
            recompute_check,
            _terminal(
                outcome="QUALIFIED_RUN_SCOPED_RECOMPUTE",
                note="N-1 and cancellation controls passed before recipe solve publication.",
                resource="solve sealed; RunRecomputeBudget remaining=214/216",
                cancellation="control acknowledged; production solve not cancelled",
                published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
                published_correction="SolvedCorrection(new generation)",
                permit="compute lease released; RetainedSourceLease recipe-owned",
            ),
        )

    factor_ready = Frame(
        phase=Phase.FACTOR_READY,
        permit_lease="factor lease released; solve lease not yet acquired",
        execution="factorize returned an opaque reusable factor",
        private_draft="none",
        published_state="ValidatedFactor(new generation)",
        resource_state="factor evidence sealed; retained bytes owned",
        cancellation_state="factor call complete",
        worker_state="not applicable - same process",
        scratch_state="temporary storage clean; 0 bytes; 0 handles",
        outcome="ValidatedFactor",
        note="Solve success or failure cannot retroactively change factor health.",
    )
    solve = Frame(
        phase=Phase.PRIVATE_SOLVE,
        permit_lease="fresh solve ExecutionLease held",
        execution="patched faer solve in progress",
        private_draft="private correction; never caller-visible",
        published_state="ValidatedFactor(new generation)",
        resource_state="solve allocations charged to solve lease",
        cancellation_state="polling at registered safe points",
        worker_state="not applicable - same process",
        scratch_state="temporary storage denied; still zero",
        outcome="PENDING",
        note="A failed solve leaves the ValidatedFactor reusable.",
    )

    if scenario is Scenario.CANCEL_MID_SOLVE:
        cancelling = replace(
            solve,
            cancellation_state="requested; waiting for bounded safe-point poll",
            note="The solve path has its own preregistered cancellation bound.",
        )
        return (
            start,
            preflight,
            factorizing,
            factor_check,
            factor_ready,
            solve,
            cancelling,
            _terminal(
                outcome="Cancelled",
                note="Private correction discarded; ValidatedFactor remains reusable.",
                resource="solve lease returned to zero live transient bytes",
                cancellation="solve acknowledged within the registered bound",
                published="ValidatedFactor(new generation)",
            ),
        )

    solve_check = Frame(
        phase=Phase.SOLVE_CHECK,
        permit_lease="solve lease held through external certification",
        execution="operational/constraint/dynamic-range correction checks",
        private_draft="SolvedCorrection(private)",
        published_state="ValidatedFactor(new generation)",
        resource_state="solve retained/transient/high-water accounted",
        cancellation_state="late cancellation still prevents correction commit",
        worker_state="not applicable - same process",
        scratch_state="temporary storage remained zero",
        outcome="PENDING",
        note="Independent value/gradient and CPD certificates decide the correction.",
    )
    solved = _terminal(
        outcome="SolvedCorrection",
        note="Factor and correction crossed their distinct atomic publication gates.",
        resource="factor + solve evidence sealed; scratch clean",
        cancellation="not requested",
        published="ValidatedFactor(new generation)",
        published_correction="SolvedCorrection(new generation)",
    )
    return (
        start,
        preflight,
        factorizing,
        factor_check,
        factor_ready,
        solve,
        solve_check,
        solved,
    )


def _worker_frames(scenario: Scenario) -> tuple[Frame, ...]:
    if scenario in REOPEN_ONLY_SCENARIOS:
        return _not_applicable_frames(Candidate.PROCESS_WORKER, scenario)
    if scenario is Scenario.RELOAD_CONTROLS:
        return _reload_control_frames(Candidate.PROCESS_WORKER)

    start = _ready(
        "Hypothetical worker contract after current distribution/platform blockers close."
    )
    preflight = Frame(
        phase=Phase.PREFLIGHT,
        permit_lease="held by parent controller",
        execution="request/plan/protocol/worker identity validated",
        private_draft="none",
        published_state=PRIOR_FACTOR,
        resource_state="platform enclosure + controller scratch grant prepared",
        cancellation_state="hard-kill handle armed",
        worker_state="not spawned until preflight closes",
        scratch_state="fresh controller-owned directory; empty",
        outcome="PENDING",
        note="Stable helper discovery and platform quota semantics are part of this seam.",
    )

    if scenario is Scenario.GRANT_MINUS_ONE:
        sizing = Frame(
            phase=Phase.PREFLIGHT,
            permit_lease="not acquired; caller still owns it",
            execution="checked exact requirement N; offered grant is N-1",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="no enclosure/scratch/worker; zero backend calls",
            cancellation_state="hard-kill handle not needed",
            worker_state="never spawned",
            scratch_state="controller directory not created",
            outcome="ResourceDenied",
            note="OS OOM/kill is not the one-byte-below control.",
        )
        return (
            start,
            sizing,
            _terminal(
                outcome="ResourceDenied",
                note="One byte below the declared minimum; no worker is spawned.",
                resource="zero bytes committed; backend calls = 0",
                cancellation="not exercised",
                worker="never spawned",
                permit="never acquired; still caller-owned",
            ),
        )

    factorizing = Frame(
        phase=Phase.PRIVATE_FACTOR,
        permit_lease="held by parent; worker cannot mint workers",
        execution="worker factorization in progress",
        private_draft="worker-private factor + factor reply staging",
        published_state=PRIOR_FACTOR,
        resource_state="process-tree high-water/quota observed by parent adapter",
        cancellation_state="parent can terminate complete worker tree",
        worker_state="spawned, enclosed, epoch-bound",
        scratch_state="worker-only directory; occupancy/writes observed",
        outcome="PENDING",
        note="The worker has no publication authority over parent state.",
    )

    if scenario is Scenario.CANCEL_MID_FACTOR:
        killing = replace(
            factorizing,
            cancellation_state="requested; parent terminates process tree",
            worker_state="termination issued; reply channel revoked",
            note="Completion waits for death, reap, and residue verification.",
        )
        cleanup = replace(
            killing,
            phase=Phase.CLEANUP,
            execution="worker dead and reaped",
            private_draft="unreachable; reply rejected",
            worker_state="terminated; no descendants",
            scratch_state="controller cleanup in progress",
            outcome="PENDING",
        )
        return (
            start,
            preflight,
            factorizing,
            killing,
            cleanup,
            _terminal(
                outcome="Cancelled",
                note=(
                    "Hard cancellation completed; any reap/cleanup audit failure "
                    "would instead quarantine the lease as ContainmentFailure."
                ),
                resource="process-tree final accounting sealed",
                cancellation="terminate/reap/cleanup/audit completed within bound",
                worker="dead; no descendants",
            ),
        )

    if scenario is Scenario.HIDDEN_ALLOCATION:
        contained = replace(
            factorizing,
            execution="faer TLS allocation grows inside worker",
            resource_state=(
                "visible to process-tree accounting; quota reaction is platform-specific"
            ),
            note=(
                "Windows/Linux have strong containers; macOS exact enforcement "
                "remains a seam risk."
            ),
        )
        return (
            start,
            preflight,
            factorizing,
            contained,
            _terminal(
                outcome="ContainmentFailure",
                note=(
                    "Tier-one adapter gap: one obligation must close while "
                    "retaining raw OS semantics."
                ),
                resource="exact enforcement/accounting remains unproven; binding quarantined",
                cancellation="hard kill remains available",
                worker="terminated and reaped",
                scratch="residue/handle cleanup unproven on the missing target adapter",
                permit="quarantined; not reusable",
            ),
        )

    if scenario is Scenario.WORKER_CRASH:
        crashed = replace(
            factorizing,
            execution="worker exited unexpectedly",
            private_draft="reply absent / incomplete",
            worker_state="dead; exit status captured",
            outcome="BackendCrashed",
            note="Parent is alive; no unvalidated bytes can cross the seam.",
        )
        return (
            start,
            preflight,
            factorizing,
            crashed,
            _terminal(
                outcome="BackendCrashed",
                note="Crash is a valid failed attempt; prior state remains reusable.",
                resource="final process-tree accounting sealed",
                cancellation="not reclassified as cancellation",
                worker="dead and reaped",
            ),
        )

    if scenario is Scenario.STALE_REPLY:
        stale = replace(
            factorizing,
            phase=Phase.FACTOR_CHECK,
            execution="reply has wrong epoch/source/profile/binding/plan identity",
            private_draft="rejected reply envelope",
            worker_state="quiescent; identity mismatch",
            outcome="ProtocolViolation",
            note="Terminate the cohort and reject stale success before payload decode.",
        )
        return (
            start,
            preflight,
            factorizing,
            stale,
            _terminal(
                outcome="ProtocolViolation",
                note="Stale reply discarded; prior generation remains authoritative.",
                resource="attempt accounting sealed",
                cancellation="not exercised",
                worker="normal exit; reaped",
            ),
        )

    if scenario is Scenario.SCRATCH_RESIDUE:
        dirty = replace(
            factorizing,
            phase=Phase.CLEANUP,
            execution="worker exited; controller found residue/open handle",
            worker_state="dead; cleanup cannot certify zero residue",
            scratch_state="NONZERO residue - primary gate failure",
            outcome="CleanupFailed",
            note=(
                "Live high-water, cumulative writes, open handles, and "
                "delete-on-close/unlinked-open files all count."
            ),
        )
        return (
            start,
            preflight,
            factorizing,
            dirty,
            _terminal(
                outcome="ContainmentFailure",
                note="No publication; cleanup failure quarantines the attempt lease.",
                resource="high-water/writes retained; residue failure recorded",
                cancellation="not a waiver",
                worker="dead and reaped",
                scratch="residue quarantined as failed-attempt evidence",
                permit="quarantined; not reusable",
            ),
        )

    factor_check = Frame(
        phase=Phase.FACTOR_CHECK,
        permit_lease="factor lease held by parent through checks",
        execution="owned factor reply decoded; factor checks in parent",
        private_draft="parent-private OwnedFactorRecord",
        published_state=PRIOR_FACTOR,
        resource_state="process-tree and scratch evidence complete",
        cancellation_state="late cancellation still prevents factor commit",
        worker_state="normal exit; reaped; no descendants",
        scratch_state="zero residue confirmed",
        outcome="PENDING",
        note="Finiteness/reconstruction/metadata/pack-reload close before publication.",
    )

    if scenario is Scenario.DURABLE_PACK_ONLY_GAP:
        durable_gap = replace(
            factor_check,
            execution="all factor gates pass except durable pack/reload",
            outcome="DURABLE_PACK_ONLY_GAP",
            note="The narrow preregistered recompute exception is now eligible.",
        )
        recipe = Frame(
            phase=Phase.FACTOR_READY,
            permit_lease="factor compute lease released; RetainedSourceLease parent-owned",
            execution="parent publishes QualifiedFactorAccess::RunScopedRecomputeRecipe",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="source lease accounted; RunRecomputeBudget remaining=216/216",
            cancellation_state="factor cohort complete",
            worker_state="factor worker reaped; no descendants",
            scratch_state="zero factor residue confirmed",
            outcome="RunScopedRecomputeRecipe",
            note="At most 216 recomputations across every recipe in this run.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_n_minus_one = Frame(
            phase=Phase.PREFLIGHT,
            permit_lease="not acquired; caller still owns compute permit",
            execution="recipe control computes exact N; offered N-1 -> ResourceDenied",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="no cohort/backend call; run token not issued; source accounted",
            cancellation_state="not installed",
            worker_state="never spawned",
            scratch_state="controller directory not created",
            outcome="ResourceDenied(control)",
            note="OS quota reaction is not substituted for exact recipe preflight.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_cancel = Frame(
            phase=Phase.PRIVATE_FACTOR,
            permit_lease="fresh control cohort lease held",
            execution="run token 1/216 issued+consumed; recomputation cancellation requested",
            private_draft="worker-private recomputed factor; reply channel revoked",
            published_state=PRIOR_FACTOR,
            resource_state="control cohort charged; RunRecomputeBudget remaining=215/216",
            cancellation_state="parent terminates complete control cohort",
            worker_state="termination issued; epoch reply rejected",
            scratch_state="control directory cleanup in progress",
            outcome="PENDING",
            note="A backend-entered failed attempt consumes the shared run token.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_cancelled = replace(
            recompute_cancel,
            phase=Phase.CLEANUP,
            permit_lease="control cohort lease released; source lease recipe-owned",
            execution="control cohort terminated, reaped, audited, and discarded",
            private_draft="none",
            resource_state="control sealed; RunRecomputeBudget remaining=215/216",
            cancellation_state="terminate/reap/cleanup/audit completed within bound",
            worker_state="control worker dead; no descendants",
            scratch_state="zero control residue confirmed",
            outcome="Cancelled(control)",
        )
        recompute_solve = Frame(
            phase=Phase.PRIVATE_SOLVE,
            permit_lease="fresh solve cohort lease held",
            execution="run token 2/216 issued+consumed; fresh cohort recomputes then solves",
            private_draft="worker-private factor + correction",
            published_state=PRIOR_FACTOR,
            resource_state="cohort charged; RunRecomputeBudget remaining=214/216",
            cancellation_state="parent hard-kill handle armed",
            worker_state="fresh recompute/solve worker enclosed",
            scratch_state="fresh directory; occupancy/writes observed",
            outcome="PENDING",
            note="A fresh cohort preserves per-operation high-water semantics.",
            published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
        )
        recompute_check = replace(
            recompute_solve,
            phase=Phase.SOLVE_CHECK,
            execution="cohort reaped; correction passes independent certificates",
            private_draft="parent-private SolvedCorrection",
            worker_state="normal exit; reaped; no descendants",
            scratch_state="zero residue confirmed",
        )
        return (
            start,
            preflight,
            factorizing,
            factor_check,
            durable_gap,
            recipe,
            recompute_n_minus_one,
            recompute_cancel,
            recompute_cancelled,
            recompute_solve,
            recompute_check,
            _terminal(
                outcome="QUALIFIED_RUN_SCOPED_RECOMPUTE",
                note="N-1 and cancellation controls passed before recipe solve publication.",
                resource="solve sealed; RunRecomputeBudget remaining=214/216",
                cancellation="control bounded; production solve not cancelled",
                worker=(
                    "factor/solve normal; control terminated; all reaped/audited; "
                    "no descendants"
                ),
                published_recipe="RunScopedRecomputeRecipe(new; shared run budget)",
                published_correction="SolvedCorrection(new generation)",
                permit="compute lease released; RetainedSourceLease recipe-owned",
            ),
        )

    factor_ready = Frame(
        phase=Phase.FACTOR_READY,
        permit_lease="factor lease released; solve lease not yet acquired",
        execution="parent created opaque ValidatedFactor",
        private_draft="none",
        published_state="ValidatedFactor(new generation)",
        resource_state="factor process-tree evidence sealed; retained record owned",
        cancellation_state="factor call complete",
        worker_state="factor worker reaped; no descendants",
        scratch_state="factor scratch clean; 0 handles",
        outcome="ValidatedFactor",
        note="Publish only after reap, zero residue, final accounting, and cancel check.",
    )
    solve = Frame(
        phase=Phase.PRIVATE_SOLVE,
        permit_lease="fresh solve lease held by parent",
        execution="solve worker reloaded owned factor and is computing",
        private_draft="worker-private correction + reply staging",
        published_state="ValidatedFactor(new generation)",
        resource_state="solve process-tree quota/high-water observed",
        cancellation_state="parent can terminate complete solve worker tree",
        worker_state="solve worker enclosed and epoch-bound",
        scratch_state="fresh solve directory; occupancy/writes observed",
        outcome="PENDING",
        note="A failed solve leaves the parent-owned factor reusable.",
    )

    if scenario is Scenario.CANCEL_MID_SOLVE:
        killing = replace(
            solve,
            cancellation_state="requested; parent terminates solve worker tree",
            worker_state="termination issued; solve reply channel revoked",
            note="Completion waits for death, reap, and residue verification.",
        )
        cleanup = replace(
            killing,
            phase=Phase.CLEANUP,
            execution="solve worker dead and reaped",
            private_draft="unreachable; solve reply rejected",
            worker_state="terminated; no descendants",
            scratch_state="controller solve cleanup in progress",
            outcome="PENDING",
        )
        return (
            start,
            preflight,
            factorizing,
            factor_check,
            factor_ready,
            solve,
            killing,
            cleanup,
            _terminal(
                outcome="Cancelled",
                note="Private correction discarded; parent factor remains reusable.",
                resource="solve process-tree final accounting sealed",
                cancellation="terminate/reap/cleanup/audit completed within bound",
                worker="solve worker dead; no descendants",
                published="ValidatedFactor(new generation)",
            ),
        )

    solve_check = Frame(
        phase=Phase.SOLVE_CHECK,
        permit_lease="solve lease held by parent through certification",
        execution="solve reply identity decoded; external certificates running",
        private_draft="parent-private SolvedCorrection",
        published_state="ValidatedFactor(new generation)",
        resource_state="solve process-tree and scratch evidence complete",
        cancellation_state="late cancellation still prevents correction commit",
        worker_state="solve worker normal exit; reaped",
        scratch_state="zero solve residue confirmed",
        outcome="PENDING",
        note="Value/gradient and CPD authority applies to correction, not factor health.",
    )
    solved = _terminal(
        outcome="SolvedCorrection",
        note="Parent alone published the separately checked factor and correction.",
        resource="factor + solve quota/high-water/writes evidence sealed",
        cancellation="not requested",
        worker="all workers normal exit; reaped",
        published="ValidatedFactor(new generation)",
        published_correction="SolvedCorrection(new generation)",
    )
    return (
        start,
        preflight,
        factorizing,
        factor_check,
        factor_ready,
        solve,
        solve_check,
        solved,
    )


def _reopen_frames(scenario: Scenario) -> tuple[Frame, ...]:
    family = "OxiBLAS 0.2.1 @ 00dcf6441ed1e74c1b4e5fe75cad8a06b16ae7bf"

    if scenario not in REOPEN_ONLY_SCENARIOS:
        start = _ready("Current evidence does not trigger the substrate contingency.")
        trigger_check = Frame(
            phase=Phase.PREFLIGHT,
            permit_lease="not acquired - no factor execution",
            execution="evaluate route trigger before screening any replacement",
            private_draft="none",
            published_state=PRIOR_FACTOR,
            resource_state="elapsed=0/5 person-days; candidate families=0/1",
            cancellation_state="not applicable",
            worker_state="execution mode not selected",
            scratch_state="no factor scratch",
            outcome="ROUTE_NOT_TRIGGERED",
            note=(
                "instrumented faer is PLAUSIBLE_NEXT_PROBE; worker blockers are "
                "not yet EVIDENCE_BACKED_REJECTED."
            ),
        )
        detail = (
            "Worker crash/stale reply are conditional on a future worker binding."
            if scenario in {Scenario.WORKER_CRASH, Scenario.STALE_REPLY}
            else "Factor controls cannot run until a concrete replacement seam is selected."
        )
        return (
            start,
            trigger_check,
            _terminal(
                outcome="ROUTE_NOT_TRIGGERED",
                note=detail,
                resource="factor grant untouched; backend calls = 0",
                cancellation="no in-flight factor existed",
                permit="never acquired; still caller-owned",
            ),
        )

    start = _ready("Hypothetical bounded contingency after both faer seams are rejected.")
    prerequisites = Frame(
        phase=Phase.PREFLIGHT,
        permit_lease="not acquired; plan audit only",
        execution=(
            "both faer seams EVIDENCE_BACKED_REJECTED; "
            "STATIC_PLAUSIBLE=PASS"
        ),
        private_draft=f"{family}; four target-specific bindings frozen",
        published_state=PRIOR_FACTOR,
        resource_state="elapsed=0/5 person-days; candidate families=1/1",
        cancellation_state="timebox can stop between bounded steps",
        worker_state="execution mode is part of each target binding",
        scratch_state="no factor scratch",
        outcome="PENDING",
        note="nalgebra 0.35.0 and exact Windows oneMKL remain excluded.",
    )
    plan_audit = replace(
        prerequisites,
        execution="Day 1/5: audit frozen identities, plans, controls, and target closure",
        resource_state="elapsed=1/5 person-days; candidate families=1/1",
        outcome="PENDING",
        note="No candidate observation may rewrite the frozen profile or plan.",
    )

    control_probe = Frame(
        phase=Phase.PRIVATE_FACTOR,
        permit_lease="probe-only lease; no mechanism-panel authority",
        execution="Days 2-4: one max fine + one coarse executable control probe",
        private_draft="diagnostic factor/solve outputs only",
        published_state=PRIOR_FACTOR,
        resource_state="elapsed=4/5 person-days; candidate families=1/1",
        cancellation_state="mid-factor and mid-solve controls required",
        worker_state="crash/protocol controls only if binding mode is worker",
        scratch_state="grant-minus-one/high-water/writes/handles/residue observed",
        outcome="PENDING",
        note="Prior-state reuse and zero publication remain mandatory.",
    )

    if scenario is Scenario.REOPEN_NO_PLAUSIBLE:
        rejected = replace(
            control_probe,
            phase=Phase.CLEANUP,
            execution="Day 5/5: executable control evidence rejects the fixed family",
            resource_state="elapsed=5/5 person-days; family limit reached",
            outcome="REJECTED_FOR_V1",
            note="Static plausibility did not waive executable resource/control gates.",
        )
        return (
            start,
            prerequisites,
            plan_audit,
            control_probe,
            rejected,
            _terminal(
                outcome="NO_PLAUSIBLE_SUBSTRATE_V1_BLOCKER",
                note="The fixed family was rejected; open-ended crate search is forbidden.",
                resource="timebox stopped; executable evidence retained",
                cancellation="no admitted factor remained in flight",
            ),
        )

    if scenario is Scenario.REOPEN_TIMEBOX_EXHAUSTED:
        unresolved = replace(
            control_probe,
            phase=Phase.CLEANUP,
            execution="Day 5/5: required executable control remains unresolved",
            resource_state="elapsed=5/5 person-days; family limit reached",
            outcome="UNJUDGED_TIMEBOX_EXHAUSTED",
            note="Unknown is not rejection, contender status, or permission to add a family.",
        )
        return (
            start,
            prerequisites,
            plan_audit,
            control_probe,
            unresolved,
            _terminal(
                outcome="UNJUDGED_TIMEBOX_EXHAUSTED",
                note="Stop without a contender; mechanism panel remains blocked.",
                resource="timebox and family cap exhausted",
                cancellation="no admitted factor remained in flight",
            ),
        )

    disposition = _terminal(
        outcome="CONTENDER_FOR_HITL",
        note=(
            "Day 5/5: concrete target adapter cards select a seam for later "
            "216-factor qualification; no factor is admitted here."
        ),
        resource="elapsed=5/5 person-days; candidate families=1/1",
        cancellation="probe controls complete; no in-flight work",
        permit="probe lease released; no mechanism-panel authority",
    )
    return (start, prerequisites, plan_audit, control_probe, disposition)


def frames_for(candidate: Candidate, scenario: Scenario) -> tuple[Frame, ...]:
    if candidate is Candidate.IN_PROCESS:
        return _in_process_frames(scenario)
    if candidate is Candidate.PROCESS_WORKER:
        return _worker_frames(scenario)
    return _reopen_frames(scenario)


def current_frame(state: LabState) -> Frame:
    frames = frames_for(state.candidate, state.scenario)
    return frames[min(state.frame_index, len(frames) - 1)]


def current_contract(state: LabState) -> Contract:
    return CONTRACTS[state.candidate]


def reduce_state(state: LabState, action: str) -> LabState:
    if action == "step":
        last = len(frames_for(state.candidate, state.scenario)) - 1
        return replace(state, frame_index=min(state.frame_index + 1, last))
    if action == "reset":
        return replace(state, frame_index=0)
    if action == "next_scenario":
        index = SCENARIOS.index(state.scenario)
        return replace(
            state,
            scenario=SCENARIOS[(index + 1) % len(SCENARIOS)],
            frame_index=0,
        )
    if action == "previous_scenario":
        index = SCENARIOS.index(state.scenario)
        return replace(
            state,
            scenario=SCENARIOS[(index - 1) % len(SCENARIOS)],
            frame_index=0,
        )
    if action == "next_view":
        index = VIEWS.index(state.view)
        return replace(state, view=VIEWS[(index + 1) % len(VIEWS)])
    if action.startswith("candidate:"):
        candidate = Candidate(action.split(":", 1)[1])
        return replace(state, candidate=candidate, frame_index=0)
    if action == "noop":
        return state
    raise ValueError(f"unknown action {action!r}")


def terminal_matrix() -> tuple[tuple[str, str, str], ...]:
    rows = []
    for candidate in CANDIDATES:
        for scenario in SCENARIOS:
            frames = frames_for(candidate, scenario)
            rows.append((candidate.value, scenario.value, frames[-1].outcome))
    return tuple(rows)
