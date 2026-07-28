#!/usr/bin/env python3
"""Terminal viewer for the captured local/coarse dense-factor prototype."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
from typing import Any, Iterable, Mapping, Sequence


PROTOTYPE_DIR = Path(__file__).resolve().parent
EVIDENCE_DIR = PROTOTYPE_DIR / "evidence"
RESULTS_DIR = PROTOTYPE_DIR / "results"
UI_SCHEMA = "rapidrbf-dense-factor-ui-summary-v1"
BACKEND_ORDER = ("faer", "nalgebra", "mkl")
VIEWS = ("overview", "certificates", "resources", "closure")
MISSING = "EVIDENCE_MISSING"
COLLECTED = "COLLECTED, UNJUDGED"


class TuiError(RuntimeError):
    """A user-actionable viewer failure."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TuiError(f"summary does not exist: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TuiError(f"cannot read JSON summary {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TuiError(f"expected a JSON object in {path}")
    return value


def _summary_candidates() -> list[Path]:
    """Prefer a checked-in evidence summary over generated results."""

    committed: list[Path] = []
    if EVIDENCE_DIR.is_dir():
        committed = sorted(
            {
                *EVIDENCE_DIR.glob("summary*.json"),
                *EVIDENCE_DIR.glob("*summary.json"),
                *EVIDENCE_DIR.glob("evidence-summary*.json"),
            },
            key=lambda path: path.name.lower(),
        )

    generated = [RESULTS_DIR / "summary.json"]
    summary_root = RESULTS_DIR / "summaries"
    if summary_root.is_dir():
        addressed = list(summary_root.glob("sha256-*/summary.json"))
        addressed.sort(
            key=lambda path: path.stat().st_mtime_ns if path.exists() else 0,
            reverse=True,
        )
        generated.extend(addressed)
    return [path for path in [*committed, *generated] if path.is_file()]


def _latest_raw_manifest() -> Path | None:
    candidates = [RESULTS_DIR / "corpus" / "manifest.raw.json"]
    corpora = RESULTS_DIR / "corpora"
    if corpora.is_dir():
        candidates.extend(corpora.glob("sha256-*/manifest.raw.json"))
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime_ns)


def _record_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "record_id",
        "panel_id",
        "case_id",
        "role",
        "assembly_variant",
        "assembly_authority",
        "matrix_kind",
        "registered_rank_expectation",
        "semantic_rank_state",
        "scalar_order",
        "polynomial_order",
        "reduced_order",
    )
    return {key: record.get(key) for key in keys}


def _missing_summary() -> tuple[dict[str, Any], str]:
    manifest_path = _latest_raw_manifest()
    records: list[dict[str, Any]] = []
    corpus: dict[str, Any] = {
        "schema": None,
        "record_count": 0,
        "records": records,
    }
    reason = "No committed or generated evidence summary was found."
    source = "synthetic missing-evidence state"
    if manifest_path is not None:
        manifest = _load_json(manifest_path)
        raw_records = manifest.get("records")
        if isinstance(raw_records, list):
            records.extend(
                _record_projection(record)
                for record in raw_records
                if isinstance(record, dict)
            )
        corpus.update(
            {
                "schema": manifest.get("schema"),
                "generator": manifest.get("generator"),
                "polatory_commit": manifest.get("polatory_commit"),
                "record_count": len(records),
            }
        )
        reason = (
            "A raw capture exists, but no replay evidence summary has been "
            "published. Run run.py --recapture."
        )
        source = str(manifest_path)

    return (
        {
            "schema": UI_SCHEMA,
            "evidence_state": MISSING,
            "judgement": "UNJUDGED",
            "reason": reason,
            "corpus": corpus,
            "attempts": [],
            "controls": [],
            "artifact_closure": {
                "state": MISSING,
                "note": "No closure evidence summary was reported.",
            },
            "m3_literal_canonical": {
                "state": MISSING,
                "comparison": "not replayed",
            },
        },
        source,
    )


def _load_default_summary(override: Path | None) -> tuple[dict[str, Any], str]:
    if override is not None:
        resolved = override.resolve()
        return _load_json(resolved), str(resolved)
    candidates = _summary_candidates()
    if candidates:
        return _load_json(candidates[0]), str(candidates[0])
    return _missing_summary()


def _at(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _pick(value: Any, *paths: str, default: Any = None) -> Any:
    for path in paths:
        candidate = _at(value, path)
        if candidate is not None:
            return candidate
    return default


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _one_line(value: Any) -> str:
    if value is None or value == "":
        return "NOT REPORTED"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return f"{value:.6e}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def _human_bytes(value: Any) -> str:
    if value is None:
        return "NOT REPORTED"
    if isinstance(value, str):
        try:
            numeric = int(value)
        except ValueError:
            return value
    elif isinstance(value, (int, float)) and math.isfinite(float(value)):
        numeric = int(value)
    else:
        return _one_line(value)
    units = ("B", "KiB", "MiB", "GiB")
    scaled = float(numeric)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if abs(scaled) < 1024.0 or candidate == units[-1]:
            break
        scaled /= 1024.0
    return f"{numeric:,} B ({scaled:.2f} {unit})"


def _shorten(value: Any, limit: int) -> str:
    text = _one_line(value)
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)] + "..."


def _field(label: str, value: Any, width: int, *, indent: int = 2) -> list[str]:
    label_width = min(28, max(18, width // 4))
    prefix = " " * indent + f"{label:<{label_width}} "
    available = max(12, width - len(prefix))
    wrapped = textwrap.wrap(
        _one_line(value),
        width=available,
        replace_whitespace=False,
        drop_whitespace=True,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]
    lines = [prefix + wrapped[0]]
    continuation = " " * len(prefix)
    lines.extend(continuation + line for line in wrapped[1:])
    return lines


def _section(title: str, rows: Iterable[tuple[str, Any]], width: int) -> list[str]:
    lines = ["", f" {title}", " " + "-" * max(1, min(width - 2, len(title) + 5))]
    for label, value in rows:
        lines.extend(_field(label, value, width))
    return lines


def _state(summary: Mapping[str, Any], attempts: Sequence[Mapping[str, Any]]) -> str:
    explicit = summary.get("evidence_state")
    if isinstance(explicit, str):
        return explicit
    coverage_complete = _pick(summary, "scope.coverage.complete")
    if coverage_complete is not None:
        return COLLECTED if coverage_complete is True else MISSING
    if any(
        str(
            attempt.get("collection_state")
            or attempt.get("attempt_state")
            or attempt.get("state")
            or ""
        ).startswith("COLLECTED")
        for attempt in attempts
    ):
        return COLLECTED
    return MISSING


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("record_id") or record.get("id") or "<no captured block>")


def _backend_name(attempt: Mapping[str, Any]) -> str:
    return str(attempt.get("backend") or "<not collected>")


def _backend_key(backend: str) -> str:
    return "mkl" if "mkl" in backend.lower() else backend.lower()


def _scope_key(record: str | None, backend: str | None) -> str:
    if record is None and backend is None:
        return "all"
    label_parts: list[str] = []
    for name, value in (("record", record), ("backend", backend)):
        if value is None:
            continue
        slug = "".join(
            character if character.isalnum() or character in "-._" else "-"
            for character in value
        ).strip("-._")
        label_parts.append(f"{name}-{slug[:48] or 'empty'}")
    identity = json.dumps(
        {"record": record, "backend": backend},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{'__'.join(label_parts)}--{hashlib.sha256(identity).hexdigest()[:12]}"


@dataclass
class Dashboard:
    summary: dict[str, Any]
    source: str
    records: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    backends: list[str]
    record_index: int = 0
    backend_index: int = 0
    view_index: int = 0

    @classmethod
    def from_summary(cls, summary: dict[str, Any], source: str) -> "Dashboard":
        raw_records = _pick(summary, "corpus.records", "records", default=[])
        records = [
            dict(record)
            for record in _as_list(raw_records)
            if isinstance(record, Mapping)
        ]
        raw_attempts = _pick(
            summary, "attempts", "replay.attempts", default=[]
        )
        attempts = [
            dict(attempt)
            for attempt in _as_list(raw_attempts)
            if isinstance(attempt, Mapping)
        ]

        known_ids = {_record_id(record) for record in records}
        for attempt in attempts:
            attempt_id = str(attempt.get("record_id") or "")
            if attempt_id and attempt_id not in known_ids:
                records.append(
                    {
                        "record_id": attempt_id,
                        "panel_id": attempt.get("panel_id"),
                        "case_id": attempt.get("case_id"),
                        "role": attempt.get("role"),
                        "assembly_variant": attempt.get("assembly_variant"),
                        "assembly_authority": attempt.get("assembly_authority"),
                        "matrix_kind": attempt.get("matrix_kind"),
                        "registered_rank_expectation": attempt.get(
                            "registered_rank_expectation"
                        ),
                        "semantic_rank_state": attempt.get("semantic_rank_state"),
                    }
                )
                known_ids.add(attempt_id)
        expected_record_ids = _pick(
            summary, "scope.expected_record_ids", default=[]
        )
        if (
            _pick(summary, "scope.kind") == "filtered"
            and isinstance(expected_record_ids, list)
        ):
            expected = {str(record_id) for record_id in expected_record_ids}
            records = [
                record for record in records if _record_id(record) in expected
            ]
        if not records:
            records = [{"record_id": "<no captured block>"}]

        observed = {
            _backend_name(attempt)
            for attempt in attempts
            if attempt.get("backend") is not None
        }
        backends = []
        for wanted in BACKEND_ORDER:
            matching = sorted(
                backend for backend in observed if _backend_key(backend) == wanted
            )
            backends.extend(matching)
        backends.extend(sorted(observed - set(backends)))
        if not backends:
            backends = list(BACKEND_ORDER)
        return cls(summary, source, records, attempts, backends)

    @property
    def record(self) -> dict[str, Any]:
        return self.records[self.record_index % len(self.records)]

    @property
    def backend(self) -> str:
        return self.backends[self.backend_index % len(self.backends)]

    @property
    def view(self) -> str:
        return VIEWS[self.view_index % len(VIEWS)]

    @property
    def attempt(self) -> dict[str, Any]:
        wanted = _record_id(self.record)
        for attempt in self.attempts:
            if (
                str(attempt.get("record_id")) == wanted
                and str(attempt.get("backend")) == self.backend
            ):
                return attempt
        return {
            "record_id": wanted,
            "backend": self.backend,
            "attempt_state": MISSING,
            "diagnostics": ["No attempt was reported for this block/backend pair."],
        }

    def move_record(self, delta: int) -> None:
        self.record_index = (self.record_index + delta) % len(self.records)

    def move_backend(self) -> None:
        self.backend_index = (self.backend_index + 1) % len(self.backends)

    def move_view(self) -> None:
        self.view_index = (self.view_index + 1) % len(VIEWS)


def _m3_pair(
    dashboard: Dashboard,
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    role = dashboard.record.get("role")
    same_backend = [
        attempt
        for attempt in dashboard.attempts
        if str(attempt.get("backend")) == dashboard.backend
        and str(attempt.get("record_id", "")).startswith("M3-")
        and (role is None or attempt.get("role") == role)
    ]
    canonical = next(
        (
            attempt
            for attempt in same_backend
            if attempt.get("assembly_variant") == "canonical-row-channel-map"
        ),
        None,
    )
    literal = next(
        (
            attempt
            for attempt in same_backend
            if attempt.get("assembly_variant") != "canonical-row-channel-map"
        ),
        None,
    )
    return canonical, literal


def _m3_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    canonical, literal = _m3_pair(dashboard)
    replay_audit = _pick(
        dashboard.summary,
        "m3_literal_canonical.replay_audit",
        "corpus.m3_assembly_audit",
    )
    summary_state = _pick(
        dashboard.summary, "m3_literal_canonical.state"
    )
    audit_items = replay_audit if isinstance(replay_audit, list) else []
    if summary_state is None:
        summary_state = (
            COLLECTED
            if audit_items
            and all(
                isinstance(item, Mapping)
                and str(item.get("state", "")).startswith("COLLECTED")
                for item in audit_items
            )
            else MISSING
        )
    audit_disagreement: list[str] = []
    for item in audit_items:
        if not isinstance(item, Mapping):
            continue
        comparisons = []
        for field in ("b_lower", "rhs_reduced"):
            byte_equal = _pick(item, f"{field}.byte_equal")
            if byte_equal is not None:
                comparisons.append(
                    f"{field}={'equal' if byte_equal else 'DIFFERENT'}"
                )
        if comparisons:
            audit_disagreement.append(
                f"{_one_line(item.get('role'))}: {', '.join(comparisons)}"
            )
    audit_display = (
        f"{len(audit_items)} role comparison(s); hashes retained in source summary"
        if audit_items
        else replay_audit
    )
    if canonical is None or literal is None:
        return [
            ("comparison state", summary_state),
            ("replay assembly audit", audit_display),
            (
                "captured payload disagreement",
                "; ".join(audit_disagreement)
                if audit_disagreement
                else "NOT EVALUATED",
            ),
            ("canonical attempt", "NOT COLLECTED"),
            ("literal attempt", "NOT COLLECTED"),
            (
                "factor-attempt disagreement",
                "NOT EVALUATED - both assembly variants are required",
            ),
            ("semantic verdict", "UNJUDGED"),
        ]

    canonical_status = _pick(canonical, "factor.status", "attempt_state")
    literal_status = _pick(literal, "factor.status", "attempt_state")
    canonical_residual = _pick(
        canonical, "solve.reduced_backward_error", "residual.reduced"
    )
    literal_residual = _pick(
        literal, "solve.reduced_backward_error", "residual.reduced"
    )
    status_disagreement = canonical_status != literal_status
    if isinstance(canonical_residual, (int, float)) and isinstance(
        literal_residual, (int, float)
    ):
        residual_delta: Any = abs(float(canonical_residual) - float(literal_residual))
    else:
        residual_delta = "NOT EVALUATED"
    return [
        ("comparison state", summary_state),
        ("replay assembly audit", audit_display),
        (
            "captured payload disagreement",
            "; ".join(audit_disagreement)
            if audit_disagreement
            else "NOT EVALUATED",
        ),
        (
            "canonical factor / residual",
            f"{_one_line(canonical_status)} / {_one_line(canonical_residual)}",
        ),
        (
            "literal factor / residual",
            f"{_one_line(literal_status)} / {_one_line(literal_residual)}",
        ),
        ("factor-status disagreement", status_disagreement),
        ("residual absolute delta", residual_delta),
        ("semantic verdict", "UNJUDGED"),
    ]


def _identity_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    record = dashboard.record
    attempt = dashboard.attempt
    return [
        ("case", record.get("case_id")),
        ("captured block", _record_id(record)),
        ("panel / role", f"{_one_line(record.get('panel_id'))} / {_one_line(record.get('role'))}"),
        ("assembly variant", _pick(attempt, "assembly_variant", default=record.get("assembly_variant"))),
        ("backend attempt", f"{dashboard.backend} @ {_one_line(attempt.get('backend_version'))}"),
        ("collection state", _pick(attempt, "collection_state", default=MISSING)),
        ("normalized factor state", _pick(attempt, "factor_state.normalized", default=MISSING)),
        ("backend observation", _pick(attempt, "attempt_state", "state", default=MISSING)),
    ]


def _semantic_factor_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    record = dashboard.record
    attempt = dashboard.attempt
    finite_gate = attempt.get("finite_gate")
    factor_health_profile = _at(
        dashboard.summary, "policy.factor_health_profile"
    )
    if factor_health_profile is None:
        factor_health_profile = "ABSENT (no profile id/hash supplied)"
    return [
        ("assembly authority", _pick(attempt, "assembly_authority", default=record.get("assembly_authority"))),
        ("registered rank expectation", record.get("registered_rank_expectation")),
        ("captured rank certificate", record.get("semantic_rank_state")),
        ("semantic admission", _pick(attempt, "semantic_rank.state", "semantic_admission.state", default="NOT EVALUATED")),
        ("semantic admission reason", _pick(attempt, "semantic_admission.reason", default="NOT REPORTED")),
        ("backend rank authority", _pick(attempt, "backend_rank.semantic_authority", default=False)),
        ("FactorHealthProfile", factor_health_profile),
        ("selection / judgement", _pick(attempt, "selection", default=_pick(dashboard.summary, "policy.selection", default=dashboard.summary.get("judgement", "UNJUDGED")))),
        ("selection reason", _pick(attempt, "selection_reason", default=_pick(dashboard.summary, "policy.selection_reason", default="NOT REPORTED"))),
        ("factor health", _pick(attempt, "factor.status", "factor_health", default="NOT REPORTED")),
        ("finite input/factor/solve", finite_gate),
        ("pivot diagnostics", _pick(attempt, "factor.pivot_diagnostics", "pivot_diagnostics")),
        ("factor reconstruction", _pick(attempt, "factor.reconstruction_relative_inf", "factor.reconstruction_residual")),
    ]


def _certificate_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    attempt = dashboard.attempt
    return [
        ("solve status", _pick(attempt, "solve.status")),
        ("reduced backward residual", _pick(attempt, "solve.reduced_backward_error", "residual.reduced_backward_error")),
        (
            "full correction residual",
            _pick(
                attempt,
                "solve.full_correction.captured_augmented_matrix_residual_alpha",
                "certificates.full_correction_residual",
                "solve.full_correction_residual",
            ),
        ),
        (
            "polynomial recovery",
            _pick(
                attempt,
                "polynomial_factor.status",
                "certificates.polynomial_recovery_residual",
                "solve.polynomial_recovery_residual",
            ),
        ),
        (
            "CPD side-condition",
            _pick(
                attempt,
                "solve.full_correction.cpd_orthogonality_eta",
                "certificates.cpd_side_condition_residual",
                "solve.cpd_side_condition_residual",
            ),
        ),
        (
            "external evaluator",
            _pick(
                attempt,
                "solve.full_correction.external_value_gradient_evaluator",
            ),
        ),
    ]


def _packing_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    attempt = dashboard.attempt
    record = dashboard.record
    return [
        ("source matrix kind", record.get("matrix_kind")),
        ("source packing", _pick(attempt, "packing.source", default="lower triangle, captured row order")),
        ("factor packing capability", _pick(attempt, "packing.capability", "packing.factor")),
        ("packing roundtrip tested", _pick(attempt, "packing.roundtrip_tested")),
        ("packed factor bytes", _human_bytes(_pick(attempt, "packing.packed_bytes"))),
    ]


def _resource_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    attempt = dashboard.attempt
    retained = _pick(
        attempt, "resources.retained_bytes", "storage.retained_bytes"
    )
    if retained is None:
        retained_lower_bound = _pick(
            attempt,
            "resources.retained_lower_bound_bytes",
            "storage.retained_lower_bound_bytes",
        )
        retained_display = (
            f">= {_human_bytes(retained_lower_bound)}"
            if retained_lower_bound is not None
            else "NOT REPORTED"
        )
    else:
        retained_display = _human_bytes(retained)
    return [
        ("retained storage", retained_display),
        ("transient peak delta", _human_bytes(_pick(attempt, "resources.transient_peak_delta_bytes", "storage.transient_bytes"))),
        ("temporary storage", _human_bytes(_pick(attempt, "resources.temp_storage_bytes", "storage.temp_bytes"))),
        ("thread ownership", _pick(attempt, "resources.thread_ownership", "threads.ownership")),
        ("requested threads", _pick(attempt, "resources.requested_threads", "threads.requested")),
        ("observed / max-live", f"{_one_line(_pick(attempt, 'resources.observed_threads', 'threads.observed'))} / {_one_line(_pick(attempt, 'resources.maximum_live_threads', 'threads.maximum_live'))}"),
    ]


def _closure_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    attempt = dashboard.attempt
    closure = attempt.get("artifact_closure")
    if closure is None:
        closure = dashboard.summary.get("artifact_closure")
    return [
        ("closure state", _pick(closure, "state", default=closure)),
        ("coordinates", _pick(closure, "coordinates", "coordinate")),
        ("runtime closure bytes", _human_bytes(_pick(closure, "runtime_bytes", "runtime_closure_bytes"))),
        ("installed closure bytes", _human_bytes(_pick(closure, "installed_bytes", "installed_closure_bytes"))),
        ("license / source", _pick(closure, "license", "license_state", "source")),
        ("closure notes", _pick(closure, "notes", "note")),
    ]


def _diagnostic_rows(dashboard: Dashboard) -> list[tuple[str, Any]]:
    diagnostics = _as_list(dashboard.attempt.get("diagnostics"))
    controls = _as_list(dashboard.summary.get("controls"))
    return [
        ("attempt diagnostics", diagnostics or "none reported"),
        ("corpus controls", controls or "none reported"),
    ]


def render(dashboard: Dashboard, width: int) -> str:
    width = max(72, min(width, 160))
    state = _state(dashboard.summary, dashboard.attempts)
    title = "RapidRBF dense-factor replay - THROWAWAY WAYFINDER EVIDENCE"
    lines = [
        title[:width],
        "=" * min(width, len(title)),
        f" state: {state}    judgement: UNJUDGED    view: {dashboard.view}",
        f" source: {_shorten(dashboard.source, max(20, width - 9))}",
        f" block {dashboard.record_index + 1}/{len(dashboard.records)}    "
        f"backend {dashboard.backend_index + 1}/{len(dashboard.backends)}",
    ]
    reason = dashboard.summary.get("reason")
    if reason:
        lines.extend(_section("WHY EVIDENCE IS MISSING", [("reason", reason)], width))

    lines.extend(_section("CASE / BLOCK / BACKEND ATTEMPT", _identity_rows(dashboard), width))
    lines.extend(_section("SEMANTIC ADMISSION vs FACTOR HEALTH", _semantic_factor_rows(dashboard), width))

    if dashboard.view in ("overview", "certificates"):
        lines.extend(_section("EXTERNAL CERTIFICATES / RESIDUALS", _certificate_rows(dashboard), width))
    if dashboard.view in ("overview", "resources"):
        lines.extend(_section("PACKING", _packing_rows(dashboard), width))
        lines.extend(_section("STORAGE AND THREAD OWNERSHIP", _resource_rows(dashboard), width))
    if dashboard.view in ("overview", "closure"):
        lines.extend(_section("ARTIFACT CLOSURE", _closure_rows(dashboard), width))

    lines.extend(_section("M3 LITERAL vs CANONICAL", _m3_rows(dashboard), width))
    if dashboard.view != "overview":
        lines.extend(_section("DIAGNOSTICS", _diagnostic_rows(dashboard), width))
    lines.extend(
        [
            "",
            " j/k block  b backend  v view  r replay selected lock  "
            "a recapture+replay all  q quit",
        ]
    )
    return "\n".join(lines)


def _rerun(dashboard: Dashboard, selected: bool) -> tuple[dict[str, Any], str] | None:
    scope = (
        f"{_record_id(dashboard.record)} on {dashboard.backend}"
        if selected
        else "the complete audit"
    )
    action = (
        "Verify the locked corpus and replay"
        if selected
        else "Recapture the frozen corpus and replay"
    )
    answer = input(f"{action} {scope}? Type YES to continue: ").strip()
    if answer != "YES":
        return None
    command = [
        sys.executable,
        str(PROTOTYPE_DIR / "run.py"),
        "--replay-only" if selected else "--recapture",
    ]
    if selected:
        digest = _pick(dashboard.summary, "corpus.sha256")
        if isinstance(digest, str) and digest:
            corpus = RESULTS_DIR / "corpora" / f"sha256-{digest}"
            if corpus.is_dir():
                command.extend(["--corpus", str(corpus)])
        command.extend(
            [
                "--record",
                _record_id(dashboard.record),
                "--backend",
                _backend_key(dashboard.backend),
            ]
        )
    completed = subprocess.run(command, cwd=PROTOTYPE_DIR, check=False)
    if completed.returncode != 0:
        input(f"Replay driver exited {completed.returncode}. Press Enter.")
        return None
    if selected:
        digest = _pick(dashboard.summary, "corpus.sha256")
        if not isinstance(digest, str) or not digest:
            input("Replay completed but the corpus digest is unavailable. Press Enter.")
            return None
        key = _scope_key(
            _record_id(dashboard.record), _backend_key(dashboard.backend)
        )
        generated = (
            RESULTS_DIR
            / "summaries"
            / f"sha256-{digest}"
            / "scopes"
            / key
            / "summary.json"
        )
    else:
        generated = RESULTS_DIR / "summary.json"
    if generated.is_file():
        return _load_json(generated), str(generated.resolve())
    return _load_default_summary(None)


def _interactive(dashboard: Dashboard, width: int) -> int:
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(render(dashboard, width))
        try:
            command = input(" command> ").strip().lower()[:1]
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if command == "q":
            return 0
        if command == "j":
            dashboard.move_record(1)
        elif command == "k":
            dashboard.move_record(-1)
        elif command == "b":
            dashboard.move_backend()
        elif command == "v":
            dashboard.move_view()
        elif command in ("r", "a"):
            refreshed = _rerun(dashboard, command == "r")
            if refreshed is not None:
                dashboard = Dashboard.from_summary(*refreshed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect captured dense-factor replay evidence. A checked-in summary "
            "under evidence/ wins over generated results/summary.json."
        )
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="explicit JSON summary instead of the default evidence search",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="print one complete non-interactive frame and exit",
    )
    parser.add_argument(
        "--width",
        type=int,
        help="render width (default: current terminal, clamped to 72..160)",
    )
    parser.add_argument("--record", help="initial captured record id")
    parser.add_argument(
        "--backend",
        choices=BACKEND_ORDER,
        help="initial backend",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary, source = _load_default_summary(args.summary)
        dashboard = Dashboard.from_summary(summary, source)
    except TuiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.record:
        for index, record in enumerate(dashboard.records):
            if _record_id(record) == args.record:
                dashboard.record_index = index
                break
        else:
            print(f"error: record not found in summary: {args.record}", file=sys.stderr)
            return 2
    if args.backend:
        matching = next(
            (
                index
                for index, backend in enumerate(dashboard.backends)
                if _backend_key(backend) == args.backend
            ),
            None,
        )
        if matching is None:
            dashboard.backends.append(args.backend)
            matching = len(dashboard.backends) - 1
        dashboard.backend_index = matching

    width = args.width or shutil.get_terminal_size(fallback=(108, 30)).columns
    width = max(72, min(width, 160))
    if args.snapshot or not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(render(dashboard, width))
        return 0
    return _interactive(dashboard, width)


if __name__ == "__main__":
    raise SystemExit(main())
