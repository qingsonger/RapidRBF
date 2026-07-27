"""Pure state model for the throwaway kifmm adaptation decision lab.

Question: does frozen kifmm d4ca4b5 support a bounded adaptation route for
RapidRBF's canonical matrix-kernel contract, and which failed or missing gate
keeps each route out of Auto?

This module performs no I/O. Source observations and probe summaries are frozen
inputs. Counterfactual states are explicitly hypothetical.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


SOURCE_FACT = "SOURCE FACT"
IDENTITY_PASS = "IDENTITY PASS"
OBSERVED_FAIL = "OBSERVED FAIL"
PARTIAL = "PARTIAL"
MISSING = "MISSING"
COUNTERFACTUAL = "COUNTERFACTUAL"

KIFMM_REVISION = "d4ca4b52a2403e6dff0d424fdbfe1f7d595f6068"
GREEN_KERNELS_REVISION = "ed83120e5e74972fb0f21593b1f8f5047b6eefac"
RLST_REVISION = "33bd9a6339f2aa60076b74b6ed020473a81b1eb6"


@dataclass(frozen=True)
class ActionCase:
    key: str
    label: str
    channels: str
    canonical: str
    fork_route: str
    frozen_gap: str


ACTIONS = (
    ActionCase(
        key="A",
        label="A / value",
        channels="1 source value -> 1 target value",
        canonical="+phi(A*d)",
        fork_route=(
            "One scalar radial RHS; return the scalar target potential."
        ),
        frozen_gap=(
            "Multiple scalar RHS machinery exists, but no RapidRBF RBF kernel "
            "is wired into KiFMM metadata."
        ),
    ),
    ActionCase(
        key="F",
        label="F / source gradient",
        channels="Dim source-gradient weights -> 1 target value",
        canonical="fixed negative source-derivative row",
        fork_route=(
            "Transform q to w=A*q, run Dim scalar RHS, contract the matching "
            "target-gradient components, and apply the canonical minus."
        ),
        frozen_gap=(
            "ValueDeriv plus multiple RHS can express the decomposition only "
            "after a custom scalar RBF is integrated."
        ),
    ),
    ActionCase(
        key="FT",
        label="F^T / target gradient",
        channels="1 source value -> Dim target-gradient values",
        canonical="fixed positive target-gradient column",
        fork_route=(
            "Run one scalar RHS with target gradients, then apply the physical "
            "A^T output transform."
        ),
        frozen_gap=(
            "ValueDeriv supplies a three-component target gradient, but only "
            "for the hard-coded supported kernels."
        ),
    ),
    ActionCase(
        key="H",
        label="H / Hessian",
        channels="Dim source-gradient weights -> Dim target gradients",
        canonical="fixed negative physical Hessian action",
        fork_route=(
            "Transform q to w=A*q, run Dim scalar RHS, differentiate target "
            "expansions twice, contract Hessian columns, then apply -A^T."
        ),
        frozen_gap=(
            "GreenKernelEvalType has only Value and ValueDeriv; frozen KiFMM "
            "has no target-Hessian request or output path."
        ),
    ),
)


@dataclass(frozen=True)
class KernelForm:
    key: str
    label: str
    route: str
    gap: str


KERNEL_FORMS = (
    KernelForm(
        key="smooth",
        label="Required smooth contribution",
        route=(
            "A fork would add scalar radial RapidRBF kernels, use only the "
            "single-node BLAS translation, and keep equivalent/local expansion "
            "data scalar."
        ),
        gap=(
            "Frozen metadata is specialized for Laplace3d/Helmholtz3d; all "
            "required RBF family branches and derivative boundaries are absent."
        ),
    ),
    KernelForm(
        key="sp-tail",
        label="sp3/sp5/sp7/sp9 smooth tail",
        route=(
            "Rust owns the normative split and exact compact contribution; the "
            "single-node BLAS fork may evaluate only the smooth tail."
        ),
        gap=(
            "No RapidRBF split-tail implementation or branch certificate exists "
            "in frozen kifmm."
        ),
    ),
)


@dataclass(frozen=True)
class AnisotropyCase:
    key: str
    label: str


ANISOTROPIES = (
    AnisotropyCase("identity", "Identity"),
    AnisotropyCase("diagonal", "Valid diagonal"),
    AnisotropyCase("shear", "Valid nonsymmetric shear"),
)


@dataclass(frozen=True)
class LifetimeCase:
    key: str
    label: str
    contract: str
    source_fact: str


LIFETIMES = (
    LifetimeCase(
        key="operator",
        label="PreparedOperator",
        contract="Fixed source/target geometry; changing call-scoped weights.",
        source_fact=(
            "attach_charges_* clears mutable expansions and reuses one KiFMM "
            "object. Immutable concurrent sessions and proof identities are absent."
        ),
    ),
    LifetimeCase(
        key="field",
        label="PreparedField",
        contract="Fixed sources/weights; changing call-scoped target batches.",
        source_fact=(
            "Targets are part of the built tree. Changing target batches requires "
            "new tree/metadata; no bounded prepared-field shape is exposed."
        ),
    ),
)


@dataclass(frozen=True)
class EvidenceProfile:
    key: str
    label: str
    description: str
    hypothetical: bool = False


EVIDENCE_PROFILES = (
    EvidenceProfile(
        key="bounded-fork",
        label="CURRENT: bounded scalar-radial fork",
        description=(
            "Generalize kernel metadata, embed 1D/2D in 3D, add target Hessians, "
            "remove unconditional FFTW, and preserve scalar expansions."
        ),
    ),
    EvidenceProfile(
        key="frozen-as-is",
        label="OBSERVED REJECTION: frozen as-is",
        description=(
            "Use the exact d4ca4b5 source and dependency shape without the "
            "semantic, build, operational, or license fork."
        ),
    ),
    EvidenceProfile(
        key="component-shortcut",
        label="OBSERVED REJECTION: component-trait shortcut",
        description=(
            "Treat green-kernels component counts as proof that KiFMM already "
            "supports arbitrary vector kernels and canonical actions."
        ),
    ),
    EvidenceProfile(
        key="all-gates-pass",
        label="COUNTERFACTUAL ONLY: every gate closes",
        description=(
            "Assume a pinned fork passes complete semantics, certification, "
            "lifetime, operations, scale, and tier-one distribution evidence."
        ),
        hypothetical=True,
    ),
)


@dataclass(frozen=True)
class EvidenceItem:
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class GateResult:
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class Assessment:
    route: str
    ledger: tuple[EvidenceItem, ...]
    gates: tuple[GateResult, ...]
    verdict: str
    first_disqualifier: str
    conclusion: str
    hypothetical: bool


@dataclass(frozen=True)
class LabState:
    action_index: int = 0
    dimension_index: int = 2
    kernel_index: int = 0
    anisotropy_index: int = 2
    lifetime_index: int = 0
    evidence_index: int = 0
    notice: str = (
        "Review whether the bounded fork is worth retaining as forced-prototype-only."
    )

    @property
    def action(self) -> ActionCase:
        return ACTIONS[self.action_index]

    @property
    def dimension(self) -> int:
        return (1, 2, 3)[self.dimension_index]

    @property
    def kernel_form(self) -> KernelForm:
        return KERNEL_FORMS[self.kernel_index]

    @property
    def anisotropy(self) -> AnisotropyCase:
        return ANISOTROPIES[self.anisotropy_index]

    @property
    def lifetime(self) -> LifetimeCase:
        return LIFETIMES[self.lifetime_index]

    @property
    def evidence(self) -> EvidenceProfile:
        return EVIDENCE_PROFILES[self.evidence_index]


def anisotropy_label(state: LabState) -> str:
    if state.dimension == 1 and state.anisotropy.key == "shear":
        return "Shear unavailable (1D)"
    return state.anisotropy.label


def transform_detail(state: LabState) -> str:
    if state.dimension == 1 and state.anisotropy.key == "shear":
        return (
            "A nonsymmetric shear does not exist in 1D; select identity or a "
            "positive diagonal transform."
        )

    embed = (
        "Metric coordinates are zero-padded into the first "
        f"{state.dimension} axes of the frozen 3D tree. "
        if state.dimension < 3
        else "Metric coordinates use the native three axes. "
    )
    by_action = {
        "A": "Scalar weights/output need no component transform.",
        "F": "Use metric source weights A*q and a negative diagonal gradient contraction.",
        "FT": "Apply A^T to the metric target gradient.",
        "H": "Use metric source weights A*q and apply -A^T to the Hessian contraction.",
    }
    return embed + by_action[state.action.key]


def _base_ledger(state: LabState) -> tuple[EvidenceItem, ...]:
    mapping_status = (
        MISSING
        if state.dimension == 1 and state.anisotropy.key == "shear"
        else IDENTITY_PASS
    )
    mapping_detail = (
        "No 1D shear case exists."
        if mapping_status == MISSING
        else (
            "The standalone Gaussian probe matches the direct physical formula "
            "for this action/dimension/transform shape; it bypasses KiFMM."
        )
    )

    items = [
        EvidenceItem(
            "Frozen graph",
            SOURCE_FACT,
            (
                f"kifmm {KIFMM_REVISION[:7]}, resolved green-kernels "
                f"{GREEN_KERNELS_REVISION[:7]} and RLST {RLST_REVISION[:7]}; "
                "Cargo.lock is ignored."
            ),
        ),
        EvidenceItem(
            "Metric mapping",
            mapping_status,
            mapping_detail,
        ),
        EvidenceItem(
            "Dimension",
            PARTIAL if state.dimension < 3 else SOURCE_FACT,
            (
                "Frozen builder/tree are 3D; zero-padding is a tested algebraic "
                "adapter idea, not an executed KiFMM path."
                if state.dimension < 3
                else "Frozen builder and tree natively assume three coordinates."
            ),
        ),
        EvidenceItem(
            "Selected action",
            MISSING,
            state.action.frozen_gap,
        ),
        EvidenceItem(
            "Kernel form",
            MISSING,
            state.kernel_form.gap,
        ),
        EvidenceItem(
            "Prepared reuse",
            PARTIAL if state.lifetime.key == "operator" else MISSING,
            state.lifetime.source_fact,
        ),
        EvidenceItem(
            "Windows build",
            OBSERVED_FAIL,
            (
                "Rust 1.96.1/MSVC reaches kifmm-fftw-src, then Unix configure "
                "execution fails with Windows OS error 193."
            ),
        ),
    ]
    if state.evidence.key == "component-shortcut":
        items.insert(
            3,
            EvidenceItem(
                "Component seam",
                OBSERVED_FAIL,
                (
                    "KiFMM core has zero calls to domain_component_count or "
                    "range_component_count and sizes output from Value/ValueDeriv."
                ),
            ),
        )
    return tuple(items)


def _current_gates(state: LabState) -> tuple[GateResult, ...]:
    profile = state.evidence.key
    if profile == "frozen-as-is":
        semantic_status = OBSERVED_FAIL
        semantic_detail = (
            "No RapidRBF RBF metadata path, no target Hessian mode, component "
            "counts unused, and native dimension fixed at 3."
        )
    elif profile == "component-shortcut":
        semantic_status = OBSERVED_FAIL
        semantic_detail = (
            "The advertised component-count trait is not consumed by KiFMM; "
            "it cannot justify canonical vector actions."
        )
    else:
        semantic_status = MISSING
        semantic_detail = (
            "The scalar decomposition is plausible, but the fork has not executed "
            "all 16 families, four actions, dimensions, geometries, derivative "
            "boundaries, or anisotropy cases."
        )

    if profile == "bounded-fork":
        tier_status = MISSING
        tier_detail = (
            "The fork must remove/feature-gate GPL FFTW, pin the graph, select "
            "reviewed BLAS/LAPACK providers, and prove four clean hosts."
        )
    else:
        tier_status = OBSERVED_FAIL
        tier_detail = (
            "Windows build fails; FFTW is unconditionally static and GPL under "
            "ordinary terms; native BLAS/LAPACK closure is unspecified."
        )

    return (
        GateResult("Semantic closure", semantic_status, semantic_detail),
        GateResult(
            "Sound certificate",
            MISSING,
            (
                "Orders/compression tolerances and sampled L2 checks do not bound "
                "complete-batch absolute-infinity action error."
            ),
        ),
        GateResult(
            "Prepared lifetime",
            MISSING,
            (
                "Mutable clear/reattach reuse is not an immutable shared prepared "
                "handle with exclusive proof-scoped sessions and bounded retention."
            ),
        ),
        GateResult(
            "Operational control",
            MISSING,
            (
                "No cancellation/deadline polling, conservative resource lease, "
                "owned Rayon pool, or full BLAS thread accounting."
            ),
        ),
        GateResult(
            "Scale qualification",
            MISSING,
            (
                "No RapidRBF 1k->10k->100k ladder, prepared-repetition plateau, "
                "partition equivalence, or million-scale evidence."
            ),
        ),
        GateResult("Tier-one closure", tier_status, tier_detail),
    )


def _counterfactual_gates() -> tuple[GateResult, ...]:
    return tuple(
        GateResult(
            label,
            COUNTERFACTUAL,
            "Assumed closed only to test the promotion rule.",
        )
        for label in (
            "Semantic closure",
            "Sound certificate",
            "Prepared lifetime",
            "Operational control",
            "Scale qualification",
            "Tier-one closure",
        )
    )


def assess(state: LabState) -> Assessment:
    profile = state.evidence
    route = (
        f"{state.kernel_form.route} {state.action.fork_route} "
        f"{transform_detail(state)}"
    )
    ledger = _base_ledger(state)

    if profile.hypothetical:
        return Assessment(
            route=route,
            ledger=ledger,
            gates=_counterfactual_gates(),
            verdict="COUNTERFACTUAL AUTO-ELIGIBLE",
            first_disqualifier="none by assumption -- this is not observed evidence",
            conclusion=(
                "This view validates only the all-gates-conjunction rule; it "
                "cannot promote kifmm."
            ),
            hypothetical=True,
        )

    gates = _current_gates(state)
    if profile.key == "bounded-fork":
        verdict = "FORCED-PROTOTYPE-ONLY"
        first = (
            "Semantic closure: the mapping identity has not been implemented or "
            "certified in a generalized KiFMM fork."
        )
        conclusion = (
            "Retain only a bounded fork hypothesis. Do not put frozen or forked "
            "kifmm in Auto until every gate closes."
        )
    elif profile.key == "component-shortcut":
        verdict = "AUTO-INELIGIBLE"
        first = (
            "Semantic closure: source evidence falsifies the claim that KiFMM "
            "consumes arbitrary component counts."
        )
        conclusion = (
            "Reject the component-trait shortcut. Any future route must use an "
            "explicit scalar decomposition and a reviewed fork."
        )
    else:
        verdict = "AUTO-INELIGIBLE"
        first = (
            "Semantic closure: frozen kifmm lacks the required RBF/action surface; "
            "the observed Windows and license failures independently block release."
        )
        conclusion = (
            "Reject frozen-as-is for Auto. Only a separately evidenced bounded "
            "fork may remain under consideration."
        )

    return Assessment(
        route=route,
        ledger=ledger,
        gates=gates,
        verdict=verdict,
        first_disqualifier=first,
        conclusion=conclusion,
        hypothetical=False,
    )


def _cycle(index: int, size: int) -> int:
    return (index + 1) % size


def transition(state: LabState, command: str) -> LabState:
    command = command.strip().lower()
    if command == "a":
        index = _cycle(state.action_index, len(ACTIONS))
        return replace(
            state,
            action_index=index,
            notice=f"Canonical action: {ACTIONS[index].label}.",
        )
    if command == "d":
        index = _cycle(state.dimension_index, 3)
        return replace(
            state,
            dimension_index=index,
            notice=f"Physical dimension: {(1, 2, 3)[index]}D.",
        )
    if command == "f":
        index = _cycle(state.kernel_index, len(KERNEL_FORMS))
        return replace(
            state,
            kernel_index=index,
            notice=f"Kernel form: {KERNEL_FORMS[index].label}.",
        )
    if command == "x":
        index = _cycle(state.anisotropy_index, len(ANISOTROPIES))
        candidate = replace(state, anisotropy_index=index)
        return replace(
            candidate,
            notice=f"Anisotropy: {anisotropy_label(candidate)}.",
        )
    if command == "u":
        index = _cycle(state.lifetime_index, len(LIFETIMES))
        return replace(
            state,
            lifetime_index=index,
            notice=f"Prepared shape: {LIFETIMES[index].label}.",
        )
    if command == "e":
        index = _cycle(state.evidence_index, len(EVIDENCE_PROFILES))
        return replace(
            state,
            evidence_index=index,
            notice=f"Decision route: {EVIDENCE_PROFILES[index].label}.",
        )
    if command == "r":
        return LabState(notice="Lab reset to the bounded 3D/shear A case.")
    return replace(state, notice=f"Unknown command {command!r}; state unchanged.")
