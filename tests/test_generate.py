"""Checks for the independent, offline synthetic source generator."""
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from po_review.generate import generate_sources  # noqa: E402


class GenerateSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def invoice_rows(directory):
        with (directory / "ap_invoices.csv").open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_same_seed_produces_identical_bytes_and_verifiable_manifest(self):
        first, second = self.root / "first", self.root / "second"
        first_manifest = generate_sources(first)
        second_manifest = generate_sources(second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_manifest["dataset_kind"], "synthetic")
        self.assertEqual(first_manifest["default_start"], "2026-08-01T00:00:00Z")
        self.assertEqual(first_manifest["default_as_of"], "2026-08-31T18:00:00Z")
        self.assertTrue(all(first_manifest["completeness"].values()))
        self.assertEqual(set(first_manifest["files"]), {
            "procurement.sqlite", "ap_invoices.csv", "ap_case_events.csv",
        })
        for name, metadata in first_manifest["files"].items():
            data = (first / name).read_bytes()
            self.assertEqual(data, (second / name).read_bytes(), name)
            self.assertEqual(metadata["sha256"], hashlib.sha256(data).hexdigest(), name)
        self.assertEqual((first / "export_manifest.json").read_bytes(),
                         (second / "export_manifest.json").read_bytes())

    def test_refuses_all_existing_source_files_including_partial_snapshots(self):
        for name in ("procurement.sqlite", "ap_invoices.csv", "ap_case_events.csv",
                     "export_manifest.json"):
            with self.subTest(name=name):
                destination = self.root / name.replace(".", "_")
                destination.mkdir()
                sentinel = destination / name
                sentinel.write_bytes(b"preserve original fixture bytes\n")
                with self.assertRaises(FileExistsError):
                    generate_sources(destination)
                self.assertEqual(sentinel.read_bytes(), b"preserve original fixture bytes\n")
                self.assertEqual([p.name for p in destination.iterdir()], [name])

    def test_force_replaces_only_owned_files(self):
        destination = self.root / "sources"
        generate_sources(destination, seed=11)
        first = (destination / "ap_invoices.csv").read_bytes()
        extra = destination / "operator-notes.txt"
        extra.write_text("keep me", encoding="utf-8")
        generate_sources(destination, seed=12, force=True)
        self.assertNotEqual(first, (destination / "ap_invoices.csv").read_bytes())
        self.assertEqual(extra.read_text(encoding="utf-8"), "keep me")
        self.assertEqual(json.loads((destination / "export_manifest.json").read_text())["seed"], 12)

    def test_broken_source_symlink_is_still_an_existing_input(self):
        destination = self.root / "sources"
        destination.mkdir()
        source_path = destination / "ap_invoices.csv"
        source_path.symlink_to(destination / "missing-original.csv")
        with self.assertRaises(FileExistsError):
            generate_sources(destination)
        self.assertTrue(source_path.is_symlink())
        self.assertFalse((destination / "export_manifest.json").exists())

    def test_only_ordinary_examples_change_with_seed(self):
        first, second = self.root / "first", self.root / "second"
        generate_sources(first, seed=11)
        generate_sources(second, seed=12)
        first_rows, second_rows = self.invoice_rows(first), self.invoice_rows(second)
        named = lambda rows: [row for row in rows if "CASE-" in row["invoice_id"].upper()]
        self.assertEqual(named(first_rows), named(second_rows))
        self.assertNotEqual(first_rows, second_rows)
        for table in ("requests", "purchase_orders", "po_events"):
            with sqlite3.connect(str(first / "procurement.sqlite")) as a:
                with sqlite3.connect(str(second / "procurement.sqlite")) as b:
                    first_records = [r for r in a.execute("SELECT * FROM " + table) if "CASE-" in r[0]]
                    second_records = [r for r in b.execute("SELECT * FROM " + table) if "CASE-" in r[0]]
            self.assertEqual(first_records, second_records, table)

    def test_raw_quality_counterexamples_are_preserved_and_core_sql_is_consistent(self):
        destination = self.root / "sources"
        generate_sources(destination)
        rows = self.invoice_rows(destination)
        self.assertEqual(len(rows), 102)
        by_id = {}
        for row in rows:
            by_id.setdefault(row["invoice_id"].strip().upper(), []).append(row)
        self.assertEqual(len(by_id), 100)
        self.assertEqual(by_id["INV-CASE-EXACT-DUPLICATE"][0],
                         by_id["INV-CASE-EXACT-DUPLICATE"][1])
        self.assertNotEqual(by_id["INV-CASE-CONFLICT-DUPLICATE"][0]["amount_minor"],
                            by_id["INV-CASE-CONFLICT-DUPLICATE"][1]["amount_minor"])
        self.assertEqual(by_id["INV-CASE-BAD-AMOUNT"][0]["amount_minor"], "123.45")
        self.assertEqual(by_id["INV-CASE-BAD-TIMESTAMP"][0]["received_at"],
                         "2026-08-99T10:00:00Z")
        self.assertEqual(by_id["INV-CASE-CLEANUP"][0]["currency"], " gbp ")
        self.assertEqual(by_id["INV-CASE-CREDIT-NOTE"][0]["amount_minor"], "-12500")
        with sqlite3.connect(str(destination / "procurement.sqlite")) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(connection.execute(
                "SELECT status FROM po_events WHERE po_id='PO-CASE-BAD-PO-HISTORY' "
                "AND status NOT IN ('CREATED','APPROVED','CLOSED','CANCELLED')"
            ).fetchall(), [("UNRECOGNISED_STATE",)])

    def test_original_references_and_explicit_case_history_are_present(self):
        destination = self.root / "sources"
        generate_sources(destination)
        invoices = {r["invoice_id"].strip().upper(): r for r in self.invoice_rows(destination)}
        with (destination / "ap_case_events.csv").open(newline="", encoding="utf-8") as handle:
            events = list(csv.DictReader(handle))
        by_invoice = {}
        for event in events:
            by_invoice.setdefault(event["invoice_id"], []).append(event)
        self.assertEqual(invoices["INV-CASE-REFERENCE-REPAIR"]["po_id"], "")
        repair = by_invoice["INV-CASE-REFERENCE-REPAIR"]
        self.assertEqual([(e["event_type"], e["po_id"]) for e in repair],
                         [("REFERENCE_CONFIRMED", "PO-CASE-REFERENCE-REPAIR")])
        reopened = sorted(by_invoice["INV-CASE-REOPENED"], key=lambda e: e["effective_at"])
        self.assertEqual([e["event_type"] for e in reopened], ["CASE_CLOSED", "CASE_REOPENED"])
        self.assertEqual(by_invoice["INV-CASE-BAD-CASE-HISTORY"][0]["recorded_at"],
                         "not-a-timestamp")
        self.assertTrue(all("SYNTHETIC" in e["note"] for e in events))

    def test_independent_expectations_cover_each_named_invoice_without_becoming_inputs(self):
        destination = self.root / "sources"
        manifest = generate_sources(destination)
        expected = json.loads((PROJECT_ROOT / "data/scenario_expectations.json").read_text())
        cases = expected["cases"]
        expected_ids = {case["invoice_id"] for case in cases}
        actual_ids = {r["invoice_id"].strip().upper() for r in self.invoice_rows(destination)
                      if "CASE-" in r["invoice_id"].upper()}
        self.assertEqual(expected_ids, actual_ids)
        self.assertEqual(len(expected_ids), len(cases))
        self.assertNotIn("scenario_expectations.json", manifest["files"])
        self.assertFalse((destination / "scenario_expectations.json").exists())
        for case in cases:
            if case["disposition"] == "ELIGIBLE":
                for field in ("arrival_status", "arrival_reason", "current_status", "current_reason"):
                    self.assertIn(field, case["expected"], (case["scenario"], field))


if __name__ == "__main__":
    unittest.main()
