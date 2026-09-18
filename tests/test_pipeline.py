"""Independent source-to-artifact checks for the declared synthetic contract.

Fixtures are created through the public generator interface. Expected business
classifications come from the separately authored scenario oracle and explicit
contract rules below, never from generator/model implementation or saved output.
Every mutation is confined to a TemporaryDirectory; this suite changes no demo
sources or published artifacts.
"""

import collections
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from po_review.generate import generate_sources
from po_review.pipeline import PipelineError, run_pipeline, verify_run


SOURCE_FILES = ("procurement.sqlite", "ap_invoices.csv", "ap_case_events.csv")
BUSINESS_FILES = (
    "model.sqlite", "invoice_trace.csv", "review_queue.csv", "metrics.json",
    "report.html", "quality_profile.json", "quality_issues.csv", "normalizations.csv",
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields=None):
    if fields is None:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            fields = csv.DictReader(handle).fieldnames
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def instant(value):
    """Compare valid oracle instants without depending on production parsing."""
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


class PipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = read_json(ROOT / "data" / "scenario_expectations.json")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.artifacts = self.root / "artifacts"
        generate_sources(self.sources)

    def _run(self, sources=None, artifacts=None, **kwargs):
        # A network dependency is a test failure, including DNS-only attempts.
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
             mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")), \
             mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("network forbidden")):
            return run_pipeline(sources or self.sources, artifacts or self.artifacts, **kwargs)

    def copy_sources(self, name):
        target = self.root / name
        shutil.copytree(self.sources, target)
        return target

    def refresh_hashes(self, sources=None):
        """Let mutated synthetic fixtures reach validation instead of the hash gate."""
        sources = sources or self.sources
        manifest_path = sources / "export_manifest.json"
        manifest = read_json(manifest_path)
        for name in SOURCE_FILES:
            manifest["files"][name]["sha256"] = digest(sources / name)
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")

    def edit_manifest(self, sources, **changes):
        path = sources / "export_manifest.json"
        manifest = read_json(path)
        manifest.update(changes)
        path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")

    def assert_failed_attempt(self, artifacts, previous_id=None):
        last = read_json(artifacts / "last_attempt.json")
        self.assertEqual(last["status"], "FAILED")
        self.assertEqual(last["previous_successful_run"], previous_id)
        attempt = artifacts / last["path"]
        self.assertEqual(read_json(attempt / "attempt_status.json")["status"], "FAILED")
        events = [json.loads(line) for line in (attempt / "run.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "FAILED")
        self.assertTrue(events[-1]["error"])
        return attempt

    def assert_reconciliation(self, run_dir, raw, canonical, duplicates, quarantined):
        metrics = read_json(run_dir / "metrics.json")
        expected = {"raw": raw, "canonical": canonical,
                    "duplicate_rows_removed": duplicates, "quarantined": quarantined, "balanced": True}
        self.assertEqual(metrics["quality_controls"]["invoice_row_reconciliation"], expected)
        self.assertEqual(raw, canonical + duplicates + quarantined)
        trace = read_csv(run_dir / "invoice_trace.csv")
        self.assertEqual(len(trace), canonical)
        self.assertEqual(len({row["invoice_id"] for row in trace}), canonical)
        return metrics

    def test_every_independent_named_case_and_record_reconciliation(self):
        run_dir = self._run()
        trace = read_csv(run_dir / "invoice_trace.csv")
        by_id = collections.defaultdict(list)
        for row in trace:
            by_id[row["invoice_id"]].append(row)
        raw_counts = collections.Counter(row["invoice_id"].strip().upper()
                                         for row in read_csv(self.sources / "ap_invoices.csv"))
        issues = read_csv(run_dir / "quality_issues.csv")
        quarantine_counts = collections.Counter(row["record_id"] for row in issues
                                                 if row["source"] == "invoices" and row["severity"] == "QUARANTINE")
        duplicate_counts = collections.Counter(row["record_id"] for row in issues
                                               if row["source"] == "invoices" and row["severity"] == "DUPLICATE_REMOVED")
        cases = self.oracle["cases"]
        self.assertTrue(cases)
        self.assertEqual(len({case["scenario"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(scenario=case["scenario"]):
                invoice_id = case["invoice_id"]
                self.assertEqual(raw_counts[invoice_id], case["raw_row_count"])
                rows = by_id[invoice_id]
                self.assertEqual(len(rows), case["expected_canonical_count"])
                self.assertEqual(quarantine_counts[invoice_id], case.get("expected_quarantined_rows", 0))
                self.assertEqual(duplicate_counts[invoice_id], case.get("expected_duplicate_rows_removed", 0))
                if case["disposition"] == "QUARANTINED":
                    self.assertFalse(rows, "Quarantined source IDs must not enter invoice trace or metrics")
                    continue
                row = rows[0]
                self.assertEqual(row["scope"], case["disposition"])
                for field, expected in case["expected"].items():
                    with self.subTest(field=field):
                        actual = row[field]
                        if isinstance(expected, bool):
                            self.assertEqual(actual, "1" if expected else "0")
                        elif isinstance(expected, int):
                            self.assertEqual(int(actual), expected)
                        elif field.endswith("_at"):
                            self.assertEqual(instant(actual), instant(expected))
                        else:
                            self.assertEqual(actual, expected)
        expected = self.oracle["expected_invoice_reconciliation"]
        metrics = self.assert_reconciliation(run_dir, expected["raw_rows"], expected["canonical_rows"],
                                             expected["duplicate_rows_removed"], expected["quarantined_rows"])
        scopes = collections.Counter(row["scope"] for row in trace)
        self.assertEqual(scopes["ELIGIBLE"], expected["eligible_canonical_rows"])
        self.assertEqual(scopes["OUT_OF_SCOPE"], expected["excluded_canonical_rows"])
        self.assertEqual(metrics["primary"]["eligible_count"], expected["eligible_canonical_rows"])
        self.assertEqual(metrics["quality_controls"]["excluded_canonical_invoice_records"],
                         expected["excluded_canonical_rows"])

    def test_network_free_rebuild_is_identical_and_raw_snapshots_are_exact(self):
        original = {name: (self.sources / name).read_bytes() for name in (*SOURCE_FILES, "export_manifest.json")}
        first = self._run()
        first_bytes = {name: (first / name).read_bytes() for name in BUSINESS_FILES}
        second = self._run(artifacts=self.root / "rebuilt")
        self.assertEqual(first.name, second.name, "Run IDs must depend on content, not wall clock or output directory")
        self.assertEqual(first_bytes, {name: (second / name).read_bytes() for name in BUSINESS_FILES})
        self.assertEqual(self._run(), first, "A repeated run must reproduce the same published content")
        manifest = verify_run(first)
        self.assertEqual(set(manifest["business_artifact_hashes"]), set(BUSINESS_FILES))
        for name, original_bytes in original.items():
            with self.subTest(snapshot=name):
                self.assertEqual((first / "raw" / name).read_bytes(), original_bytes)
                self.assertEqual((self.sources / name).read_bytes(), original_bytes, "Retrieval must not clean source files")
                self.assertEqual(manifest["raw_hashes"][name], hashlib.sha256(original_bytes).hexdigest())
        retrieval = read_json(first / "retrieval.json")
        self.assertEqual(set(retrieval["source_types"]), {"SQL", "CSV"})
        self.assertEqual(set(retrieval["sql_queries"]),
                         {"departments", "suppliers", "requests", "purchase_orders", "po_events"})
        self.assertEqual(retrieval["row_counts"]["invoices"], self.oracle["expected_invoice_reconciliation"]["raw_rows"])

    def test_fatal_snapshot_schema_history_and_cutoff_failures_do_not_publish(self):
        # These are different contract gates, not variations of one parser rule.
        for variant in ("hash", "csv_schema", "sql_schema", "version", "incomplete", "old_export",
                        "late_history", "reversed_cohort", "missing_source", "sql_parent_identity"):
            with self.subTest(gate=variant):
                sources = self.copy_sources("sources-" + variant)
                artifacts = self.root / ("artifacts-" + variant)
                kwargs = {}
                if variant == "hash":
                    with (sources / "ap_invoices.csv").open("a", encoding="utf-8") as handle:
                        handle.write("\n")
                elif variant == "csv_schema":
                    path = sources / "ap_invoices.csv"
                    path.write_text(path.read_text().replace("amount_minor", "amount", 1), encoding="utf-8")
                    self.refresh_hashes(sources)
                elif variant == "sql_schema":
                    with sqlite3.connect(str(sources / "procurement.sqlite")) as conn:
                        conn.execute("ALTER TABLE departments RENAME COLUMN owner_role TO owner")
                    self.refresh_hashes(sources)
                elif variant == "version":
                    self.edit_manifest(sources, schema_version=2)
                elif variant == "incomplete":
                    complete = read_json(sources / "export_manifest.json")["completeness"]
                    complete["po_history_complete"] = False
                    self.edit_manifest(sources, completeness=complete)
                elif variant == "old_export":
                    self.edit_manifest(sources, exported_at="2026-08-30T12:00:00Z")
                elif variant == "late_history":
                    self.edit_manifest(sources, history_start="2026-08-02T00:00:00Z")
                elif variant == "reversed_cohort":
                    kwargs["start"] = "2026-09-01T00:00:00Z"
                elif variant == "missing_source":
                    (sources / "ap_case_events.csv").unlink()
                elif variant == "sql_parent_identity":
                    with sqlite3.connect(str(sources / "procurement.sqlite")) as conn:
                        conn.execute("UPDATE requests SET department_id = 'DEPT-NOT-IN-REGISTRY' WHERE rowid = (SELECT MIN(rowid) FROM requests)")
                    self.refresh_hashes(sources)
                with self.assertRaises(PipelineError):
                    self._run(sources, artifacts, **kwargs)
                self.assertFalse((artifacts / "latest.json").exists())
                self.assertEqual(list((artifacts / "runs").glob("*")), [])
                self.assert_failed_attempt(artifacts)

    def test_all_quarantined_invoices_refused_with_raw_and_failure_evidence(self):
        rows = read_csv(self.sources / "ap_invoices.csv")
        malformed = next(row for row in rows if row["invoice_id"] == "INV-CASE-BAD-TIMESTAMP")
        write_csv(self.sources / "ap_invoices.csv", [malformed])
        write_csv(self.sources / "ap_case_events.csv", [])
        self.refresh_hashes()
        with self.assertRaisesRegex(PipelineError, "all invoice records are quarantined"):
            self._run()
        attempt = self.assert_failed_attempt(self.artifacts)
        for name in (*SOURCE_FILES, "export_manifest.json"):
            self.assertEqual((attempt / "raw" / name).read_bytes(), (self.sources / name).read_bytes())
        self.assertEqual(read_json(attempt / "quality_profile.json")["reconciliation"]["invoice_quarantined_rows"], 1)
        self.assertFalse((self.artifacts / "latest.json").exists())

    def test_empty_declared_feed_has_visible_null_denominators(self):
        write_csv(self.sources / "ap_invoices.csv", [])
        write_csv(self.sources / "ap_case_events.csv", [])
        self.refresh_hashes()
        run_dir = self._run()
        metrics = self.assert_reconciliation(run_dir, 0, 0, 0, 0)
        self.assertEqual(metrics["primary"]["denominator"], 0)
        self.assertIsNone(metrics["primary"]["percentage"])
        self.assertTrue(metrics["primary"]["zero_denominator_explanation"])
        coverage = metrics["supporting"]["arrival_assessment_coverage"]
        self.assertIsNone(coverage["percentage"])
        self.assertTrue(coverage["zero_denominator_explanation"])
        self.assertEqual(read_csv(run_dir / "review_queue.csv"), [])

    def test_valid_and_invalid_rows_with_same_invoice_id_are_both_quarantined(self):
        rows = read_csv(self.sources / "ap_invoices.csv")
        invoice_id = "INV-CASE-LATER-APPROVAL"
        original = next(row for row in rows if row["invoice_id"] == invoice_id)
        rows.append(dict(original, amount_minor="not-an-integer"))
        write_csv(self.sources / "ap_invoices.csv", rows)
        self.refresh_hashes()
        run_dir = self._run()
        self.assertFalse(any(row["invoice_id"] == invoice_id for row in read_csv(run_dir / "invoice_trace.csv")),
                         "A malformed competing record cannot make the surviving version trustworthy")
        baseline = self.oracle["expected_invoice_reconciliation"]
        self.assert_reconciliation(run_dir, baseline["raw_rows"] + 1, baseline["canonical_rows"] - 1,
                                   baseline["duplicate_rows_removed"], baseline["quarantined_rows"] + 2)
        issues = [row for row in read_csv(run_dir / "quality_issues.csv")
                  if row["source"] == "invoices" and row["record_id"] == invoice_id and row["severity"] == "QUARANTINE"]
        self.assertEqual(len({row["source_row"] for row in issues}), 2)

    def test_malformed_timezone_invoice_is_quarantined_and_history_is_tainted(self):
        for fixture_number, bad_time in enumerate(("2026-08-12T12:00:00", "2026-08-12T12:00:00+05:99")):
            with self.subTest(timestamp=bad_time):
                sources = self.copy_sources("timezone-" + str(fixture_number))
                artifacts = sources.parent / (sources.name + "-artifacts")
                invoices = read_csv(sources / "ap_invoices.csv")
                invalid_invoice = "INV-CASE-EXACT-DUPLICATE"
                for row in invoices:
                    if row["invoice_id"] == invalid_invoice:
                        row["received_at"] = bad_time
                write_csv(sources / "ap_invoices.csv", invoices)
                po_invoice = next(row for row in invoices if row["invoice_id"] == "INV-CASE-SHARED-PO-A")
                with sqlite3.connect(str(sources / "procurement.sqlite")) as conn:
                    conn.execute("INSERT INTO po_events (event_id, po_id, status, effective_at, recorded_at) VALUES (?, ?, ?, ?, ?)",
                                 ("PE-INTEGRATION-BAD-TIMEZONE", po_invoice["po_id"], "CANCELLED", bad_time, bad_time))
                events = read_csv(sources / "ap_case_events.csv")
                events.append({"event_id": "CE-INTEGRATION-BAD-TIMEZONE", "invoice_id": "INV-CASE-FUTURE-STATE",
                               "event_type": "CASE_CLOSED", "effective_at": "2026-08-11T10:00:00Z",
                               "recorded_at": bad_time, "po_id": "", "actor_role": "AP_PROCESSOR",
                               "note": "Synthetic malformed timezone integration fixture"})
                write_csv(sources / "ap_case_events.csv", events)
                self.refresh_hashes(sources)
                run_dir = self._run(sources, artifacts)
                by_id = {row["invoice_id"]: row for row in read_csv(run_dir / "invoice_trace.csv")}
                profile = read_json(run_dir / "quality_profile.json")
                with self.subTest(entity="invoice"):
                    self.assertFalse(invalid_invoice in by_id, "Malformed invoice receipt must be quarantined")
                with self.subTest(entity="po_history"):
                    row = by_id["INV-CASE-SHARED-PO-A"]
                    self.assertEqual((row["arrival_status"], row["current_status"]), ("UNKNOWN", "UNKNOWN"))
                    self.assertEqual(row["current_reason"], "INVALID_PO_HISTORY")
                    self.assertIn(po_invoice["po_id"], profile["uncertain_entities"]["po_ids"])
                with self.subTest(entity="case_history"):
                    row = by_id["INV-CASE-FUTURE-STATE"]
                    self.assertEqual((row["current_status"], row["case_state"]), ("UNKNOWN", "UNKNOWN"))
                    self.assertEqual(row["routing"], "AP_DATA_INVESTIGATION")
                    self.assertIn("INV-CASE-FUTURE-STATE", profile["uncertain_entities"]["invoice_ids"])

    def test_shared_po_and_many_history_rows_do_not_multiply_counts_or_money(self):
        ids = {"INV-CASE-SHARED-PO-A", "INV-CASE-SHARED-PO-B"}
        rows = [row for row in read_csv(self.sources / "ap_invoices.csv") if row["invoice_id"] in ids]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(int(row["amount_minor"]) for row in rows), 30000)
        write_csv(self.sources / "ap_invoices.csv", rows)
        events = [row for row in read_csv(self.sources / "ap_case_events.csv") if row["invoice_id"] in ids]
        self.assertGreater(len(events), len(rows), "Fixture must actually exercise a many-side join")
        write_csv(self.sources / "ap_case_events.csv", events)
        po_ids = {row["po_id"] for row in rows}
        self.assertEqual(len(po_ids), 1)
        with sqlite3.connect(str(self.sources / "procurement.sqlite")) as conn:
            po_id = next(iter(po_ids))
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM po_events WHERE po_id = ?", (po_id,)).fetchone()[0], 1)
            conn.execute("UPDATE po_events SET status = 'CREATED' WHERE po_id = ?", (po_id,))
        self.refresh_hashes()
        run_dir = self._run()
        metrics = self.assert_reconciliation(run_dir, 2, 2, 0, 0)
        self.assertEqual((metrics["primary"]["numerator"], metrics["primary"]["denominator"]), (2, 2))
        self.assertEqual(metrics["supporting"]["open_exceptions_by_reason"]["counts"], {"PO_NOT_APPROVED": 2})
        self.assertEqual(metrics["supporting"]["open_exceptions_gross_value"]["amount_minor"], 30000)
        self.assertEqual(len(read_csv(run_dir / "review_queue.csv")), 2)

    def test_failed_cli_and_partial_model_runs_preserve_latest_good(self):
        good = self._run()
        latest_bytes = (self.artifacts / "latest.json").read_bytes()
        good_bytes = {name: (good / name).read_bytes() for name in BUSINESS_FILES}
        with (self.sources / "ap_invoices.csv").open("a", encoding="utf-8") as handle:
            handle.write("\n")
        result = subprocess.run([sys.executable, str(ROOT / "run.py"), "run", "--sources", str(self.sources),
                                 "--artifacts", str(self.artifacts)], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAILED", result.stderr)
        self.assertEqual((self.artifacts / "latest.json").read_bytes(), latest_bytes)
        self.assertEqual(good_bytes, {name: (good / name).read_bytes() for name in BUSINESS_FILES})
        self.assert_failed_attempt(self.artifacts, previous_id=good.name)
        self.assertEqual(verify_run(good)["run_id"], good.name)

        for name in (*SOURCE_FILES, "export_manifest.json"):
            shutil.copy2(good / "raw" / name, self.sources / name)

        def fail_after_partial_output(data, start, as_of, output_dir, taints=None):
            (output_dir / "report.html").write_text("Incomplete synthetic report", encoding="utf-8")
            raise RuntimeError("injected failure after partial model output")

        with mock.patch("po_review.model.build_outputs", side_effect=fail_after_partial_output):
            with self.assertRaisesRegex(PipelineError, "injected failure after partial model output"):
                self._run()
        attempt = self.assert_failed_attempt(self.artifacts, previous_id=good.name)
        self.assertEqual((attempt / "report.html").read_text(), "Incomplete synthetic report")
        self.assertEqual((self.artifacts / "latest.json").read_bytes(), latest_bytes)
        self.assertEqual(good_bytes, {name: (good / name).read_bytes() for name in BUSINESS_FILES})
        self.assertEqual(list((self.artifacts / "runs").iterdir()), [good])

    def test_published_business_and_raw_tampering_is_detected(self):
        good = self._run()
        for relative in ("invoice_trace.csv", "raw/ap_invoices.csv"):
            with self.subTest(tampered=relative):
                copy = self.root / ("tampered-" + relative.replace("/", "-"))
                shutil.copytree(good, copy)
                with (copy / relative).open("ab") as handle:
                    handle.write(b"TAMPERED\n")
                with self.assertRaisesRegex(PipelineError, "absent or changed"):
                    verify_run(copy)
        # Verification failure during an attempted same-content republish must
        # also be visible, rather than silently blessing a damaged publication.
        with (good / "report.html").open("a", encoding="utf-8") as handle:
            handle.write("<!-- tampered integration fixture -->")
        with self.assertRaises(PipelineError):
            self._run()
        self.assert_failed_attempt(self.artifacts, previous_id=good.name)


if __name__ == "__main__":
    unittest.main()
