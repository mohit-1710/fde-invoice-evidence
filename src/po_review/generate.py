"""Create explicitly synthetic procurement/AP sources, independently of the model.

The chosen cases exercise declared evidence rules; their frequency is not an
estimate of any organisation's workload. Nothing in this module imports the
pipeline, its validation, or its classifications.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

INVOICE_COLUMNS = (
    "invoice_id", "supplier_id", "supplier_invoice_no", "request_id", "po_id",
    "issued_at", "received_at", "amount_minor", "currency", "category", "document_type",
)
CASE_COLUMNS = (
    "event_id", "invoice_id", "event_type", "effective_at", "recorded_at", "po_id",
    "actor_role", "note",
)
SOURCE_FILES = ("procurement.sqlite", "ap_invoices.csv", "ap_case_events.csv")
MANIFEST_FILE = "export_manifest.json"
HISTORY_START = "2026-07-01T00:00:00Z"
EXPORT_TIME = "2026-09-01T12:00:00Z"
DEFAULT_START = "2026-08-01T00:00:00Z"
DEFAULT_AS_OF = "2026-08-31T18:00:00Z"
SCENARIO_RECEIPT = "2026-08-10T10:00:00Z"


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _Sources:
    def __init__(self) -> None:
        self.departments = [
            ("DEPT-01", "Fictional Workplace Services", "WORKPLACE_BUYER"),
            ("DEPT-02", "Fictional Digital Operations", "DIGITAL_BUYER"),
            ("DEPT-03", "Fictional Field Logistics", "LOGISTICS_BUYER"),
            ("DEPT-04", "Fictional Shared Support", ""),
            ("DEPT-05", "Fictional Learning Studio", "LEARNING_BUYER"),
        ]
        self.suppliers = [
            ("SUP-01", "Fictional Kestrel Paperworks"),
            ("SUP-02", "Fictional Juniper Device Care"),
            ("SUP-03", "Fictional Amber Route Supplies"),
            ("SUP-04", "Fictional Fern Workshop Goods"),
            ("SUP-05", "Fictional Lantern Workspace"),
            ("SUP-06", "Fictional Willow Learning Materials"),
            ("SUP-07", "Fictional Pebble Maintenance"),
            ("SUP-08", "Fictional Copper Parcel Services"),
        ]
        self.requests: List[Tuple[str, ...]] = []
        self.purchase_orders: List[Tuple[str, ...]] = []
        self.po_events: List[Tuple[str, ...]] = []
        self.invoices: List[Dict[str, Any]] = []
        self.case_events: List[Dict[str, str]] = []

    def order(
        self, tag: str, supplier: str = "SUP-01", department: str = "DEPT-01",
        created_at: str = "2026-07-25T09:00:00Z", currency: str = "GBP",
        requested_at: str = "2026-07-20T09:00:00Z",
        states: Optional[List[Tuple[str, str, str]]] = None,
    ) -> Tuple[str, str]:
        request_id, po_id = "REQ-" + tag, "PO-" + tag
        self.requests.append((request_id, supplier, department, requested_at, "ROUTINE"))
        self.purchase_orders.append((po_id, request_id, supplier, currency, created_at))
        if states is None:
            states = [
                ("CREATED", created_at, created_at),
                ("APPROVED", "2026-07-26T09:00:00Z", "2026-07-26T09:00:00Z"),
            ]
        for position, (status, effective_at, recorded_at) in enumerate(states, 1):
            self.po_events.append((
                "PE-" + tag + "-%02d" % position, po_id, status, effective_at, recorded_at,
            ))
        return request_id, po_id

    def invoice(
        self, tag: str, request_id: str, po_id: str, supplier: str = "SUP-01",
        **overrides: Any,
    ) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "invoice_id": "INV-" + tag,
            "supplier_id": supplier,
            "supplier_invoice_no": "SYNTHETIC-" + tag,
            "request_id": request_id,
            "po_id": po_id,
            "issued_at": "2026-08-08T09:00:00Z",
            "received_at": SCENARIO_RECEIPT,
            "amount_minor": 31050,
            "currency": "GBP",
            "category": "ROUTINE",
            "document_type": "INVOICE",
        }
        row.update(overrides)
        self.invoices.append(row)
        return row

    def interaction(
        self, tag: str, invoice_id: str, event_type: str, effective_at: str,
        po_id: str = "", recorded_at: Optional[str] = None,
        actor_role: str = "AP_PROCESSOR", note: str = "",
    ) -> None:
        self.case_events.append({
            "event_id": "CE-" + tag,
            "invoice_id": invoice_id,
            "event_type": event_type,
            "effective_at": effective_at,
            "recorded_at": recorded_at or effective_at,
            "po_id": po_id,
            "actor_role": actor_role,
            "note": "SYNTHETIC historical event. " + note,
        })


def _ordinary_sources(source: _Sources, seed: int) -> None:
    """Sixty illustrative rows with limited variety, not calibrated frequencies."""
    rng = random.Random(seed)
    base = datetime(2026, 8, 2, 10, tzinfo=timezone.utc)
    for index in range(1, 61):
        tag = "SYN-%03d" % index
        supplier = "SUP-%02d" % rng.randint(1, 8)
        department = "DEPT-%02d" % rng.randint(1, 5)
        received = base + timedelta(days=rng.randint(0, 23), hours=rng.randint(0, 5))
        created = received - timedelta(days=rng.randint(5, 12))
        approved = created + timedelta(days=1)
        profile = index % 10
        states = [("CREATED", _utc(created), _utc(created))]
        if profile != 6:
            approved = received + timedelta(days=3) if profile == 7 else approved
            states.append(("APPROVED", _utc(approved), _utc(approved)))
        if profile == 9:
            cancelled = received - timedelta(days=1)
            states.append(("CANCELLED", _utc(cancelled), _utc(cancelled)))
        request_id, po_id = source.order(
            tag, supplier, department, _utc(created),
            requested_at=_utc(created - timedelta(days=2)), states=states,
        )
        row = source.invoice(
            tag, request_id, "" if profile == 8 else po_id, supplier,
            issued_at=_utc(received - timedelta(days=rng.randint(1, 3))),
            received_at=_utc(received), amount_minor=rng.randint(1500, 450000),
        )
        if profile in (6, 7, 8, 9):
            source.interaction(
                tag + "-FOLLOWUP", row["invoice_id"], "FOLLOW_UP",
                _utc(received + timedelta(days=1)),
                note="Illustrative request for PO evidence; no resolution is implied.",
            )
        elif index % 4 == 0:
            source.interaction(
                tag + "-CLOSED", row["invoice_id"], "CASE_CLOSED",
                _utc(received + timedelta(days=4)),
                note="Illustrative AP case closure; payment status is not supplied.",
            )


def _named_sources(s: _Sources) -> None:
    """Deliberately authored counterexamples; independent labels live in data/."""
    created = ("CREATED", "2026-07-25T09:00:00Z", "2026-07-25T09:00:00Z")
    approved = ("APPROVED", "2026-07-26T09:00:00Z", "2026-07-26T09:00:00Z")

    req, po = s.order("CASE-LATER-APPROVAL", states=[
        created, ("APPROVED", "2026-08-15T09:00:00Z", "2026-08-15T09:00:00Z"),
    ])
    s.invoice("CASE-LATER-APPROVAL", req, po)
    s.interaction("LATER-APPROVAL-FOLLOWUP", "INV-CASE-LATER-APPROVAL", "FOLLOW_UP",
                  "2026-08-12T09:00:00Z", note="Buyer asked to inspect approval evidence.")

    req, po = s.order("CASE-REFERENCE-REPAIR")
    s.invoice("CASE-REFERENCE-REPAIR", req, "")
    s.interaction("REFERENCE-REPAIR", "INV-CASE-REFERENCE-REPAIR", "REFERENCE_CONFIRMED",
                  "2026-08-12T09:00:00Z", po, actor_role="DEPARTMENT_BUYER",
                  note="PO reference confirmed; original invoice reference stays empty.")

    req, po = s.order("CASE-WRONG-SUPPLIER")
    s.invoice("CASE-WRONG-SUPPLIER", req, po, supplier="SUP-02")

    req, _ = s.order("CASE-MISSING-REFERENCE")
    s.invoice("CASE-MISSING-REFERENCE", req, "")
    req, _ = s.order("CASE-UNKNOWN-REFERENCE")
    s.invoice("CASE-UNKNOWN-REFERENCE", req, "PO-NOT-IN-REGISTRY")

    req, po = s.order("CASE-ABSENT-OWNER", department="DEPT-04", states=[created])
    s.invoice("CASE-ABSENT-OWNER", req, po)
    req, po = s.order("CASE-NO-STATE", states=[])
    s.invoice("CASE-NO-STATE", req, po)
    req, po = s.order("CASE-AMBIGUOUS-STATE", states=[created,
        ("APPROVED", "2026-08-05T09:00:00Z", "2026-08-05T09:00:00Z"),
        ("CANCELLED", "2026-08-05T09:00:00Z", "2026-08-05T09:00:00Z"),
    ])
    s.invoice("CASE-AMBIGUOUS-STATE", req, po)
    req, po = s.order("CASE-LATE-RECORDED", states=[created,
        ("APPROVED", "2026-08-05T09:00:00Z", "2026-08-12T09:00:00Z"),
    ])
    s.invoice("CASE-LATE-RECORDED", req, po)

    req, po = s.order("CASE-CLEANUP")
    s.invoice("CASE-CLEANUP", "  " + req.lower() + "  ", " " + po.lower() + " ",
              supplier=" sup-01 ", invoice_id=" inv-case-cleanup ",
              currency=" gbp ", category=" routine ", document_type=" invoice ",
              amount_minor=" 31050 ", received_at="2026-08-10T11:00:00+01:00")

    req, po = s.order("CASE-EXACT-DUPLICATE")
    duplicate = s.invoice("CASE-EXACT-DUPLICATE", req, po)
    s.invoices.append(dict(duplicate))
    req, po = s.order("CASE-CONFLICT-DUPLICATE")
    conflicting = s.invoice("CASE-CONFLICT-DUPLICATE", req, po)
    s.invoices.append(dict(conflicting, amount_minor=31100))

    req, po = s.order("CASE-BAD-TIMESTAMP")
    s.invoice("CASE-BAD-TIMESTAMP", req, po, received_at="2026-08-99T10:00:00Z")
    req, po = s.order("CASE-BAD-AMOUNT")
    s.invoice("CASE-BAD-AMOUNT", req, po, amount_minor="123.45")
    req, po = s.order("CASE-CREDIT-NOTE")
    s.invoice("CASE-CREDIT-NOTE", req, po, document_type="CREDIT_NOTE", amount_minor=-12500)
    req, po = s.order("CASE-NON-GBP", currency="USD")
    s.invoice("CASE-NON-GBP", req, po, currency="USD")
    for category in ("EMERGENCY", "CAPITAL", "PO_EXEMPT"):
        tag = "CASE-" + category.replace("_", "-")
        req, po = s.order(tag)
        s.invoice(tag, req, po, category=category)

    req, po = s.order("CASE-SHARED-PO", states=[created, approved,
        ("APPROVED", "2026-08-04T09:00:00Z", "2026-08-04T09:00:00Z"),
    ])
    s.invoice("CASE-SHARED-PO-A", req, po, amount_minor=12000)
    s.invoice("CASE-SHARED-PO-B", req, po, amount_minor=18000)
    for suffix in ("A", "B"):
        for day in (11, 12):
            s.interaction("SHARED-" + suffix + "-%d" % day,
                          "INV-CASE-SHARED-PO-" + suffix, "FOLLOW_UP",
                          "2026-08-%02dT09:00:00Z" % day,
                          note="Synthetic repeated contact tests invoice-grain aggregation.")

    req, po = s.order("CASE-FUTURE-STATE", states=[created, approved,
        ("CANCELLED", "2026-08-31T20:00:00Z", "2026-08-31T20:00:00Z"),
    ])
    s.invoice("CASE-FUTURE-STATE", req, po)

    req, po = s.order("CASE-CLOSED-PO", states=[created, approved,
        ("CLOSED", "2026-08-08T09:00:00Z", "2026-08-08T09:00:00Z"),
    ])
    s.invoice("CASE-CLOSED-PO", req, po)

    for tag in ("CASE-CLOSED", "CASE-REOPENED"):
        req, _ = s.order(tag)
        s.invoice(tag, req, "")
        s.interaction(tag + "-CLOSE", "INV-" + tag, "CASE_CLOSED", "2026-08-14T09:00:00Z",
                      note="AP case closed while PO condition remains; this is not payment.")
    s.interaction("CASE-REOPENED-REOPEN", "INV-CASE-REOPENED", "CASE_REOPENED",
                  "2026-08-20T09:00:00Z", note="AP review reopened explicitly.")

    req, po = s.order("CASE-BAD-PO-HISTORY", states=[created, approved,
        ("UNRECOGNISED_STATE", "2026-08-08T09:00:00Z", "2026-08-08T09:00:00Z"),
    ])
    s.invoice("CASE-BAD-PO-HISTORY", req, po)
    req, po = s.order("CASE-LATE-CREATED", created_at="2026-08-12T09:00:00Z", states=[
        ("CREATED", "2026-08-12T09:00:00Z", "2026-08-12T09:00:00Z"),
        ("APPROVED", "2026-08-14T09:00:00Z", "2026-08-14T09:00:00Z"),
    ])
    s.invoice("CASE-LATE-CREATED", req, po)
    req, po = s.order("CASE-EQUAL-RECEIPT", states=[created,
        ("APPROVED", SCENARIO_RECEIPT, SCENARIO_RECEIPT),
    ])
    s.invoice("CASE-EQUAL-RECEIPT", req, po)

    _, po = s.order("CASE-WRONG-REQUEST")
    other_req, _ = s.order("CASE-ALTERNATIVE-REQUEST")
    s.invoice("CASE-WRONG-REQUEST", other_req, po)
    req, po = s.order("CASE-CURRENCY-MISMATCH", currency="EUR")
    s.invoice("CASE-CURRENCY-MISMATCH", req, po)
    req, po = s.order("CASE-UNKNOWN-SUPPLIER")
    s.invoice("CASE-UNKNOWN-SUPPLIER", req, po, supplier="SUP-NOT-IN-REGISTRY")
    _, po = s.order("CASE-UNKNOWN-REQUEST")
    s.invoice("CASE-UNKNOWN-REQUEST", "REQ-NOT-IN-REGISTRY", po)

    for suffix in ("A", "B"):
        tag = "CASE-COMMERCIAL-COLLISION-" + suffix
        req, po = s.order(tag)
        s.invoice(tag, req, po, supplier_invoice_no="SYNTHETIC-SHARED-COMMERCIAL-REFERENCE")

    req, po = s.order("CASE-AMBIGUOUS-REFERENCE")
    s.invoice("CASE-AMBIGUOUS-REFERENCE", req, po)
    _, other_po = s.order("CASE-ALTERNATIVE-REFERENCE")
    for suffix, reference in (("A", po), ("B", other_po)):
        s.interaction("AMBIGUOUS-REFERENCE-" + suffix, "INV-CASE-AMBIGUOUS-REFERENCE",
                      "REFERENCE_CONFIRMED", "2026-08-15T09:00:00Z", reference,
                      actor_role="DEPARTMENT_BUYER", note="Conflicting same-time reference evidence.")

    req, po = s.order("CASE-BAD-CASE-HISTORY")
    s.invoice("CASE-BAD-CASE-HISTORY", req, po)
    s.interaction("BAD-CASE-HISTORY", "INV-CASE-BAD-CASE-HISTORY", "CASE_CLOSED",
                  "2026-08-13T09:00:00Z", recorded_at="not-a-timestamp",
                  note="Deliberately malformed closure history must not silently clear a case.")

    req, po = s.order("CASE-FUTURE-REFERENCE")
    s.invoice("CASE-FUTURE-REFERENCE", req, "")
    s.interaction("FUTURE-REFERENCE", "INV-CASE-FUTURE-REFERENCE", "REFERENCE_CONFIRMED",
                  "2026-08-31T20:00:00Z", po, actor_role="DEPARTMENT_BUYER",
                  note="Recorded after cutoff and must not change the default report.")

    req, po = s.order("CASE-LATE-CANCELLATION", states=[created, approved,
        ("CANCELLED", "2026-08-08T09:00:00Z", "2026-08-12T09:00:00Z"),
    ])
    s.invoice("CASE-LATE-CANCELLATION", req, po)
    req, po = s.order("CASE-BEFORE-COHORT")
    s.invoice("CASE-BEFORE-COHORT", req, po, issued_at="2026-07-28T09:00:00Z",
              received_at="2026-07-30T10:00:00Z")
    req, po = s.order("CASE-AFTER-CUTOFF")
    s.invoice("CASE-AFTER-CUTOFF", req, po, issued_at="2026-08-30T09:00:00Z",
              received_at="2026-08-31T20:00:00Z")


def _write_sqlite(path: Path, source: _Sources) -> None:
    with sqlite3.connect(str(path)) as connection:
        connection.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE departments (
                department_id TEXT PRIMARY KEY, name TEXT, owner_role TEXT
            );
            CREATE TABLE suppliers (supplier_id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE requests (
                request_id TEXT PRIMARY KEY, supplier_id TEXT REFERENCES suppliers(supplier_id),
                department_id TEXT REFERENCES departments(department_id), requested_at TEXT,
                category TEXT
            );
            CREATE TABLE purchase_orders (
                po_id TEXT PRIMARY KEY, request_id TEXT REFERENCES requests(request_id),
                supplier_id TEXT REFERENCES suppliers(supplier_id), currency TEXT, created_at TEXT
            );
            CREATE TABLE po_events (
                event_id TEXT PRIMARY KEY, po_id TEXT REFERENCES purchase_orders(po_id),
                status TEXT, effective_at TEXT, recorded_at TEXT
            );
        """)
        for table, width in (("departments", 3), ("suppliers", 2), ("requests", 5),
                             ("purchase_orders", 5), ("po_events", 5)):
            connection.executemany(
                "INSERT INTO " + table + " VALUES (" + ",".join(["?"] * width) + ")",
                sorted(getattr(source, table)),
            )


def _write_csv(path: Path, columns: Tuple[str, ...], rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda value: tuple(str(value[key]) for key in columns)):
            writer.writerow(row)


def generate_sources(output_dir: Path, seed: int = 20260918, force: bool = False) -> dict:
    """Write synthetic SQLite and CSV exports and return their snapshot manifest.

    Existing named inputs (including a manifest on its own) cause FileExistsError
    before any file changes, unless force=True. Unrelated files are preserved.
    Randomness affects ordinary examples only; authored adversarial cases are fixed.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    output_dir = Path(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(str(output_dir))
    targets = SOURCE_FILES + (MANIFEST_FILE,)
    existing = [name for name in targets
                if (output_dir / name).exists() or (output_dir / name).is_symlink()]
    if existing and not force:
        raise FileExistsError("Refusing to replace existing synthetic inputs without force=True: "
                              + ", ".join(existing))
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    source = _Sources()
    _ordinary_sources(source, seed)
    _named_sources(source)
    # Stage a complete fixture before touching the destination's named inputs.
    with tempfile.TemporaryDirectory(prefix=".synthetic-sources-", dir=str(output_dir.parent)) as tmp:
        staging = Path(tmp)
        _write_sqlite(staging / "procurement.sqlite", source)
        _write_csv(staging / "ap_invoices.csv", INVOICE_COLUMNS, source.invoices)
        _write_csv(staging / "ap_case_events.csv", CASE_COLUMNS, source.case_events)
        manifest = {
            "schema_version": 1,
            "dataset_kind": "synthetic",
            "seed": seed,
            "organisation": "Fictional Alder Vale Services — demonstration only",
            "history_start": HISTORY_START,
            "exported_at": EXPORT_TIME,
            "default_start": DEFAULT_START,
            "default_as_of": DEFAULT_AS_OF,
            "completeness": {
                "po_registry_complete": True,
                "po_history_complete": True,
                "invoice_feed_complete": True,
                "case_history_complete": True,
            },
            "files": {name: {"sha256": _sha256(staging / name)} for name in SOURCE_FILES},
            "synthetic_design_note": (
                "All operational records and interactions are fictional. Scenario frequencies "
                "are deliberately chosen tests, not measured or estimated organisational data. "
                "Declared completeness bounds this generated snapshot and is not evidence "
                "about any real system. No time savings, payment outcome or intervention benefit "
                "has been measured."
            ),
        }
        (staging / MANIFEST_FILE).write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        # Check again after staging, so an ordinary rerun never replaces new inputs.
        if not force:
            concurrent = [name for name in targets
                          if (output_dir / name).exists() or (output_dir / name).is_symlink()]
            if concurrent:
                raise FileExistsError("Source inputs appeared while staging; refusing overwrite: "
                                      + ", ".join(concurrent))
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in targets:
            os.replace(str(staging / name), str(output_dir / name))
    return manifest
