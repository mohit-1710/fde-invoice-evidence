"""Independent, small counterexamples for temporal and invoice-grain rules."""

import copy
import csv
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from po_review.model import build_outputs


START = "2026-08-01T00:00:00Z"
CUTOFF = "2026-08-31T18:00:00Z"
RECEIPT = "2026-08-10T12:00:00Z"


def event(event_id, status, effective, recorded=None, po="P1"):
    return {"event_id": event_id, "po_id": po, "status": status,
            "effective_at": effective, "recorded_at": recorded or effective}


def case(event_id, event_type, effective, recorded=None, po="", invoice="I1"):
    return {"event_id": event_id, "invoice_id": invoice, "event_type": event_type,
            "effective_at": effective, "recorded_at": recorded or effective,
            "po_id": po, "actor_role": "AP_PROCESSOR", "note": "Synthetic historical interaction."}


def fixture():
    return {
        "departments": [{"department_id": "D1", "name": "Fictional labs", "owner_role": "LAB_BUYER"},
                        {"department_id": "D2", "name": "Fictional estates", "owner_role": ""}],
        "suppliers": [{"supplier_id": "S1", "name": "Fictional supplier one"},
                      {"supplier_id": "S2", "name": "Fictional supplier two"}],
        "requests": [{"request_id": "R1", "supplier_id": "S1", "department_id": "D1", "requested_at": "2026-07-01T00:00:00Z", "category": "ROUTINE"},
                     {"request_id": "R2", "supplier_id": "S1", "department_id": "D2", "requested_at": "2026-07-01T00:00:00Z", "category": "ROUTINE"},
                     {"request_id": "R3", "supplier_id": "S2", "department_id": "D1", "requested_at": "2026-07-01T00:00:00Z", "category": "ROUTINE"}],
        "purchase_orders": [{"po_id": "P1", "request_id": "R1", "supplier_id": "S1", "currency": "GBP", "created_at": "2026-07-01T12:00:00Z"}],
        "po_events": [event("E1", "CREATED", "2026-07-01T12:00:00Z"), event("E2", "APPROVED", "2026-08-02T12:00:00Z")],
        "invoices": [{"invoice_id": "I1", "supplier_id": "S1", "supplier_invoice_no": "COMM-1", "request_id": "R1", "po_id": "P1",
                      "issued_at": "2026-08-09T12:00:00Z", "received_at": RECEIPT,
                      "amount_minor": 10101, "currency": "GBP", "category": "ROUTINE", "document_type": "INVOICE"}],
        "case_events": [],
    }


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, data, taints=None, directory="run", start=START, as_of=CUTOFF):
        output = self.path / directory
        metrics = build_outputs(data, start, as_of, output, taints)
        with (output / "invoice_trace.csv").open(encoding="utf-8", newline="") as handle:
            rows = {row["invoice_id"]: row for row in csv.DictReader(handle)}
        with (output / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
            queue = list(csv.DictReader(handle))
        return metrics, rows, queue

    def test_later_approval_changes_current_but_does_not_backfill_arrival(self):
        data = fixture()
        data["po_events"][1] = event("E2", "APPROVED", "2026-08-20T12:00:00Z")
        data["case_events"] = [case("C1", "FOLLOW_UP", "2026-08-12T12:00:00Z")]
        metrics, rows, queue = self.build(data)
        row = rows["I1"]
        self.assertEqual((row["arrival_status"], row["arrival_reason"]), ("EXCEPTION", "PO_NOT_APPROVED"))
        self.assertEqual(row["current_status"], "READY")
        self.assertEqual(row["po_condition_cleared"], "1")
        self.assertEqual(row["case_state"], "OPEN")
        self.assertEqual(metrics["primary"]["numerator"], 1)
        self.assertEqual(metrics["supporting"]["open_exceptions_by_reason"]["total"], 0)
        self.assertEqual(queue, [])

    def test_reference_correction_keeps_original_arrival_reference(self):
        data = fixture()
        data["invoices"][0]["po_id"] = ""
        data["case_events"] = [case("C1", "REFERENCE_CONFIRMED", "2026-08-11T12:00:00Z", po="P1")]
        _, rows, _ = self.build(data)
        row = rows["I1"]
        self.assertEqual(row["original_po_id"], "")
        self.assertEqual(row["current_po_id"], "P1")
        self.assertEqual(row["arrival_reason"], "MISSING_PO_REFERENCE")
        self.assertEqual(row["current_status"], "READY")
        self.assertNotIn("case_event:C1", row["arrival_evidence_ids"])
        self.assertIn("case_event:C1", row["current_evidence_ids"])

    def test_late_recording_is_unknown_at_arrival_and_ready_at_cutoff(self):
        data = fixture()
        data["po_events"][1] = event("E2", "APPROVED", "2026-08-02T12:00:00Z", "2026-08-15T12:00:00Z")
        metrics, rows, _ = self.build(data)
        self.assertEqual(rows["I1"]["arrival_reason"], "LATE_RECORDED_PO_STATE")
        self.assertEqual(rows["I1"]["arrival_status"], "UNKNOWN")
        self.assertEqual(rows["I1"]["current_status"], "READY")
        self.assertIsNone(metrics["primary"]["percentage"])
        self.assertEqual(metrics["primary"]["denominator"], 0)
        self.assertEqual(metrics["primary"]["unknown_count"], 1)
        self.assertEqual(metrics["supporting"]["arrival_assessment_coverage"]["percentage"], 0.0)

    def test_exact_receipt_transition_unknown_but_fraction_before_is_ready(self):
        data = fixture()
        data["po_events"][1] = event("E2", "APPROVED", RECEIPT)
        _, rows, _ = self.build(data, directory="equal")
        self.assertEqual(rows["I1"]["arrival_reason"], "STATE_AT_RECEIPT")
        self.assertEqual(rows["I1"]["current_status"], "READY")
        data["po_events"][1] = event("E2", "APPROVED", "2026-08-10T11:59:59.999999Z")
        _, rows, _ = self.build(data, directory="microsecond")
        self.assertEqual(rows["I1"]["arrival_status"], "READY")

    def test_conflicting_latest_states_unknown_and_same_state_ties_allowed(self):
        data = fixture()
        data["po_events"].append(event("E3", "CANCELLED", "2026-08-02T12:00:00Z"))
        _, rows, queue = self.build(data, directory="different")
        self.assertEqual(rows["I1"]["arrival_reason"], "AMBIGUOUS_PO_STATE")
        self.assertEqual(rows["I1"]["current_reason"], "AMBIGUOUS_PO_STATE")
        self.assertEqual(queue[0]["routing"], "AP_DATA_INVESTIGATION")
        data["po_events"][-1]["status"] = "APPROVED"
        _, rows, _ = self.build(data, directory="same")
        self.assertEqual(rows["I1"]["arrival_status"], "READY")
        self.assertIn("po_event:E2", rows["I1"]["arrival_evidence_ids"])
        self.assertIn("po_event:E3", rows["I1"]["arrival_evidence_ids"])

    def test_future_effective_and_future_recorded_events_do_not_leak(self):
        data = fixture()
        data["po_events"] += [event("F1", "CANCELLED", "2026-09-01T00:00:00Z"),
                              event("F2", "CANCELLED", "2026-08-03T12:00:00Z", "2026-09-01T00:00:00Z")]
        data["case_events"] = [case("F3", "REFERENCE_CONFIRMED", "2026-09-01T00:00:00Z", po="DOES-NOT-EXIST"),
                               case("F4", "CASE_CLOSED", "2026-08-20T00:00:00Z", "2026-09-01T00:00:00Z")]
        _, rows, _ = self.build(data)
        row = rows["I1"]
        self.assertEqual((row["arrival_status"], row["current_status"], row["case_state"]), ("READY", "READY", "OPEN"))
        self.assertEqual(row["current_po_id"], "P1")
        for field in ("arrival_evidence_ids", "current_evidence_ids", "case_evidence_ids"):
            self.assertNotIn("F1", row[field])
            self.assertNotIn("F2", row[field])
            self.assertNotIn("F3", row[field])
            self.assertNotIn("F4", row[field])

    def test_latest_effective_not_latest_recorded_wins(self):
        data = fixture()
        data["po_events"] = [event("E1", "CREATED", "2026-07-01T12:00:00Z"),
                             event("E2", "CANCELLED", "2026-08-02T12:00:00Z", "2026-08-25T12:00:00Z"),
                             event("E3", "APPROVED", "2026-08-20T12:00:00Z")]
        _, rows, _ = self.build(data)
        self.assertEqual(rows["I1"]["arrival_reason"], "LATE_RECORDED_PO_STATE")
        self.assertEqual(rows["I1"]["current_status"], "READY")
        self.assertIn("po_event:E3", rows["I1"]["current_evidence_ids"])

    def test_case_closure_reopening_and_followup_are_distinct(self):
        data = fixture()
        data["po_events"] = data["po_events"][:1]
        data["case_events"] = [case("C1", "CASE_CLOSED", "2026-08-12T12:00:00Z"),
                               case("C2", "FOLLOW_UP", "2026-08-13T12:00:00Z")]
        metrics, rows, queue = self.build(data, directory="closed")
        self.assertEqual(rows["I1"]["current_status"], "EXCEPTION")
        self.assertEqual(rows["I1"]["case_state"], "CLOSED")
        self.assertEqual(rows["I1"]["po_condition_cleared"], "0")
        self.assertEqual(metrics["supporting"]["open_exceptions_by_reason"]["total"], 0)
        self.assertEqual(queue, [])
        data["case_events"].append(case("C3", "CASE_REOPENED", "2026-08-14T12:00:00Z"))
        metrics, rows, queue = self.build(data, directory="reopened")
        self.assertEqual(rows["I1"]["case_state"], "OPEN")
        self.assertEqual(metrics["supporting"]["open_exceptions_by_reason"]["total"], 1)
        self.assertEqual(len(queue), 1)

    def test_case_state_tie_routes_to_investigation_even_with_ready_header(self):
        data = fixture()
        data["case_events"] = [case("C1", "CASE_CLOSED", "2026-08-12T12:00:00Z"),
                               case("C2", "CASE_REOPENED", "2026-08-12T12:00:00Z")]
        metrics, rows, queue = self.build(data)
        self.assertEqual(rows["I1"]["current_status"], "READY")
        self.assertEqual(rows["I1"]["case_state"], "UNKNOWN")
        self.assertEqual(rows["I1"]["case_reason"], "AMBIGUOUS_CASE_STATE")
        self.assertEqual(queue[0]["routing"], "AP_DATA_INVESTIGATION")
        self.assertEqual(metrics["quality_controls"]["unknown_case_state_count"], 1)

    def test_reference_tie_unknown_only_for_current_reference(self):
        data = fixture()
        data["case_events"] = [case("C1", "REFERENCE_CONFIRMED", "2026-08-12T12:00:00Z", po="P1"),
                               case("C2", "REFERENCE_CONFIRMED", "2026-08-12T12:00:00Z", po="OTHER")]
        _, rows, queue = self.build(data)
        self.assertEqual(rows["I1"]["arrival_status"], "READY")
        self.assertEqual(rows["I1"]["current_reason"], "AMBIGUOUS_CURRENT_REFERENCE")
        self.assertEqual(rows["I1"]["current_po_id"], "")
        self.assertIn("case_event:C1", queue[0]["current_evidence_ids"])
        self.assertIn("case_event:C2", queue[0]["current_evidence_ids"])

    def test_many_events_and_shared_po_never_multiply_invoice_counts_or_money(self):
        data = fixture()
        data["po_events"] = data["po_events"][:1]
        data["po_events"] += [event("E" + str(n), "CREATED", "2026-08-0{}T12:00:00Z".format(n)) for n in range(2, 6)]
        second = dict(data["invoices"][0], invoice_id="I2", supplier_invoice_no="COMM-2", amount_minor=20303, received_at="2026-08-20T12:00:00Z")
        data["invoices"].append(second)
        data["case_events"] = [case("C" + str(n), "FOLLOW_UP", "2026-08-2{}T12:00:00Z".format(n), invoice=invoice) for n, invoice in enumerate(("I1", "I1", "I2", "I2"), 1)]
        metrics, rows, queue = self.build(data)
        support = metrics["supporting"]
        self.assertEqual(metrics["primary"]["numerator"], 2)
        self.assertEqual(metrics["primary"]["denominator"], 2)
        self.assertEqual(support["open_exceptions_by_reason"]["counts"], {"PO_NOT_APPROVED": 2})
        self.assertEqual(support["open_exceptions_gross_value"]["amount_minor"], 30404)
        self.assertEqual(support["open_exceptions_median_invoice_age"]["days"], 16.25)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(queue), 2)
        with sqlite3.connect(str(self.path / "run" / "model.sqlite")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM invoice_assessments").fetchone()[0], 2)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM interactions").fetchone()[0], 4)
            self.assertEqual(con.execute("SELECT DISTINCT dataset_kind FROM interactions").fetchall(), [("SYNTHETIC",)])

    def test_blank_owner_routes_triage_and_coverage_is_zero(self):
        data = fixture()
        data["invoices"][0]["request_id"] = "R2"
        data["purchase_orders"][0]["request_id"] = "R2"
        data["po_events"] = data["po_events"][:1]
        metrics, rows, queue = self.build(data)
        self.assertEqual(rows["I1"]["owner_role"], "")
        self.assertEqual(queue[0]["routing"], "AP_TRIAGE")
        self.assertEqual(metrics["supporting"]["open_exceptions_owner_coverage"]["percentage"], 0.0)
        self.assertEqual(metrics["supporting"]["open_exceptions_owner_coverage"]["ap_triage_count"], 1)

    def test_optional_blank_request_resolves_via_po_but_unknown_request_does_not(self):
        data = fixture()
        data["invoices"][0]["request_id"] = ""
        _, rows, _ = self.build(data, directory="blank")
        self.assertEqual(rows["I1"]["current_status"], "READY")
        self.assertEqual(rows["I1"]["owner_role"], "LAB_BUYER")
        data["invoices"][0]["request_id"] = "MISSING"
        _, rows, _ = self.build(data, directory="unknown")
        self.assertEqual(rows["I1"]["current_reason"], "UNKNOWN_REQUEST_IDENTITY")
        self.assertEqual(rows["I1"]["owner_role"], "")

    def test_po_created_after_receipt_and_missing_state_are_distinct(self):
        data = fixture()
        data["purchase_orders"][0]["created_at"] = "2026-08-15T12:00:00Z"
        data["po_events"] = [event("E1", "CREATED", "2026-08-15T12:00:00Z"), event("E2", "APPROVED", "2026-08-16T12:00:00Z")]
        _, rows, _ = self.build(data, directory="late")
        self.assertEqual(rows["I1"]["arrival_reason"], "PO_CREATED_AFTER_RECEIPT")
        self.assertEqual(rows["I1"]["current_status"], "READY")
        data = fixture()
        data["po_events"] = []
        _, rows, _ = self.build(data, directory="absent")
        self.assertEqual(rows["I1"]["arrival_status"], "UNKNOWN")
        self.assertEqual(rows["I1"]["arrival_reason"], "NO_PO_STATE_HISTORY")

    def test_known_mismatches_have_distinct_reasons(self):
        for field, value, expected in (("supplier_id", "S2", "SUPPLIER_MISMATCH"),
                                       ("request_id", "R2", "REQUEST_MISMATCH")):
            data = fixture()
            data["invoices"][0][field] = value
            _, rows, _ = self.build(data, directory=field)
            self.assertEqual(rows["I1"]["current_status"], "EXCEPTION")
            self.assertEqual(rows["I1"]["current_reason"], expected)
        data = fixture()
        data["purchase_orders"][0]["currency"] = "USD"
        _, rows, _ = self.build(data, directory="currency")
        self.assertEqual(rows["I1"]["current_reason"], "CURRENCY_MISMATCH")

    def test_tainted_history_cannot_silently_look_ready(self):
        metrics, rows, _ = self.build(fixture(), taints={"po_ids": {"P1": ["BAD_STATE"]}, "invoice_ids": {}}, directory="po")
        self.assertEqual(rows["I1"]["arrival_reason"], "INVALID_PO_HISTORY")
        self.assertEqual(rows["I1"]["current_reason"], "INVALID_PO_HISTORY")
        self.assertEqual(metrics["primary"]["unknown_count"], 1)
        _, rows, queue = self.build(fixture(), taints={"po_ids": {}, "invoice_ids": {"I1": ["INVALID_CASE_HISTORY"]}}, directory="case")
        self.assertEqual(rows["I1"]["arrival_reason"], "INVALID_CASE_HISTORY")
        self.assertEqual(rows["I1"]["current_reason"], "INVALID_CASE_HISTORY")
        self.assertEqual(rows["I1"]["case_state"], "UNKNOWN")
        self.assertEqual(queue[0]["routing"], "AP_DATA_INVESTIGATION")

    def test_commercial_collision_records_retained_and_not_assessable(self):
        data = fixture()
        data["invoices"].append(dict(data["invoices"][0], invoice_id="I2"))
        metrics, rows, queue = self.build(data)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["arrival_reason"] == "COMMERCIAL_DOCUMENT_COLLISION" for row in rows.values()))
        self.assertEqual(metrics["primary"]["unknown_count"], 2)
        self.assertEqual(metrics["primary"]["denominator"], 0)
        self.assertEqual(len(queue), 2)
        self.assertTrue(all(row["case_state"] == "OPEN" for row in rows.values()))

    def test_future_invoice_and_credit_note_do_not_create_invoice_collision(self):
        variants = (
            ("future", {"received_at": "2026-09-01T12:00:00Z"}, "AFTER_REPORT_CUTOFF"),
            ("credit", {"document_type": "CREDIT_NOTE", "amount_minor": -10101}, "CREDIT_NOTE"),
        )
        for name, changes, exclusion in variants:
            with self.subTest(name=name):
                data = fixture()
                data["invoices"].append(dict(data["invoices"][0], invoice_id="I2", **changes))
                metrics, rows, queue = self.build(data, directory=name)
                self.assertEqual(rows["I1"]["arrival_status"], "READY")
                self.assertEqual(rows["I1"]["current_status"], "READY")
                self.assertEqual(rows["I2"]["exclusion_reason"], exclusion)
                self.assertEqual(metrics["primary"]["denominator"], 1)
                self.assertEqual(metrics["primary"]["unknown_count"], 0)
                self.assertEqual(queue, [])

    def test_before_cohort_invoice_still_identifies_commercial_collision(self):
        data = fixture()
        data["invoices"].append(dict(data["invoices"][0], invoice_id="I2", received_at="2026-07-31T12:00:00Z"))
        metrics, rows, queue = self.build(data)
        self.assertEqual(rows["I1"]["arrival_reason"], "COMMERCIAL_DOCUMENT_COLLISION")
        self.assertEqual(rows["I1"]["current_reason"], "COMMERCIAL_DOCUMENT_COLLISION")
        self.assertEqual(rows["I2"]["exclusion_reason"], "BEFORE_COHORT_START")
        self.assertEqual(metrics["primary"]["denominator"], 0)
        self.assertEqual(metrics["primary"]["unknown_count"], 1)
        self.assertEqual([row["invoice_id"] for row in queue], ["I1"])

    def test_exclusions_and_quality_reconciliation_do_not_enter_primary(self):
        data = fixture()
        additions = [dict(invoice_id="I2", currency="USD"), dict(invoice_id="I3", document_type="CREDIT_NOTE", amount_minor=-100),
                     dict(invoice_id="I4", category="EMERGENCY"), dict(invoice_id="I5", received_at="2026-07-31T12:00:00Z"),
                     dict(invoice_id="I6", received_at="2026-09-01T12:00:00Z")]
        for extra in additions:
            data["invoices"].append(dict(data["invoices"][0], **dict(extra, supplier_invoice_no=extra["invoice_id"])))
        data["_quality_controls"] = {"invoice_raw_rows": 9, "invoice_canonical_rows": 6,
                                     "invoice_duplicate_rows_removed": 1, "invoice_quarantined_rows": 2}
        metrics, rows, _ = self.build(data)
        self.assertEqual(metrics["primary"]["denominator"], 1)
        self.assertEqual(metrics["quality_controls"]["excluded_canonical_invoice_records"], 5)
        self.assertTrue(metrics["quality_controls"]["invoice_row_reconciliation"]["balanced"])
        self.assertEqual(rows["I2"]["exclusion_reason"], "UNSUPPORTED_CURRENCY")
        self.assertEqual(rows["I3"]["exclusion_reason"], "CREDIT_NOTE")
        self.assertEqual(rows["I4"]["exclusion_reason"], "CATEGORY_EMERGENCY")
        self.assertEqual(rows["I5"]["exclusion_reason"], "BEFORE_COHORT_START")
        self.assertEqual(rows["I6"]["exclusion_reason"], "AFTER_REPORT_CUTOFF")
        self.assertIsNone(metrics["supporting"]["open_exceptions_owner_coverage"]["percentage"])

    def test_empty_data_yields_null_denominators_and_exact_metric_set(self):
        data = {key: [] for key in fixture()}
        metrics, rows, queue = self.build(data)
        self.assertEqual(rows, {})
        self.assertEqual(queue, [])
        self.assertIsNone(metrics["primary"]["percentage"])
        self.assertEqual(len(metrics["supporting"]), 5)
        self.assertIsNone(metrics["supporting"]["arrival_assessment_coverage"]["percentage"])
        self.assertIsNone(metrics["supporting"]["open_exceptions_median_invoice_age"]["days"])
        self.assertEqual(metrics["supporting"]["open_exceptions_gross_value"]["amount_minor"], 0)

    def test_cutoff_and_timezone_boundary_are_inclusive(self):
        data = fixture()
        data["invoices"][0]["received_at"] = "2026-08-31T23:30:00+05:30"
        data["po_events"].append(event("E3", "CANCELLED", CUTOFF))
        _, rows, _ = self.build(data)
        self.assertEqual(rows["I1"]["scope"], "ELIGIBLE")
        self.assertEqual(rows["I1"]["arrival_reason"], "STATE_AT_RECEIPT")
        self.assertEqual(rows["I1"]["current_reason"], "PO_CANCELLED")
        self.assertEqual(float(rows["I1"]["invoice_age_days"]), 0.0)

    def test_deterministic_artifacts_and_report_is_self_contained(self):
        data = fixture()
        data["po_events"] = data["po_events"][:1]
        data["case_events"] = [case("C1", "FOLLOW_UP", "2026-08-12T12:00:00Z")]
        self.build(data, directory="one")
        shuffled = copy.deepcopy(data)
        for rows in shuffled.values():
            rows.reverse()
        self.build(shuffled, directory="two")
        for filename in ("invoice_trace.csv", "review_queue.csv", "metrics.json", "report.html", "model.sqlite"):
            self.assertEqual((self.path / "one" / filename).read_bytes(), (self.path / "two" / filename).read_bytes(), filename)
        report = (self.path / "one" / "report.html").read_text(encoding="utf-8")
        self.assertIn("SYNTHETIC", report)
        self.assertIn("not unpaid value", report)
        self.assertIn("not elapsed exception duration", report)
        self.assertNotIn("<script", report)
        self.assertNotIn('href="http', report)
        self.assertNotIn('src="http', report)
        parsed = json.loads((self.path / "one" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(parsed["dataset_kind"], "SYNTHETIC")


if __name__ == "__main__":
    unittest.main()
