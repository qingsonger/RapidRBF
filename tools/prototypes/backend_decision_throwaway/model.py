"""Pure state model for the throwaway backend candidate evidence lab.

Question: does the backend-selection model distinguish contract fit, forced
prototype eligibility, and evidence-backed Auto eligibility across canonical
actions, kernel forms, reuse shapes, scale, and tier-one platforms?

This module performs no I/O.  The terminal shell in ``tui.py`` owns interaction
and rendering so this logic can be inspected independently.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


ACTIONS = ("A", "F", "F^T", "H")
DIMENSIONS = (1, 2, 3)
PLATFORMS = (
    "Windows x86_64",
    "Linux x86_64 glibc",
    "macOS arm64",
    "macOS x86_64",
)


@dataclass(frozen=True)
class KernelCase:
    key: str
    label: str
    form: str
    coincident_derivatives_defined: bool


KERNELS = (
    KernelCase("bh2", "bh2 (c=0 boundary)", "smooth", False),
    KernelCase("bh3", "bh3 (c=0 boundary)", "smooth", False),
    KernelCase("th2", "th2 (c=0 boundary)", "smooth", True),
    KernelCase("th3", "th3 (c=0 boundary)", "smooth", True),
    KernelCase("cub", "cub", "compact", True),
    KernelCase("exp", "exp", "smooth", False),
    KernelCase("gau", "gau", "smooth", True),
    KernelCase("gc3", "gc3", "smooth", True),
    KernelCase("gc5", "gc5", "smooth", True),
    KernelCase("gc7", "gc7", "smooth", True),
    KernelCase("gc9", "gc9", "smooth", True),
    KernelCase("sph", "sph", "compact", False),
    KernelCase("sp3", "sp3", "split", False),
    KernelCase("sp5", "sp5", "split", False),
    KernelCase("sp7", "sp7", "split", False),
    KernelCase("sp9", "sp9", "split", False),
    KernelCase("th3+gau", "th3(c>0) + gau", "multi-term smooth", True),
)
ALL_FAMILY_INDICES = tuple(range(16))


@dataclass(frozen=True)
class AnisotropyCase:
    key: str
    label: str
    valid: bool


ANISOTROPY_CASES = (
    AnisotropyCase("identity", "identity", True),
    AnisotropyCase("diagonal", "positive diagonal", True),
    AnisotropyCase("rotation-scale", "rotation + scale", True),
    AnisotropyCase("shear", "nonsymmetric shear", True),
    AnisotropyCase(
        "ill-conditioned", "strongly ill-conditioned but certifiably valid", True
    ),
    AnisotropyCase("reflection", "reflection (invalid)", False),
    AnisotropyCase("singular", "singular (invalid)", False),
    AnisotropyCase("non-finite", "non-finite (invalid)", False),
)


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    scale: str
    geometry: str
    reuse: str
    origin_interactions: bool
    kernel_indices: tuple[int, ...]
    description: str


SCENARIOS = (
    Scenario(
        key="small-cross",
        label="Small cross-geometry action",
        scale="small",
        geometry="cross",
        reuse="single call",
        origin_interactions=False,
        kernel_indices=ALL_FAMILY_INDICES,
        description=(
            "A cheap deterministic action where the streaming canonical direct "
            "reference is expected to fit the declared resource lease."
        ),
    ),
    Scenario(
        key="prepared-operator",
        label="Large prepared operator",
        scale="large pair workload",
        geometry="self",
        reuse="fixed geometry / changing weights",
        origin_interactions=True,
        kernel_indices=ALL_FAMILY_INDICES,
        description=(
            "Repeated solver matvecs over fixed geometry; the selected family "
            "determines direct, compact, smooth, or split route eligibility."
        ),
    ),
    Scenario(
        key="prepared-field",
        label="Large prepared field",
        scale="large rectangular",
        geometry="cross",
        reuse="fixed sources+weights / changing targets",
        origin_interactions=False,
        kernel_indices=ALL_FAMILY_INDICES,
        description=(
            "Repeated fitted-field evaluation, including the release matrix's "
            "large-source/small-target and small-source/large-target shapes."
        ),
    ),
    Scenario(
        key="release-exp",
        label="Release exp ordinary/incremental journey",
        scale="1M release gate",
        geometry="self fit + cross evaluation",
        reuse="fit operator + repeated field evaluation",
        origin_interactions=True,
        kernel_indices=(5,),
        description=(
            "The frozen 3D exp value-only million-row ordinary and incremental "
            "journeys plus one million independent value targets."
        ),
    ),
    Scenario(
        key="release-hermite",
        label="Release Hermite composite journey",
        scale="1M release gate",
        geometry="mixed value/full-gradient",
        reuse="fit operator + repeated field evaluation",
        origin_interactions=True,
        kernel_indices=(16,),
        description=(
            "The 3D th3+gau million-row journey with heterogeneous anisotropy, "
            "value/full-gradient observations, and value+gradient targets."
        ),
    ),
)


@dataclass(frozen=True)
class EvidenceProfile:
    key: str
    label: str
    hypothetical: bool
    description: str


EVIDENCE_PROFILES = (
    EvidenceProfile(
        key="current",
        label="Current audited evidence",
        hypothetical=False,
        description=(
            "Only frozen Polatory evidence and accepted RapidRBF contracts count; "
            "no candidate adapter has been promoted."
        ),
    ),
    EvidenceProfile(
        key="scalfmm-promoted",
        label="WHAT-IF: narrow ScalFMM3 adapter passes every gate",
        hypothetical=True,
        description=(
            "Assume the pinned native adapter has sound call certificates, bounded "
            "reuse/resources, cancellation, scale parity, and tier-one packaging."
        ),
    ),
    EvidenceProfile(
        key="ferreus-promoted",
        label="WHAT-IF: Ferreus adaptation passes every gate",
        hypothetical=True,
        description=(
            "Assume Ferreus is extended across every canonical action, dimension, "
            "smooth family, certificate, scale, and tier-one lane."
        ),
    ),
    EvidenceProfile(
        key="kifmm-promoted",
        label="WHAT-IF: kifmm adaptation passes every gate",
        hypothetical=True,
        description=(
            "Assume kifmm's component seam gains every required dimension, RBF, "
            "certificate, platform, and self-contained dependency closure."
        ),
    ),
    EvidenceProfile(
        key="native-unavailable",
        label="WHAT-IF: native fallback cannot ship",
        hypothetical=True,
        description=(
            "Assume licensing or runtime-closure evidence makes ScalFMM3 "
            "ineligible for official artifacts."
        ),
    ),
)


@dataclass(frozen=True)
class Candidate:
    key: str
    label: str
    role: str
    comparison: tuple[tuple[str, str], ...]


CANDIDATES = (
    Candidate(
        key="direct",
        label="Streaming direct",
        role="Rust-owned reference and final fallback",
        comparison=(
            (
                "Accuracy",
                "Zero backend-approximation charge against the canonical floating reference.",
            ),
            (
                "Calibration",
                "None; operation-level floating acceptance still applies.",
            ),
            (
                "Reuse",
                "Geometry snapshots and bounded tiling; no hidden semantic cache.",
            ),
            (
                "Throughput",
                "Quadratic pair work; useful for small cases and capacity-admitted fallback.",
            ),
            (
                "Memory",
                "Deterministically tileable under a declared session lease.",
            ),
            (
                "Safety",
                "Pure Rust target with atomic staged output.",
            ),
            (
                "License/build",
                "RapidRBF-owned; lowest packaging risk on every tier-one platform.",
            ),
        ),
    ),
    Candidate(
        key="neighbor",
        label="Exact compact neighbor",
        role="Rust-owned compact contribution",
        comparison=(
            (
                "Accuracy",
                "Canonical strict support predicate; exact zero at/outside support.",
            ),
            (
                "Calibration",
                "No approximate calibration; index is only a conservative candidate generator.",
            ),
            (
                "Reuse",
                "Prepared metric-space index may be reused under proof-scoped geometry identity.",
            ),
            (
                "Throughput",
                "Expected to scale with candidate neighborhoods; boundary/adversarial data need probes.",
            ),
            (
                "Memory",
                "Index plus bounded candidate/output buffers; exact peak is unmeasured.",
            ),
            (
                "Safety",
                "Pure Rust target; must preserve membership and atomic failure.",
            ),
            (
                "License/build",
                "RapidRBF-owned plus a permissive exact-radius index candidate.",
            ),
        ),
    ),
    Candidate(
        key="ferreus",
        label="Ferreus adaptation",
        role="Rust-first RBF-specific forced spike",
        comparison=(
            (
                "Accuracy",
                "Scalar kernel seam; no audited sound certificate for all four RapidRBF actions.",
            ),
            (
                "Calibration",
                "Must replace sampling-as-proof with a conservative bound and deterministic refinement.",
            ),
            (
                "Reuse",
                "Prepared operator/field mapping and proof identity are unproven.",
            ),
            (
                "Throughput",
                "Promising for large smooth work; no accepted RapidRBF scale or parity run.",
            ),
            (
                "Memory",
                "Translation/operator/scratch bounds are not measured under RapidRBF leases.",
            ),
            (
                "Safety",
                "Rust-first implementation reduces native boundary risk.",
            ),
            (
                "License/build",
                "MIT with existing tier-one CI signals; those jobs are not RapidRBF evidence.",
            ),
        ),
    ),
    Candidate(
        key="kifmm",
        label="kifmm adaptation",
        role="Component-aware architectural spike",
        comparison=(
            (
                "Accuracy",
                "Component-aware seam is promising; no RapidRBF RBF/action certificate exists.",
            ),
            (
                "Calibration",
                "Must produce a sound complete-call bound and deterministic refinement.",
            ),
            (
                "Reuse",
                "Prepared operator/field mapping and proof identity are unproven.",
            ),
            (
                "Throughput",
                "No accepted RapidRBF scale or Polatory-parity execution.",
            ),
            (
                "Memory",
                "Translation/operator/scratch bounds are unmeasured under RapidRBF leases.",
            ),
            (
                "Safety",
                "Rust API still carries native FFTW plus BLAS/LAPACK integration risk.",
            ),
            (
                "License/build",
                "BSD-3-Clause core; currently 3D, Unix-only, and native-dependent.",
            ),
        ),
    ),
    Candidate(
        key="scalfmm-cabi",
        label="ScalFMM3 narrow C ABI",
        role="Native parity fallback candidate",
        comparison=(
            (
                "Accuracy",
                "Polatory supplies inherited behavior evidence, not a RapidRBF sound call certificate.",
            ),
            (
                "Calibration",
                "Legacy deterministic sampling may tune a route but cannot certify public success.",
            ),
            (
                "Reuse",
                "Opaque prepared handles are plausible; retained trees/interpolators need measurement.",
            ),
            (
                "Throughput",
                "Only candidate with frozen Polatory large-smooth lineage; wrapper parity is unmeasured.",
            ),
            (
                "Memory",
                "Native trees/operators/caches need conservative leases and repeated-call high-water probes.",
            ),
            (
                "Safety",
                "C++ exceptions, lengths, lifetimes, cancellation, threads, and destruction must be contained.",
            ),
            (
                "License/build",
                "CeCILL-C fork plus OpenMP and configuration-dependent FFTW/BLAS closure.",
            ),
        ),
    ),
    Candidate(
        key="hybrid",
        label="Rust-owned hybrid",
        role="Accepted composition shell; shipping strategy remains unresolved",
        comparison=(
            (
                "Accuracy",
                "Owns the complete error ledger, refinement order, composition, and direct fallback.",
            ),
            (
                "Calibration",
                "May sample only for route tuning; adapter bounds plus Rust allowances certify the call.",
            ),
            (
                "Reuse",
                "Explicit immutable PreparedOperator/PreparedField plus exclusive execution sessions.",
            ),
            (
                "Throughput",
                "Selects direct, neighbor, and a promoted smooth adapter by capability and resource lease.",
            ),
            (
                "Memory",
                "One hierarchical governor charges persistent and session state across all components.",
            ),
            (
                "Safety",
                "Sealed private adapters; staged results and normalized failures contain native risk.",
            ),
            (
                "License/build",
                "Pure-Rust shell; official artifact risk equals the promoted native component's closure.",
            ),
        ),
    ),
)


@dataclass(frozen=True)
class LabState:
    scenario_index: int = 1
    action_index: int = 0
    dimension_index: int = 2
    platform_index: int = 0
    evidence_index: int = 0
    candidate_index: int = 5
    kernel_index: int = 5
    anisotropy_index: int = 0

    @property
    def scenario(self) -> Scenario:
        return SCENARIOS[self.scenario_index]

    @property
    def action(self) -> str:
        return ACTIONS[self.action_index]

    @property
    def kernel(self) -> KernelCase:
        allowed = self.scenario.kernel_indices
        return KERNELS[allowed[self.kernel_index % len(allowed)]]

    @property
    def anisotropy(self) -> AnisotropyCase:
        return ANISOTROPY_CASES[self.anisotropy_index]

    @property
    def dimension(self) -> int:
        return DIMENSIONS[self.dimension_index]

    @property
    def platform(self) -> str:
        return PLATFORMS[self.platform_index]

    @property
    def evidence(self) -> EvidenceProfile:
        return EVIDENCE_PROFILES[self.evidence_index]

    @property
    def candidate(self) -> Candidate:
        return CANDIDATES[self.candidate_index]


@dataclass(frozen=True)
class Assessment:
    candidate: Candidate
    route_fit: str
    use: str
    evidence: str
    blockers: tuple[str, ...]


def _cycle(value: int, size: int) -> int:
    return (value + 1) % size


def transition(state: LabState, command: str) -> LabState:
    """Return the next state for one TUI command."""

    command = command.strip().lower()
    if command == "n":
        return replace(
            state,
            scenario_index=_cycle(state.scenario_index, len(SCENARIOS)),
            kernel_index=0,
        )
    if command == "a":
        return replace(state, action_index=_cycle(state.action_index, len(ACTIONS)))
    if command == "f":
        return replace(
            state,
            kernel_index=_cycle(
                state.kernel_index, len(state.scenario.kernel_indices)
            ),
        )
    if command == "x":
        return replace(
            state,
            anisotropy_index=_cycle(
                state.anisotropy_index, len(ANISOTROPY_CASES)
            ),
        )
    if command == "d":
        return replace(
            state, dimension_index=_cycle(state.dimension_index, len(DIMENSIONS))
        )
    if command == "p":
        return replace(
            state, platform_index=_cycle(state.platform_index, len(PLATFORMS))
        )
    if command == "e":
        return replace(
            state,
            evidence_index=_cycle(state.evidence_index, len(EVIDENCE_PROFILES)),
        )
    if command == "c":
        return replace(
            state, candidate_index=_cycle(state.candidate_index, len(CANDIDATES))
        )
    if command == "r":
        return LabState()
    return state


def semantic_gate(state: LabState) -> str | None:
    """Return a stable pre-adapter outcome, if the selected request has one."""

    if not state.anisotropy.valid:
        return (
            f"InvalidRequest: {state.anisotropy.label} is rejected by Rust-owned "
            "validation before adapter selection."
        )
    if (
        state.scenario.origin_interactions
        and state.action != "A"
        and not state.kernel.coincident_derivatives_defined
    ):
        return (
            f"UndefinedDerivative: {state.kernel.label} has no unique finite "
            f"coincident derivative for action {state.action}."
        )
    return None


def assess(candidate: Candidate, state: LabState) -> Assessment:
    """Assess one candidate without converting hypotheses into evidence."""

    scenario = state.scenario
    profile = state.evidence.key
    kernel_form = state.kernel.form
    gate = semantic_gate(state)

    if gate is not None:
        if candidate.key == "hybrid":
            return Assessment(
                candidate,
                "complete pre-adapter semantic gate",
                gate,
                "accepted numerical contract",
                (),
            )
        return Assessment(
            candidate,
            "not reached",
            "must not be invoked",
            "Rust-owned validation/derivative semantics",
            (gate,),
        )

    if candidate.key == "direct":
        if scenario.scale == "small":
            return Assessment(
                candidate,
                "complete",
                "canonical reference / Auto fallback",
                "accepted contract; implementation evidence still future work",
                (),
            )
        return Assessment(
            candidate,
            "complete but capacity-gated",
            "final fallback only when its full lease is admitted",
            "accepted contract; large-scale throughput is not assumed",
            (
                "quadratic pair work at this scale",
                "must preflight time, scratch, and cancellation quantum",
            ),
        )

    if candidate.key == "neighbor":
        if kernel_form == "compact":
            return Assessment(
                candidate,
                "complete",
                "eligible route design for compact kernels",
                "accepted semantics; implementation/scale probes missing",
                (
                    "exact f64 support-boundary fixtures",
                    "adversarial density and repeated-index resource measurements",
                ),
            )
        if kernel_form == "split":
            return Assessment(
                candidate,
                "partial: compact contribution only",
                "component inside the hybrid planner",
                "accepted composition semantics; measurements missing",
                ("requires a separately certified smooth contribution",),
            )
        return Assessment(
            candidate,
            "none",
            "ineligible for this kernel form",
            "not applicable",
            ("no finite strict-support neighborhood exists",),
        )

    if candidate.key == "ferreus":
        if profile == "ferreus-promoted":
            if kernel_form == "compact":
                return Assessment(
                    candidate,
                    "unnecessary",
                    "not selected; exact neighbor route is deeper and cheaper",
                    "counterfactual promotion does not override route shape",
                    (),
                )
            return Assessment(
                candidate,
                "complete for smooth contribution",
                "Auto-eligible inside the hybrid planner",
                "COUNTERFACTUAL: all promotion gates assumed passed",
                (),
            )
        partial = state.action == "A" and kernel_form != "compact"
        return Assessment(
            candidate,
            "scalar-spike-shaped" if partial else "no complete action seam",
            "forced prototype only",
            "source audit only; no RapidRBF candidate execution",
            (
                "component permutation/sign handling for A/F/F^T/H and anisotropy",
                "exact RapidRBF conventions for all 16 families in dimensions 1-3",
                "sound call-scoped certificate and deterministic refinement",
                "prepared reuse, cancellation, resource, and million-scale evidence",
                "all four tier-one packaging lanes",
            ),
        )

    if candidate.key == "kifmm":
        if profile == "kifmm-promoted":
            if kernel_form == "compact":
                return Assessment(
                    candidate,
                    "unnecessary",
                    "not selected; use exact neighbor",
                    "counterfactual promotion does not override route shape",
                    (),
                )
            return Assessment(
                candidate,
                "complete for smooth contribution",
                "Auto-eligible inside the Rust-owned planner",
                "COUNTERFACTUAL: every promotion gate assumed passed",
                (),
            )
        partial = state.dimension == 3 and kernel_form != "compact"
        return Assessment(
            candidate,
            "component-spike-shaped" if partial else "none for this declared shape",
            "forced prototype only",
            "source audit only; no RapidRBF candidate execution",
            (
                "RapidRBF RBF kernels and all four action conventions",
                "1D/2D support and Windows support",
                "sound call-scoped certificate and deterministic refinement",
                "prepared reuse, cancellation, resource, and million-scale evidence",
                "self-contained FFTW/BLAS-free or approved runtime closure",
            ),
        )

    if candidate.key == "scalfmm-cabi":
        if profile == "native-unavailable":
            return Assessment(
                candidate,
                "native engine lineage exists",
                "ineligible for official artifacts",
                "COUNTERFACTUAL: release closure failed",
                ("licensing or runtime closure blocks distribution",),
            )
        if kernel_form == "compact":
            return Assessment(
                candidate,
                "none",
                "ineligible; use exact neighbor",
                "accepted route split",
                (),
            )
        fit = (
            "partial: smooth contribution only"
            if kernel_form == "split"
            else "complete native action lineage"
        )
        if profile == "scalfmm-promoted":
            return Assessment(
                candidate,
                fit,
                "Auto-eligible inside the hybrid planner",
                "COUNTERFACTUAL: every wrapper promotion gate assumed passed",
                (),
            )
        return Assessment(
            candidate,
            fit,
            "forced prototype only",
            "frozen Polatory lineage; RapidRBF wrapper evidence missing",
            (
                "versioned C ABI build/load/failure/destruction tests",
                "sound call certificate beyond sampling calibration",
                "bounded prepared reuse, cancellation, threads, and native resources",
                "differential and repeated-evaluation runs",
                "million-scale parity and four tier-one runtime/license closure",
            ),
        )

    # The hybrid is the accepted Rust-owned composition shell, not an adapter.
    if kernel_form == "compact":
        return Assessment(
            candidate,
            "complete composition",
            "direct + exact neighbor route shape",
            "accepted architecture; component implementation evidence missing",
            ("promote the Rust direct and neighbor implementations",),
        )
    if scenario.scale == "small":
        return Assessment(
            candidate,
            "complete composition",
            "direct route with no approximate adapter required",
            "accepted architecture; implementation evidence missing",
            (),
        )
    if profile == "scalfmm-promoted":
        return Assessment(
            candidate,
            "complete composition",
            "technically admissible with the pinned native smooth adapter",
            "COUNTERFACTUAL: native adapter promotion assumed",
            (),
        )
    if profile == "ferreus-promoted":
        return Assessment(
            candidate,
            "complete composition",
            "technically admissible with the promoted Ferreus adaptation",
            "COUNTERFACTUAL: Ferreus promotion assumed",
            (),
        )
    if profile == "kifmm-promoted":
        return Assessment(
            candidate,
            "complete composition",
            "technically admissible with the promoted kifmm adaptation",
            "COUNTERFACTUAL: kifmm promotion assumed",
            (),
        )
    if profile == "native-unavailable":
        return Assessment(
            candidate,
            "contract-complete but no scalable smooth component",
            "release blocked for this workload",
            "COUNTERFACTUAL: native route unavailable; pure-Rust route unpromoted",
            (
                "direct route cannot be presumed capacity-admissible",
                "no smooth approximate adapter has passed promotion",
            ),
        )
    return Assessment(
        candidate,
        "contract-complete shell; smooth route evidence-blocked",
        "forced probes only; no large-smooth adapter may enter Auto",
        "accepted architecture plus inherited/audit evidence only",
        (
            "compare and promote a concrete smooth adapter",
            "retain direct fallback and exact neighbor independently",
            "prove the outer certificate, resource governor, and failure normalization",
        ),
    )


def assessments(state: LabState) -> tuple[Assessment, ...]:
    return tuple(assess(candidate, state) for candidate in CANDIDATES)


def recommendation(state: LabState) -> str:
    """Return the route conclusion implied by the current state."""

    scenario = state.scenario
    profile = state.evidence.key
    kernel_form = state.kernel.form
    gate = semantic_gate(state)

    if gate is not None:
        return f"SEMANTIC GATE -- {gate} No backend comparison is reached."
    if scenario.scale == "small":
        return (
            "ADMISSIBLE ROUTE -- canonical streaming direct fits this scenario. "
            "This does not choose the large-smooth shipping strategy."
        )
    if kernel_form == "compact":
        return (
            "ADMISSIBLE ROUTE SHAPE -- exact compact neighbor plus capacity-admitted "
            "streaming direct. Implementation and scale evidence are still missing."
        )
    if profile == "scalfmm-promoted":
        return (
            "COUNTERFACTUAL ADMISSIBLE -- the pinned ScalFMM3 adapter could supply "
            "the smooth contribution. Comparable preference evidence would still "
            "be needed to call it the winner."
        )
    if profile == "ferreus-promoted":
        return (
            "COUNTERFACTUAL ADMISSIBLE -- the promoted Ferreus adaptation could "
            "supply the smooth contribution without changing the planner contract."
        )
    if profile == "kifmm-promoted":
        return (
            "COUNTERFACTUAL ADMISSIBLE -- the promoted kifmm adaptation could "
            "supply the smooth contribution without changing the planner contract."
        )
    if profile == "native-unavailable":
        return (
            "EVIDENCE-BLOCKED -- no scalable smooth route is qualified. Official "
            "v1 remains blocked until a concrete Rust candidate is promoted or "
            "the destination is explicitly narrowed."
        )
    return (
        "UNRESOLVED -- the Rust-owned composition shell is fixed, but no concrete "
        "large-smooth adapter qualifies for Auto and current evidence cannot rank "
        "ScalFMM3, Ferreus, and kifmm on comparable terms."
    )


def required_probe_groups(state: LabState) -> tuple[str, ...]:
    """Return the evidence groups that remain decision-relevant."""

    common = (
        "KRN.CENSUS/KRN.ANISOTROPY: all 16 families x 1D-3D x legal A/F/F^T/H",
        "requested-accuracy calibration plus a sound complete-batch certificate against direct",
        "OPR.SHAPE/TRANSITION: PreparedOperator and PreparedField at 1k-10k, including crossover triplets",
        "wall/CPU, peak RSS, scratch, cache, configured/effective/max-live threads, and cancellation",
        "OPR.STRESS at 10k/100k before immutable 1M promotion; never exploratory 1M runs",
        "Windows x86_64, Linux x86_64 glibc, macOS arm64, and macOS x86_64 clean-host closure",
    )
    gate = semantic_gate(state)
    if gate is not None:
        return (
            "below/at/above semantic boundary fixtures with stable category and index",
            "prove validation happens before adapter selection and leaves prepared state reusable",
        )
    if state.kernel.form == "compact":
        return (
            "strict support below/equal/above boundary triplets and signed-zero coordinates",
            "candidate over-inclusion without omission across adversarial neighborhood density",
            "fixed-geometry reuse, deterministic accumulation, peak RSS, and thread lanes",
        )
    return common
