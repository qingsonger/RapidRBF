"""Pure state model for the throwaway solver-stack decision lab.

Question: does a proposed RapidRBF solve plan make every decision-critical
solver, factorization, observation, resource, and evidence obligation explicit
before it can be treated as a v1 qualification candidate?

This module performs no I/O.  ``tui.py`` is a thin terminal adapter over the
small public interface:

``build_solve_plan(state)``
    Normalize selections into one invariant-checked plan with a shared resource
    ledger, a plan-shape fingerprint, and explicit immutable-binding requirements.

``assess(state)``
    Explain whether that plan shape is invalid, missing a bound evidence bundle,
    collected but unjudged, or hypothetically closed for one prototype case.

``compare_axis(state)``
    Hold the plan fixed while replacing one decision axis at a time.

``transition(state, command)``
    Return the next immutable lab state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256


MIB = 1024**2
GIB = 1024**3
F64_BYTES = 8
MAX_FINE_DOMAIN_POINTS = 1024
MAX_FINE_FACTOR_BYTES = (
    MAX_FINE_DOMAIN_POINTS * (MAX_FINE_DOMAIN_POINTS + 1) // 2 * F64_BYTES
)


@dataclass(frozen=True)
class PrototypeWorkload:
    prototype_id: str
    case_id: str
    accepted_seed: str
    label: str
    stage: str
    scalar_unknowns: int | None
    supplied_rows: int
    identity_preconditioner_allowed: bool
    sequence_kind: str
    operator_route: str
    baseline_authority: str
    factor_pressure_bytes: int | None
    factor_pressure_note: str
    fixture_identity_requirement: str
    description: str
    unknowns_note: str


WORKLOADS = (
    PrototypeWorkload(
        prototype_id="M1-EXP-LOCAL",
        case_id="M1/EXP/1K-EXACT",
        accepted_seed="lower rung of SCL.EXP-ORDINARY-1M",
        label="Localized exponential / 1k exact-direct",
        stage="1k mechanism truth",
        scalar_unknowns=1_001,
        supplied_rows=1_000,
        identity_preconditioner_allowed=True,
        sequence_kind="single",
        operator_route="small exact-direct authority",
        baseline_authority="Frozen Polatory lower-rung comparison; candidate missing",
        factor_pressure_bytes=None,
        factor_pressure_note="No measured 1k hierarchy/factor volume is bound.",
        fixture_identity_requirement=(
            "Bind the accepted generator version and exact 1k fixture/content hash."
        ),
        description=(
            "3D value-only exp(psill=1, range=0.02), identity anisotropy, "
            "degree zero, and zero nugget."
        ),
        unknowns_note="1,000 value equations plus one degree-zero coefficient.",
    ),
    PrototypeWorkload(
        prototype_id="M1-EXP-LOCAL",
        case_id="M1/EXP/10K-ASSIGNED",
        accepted_seed="lower rung of SCL.EXP-ORDINARY-1M",
        label="Localized exponential / 10k assigned route",
        stage="10k mechanism",
        scalar_unknowns=10_001,
        supplied_rows=10_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="assigned certified large-smooth route",
        baseline_authority="Frozen Polatory lower-rung comparison; candidate missing",
        factor_pressure_bytes=None,
        factor_pressure_note="No measured 10k hierarchy/factor volume is bound.",
        fixture_identity_requirement=(
            "Bind the accepted generator version and exact 10k fixture/content hash."
        ),
        description=(
            "3D value-only exp(psill=1, range=0.02), identity anisotropy, "
            "degree zero, and zero nugget."
        ),
        unknowns_note="10,000 value equations plus one degree-zero coefficient.",
    ),
    PrototypeWorkload(
        prototype_id="M2-TH3-CPD",
        case_id="M2/TH3/1K-EXACT",
        accepted_seed="th3 fixed solver panel + FIT.GEOMETRY",
        label="Global CPD mechanism / 1k exact-direct",
        stage="1k mechanism truth",
        scalar_unknowns=1_004,
        supplied_rows=1_000,
        identity_preconditioner_allowed=True,
        sequence_kind="single",
        operator_route="small exact-direct authority",
        baseline_authority="Accepted family/geometry seed; exact prototype fixture missing",
        factor_pressure_bytes=None,
        factor_pressure_note="No measured 1k hierarchy/factor volume is bound.",
        fixture_identity_requirement=(
            "Bind the accepted generator version, geometry case, and exact 1k content hash."
        ),
        description=(
            "3D value-only th3 with AUTO degree and nonuniform-boundary "
            "geometry to expose global polynomial/coarse modes."
        ),
        unknowns_note="1,000 value equations plus four degree-one coefficients.",
    ),
    PrototypeWorkload(
        prototype_id="M2-TH3-CPD",
        case_id="M2/TH3/10K-ASSIGNED",
        accepted_seed="th3 fixed solver panel + FIT.GEOMETRY",
        label="Global CPD mechanism / 10k assigned route",
        stage="10k mechanism",
        scalar_unknowns=10_004,
        supplied_rows=10_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="assigned certified route",
        baseline_authority="Accepted family/geometry seed; exact prototype fixture missing",
        factor_pressure_bytes=None,
        factor_pressure_note="No measured 10k hierarchy/factor volume is bound.",
        fixture_identity_requirement=(
            "Bind the accepted generator version, geometry case, and exact 10k content hash."
        ),
        description=(
            "3D value-only th3 with AUTO degree and nonuniform-boundary "
            "geometry to expose global polynomial/coarse modes."
        ),
        unknowns_note="10,000 value equations plus four degree-one coefficients.",
    ),
    PrototypeWorkload(
        prototype_id="M3-HERMITE-COMPOSITE",
        case_id="M3/HERMITE/1K-EXACT",
        accepted_seed="lower rung of SCL.HERMITE-COMPOSITE-1M",
        label="Mixed Hermite mechanism / 1k exact-direct",
        stage="1k mechanism truth",
        scalar_unknowns=1_504,
        supplied_rows=1_000,
        identity_preconditioner_allowed=True,
        sequence_kind="single",
        operator_route="small exact-direct certified A/F/F^T/H route",
        baseline_authority="Accepted journey shape; exact prototype fixture missing",
        factor_pressure_bytes=None,
        factor_pressure_note="Gradient multiplicity makes scalar value-only factor estimates inapplicable.",
        fixture_identity_requirement=(
            "Bind the accepted generator version and exact mixed-channel 1k content hash."
        ),
        description=(
            "3D th3(c>0)+gau, heterogeneous full anisotropy including shear, "
            "AUTO degree, nonzero nugget, 75% value and 25% full-gradient rows."
        ),
        unknowns_note=(
            "750 value equations + 250*3 gradient equations + four "
            "degree-one coefficients = 1,504."
        ),
    ),
    PrototypeWorkload(
        prototype_id="M3-HERMITE-COMPOSITE",
        case_id="M3/HERMITE/10K-ASSIGNED",
        accepted_seed="lower rung of SCL.HERMITE-COMPOSITE-1M",
        label="Mixed Hermite mechanism / 10k assigned route",
        stage="10k mechanism",
        scalar_unknowns=15_004,
        supplied_rows=10_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="assigned certified A/F/F^T/H route",
        baseline_authority="Accepted journey shape; exact prototype fixture missing",
        factor_pressure_bytes=None,
        factor_pressure_note="Gradient multiplicity makes scalar value-only factor estimates inapplicable.",
        fixture_identity_requirement=(
            "Bind the accepted generator version and exact mixed-channel 10k content hash."
        ),
        description=(
            "3D th3(c>0)+gau, heterogeneous full anisotropy including shear, "
            "AUTO degree, nonzero nugget, 75% value and 25% full-gradient rows."
        ),
        unknowns_note=(
            "7,500 value equations + 2,500*3 gradient equations + four "
            "degree-one coefficients = 15,004."
        ),
    ),
    PrototypeWorkload(
        prototype_id="M4-GEOMETRY-FAILURE",
        case_id="M4/GEOMETRY/1K-TRUTH-TABLE",
        accepted_seed="FIT.GEOMETRY boundary triplets",
        label="Hard-valid and structured-failure / 1k",
        stage="1k algorithm truth table",
        scalar_unknowns=None,
        supplied_rows=1_000,
        identity_preconditioner_allowed=True,
        sequence_kind="single",
        operator_route="small exact-direct authority",
        baseline_authority="Accepted family grammar; materialized triplet missing",
        factor_pressure_bytes=None,
        factor_pressure_note="A 1k diagnostic does not establish a scale factor policy.",
        fixture_identity_requirement=(
            "Bind each valid/invalid case ID, generator version, content hash, and expected status."
        ),
        description=(
            "Clustered, near-coincident, and nonuniform valid cases plus a "
            "separately labelled rank-invalid control."
        ),
        unknowns_note="This row contains multiple valid and invalid cases; bind each equation count.",
    ),
    PrototypeWorkload(
        prototype_id="M4-GEOMETRY-FAILURE",
        case_id="M4/GEOMETRY/10K-SELECTED-VALID",
        accepted_seed="FIT.GEOMETRY selected valid cases",
        label="Hard-valid geometry / selected 10k cases",
        stage="10k selected-valid follow-up",
        scalar_unknowns=None,
        supplied_rows=10_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="assigned certified route",
        baseline_authority="Accepted family grammar; selected case list is unmaterialized",
        factor_pressure_bytes=None,
        factor_pressure_note="No measured selected-case hierarchy/factor volume is bound.",
        fixture_identity_requirement=(
            "Bind the selected valid case IDs, generator version, exact content hashes, and counts."
        ),
        description=(
            "Only predeclared valid clustered, near-coincident, and nonuniform "
            "boundary cases graduate from the 1k truth table."
        ),
        unknowns_note="Selected valid cases may have different polynomial ranks; bind each count.",
    ),
    PrototypeWorkload(
        prototype_id="S1-SAME-A-SEQUENCE",
        case_id="S1/COMPATIBLE-WARM/ORDERED-SEQUENCE",
        accepted_seed="compatible FIT.WARM sequence over one prepared operator",
        label="Same-operator changing-RHS sequence",
        stage="materialized sequence required",
        scalar_unknowns=None,
        supplied_rows=0,
        identity_preconditioner_allowed=False,
        sequence_kind="same-operator",
        operator_route="one immutable prepared operator across every solve",
        baseline_authority="Accepted warm-start semantics; recycle fixture missing",
        factor_pressure_bytes=None,
        factor_pressure_note="Retained recycle and factor bytes must share one sequence grant.",
        fixture_identity_requirement=(
            "Bind ordered step IDs, payload hashes, one operator/hierarchy/factor identity, "
            "and per-step oracle identities."
        ),
        description=(
            "Several deterministic payload/right-hand-side changes under one "
            "geometry, model, action route, hierarchy, and factor identity."
        ),
        unknowns_note="No scale or maximum equation count is invented before sequence registration.",
    ),
    PrototypeWorkload(
        prototype_id="S2-CHANGED-A-SEQUENCE",
        case_id="S2/INCREMENTAL-1K-TO-10K+INCOMPATIBLE",
        accepted_seed="FIT.INCREMENTAL + incompatible FIT.WARM controls",
        label="Changed-operator recycle-invalidation sequence",
        stage="sequence correctness",
        scalar_unknowns=None,
        supplied_rows=10_000,
        identity_preconditioner_allowed=False,
        sequence_kind="changed-operator",
        operator_route="dimension/operator identity changes across sequence steps",
        baseline_authority="Accepted invalidation semantics; mapping is deliberately absent",
        factor_pressure_bytes=None,
        factor_pressure_note="Factor and vector dimensions vary; materialization must provide maxima.",
        fixture_identity_requirement=(
            "Bind ordered 1k->10k step IDs, per-step content/operator/dimension identities, "
            "and the incompatible-control reason."
        ),
        description=(
            "Nested incremental steps plus incompatible geometry, dimension, "
            "anisotropy, polynomial, route, or hierarchy changes."
        ),
        unknowns_note="No single scalar-unknown count exists; each registered step must bind one.",
    ),
    PrototypeWorkload(
        prototype_id="R1-RESOURCE-100K",
        case_id="R1/EXP/100K",
        accepted_seed="Nightly 100k lower rung of SCL.EXP-ORDINARY-1M",
        label="Resource/thread/I/O / 100k exp",
        stage="100k collection",
        scalar_unknowns=100_001,
        supplied_rows=100_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="fixed certified large-smooth route",
        baseline_authority="Nightly trend family; no threshold implied by tier",
        factor_pressure_bytes=None,
        factor_pressure_note="Actual hierarchy, factor, page-cache, and I/O volume must be measured.",
        fixture_identity_requirement=(
            "Bind the exp 100k fixture hash, lifecycle ordering, and paired run-plan identity."
        ),
        description=(
            "Fresh, declared-warm, and prepared-reuse lifecycles under 1, 2, "
            "and physical-core execution lanes."
        ),
        unknowns_note="100,000 value equations plus one degree-zero coefficient.",
    ),
    PrototypeWorkload(
        prototype_id="R1-RESOURCE-100K",
        case_id="R1/TH3/100K",
        accepted_seed="Nightly 100k th3 fixed-panel lower rung",
        label="Resource/thread/I/O / 100k th3",
        stage="100k collection",
        scalar_unknowns=100_004,
        supplied_rows=100_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="fixed certified large-smooth route",
        baseline_authority="Nightly trend family; no threshold implied by tier",
        factor_pressure_bytes=None,
        factor_pressure_note="Actual hierarchy, factor, page-cache, and I/O volume must be measured.",
        fixture_identity_requirement=(
            "Bind the th3 100k fixture hash, lifecycle ordering, and paired run-plan identity."
        ),
        description=(
            "Fresh, declared-warm, and prepared-reuse lifecycles under 1, 2, "
            "and physical-core execution lanes."
        ),
        unknowns_note="100,000 value equations plus four degree-one coefficients.",
    ),
    PrototypeWorkload(
        prototype_id="R1-RESOURCE-100K",
        case_id="R1/HERMITE/100K",
        accepted_seed="Nightly 100k lower rung of SCL.HERMITE-COMPOSITE-1M",
        label="Resource/thread/I/O / 100k Hermite composite",
        stage="100k collection",
        scalar_unknowns=150_004,
        supplied_rows=100_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="fixed certified A/F/F^T/H large-smooth route",
        baseline_authority="Nightly trend family; no threshold implied by tier",
        factor_pressure_bytes=None,
        factor_pressure_note="Actual mixed hierarchy, factor, page-cache, and I/O volume must be measured.",
        fixture_identity_requirement=(
            "Bind the Hermite 100k fixture hash, lifecycle ordering, and paired run-plan identity."
        ),
        description=(
            "Fresh, declared-warm, and prepared-reuse lifecycles under 1, 2, "
            "and physical-core execution lanes."
        ),
        unknowns_note=(
            "75,000 value + 25,000*3 gradient + four degree-one coefficients = 150,004."
        ),
    ),
    PrototypeWorkload(
        prototype_id="L1-RELEASE-1M",
        case_id="L1/SCL.EXP-ORDINARY-1M",
        accepted_seed="SCL.EXP-ORDINARY-1M.v1/{tier1}",
        label="Release row / exponential ordinary journey",
        stage="1M finalist-only",
        scalar_unknowns=1_000_001,
        supplied_rows=1_000_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="Ferreus-derived large-smooth qualification route",
        baseline_authority="Frozen input ladder; paired execution still required",
        factor_pressure_bytes=None,
        factor_pressure_note=(
            "Source-derived scalar illustration: about 9.37 GB packed factors "
            "and 10.53 GB reads per frozen four-level RAS application; approximate, "
            "not a preflight reservation or measured peak."
        ),
        fixture_identity_requirement=(
            "Bind the accepted content-addressed dataset, baseline/subject artifacts, "
            "paired immutable run plan, and threshold/profile versions."
        ),
        description=(
            "3D exp value-only ordinary fit, degree zero, zero nugget, followed "
            "by one million independent value targets."
        ),
        unknowns_note="1,000,000 value equations plus one degree-zero coefficient.",
    ),
    PrototypeWorkload(
        prototype_id="L1-RELEASE-1M",
        case_id="L1/SCL.EXP-INCREMENTAL-1M",
        accepted_seed="SCL.EXP-INCREMENTAL-1M.v1/{tier1}",
        label="Release row / exponential incremental journey",
        stage="1M finalist-only",
        scalar_unknowns=None,
        supplied_rows=1_000_000,
        identity_preconditioner_allowed=False,
        sequence_kind="changed-operator",
        operator_route="Ferreus-derived route with nested selected-center fits",
        baseline_authority="Frozen input ladder; selected-center execution missing",
        factor_pressure_bytes=None,
        factor_pressure_note="Selected-center count and every nested hierarchy must be materialized.",
        fixture_identity_requirement=(
            "Bind the accepted content-addressed dataset, ordered selected-center steps, "
            "per-step identities, paired run plan, and threshold/profile versions."
        ),
        description=(
            "Same 3D exp data/model, independent incremental fit, full-data "
            "certification, and one million value targets."
        ),
        unknowns_note="The selected-center count is evidence, so no scalar-unknown count is invented.",
    ),
    PrototypeWorkload(
        prototype_id="L1-RELEASE-1M",
        case_id="L1/SCL.HERMITE-COMPOSITE-1M",
        accepted_seed="SCL.HERMITE-COMPOSITE-1M.v1/{tier1}",
        label="Release row / Hermite composite journey",
        stage="1M finalist-only",
        scalar_unknowns=1_500_004,
        supplied_rows=1_000_000,
        identity_preconditioner_allowed=False,
        sequence_kind="single",
        operator_route="Ferreus-derived certified A/F/F^T/H route",
        baseline_authority="Accepted journey; executable authority missing",
        factor_pressure_bytes=None,
        factor_pressure_note=(
            "Value-only source estimates cannot predict the mixed-gradient "
            "hierarchy, factor volume, action cost, or stopping work."
        ),
        fixture_identity_requirement=(
            "Bind the accepted content-addressed mixed-channel dataset, baseline/subject "
            "artifacts, paired immutable run plan, and threshold/profile versions."
        ),
        description=(
            "3D th3(c>0)+gau with distinct anisotropies including shear, AUTO "
            "degree, nonzero nugget, 75% value and 25% full-gradient rows."
        ),
        unknowns_note=(
            "750,000 value + 250,000*3 gradient + four degree-one coefficients "
            "= 1,500,004."
        ),
    ),
)


@dataclass(frozen=True)
class DenseChoice:
    key: str
    label: str
    audited_coordinate: str
    role: str
    runtime: str
    factorization_fit: str
    threading: str
    evidence: str
    v1_scope: str


DENSE_CHOICES = (
    DenseChoice(
        key="faer",
        label="faer 0.24.4 behind RapidRBF-owned matrix views",
        audited_coordinate="faer@0.24.4",
        role="First pure-Rust dense-factor candidate",
        runtime="No mandatory BLAS/LAPACK runtime.",
        factorization_fit=(
            "LLT/LBLT, partial/full-pivot LU, QR, caller-planned scratch, and "
            "explicit Seq/Rayon execution; factor packing remains a probe."
        ),
        threading="Run sequential inside admitted outer-domain parallelism.",
        evidence="Capability audit only; no captured-block or end-to-end parity.",
        v1_scope="leading dense candidate",
    ),
    DenseChoice(
        key="nalgebra",
        label="nalgebra 0.35.0 dense fallback",
        audited_coordinate="nalgebra@0.35.0 + nalgebra-sparse@0.12.0",
        role="Pure-Rust replay comparator",
        runtime="Core is Rust; optional LAPACK features are a separate path.",
        factorization_fit="Broad decompositions but weaker explicit scratch planning.",
        threading="Selected path must remain inside the caller thread grant.",
        evidence="No accepted factor corpus or scale advantage.",
        v1_scope="captured-block fallback comparator",
    ),
    DenseChoice(
        key="native-lapack",
        label="ndarray-linalg/lax 0.18.1 + one native LAPACK backend",
        audited_coordinate=(
            "ndarray-linalg@0.18.1 + lax@0.18.1 + native-backend@UNMATERIALIZED"
        ),
        role="Native replay/benchmark comparator",
        runtime="Adds OpenBLAS, Netlib, MKL, or platform LAPACK closure.",
        factorization_fit="Mature native routines; RapidRBF still owns records and errors.",
        threading="Native worker counts must be explicit and observable.",
        evidence="No same-budget end-to-end win or four-target closure.",
        v1_scope="optional benchmark only",
    ),
    DenseChoice(
        key="oxiblas",
        label="OxiBLAS 0.2.1 watchlist",
        audited_coordinate="oxiblas@0.2.1 + oxiblas-sparse@0.2.1",
        role="Young pure-Rust workspace comparison",
        runtime="Pure Rust; inspected release lacks active GitHub CI.",
        factorization_fit="Promising factor/workspace inventory requires direct validation.",
        threading="Thread and memory-pool behavior must enter the shared grant.",
        evidence="Very young project; no RapidRBF numerical or tier-one evidence.",
        v1_scope="watchlist, not v1 default",
    ),
)


@dataclass(frozen=True)
class KrylovChoice:
    key: str
    label: str
    audited_coordinate: str
    role: str
    contract_complete: bool
    restarted: bool
    fixed_window: int | None
    observations: str
    evidence: str
    v1_scope: str


KRYLOV_CHOICES = (
    KrylovChoice(
        key="owned-restarted-fgmres",
        label="RapidRBF-owned restarted right FGMRES",
        audited_coordinate="RapidRBF-owned-fgmres@UNMATERIALIZED",
        role="Target deep solver module",
        contract_complete=True,
        restarted=True,
        fixed_window=None,
        observations=(
            "Contiguous V/Z, apply-into actions, fallible reservation, monitor/"
            "cancel, stable termination, and both residual histories."
        ),
        evidence="Required shape; restart and reorthogonalization remain empirical.",
        v1_scope="leading v1 shape",
    ),
    KrylovChoice(
        key="kryst-fgmres",
        label="kryst 4.3.0 FGMRES integration spike",
        audited_coordinate="kryst@4.3.0",
        role="Closest off-the-shelf differential comparison",
        contract_complete=False,
        restarted=True,
        fixed_window=None,
        observations="Right FGMRES, V/Z workspace, monitors, and true-residual checks.",
        evidence="Owned Vec allocation, broad lifecycle, and Linux-only upstream CI gaps.",
        v1_scope="spike/oracle, not v1 runtime yet",
    ),
    KrylovChoice(
        key="owned-unrestarted-fgmres",
        label="Owned Polatory-shape unrestarted FGMRES",
        audited_coordinate="RapidRBF-owned-polatory-shape-fgmres@UNMATERIALIZED",
        role="Lower-rung trajectory comparator",
        contract_complete=True,
        restarted=False,
        fixed_window=100,
        observations="Frozen public ceiling shape with V/Z retained for every step.",
        evidence="Source trajectory exists; Rust parity and scale admissibility do not.",
        v1_scope="lower-rung comparator only",
    ),
    KrylovChoice(
        key="ferreus-internal-fgmres",
        label="Ferreus 0.2.2 internal restarted FGMRES",
        audited_coordinate="ferreus_rbf@0.2.2",
        role="Acceleration-lineage code reference",
        contract_complete=False,
        restarted=True,
        fixed_window=5,
        observations="Accepts inner recurrence convergence; lacks required termination contract.",
        evidence="Source fact only; not a reusable solver crate or acceptance authority.",
        v1_scope="algorithm reference only",
    ),
    KrylovChoice(
        key="owned-gcrodr",
        label="Owned flexible GCRO-DR/recycling spike",
        audited_coordinate="RapidRBF-owned-gcrodr@UNMATERIALIZED",
        role="Sequence-only retained-subspace hypothesis",
        contract_complete=True,
        restarted=True,
        fixed_window=None,
        observations="Recycle identity, invalidation, retained bytes, and extraction enter the plan.",
        evidence="Algorithm authority only; no RapidRBF sequence evidence.",
        v1_scope="sequence-only follow-up",
    ),
    KrylovChoice(
        key="petsc-fgmres",
        label="PETSc/HPDDM FGMRES experiment",
        audited_coordinate="PETSc+HPDDM@UNMATERIALIZED",
        role="External numerical experiment",
        contract_complete=False,
        restarted=True,
        fixed_window=None,
        observations="Mature monitors and flexible/recycling variants behind a native runtime.",
        evidence="RapidRBF semantics, resource ownership, and distribution are unbound.",
        v1_scope="external oracle only",
    ),
)


@dataclass(frozen=True)
class OrthogonalizationChoice:
    key: str
    label: str
    description: str
    risk: str


ORTHOGONALIZATION_CHOICES = (
    OrthogonalizationChoice(
        key="mgs-guarded-reorth",
        label="MGS with an explicit guarded second pass",
        description="Leading robust policy; trigger and breakdown rules are versioned.",
        risk="More dot/axpy work; trigger needs M4 and scale evidence.",
    ),
    OrthogonalizationChoice(
        key="mgs-one-pass",
        label="One-pass modified Gram-Schmidt",
        description="Simple candidate trajectory without a recovery pass.",
        risk="Loss of orthogonality on M4 must be observed, not assumed safe.",
    ),
    OrthogonalizationChoice(
        key="cgs-frozen",
        label="Frozen one-pass classical Gram-Schmidt",
        description="Polatory lower-rung trajectory comparator.",
        risk="No reorthogonalization or robust near-breakdown protection.",
    ),
)


@dataclass(frozen=True)
class FactorAlgorithmChoice:
    key: str
    label: str
    contract_complete: bool
    description: str
    evidence: str


FACTOR_ALGORITHMS = (
    FactorAlgorithmChoice(
        key="lblt-gated-llt-lu",
        label="Pivoted LBLT + gated LLT + explicit LU fallback",
        contract_complete=True,
        description="Record pivots, status, rank gate, solve residual, and fallback reason.",
        evidence="Leading captured-block policy; no crate has passed the corpus yet.",
    ),
    FactorAlgorithmChoice(
        key="lblt-only",
        label="Pivoted LBLT only",
        contract_complete=True,
        description="Closest robust symmetric-indefinite comparator.",
        evidence="Factor-health, block pivots, packing, and coarse recovery unproven.",
    ),
    FactorAlgorithmChoice(
        key="silent-llt-fallback",
        label="Try LLT then silently fall back",
        contract_complete=False,
        description="Fallback is not declared before mutation and has no stable reason.",
        evidence="Deliberately invalid control.",
    ),
    FactorAlgorithmChoice(
        key="native-bk-lu",
        label="Native Bunch-Kaufman/LU replay policy",
        contract_complete=True,
        description="Narrow native captured-block comparator with normalized status.",
        evidence="Packaging, pivot parity, workspace, and thread evidence missing.",
    ),
)


@dataclass(frozen=True)
class PreconditionerChoice:
    key: str
    label: str
    role: str
    contract_complete: bool
    factor_store_required: bool
    topology: str
    evidence: str
    v1_scope: str


PRECONDITIONERS = (
    PreconditionerChoice(
        key="frozen-multilevel-ras",
        label="Frozen multilevel residual-correction RAS",
        role="Parity topology",
        contract_complete=True,
        factor_store_required=True,
        topology="Frozen domains, overlap, restriction, projection, transfers, and sweep order.",
        evidence="Source mechanism only; Rust hierarchy/convergence parity missing.",
        v1_scope="required comparator and initial port shape",
    ),
    PreconditionerChoice(
        key="same-hierarchy-additive-ras",
        label="Same-hierarchy additive RAS",
        role="Leading composition alternative",
        contract_complete=True,
        factor_store_required=True,
        topology="Same factors/coarse basis, explicit additive corrections, no frozen sweep.",
        evidence="Potential parallelism is a hypothesis; convergence is wholly empirical.",
        v1_scope="first-round alternative",
    ),
    PreconditionerChoice(
        key="projected-deflated-ras",
        label="Projected/deflated RAS with geometric coarse space",
        role="Leading coarse-space alternative",
        contract_complete=True,
        factor_store_required=True,
        topology="Versioned coarse projector with rank, compatibility, and fallback rules.",
        evidence="No RapidRBF fixture, rank, resource, or convergence evidence.",
        v1_scope="first-round alternative",
    ),
    PreconditionerChoice(
        key="one-level-ras",
        label="One-level RAS ablation",
        role="Coarse/multilevel necessity test",
        contract_complete=True,
        factor_store_required=True,
        topology="Frozen finest domains/restriction with no global coarse correction.",
        evidence="Sparse/RBF papers motivate a probe, not a RapidRBF result.",
        v1_scope="ablation; never infer a global default from exp alone",
    ),
    PreconditionerChoice(
        key="identity",
        label="Identity preconditioner",
        role="Exact-action Krylov diagnostic",
        contract_complete=True,
        factor_store_required=False,
        topology="No hierarchy, factors, or temporary factor I/O.",
        evidence="Useful only on 1k diagnostics.",
        v1_scope="M1-M4/1k diagnostic only",
    ),
    PreconditionerChoice(
        key="petsc-asm-mg",
        label="PETSc ASM/MG experiment",
        role="External matched-hierarchy experiment",
        contract_complete=False,
        factor_store_required=False,
        topology="PETSc-owned resource and hierarchy lifecycle is not mapped.",
        evidence="Official primitives exist; RapidRBF semantics/distribution are unbound.",
        v1_scope="external oracle only",
    ),
)


@dataclass(frozen=True)
class FactorStoreChoice:
    key: str
    label: str
    contract_complete: bool
    reservation_mode: str
    temporary_io: str
    evidence: str


FACTOR_STORES = (
    FactorStoreChoice(
        key="bounded-lru-positional",
        label="Explicit-cap LRU + positional ephemeral spill",
        contract_complete=True,
        reservation_mode="selected-cap",
        temporary_io="Self-describing checksummed records and independent offset reads.",
        evidence="Leading policy; hit ratio, page-cache effects, and I/O crossover unmeasured.",
    ),
    FactorStoreChoice(
        key="resident-if-admitted",
        label="Resident-all only after full preflight admission",
        contract_complete=True,
        reservation_mode="full-estimate",
        temporary_io="No factor I/O after setup.",
        evidence="Requires a materialized full-factor byte plan before admission.",
    ),
    FactorStoreChoice(
        key="frozen-single-cursor",
        label="Frozen single-cursor temporary spill",
        contract_complete=False,
        reservation_mode="unknown",
        temporary_io="One shared seek/read/write cursor and mutex; no common resource grant.",
        evidence="Parity/contention baseline only.",
    ),
    FactorStoreChoice(
        key="resident-unbounded",
        label="Retain every factor without preflight",
        contract_complete=False,
        reservation_mode="unknown",
        temporary_io="No factor spill, but no enforceable resident ceiling.",
        evidence="Ferreus lineage; deliberately inadmissible resource control.",
    ),
    FactorStoreChoice(
        key="bounded-recompute",
        label="Explicit-cap recompute-on-use pool",
        contract_complete=True,
        reservation_mode="selected-cap",
        temporary_io="Avoid factor spill and record every repeated assembly/factorization.",
        evidence="Bounded shape; cubic rebuild cost and convergence impact unmeasured.",
    ),
)


@dataclass(frozen=True)
class ObservationPolicy:
    key: str
    label: str
    schedule: str
    risk: str


OBSERVATION_POLICIES = (
    ObservationPolicy(
        key="restart-trigger",
        label="Algebraic residual at restart/trigger",
        schedule=(
            "Record recurrence each step; recompute b-A_route*x at restart and "
            "first trigger; attempt the fixed external/CPD certificate on candidates."
        ),
        risk="Leading schedule; trigger and action work require calibration.",
    ),
    ObservationPolicy(
        key="every-iteration",
        label="Every-iteration algebraic observation",
        schedule="Recompute b-A_route*x every step before any candidate certificate.",
        risk="Truth-table reference; too much operator work may block scale.",
    ),
    ObservationPolicy(
        key="terminal-only",
        label="Terminal/candidate observation only",
        schedule="Use recurrence to trigger the complete fixed terminal certificate.",
        risk="May waste a restart epoch after optimistic recurrence drift.",
    ),
    ObservationPolicy(
        key="polatory-legacy",
        label="Literal Polatory legacy observation trace",
        schedule="Direct 1024-target sample then full-site legacy evaluator.",
        risk=(
            "At 1M value sources the sample implies about 1.024B interactions; "
            "full-site legacy coverage may still be approximate and omits CPD."
        ),
    ),
    ObservationPolicy(
        key="recurrence-trigger",
        label="Recurrence-only certification trigger",
        schedule="No algebraic observation before attempting the fixed external/CPD certificate.",
        risk="Correctness stays external, but false triggers and wasted work are unobserved.",
    ),
)


@dataclass(frozen=True)
class ThreadPolicy:
    key: str
    label: str
    bounded: bool
    description: str
    risk: str


THREAD_POLICIES = (
    ThreadPolicy(
        key="outer-owned",
        label="One RapidRBF-owned outer pool; admitted inner kernels sequential",
        bounded=True,
        description="Parallelize admitted domains/operator chunks under one grant.",
        risk="Large isolated coarse work may underuse cores.",
    ),
    ThreadPolicy(
        key="phase-owned",
        label="One explicit owner per quiescent phase",
        bounded=True,
        description="Outer work pauses before an admitted dense/native sub-grant.",
        risk="Requires measured handoff and proof of no hidden workers.",
    ),
    ThreadPolicy(
        key="single-thread",
        label="Canonical single-thread lane",
        bounded=True,
        description="Configured/effective/maximum-live thread counts are one.",
        risk="Required evidence lane, not a million-scale throughput assumption.",
    ),
    ThreadPolicy(
        key="nested-auto",
        label="Rayon + dense/native pools all automatic",
        bounded=False,
        description="Independent runtimes choose workers outside one enforceable grant.",
        risk="Oversubscription and hidden maximum-live threads.",
    ),
)


@dataclass(frozen=True)
class ThreadLane:
    key: str
    label: str
    configured_threads: int | None
    requirement: str
    risk: str


THREAD_LANES = (
    ThreadLane(
        key="one",
        label="Canonical 1-thread lane",
        configured_threads=1,
        requirement="Configured, effective, and maximum-live counts must all equal one.",
        risk="Required truth lane; not a release-scale throughput claim.",
    ),
    ThreadLane(
        key="two",
        label="Canonical 2-thread lane",
        configured_threads=2,
        requirement="Exactly two admitted workers; hidden runtime and I/O workers still count.",
        risk="Distinguishes actual bounded parallelism from a nominal thread setting.",
    ),
    ThreadLane(
        key="physical-core",
        label="Canonical physical-core lane",
        configured_threads=None,
        requirement=(
            "Resolve the host physical-core count before the immutable plan; bind affinity "
            "and configured/effective/maximum-live counts."
        ),
        risk="Logical-core or auto-pool substitution would invalidate the accepted lane.",
    ),
)


@dataclass(frozen=True)
class BudgetPolicy:
    key: str
    label: str
    contract_complete: bool
    description: str
    risk: str


BUDGET_POLICIES = (
    BudgetPolicy(
        key="declared-complete",
        label="Declared iteration/action/work/certificate budgets",
        contract_complete=True,
        description="Every expensive action and terminal certificate is counted in the immutable plan.",
        risk="Exact values are fixture evidence, not defaults invented by this lab.",
    ),
    BudgetPolicy(
        key="iteration-only",
        label="Iteration limit only",
        contract_complete=False,
        description="Operator, preconditioner, observation, and certificate work is hidden.",
        risk="Two solvers can spend incomparable work under the same iteration count.",
    ),
    BudgetPolicy(
        key="unbounded",
        label="Unbounded until convergence",
        contract_complete=False,
        description="No enforceable resource/action/deadline termination.",
        risk="Incompatible with preflight, cancellation, and stable failure semantics.",
    ),
)


@dataclass(frozen=True)
class ExecutionLane:
    key: str
    label: str
    lifecycle: str
    affinity_cache: str
    risk: str


EXECUTION_LANES = (
    ExecutionLane(
        key="fresh-pinned",
        label="Fresh process / pinned affinity",
        lifecycle="New subject process and isolated scratch; no cold-page-cache claim.",
        affinity_cache="Selected cores are pinned; cache condition is declared and recorded.",
        risk="Required clean lifecycle; does not imply cold operating-system cache.",
    ),
    ExecutionLane(
        key="declared-warm",
        label="Declared warm-up / pinned affinity",
        lifecycle="Recorded untimed precondition precedes each measured subject.",
        affinity_cache="Same host/cores and symmetric warm-up for the paired subjects.",
        risk="Warm state must be part of the immutable plan, not inferred post hoc.",
    ),
    ExecutionLane(
        key="prepared-reuse",
        label="Prepared reuse / retained-state accounting",
        lifecycle="Preparation is separated from ordered measured applications.",
        affinity_cache="Retained memory, cache identity, apply index, and cleanup are recorded.",
        risk="Preparation time and retained high-water cannot disappear from evidence.",
    ),
)


@dataclass(frozen=True)
class EvidenceProfile:
    key: str
    label: str
    hypothetical: bool
    collected_complete: bool
    binding_manifest_complete: bool
    resource_manifest_complete: bool
    thresholds_attached: bool
    judged_pass: bool
    description: str


EVIDENCE_PROFILES = (
    EvidenceProfile(
        key="current",
        label="Current bound-plan evidence",
        hypothetical=False,
        collected_complete=False,
        binding_manifest_complete=False,
        resource_manifest_complete=False,
        thresholds_attached=False,
        judged_pass=False,
        description="Audits and contracts exist; no exact selected-plan bundle exists.",
    ),
    EvidenceProfile(
        key="collected-unjudged",
        label="WHAT-IF: immutable plan bundle is completely collected",
        hypothetical=True,
        collected_complete=True,
        binding_manifest_complete=True,
        resource_manifest_complete=True,
        thresholds_attached=False,
        judged_pass=False,
        description=(
            "Assume every required fixture, candidate, sequence, hierarchy, factor, "
            "operator, resource, and run-plan identity is supplied by an immutable "
            "manifest and every registered channel is integrity-closed, but no "
            "separately versioned threshold set is attached."
        ),
    ),
    EvidenceProfile(
        key="exact-row-gate-closed",
        label="WHAT-IF: selected plan/lane bundle gate closes",
        hypothetical=True,
        collected_complete=True,
        binding_manifest_complete=True,
        resource_manifest_complete=True,
        thresholds_attached=True,
        judged_pass=True,
        description=(
            "Assume a complete bound preflight/resource manifest, accepted-ready "
            "fixtures/oracles, separately versioned thresholds, and every semantic/"
            "resource/distribution obligation for this selected case/platform/lane bundle pass."
        ),
    ),
)


# Evidence-backed restarted brackets only. The frozen unrestarted comparator
# owns its separate fixed cap of 100; m=16 requires a later registered bracket.
WINDOWS = (5, 32, 64)
MEMORY_GRANTS_GIB = (2, 4, 8, 16, 32)
FACTOR_CAPS_GIB = (0.5, 1.0, 2.0, 4.0, 8.0)
PLATFORMS = (
    "Windows x86_64",
    "Linux x86_64 glibc",
    "macOS arm64",
    "macOS x86_64",
)
AXES = (
    "dense",
    "krylov",
    "restart window",
    "memory grant",
    "factor cap",
    "orthogonalization",
    "factor algorithm",
    "preconditioner",
    "factor store",
    "observation",
    "threads",
    "thread lane",
    "budgets",
    "execution lane",
)


@dataclass(frozen=True)
class LabState:
    workload_index: int = 13
    dense_index: int = 0
    krylov_index: int = 0
    orthogonalization_index: int = 0
    factor_algorithm_index: int = 0
    preconditioner_index: int = 0
    factor_store_index: int = 0
    observation_index: int = 0
    thread_index: int = 0
    thread_lane_index: int = 2
    budget_index: int = 0
    execution_lane_index: int = 0
    platform_index: int = 0
    window_index: int = 1
    grant_index: int = 2
    factor_cap_index: int = 2
    evidence_index: int = 0
    axis_index: int = 1
    notice: str = "No candidate is promoted by the current evidence."

    @property
    def workload(self) -> PrototypeWorkload:
        return WORKLOADS[self.workload_index]

    @property
    def dense(self) -> DenseChoice:
        return DENSE_CHOICES[self.dense_index]

    @property
    def krylov(self) -> KrylovChoice:
        return KRYLOV_CHOICES[self.krylov_index]

    @property
    def orthogonalization(self) -> OrthogonalizationChoice:
        return ORTHOGONALIZATION_CHOICES[self.orthogonalization_index]

    @property
    def factor_algorithm(self) -> FactorAlgorithmChoice:
        return FACTOR_ALGORITHMS[self.factor_algorithm_index]

    @property
    def preconditioner(self) -> PreconditionerChoice:
        return PRECONDITIONERS[self.preconditioner_index]

    @property
    def factor_store(self) -> FactorStoreChoice:
        return FACTOR_STORES[self.factor_store_index]

    @property
    def observation(self) -> ObservationPolicy:
        return OBSERVATION_POLICIES[self.observation_index]

    @property
    def threads(self) -> ThreadPolicy:
        return THREAD_POLICIES[self.thread_index]

    @property
    def thread_lane(self) -> ThreadLane:
        return THREAD_LANES[self.thread_lane_index]

    @property
    def budgets(self) -> BudgetPolicy:
        return BUDGET_POLICIES[self.budget_index]

    @property
    def execution_lane(self) -> ExecutionLane:
        return EXECUTION_LANES[self.execution_lane_index]

    @property
    def platform(self) -> str:
        return PLATFORMS[self.platform_index]

    @property
    def selected_window(self) -> int:
        return WINDOWS[self.window_index]

    @property
    def effective_window(self) -> int:
        return self.krylov.fixed_window or self.selected_window

    @property
    def grant_gib(self) -> int:
        return MEMORY_GRANTS_GIB[self.grant_index]

    @property
    def factor_cap_gib(self) -> float:
        return FACTOR_CAPS_GIB[self.factor_cap_index]

    @property
    def evidence(self) -> EvidenceProfile:
        return EVIDENCE_PROFILES[self.evidence_index]

    @property
    def axis(self) -> str:
        return AXES[self.axis_index]


@dataclass(frozen=True)
class ResourceLedger:
    grant_bytes: int
    krylov_window: int
    basis_vectors: int | None
    basis_bytes: int | None
    coefficient_bytes: int | None
    factor_reservation_bytes: int | None
    known_subtotal_bytes: int
    headroom_after_known_bytes: int
    unknown_reservations: tuple[str, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class SolvePlan:
    plan_shape_id: str
    binding_requirements: tuple[str, ...]
    resource: ResourceLedger
    invariant_gaps: tuple[str, ...]
    warnings: tuple[str, ...]
    dense_applicable: bool
    factor_algorithm_applicable: bool
    factor_store_applicable: bool
    terminal_authority: str
    termination_states: tuple[str, ...]


@dataclass(frozen=True)
class Assessment:
    status: str
    plan: SolvePlan
    evidence_gaps: tuple[str, ...]
    probes: tuple[str, ...]
    conclusion: str


@dataclass(frozen=True)
class AxisRow:
    selected: bool
    label: str
    status: str
    reason: str


TERMINAL_AUTHORITY = (
    "Complete external value/gradient residual + evaluator error + normalized "
    "CPD-side certificate within declared work budgets"
)
TERMINATION_STATES = (
    "Converged",
    "BudgetExhausted",
    "Breakdown",
    "NonFinite",
    "RankDeficient",
    "ResourceDenied",
    "Cancelled",
)


def _cycle(value: int, size: int) -> int:
    return (value + 1) % size


def _factor_reservation(
    state: LabState,
) -> tuple[int | None, tuple[str, ...], tuple[str, ...]]:
    if not state.preconditioner.factor_store_required:
        return 0, (), ("Factor storage is not applicable to this preconditioner.",)

    store = state.factor_store
    if store.reservation_mode == "selected-cap":
        cap = int(state.factor_cap_gib * GIB)
        return (
            cap,
            (),
            (
                f"Resident-factor/recompute-pool cap is an explicit lab selection: "
                f"{state.factor_cap_gib:g} GiB.",
            ),
        )
    if store.reservation_mode == "full-estimate":
        return (
            None,
            ("materialized full-factor reservation",),
            (
                "The approximate frozen Polatory scalar illustration is never promoted "
                "to a byte-exact preflight reservation; the selected hierarchy must be measured.",
            ),
        )
    return (
        None,
        ("enforceable factor resident/scratch reservation",),
        ("The selected factor store exposes no complete reservation.",),
    )


def resource_ledger(state: LabState) -> ResourceLedger:
    """Build one shared ledger; unknown categories can never imply admission."""

    grant_bytes = state.grant_gib * GIB
    n = state.workload.scalar_unknowns
    m = state.effective_window
    if n is None:
        basis_vectors = None
        basis_bytes = None
        coefficient_bytes = None
    else:
        basis_vectors = 2 * m + 1
        basis_bytes = F64_BYTES * n * basis_vectors
        coefficient_bytes = F64_BYTES * n

    factor_bytes, factor_unknowns, factor_assumptions = _factor_reservation(state)
    known_parts = tuple(
        value
        for value in (basis_bytes, coefficient_bytes, factor_bytes)
        if value is not None
    )
    known_subtotal = sum(known_parts)
    unknowns: list[str] = [
        "prepared operator persistent/session bytes",
        f"per-thread operator/I/O workspace under {state.thread_lane.label}",
        "candidate reconstruction, terminal certificate, and output staging",
        "allocator/runtime overhead and concurrent high-water",
    ]
    if state.preconditioner.factor_store_required:
        unknowns.extend(
            (
                "local/coarse matrix assembly and factorization workspace",
                "preconditioner hierarchy/transfer scratch",
            )
        )
    elif state.preconditioner.key == "petsc-asm-mg":
        unknowns.append("external PETSc hierarchy/preconditioner workspace and native runtime")
    if n is None:
        unknowns.insert(0, "V/Z and coefficient bytes for each materialized solve step")
    unknowns.extend(factor_unknowns)
    if (
        state.preconditioner.factor_store_required
        and state.factor_store.key == "bounded-lru-positional"
    ):
        unknowns.append(
            "ephemeral scratch capacity, I/O buffers, queue wait, and page-cache/RSS accounting"
        )
    if state.workload.prototype_id == "S1-SAME-A-SEQUENCE":
        unknowns.append(
            "registered equal retained-vector byte cap and paired FGMRES/GCRO-DR workspace mapping"
        )
    if state.krylov.key == "owned-gcrodr":
        unknowns.append("recycle U/C/extraction workspace under the retained-vector cap")

    assumptions: list[str] = [
        "V/Z uses 8*n*(2m+1) and excludes every other solver allocation.",
    ]
    if state.preconditioner.factor_store_required:
        assumptions.append(state.workload.factor_pressure_note)
    assumptions.extend(factor_assumptions)
    return ResourceLedger(
        grant_bytes=grant_bytes,
        krylov_window=m,
        basis_vectors=basis_vectors,
        basis_bytes=basis_bytes,
        coefficient_bytes=coefficient_bytes,
        factor_reservation_bytes=factor_bytes,
        known_subtotal_bytes=known_subtotal,
        headroom_after_known_bytes=grant_bytes - known_subtotal,
        unknown_reservations=tuple(dict.fromkeys(unknowns)),
        assumptions=tuple(dict.fromkeys(assumptions)),
    )


def _binding_requirements(state: LabState) -> tuple[str, ...]:
    requirements = [
        (
            f"Accepted stable scenario ID + prototype case {state.workload.case_id}; "
            f"seed is only {state.workload.accepted_seed}."
        ),
        state.workload.fixture_identity_requirement,
        (
            f"Krylov audited coordinate is {state.krylov.audited_coordinate}; bind the exact "
            "source/lock graph, features, toolchain, build flags, and implementation artifact hash."
        ),
        (
            "Bind versioned Krylov restart/termination, orthogonalization/reorthogonalization, "
            "and selected preconditioner-composition policy records."
        ),
        (
            f"Bind thread lane {state.thread_lane.label}: "
            f"{state.thread_lane.requirement}"
        ),
        (
            f"Bind platform {state.platform}: canonical subject build, target/toolchain, "
            "host/environment fingerprint, and effective affinity."
        ),
        (
            f"Bind execution lane {state.execution_lane.label}: lifecycle/cache precondition, "
            "scratch containment, paired ordering, cleanup, and retained-state identity."
        ),
        (
            "Bind the content-addressed frozen Polatory baseline executable/build and adapter "
            "identity plus the full RapidRBF subject/harness artifact and paired-run identity."
        ),
        (
            f"Bind the selected {state.grant_gib} GiB total resource grant and every "
            "memory, scratch, thread, action, certificate, and deadline subgrant."
        ),
        "Bind the operator/action implementation build and acceleration-routing profile version.",
        "Bind the observation/certificate implementation, work-budget plan, and run-plan version.",
        "Bind the separately governed threshold/profile version before judgment.",
    ]
    if state.workload.sequence_kind != "single":
        requirements.append(
            "Bind every ordered sequence-step ID, operator/dimension identity, and invalidation event."
        )
    if state.preconditioner.factor_store_required:
        requirements.extend(
            (
                (
                    f"Dense audited coordinate is {state.dense.audited_coordinate}; bind the exact "
                    "lock graph, features/backend, toolchain, target, build flags, and artifact hash."
                ),
                "Bind versioned local/coarse factor/fallback and factor-store policy records.",
                "Bind hierarchy, partition, overlap, restriction, projection, transfer, and coarse identities.",
                "Bind local/coarse matrix hashes, factor-corpus identity, and factor-record format version.",
            )
        )
    if (
        state.preconditioner.factor_store_required
        and state.factor_store.reservation_mode == "selected-cap"
    ):
        requirements.append(
            f"Bind the {state.factor_cap_gib:g} GiB cap to the factor-store resource manifest."
        )
    if (
        state.preconditioner.factor_store_required
        and "UNMATERIALIZED" in state.dense.audited_coordinate
    ):
        requirements.append("Replace the unmaterialized native dense backend identity.")
    if "UNMATERIALIZED" in state.krylov.audited_coordinate:
        requirements.append("Replace the unmaterialized Krylov implementation identity.")
    if state.workload.prototype_id == "S1-SAME-A-SEQUENCE":
        requirements.append(
            "Bind a paired owned restarted-FGMRES/GCRO-DR sequence experiment under one "
            "equal retained-vector byte cap, including the reduced-FGMRES restart mapping "
            "and whole-sequence work comparison."
        )
    return tuple(dict.fromkeys(requirements))


def _plan_shape_id(state: LabState) -> str:
    dense_key = (
        state.dense.audited_coordinate
        if state.preconditioner.factor_store_required
        else "dense-na"
    )
    factor_algorithm_key = (
        state.factor_algorithm.key
        if state.preconditioner.factor_store_required
        else "factor-algorithm-na"
    )
    factor_cap_key = (
        f"factor-cap={state.factor_cap_gib:g}GiB"
        if (
            state.preconditioner.factor_store_required
            and state.factor_store.reservation_mode == "selected-cap"
        )
        else "factor-cap-na"
    )
    material = "|".join(
        (
            state.workload.prototype_id,
            state.workload.case_id,
            state.workload.accepted_seed,
            dense_key,
            state.krylov.audited_coordinate,
            state.orthogonalization.key,
            factor_algorithm_key,
            state.preconditioner.key,
            state.factor_store.key
            if state.preconditioner.factor_store_required
            else "factor-store-na",
            state.observation.key,
            state.threads.key,
            state.thread_lane.key,
            state.budgets.key,
            state.execution_lane.key,
            state.platform,
            f"window={state.effective_window}",
            f"grant={state.grant_gib}GiB",
            factor_cap_key,
        )
    )
    return f"{state.workload.prototype_id}/shape-{sha256(material.encode()).hexdigest()[:12]}"


def build_solve_plan(state: LabState) -> SolvePlan:
    """Normalize selections and reject invalid cross-axis compositions."""

    ledger = resource_ledger(state)
    gaps: list[str] = []
    warnings: list[str] = []

    if not state.krylov.contract_complete:
        gaps.append(f"{state.krylov.label} does not satisfy the owned solve/report contract.")
    if (
        state.preconditioner.factor_store_required
        and not state.factor_algorithm.contract_complete
    ):
        gaps.append(f"{state.factor_algorithm.label} has no declared stable fallback/status contract.")
    if (
        state.preconditioner.factor_store_required
        and state.factor_algorithm.key == "native-bk-lu"
        and state.dense.key != "native-lapack"
    ):
        gaps.append("The native Bunch-Kaufman/LU replay policy requires the native LAPACK substrate.")
    if not state.preconditioner.contract_complete:
        gaps.append(f"{state.preconditioner.label} has no RapidRBF-owned lifecycle/resource contract.")
    if state.preconditioner.factor_store_required and not state.factor_store.contract_complete:
        gaps.append(f"{state.factor_store.label} has no enforceable complete factor resource policy.")
    if not state.threads.bounded:
        gaps.append("Thread ownership cannot enforce configured/effective/maximum-live counts.")
    if state.threads.key == "single-thread" and state.thread_lane.key != "one":
        gaps.append("The canonical single-thread policy composes only with the 1-thread lane.")
    if state.workload.prototype_id == "L1-RELEASE-1M" and state.thread_lane.key != "physical-core":
        gaps.append("Every L1 release case requires the canonical physical-core tier-one lane.")
    if not state.budgets.contract_complete:
        gaps.append("Iteration-only or unbounded work cannot define certified convergence.")
    if ledger.known_subtotal_bytes > ledger.grant_bytes:
        gaps.append("Known V/Z, coefficient, and factor reservations exceed the total grant.")

    if (
        state.preconditioner.key == "identity"
        and not state.workload.identity_preconditioner_allowed
    ):
        gaps.append("Identity preconditioning is restricted to registered M1-M4 1k diagnostics.")
    if state.krylov.key == "owned-gcrodr" and state.workload.sequence_kind == "single":
        gaps.append("GCRO-DR may be judged only on a declared solve sequence.")
    if (
        state.workload.prototype_id == "S1-SAME-A-SEQUENCE"
        and state.krylov.key not in {"owned-restarted-fgmres", "owned-gcrodr"}
    ):
        gaps.append(
            "S1 admits only the paired owned restarted-FGMRES and GCRO-DR experiment."
        )
    if state.krylov.key == "owned-gcrodr" and state.workload.sequence_kind == "changed-operator":
        warnings.append("Changed-operator sequence judges conservative recycle discard, not speed.")
    if state.krylov.key != "owned-gcrodr" and state.workload.sequence_kind == "same-operator":
        warnings.append("This is the non-recycling comparator for the same-operator sequence.")

    if state.orthogonalization.key == "cgs-frozen":
        warnings.append("Frozen one-pass CGS is a parity comparator, not the robust default.")
    elif state.orthogonalization.key == "mgs-one-pass":
        warnings.append("One-pass MGS needs M4 loss-of-orthogonality evidence.")
    if state.preconditioner.factor_store_required and state.dense.key == "native-lapack":
        warnings.append("Native artifact, license, thread, and cross-backend closure remains mandatory.")
    if state.preconditioner.factor_store_required and state.dense.key == "oxiblas":
        warnings.append("OxiBLAS maturity and tier-one validation are open.")
    if state.preconditioner.key != "frozen-multilevel-ras":
        warnings.append("Selected preconditioner is an alternative, not a frozen-topology port.")
    if state.observation.key == "polatory-legacy":
        warnings.append("The literal Polatory trace is diagnostic and never terminal authority.")
    if state.krylov.fixed_window is not None:
        warnings.append(
            f"{state.krylov.label} fixes its comparison window/cap at {state.effective_window}."
        )
    if ledger.unknown_reservations:
        warnings.append("Resource preflight is incomplete until every unknown reservation is materialized.")
    if state.thread_lane.key == "physical-core":
        warnings.append(
            "The physical-core count and affinity are identities to bind, never an auto-pool request."
        )
    if state.workload.prototype_id == "S1-SAME-A-SEQUENCE":
        warnings.append(
            "S1 judgment is pair-level: both owned FGMRES and GCRO-DR share one retained-vector byte cap."
        )

    return SolvePlan(
        plan_shape_id=_plan_shape_id(state),
        binding_requirements=_binding_requirements(state),
        resource=ledger,
        invariant_gaps=tuple(dict.fromkeys(gaps)),
        warnings=tuple(dict.fromkeys(warnings)),
        dense_applicable=state.preconditioner.factor_store_required,
        factor_algorithm_applicable=state.preconditioner.factor_store_required,
        factor_store_applicable=state.preconditioner.factor_store_required,
        terminal_authority=TERMINAL_AUTHORITY,
        termination_states=TERMINATION_STATES,
    )


def _probes(state: LabState) -> tuple[str, ...]:
    probe_by_axis = {
        "dense": (
            f"Dense: replay M1-M4 captured blocks through {state.dense.label} "
            f"with {state.factor_algorithm.label}; record pivots/status/residual/workspace."
        ),
        "factor algorithm": (
            f"Factors: replay one captured corpus through {state.factor_algorithm.label}; "
            "record factor health, pivots, packing, fallback, coarse recovery, and workspace."
        ),
        "krylov": (
            f"Krylov: compare m=5/32/64 and lower-rung unrestarted with "
            f"{state.orthogonalization.label}; count actions and both residual histories."
        ),
        "restart window": (
            f"Restart window: compare m=5/32/64 and the affordable unrestarted "
            f"lower-rung cap under one shared grant; selected m={state.effective_window}."
        ),
        "memory grant": (
            f"Memory grant: materialize every unknown reservation before testing "
            f"the selected {state.grant_gib} GiB admission and one byte-below failure."
        ),
        "factor cap": (
            f"Factor cap: compare resident/spill/recompute behavior at the selected "
            f"{state.factor_cap_gib:g} GiB only where the store consumes an explicit cap."
        ),
        "orthogonalization": (
            f"Orthogonalization: compare {state.orthogonalization.label} with frozen CGS "
            "on M4 and record loss, reorthogonalization, breakdown, and extra vector traffic."
        ),
        "preconditioner": (
            f"Preconditioner: hold one hierarchy/factor corpus fixed while comparing "
            f"{state.preconditioner.label} against frozen/additive/projected/one-level variants."
        ),
        "observation": (
            f"Observation: calibrate {state.observation.label} against every-iteration "
            "algebraic traces and the fixed terminal certificate."
        ),
        "threads": (
            f"Ownership: materialize every unknown reservation under {state.threads.label} "
            f"on {state.thread_lane.label}; "
            "record configured/effective/maximum-live counts."
        ),
        "thread lane": (
            f"Thread lane: run the registered 1, 2, and physical-core lanes under "
            f"one ownership policy; selected={state.thread_lane.label}."
        ),
        "budgets": (
            f"Budgets: register {state.budgets.label} with iteration, action, "
            "preconditioner-work, observation, certificate, cancellation, and deadline counts."
        ),
        "execution lane": (
            f"Lane: capture {state.execution_lane.label} on {state.platform} with "
            "affinity/cache/lifecycle identity and cleanup evidence."
        ),
    }
    if not state.preconditioner.factor_store_required:
        probe_by_axis["dense"] = (
            f"Dense/local factors: N/A for {state.preconditioner.label}; verify the "
            "plan binds no dense-factor artifact, workspace, or hidden factor path."
        )
        probe_by_axis["factor algorithm"] = (
            f"Factor algorithm: N/A for {state.preconditioner.label}."
        )
    if state.preconditioner.factor_store_required:
        if state.factor_store.reservation_mode == "selected-cap":
            probe_by_axis["factor store"] = (
                f"Factors: measure {state.factor_store.label} under the explicit "
                f"{state.factor_cap_gib:g} GiB cap, including I/O wait, cache hits, and rebuilds."
            )
        elif state.factor_store.reservation_mode == "full-estimate":
            probe_by_axis["factor store"] = (
                f"Factors: materialize the complete hierarchy reservation before "
                f"admitting {state.factor_store.label}; then record retained high-water."
            )
        else:
            probe_by_axis["factor store"] = (
                f"Factors: retain {state.factor_store.label} only as a parity/risk "
                "control and record its missing reservation, contention, and cleanup behavior."
            )
    else:
        probe_by_axis["factor store"] = (
            f"Factor store: N/A for {state.preconditioner.label}; verify no factor "
            "reservation or I/O leaks into the plan."
        )

    order = (
        state.axis,
        "dense",
        "factor algorithm",
        "krylov",
        "restart window",
        "memory grant",
        "factor cap",
        "orthogonalization",
        "preconditioner",
        "factor store",
        "observation",
        "threads",
        "thread lane",
        "budgets",
        "execution lane",
    )
    probes = [probe_by_axis[key] for key in dict.fromkeys(order)]
    if state.workload.prototype_id == "S1-SAME-A-SEQUENCE":
        probes.insert(
            0,
            "S1 pair: compare owned restarted-FGMRES and GCRO-DR over the full sequence "
            "under one equal retained-vector byte cap and registered restart mapping.",
        )
    elif state.krylov.key == "owned-gcrodr":
        probes.insert(
            0,
            "Recycling: compare whole-sequence work under equal retained-vector bytes and exact identity invalidation.",
        )
    return tuple(probes)


def assess(state: LabState) -> Assessment:
    """Assess one plan shape without treating tier as evidence readiness."""

    plan = build_solve_plan(state)
    evidence_gaps: list[str] = []
    evidence = state.evidence

    if plan.invariant_gaps:
        status = "PLAN INVALID"
        conclusion = "Redesign the selected composition before collecting qualification evidence."
    elif not evidence.collected_complete:
        status = "BOUND-PLAN EVIDENCE MISSING"
        evidence_gaps.extend(
            (
                (
                    f"No immutable bundle satisfies the {len(plan.binding_requirements)} "
                    f"binding requirements for {plan.plan_shape_id}."
                ),
                "Factor parity, convergence, resource high-water, runtime, and failure channels are missing.",
            )
        )
        if plan.resource.unknown_reservations:
            evidence_gaps.append("The shared preflight plan still contains unmaterialized byte categories.")
        conclusion = (
            "The plan shape is internally admissible, but every numerical and "
            "performance conclusion remains unjudged."
        )
    elif not evidence.binding_manifest_complete:
        status = "IMMUTABLE BINDING MANIFEST MISSING"
        evidence_gaps.append(
            "Collection cannot be associated with an accepted scenario, exact fixture, "
            "candidate artifacts, sequence steps, hierarchy/factors, and profile versions."
        )
        conclusion = "The plan shape cannot be collected or judged without one immutable binding manifest."
    elif plan.resource.unknown_reservations and not evidence.resource_manifest_complete:
        status = "RESOURCE MANIFEST MISSING"
        evidence_gaps.append(
            "The evidence view does not replace every unmaterialized byte category with a bound manifest."
        )
        conclusion = "The bound bundle cannot be collected or judged before resource preflight closes."
    elif not evidence.thresholds_attached:
        status = "COLLECTED, UNJUDGED"
        evidence_gaps.append("No separately versioned threshold set is attached to the bound bundle.")
        conclusion = (
            "Counterfactually complete evidence would be reviewable, but collection "
            "alone asserts neither compatibility nor performance parity."
        )
    elif evidence.judged_pass:
        status = "WHAT-IF SELECTED PLAN/LANE GATE CLOSED"
        conclusion = (
            "Only this selected case/platform/thread/lifecycle bundle closes in the "
            "counterfactual; required sibling lanes, other cases, tiers, and v1 remain open."
        )
    else:
        status = "JUDGMENT FAILED"
        conclusion = "The bound bundle does not satisfy its separately governed gates."

    return Assessment(
        status=status,
        plan=plan,
        evidence_gaps=tuple(dict.fromkeys(evidence_gaps)),
        probes=_probes(state),
        conclusion=conclusion,
    )


def _axis_variants(state: LabState) -> tuple[tuple[str, object, int], ...]:
    if state.axis == "dense":
        return tuple(("dense_index", item, index) for index, item in enumerate(DENSE_CHOICES))
    if state.axis == "krylov":
        return tuple(("krylov_index", item, index) for index, item in enumerate(KRYLOV_CHOICES))
    if state.axis == "orthogonalization":
        return tuple(
            ("orthogonalization_index", item, index)
            for index, item in enumerate(ORTHOGONALIZATION_CHOICES)
        )
    if state.axis == "factor algorithm":
        return tuple(
            ("factor_algorithm_index", item, index)
            for index, item in enumerate(FACTOR_ALGORITHMS)
        )
    if state.axis == "preconditioner":
        return tuple(
            ("preconditioner_index", item, index)
            for index, item in enumerate(PRECONDITIONERS)
        )
    if state.axis == "factor store":
        return tuple(
            ("factor_store_index", item, index)
            for index, item in enumerate(FACTOR_STORES)
        )
    if state.axis == "observation":
        return tuple(
            ("observation_index", item, index)
            for index, item in enumerate(OBSERVATION_POLICIES)
        )
    if state.axis == "threads":
        return tuple(("thread_index", item, index) for index, item in enumerate(THREAD_POLICIES))
    if state.axis == "thread lane":
        return tuple(
            ("thread_lane_index", item, index)
            for index, item in enumerate(THREAD_LANES)
        )
    if state.axis == "budgets":
        return tuple(("budget_index", item, index) for index, item in enumerate(BUDGET_POLICIES))
    return tuple(
        ("execution_lane_index", item, index)
        for index, item in enumerate(EXECUTION_LANES)
    )


def _axis_reason(item: object) -> str:
    if isinstance(item, DenseChoice):
        return f"{item.v1_scope}; {item.evidence}"
    if isinstance(item, KrylovChoice):
        return f"{item.v1_scope}; {item.evidence}"
    if isinstance(item, OrthogonalizationChoice):
        return item.risk
    if isinstance(item, FactorAlgorithmChoice):
        return item.evidence
    if isinstance(item, PreconditionerChoice):
        return f"{item.v1_scope}; {item.evidence}"
    if isinstance(item, FactorStoreChoice):
        return item.evidence
    if isinstance(item, ObservationPolicy):
        return item.risk
    if isinstance(item, ThreadPolicy):
        return item.risk
    if isinstance(item, ThreadLane):
        return f"{item.requirement} {item.risk}"
    if isinstance(item, BudgetPolicy):
        return item.risk
    if isinstance(item, ExecutionLane):
        return item.risk
    return "No axis-specific reason."


def compare_axis(state: LabState) -> tuple[AxisRow, ...]:
    """Compare one axis with axis-specific reasons, never inherited-gap prose."""

    if state.axis == "restart window":
        if state.krylov.fixed_window is not None:
            return (
                AxisRow(
                    selected=True,
                    label=f"Fixed at {state.krylov.fixed_window}",
                    status="N/A",
                    reason=f"{state.krylov.label} fixes its comparison window/cap.",
                ),
            )
        rows = []
        for index, window in enumerate(WINDOWS):
            candidate_state = replace(state, window_index=index)
            ledger = build_solve_plan(candidate_state).resource
            rows.append(
                AxisRow(
                    selected=state.window_index == index,
                    label=f"restart m={window}",
                    status=assess(candidate_state).status,
                    reason=(
                        f"V/Z={ledger.basis_bytes / MIB:.1f} MiB"
                        if ledger.basis_bytes is not None
                        else "V/Z unmaterialized for this workload"
                    ),
                )
            )
        return tuple(rows)

    if state.axis == "memory grant":
        rows = []
        for index, grant in enumerate(MEMORY_GRANTS_GIB):
            candidate_state = replace(state, grant_index=index)
            ledger = build_solve_plan(candidate_state).resource
            rows.append(
                AxisRow(
                    selected=state.grant_index == index,
                    label=f"total grant={grant} GiB",
                    status=assess(candidate_state).status,
                    reason=(
                        f"known={ledger.known_subtotal_bytes / GIB:.2f} GiB; "
                        f"headroom={ledger.headroom_after_known_bytes / GIB:.2f} GiB; "
                        f"unknown={len(ledger.unknown_reservations)}"
                    ),
                )
            )
        return tuple(rows)

    if state.axis == "factor cap":
        if not state.preconditioner.factor_store_required:
            return (
                AxisRow(
                    selected=True,
                    label="Not applicable",
                    status="N/A",
                    reason=(
                        f"{state.preconditioner.label} owns no RapidRBF factor store or cap."
                    ),
                ),
            )
        if state.factor_store.reservation_mode != "selected-cap":
            return (
                AxisRow(
                    selected=True,
                    label="Not applicable",
                    status="N/A",
                    reason=f"{state.factor_store.label} does not consume the explicit cap.",
                ),
            )
        rows = []
        for index, cap in enumerate(FACTOR_CAPS_GIB):
            candidate_state = replace(state, factor_cap_index=index)
            ledger = build_solve_plan(candidate_state).resource
            rows.append(
                AxisRow(
                    selected=state.factor_cap_index == index,
                    label=f"factor cap={cap:g} GiB",
                    status=assess(candidate_state).status,
                    reason=(
                        f"known={ledger.known_subtotal_bytes / GIB:.2f} GiB; "
                        f"headroom={ledger.headroom_after_known_bytes / GIB:.2f} GiB"
                    ),
                )
            )
        return tuple(rows)

    if (
        state.axis in {"dense", "factor algorithm", "factor store"}
        and not state.preconditioner.factor_store_required
    ):
        return (
            AxisRow(
                selected=True,
                label="Not applicable",
                status="N/A",
                reason=f"{state.preconditioner.label} owns no RapidRBF local-factor decision.",
            ),
        )

    rows: list[AxisRow] = []
    for field, item, index in _axis_variants(state):
        candidate_state = replace(state, **{field: index})
        candidate_status = assess(candidate_state).status
        rows.append(
            AxisRow(
                selected=getattr(state, field) == index,
                label=getattr(item, "label"),
                status=candidate_status,
                reason=_axis_reason(item),
            )
        )
    return tuple(rows)


def transition(state: LabState, command: str) -> LabState:
    """Return the next state while explaining ignored/inapplicable controls."""

    command = command.strip().lower()
    if command == "r":
        return LabState(notice="Lab reset; no evidence or decision was persisted.")
    if command == "m" and state.krylov.fixed_window is not None:
        return replace(
            state,
            notice=(
                f"{state.krylov.label} fixes its comparison window/cap at "
                f"{state.krylov.fixed_window}; [m] is intentionally ignored."
            ),
        )
    if command in {"d", "l", "f", "c"} and not state.preconditioner.factor_store_required:
        return replace(
            state,
            notice=(
                f"{state.preconditioner.label} has no RapidRBF dense/local-factor decision."
            ),
        )
    if command == "c" and state.factor_store.reservation_mode != "selected-cap":
        return replace(
            state,
            notice=f"{state.factor_store.label} does not use the explicit cap control.",
        )

    transitions = {
        "s": ("workload_index", len(WORKLOADS), "Canonical prototype case changed."),
        "d": ("dense_index", len(DENSE_CHOICES), "Dense substrate changed."),
        "k": ("krylov_index", len(KRYLOV_CHOICES), "Krylov variant changed."),
        "a": (
            "orthogonalization_index",
            len(ORTHOGONALIZATION_CHOICES),
            "Orthogonalization policy changed.",
        ),
        "l": (
            "factor_algorithm_index",
            len(FACTOR_ALGORITHMS),
            "Local/coarse factor policy changed.",
        ),
        "p": (
            "preconditioner_index",
            len(PRECONDITIONERS),
            "Preconditioner topology changed.",
        ),
        "f": (
            "factor_store_index",
            len(FACTOR_STORES),
            "Factor-store policy changed.",
        ),
        "o": (
            "observation_index",
            len(OBSERVATION_POLICIES),
            "Algebraic observation schedule changed; terminal authority did not.",
        ),
        "t": ("thread_index", len(THREAD_POLICIES), "Thread policy changed."),
        "n": (
            "thread_lane_index",
            len(THREAD_LANES),
            "Canonical configured-thread lane changed.",
        ),
        "b": ("budget_index", len(BUDGET_POLICIES), "Complete work-budget policy changed."),
        "x": (
            "execution_lane_index",
            len(EXECUTION_LANES),
            "Execution lifecycle/affinity/cache lane changed.",
        ),
        "y": ("platform_index", len(PLATFORMS), "Tier-one evidence platform changed."),
        "m": ("window_index", len(WINDOWS), "Krylov window changed."),
        "g": ("grant_index", len(MEMORY_GRANTS_GIB), "Total memory grant changed."),
        "c": ("factor_cap_index", len(FACTOR_CAPS_GIB), "Explicit factor/workspace cap changed."),
        "e": (
            "evidence_index",
            len(EVIDENCE_PROFILES),
            "Evidence view changed; WHAT-IF views remain counterfactual.",
        ),
        "v": ("axis_index", len(AXES), "Comparison axis changed."),
    }
    if command not in transitions:
        return replace(state, notice=f"Unknown command: {command!r}.")
    field, size, notice = transitions[command]
    return replace(state, **{field: _cycle(getattr(state, field), size)}, notice=notice)
