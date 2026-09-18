"""Independent reliability regressions using disposable SQL/CSV source exports.

Each fixture starts with the real explicit generator CLI, then replaces only the
temporary operational rows with a hand-checkable one-invoice example. These are
contract assertions, including counterexamples discovered during the audit.
"""

import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from po_review import pipeline


CASE_FIELDS = ("event_id", "invoice_id", "event_type", "effective_at", "recorded_at",
               "po_id", "actor_role", "note")


def fixture():
    return {
        "departments": [{"department_id": "D1", "name": "Fictional unit", "owner_role": "BUYER"}],
        "suppliers": [{"supplier_id": "S1", "name": "Fictional supplier"}],
        "requests": [{"request_id": "R1", "supplier_id": "S1", "department_id": "D1",
                      "requested_at": "2026-07-01T00:00:00Z", "category": "ROUTINE"}],
        "purchase_orders": [{"po_id": "P1", "request_id": "R1", "supplier_id": "S1",
                             "currency": "GBP", "created_at": "2026-07-02T00:00:00Z"}],
        "po_events": [{"event_id": "P-CREATED", "po_id": "P1", "status": "CREATED",
                       "effective_at": "2026-07-02T00:00:00Z", "recorded_at": "2026-07-02T00:00:00Z"},
                      {"event_id": "P-APPROVED", "po_id": "P1", "status": "APPROVED",
                       "effective_at": "2026-08-02T00:00:00Z", "recorded_at": "2026-08-02T00:00:00Z"}],
        "invoices": [{"invoice_id": "I1", "supplier_id": "S1", "supplier_invoice_no": "COMM-1",
                      "request_id": "R1", "po_id": "P1", "issued_at": "2026-08-09T00:00:00Z",
                      "received_at": "2026-08-10T00:00:00Z", "amount_minor": 10101,
                      "currency": "GBP", "category": "ROUTINE", "document_type": "INVOICE"}],
        "case_events": [],
    }


class AdversarialReliabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = self.root / "sources"
        self.artifacts = self.root / "artifacts"
        result = subprocess.run([sys.executable, str(ROOT / "run.py"), "generate", "--sources", str(self.sources)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_fixture(fixture())

    def write_fixture(self, data):
        with sqlite3.connect(str(self.sources / "procurement.sqlite")) as connection:
            for table in ("po_events", "purchase_orders", "requests", "suppliers", "departments"):
                connection.execute("DELETE FROM " + table)
            for table in ("departments", "suppliers", "requests", "purchase_orders", "po_events"):
                for row in data[table]:
                    columns = tuple(row)
                    connection.execute("INSERT INTO " + table + " (" + ",".join(columns) + ") VALUES (" +
                                       ",".join("?" for _ in columns) + ")", tuple(row[c] for c in columns))
        for name, rows, fields in (("ap_invoices.csv", data["invoices"], tuple(fixture()["invoices"][0])),
                                   ("ap_case_events.csv", data["case_events"], CASE_FIELDS)):
            with (self.sources / name).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        manifest_path = self.sources / "export_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for name in pipeline.INPUTS:
            manifest["files"][name]["sha256"] = pipeline.sha256(self.sources / name)
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")

    def run_fixture(self, **kwargs):
        run = pipeline.run_pipeline(self.sources, self.artifacts, **kwargs)
        with (run / "invoice_trace.csv").open(newline="", encoding="utf-8") as handle:
            trace = {row["invoice_id"]: row for row in csv.DictReader(handle)}
        return run, trace, json.loads((run / "metrics.json").read_text())

    def assert_ready(self, trace, metrics):
        self.assertEqual((trace["I1"]["arrival_status"], trace["I1"]["current_status"], trace["I1"]["case_state"]),
                         ("READY", "READY", "OPEN"))
        self.assertEqual(metrics["primary"]["denominator"], 1)
        self.assertEqual(metrics["primary"]["unknown_count"], 0)

    def test_future_invalid_po_event_cannot_change_earlier_assessment(self):
        data = fixture()
        data["po_events"].append({"event_id": "FUTURE", "po_id": "P1", "status": "MALFORMED",
                                  "effective_at": "2026-09-01T00:00:00Z", "recorded_at": "2026-09-01T00:00:00Z"})
        self.write_fixture(data)
        _, trace, metrics = self.run_fixture()
        self.assert_ready(trace, metrics)

    def test_invalid_po_event_recorded_after_cutoff_cannot_change_assessment(self):
        data = fixture()
        data["po_events"].append({"event_id": "FUTURE", "po_id": "P1", "status": "MALFORMED",
                                  "effective_at": "2026-08-03T00:00:00Z", "recorded_at": "2026-09-01T00:00:00Z"})
        self.write_fixture(data)
        _, trace, metrics = self.run_fixture()
        self.assert_ready(trace, metrics)

    def test_future_invalid_case_event_cannot_change_earlier_assessment(self):
        data = fixture()
        data["case_events"].append({"event_id": "FUTURE", "invoice_id": "I1", "event_type": "MALFORMED",
                                    "effective_at": "2026-09-01T00:00:00Z", "recorded_at": "2026-09-01T00:00:00Z",
                                    "po_id": "", "actor_role": "AP_PROCESSOR", "note": "Synthetic future record."})
        self.write_fixture(data)
        _, trace, metrics = self.run_fixture()
        self.assert_ready(trace, metrics)

    def test_future_commercial_collision_cannot_change_earlier_assessment(self):
        data = fixture()
        data["invoices"].append(dict(data["invoices"][0], invoice_id="I2", issued_at="2026-09-01T00:00:00Z",
                                     received_at="2026-09-01T00:00:00Z"))
        self.write_fixture(data)
        _, trace, metrics = self.run_fixture()
        self.assertEqual(trace["I2"]["exclusion_reason"], "AFTER_REPORT_CUTOFF")
        self.assert_ready(trace, metrics)

    def test_failed_publication_preserves_prior_successful_pointer_and_diagnostics(self):
        self.run_fixture()
        previous = json.loads((self.artifacts / "latest.json").read_text())
        original = pipeline.atomic_json

        def fail_success_status(path, value):
            if Path(path).name == "last_attempt.json" and value.get("status") == "SUCCESS":
                raise OSError("injected final status write failure")
            return original(path, value)

        with patch.object(pipeline, "atomic_json", side_effect=fail_success_status):
            with self.assertRaises(pipeline.PipelineError):
                self.run_fixture(as_of="2026-08-30T18:00:00Z")
        self.assertEqual(json.loads((self.artifacts / "latest.json").read_text()), previous)
        failed = json.loads((self.artifacts / "last_attempt.json").read_text())
        self.assertEqual(failed["status"], "FAILED")
        self.assertTrue((self.artifacts / failed["path"] / "run.jsonl").is_file())
        self.assertEqual(json.loads((self.artifacts / failed["path"] / "attempt_status.json").read_text())["status"], "FAILED")

    def test_corrupt_previous_pointer_does_not_leave_stale_success_as_last_attempt(self):
        self.run_fixture()
        (self.artifacts / "latest.json").write_text("{broken")
        with patch.object(pipeline, "retrieve", side_effect=pipeline.PipelineError("injected retrieval failure")):
            with self.assertRaises(Exception):
                pipeline.run_pipeline(self.sources, self.artifacts)
        self.assertEqual(json.loads((self.artifacts / "last_attempt.json").read_text())["status"], "FAILED")

    def test_hash_mismatch_preserves_rejected_raw_bytes(self):
        self.run_fixture()
        previous = (self.artifacts / "latest.json").read_bytes()
        rejected = b"broken,source,bytes\n"
        (self.sources / "ap_invoices.csv").write_bytes(rejected)
        with self.assertRaises(pipeline.PipelineError):
            self.run_fixture()
        last = json.loads((self.artifacts / "last_attempt.json").read_text())
        raw = self.artifacts / last["path"] / "raw" / "ap_invoices.csv"
        self.assertTrue(raw.is_file(), "The rejected source is required to reproduce the hash failure.")
        self.assertEqual(raw.read_bytes(), rejected)
        self.assertEqual((self.artifacts / "latest.json").read_bytes(), previous)

    def test_verify_rejects_manifest_with_empty_hash_inventories(self):
        run, _, _ = self.run_fixture()
        path = run / "artifact_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["business_artifact_hashes"] = {}
        manifest["raw_hashes"] = {}
        path.write_text(json.dumps(manifest))
        (run / "metrics.json").unlink()
        with self.assertRaises(pipeline.PipelineError):
            pipeline.verify_run(run)

    def test_known_invalid_history_remains_unknown(self):
        data = fixture()
        data["po_events"].append({"event_id": "KNOWN-BAD", "po_id": "P1", "status": "MALFORMED",
                                  "effective_at": "2026-08-03T00:00:00Z", "recorded_at": "2026-08-03T00:00:00Z"})
        self.write_fixture(data)
        _, trace, metrics = self.run_fixture()
        self.assertEqual(trace["I1"]["current_status"], "UNKNOWN")
        self.assertEqual(metrics["primary"]["denominator"], 0)

    def test_malformed_competing_duplicate_quarantines_good_twin(self):
        data = fixture()
        data["invoices"].append(dict(data["invoices"][0], amount_minor="broken"))
        data["invoices"].append(dict(data["invoices"][0], invoice_id="I2", supplier_invoice_no="COMM-2"))
        self.write_fixture(data)
        _, trace, metrics = self.run_fixture()
        self.assertEqual(set(trace), {"I2"})
        quality = metrics["quality_controls"]
        self.assertEqual(quality["invoice_quarantined_rows"], 2)
        self.assertTrue(quality["invoice_row_reconciliation"]["balanced"])


if __name__ == "__main__":
    unittest.main()
