"""Pure state model for the throwaway Ferreus adaptation decision lab.

Question: does the frozen Ferreus d0442ee evidence support a safe scalar-BBFMM
adaptation for RapidRBF's four canonical matrix-kernel actions, and which
missing or failed promotion gate keeps that adaptation out of Auto?

This module performs no I/O. The observed probe summaries are frozen inputs;
the counterfactual view is deliberately hypothetical.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


SOURCE_FACT = "SOURCE FACT"
OBSERVED_PASS = "OBSERVED PASS"
OBSERVED_SUPPORT = "OBSERVED SUPPORT"
OBSERVED_FAIL = "OBSERVED FAIL"
MISSING = "MISSING"
COUNTERFACTUAL = "COUNTERFACTUAL"

FERREUS_REVISION = "d0442ee978668386f6ccbeec866bfa52fcc4484f"


@dataclass(frozen=True)
class ActionCase:
    key: str
    label: str
    channels: str
    canonical: str
    probe_status: str
    adaptation: str


ACTIONS = (
    ActionCase(
        key="A",
        label="A / value",
        channels="1 source value -> 1 target value",
        canonical="+phi(A*d)",
        probe_status=OBSERVED_SUPPORT,
        adaptation=(
            "Use Ferreus' scalar kernel and scalar local expansion without a "
            "component-valued M2L shortcut."
        ),
    ),
    ActionCase(
        key="F",
        label="F / source gradient",
        channels="Dim source-gradient weights -> 1 target value",
        canonical="fixed negative source-derivative row",
        probe_status=OBSERVED_SUPPORT,
        adaptation=(
            "Run Dim scalar right-hand sides using metric weights A*q, then "
            "contract target gradients diagonally and apply the canonical "
            "external minus."
        ),
    ),
    ActionCase(
        key="FT",
        label="F^T / target gradient",
        channels="1 source value -> Dim target-gradient values",
        canonical="fixed positive target-gradient column",
        probe_status=OBSERVED_SUPPORT,
        adaptation=(
            "Use scalar weights and evaluate_with_gradients, then apply the "
            "physical A^T output transform."
        ),
    ),
    ActionCase(
        key="H",
        label="H / Hessian",
        channels="Dim source-gradient weights -> Dim target gradients",
        canonical="fixed negative physical Hessian action",
        probe_status=OBSERVED_SUPPORT,
        adaptation=(
            "A throwaway fork differentiates scalar local expansions twice and "
            "contracts Dim scalar right-hand sides; component kernels never "
            "enter M2L."
        ),
    ),
)


@dataclass(frozen=True)
class KernelCase:
    key: str
    label: str
    route: str
    gap: str


KERNELS = (
    KernelCase(
        key="smooth",
        label="Required smooth contribution",
        route=(
            "Ferreus may supply only the smooth contribution; the frozen "
            "Gaussian/transformed-coordinate probe exercises the low-level "
            "scalar BBFMM seam."
        ),
        gap=(
            "The required smooth-family census and exact RapidRBF branch and "
            "derivative conventions are incomplete."
        ),
    ),
    KernelCase(
        key="sp-tail",
        label="sp3/sp5/sp7/sp9 smooth tail",
        route=(
            "Rust owns the canonical split; exact-neighbor owns the compact "
            "part and a Ferreus adapter may supply only the smooth tail."
        ),
        gap=(
            "Ferreus' full spheroidal forms are not evidence for RapidRBF's "
            "normative compact-plus-smooth split."
        ),
    ),
)


@dataclass(frozen=True)
class GeometryCase:
    key: str
    label: str
    contract: str
    probe_shape: str


GEOMETRIES = (
    GeometryCase(
        key="self",
        label="Self geometry",
        contract=(
            "Source and target point sets alias; canonical self interactions "
            "remain explicit, including A/H symmetry and F/F^T transpose "
            "semantics."
        ),
        probe_shape="128 sources / 128 self targets",
    ),
    GeometryCase(
        key="cross",
        label="Cross geometry",
        contract="Source and target point sets are independent and rectangular.",
        probe_shape="128 sources / 83 cross targets",
    ),
)


@dataclass(frozen=True)
class AnisotropyCase:
    key: str
    label: str


ANISOTROPIES = (
    AnisotropyCase(
        key="identity",
        label="Identity",
    ),
    AnisotropyCase(
        key="diagonal",
        label="Valid diagonal",
    ),
    AnisotropyCase(
        key="shear",
        label="Valid nonsymmetric shear",
    ),
)


@dataclass(frozen=True)
class LifetimeCase:
    key: str
    label: str
    contract: str
    observed: str


LIFETIMES = (
    LifetimeCase(
        key="operator",
        label="PreparedOperator",
        contract="Fixed source/target geometry; changing call-scoped weights.",
        observed=(
            "Sequential geometry reuse is partial; immutable concurrent "
            "sessions, proof identity, and resource bounds are missing."
        ),
    ),
    LifetimeCase(
        key="field",
        label="PreparedField",
        contract="Fixed sources/weights; changing call-scoped target batches.",
        observed=(
            "Sequential field reuse is partial; immutable concurrent sessions, "
            "partition evidence, and retained-memory bounds are missing."
        ),
    ),
)


@dataclass(frozen=True)
class EvidenceProfile:
    key: str
    label: str
    description: str
    hypothetical: bool


EVIDENCE_PROFILES = (
    EvidenceProfile(
        key="safe-scalar-lift",
        label="CURRENT: safe scalar-lift evidence",
        description=(
            "Use scalar M2L/local expansions, external component transforms, "
            "and only the frozen source audit and Gaussian/transform probes."
        ),
        hypothetical=False,
    ),
    EvidenceProfile(
        key="unsafe-component-shortcut",
        label="OBSERVED REJECTION: component shortcut",
        description=(
            "Pretend signed/permuted scalar M2L offsets also transform vector "
            "components. The actual F/H shortcut probes falsify this route."
        ),
        hypothetical=False,
    ),
    EvidenceProfile(
        key="all-gates-pass",
        label="COUNTERFACTUAL ONLY: every gate closes",
        description=(
            "Assume a fork passes the complete semantic, certificate, lifetime, "
            "operational, scale, and tier-one evidence path."
        ),
        hypothetical=True,
    ),
)


@dataclass(frozen=True)
class ProbeRow:
    """Frozen row summary copied from the companion observation artifact."""

    dimension: int
    geometry: str
    near_control_max: str
    far_a: str
    far_ft: str
    far_f_radial: str
    far_f_component: str
    far_h_component: str
    near_h_safe: str
    far_h_safe: str
    far_h_safe_relative_l2: str


PROBE_ROWS = (
    ProbeRow(
        1,
        "cross",
        "5.773159728050814e-15",
        "1.11503408595226e-6",
        "4.948867313903094e-5",
        "7.964282082800755e-6",
        "1.0426441986466783",
        "7.2272609877156",
        "2.602085e-17",
        "5.141875e-6",
        "9.378082e-5",
    ),
    ProbeRow(
        1,
        "self",
        "7.771561172376096e-15",
        "1.1413812117666566e-6",
        "1.2310633279155603e-4",
        "2.4563247802866783e-5",
        "1.0522367567775666",
        "6.306803972941173",
        "2.688821e-17",
        "7.601615e-6",
        "1.057881e-4",
    ),
    ProbeRow(
        2,
        "cross",
        "5.773159728050814e-15",
        "3.3470678775238127e-6",
        "6.822284576335491e-5",
        "1.02578862648528e-5",
        "6.85187942842204",
        "7.375306246275892",
        "2.211772e-17",
        "9.713136e-6",
        "2.569347e-4",
    ),
    ProbeRow(
        2,
        "self",
        "7.105427357601002e-15",
        "4.2364467345290535e-6",
        "3.306160658285151e-4",
        "2.6286988686896606e-5",
        "6.892581470947053",
        "8.657643970770103",
        "2.168404e-17",
        "1.204804e-5",
        "2.503914e-4",
    ),
    ProbeRow(
        3,
        "cross",
        "9.769962616701378e-15",
        "1.5772184429607705e-6",
        "1.589476999628303e-4",
        "4.893211298861999e-5",
        "9.52100754872272",
        "15.065703042324033",
        "2.081668e-17",
        "1.951370e-5",
        "1.590488e-4",
    ),
    ProbeRow(
        3,
        "self",
        "1.2434497875801753e-14",
        "3.503630720436135e-6",
        "1.0298927839846872e-4",
        "2.6757503898244828e-5",
        "10.3755590606318",
        "14.806832793326846",
        "2.775558e-17",
        "2.548270e-5",
        "1.872415e-4",
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
    geometry_index: int = 1
    anisotropy_index: int = 2
    lifetime_index: int = 0
    evidence_index: int = 0
    notice: str = (
        "Current evidence is candidate-specific support/falsification, not an "
        "Auto promotion record."
    )

    @property
    def action(self) -> ActionCase:
        return ACTIONS[self.action_index]

    @property
    def dimension(self) -> int:
        return (1, 2, 3)[self.dimension_index]

    @property
    def kernel(self) -> KernelCase:
        return KERNELS[self.kernel_index]

    @property
    def geometry(self) -> GeometryCase:
        return GEOMETRIES[self.geometry_index]

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
    """Describe the selected transform without inventing a 1D shear."""

    if state.dimension == 1 and state.anisotropy.key == "shear":
        return "Shear unavailable (1D)"
    return state.anisotropy.label


def anisotropy_detail(state: LabState) -> str:
    """Return the action-specific coordinate/component transformation."""

    action = state.action.key
    transform = state.anisotropy.key
    if state.dimension == 1 and transform == "shear":
        return (
            "A nonsymmetric shear does not exist in 1D; choose identity or a "
            "valid diagonal transform."
        )

    if transform == "identity":
        details = {
            "A": "Use u=x-origin; scalar weights and outputs are unchanged.",
            "F": (
                "Use u=x-origin; source-vector bases coincide, then apply the "
                "canonical external minus after the diagonal contraction."
            ),
            "FT": (
                "Use u=x-origin and scalar source weights; the metric target "
                "gradient is already physical."
            ),
            "H": (
                "Use u=x-origin; source and target component bases coincide, "
                "with the canonical negative Hessian action."
            ),
        }
        return details[action]

    details = {
        "A": (
            "Use u=A*(x-origin); scalar source weights and target values are "
            "unchanged."
        ),
        "F": (
            "Use u=A*(x-origin) and metric source weights A*q; the target is "
            "scalar, then the canonical external minus is applied."
        ),
        "FT": (
            "Use u=A*(x-origin) and scalar source weights; apply A^T to the "
            "metric target gradient."
        ),
        "H": (
            "Use u=A*(x-origin), metric source weights A*q, and A^T on the "
            "target contraction, with the canonical negative sign."
        ),
    }
    return details[action]


def recorded_probe_axes(state: LabState) -> str:
    """Name the actual frozen transform/family behind a displayed row."""

    transform = "1D diagonal" if state.dimension == 1 else "nonsymmetric shear"
    suffix = " / uniform tree" if state.action.key == "H" else ""
    return f"Gaussian / {transform}{suffix}"


def probe_applicability(state: LabState) -> tuple[bool, str]:
    """Say whether a frozen row matches all selectable evidence axes."""

    if state.kernel.key != "smooth":
        return (
            False,
            "No sp* smooth-tail row was run; the frozen rows are Gaussian "
            "smooth-kernel observations only.",
        )
    if state.dimension == 1:
        matches_transform = state.anisotropy.key == "diagonal"
    else:
        matches_transform = state.anisotropy.key == "shear"
    if not matches_transform:
        return (
            False,
            "No recorded row matches this transform; the frozen corpus uses "
            "1D diagonal scaling and 2D/3D nonsymmetric shear.",
        )
    return (
        True,
        "The selected form and transform match the frozen Gaussian probe axes.",
    )


def probe_row(state: LabState) -> ProbeRow:
    """Return the exact frozen far/near row for the selected case."""

    return next(
        row
        for row in PROBE_ROWS
        if row.dimension == state.dimension
        and row.geometry == state.geometry.key
    )


def _action_probe_detail(state: LabState) -> str:
    row = probe_row(state)
    if state.action.key == "A":
        return (
            f"{state.dimension}D/{state.geometry.key} far A error={row.far_a}; "
            "support only, not acceptance"
        )
    if state.action.key == "F":
        return (
            f"{state.dimension}D/{state.geometry.key} radial multi-RHS "
            f"unsigned-contraction error={row.far_f_radial}; the canonical "
            "external minus was not exercised"
        )
    if state.action.key == "FT":
        return (
            f"{state.dimension}D/{state.geometry.key} far F^T "
            f"error={row.far_ft}; support only, not acceptance"
        )
    return (
        f"Separate 96-source uniform-tree fork {state.dimension}D/"
        f"{state.geometry.key} far H max-abs={row.far_h_safe}, "
        f"relative-L2={row.far_h_safe_relative_l2}; support only. "
        f"Rejected component-H shortcut error={row.far_h_component}"
    )


def _ledger(state: LabState) -> tuple[EvidenceItem, ...]:
    action = state.action
    row = probe_row(state)
    applicable, applicability_detail = probe_applicability(state)
    if action.key == "H":
        recorded_control = (
            f"Separate Hessian fork {state.dimension}D/{state.geometry.key} "
            f"near-control max={row.near_h_safe}; 96 sources / "
            f"{96 if state.geometry.key == 'self' else 57} targets."
        )
    else:
        recorded_control = (
            f"{recorded_probe_axes(state)} {state.dimension}D/"
            f"{state.geometry.key} "
            f"near-control max={row.near_control_max}; "
            f"{state.geometry.probe_shape}."
        )

    if state.evidence.key == "unsafe-component-shortcut":
        control_status = OBSERVED_SUPPORT
        control_detail = (
            recorded_control
            + " This is a frozen counterexample control, independent of "
            "unobserved selected axes."
        )
        selected_item = EvidenceItem(
            "Component shortcut",
            OBSERVED_FAIL,
            (
                "Frozen Gaussian counterexamples reject scalar component "
                f"symmetry: far F/H errors={row.far_f_component}/"
                f"{row.far_h_component}."
            ),
        )
    elif applicable:
        control_status = OBSERVED_SUPPORT
        control_detail = recorded_control
        selected_item = EvidenceItem(
            f"Selected {action.key}",
            action.probe_status,
            _action_probe_detail(state),
        )
    else:
        control_status = MISSING
        control_detail = applicability_detail
        selected_item = EvidenceItem(
            f"Selected {action.key}",
            MISSING,
            (
                applicability_detail
                + " The displayed frozen row is context, not selected-case "
                "evidence."
            ),
        )

    return (
        EvidenceItem(
            "Frozen source",
            SOURCE_FACT,
            (
                f"Ferreus {FERREUS_REVISION[:7]}; 1D-3D scalar kernels and "
                "target gradients exist. The public API has no Hessian output; "
                "the recorded throwaway fork adds a uniform-tree path."
            ),
        ),
        EvidenceItem(
            "Toolchain",
            OBSERVED_PASS,
            "Windows rustc 1.85 passed 1 BBFMM unit test and 3 doctests.",
        ),
        EvidenceItem(
            "Current stable",
            OBSERVED_FAIL,
            "Windows rustc 1.96 fails in locked transitive spindle 0.2.5.",
        ),
        EvidenceItem(
            "Probe control",
            control_status,
            control_detail,
        ),
        selected_item,
        EvidenceItem(
            "Promotion evidence",
            MISSING,
            (
                "Sound certificate, cancellation/resource/determinism, scale, "
                "and accepted four-host closure are absent."
            ),
        ),
    )


def _current_gates(state: LabState) -> tuple[GateResult, ...]:
    if state.evidence.key == "unsafe-component-shortcut":
        row = probe_row(state)
        semantic = GateResult(
            "Semantic closure",
            OBSERVED_FAIL,
            (
                "Scalar signed/permuted M2L offsets do not transform vector "
                f"components; frozen counterexample far F/H errors are "
                f"{row.far_f_component}/{row.far_h_component}."
            ),
        )
    else:
        action_gaps = []
        if state.action.key == "H":
            action_gaps.append(
                "H support is Gaussian/uniform only; adaptive W-list/M2P and "
                "required families remain absent."
            )
        if state.action.key == "F":
            action_gaps.append(
                "The radial probe did not exercise F's canonical external minus."
            )
        applicable, applicability_detail = probe_applicability(state)
        if not applicable:
            action_gaps.append(applicability_detail)
        action_gap = " ".join(action_gaps)
        if action_gap:
            action_gap += " "
        semantic = GateResult(
            "Semantic closure",
            MISSING,
            (
                action_gap
                + state.kernel.gap
                + " Full family/action census, derivative boundaries, and "
                "rotation-scale/ill-conditioned anisotropy evidence are absent."
            ),
        )

    return (
        semantic,
        GateResult(
            "Sound certificate",
            MISSING,
            (
                "Ferreus epsilon controls relative Frobenius M2L compression; "
                "it is not a call-scoped absolute-infinity error bound."
            ),
        ),
        GateResult(
            "Prepared lifetime",
            MISSING,
            state.lifetime.observed,
        ),
        GateResult(
            "Operational control",
            MISSING,
            (
                "No bounded cancellation, conservative resource lease, complete "
                "thread accounting, or deterministic accumulation evidence."
            ),
        ),
        GateResult(
            "Scale qualification",
            MISSING,
            (
                (
                    "H: 6 near + 6 far rows at 96 sources and 57/96 targets; "
                    "scalar: 6 + 6 at 128 and 83/128. "
                    if state.action.key == "H"
                    else "Scalar: 6 near + 6 far rows at 128 sources and "
                    "83/128 targets; H: 6 + 6 at 96 and 57/96. "
                )
                + "No 1k -> 10k -> 100k or repeated-memory evidence."
            ),
        ),
        GateResult(
            "Tier-one closure",
            MISSING,
            (
                "MIT/pure-Rust shape and a four-platform workflow are useful "
                "facts, not accepted clean-host closure; current rustc fails."
            ),
        ),
    )


def _counterfactual_gates() -> tuple[GateResult, ...]:
    return tuple(
        GateResult(
            label,
            COUNTERFACTUAL,
            "Assumed closed only to test the promotion decision boundary.",
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
    """Derive the complete decision view for one immutable lab state."""

    profile = state.evidence
    safe_route = (
        f"{state.kernel.route} {state.action.adaptation} "
        "cub/sph remain Rust-owned exact-neighbor routes."
    )
    if profile.key == "unsafe-component-shortcut":
        route = (
            "REJECTED SHORTCUT: wrap gradient/Hessian components as scalar "
            "kernels and reuse scalar signed/permuted reference-vector M2L "
            "operators. Frozen far-field counterexamples invalidate this "
            "universal mapping."
        )
    else:
        route = safe_route

    if profile.hypothetical:
        return Assessment(
            route=route,
            ledger=_ledger(state),
            gates=_counterfactual_gates(),
            verdict="COUNTERFACTUAL AUTO-ELIGIBLE",
            first_disqualifier="none by assumption -- this is not observed evidence",
            conclusion=(
                "This view tests the decision rule only. It cannot promote "
                "Ferreus or replace the required evidence bundle."
            ),
            hypothetical=True,
        )

    gates = _current_gates(state)
    if profile.key == "unsafe-component-shortcut":
        verdict = "AUTO-INELIGIBLE"
        first_disqualifier = (
            "Semantic closure: frozen F/H counterexamples reject "
            "component-kernel symmetry reuse."
        )
        conclusion = (
            "Reject the component-kernel shortcut. Keep any Ferreus work behind "
            "a forced safe scalar-lift probe."
        )
    else:
        verdict = "FORCED-PROTOTYPE-ONLY"
        first_disqualifier = (
            "Semantic closure: the selected route lacks complete "
            "family/action/boundary/anisotropy evidence."
        )
        conclusion = (
            "The safe scalar-lift route remains plausible but unqualified. "
            "Empirical agreement can falsify mappings; it cannot certify a call "
            "or satisfy Auto promotion."
        )

    return Assessment(
        route=route,
        ledger=_ledger(state),
        gates=gates,
        verdict=verdict,
        first_disqualifier=first_disqualifier,
        conclusion=conclusion,
        hypothetical=False,
    )


def _cycle(index: int, size: int) -> int:
    return (index + 1) % size


def transition(state: LabState, command: str) -> LabState:
    """Apply one TUI command without performing I/O."""

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
            notice=f"Dimension: {(1, 2, 3)[index]}D.",
        )
    if command == "f":
        index = _cycle(state.kernel_index, len(KERNELS))
        return replace(
            state,
            kernel_index=index,
            notice=f"Kernel execution form: {KERNELS[index].label}.",
        )
    if command == "g":
        index = _cycle(state.geometry_index, len(GEOMETRIES))
        return replace(
            state,
            geometry_index=index,
            notice=f"Geometry: {GEOMETRIES[index].label}.",
        )
    if command == "x":
        index = _cycle(state.anisotropy_index, len(ANISOTROPIES))
        candidate = replace(
            state,
            anisotropy_index=index,
        )
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
            notice=f"Evidence view: {EVIDENCE_PROFILES[index].label}.",
        )
    if command == "r":
        return LabState(
            notice="Lab reset to the frozen Gaussian/transformed-coordinate case."
        )
    return replace(state, notice=f"Unknown command {command!r}; state unchanged.")
