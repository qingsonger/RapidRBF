from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import oracle  # noqa: E402


def make_index(*, value: str = "one", timeout: float = 5.0) -> dict:
    scenario_id = "fake-process"
    item_id = "stable.fake"
    code = (
        "import os,pathlib;"
        "data=os.environ['VALUE'].encode();"
        "print(os.environ['VALUE']);"
        "pathlib.Path('result.bin').write_bytes(data)"
    )
    return {
        "schema_version": oracle.SCHEMA_VERSION,
        "id": "test-bundle",
        "compatibility_items": [
            {
                "id": item_id,
                "oracle_applicability": "required",
                "scenario_ids": [scenario_id],
            },
            {
                "id": "migration.none",
                "oracle_applicability": "not_applicable",
                "reason": "not exposed by the fake",
            },
        ],
        "scenarios": [
            {
                "id": scenario_id,
                "covers": [item_id],
                "authority": "canonical",
                "role": "accepted_surface",
                "surface": "fake",
                "argv": ["${PYTHON}", "-c", code],
                "env": {"VALUE": value},
                "timeout_seconds": timeout,
                "expected": {"terminal_status": "exited", "exit_code": 0},
                "outputs": [{"path": "result.bin"}],
            }
        ],
    }


class OracleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rapidrbf-oracle-test-")
        self.root = pathlib.Path(self.temp.name)
        self.index_path = self.root / "index.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_index(self, value: dict) -> None:
        self.index_path.write_text(json.dumps(value), encoding="utf-8")

    def test_capture_verify_and_no_overwrite(self) -> None:
        self.write_index(make_index())
        bundle = self.root / "bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        oracle.verify(self.index_path, bundle)
        self.assertEqual(
            (bundle / "runs" / "fake-process" / "outputs" / "result.bin").read_bytes(),
            b"one",
        )
        with self.assertRaises(oracle.OracleError):
            oracle.capture(
                self.index_path, bundle, self.root, {"PYTHON": sys.executable}
            )

    def test_tampered_bundle_fails(self) -> None:
        self.write_index(make_index())
        bundle = self.root / "bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        (bundle / "runs" / "fake-process" / "stdout.txt").write_bytes(b"tampered")
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path, bundle)

    def test_checksum_row_deletion_does_not_hide_tamper(self) -> None:
        self.write_index(make_index())
        bundle = self.root / "bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        run = bundle / "runs" / "fake-process"
        checksums = run / "checksums.sha256"
        checksums.write_text(
            "".join(
                line
                for line in checksums.read_text(encoding="utf-8").splitlines(True)
                if not line.endswith("  stdout.txt\n")
            ),
            encoding="utf-8",
        )
        (run / "stdout.txt").write_bytes(b"hidden tamper")
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path, bundle)

    def test_changed_index_fails_bundle_verification(self) -> None:
        index = make_index()
        self.write_index(index)
        bundle = self.root / "bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        index["scenarios"][0]["timeout_seconds"] = 123
        self.write_index(index)
        with self.assertRaisesRegex(oracle.OracleError, "different index"):
            oracle.verify(self.index_path, bundle)

    def test_unsafe_output_path_fails(self) -> None:
        index = make_index()
        index["scenarios"][0]["outputs"][0]["path"] = "../escape"
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_windows_absolute_and_drive_relative_paths_fail(self) -> None:
        for value in ("C:/escape", "C:escape", "//server/share/file"):
            with self.subTest(value=value), self.assertRaises(oracle.OracleError):
                oracle.safe_relative(value, "test")

    def test_duplicate_scenario_id_fails(self) -> None:
        index = make_index()
        index["scenarios"].append(dict(index["scenarios"][0]))
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_duplicate_json_key_fails(self) -> None:
        self.index_path.write_text(
            '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(oracle.OracleError, "duplicate JSON key"):
            oracle.load_json(self.index_path)

    def test_dangling_coverage_reference_fails(self) -> None:
        index = make_index()
        index["scenarios"][0]["covers"] = ["stable.missing"]
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_research_scenario_cannot_satisfy_required_coverage(self) -> None:
        index = make_index()
        scenario = index["scenarios"][0]
        scenario["role"] = "research_only"
        scenario["authority"] = "instrumented"
        scenario["relates_to"] = scenario.pop("covers")
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_research_scenario_must_use_relates_to(self) -> None:
        index = make_index()
        research = {
            "id": "research",
            "authority": "instrumented",
            "role": "research_only",
            "covers": ["stable.fake"],
            "argv": ["${PYTHON}", "-c", "pass"],
            "expected": {"terminal_status": "exited", "exit_code": 0},
            "outputs": [],
        }
        index["scenarios"].append(research)
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_invalid_authority_fails(self) -> None:
        index = make_index()
        index["scenarios"][0]["authority"] = "candidate"
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_legacy_scenario_requires_native_layout_metadata(self) -> None:
        index = make_index()
        index["scenarios"][0]["surface"] = "legacy_artifact"
        self.write_index(index)
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path)

    def test_timeout_is_captured(self) -> None:
        index = make_index(timeout=0.05)
        scenario = index["scenarios"][0]
        scenario["argv"] = [
            "${PYTHON}",
            "-c",
            "import time; time.sleep(2)",
        ]
        scenario["outputs"] = []
        scenario["expected"] = {"terminal_status": "timeout"}
        self.write_index(index)
        bundle = self.root / "timeout-bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        record = oracle.load_json(bundle / "runs" / "fake-process" / "run.json")
        self.assertEqual(record["terminal_status"], "timeout")
        self.assertIsNone(record["exit_code"])

    def test_failed_capture_cleans_isolated_work_directory(self) -> None:
        index = make_index()
        index["scenarios"][0]["argv"] = ["${PYTHON}", "-c", "pass"]
        self.write_index(index)
        before = set(
            pathlib.Path(tempfile.gettempdir()).glob("rapidrbf-oracle-fake-process-*")
        )
        with self.assertRaises(oracle.OracleError):
            oracle.capture(
                self.index_path,
                self.root / "failed-bundle",
                self.root,
                {"PYTHON": sys.executable},
            )
        after = set(
            pathlib.Path(tempfile.gettempdir()).glob("rapidrbf-oracle-fake-process-*")
        )
        self.assertEqual(after, before)

    def test_capture_honors_safe_cwd(self) -> None:
        index = make_index()
        scenario = index["scenarios"][0]
        scenario["cwd"] = "nested/work"
        scenario["argv"] = [
            "${PYTHON}",
            "-c",
            "import pathlib;print(pathlib.Path.cwd().as_posix());"
            "pathlib.Path('result.bin').write_bytes(b'cwd')",
        ]
        self.write_index(index)
        bundle = self.root / "cwd-bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        run = bundle / "runs" / "fake-process"
        self.assertTrue((run / "stdout.txt").read_text().strip().endswith("nested/work"))
        self.assertEqual((run / "outputs" / "result.bin").read_bytes(), b"cwd")
        record = oracle.load_json(run / "run.json")
        self.assertEqual(record["working_directory"], "${WORK}/nested/work")

    def test_capture_rejects_temp_environment_override(self) -> None:
        index = make_index()
        index["scenarios"][0]["env"]["TEMP"] = "C:/external"
        self.write_index(index)
        with self.assertRaisesRegex(oracle.OracleError, "must not override"):
            oracle.verify(self.index_path)

    def test_capture_does_not_inherit_unallowlisted_environment(self) -> None:
        marker = "RAPIDRBF_ORACLE_SECRET_FOR_TEST"
        previous = os.environ.get(marker)
        os.environ[marker] = "secret"
        try:
            index = make_index()
            scenario = index["scenarios"][0]
            scenario["argv"] = [
                "${PYTHON}",
                "-c",
                f"import os,pathlib;print({marker!r} in os.environ);"
                "pathlib.Path('result.bin').write_bytes(b'ok')",
            ]
            self.write_index(index)
            bundle = self.root / "env-bundle"
            oracle.capture(
                self.index_path, bundle, self.root, {"PYTHON": sys.executable}
            )
        finally:
            if previous is None:
                os.environ.pop(marker, None)
            else:
                os.environ[marker] = previous
        stdout = bundle / "runs" / "fake-process" / "stdout.txt"
        self.assertEqual(stdout.read_text().strip(), "False")

    def test_replay_reports_exact_mismatch(self) -> None:
        index = make_index()
        index["scenarios"][0]["env"]["VALUE"] = "${VALUE}"
        self.write_index(index)
        bundle = self.root / "bundle"
        oracle.capture(
            self.index_path,
            bundle,
            self.root,
            {"PYTHON": sys.executable, "VALUE": "one"},
        )
        differences = oracle.replay(
            self.index_path,
            bundle,
            self.root,
            {"PYTHON": sys.executable, "VALUE": "two"},
            self.root / "diff.json",
        )
        self.assertEqual(
            {item["scenario_id"] for item in differences}, {"fake-process"}
        )
        self.assertIn("structure", {item["kind"] for item in differences})
        self.assertIn("bytes", {item["kind"] for item in differences})

    def test_replay_compare_false_output_is_diagnostic_only(self) -> None:
        index = make_index()
        scenario = index["scenarios"][0]
        scenario["argv"] = [
            "${PYTHON}",
            "-c",
            "import os,pathlib;"
            "pathlib.Path('result.bin').write_bytes(os.urandom(32))",
        ]
        scenario["outputs"][0]["replay_compare"] = False
        self.write_index(index)
        bundle = self.root / "bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        differences = oracle.replay(
            self.index_path,
            bundle,
            self.root,
            {"PYTHON": sys.executable},
            self.root / "diff.json",
        )
        self.assertEqual(differences, [])
        output = bundle / "runs" / "fake-process" / "outputs" / "result.bin"
        output.write_bytes(b"tampered diagnostic")
        with self.assertRaises(oracle.OracleError):
            oracle.verify(self.index_path, bundle)

    def test_replay_ignores_isolated_work_directory_identity(self) -> None:
        self.write_index(make_index())
        bundle = self.root / "same-bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        differences = oracle.replay(
            self.index_path,
            bundle,
            self.root,
            {"PYTHON": sys.executable},
            self.root / "same-diff.json",
        )
        self.assertEqual(differences, [])

    @unittest.skipUnless(os.name == "nt", "Windows-only resource assertion")
    def test_windows_capture_observes_effective_thread_count(self) -> None:
        index = make_index()
        index["scenarios"][0]["argv"] = [
            "${PYTHON}",
            "-c",
            "import pathlib,time;pathlib.Path('result.bin').write_bytes(b'ok');"
            "time.sleep(.15)",
        ]
        self.write_index(index)
        bundle = self.root / "threads-bundle"
        oracle.capture(
            self.index_path, bundle, self.root, {"PYTHON": sys.executable}
        )
        record = oracle.load_json(bundle / "runs" / "fake-process" / "run.json")
        self.assertGreaterEqual(record["effective_threads"], 1)

    @unittest.skipUnless(os.name == "nt", "Windows-only process-tree assertion")
    def test_windows_timeout_terminates_descendant_process_tree(self) -> None:
        index = make_index(timeout=0.2)
        scenario = index["scenarios"][0]
        scenario["argv"] = [
            "${PYTHON}",
            "-c",
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);"
            "time.sleep(10)",
        ]
        scenario["outputs"] = []
        scenario["expected"] = {"terminal_status": "timeout"}
        self.write_index(index)
        started = time.monotonic()
        oracle.capture(
            self.index_path,
            self.root / "tree-timeout-bundle",
            self.root,
            {"PYTHON": sys.executable},
        )
        self.assertLess(time.monotonic() - started, 3)


if __name__ == "__main__":
    unittest.main()
