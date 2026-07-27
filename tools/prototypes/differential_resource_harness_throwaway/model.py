"""Pure state model for the throwaway differential/resource harness lab.

Question: can one immutable paired plan bind a stable acceptance-scenario
identity and frozen logical input to Polatory and RapidRBF candidate runs,
retain auditable semantic/resource evidence, and stop at COLLECTED, UNJUDGED
until separately owned threshold sets exist?

This module performs no I/O.  Every captured value is deterministic synthetic
data used only to exercise the evidence state model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json


BASELINE_SUBJECT = "Frozen Polatory 4a30beb"
POLATORY_BUILD_ID = "polatory-build:4a30beb:95cd325f727e"
POLATORY_ADAPTER_ID = "polatory-process-adapter:prototype-v1"
HOST_ID = "paired-host:windows-x86_64:demo-pinned"
WRAPPER_ID = "harness-wrapper:prototype-v1"
THREAD_GRANT = 4
MEASUREMENT_BUILD_ROLE = "canonical optimized measurement"
SCRATCH_VOLUME_ID = "scratch-volume:demo-pinned"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def short(value: str, length: int = 12) -> str:
    return value[:length]


@dataclass(frozen=True)
class ChannelRule:
    key: str
    label: str
    comparison_required: bool
    polatory_status: str
    candidate_status: str


@dataclass(frozen=True)
class Scenario:
    stable_id: str
    label: str
    minimum_tier: str
    expected_terminal: str
    oracle_authority: str
    readiness: str
    fixture_digest: str
    description: str
    channels: tuple[ChannelRule, ...]
    synthetic_weight: int


SCENARIOS = (
    Scenario(
        stable_id="OPR.SHAPE.v1/gau/H/prepared-reuse",
        label="Prepared Hessian action",
        minimum_tier="Extended",
        expected_terminal="exited",
        oracle_authority="math/direct, then accepted Polatory slice",
        readiness="reference accepted-ready; candidate missing",
        fixture_digest=digest(
            "OPR.SHAPE.v1/gau/H/prepared-reuse|frozen-small-3d-v1"
        ),
        description=(
            "Repeated self/cross H actions over one frozen 3D fixture; the "
            "logical action and output order are shared, not adapter argv."
        ),
        channels=(
            ChannelRule("values", "values", True, "observed", "observed"),
            ChannelRule("gradients", "gradients", True, "observed", "observed"),
            ChannelRule("hessians", "Hessian blocks", True, "observed", "observed"),
            ChannelRule(
                "certificate",
                "call-scoped error certificate",
                True,
                "derived",
                "observed",
            ),
            ChannelRule(
                "route",
                "route/refinement diagnostics",
                False,
                "unavailable",
                "observed",
            ),
        ),
        synthetic_weight=2,
    ),
    Scenario(
        stable_id="FIT.CENSUS.v1/3/th3+gau/mixed",
        label="Mixed Hermite fit and evaluation",
        minimum_tier="Extended",
        expected_terminal="exited",
        oracle_authority="math/high precision, then accepted Polatory workflow",
        readiness="reference accepted-ready; complete comparator missing",
        fixture_digest=digest(
            "values-3d.csv|gradients-3d.csv|evaluation-points-3d.csv"
        ),
        description=(
            "Fit and evaluate one frozen mixed value/full-gradient problem while "
            "keeping full residual certification separate from solver history."
        ),
        channels=(
            ChannelRule("values", "values", True, "observed", "observed"),
            ChannelRule("gradients", "gradients", True, "observed", "observed"),
            ChannelRule(
                "full_residual",
                "independent full-data residual",
                True,
                "derived",
                "derived",
            ),
            ChannelRule(
                "cpd_residual",
                "CPD side-condition residual",
                True,
                "derived",
                "derived",
            ),
            ChannelRule(
                "iterations",
                "iteration count",
                False,
                "observed",
                "observed",
            ),
            ChannelRule(
                "residual_history",
                "solver residual history",
                False,
                "unavailable",
                "observed",
            ),
        ),
        synthetic_weight=4,
    ),
    Scenario(
        stable_id="INV.CORE.v1/invalid-request/middle-index",
        label="Stable atomic failure",
        minimum_tier="PR",
        expected_terminal="stable_failure",
        oracle_authority="accepted contract; Polatory bytes diagnostic",
        readiness="expected RapidRBF outcome specified; candidate missing",
        fixture_digest=digest("invalid-middle-index|signed-zero-normalized-v1"),
        description=(
            "The normalized result is a stable failure stage/category/index plus "
            "prior-state preservation; wording and raw stderr may differ."
        ),
        channels=(
            ChannelRule(
                "failure_stage", "failure stage", True, "derived", "observed"
            ),
            ChannelRule(
                "failure_category", "failure category", True, "derived", "observed"
            ),
            ChannelRule(
                "original_index", "original failing index", True, "derived", "observed"
            ),
            ChannelRule(
                "atomic_state", "prior-state preservation", True, "derived", "observed"
            ),
            ChannelRule(
                "reusable_state", "state reusable after failure", True, "derived", "observed"
            ),
        ),
        synthetic_weight=1,
    ),
    Scenario(
        stable_id="GEO.ANALYTIC.v1/3d/seeded/Surface/torus",
        label="Certified semantic geometry",
        minimum_tier="Extended",
        expected_terminal="exited",
        oracle_authority="analytic/certified geometry, then Polatory observation",
        readiness="legacy observation accepted-ready; certified oracle missing",
        fixture_digest=digest("analytic-torus-v1|seeded|bbox-v1|accuracy-profile-ref"),
        description=(
            "Compare state, topology, orientation, associations, and certified "
            "metrics while retaining raw meshes without requiring byte identity."
        ),
        channels=(
            ChannelRule("surface_state", "surface state", True, "derived", "observed"),
            ChannelRule("topology", "topology and bbox incidence", True, "derived", "observed"),
            ChannelRule("orientation", "orientation", True, "derived", "observed"),
            ChannelRule(
                "associations", "seed/component associations", True, "derived", "observed"
            ),
            ChannelRule(
                "geometry_metrics", "certified continuous metrics", True, "derived", "observed"
            ),
            ChannelRule(
                "raw_mesh", "raw mesh artifact", False, "observed", "observed"
            ),
        ),
        synthetic_weight=5,
    ),
    Scenario(
        stable_id="SCL.EXP-ORDINARY-1M.v1/windows-x86_64",
        label="Million-scale evidence shape only",
        minimum_tier="Release-blocking",
        expected_terminal="exited",
        oracle_authority="frozen inputs plus full certificates",
        readiness="input prerequisite accepted-ready; execution missing",
        fixture_digest=digest(
            "3955e60f37baad16f6b93c4d29c9346b957386df873b717b"
            "|b0abbfcbfbc2ab3da71a593431e62ba875932303286c95bc0"
        ),
        description=(
            "Exercise the ledger shape for the 1M ordinary fit/evaluation gate. "
            "This prototype never launches that workload."
        ),
        channels=(
            ChannelRule("values", "million target values", True, "observed", "observed"),
            ChannelRule(
                "full_residual", "full fit residual", True, "derived", "derived"
            ),
            ChannelRule(
                "certificate", "accuracy/convergence certificate", True, "derived", "observed"
            ),
            ChannelRule(
                "iterations", "iteration count", True, "observed", "observed"
            ),
            ChannelRule(
                "residual_history", "residual history", False, "unavailable", "observed"
            ),
        ),
        synthetic_weight=9,
    ),
)


@dataclass(frozen=True)
class Candidate:
    key: str
    label: str
    adapter: str
    build_identity: str


CANDIDATES = (
    Candidate(
        "rapidrbf-direct",
        "RapidRBF streaming direct",
        "rust-core-action-adapter",
        "candidate-build:rapidrbf-direct:unimplemented",
    ),
    Candidate(
        "ferreus",
        "Ferreus forced probe",
        "rust-ferreus-probe-adapter",
        "candidate-build:ferreus-d0442ee:unimplemented",
    ),
    Candidate(
        "kifmm",
        "kifmm forced probe",
        "rust-kifmm-probe-adapter",
        "candidate-build:kifmm-d4ca4b5:unimplemented",
    ),
    Candidate(
        "scalfmm3",
        "ScalFMM3 narrow C-ABI probe",
        "rust-scalfmm3-cabi-probe-adapter",
        "candidate-build:scalfmm3-0be3d74:unimplemented",
    ),
)


@dataclass(frozen=True)
class LaneProfile:
    key: str
    label: str
    cache_claim: str
    lifecycle: str


LANES = (
    LaneProfile(
        "fresh-process",
        "Fresh process",
        "new process + isolated scratch; OS page cache is not claimed cold",
        "end-to-end subject invocation",
    ),
    LaneProfile(
        "declared-warmup",
        "Declared warm-up",
        "each subject independently establishes and records one untimed precondition",
        "warm-up retained separately; measured end-to-end invocation",
    ),
    LaneProfile(
        "prepared-reuse",
        "Prepared reuse",
        "prepared state is explicit; retained-memory series is recorded, not judged",
        "preparation and apply phases are metered separately",
    ),
)


@dataclass(frozen=True)
class FaultMode:
    key: str
    label: str


FAULTS = (
    FaultMode("none", "none"),
    FaultMode("fixture-drift", "fixture digest drifts"),
    FaultMode("cache-mismatch", "subject cache profile mismatches"),
    FaultMode("thread-overrun", "maximum-live threads exceed grant"),
    FaultMode("missing-channel", "one required semantic channel is absent"),
    FaultMode("timeout", "subject times out; partial evidence is retained"),
    FaultMode(
        "raw-byte-drift",
        "raw bytes differ while normalized semantics remain equal",
    ),
)


REPETITION_DEMOS = (2, 4, 6)
ORDER_SEEDS = (17, 53, 101)
VIEW_MODES = ("pair-ledger", "pair-detail")


@dataclass(frozen=True)
class RunSlot:
    pair_index: int
    position: int
    subject: str
    role: str


@dataclass(frozen=True)
class ChannelCapture:
    key: str
    status: str


@dataclass(frozen=True)
class ResourceCapture:
    monotonic_wall_ms: int | None
    user_cpu_ms: int | None
    system_cpu_ms: int | None
    platform_peak_memory_bytes: int | None
    normalized_peak_tree_rss_bytes: int | None
    scratch_high_water_bytes: int | None
    io_read_bytes: int | None
    io_write_bytes: int | None
    output_bytes: int | None
    configured_threads: int | None
    effective_threads: int | None
    maximum_live_threads: int | None
    sampling_interval_ms: int | None
    resource_scope: str
    cleanup_verified: bool


@dataclass(frozen=True)
class PhaseCapture:
    name: str
    primary_measurement: bool
    monotonic_wall_ms: int | None
    cpu_ms: int | None
    peak_tree_rss_bytes: int | None
    scratch_high_water_bytes: int | None
    evidence_digest: str


@dataclass(frozen=True)
class LifecycleCapture:
    profile: str
    session_identity: str
    apply_index: int
    precondition_digest: str | None
    phases: tuple[PhaseCapture, ...]
    retained_tree_rss_bytes: int | None
    session_cleanup_verified: bool


@dataclass(frozen=True)
class RunEvidence:
    slot: RunSlot
    plan_digest: str
    fixture_digest: str
    subject: str
    adapter_identity: str
    build_identity: str
    build_role: str
    wrapper_identity: str
    invocation_digest: str
    working_directory: str
    scratch_volume_identity: str
    host_identity: str
    environment_digest: str
    cache_profile: str
    affinity: str
    seed: int
    terminal_status: str
    channels: tuple[ChannelCapture, ...]
    resources: ResourceCapture
    lifecycle: LifecycleCapture
    stdout_digest: str
    stderr_digest: str
    raw_artifact_digest: str
    normalized_observation_digest: str
    record_digest: str
    anomaly: str


@dataclass(frozen=True)
class AuditReport:
    status: str
    conclusion: str
    checks: tuple[tuple[str, bool], ...]
    findings: tuple[str, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class LabState:
    scenario_index: int = 0
    candidate_index: int = 0
    lane_index: int = 0
    repetition_index: int = 1
    order_seed_index: int = 0
    fault_index: int = 0
    phase: str = "DRAFT"
    plan_digest: str | None = None
    bundle_digest: str | None = None
    evidence: tuple[RunEvidence, ...] = ()
    report_requested: bool = False
    view_index: int = 0
    focus_pair: int = 1
    notice: str = "Configure a symbolic plan, then register it."

    @property
    def scenario(self) -> Scenario:
        return SCENARIOS[self.scenario_index]

    @property
    def candidate(self) -> Candidate:
        return CANDIDATES[self.candidate_index]

    @property
    def lane(self) -> LaneProfile:
        return LANES[self.lane_index]

    @property
    def repetitions(self) -> int:
        return REPETITION_DEMOS[self.repetition_index]

    @property
    def order_seed(self) -> int:
        return ORDER_SEEDS[self.order_seed_index]

    @property
    def fault(self) -> FaultMode:
        return FAULTS[self.fault_index]

    @property
    def view(self) -> str:
        return VIEW_MODES[self.view_index]


def plan_payload(state: LabState) -> dict[str, object]:
    return {
        "schema": "rapidrbf-harness-plan/prototype-v1",
        "scenario_id": state.scenario.stable_id,
        "fixture_sha256": state.scenario.fixture_digest,
        "subjects": {
            "polatory": {
                "label": BASELINE_SUBJECT,
                "build": POLATORY_BUILD_ID,
                "adapter": POLATORY_ADAPTER_ID,
            },
            "candidate": {
                "key": state.candidate.key,
                "label": state.candidate.label,
                "build": state.candidate.build_identity,
                "adapter": state.candidate.adapter,
            },
        },
        "measurement_build_role": MEASUREMENT_BUILD_ROLE,
        "lane": state.lane.key,
        "cache_claim": state.lane.cache_claim,
        "host": HOST_ID,
        "affinity": "physical-cores:0-3:demo-pinned",
        "scratch_volume": SCRATCH_VOLUME_ID,
        "thread_grant": THREAD_GRANT,
        "repetitions": state.repetitions,
        "repetition_policy": "illustrative-only; downstream policy ref required",
        "order_seed": state.order_seed,
        "order_policy": (
            "illustrative seeded balanced crossover; downstream policy ref required"
        ),
        "wrapper": WRAPPER_ID,
        "threshold_sets": [],
        "instrumented_link_policy": (
            "separate immutable diagnostic records; never canonical timing"
        ),
    }


def compute_plan_digest(state: LabState) -> str:
    encoded = json.dumps(
        plan_payload(state), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def subject_order(pair_index: int, seed: int) -> tuple[str, str]:
    seeded_start = int(digest(f"{seed}|balanced-crossover")[-1], 16) % 2
    candidate_first = (seeded_start + pair_index - 1) % 2
    if candidate_first == 0:
        return ("polatory", "candidate")
    return ("candidate", "polatory")


def slots(state: LabState) -> tuple[RunSlot, ...]:
    result: list[RunSlot] = []
    for pair_index in range(1, state.repetitions + 1):
        for position, role in enumerate(
            subject_order(pair_index, state.order_seed), start=1
        ):
            subject = BASELINE_SUBJECT if role == "polatory" else state.candidate.label
            result.append(RunSlot(pair_index, position, subject, role))
    return tuple(result)


def _channel_captures(state: LabState, role: str) -> tuple[ChannelCapture, ...]:
    captures = [
        ChannelCapture(
            rule.key,
            rule.polatory_status if role == "polatory" else rule.candidate_status,
        )
        for rule in state.scenario.channels
    ]
    if state.fault.key == "missing-channel":
        required = {
            rule.key for rule in state.scenario.channels if rule.comparison_required
        }
        for index, capture in enumerate(captures):
            if capture.key in required:
                del captures[index]
                break
    if state.fault.key == "timeout":
        captures = [
            ChannelCapture(capture.key, "unavailable") for capture in captures
        ]
    return tuple(captures)


def _phase(
    name: str,
    primary_measurement: bool,
    wall_ms: int | None,
    cpu_ms: int | None,
    peak_tree_rss_bytes: int | None,
    scratch_high_water_bytes: int | None,
) -> PhaseCapture:
    payload = {
        "name": name,
        "primary_measurement": primary_measurement,
        "monotonic_wall_ms": wall_ms,
        "cpu_ms": cpu_ms,
        "peak_tree_rss_bytes": peak_tree_rss_bytes,
        "scratch_high_water_bytes": scratch_high_water_bytes,
    }
    evidence_digest = digest(
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )
    return PhaseCapture(evidence_digest=evidence_digest, **payload)


def compute_phase_digest(phase: PhaseCapture) -> str:
    payload = asdict(phase)
    payload.pop("evidence_digest")
    return digest(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _subject_run_index(state: LabState, role: str) -> int:
    return 1 + sum(record.slot.role == role for record in state.evidence)


def _resources(
    state: LabState, slot: RunSlot, ordinal: int
) -> ResourceCapture:
    subject_factor = 11 if slot.role == "polatory" else 9
    lane_factor = state.lane_index + 1
    weight = state.scenario.synthetic_weight
    wall = 30 + weight * 23 + subject_factor + lane_factor * 7 + ordinal
    peak = (12 + weight * 5 + subject_factor) * 1024 * 1024
    configured = THREAD_GRANT
    maximum = min(configured, 2 + state.lane_index)
    if state.fault.key == "thread-overrun":
        maximum = configured + 2
    complete = state.fault.key != "timeout"
    subject_run_index = _subject_run_index(state, slot.role)
    cleanup_verified = (
        state.lane.key != "prepared-reuse"
        or subject_run_index == state.repetitions
    )
    return ResourceCapture(
        monotonic_wall_ms=wall,
        user_cpu_ms=wall * 2 if complete else None,
        system_cpu_ms=max(1, wall // 7) if complete else None,
        platform_peak_memory_bytes=peak if complete else None,
        normalized_peak_tree_rss_bytes=peak if complete else None,
        scratch_high_water_bytes=(weight + 1) * 1024 * 1024 if complete else None,
        io_read_bytes=(weight + 2) * 4096 if complete else None,
        io_write_bytes=(weight + 1) * 2048 if complete else None,
        output_bytes=(weight + 1) * 8192 if complete else None,
        configured_threads=configured,
        effective_threads=min(2 + state.lane_index, configured) if complete else None,
        maximum_live_threads=maximum if complete else None,
        sampling_interval_ms=10 if complete else None,
        resource_scope="contained descendant process tree",
        cleanup_verified=cleanup_verified,
    )


def _lifecycle(
    state: LabState,
    slot: RunSlot,
    resources: ResourceCapture,
    cache_profile: str,
) -> LifecycleCapture:
    subject_run_index = _subject_run_index(state, slot.role)
    cpu = (
        None
        if resources.user_cpu_ms is None or resources.system_cpu_ms is None
        else resources.user_cpu_ms + resources.system_cpu_ms
    )
    invoke = _phase(
        "invoke" if state.lane.key != "prepared-reuse" else "apply",
        True,
        resources.monotonic_wall_ms,
        cpu,
        resources.normalized_peak_tree_rss_bytes,
        resources.scratch_high_water_bytes,
    )

    if state.lane.key == "fresh-process":
        session = digest(
            f"{state.plan_digest}|{slot.role}|{slot.pair_index}|fresh-session"
        )
        return LifecycleCapture(
            profile=cache_profile,
            session_identity=session,
            apply_index=1,
            precondition_digest=None,
            phases=(invoke,),
            retained_tree_rss_bytes=None,
            session_cleanup_verified=True,
        )

    if state.lane.key == "declared-warmup":
        session = digest(
            f"{state.plan_digest}|{slot.role}|{slot.pair_index}|warm-session"
        )
        warmup = _phase(
            "warmup",
            False,
            5 + state.scenario.synthetic_weight,
            7 + state.scenario.synthetic_weight,
            resources.normalized_peak_tree_rss_bytes,
            resources.scratch_high_water_bytes,
        )
        return LifecycleCapture(
            profile=cache_profile,
            session_identity=session,
            apply_index=1,
            precondition_digest=digest(f"{session}|warmup-precondition"),
            phases=(warmup, invoke),
            retained_tree_rss_bytes=None,
            session_cleanup_verified=True,
        )

    session = digest(f"{state.plan_digest}|{slot.role}|prepared-session")
    phases: list[PhaseCapture] = []
    if subject_run_index == 1:
        phases.append(
            _phase(
                "prepare",
                False,
                12 + state.scenario.synthetic_weight * 2,
                15 + state.scenario.synthetic_weight * 2,
                resources.normalized_peak_tree_rss_bytes,
                resources.scratch_high_water_bytes,
            )
        )
    phases.append(invoke)
    retained = (
        None
        if resources.normalized_peak_tree_rss_bytes is None
        else resources.normalized_peak_tree_rss_bytes
        + state.scenario.synthetic_weight * 4096
    )
    return LifecycleCapture(
        profile=cache_profile,
        session_identity=session,
        apply_index=subject_run_index,
        precondition_digest=digest(f"{session}|prepared-state"),
        phases=tuple(phases),
        retained_tree_rss_bytes=retained,
        session_cleanup_verified=(
            subject_run_index == state.repetitions
        ),
    )


def record_payload(record: RunEvidence) -> dict[str, object]:
    payload = asdict(record)
    payload.pop("record_digest")
    return payload


def compute_record_digest(record: RunEvidence) -> str:
    return digest(
        json.dumps(record_payload(record), sort_keys=True, separators=(",", ":"))
    )


def compute_bundle_digest(
    plan_digest: str, evidence: tuple[RunEvidence, ...]
) -> str:
    payload = {
        "schema": "rapidrbf-evidence-bundle/prototype-v1",
        "plan_digest": plan_digest,
        "record_digests": [record.record_digest for record in evidence],
    }
    return digest(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def build_evidence(state: LabState, slot: RunSlot) -> RunEvidence:
    if state.plan_digest is None:
        raise ValueError("plan must be registered before capture")
    ordinal = len(state.evidence) + 1
    fixture = state.scenario.fixture_digest
    cache_profile = state.lane.key
    if state.fault.key == "fixture-drift":
        fixture = digest(f"{fixture}|tampered")
    if state.fault.key == "cache-mismatch":
        cache_profile = "undeclared-cache-state"

    terminal = state.scenario.expected_terminal
    if state.fault.key == "timeout":
        terminal = "deadline_exceeded"

    build_identity = (
        POLATORY_BUILD_ID
        if slot.role == "polatory"
        else state.candidate.build_identity
    )
    adapter_identity = (
        POLATORY_ADAPTER_ID
        if slot.role == "polatory"
        else state.candidate.adapter
    )
    channels = _channel_captures(state, slot.role)
    rules = {rule.key: rule for rule in state.scenario.channels}
    semantic_shape = "|".join(
        (
            f"{item.key}:synthetic-payload-v1"
            if item.status in {"observed", "derived"}
            else f"{item.key}:{item.status}"
        )
        for item in channels
        if rules[item.key].comparison_required
    )
    semantic_label = (
        f"{state.scenario.stable_id}|{fixture}|{slot.pair_index}|"
        f"{semantic_shape}|normalized-demo-result"
    )
    if state.fault.key == "raw-byte-drift":
        raw_label = f"raw-byte-drift|{slot.subject}|{ordinal}"
    else:
        raw_label = f"raw|{slot.subject}|{ordinal}|{semantic_label}"
    normalized_digest = digest(semantic_label)
    raw_digest = digest(raw_label)
    stdout_digest = digest(f"stdout|{raw_label}")
    stderr_digest = digest(f"stderr|{raw_label}")
    invocation_digest = digest(
        f"argv|{adapter_identity}|{state.scenario.stable_id}|allowlist-v1"
    )
    resources = _resources(state, slot, ordinal)
    lifecycle = _lifecycle(state, slot, resources, cache_profile)
    record = RunEvidence(
        slot=slot,
        plan_digest=state.plan_digest,
        fixture_digest=fixture,
        subject=slot.subject,
        adapter_identity=adapter_identity,
        build_identity=build_identity,
        build_role=MEASUREMENT_BUILD_ROLE,
        wrapper_identity=WRAPPER_ID,
        invocation_digest=invocation_digest,
        working_directory="isolated-slot-root",
        scratch_volume_identity=SCRATCH_VOLUME_ID,
        host_identity=HOST_ID,
        environment_digest=digest(f"env|{slot.role}|{build_identity}|allowlist-v1"),
        cache_profile=cache_profile,
        affinity="physical-cores:0-3:demo-pinned",
        seed=state.order_seed,
        terminal_status=terminal,
        channels=channels,
        resources=resources,
        lifecycle=lifecycle,
        stdout_digest=stdout_digest,
        stderr_digest=stderr_digest,
        raw_artifact_digest=raw_digest,
        normalized_observation_digest=normalized_digest,
        record_digest="",
        anomaly=state.fault.key,
    )
    return replace(record, record_digest=compute_record_digest(record))


def _pair_complete(state: LabState) -> bool:
    expected_roles = {"polatory", "candidate"}
    for pair_index in range(1, state.repetitions + 1):
        roles = {
            record.slot.role
            for record in state.evidence
            if record.slot.pair_index == pair_index
        }
        if roles != expected_roles:
            return False
    return True


def _records_conform_to_plan(state: LabState) -> bool:
    if state.plan_digest is None:
        return False
    expected_slots = slots(state)
    if len(state.evidence) != len(expected_slots):
        return False
    for expected_slot, record in zip(expected_slots, state.evidence):
        expected_build = (
            POLATORY_BUILD_ID
            if expected_slot.role == "polatory"
            else state.candidate.build_identity
        )
        expected_adapter = (
            POLATORY_ADAPTER_ID
            if expected_slot.role == "polatory"
            else state.candidate.adapter
        )
        expected_environment = digest(
            f"env|{expected_slot.role}|{expected_build}|allowlist-v1"
        )
        expected_invocation = digest(
            f"argv|{expected_adapter}|{state.scenario.stable_id}|allowlist-v1"
        )
        if (
            record.slot != expected_slot
            or record.subject != expected_slot.subject
            or record.build_identity != expected_build
            or record.adapter_identity != expected_adapter
            or record.environment_digest != expected_environment
            or record.invocation_digest != expected_invocation
            or record.seed != state.order_seed
            or record.fixture_digest != state.scenario.fixture_digest
            or record.cache_profile != state.lane.key
            or record.host_identity != HOST_ID
            or record.affinity != "physical-cores:0-3:demo-pinned"
            or record.scratch_volume_identity != SCRATCH_VOLUME_ID
            or record.wrapper_identity != WRAPPER_ID
            or record.build_role != MEASUREMENT_BUILD_ROLE
            or record.plan_digest != state.plan_digest
        ):
            return False
    return True


def _lifecycle_complete(state: LabState) -> bool:
    if not state.evidence:
        return False

    for record in state.evidence:
        lifecycle = record.lifecycle
        if lifecycle.profile != state.lane.key:
            return False
        if lifecycle.session_cleanup_verified != record.resources.cleanup_verified:
            return False
        if not lifecycle.phases or sum(
            phase.primary_measurement for phase in lifecycle.phases
        ) != 1:
            return False
        for phase in lifecycle.phases:
            if (
                phase.monotonic_wall_ms is None
                or phase.cpu_ms is None
                or phase.peak_tree_rss_bytes is None
                or phase.scratch_high_water_bytes is None
                or phase.evidence_digest != compute_phase_digest(phase)
            ):
                return False

    if state.lane.key == "fresh-process":
        sessions = {record.lifecycle.session_identity for record in state.evidence}
        return (
            len(sessions) == len(state.evidence)
            and all(
                tuple(phase.name for phase in record.lifecycle.phases) == ("invoke",)
                and record.lifecycle.apply_index == 1
                and record.lifecycle.precondition_digest is None
                and record.lifecycle.retained_tree_rss_bytes is None
                and record.lifecycle.session_cleanup_verified
                for record in state.evidence
            )
        )

    if state.lane.key == "declared-warmup":
        sessions = {record.lifecycle.session_identity for record in state.evidence}
        return (
            len(sessions) == len(state.evidence)
            and all(
                tuple(phase.name for phase in record.lifecycle.phases)
                == ("warmup", "invoke")
                and not record.lifecycle.phases[0].primary_measurement
                and record.lifecycle.phases[1].primary_measurement
                and record.lifecycle.apply_index == 1
                and bool(record.lifecycle.precondition_digest)
                and record.lifecycle.retained_tree_rss_bytes is None
                and record.lifecycle.session_cleanup_verified
                for record in state.evidence
            )
        )

    for role in ("polatory", "candidate"):
        records = [
            record for record in state.evidence if record.slot.role == role
        ]
        if len(records) != state.repetitions:
            return False
        if len({record.lifecycle.session_identity for record in records}) != 1:
            return False
        if [record.lifecycle.apply_index for record in records] != list(
            range(1, state.repetitions + 1)
        ):
            return False
        if tuple(phase.name for phase in records[0].lifecycle.phases) != (
            "prepare",
            "apply",
        ):
            return False
        if any(
            tuple(phase.name for phase in record.lifecycle.phases) != ("apply",)
            for record in records[1:]
        ):
            return False
        if any(
            not record.lifecycle.precondition_digest
            or record.lifecycle.retained_tree_rss_bytes is None
            for record in records
        ):
            return False
        if any(record.lifecycle.session_cleanup_verified for record in records[:-1]):
            return False
        if not records[-1].lifecycle.session_cleanup_verified:
            return False
    return True


def audit(state: LabState) -> AuditReport:
    expected = len(slots(state)) if state.plan_digest else state.repetitions * 2
    registered = state.plan_digest is not None
    complete = registered and len(state.evidence) == expected
    pair_complete = complete and _pair_complete(state)
    fixture_stable = bool(state.evidence) and all(
        record.fixture_digest == state.scenario.fixture_digest
        for record in state.evidence
    )
    paired_lane = bool(state.evidence) and all(
        record.host_identity == HOST_ID
        and record.cache_profile == state.lane.key
        and record.affinity == "physical-cores:0-3:demo-pinned"
        and record.scratch_volume_identity == SCRATCH_VOLUME_ID
        for record in state.evidence
    )

    rules = {rule.key: rule for rule in state.scenario.channels}
    channels_complete = bool(state.evidence)
    for record in state.evidence:
        captured = {item.key: item.status for item in record.channels}
        if set(captured) != set(rules):
            channels_complete = False
            break
        for key, rule in rules.items():
            if rule.comparison_required and captured[key] not in {"observed", "derived"}:
                channels_complete = False
                break

    required_resource_values = (
        "monotonic_wall_ms",
        "user_cpu_ms",
        "system_cpu_ms",
        "platform_peak_memory_bytes",
        "normalized_peak_tree_rss_bytes",
        "scratch_high_water_bytes",
        "io_read_bytes",
        "io_write_bytes",
        "output_bytes",
        "configured_threads",
        "effective_threads",
        "maximum_live_threads",
        "sampling_interval_ms",
    )
    resources_complete = bool(state.evidence) and all(
        all(getattr(record.resources, key) is not None for key in required_resource_values)
        and record.resources.resource_scope == "contained descendant process tree"
        for record in state.evidence
    )
    lifecycle_complete = _lifecycle_complete(state)
    threads_within_grant = bool(state.evidence) and all(
        record.resources.configured_threads is not None
        and record.resources.effective_threads is not None
        and record.resources.maximum_live_threads is not None
        and 0
        < record.resources.effective_threads
        <= record.resources.maximum_live_threads
        <= record.resources.configured_threads
        == THREAD_GRANT
        for record in state.evidence
    )
    terminal_expected = bool(state.evidence) and all(
        record.terminal_status == state.scenario.expected_terminal
        for record in state.evidence
    )
    records_conform = _records_conform_to_plan(state)
    record_integrity = bool(state.evidence) and all(
        bool(record.raw_artifact_digest)
        and bool(record.stdout_digest)
        and bool(record.stderr_digest)
        and bool(record.normalized_observation_digest)
        and bool(record.record_digest)
        and bool(record.invocation_digest)
        and record.build_role == MEASUREMENT_BUILD_ROLE
        and record.working_directory == "isolated-slot-root"
        and record.plan_digest == state.plan_digest
        and record.wrapper_identity == WRAPPER_ID
        and record.record_digest == compute_record_digest(record)
        for record in state.evidence
    )
    plan_integrity = (
        state.plan_digest is not None
        and state.plan_digest == compute_plan_digest(state)
    )
    bundle_integrity = (
        state.plan_digest is not None
        and state.bundle_digest is not None
        and state.bundle_digest
        == compute_bundle_digest(state.plan_digest, state.evidence)
    )
    integrity_closed = (
        records_conform
        and record_integrity
        and plan_integrity
        and bundle_integrity
    )

    checks = (
        ("registered immutable plan", registered),
        ("all pre-registered slots captured", complete),
        ("every repetition is a complete pair", pair_complete),
        ("each record conforms to its exact plan slot", records_conform),
        ("fixture identity is stable", fixture_stable),
        ("host/affinity/cache lane is paired", paired_lane),
        ("declared semantic channels are explicit", channels_complete),
        ("process-tree resource record is complete", resources_complete),
        ("cache/reuse lifecycle evidence is explicit", lifecycle_complete),
        ("thread accounting stays within grant", threads_within_grant),
        ("terminal state matches scenario", terminal_expected),
        ("raw + normalized checksum closure", integrity_closed),
    )
    findings = tuple(label for label, passed in checks if not passed)
    diagnostics: list[str] = []
    if any(record.anomaly == "raw-byte-drift" for record in state.evidence):
        diagnostics.append(
            "Raw-byte drift is retained, but semantic comparison does not use "
            "raw text/mesh identity as a global pass criterion."
        )
    if any(
        item.status == "unavailable"
        for record in state.evidence
        for item in record.channels
        if not rules[item.key].comparison_required
    ):
        diagnostics.append(
            "A diagnostic channel is explicitly unavailable; it is not silently "
            "missing and does not block the declared semantic comparison."
        )
    if state.lane.key == "prepared-reuse" and state.evidence:
        diagnostics.append(
            "Preparation/apply phases and retained-memory samples are present; "
            "plateau judgment remains external to this unthresholded report."
        )

    if not registered:
        status = "DRAFT"
        conclusion = "No evidence plan exists."
    elif not complete:
        status = "COLLECTING"
        conclusion = (
            "Evidence is append-only but incomplete; no pair or acceptance "
            "conclusion is available."
        )
    elif findings:
        status = "AUDIT BLOCKED"
        conclusion = (
            "The bundle is retained for diagnosis, but identity/evidence closure "
            "is insufficient for comparison."
        )
    else:
        status = "COLLECTED, UNJUDGED"
        conclusion = (
            "Evidence is reviewable. No numerical or resource threshold set is "
            "attached, so this report cannot declare compatibility or parity."
        )
    return AuditReport(
        status=status,
        conclusion=conclusion,
        checks=checks,
        findings=findings,
        diagnostics=tuple(diagnostics),
    )


def _draft_only(state: LabState, **changes: object) -> LabState:
    if state.phase != "DRAFT":
        return replace(
            state,
            notice="The registered plan is immutable; reset before changing it.",
        )
    return replace(state, **changes)


def transition(state: LabState, command: str) -> LabState:
    command = command.strip().lower()
    if command == "s":
        return _draft_only(
            state,
            scenario_index=(state.scenario_index + 1) % len(SCENARIOS),
            focus_pair=1,
            notice="Scenario identity changed; the execution lane did not.",
        )
    if command == "c":
        return _draft_only(
            state,
            candidate_index=(state.candidate_index + 1) % len(CANDIDATES),
            notice="Candidate adapter changed; Polatory remains the paired reference.",
        )
    if command == "l":
        return _draft_only(
            state,
            lane_index=(state.lane_index + 1) % len(LANES),
            notice="Execution lane changed; the acceptance scenario did not.",
        )
    if command == "n":
        return _draft_only(
            state,
            repetition_index=(state.repetition_index + 1)
            % len(REPETITION_DEMOS),
            focus_pair=1,
            notice="Illustrative repetitions changed; no normative count is chosen.",
        )
    if command == "o":
        return _draft_only(
            state,
            order_seed_index=(state.order_seed_index + 1) % len(ORDER_SEEDS),
            notice="The pre-registered paired order changed.",
        )
    if command == "p":
        if state.phase != "DRAFT":
            return replace(state, notice="This plan is already registered.")
        registered = replace(
            state,
            phase="REGISTERED",
            plan_digest=compute_plan_digest(state),
            bundle_digest=None,
            evidence=(),
            report_requested=False,
            notice="Plan registered. Configuration is now immutable.",
        )
        return registered
    if command == "i":
        next_index = (state.fault_index + 1) % len(FAULTS)
        return replace(
            state,
            fault_index=next_index,
            notice=f"Next capture anomaly: {FAULTS[next_index].label}.",
        )
    if command == "x":
        if state.plan_digest is None:
            return replace(state, notice="Register the plan before capture.")
        planned = slots(state)
        if len(state.evidence) >= len(planned):
            return replace(state, notice="Every pre-registered slot is already captured.")
        slot = planned[len(state.evidence)]
        record = build_evidence(state, slot)
        evidence = state.evidence + (record,)
        phase = "COMPLETE" if len(evidence) == len(planned) else "COLLECTING"
        bundle_digest = (
            compute_bundle_digest(state.plan_digest, evidence)
            if phase == "COMPLETE"
            else None
        )
        return replace(
            state,
            phase=phase,
            evidence=evidence,
            bundle_digest=bundle_digest,
            fault_index=0,
            report_requested=False,
            focus_pair=slot.pair_index,
            notice=(
                f"Captured synthetic slot pair {slot.pair_index}, "
                f"position {slot.position}: {slot.subject}."
            ),
        )
    if command == "v":
        view_index = (state.view_index + 1) % len(VIEW_MODES)
        return replace(
            state,
            view_index=view_index,
            notice=f"Evidence view: {VIEW_MODES[view_index]}.",
        )
    if command == "j":
        focus_pair = state.focus_pair % state.repetitions + 1
        return replace(
            state,
            focus_pair=focus_pair,
            notice=f"Focused evidence pair {focus_pair}.",
        )
    if command == "a":
        report = audit(state)
        phase = "REPORTED" if state.phase == "COMPLETE" else state.phase
        return replace(
            state,
            phase=phase,
            report_requested=True,
            notice=f"Derived report state: {report.status}.",
        )
    if command == "r":
        return LabState(notice="Lab reset; no synthetic evidence was persisted.")
    return replace(state, notice=f"Unknown command: {command!r}.")
