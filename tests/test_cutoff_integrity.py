"""Cutoff filtering does not override conflicting source-event identities.

The generated sources and every mutation/output stay in a TemporaryDirectory.
"""

import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from po_review.generate import generate_sources
from po_review.pipeline import run_pipeline


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class CutoffIntegrityTests(unittest.TestCase):
    def test_future_event_identity_conflict_invalidates_earlier_evidence(self):
        invoice_id = "INV-CASE-REFERENCE-REPAIR"
        approval_id = "PE-CASE-REFERENCE-REPAIR-02"
        future_id = "PE-CUTOFF-INTEGRITY-FUTURE"
        cutoff = "2026-08-31T18:00:00Z"
        later = "2026-09-01T00:00:00Z"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "sources"
            manifest = generate_sources(sources)
            database = sources / "procurement.sqlite"
            # All three timestamps use the same UTC representation. The added
            # event is after the assessment cutoff but inside the source export.
            self.assertLess(cutoff, later)
            self.assertLessEqual(later, manifest["exported_at"])

            def run_variant(name):
                # The test authors a new temporary export, so its manifest must
                # declare the changed SQLite bytes accurately.
                manifest["files"]["procurement.sqlite"]["sha256"] = hashlib.sha256(database.read_bytes()).hexdigest()
                (sources / "export_manifest.json").write_text(
                    json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
                run = run_pipeline(sources, root / name, as_of=cutoff)
                trace = {row["invoice_id"]: row for row in read_csv(run / "invoice_trace.csv")}
                queue = [row for row in read_csv(run / "review_queue.csv") if row["invoice_id"] == invoice_id]
                return read_csv(run / "quality_issues.csv"), trace[invoice_id], queue

            _, baseline, queue = run_variant("baseline")
            self.assertEqual((baseline["current_status"], baseline["current_reason"], baseline["review_required"]),
                             ("READY", "READY", "0"))
            self.assertIn("po_event:" + approval_id, baseline["current_evidence_ids"].split(";"))
            self.assertEqual(queue, [])

            with sqlite3.connect(str(database)) as connection:
                connection.execute(
                    "INSERT INTO po_events (event_id, po_id, status, effective_at, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (future_id, "PO-CASE-REFERENCE-REPAIR", "CANCELLED", later, later))

            unique_issues, unique, queue = run_variant("unique-future-event")
            self.assertEqual(unique, baseline, "A valid unique later event must not change the cutoff assessment")
            self.assertEqual(queue, [])
            self.assertFalse([row for row in unique_issues
                              if row["source"] == "po_events" and row["record_id"] == future_id])

            # Change only the later event's raw identity. SQLite accepts this
            # distinct key; declared whitespace/case normalization makes it
            # conflict with the approval supporting the earlier READY result.
            with sqlite3.connect(str(database)) as connection:
                connection.execute("UPDATE po_events SET event_id = ? WHERE event_id = ?",
                                   (" " + approval_id.lower() + " ", future_id))

            conflict_issues, conflict, queue = run_variant("conflicting-future-event")
            self.assertEqual((conflict["current_status"], conflict["current_reason"], conflict["review_required"]),
                             ("UNKNOWN", "INVALID_PO_HISTORY", "1"))
            self.assertEqual(conflict["po_condition_cleared"], "0")
            self.assertNotIn("po_event:" + approval_id, conflict["current_evidence_ids"].split(";"))
            self.assertEqual(len(queue), 1)
            self.assertEqual((queue[0]["current_status"], queue[0]["routing"]),
                             ("UNKNOWN", "AP_DATA_INVESTIGATION"))
            conflicts = [row for row in conflict_issues
                         if row["source"] == "po_events" and row["record_id"] == approval_id]
            self.assertEqual(len(conflicts), 2, "Both competing versions must be visibly quarantined")
            self.assertEqual({(row["severity"], row["rule"]) for row in conflicts},
                             {("QUARANTINE", "CONFLICTING_DUPLICATE_ID")})


if __name__ == "__main__":
    unittest.main()
