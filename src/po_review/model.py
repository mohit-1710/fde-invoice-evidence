"""Invoice-grain, point-in-time PO header evidence review (synthetic only).

Retrieval and validation belong to the pipeline. This module accepts canonical
records, preserves them in SQLite, reduces histories to one assessment per
invoice, and only then joins and aggregates for the six declared measures.
"""

import csv
import html
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REASONS = {
    "READY": "PO header identity, currency and approval evidence satisfy the declared rules.",
    "MISSING_PO_REFERENCE": "No PO reference is supplied; this does not prove that no other PO exists.",
    "PO_NOT_FOUND": "The supplied PO reference is absent from the declared complete registry.",
    "PO_CREATED_AFTER_RECEIPT": "The referenced PO was created after invoice receipt.",
    "PO_CREATED_AFTER_CUTOFF": "The referenced PO had not been created at the report cutoff.",
    "SUPPLIER_MISMATCH": "Known supplier identities disagree across the invoice, request or PO.",
    "REQUEST_MISMATCH": "The known invoice request differs from the PO request.",
    "CURRENCY_MISMATCH": "Invoice and PO currencies differ.",
    "PO_NOT_APPROVED": "The latest eligible PO state is CREATED, without an effective approval.",
    "PO_CLOSED": "The latest eligible PO state is CLOSED and requires human review.",
    "PO_CANCELLED": "The latest eligible PO state is CANCELLED and requires human review.",
    "UNKNOWN_SUPPLIER_IDENTITY": "A supplier identity cannot be resolved in the source registry.",
    "UNKNOWN_REQUEST_IDENTITY": "A supplied request identity cannot be resolved in the source registry.",
    "COMMERCIAL_DOCUMENT_COLLISION": "Multiple invoice records share the supplier and commercial document number.",
    "INVALID_PO_HISTORY": "Validation identified invalid history for this PO; discarding it cannot establish state.",
    "INVALID_CASE_HISTORY": "Validation identified invalid invoice case history; its effect is unresolved.",
    "NO_PO_STATE_HISTORY": "No eligible state evidence is available for the existing PO.",
    "AMBIGUOUS_PO_STATE": "Different PO states share the latest eligible effective timestamp.",
    "AMBIGUOUS_CURRENT_REFERENCE": "Different reference confirmations share the latest eligible effective timestamp.",
    "STATE_AT_RECEIPT": "A PO state transition coincides exactly with receipt; cross-system order is unknown.",
    "LATE_RECORDED_PO_STATE": "A pre-receipt state event was recorded after receipt, so arrival state cannot be backfilled.",
    "AMBIGUOUS_CASE_STATE": "Closure and reopening share the latest effective timestamp.",
}

SOURCE_COLUMNS = {
    "departments": ("department_id", "name", "owner_role"),
    "suppliers": ("supplier_id", "name"),
    "requests": ("request_id", "supplier_id", "department_id", "requested_at", "category"),
    "purchase_orders": ("po_id", "request_id", "supplier_id", "currency", "created_at"),
    "po_events": ("event_id", "po_id", "status", "effective_at", "recorded_at"),
    "invoices": ("invoice_id", "supplier_id", "supplier_invoice_no", "request_id", "po_id", "issued_at", "received_at", "amount_minor", "currency", "category", "document_type"),
    "case_events": ("event_id", "invoice_id", "event_type", "effective_at", "recorded_at", "po_id", "actor_role", "note"),
}

TRACE_FIELDS = (
    "invoice_id", "dataset_kind", "scope", "exclusion_reason", "supplier_id",
    "supplier_invoice_no", "request_id", "received_at", "issued_at", "amount_minor",
    "currency", "category", "document_type", "original_po_id", "current_po_id",
    "arrival_status", "arrival_reason", "arrival_reason_detail", "arrival_evidence_ids",
    "current_status", "current_reason", "current_reason_detail", "current_evidence_ids",
    "case_state", "case_reason", "case_evidence_ids", "po_condition_cleared",
    "owner_request_id", "department_id", "owner_role", "routing", "proposed_action",
    "invoice_age_days", "review_required",
)

QUEUE_FIELDS = (
    "invoice_id", "dataset_kind", "received_at", "invoice_age_days", "amount_minor",
    "currency", "original_po_id", "current_po_id", "arrival_status", "arrival_reason",
    "current_status", "current_reason", "current_reason_detail", "case_state",
    "case_reason", "arrival_evidence_ids", "current_evidence_ids", "case_evidence_ids",
    "owner_role", "routing", "proposed_action",
)


def _dt(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Point-in-time model requires timezone-aware timestamps")
    return result.astimezone(timezone.utc)


def _utc(value):
    return _dt(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _ids(*values):
    return ";".join(sorted({str(v) for value in values for v in
                            (value if isinstance(value, (tuple, list, set)) else [value]) if v}))


def _result(status, reason, evidence):
    return {"status": status, "reason": reason, "detail": REASONS[reason], "evidence": evidence}


def _eligible_events(events, as_of):
    return [event for event in events if _dt(event["effective_at"]) <= as_of
            and _dt(event["recorded_at"]) <= as_of]


def _latest_group(events):
    if not events:
        return []
    latest = max(_dt(event["effective_at"]) for event in events)
    return sorted((event for event in events if _dt(event["effective_at"]) == latest),
                  key=lambda event: event["event_id"])


def _case_snapshot(invoice, events, as_of, invalid_case_history):
    known = _eligible_events(events, as_of)
    reference_group = _latest_group([e for e in known if e["event_type"] == "REFERENCE_CONFIRMED"])
    references = {e["po_id"] for e in reference_group}
    ambiguous_reference = len(references) > 1
    reference = "" if ambiguous_reference else (next(iter(references)) if references else invoice["po_id"])
    ref_evidence = ["case_event:" + e["event_id"] for e in reference_group]
    state_group = _latest_group([e for e in known if e["event_type"] in ("CASE_CLOSED", "CASE_REOPENED")])
    states = {e["event_type"] for e in state_group}
    evidence = _ids("invoice:" + invoice["invoice_id"], ["case_event:" + e["event_id"] for e in state_group])
    if invalid_case_history:
        state, reason = "UNKNOWN", "INVALID_CASE_HISTORY"
    elif len(states) > 1:
        state, reason = "UNKNOWN", "AMBIGUOUS_CASE_STATE"
    elif states == {"CASE_CLOSED"}:
        state, reason = "CLOSED", "EXPLICIT_CASE_CLOSED"
    elif states == {"CASE_REOPENED"}:
        state, reason = "OPEN", "EXPLICIT_CASE_REOPENED"
    else:
        state, reason = "OPEN", "OPEN_AT_RECEIPT"
    return reference, ambiguous_reference, ref_evidence, state, reason, evidence


def _assess(invoice, po_id, moment, as_of, arrival, indexes, po_histories,
            po_taints, invoice_reason, ref_evidence=(), ambiguous_reference=False):
    evidence = _ids("invoice:" + invoice["invoice_id"], ref_evidence)
    if invoice_reason:
        return _result("UNKNOWN", invoice_reason, evidence)
    if ambiguous_reference:
        return _result("UNKNOWN", "AMBIGUOUS_CURRENT_REFERENCE", evidence)
    if not po_id:
        return _result("EXCEPTION", "MISSING_PO_REFERENCE", evidence)
    evidence = _ids(evidence.split(";"), "po:" + po_id)
    po = indexes["purchase_orders"].get(po_id)
    if po is None:
        return _result("EXCEPTION", "PO_NOT_FOUND", evidence)
    if po_id in po_taints:
        return _result("UNKNOWN", "INVALID_PO_HISTORY", evidence)
    supplier_ids = [invoice["supplier_id"], po["supplier_id"]]
    if any(supplier_id not in indexes["suppliers"] for supplier_id in supplier_ids):
        return _result("UNKNOWN", "UNKNOWN_SUPPLIER_IDENTITY", evidence)
    request_ids = [po["request_id"]] + ([invoice["request_id"]] if invoice["request_id"] else [])
    if any(request_id not in indexes["requests"] for request_id in request_ids):
        return _result("UNKNOWN", "UNKNOWN_REQUEST_IDENTITY", evidence)
    requests = [indexes["requests"][request_id] for request_id in request_ids]
    if any(request["supplier_id"] not in indexes["suppliers"] for request in requests):
        return _result("UNKNOWN", "UNKNOWN_SUPPLIER_IDENTITY", evidence)
    evidence = _ids(evidence.split(";"), ["supplier:" + s for s in supplier_ids],
                    ["request:" + r for r in request_ids])
    if len(set(supplier_ids + [request["supplier_id"] for request in requests])) > 1:
        return _result("EXCEPTION", "SUPPLIER_MISMATCH", evidence)
    if invoice["request_id"] and invoice["request_id"] != po["request_id"]:
        return _result("EXCEPTION", "REQUEST_MISMATCH", evidence)
    if invoice["currency"] != po["currency"]:
        return _result("EXCEPTION", "CURRENCY_MISMATCH", evidence)
    if _dt(po["created_at"]) > moment:
        reason = "PO_CREATED_AFTER_RECEIPT" if arrival else "PO_CREATED_AFTER_CUTOFF"
        return _result("EXCEPTION", reason, evidence)
    known = _eligible_events(po_histories.get(po_id, []), as_of)
    before = [e for e in known if _dt(e["effective_at"]) <= moment]
    if arrival:
        equal = [e for e in before if _dt(e["effective_at"]) == moment]
        if equal:
            return _result("UNKNOWN", "STATE_AT_RECEIPT", _ids(evidence.split(";"),
                           ["po_event:" + e["event_id"] for e in equal]))
        late = [e for e in before if _dt(e["recorded_at"]) > moment]
        if late:
            return _result("UNKNOWN", "LATE_RECORDED_PO_STATE", _ids(evidence.split(";"),
                           ["po_event:" + e["event_id"] for e in late]))
    latest = _latest_group(before)
    if not latest:
        return _result("UNKNOWN", "NO_PO_STATE_HISTORY", evidence)
    evidence = _ids(evidence.split(";"), ["po_event:" + e["event_id"] for e in latest])
    states = {e["status"] for e in latest}
    if len(states) > 1:
        return _result("UNKNOWN", "AMBIGUOUS_PO_STATE", evidence)
    state = next(iter(states))
    if state == "APPROVED":
        return _result("READY", "READY", evidence)
    reason = {"CREATED": "PO_NOT_APPROVED", "CLOSED": "PO_CLOSED", "CANCELLED": "PO_CANCELLED"}.get(state)
    return _result("EXCEPTION", reason, evidence) if reason else _result("UNKNOWN", "INVALID_PO_HISTORY", evidence)


def _exclusion(invoice, start, as_of):
    receipt = _dt(invoice["received_at"])
    if receipt < start:
        return "BEFORE_COHORT_START"
    if receipt > as_of:
        return "AFTER_REPORT_CUTOFF"
    if invoice["document_type"] == "CREDIT_NOTE":
        return "CREDIT_NOTE"
    if invoice["category"] != "ROUTINE":
        return "CATEGORY_" + invoice["category"]
    if invoice["currency"] != "GBP":
        return "UNSUPPORTED_CURRENCY"
    return ""


def _owner(invoice, current_po_id, indexes):
    # A supplied unresolved request must not borrow an unrelated PO's owner.
    request_id = invoice["request_id"]
    if not request_id:
        po = indexes["purchase_orders"].get(current_po_id)
        request_id = po["request_id"] if po else ""
    request = indexes["requests"].get(request_id)
    department_id = request["department_id"] if request else ""
    department = indexes["departments"].get(department_id)
    owner_role = department["owner_role"].strip() if department else ""
    return request_id, department_id, owner_role


def _action(current, case_state, routing):
    if case_state == "UNKNOWN":
        return "AP data investigation: reconcile case event history before deciding whether the case is open or closed."
    if case_state == "CLOSED":
        return "AP case is explicitly closed in source history; payment status remains unassessed."
    reason = current["reason"]
    actions = {
        "MISSING_PO_REFERENCE": "Ask the responsible department to identify and confirm the invoice's PO reference.",
        "PO_NOT_FOUND": "Check the supplied reference against procurement records and obtain an evidenced correction.",
        "PO_NOT_APPROVED": "Ask the department buyer to review the PO approval evidence and required approval process.",
        "PO_CLOSED": "Ask the department buyer to review the closed PO and the invoice's intended order reference.",
        "PO_CANCELLED": "Ask the department buyer to review the cancelled PO and establish the correct order evidence.",
        "SUPPLIER_MISMATCH": "Reconcile supplier identity across the invoice, request and PO before confirming a reference.",
        "REQUEST_MISMATCH": "Reconcile the invoice's request identity with the PO's linked request.",
        "CURRENCY_MISMATCH": "Resolve the invoice and PO currency mismatch with the department buyer.",
        "PO_CREATED_AFTER_CUTOFF": "Investigate the reference chronology; no PO header existed at the cutoff.",
        "COMMERCIAL_DOCUMENT_COLLISION": "Investigate the shared supplier/document number without merging or paying either record automatically.",
        "READY": "AP processor to review case disposition; PO header readiness alone does not authorise payment.",
    }
    action = actions.get(reason, "AP data investigation: reconcile the missing, invalid or ambiguous evidence identified by the reason and evidence IDs.")
    if routing == "AP_TRIAGE" and current["status"] == "EXCEPTION":
        return "AP triage: establish and confirm the responsible department role first. Then " + action[0].lower() + action[1:]
    return action


def _assess_invoices(data, start, as_of, taints):
    indexes = {name: {row[key]: row for row in data[name]} for name, key in
               (("departments", "department_id"), ("suppliers", "supplier_id"),
                ("requests", "request_id"), ("purchase_orders", "po_id"))}
    po_histories, cases, commercial = {}, {}, {}
    for event in data["po_events"]:
        po_histories.setdefault(event["po_id"], []).append(event)
    for event in data["case_events"]:
        cases.setdefault(event["invoice_id"], []).append(event)
    for invoice in data["invoices"]:
        # Earlier-cohort invoices can identify a collision, but future arrivals
        # are not yet knowable and credit notes are a separate document kind.
        if invoice["document_type"] != "INVOICE" or _dt(invoice["received_at"]) > as_of:
            continue
        key = (invoice["supplier_id"], invoice["supplier_invoice_no"])
        commercial.setdefault(key, set()).add(invoice["invoice_id"])
    rows = []
    for invoice in sorted(data["invoices"], key=lambda item: item["invoice_id"]):
        row = {key: (_utc(invoice[key]) if key.endswith("_at") else invoice[key]) for key in ("invoice_id", "supplier_id", "supplier_invoice_no", "request_id", "received_at", "issued_at", "amount_minor", "currency", "category", "document_type")}
        row.update(dataset_kind="SYNTHETIC", original_po_id=invoice["po_id"])
        exclusion = _exclusion(invoice, start, as_of)
        row.update(scope="OUT_OF_SCOPE" if exclusion else "ELIGIBLE", exclusion_reason=exclusion)
        invoice_taints = taints.get("invoice_ids", {}).get(invoice["invoice_id"], [])
        if isinstance(invoice_taints, str):
            invoice_taints = [invoice_taints]
        collision = len(commercial.get((invoice["supplier_id"], invoice["supplier_invoice_no"]), ())) > 1 or any(
            "DUPLICATE_DOCUMENT" in str(t) or "COMMERCIAL_DOCUMENT_COLLISION" in str(t) for t in invoice_taints)
        invalid_case = any("DUPLICATE_DOCUMENT" not in str(t) and "COMMERCIAL_DOCUMENT_COLLISION" not in str(t) for t in invoice_taints)
        invoice_reason = "INVALID_CASE_HISTORY" if invalid_case else ("COMMERCIAL_DOCUMENT_COLLISION" if collision else "")
        reference, ambiguous, ref_evidence, state, case_reason, case_evidence = _case_snapshot(
            invoice, cases.get(invoice["invoice_id"], []), as_of, invalid_case)
        if exclusion:
            empty = {"status": "EXCLUDED", "reason": exclusion, "detail": "Outside the declared analysis cohort or supported invoice scope.", "evidence": "invoice:" + invoice["invoice_id"]}
            arrival, current = dict(empty), dict(empty)
            state, case_reason, case_evidence = "NOT_ASSESSED", exclusion, ""
            reference = invoice["po_id"]
        else:
            arrival = _assess(invoice, invoice["po_id"], _dt(invoice["received_at"]), as_of, True,
                              indexes, po_histories, taints.get("po_ids", {}), invoice_reason)
            current = _assess(invoice, reference, as_of, as_of, False, indexes, po_histories,
                              taints.get("po_ids", {}), invoice_reason, ref_evidence, ambiguous)
        owner_request, department, owner = _owner(invoice, reference, indexes)
        review = not exclusion and (state == "UNKNOWN" or (state == "OPEN" and current["status"] in ("EXCEPTION", "UNKNOWN")))
        routing = "AP_DATA_INVESTIGATION" if state == "UNKNOWN" or current["status"] == "UNKNOWN" else (owner or "AP_TRIAGE")
        row.update(current_po_id=reference, case_state=state, case_reason=case_reason,
                   case_evidence_ids=case_evidence, po_condition_cleared=int(arrival["status"] == "EXCEPTION" and current["status"] == "READY"),
                   owner_request_id=owner_request, department_id=department, owner_role=owner,
                   routing=routing, proposed_action="Outside review scope." if exclusion else _action(current, state, routing),
                   invoice_age_days=(as_of - _dt(invoice["received_at"])).total_seconds() / 86400 if _dt(invoice["received_at"]) <= as_of else None,
                   review_required=int(review))
        for prefix, assessment in (("arrival", arrival), ("current", current)):
            row.update({prefix + "_status": assessment["status"], prefix + "_reason": assessment["reason"],
                        prefix + "_reason_detail": assessment["detail"], prefix + "_evidence_ids": assessment["evidence"]})
        rows.append(row)
    return rows


def _create_model(connection, data, rows, start, as_of, taints):
    connection.execute("PRAGMA foreign_keys = ON")
    foreign_keys = {
        "requests": ["FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)", "FOREIGN KEY(department_id) REFERENCES departments(department_id)"],
        "purchase_orders": ["FOREIGN KEY(request_id) REFERENCES requests(request_id)", "FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)"],
        "po_events": ["FOREIGN KEY(po_id) REFERENCES purchase_orders(po_id)"],
        "case_events": ["FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)"],
    }
    for table, columns in SOURCE_COLUMNS.items():
        declarations = [column + (" INTEGER" if column == "amount_minor" else " TEXT") +
                        (" PRIMARY KEY" if index == 0 else " NOT NULL") for index, column in enumerate(columns)]
        connection.execute("CREATE TABLE " + table + " (" + ",".join(declarations + foreign_keys.get(table, [])) + ")")
        values = []
        for source in sorted(data[table], key=lambda record: record[columns[0]]):
            values.append(tuple(_utc(source[column]) if column.endswith("_at") else source[column] for column in columns))
        connection.executemany("INSERT INTO " + table + " VALUES (" + ",".join("?" for _ in columns) + ")", values)
    declarations = [field + (" INTEGER" if field in ("amount_minor", "review_required", "po_condition_cleared") else
                              " REAL" if field == "invoice_age_days" else " TEXT") +
                    (" PRIMARY KEY" if field == "invoice_id" else "") for field in TRACE_FIELDS]
    connection.execute("CREATE TABLE invoice_assessments (" + ",".join(declarations) + ", FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id))")
    connection.executemany("INSERT INTO invoice_assessments VALUES (" + ",".join("?" for _ in TRACE_FIELDS) + ")",
                           [tuple(row[field] for field in TRACE_FIELDS) for row in rows])
    connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    metadata = {"schema_version": "1", "dataset_kind": "SYNTHETIC", "cohort_start": start, "as_of": as_of,
                "taints": json.dumps(taints, sort_keys=True), "scope": "PO header evidence only; payment and remaining PO capacity are not assessed."}
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", sorted(metadata.items()))
    connection.execute("CREATE VIEW interactions AS SELECT event_id, invoice_id, event_type, effective_at, recorded_at, po_id, actor_role, note, 'SYNTHETIC' AS dataset_kind FROM case_events WHERE event_type IN ('FOLLOW_UP', 'REFERENCE_CONFIRMED')")
    connection.execute("CREATE INDEX po_events_point_in_time ON po_events(po_id, effective_at, recorded_at)")
    connection.execute("CREATE INDEX case_events_point_in_time ON case_events(invoice_id, effective_at, recorded_at)")
    connection.execute("CREATE INDEX assessment_scope ON invoice_assessments(scope, case_state, current_status)")
    connection.commit()


def _percentage(numerator, denominator):
    return round(100.0 * numerator / denominator, 2) if denominator else None


def _ratio(numerator, denominator, definition, unit="percent"):
    return {"numerator": numerator, "denominator": denominator,
            "percentage": _percentage(numerator, denominator), "unit": unit,
            "definition": definition, "zero_denominator_explanation": None if denominator else "No records meet this metric's denominator; a percentage is undefined."}


def _gbp(minor):
    whole, pennies = divmod(abs(minor), 100)
    return "{}£{:,}.{:02d}".format("-" if minor < 0 else "", whole, pennies)


def _metrics(connection, data, start, as_of):
    joined = " FROM invoice_assessments a JOIN invoices i ON i.invoice_id = a.invoice_id "
    eligible = " a.scope = 'ELIGIBLE' "
    open_exception = eligible + " AND a.case_state = 'OPEN' AND a.current_status = 'EXCEPTION' "
    eligible_count, assessable, numerator, unknown = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(a.arrival_status IN ('READY','EXCEPTION')),0), "
        "COALESCE(SUM(a.arrival_status = 'EXCEPTION'),0), COALESCE(SUM(a.arrival_status = 'UNKNOWN'),0)" + joined + "WHERE" + eligible).fetchone()
    reasons = dict(connection.execute("SELECT a.current_reason, COUNT(*)" + joined + "WHERE" + open_exception + "GROUP BY a.current_reason ORDER BY a.current_reason").fetchall())
    count, gross = connection.execute("SELECT COUNT(*), COALESCE(SUM(i.amount_minor),0)" + joined + "WHERE" + open_exception).fetchone()
    median = connection.execute(
        "WITH ranked AS (SELECT a.invoice_age_days AS age, ROW_NUMBER() OVER (ORDER BY a.invoice_age_days, a.invoice_id) AS rn, "
        "COUNT(*) OVER () AS n" + joined + "WHERE" + open_exception + ") "
        "SELECT AVG(age) FROM ranked WHERE rn IN ((n + 1) / 2, (n + 2) / 2)").fetchone()[0]
    owners = connection.execute(
        "SELECT COALESCE(SUM(CASE WHEN TRIM(COALESCE(d.owner_role,'')) <> '' THEN 1 ELSE 0 END),0)" + joined +
        " LEFT JOIN requests r ON r.request_id = a.owner_request_id LEFT JOIN departments d ON d.department_id = r.department_id WHERE" + open_exception).fetchone()[0]
    primary = _ratio(numerator, assessable, "Arrival confirmed PO-evidence exception invoices / arrival assessable eligible canonical invoice records. Assessable means READY + EXCEPTION.")
    primary.update(metric_id="arrival_confirmed_exception_rate", unknown_count=unknown, eligible_count=eligible_count)
    support = {
        "open_exceptions_by_reason": {"metric_id": "current_open_confirmed_exceptions", "total": count, "counts": reasons,
            "definition": "Eligible invoice records with an OPEN AP case and current EXCEPTION evidence, grouped by one exclusive reason per invoice.", "unit": "invoice records"},
        "open_exceptions_gross_value": {"metric_id": "gross_open_exception_value", "amount_minor": gross, "currency": "GBP", "formatted_gbp": _gbp(gross),
            "invoice_count": count, "definition": "Sum of gross invoice GBP pence for current OPEN confirmed exceptions; this is neither unpaid value nor loss.", "unit": "GBP pence"},
        "open_exceptions_median_invoice_age": {"metric_id": "median_open_exception_invoice_age", "days": median,
            "invoice_count": count, "definition": "Median of (report cutoff minus invoice received_at), in days, for current OPEN confirmed exceptions. This is invoice age, not elapsed exception duration.",
            "unit": "days", "zero_denominator_explanation": None if count else "No current OPEN confirmed exception invoices; a median is undefined."},
        "open_exceptions_owner_coverage": dict(_ratio(owners, count, "Current OPEN confirmed exception invoice records linked through a known request/PO department to a nonempty owner_role / all current OPEN confirmed exceptions."),
            metric_id="open_exception_owner_coverage", ap_triage_count=count - owners),
        "arrival_assessment_coverage": dict(_ratio(assessable, eligible_count, "Arrival assessable invoice records (READY + EXCEPTION) / all eligible canonical invoice records."),
            metric_id="arrival_assessment_coverage", unknown_count=unknown),
    }
    quality = dict(data.get("_quality_controls", {}))
    quality.update(invoice_canonical_rows=len(data["invoices"]), eligible_canonical_invoice_records=eligible_count,
                   excluded_canonical_invoice_records=len(data["invoices"]) - eligible_count,
                   exclusions_by_reason=dict(connection.execute("SELECT exclusion_reason, COUNT(*) FROM invoice_assessments WHERE scope = 'OUT_OF_SCOPE' GROUP BY exclusion_reason ORDER BY exclusion_reason")),
                   arrival_unknown_by_reason=dict(connection.execute("SELECT arrival_reason, COUNT(*) FROM invoice_assessments WHERE scope = 'ELIGIBLE' AND arrival_status = 'UNKNOWN' GROUP BY arrival_reason ORDER BY arrival_reason")),
                   current_unknown_by_reason=dict(connection.execute("SELECT current_reason, COUNT(*) FROM invoice_assessments WHERE scope = 'ELIGIBLE' AND current_status = 'UNKNOWN' GROUP BY current_reason ORDER BY current_reason")),
                   unknown_case_state_count=connection.execute("SELECT COUNT(*) FROM invoice_assessments WHERE scope = 'ELIGIBLE' AND case_state = 'UNKNOWN'").fetchone()[0],
                   review_queue_count=connection.execute("SELECT COUNT(*) FROM invoice_assessments WHERE review_required = 1").fetchone()[0])
    reconciliation_keys = ("invoice_raw_rows", "invoice_canonical_rows", "invoice_duplicate_rows_removed", "invoice_quarantined_rows")
    quality["invoice_row_reconciliation"] = ({"raw": quality[reconciliation_keys[0]], "canonical": quality[reconciliation_keys[1]],
        "duplicate_rows_removed": quality[reconciliation_keys[2]], "quarantined": quality[reconciliation_keys[3]],
        "balanced": quality[reconciliation_keys[0]] == sum(quality[key] for key in reconciliation_keys[1:])}
        if all(key in quality for key in reconciliation_keys) else {"balanced": None, "explanation": "Raw row reconciliation counts were not supplied by the retrieval/validation layer."})
    return {"dataset_kind": "SYNTHETIC", "cohort": {"start": start, "as_of": as_of, "boundary": "Both endpoints inclusive; received_at determines the invoice cohort.",
            "policy": "ROUTINE, INVOICE, positive GBP canonical records only."}, "primary": primary, "supporting": support, "quality_controls": quality,
            "evidence_notes": [
                "Operational rows and interactions are synthetic; no real organisation's operational records, interviews or intervention outcomes are represented.",
                "Arrival uses the original immutable invoice PO reference; current uses the latest eligible REFERENCE_CONFIRMED event.",
                "Evidence must be both effective and recorded on or before the report cutoff. Pre-receipt state recorded after receipt makes arrival UNKNOWN; exact-receipt transitions have unknown ordering.",
                "Latest effective timestamp wins. Conflicting states or references tied at that timestamp are UNKNOWN. Future events cannot change assessments.",
                "Commercial-document collisions compare INVOICE records received on or before cutoff, including invoices before cohort start. Credit notes are a separate document kind and do not create invoice collisions.",
                "Exclusive reason precedence: invoice history taint, commercial collision, ambiguous current reference, missing/nonexistent reference, PO history taint, unresolved identities, supplier mismatch, request mismatch, currency mismatch, creation chronology, receipt-time uncertainty, latest PO state.",
                "A blank optional invoice request may resolve through the PO; a nonempty unknown request is UNKNOWN. A supplied unresolved request never borrows another request's owner.",
                "READY means PO header evidence ready only. Remaining PO value, quantities, receipts, disputes, tax, invoice approval and payment are not tested; multiple invoices may share one PO.",
                "PO condition cleared means arrival EXCEPTION and current READY. It is separate from formal AP case closure and from payment. FOLLOW_UP does not prove a change.",
                "Unknown evidence is not counted as a confirmed exception or silently excluded from coverage. Quarantined rows never enter canonical invoice denominators.",
                "Declared registry/history completeness and input hashes are a bounded snapshot contract, not evidence that a real source system is complete.",
                "The current review queue and supporting exception measures cover only the selected arrival cohort, not the whole AP backlog.",
                "The arrival exception rate is a diagnostic baseline for examining upstream failures, not a success measure for later queue handling. No intervention benefit is measured.",
                "All next actions are unexecuted recommendations. No messages are sent.",
            ]}


def _write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _render_report(metrics, rows, data):
    esc = lambda value: html.escape(str(value), quote=True)
    ratio = lambda value: ("Undefined (zero denominator)" if value["percentage"] is None else "{:.2f}%".format(value["percentage"])) + " ({} / {})".format(value["numerator"], value["denominator"])
    primary, support, quality = metrics["primary"], metrics["supporting"], metrics["quality_controls"]
    reasons = support["open_exceptions_by_reason"]
    reason_text = "; ".join("{}: {}".format(key, value) for key, value in reasons["counts"].items()) or "No current OPEN confirmed exceptions."
    median = support["open_exceptions_median_invoice_age"]
    median_text = "Undefined (no qualifying cases)" if median["days"] is None else "{:.2f} days".format(median["days"])
    supporting_rows = [
        ("1. Current OPEN confirmed exceptions, by reason", "{} invoice records. {}".format(reasons["total"], reason_text), reasons["definition"]),
        ("2. Gross GBP value of those exceptions", support["open_exceptions_gross_value"]["formatted_gbp"] + " ({} pence)".format(support["open_exceptions_gross_value"]["amount_minor"]), support["open_exceptions_gross_value"]["definition"]),
        ("3. Median invoice age of those cases", median_text, median["definition"]),
        ("4. Owner coverage for those cases", ratio(support["open_exceptions_owner_coverage"]) + "; {} to AP triage".format(support["open_exceptions_owner_coverage"]["ap_triage_count"]), support["open_exceptions_owner_coverage"]["definition"]),
        ("5. Arrival assessment coverage", ratio(support["arrival_assessment_coverage"]) + "; {} UNKNOWN".format(primary["unknown_count"]), support["arrival_assessment_coverage"]["definition"]),
    ]
    support_html = "".join("<tr><th scope='row'>{}</th><td>{}</td><td>{}</td></tr>".format(*(esc(item) for item in row)) for row in supporting_rows)
    queue = [row for row in rows if row["review_required"]]
    display_label = lambda value: " ".join(word if word in {"AP", "PO"} else word.title() for word in str(value).split("_"))
    queue_html = "".join("<tr><th scope='row'>{}<details class='evidence'><summary>Evidence IDs</summary><ul>{}</ul></details></th><td><span class='status'>{}</span><br><span class='secondary'>{}</span></td><td><span class='status'>{}</span><br><span class='secondary'>{}</span></td><td>{}</td><td>{}</td></tr>".format(
        esc(row["invoice_id"]), "".join("<li>{}</li>".format(esc(evidence_id)) for evidence_id in _ids(row["current_evidence_ids"].split(";"), row["case_evidence_ids"].split(";")).split(";") if evidence_id),
        esc(row["current_status"]), esc(row["current_reason_detail"]), esc(row["case_state"]), esc(display_label(row["case_reason"])),
        esc(display_label(row["routing"])), esc(row["proposed_action"])) for row in queue)
    if not queue_html:
        queue_html = "<tr><td colspan='5'>No current review items under the declared rules.</td></tr>"
    quality_rows = []
    for key in ("invoice_raw_rows", "invoice_canonical_rows", "invoice_duplicate_rows_removed", "invoice_quarantined_rows", "eligible_canonical_invoice_records", "excluded_canonical_invoice_records", "case_raw_rows", "case_canonical_rows", "case_quarantined_rows", "po_event_raw_rows", "po_event_canonical_rows", "po_event_quarantined_rows", "normalization_count", "issue_count", "unknown_case_state_count", "review_queue_count"):
        quality_rows.append("<tr><th scope='row'>{}</th><td>{}</td></tr>".format(esc(key.replace("_", " ")), esc(quality.get(key, "Not supplied by retrieval layer"))))
    breakdown = "".join("<h3>{}</h3><p>{}</p>".format(esc(title), esc("; ".join("{}: {}".format(k, v) for k, v in quality[key].items()) or "None.")) for title, key in
                        (("Excluded canonical records", "exclusions_by_reason"), ("Arrival UNKNOWN evidence", "arrival_unknown_by_reason"), ("Current UNKNOWN evidence", "current_unknown_by_reason")))
    reconciliation = quality["invoice_row_reconciliation"]
    recon_text = ("Raw {} = canonical {} + duplicate rows removed {} + quarantined {}. Balanced: {}.".format(reconciliation["raw"], reconciliation["canonical"], reconciliation["duplicate_rows_removed"], reconciliation["quarantined"], reconciliation["balanced"])) if reconciliation["balanced"] is not None else reconciliation["explanation"]
    manifest = data.get("_manifest", {})
    manifest_text = "".join("<dt>{}</dt><dd>{}</dd>".format(esc(key.replace("_", " ")), esc(manifest[key])) for key in ("organisation", "seed", "history_start", "exported_at") if key in manifest)
    notes = "".join("<li>{}</li>".format(esc(note)) for note in metrics["evidence_notes"])
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SYNTHETIC · Supplier invoice PO evidence review</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#faf9f6;color:#202624;font:16px/1.55 Georgia,'Times New Roman',serif}main{max-width:1180px;margin:0 auto;padding:40px 32px 64px}h1{font-size:30px;line-height:1.2;font-weight:500;margin:10px 0 16px}h2{font-size:22px;margin:34px 0 12px;border-bottom:1px solid #b7bdb7;padding-bottom:7px}h3{font-size:17px;margin:22px 0 5px}p{max-width:95ch}.label{font:700 13px/1.5 system-ui,sans-serif;letter-spacing:.08em;color:#614119}.lead{font-size:18px}.secondary{color:#535e59;font-size:13px}table{width:100%;border-collapse:collapse;margin:14px 0;font:13px/1.5 system-ui,sans-serif}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #d6dad4;padding:9px 10px;overflow-wrap:anywhere}thead th{background:#ecefe9;font-weight:650}tbody th{font-weight:600}a{color:#234d47;text-underline-offset:3px}.result{font-size:24px;font-variant-numeric:tabular-nums}.quality{max-width:750px}dl{display:grid;grid-template-columns:150px 1fr;font:14px/1.5 system-ui,sans-serif;gap:6px 14px}dt{font-weight:600}dd{margin:0;overflow-wrap:anywhere}.evidence{font-size:11px}.table-scroll{overflow-x:auto}li{margin:8px 0}footer{margin-top:36px;border-top:1px solid #b7bdb7;padding-top:14px;font-size:13px}@media(max-width:650px){main{padding:24px 16px}h1{font-size:26px}dl{grid-template-columns:1fr;gap:3px}dd{margin-bottom:10px}table{min-width:640px}.quality{min-width:0}}@media print{body{background:white}main{max-width:none;padding:0}h2{break-after:avoid}tr{break-inside:avoid}.table-scroll{overflow:visible}a{color:inherit}}
.queue{table-layout:fixed;min-width:1000px}.queue col:nth-child(1){width:19%}.queue col:nth-child(2){width:24%}.queue col:nth-child(3){width:13%}.queue col:nth-child(4){width:15%}.queue col:nth-child(5){width:29%}.queue th,.queue td{overflow-wrap:normal}.status{white-space:nowrap}.queue .evidence{margin-top:4px;font-size:12px;font-weight:400}.evidence summary{cursor:pointer;color:#234d47;padding:6px 0}.evidence ul{list-style:none;padding:0;margin:4px 0}.evidence li{overflow-wrap:anywhere;margin:4px 0}.evidence summary:focus-visible,.table-scroll:focus-visible{outline:2px solid #234d47;outline-offset:2px}@media(pointer:coarse){.evidence summary{min-height:40px;padding:10px 0}}@media print{.queue{min-width:0}}
</style></head><body><main>
<div class="label">SYNTHETIC DATA · DESK-RESEARCH PROTOTYPE</div>
<h1>Supplier invoice PO evidence review</h1>
<p class="lead">An invoice-level review of purchase-order reference, identity, currency and approval evidence at receipt and at a declared report cutoff.</p>
<p>Fictional operational records illustrate the workflow. BHT public reports motivate the problem; BHT is not a client and its operational records are not used. No interviews, deployment, time savings or intervention benefit have occurred.</p>
<dl><dt>Cohort start</dt><dd>COHORT_START</dd><dt>Report cutoff</dt><dd>REPORT_CUTOFF</dd><dt>Boundary</dt><dd>Received-at timestamps; both endpoints inclusive. Times are UTC.</dd>MANIFEST</dl>
<p><strong>Interpretation:</strong> READY means PO header evidence ready under these rules. Remaining order value, quantities, receipts, disputes, tax, invoice approval and payment are outside scope. A case closure does not mean paid; gross invoice value is not unpaid value or a loss.</p>
<h2>Primary measure</h2><p class="result">PRIMARY_RESULT</p><p>PRIMARY_DEFINITION</p><p>There are UNKNOWN_COUNT eligible arrival UNKNOWN records. They remain outside the assessable denominator and inside the coverage denominator. Coverage is COVERAGE_RESULT. Zero denominators produce undefined values, represented as null in JSON.</p>
<h2>Five supporting measures</h2><div class="table-scroll"><table><thead><tr><th scope="col">Measure</th><th scope="col">Result</th><th scope="col">Definition and limits</th></tr></thead><tbody>SUPPORT_ROWS</tbody></table></div>
<h2>Inputs, quality and coverage</h2><p>Inputs are procurement.sqlite (departments, suppliers, requests, purchase_orders and immutable po_events), ap_invoices.csv and ap_case_events.csv, retrieved separately through SQL and CSV parsing. The export manifest declares snapshot completeness and hashes. Raw snapshots and validation diagnostics belong to the pipeline run.</p><p>RECONCILIATION</p><div class="table-scroll"><table class="quality"><thead><tr><th scope="col">Quality control (not an outcome measure)</th><th scope="col">Count</th></tr></thead><tbody>QUALITY_ROWS</tbody></table></div>BREAKDOWN
<h2>Method and evidence boundaries</h2><ol>NOTES</ol>
<p>Histories are reduced to one assessment per invoice in model.sqlite before metric SQL joins and aggregation. Source entities, events and a synthetic interaction view are retained. invoice_trace.csv preserves original and current classifications, formal AP case state, a separate PO-condition-cleared flag, and the evidence IDs supporting each determination.</p>
<h2>Current cohort review · synthetic recommendations</h2><p>This is the selected arrival cohort, not the whole AP backlog. OPEN AP cases with current EXCEPTION or UNKNOWN evidence require review. UNKNOWN case state also requires data investigation. A formally CLOSED case is not an open exception. Recommendations below have not been executed.</p><div class="table-scroll" tabindex="0" role="region" aria-label="Current cohort review"><table class="queue"><colgroup><col><col><col><col><col></colgroup><thead><tr><th scope="col">Invoice</th><th scope="col">Current PO evidence</th><th scope="col">AP case</th><th scope="col">Owner or routing</th><th scope="col">Proposed next action</th></tr></thead><tbody>QUEUE_ROWS</tbody></table></div>
<footer>Reproducible artifacts: <a href="invoice_trace.csv">invoice trace CSV</a> · <a href="review_queue.csv">review queue CSV</a> · <a href="metrics.json">metric definitions and values (JSON)</a> · <a href="model.sqlite">modeled SQLite database</a>. All operational rows and interactions are SYNTHETIC.</footer>
</main></body></html>
""".replace("COHORT_START", esc(metrics["cohort"]["start"])).replace("REPORT_CUTOFF", esc(metrics["cohort"]["as_of"])).replace("MANIFEST", manifest_text).replace("PRIMARY_RESULT", esc(ratio(primary))).replace("PRIMARY_DEFINITION", esc(primary["definition"])).replace("UNKNOWN_COUNT", str(primary["unknown_count"])).replace("COVERAGE_RESULT", esc(ratio(support["arrival_assessment_coverage"]))).replace("SUPPORT_ROWS", support_html).replace("RECONCILIATION", esc(recon_text)).replace("QUALITY_ROWS", "".join(quality_rows)).replace("BREAKDOWN", breakdown).replace("NOTES", notes).replace("QUEUE_ROWS", queue_html)


def build_outputs(data, start, as_of, output_dir, taints=None):
    """Write deterministic synthetic model, trace, queue, six metrics and report.

    Optional ``data['_quality_controls']`` and ``data['_manifest']`` carry the
    retrieval layer's audit counts and snapshot metadata for faithful reporting.
    Neither is used to classify invoices or calculate the business measures.
    """
    start, as_of = _utc(start), _utc(as_of)
    if _dt(start) > _dt(as_of):
        raise ValueError("Cohort start must be on or before report cutoff")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    taints = taints or {"po_ids": {}, "invoice_ids": {}}
    rows = _assess_invoices(data, _dt(start), _dt(as_of), taints)
    database = output_dir / "model.sqlite"
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(str(database))
    try:
        _create_model(connection, data, rows, start, as_of, taints)
        metrics = _metrics(connection, data, start, as_of)
    finally:
        connection.close()
    _write_csv(output_dir / "invoice_trace.csv", rows, TRACE_FIELDS)
    _write_csv(output_dir / "review_queue.csv", [row for row in rows if row["review_required"]], QUEUE_FIELDS)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.html").write_text(_render_report(metrics, rows, data), encoding="utf-8")
    return metrics
