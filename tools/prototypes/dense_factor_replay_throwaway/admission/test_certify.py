from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from unittest import mock

import numpy as np

import certify

HERE = Path(__file__).resolve().parent


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = certify.load_profile(HERE / "rank-scaling-profile.v1.json")

    def test_profile_hash_is_frozen(self) -> None:
        self.assertEqual(
            self.profile["profile_hash"], certify.profile_digest(self.profile)
        )
        self.assertEqual(self.profile["profile_hash"], certify.CANONICAL_PROFILE_HASH)
        inventory = self.profile["inventory"]
        self.assertEqual(
            (
                inventory["workload_count"],
                inventory["block_count"],
                inventory["carried_factor_source_count"],
                inventory["generator_auxiliary_p_top_count"],
                inventory["rank_certificate_count"],
                inventory["q_certificate_count"],
            ),
            (12, 204, 216, 12, 420, 204),
        )

    def test_self_consistent_profile_semantic_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            drifted = json.loads(json.dumps(self.profile))
            drifted["q_nullspace"]["cpd_level_limit"] = "1"
            drifted["profile_hash"] = certify.profile_digest(drifted)
            path = Path(temporary) / "drifted-profile.json"
            path.write_text(json.dumps(drifted), encoding="utf-8")
            with self.assertRaises(certify.CorpusError) as caught:
                certify.load_profile(path)
        self.assertEqual(caught.exception.state, "IntegrityMismatch")
        self.assertIn("pinned canonical", caught.exception.reason)

    def test_validated_profile_is_an_independent_canonical_snapshot(self) -> None:
        source = json.loads(json.dumps(self.profile))
        validated = certify.validate_profile(source)
        source["rank_rule"]["tau_rank"] = "0.99"
        self.assertNotEqual(
            source["rank_rule"]["tau_rank"],
            validated["rank_rule"]["tau_rank"],
        )
        self.assertEqual(validated["profile_hash"], certify.CANONICAL_PROFILE_HASH)

    def test_execution_provenance_binds_source_runtime_and_threads(self) -> None:
        provenance = certify.execution_provenance(HERE / "rank-scaling-profile.v1.json")
        closure = provenance["source_closure"]
        self.assertEqual(
            [record["path"] for record in closure["files"]],
            [
                "certify.py",
                "exact_rank.py",
                "pyproject.toml",
                "rank-scaling-profile.v1.json",
                "uv.lock",
            ],
        )
        self.assertEqual(len(closure["sha256"]), 64)
        runtime = provenance["runtime"]
        self.assertEqual(runtime["numpy_version"], np.__version__)
        self.assertIn("OPENBLAS_NUM_THREADS", runtime["thread_environment"])
        self.assertIn("version", runtime["blas"])
        self.assertEqual(runtime["threadpoolctl_version"], "3.6.0")
        openblas = [
            item
            for item in runtime["loaded_threadpools"]
            if item["internal_api"] == "openblas"
        ]
        self.assertTrue(openblas)
        self.assertTrue(all(item["binary"]["sha256"] for item in openblas))

    def test_execution_coordinate_rejects_unrelated_or_extra_blas(self) -> None:
        provenance = certify.execution_provenance(HERE / "rank-scaling-profile.v1.json")
        unrelated = json.loads(json.dumps(provenance))
        unrelated["runtime"]["blas"]["name"] = "mkl"
        with self.assertRaises(certify.CorpusError) as caught:
            certify.validate_execution_coordinate(self.profile, unrelated)
        self.assertEqual(caught.exception.state, "EVIDENCE_MISSING")

        extra = json.loads(json.dumps(provenance))
        extra["runtime"]["loaded_threadpools"].append(
            {
                "user_api": "blas",
                "internal_api": "openblas",
                "prefix": "unrelated",
                "num_threads": 16,
                "version": "0",
                "threading_layer": "pthreads",
                "architecture": "unknown",
                "binary": {
                    "basename": "unrelated.dll",
                    "bytes": 1,
                    "sha256": "0" * 64,
                },
            }
        )
        with self.assertRaises(certify.CorpusError) as caught:
            certify.validate_execution_coordinate(self.profile, extra)
        self.assertEqual(caught.exception.state, "EVIDENCE_MISSING")

    def test_captured_profile_bytes_close_provenance_toctou(self) -> None:
        original = (HERE / "rank-scaling-profile.v1.json").read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_bytes(original)
            path.write_bytes(b'{"changed":true}')
            provenance = certify.execution_provenance(path, original)
        profile_record = next(
            record
            for record in provenance["source_closure"]["files"]
            if record["path"] == "rank-scaling-profile.v1.json"
        )
        self.assertEqual(profile_record["sha256"], certify.sha256_bytes(original))

    def test_malformed_profile_variants_publish_stable_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, payload in enumerate((b"[]", b"\xff\xfe")):
                profile = root / f"profile-{index}.json"
                output = root / f"diagnostic-{index}.json"
                profile.write_bytes(payload)
                status = certify.main(
                    ["--profile", str(profile), "--output", str(output)]
                )
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(status, 2)
                self.assertEqual(report["state"], "MalformedCorpus")
                self.assertEqual(report["backend_invocations"], 0)

    def test_programmatic_semantic_entry_revalidates_profile_pin(self) -> None:
        drifted = json.loads(json.dumps(self.profile))
        drifted["rank_rule"]["tau_rank"] = "0.99"
        drifted["profile_hash"] = certify.profile_digest(drifted)
        with self.assertRaises(certify.CorpusError) as caught:
            certify.certify_corpus(Path("unused.json"), drifted)
        self.assertEqual(caught.exception.state, "IntegrityMismatch")

    def test_concurrent_fresh_publish_has_one_complete_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "evidence.json"
            payloads = [f'{{"writer":{index}}}\n' for index in range(8)]

            def publish(payload: str) -> bool:
                try:
                    certify.publish_text_fresh(target, payload)
                except OSError:
                    return False
                return True

            with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
                outcomes = list(executor.map(publish, payloads))
            self.assertEqual(outcomes.count(True), 1)
            self.assertIn(target.read_text(encoding="utf-8"), payloads)
            self.assertEqual(
                list(target.parent.glob(f".{target.name}.*.tmp")),
                [],
            )

    def test_cli_rejection_is_published_to_a_fresh_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "rejection.json"
            status = certify.main(
                [
                    "--profile",
                    str(HERE / "rank-scaling-profile.v1.json"),
                    "--output",
                    str(output),
                ]
            )
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(status, 2)
        self.assertEqual(report["state"], "MalformedCorpus")
        self.assertEqual(report["backend_invocations"], 0)
        self.assertIn("execution", report)

    def test_cli_refuses_to_overwrite_prior_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "prior.json"
            sentinel = b"prior admitted evidence\n"
            output.write_bytes(sentinel)
            with mock.patch.object(
                certify,
                "execution_provenance",
                side_effect=AssertionError("existing output should fail early"),
            ):
                status = certify.main(
                    [
                        "--profile",
                        str(HERE / "rank-scaling-profile.v1.json"),
                        "--output",
                        str(output),
                    ]
                )
            preserved = output.read_bytes()
        self.assertEqual(status, 2)
        self.assertEqual(preserved, sentinel)

    def test_missing_profile_diagnostic_does_not_leak_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "private" / "missing-profile.json"
            output = root / "diagnostic.json"
            status = certify.main(["--profile", str(missing), "--output", str(output)])
            text = output.read_text(encoding="utf-8")
            report = json.loads(text)
        self.assertEqual(status, 2)
        self.assertEqual(report["state"], "MalformedCorpus")
        self.assertNotIn(str(missing), text)
        self.assertIn("FileNotFoundError", report["reason"])

    def test_runtime_sampling_failure_is_stable_and_published(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "runtime-diagnostic.json"
            with mock.patch.object(
                certify,
                "distribution_version",
                side_effect=certify.PackageNotFoundError,
            ):
                status = certify.main(
                    [
                        "--profile",
                        str(HERE / "rank-scaling-profile.v1.json"),
                        "--output",
                        str(output),
                    ]
                )
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(status, 2)
        self.assertEqual(report["state"], "EVIDENCE_MISSING")
        self.assertIn("threadpoolctl", report["reason"])

    def test_tau_uses_unit_roundoff_not_machine_epsilon(self) -> None:
        self.assertEqual(certify.tau_rank((4, 4)), 2.0**-51)

    def test_f64_analytic_checker_admits_identity(self) -> None:
        certificate = certify.rank_certificate(
            "identity", "CONTROL", np.eye(4), self.profile
        )
        self.assertEqual(certificate["state"], "Admitted")
        self.assertEqual(certificate["backend_invocations"], 0)
        self.assertGreater(certificate["steps"][0]["lower"], certificate["tau_rank"])

    def test_exact_singular_control_fails_rank(self) -> None:
        certificate = certify.rank_certificate(
            "singular", "CONTROL", np.diag([1.0, 0.0]), self.profile
        )
        self.assertEqual(certificate["state"], "RankDeficient")
        self.assertEqual(certificate["backend_invocations"], 0)
        self.assertEqual(certificate["steps"][0]["lower"], 0.0)
        self.assertEqual(certificate["steps"][0]["upper"], 0.0)
        self.assertEqual(certificate["steps"][0]["width"], 0.0)
        self.assertEqual(certificate["steps"][0]["width_binary64_hex"], "0x0.0p+0")
        self.assertEqual(
            certificate["steps"][0]["authority"],
            "exact-zero-row-or-column-dyadic",
        )

    def test_true_final_straddle_is_indeterminate(self) -> None:
        tau = certify.tau_rank((4, 4))
        initial = certify.RatioEnvelope(
            tau - tau / 16, tau + tau / 16, "test-envelope", 53
        )

        def provider(bits: int) -> certify.RatioEnvelope:
            return certify.RatioEnvelope(
                tau - tau / 32, tau + tau / 32, "test-envelope", bits
            )

        state, steps, _reason = certify.drive_precision_ladder(
            initial,
            tau,
            self.profile["rank_rule"]["precision_ladder_bits"],
            provider,
        )
        self.assertEqual(state, "IndeterminateRank")
        self.assertEqual(
            [step["precision_bits"] for step in steps], [53, 256, 512, 1024, 2048]
        )
        self.assertLessEqual(steps[-1]["width"], tau / 8)

    def test_unavailable_ladder_fails_closed(self) -> None:
        tau = certify.tau_rank((4, 4))
        state, _steps, reason = certify.drive_precision_ladder(
            certify.RatioEnvelope(0.0, tau * 2, "test-envelope", 53),
            tau,
            self.profile["rank_rule"]["precision_ladder_bits"],
            None,
        )
        self.assertEqual(state, "EVIDENCE_MISSING")
        self.assertIn("not installed", reason)

    def test_resource_denial_during_ladder_is_missing_evidence(self) -> None:
        tau = certify.tau_rank((4, 4))

        def denied_provider(_bits: int) -> certify.RatioEnvelope:
            raise certify.PrecisionResourceDenied

        state, steps, reason = certify.drive_precision_ladder(
            certify.RatioEnvelope(tau - tau / 16, tau + tau / 16, "test-envelope", 53),
            tau,
            self.profile["rank_rule"]["precision_ladder_bits"],
            denied_provider,
        )
        self.assertEqual(state, "EVIDENCE_MISSING")
        self.assertEqual([step["precision_bits"] for step in steps], [53])
        self.assertIn("before the required final narrow straddle completed", reason)

    def test_corpus_resource_preflight_precedes_array_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = certify.make_synthetic_manifest(Path(temporary))
            with (
                mock.patch.object(
                    certify.Corpus,
                    "array",
                    side_effect=AssertionError(
                        "array materialized before resource denial"
                    ),
                ),
                self.assertRaises(certify.CorpusError) as caught,
            ):
                certify.certify_corpus(
                    manifest,
                    self.profile,
                    production=False,
                    max_resource_units=1,
                )
        self.assertEqual(caught.exception.state, "ResourceDenied")
        self.assertIn("before payload materialization", caught.exception.reason)

    def test_coordinate_scaling_and_derivative_mechanics(self) -> None:
        values = np.array([[0.0, 0.0, 0.0], [3.0, 1.0, -1.0]])
        gradients = np.array([[1.5, 0.25, -0.5]])
        transform = certify.coordinate_transform(values, gradients)
        self.assertEqual(transform["scale_hex"][0], float(2).hex())
        p = certify.build_polynomial_matrix(1, values, gradients, transform)
        self.assertEqual(p.shape, (5, 4))
        self.assertEqual(p[2, 1], 0.5)
        self.assertEqual(p[3, 2], 2.0)
        self.assertEqual(p[4, 3], 2.0)

    def test_synthetic_corpus_closes_rank_and_q(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = certify.make_synthetic_manifest(Path(temporary))
            report = certify.certify_corpus(manifest, self.profile, production=False)
        self.assertEqual(report["state"], "Admitted")
        self.assertEqual(report["manifest"]["path"], "hierarchy.manifest.raw.json")
        self.assertEqual(report["inventory"]["rank_certificates"], 3)
        self.assertEqual(report["inventory"]["q_certificates"], 1)
        self.assertTrue(
            report["q_certificates"][0]["qstar_exact_proof"][
                "p_transpose_qstar_exact_zero"
            ]
        )
        self.assertFalse(
            report["q_certificates"][0]["qstar_exact_proof"][
                "captured_bit_equality_required"
            ]
        )

    def test_q_eta_uses_p_transpose_infinity_norm(self) -> None:
        delta = 2.0**-30
        certificate = certify.q_nullspace_certificate(
            "eta-norm",
            np.array([[1.0], [2.0], [3.0]]),
            np.array([[-2.0, -3.0 + delta]]),
            np.array([0, 1, 2], dtype=np.int64),
            np.array([0, 1, 2], dtype=np.int64),
            np.array([], dtype=np.int64),
            3,
        )
        expected = Fraction.from_float(delta) / (
            Fraction(6, 1) * (Fraction(2, 1) + Fraction.from_float(abs(-3.0 + delta)))
        )
        self.assertEqual(
            Fraction(certificate["captured_q"]["exact_dyadic_eta"]), expected
        )

    def test_artifact_hash_mismatch_is_integrity_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = certify.make_synthetic_manifest(Path(temporary))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact = manifest["artifacts"][0]
            target = Path(temporary) / Path(*Path(artifact["path"]).parts)
            payload = bytearray(target.read_bytes())
            payload[0] ^= 1
            target.write_bytes(payload)
            with self.assertRaises(certify.CorpusError) as caught:
                certify.Corpus(manifest_path, production=False)
        self.assertEqual(caught.exception.state, "IntegrityMismatch")

    def test_materialized_duplicate_control_is_exact_and_pre_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = certify.make_synthetic_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            control_id = "SYNTHETIC-RANK-INVALID"
            base = np.array([[0.0, 0.0, 0.0], [0.5, 0.25, 0.75], [1.0, 1.0, 1.0]])
            mutated = base.copy()
            mutated[2, :] = mutated[1, :]
            recipe_id = certify._artifact_record(
                root,
                manifest["artifacts"],
                "control",
                control_id,
                "duplicate_coordinate_mutation",
                np.array([2, 1], dtype=np.int64),
                "contiguous",
            )
            mutated_id = certify._artifact_record(
                root,
                manifest["artifacts"],
                "control",
                control_id,
                "mutated_value_points",
                mutated,
                "row-major",
            )
            manifest["counts"]["artifacts"] += 2
            manifest["counts"]["controls"] = 1
            manifest["controls"] = [
                {
                    "control_id": control_id,
                    "base_fixture": {
                        "workload_id": manifest["workloads"][0]["workload_id"],
                        "coordinate_artifact": manifest["workloads"][0]["artifacts"][
                            "value_points"
                        ],
                    },
                    "mutation": {
                        "recipe_artifact": recipe_id,
                        "mutated_coordinate_artifact": mutated_id,
                        "destination_row": 2,
                        "source_row": 1,
                    },
                }
            ]
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            corpus = certify.Corpus(manifest_path, production=False)
            certificates = certify.certify_materialized_controls(corpus)
        self.assertEqual(len(certificates), 1)
        self.assertEqual(certificates[0]["state"], "Admitted")
        self.assertEqual(certificates[0]["observed_disposition"], "RankDeficient")
        self.assertEqual(certificates[0]["backend_invocations"], 0)
        self.assertTrue(
            certificates[0]["checks"][
                "source_and_destination_are_non_polynomial_anchors"
            ]
        )
        self.assertEqual(
            certificates[0]["ratio_envelope"]["upper_binary64_hex"],
            "0x0.0p+0",
        )
        json.dumps(certify.json_safe(certificates[0]), allow_nan=False)

    def test_malformed_manifest_is_stable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hierarchy.manifest.raw.json"
            path.write_text('{"schema":"wrong"}', encoding="utf-8")
            with self.assertRaises(certify.CorpusError) as caught:
                certify.Corpus(path, production=False)
        self.assertEqual(caught.exception.state, "MalformedCorpus")

    def test_all_self_test_controls_make_zero_backend_calls(self) -> None:
        controls = certify.self_test_controls(self.profile)
        self.assertTrue(controls)
        self.assertTrue(all(item["backend_invocations"] == 0 for item in controls))
        states = {item["state"] for item in controls}
        self.assertTrue(
            {
                "RankDeficient",
                "IndeterminateRank",
                "NonFinite",
                "ResourceDenied",
                "MalformedCorpus",
                "IntegrityMismatch",
            }.issubset(states)
        )


if __name__ == "__main__":
    unittest.main()
