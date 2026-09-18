"""Explicit, conservative cleaning of declared source exports.

Malformed evidence is never silently treated as an absent approval or a good match.
"""

import collections
import datetime as dt
import json
import re
from dataclasses import dataclass


TABLE_FIELDS = {
    "departments": ("department_id", "name", "owner_role"),
    "suppliers": ("supplier_id", "name"),
    "requests": ("request_id", "supplier_id", "department_id", "requested_at", "category"),
    "purchase_orders": ("po_id", "request_id", "supplier_id", "currency", "created_at"),
    "po_events": ("event_id", "po_id", "status", "effective_at", "recorded_at"),
    "invoices": ("invoice_id", "supplier_id", "supplier_invoice_no", "request_id", "po_id",
                 "issued_at", "received_at", "amount_minor", "currency", "category", "document_type"),
    "case_events": ("event_id", "invoice_id", "event_type", "effective_at", "recorded_at",
                    "po_id", "actor_role", "note"),
}
KEYS = {"departments": "department_id", "suppliers": "supplier_id", "requests": "request_id",
        "purchase_orders": "po_id", "po_events": "event_id", "invoices": "invoice_id",
        "case_events": "event_id"}
CATEGORIES = {"ROUTINE", "EMERGENCY", "CAPITAL", "PO_EXEMPT"}
PO_STATES = {"CREATED", "APPROVED", "CLOSED", "CANCELLED"}
CASE_TYPES = {"FOLLOW_UP", "REFERENCE_CONFIRMED", "CASE_CLOSED", "CASE_REOPENED"}


class ValidationError(ValueError):
    """An unreliable source snapshot must not produce a successful report."""


def timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing timestamp")
    raw = value.strip()
    match = re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(Z|([+-])([0-9]{2}):([0-9]{2}))", raw)
    if not match:
        raise ValueError("expected ISO timestamp with seconds, timezone and at most six fractional digits")
    if match.group(1) != "Z" and (int(match.group(3)) > 23 or int(match.group(4)) > 59):
        raise ValueError("invalid numeric timezone offset")
    parsed = dt.datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp has no timezone; guessing is not a safe fix")
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identifier(value, optional=False):
    value = "" if value is None else str(value).strip().upper()
    if not value and optional:
        return value
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.:/-]*", value):
        raise ValueError("missing or invalid identifier")
    return value


def _word(value, optional=False):
    value = "" if value is None else str(value).strip()
    if not value and not optional:
        raise ValueError("missing text")
    if any(ord(c) < 32 for c in value):
        raise ValueError("control character in text")
    return value


def profile(rows, fields):
    cols = {}
    for field in fields:
        values = [r.get(field) for r in rows]
        cols[field] = {
            "missing": sum(v is None or str(v).strip() == "" for v in values),
            "distinct": len({str(v) for v in values if v is not None}),
        }
    return {"rows": len(rows), "columns": cols}


@dataclass
class Validated:
    data: dict
    taints: dict
    profile: dict
    issues: list
    fixes: list


def validate(raw, as_of=None):
    issues, fixes = [], []
    data = {}
    taints = {"po_ids": {}, "invoice_ids": {}}
    counters = collections.Counter()
    invalid_keys = collections.defaultdict(set)
    cutoff = timestamp(as_of) if as_of else None

    def could_affect_cutoff(row):
        if cutoff is None:
            return True
        for field in ("effective_at", "recorded_at"):
            try:
                if timestamp(row.get(field)) > cutoff:
                    return False
            except (ValueError, TypeError):
                pass
        return True

    def issue(source, row, rule, detail, severity="QUARANTINE"):
        if severity == "QUARANTINE":
            invalid_keys[source].add(str(row.get(KEYS[source], "")).strip().upper())
        issues.append({"source": source, "source_row": row.get("_source_row", ""),
                       "record_id": str(row.get(KEYS[source], "")), "severity": severity,
                       "rule": rule, "detail": detail})

    def taint(kind, record_id, reason):
        if record_id:
            taints[kind].setdefault(record_id, [])
            if reason not in taints[kind][record_id]:
                taints[kind][record_id].append(reason)

    def clean(source, row, optional=()):
        if row.get("_row_error"):
            raise ValueError(row["_row_error"])
        output = {"_source_row": row.get("_source_row", "")}
        for field in TABLE_FIELDS[source]:
            old = row.get(field)
            if field.endswith("_at"):
                value = timestamp(old)
            elif field.endswith("_id"):
                value = _identifier(old, field in optional)
            elif field == "amount_minor":
                if not re.fullmatch(r"[+-]?[0-9]+", str(old).strip()):
                    raise ValueError("amount_minor must be integer minor units, not a decimal guess")
                value = int(str(old).strip())
                if abs(value) > 10**12:
                    raise ValueError("amount outside declared demo range")
            else:
                value = _word(old, field in optional)
                if field in {"currency", "category", "document_type", "status", "event_type", "actor_role", "supplier_invoice_no"}:
                    value = value.upper()
            if field == "currency" and not re.fullmatch(r"[A-Z]{3}", value):
                raise ValueError("currency must be a three-letter code")
            output[field] = value
            if str(old) != str(value):
                fixes.append({"source": source, "source_row": row.get("_source_row", ""),
                              "record_id": str(row.get(KEYS[source], "")), "field": field,
                              "before": "" if old is None else str(old), "after": str(value),
                              "rule": "SAFE_CANONICAL_FORMAT"})
        return output

    def core(source, optional=()):
        result, seen = [], set()
        for row in raw[source]:
            try:
                r = clean(source, row, optional)
            except (ValueError, TypeError) as exc:
                raise ValidationError("{} row {}: {}".format(source, row.get("_source_row"), exc)) from exc
            key = r[KEYS[source]]
            if key in seen:
                raise ValidationError("duplicate core identity {} in {}".format(key, source))
            seen.add(key)
            result.append(r)
        data[source] = result
        return {r[KEYS[source]]: r for r in result}

    departments = core("departments", ("owner_role",))
    suppliers = core("suppliers")
    requests = core("requests")
    for r in requests.values():
        if r["supplier_id"] not in suppliers or r["department_id"] not in departments:
            raise ValidationError("request {} has an unknown supplier/department".format(r["request_id"]))
        if r["category"] not in CATEGORIES:
            raise ValidationError("unknown request category for " + r["request_id"])
    orders = core("purchase_orders")
    for r in orders.values():
        if r["supplier_id"] not in suppliers or r["request_id"] not in requests:
            raise ValidationError("PO {} has an unknown supplier/request".format(r["po_id"]))
        if requests[r["request_id"]]["supplier_id"] != r["supplier_id"]:
            raise ValidationError("PO/request supplier identity conflict for " + r["po_id"])

    def deduplicate(source, rows, taint_kind=None, parent=None):
        groups = collections.defaultdict(list)
        for r in rows:
            groups[r[KEYS[source]]].append(r)
        accepted = []
        for key in sorted(groups):
            group = groups[key]
            payloads = {json.dumps({k: r[k] for k in TABLE_FIELDS[source]}, sort_keys=True) for r in group}
            if len(payloads) > 1 or key in invalid_keys[source]:
                for r in group:
                    issue(source, r, "CONFLICTING_DUPLICATE_ID", "all competing source rows quarantined")
                    counters[source + "_quarantined"] += 1
                    if taint_kind and could_affect_cutoff(r):
                        taint(taint_kind, r[parent], "CONFLICTING_EVENT_ID")
            else:
                accepted.append(group[0])
                for r in group[1:]:
                    issue(source, r, "EXACT_DUPLICATE", "identical after logged safe normalization", "DUPLICATE_REMOVED")
                    counters[source + "_duplicate"] += 1
        return accepted

    events = []
    for row in raw["po_events"]:
        po_id = str(row.get("po_id", "")).strip().upper()
        if po_id not in orders:
            raise ValidationError("PO history has unknown parent " + po_id)
        try:
            r = clean("po_events", row)
            if r["status"] not in PO_STATES:
                raise ValueError("unknown PO state")
            if r["recorded_at"] < r["effective_at"]:
                raise ValueError("recorded time precedes event time")
            if r["effective_at"] < orders[po_id]["created_at"]:
                raise ValueError("PO state predates PO creation")
            events.append(r)
        except (ValueError, TypeError) as exc:
            issue("po_events", row, "INVALID_PO_HISTORY", str(exc))
            counters["po_events_quarantined"] += 1
            if could_affect_cutoff(row):
                taint("po_ids", po_id, "INVALID_PO_HISTORY")
    data["po_events"] = deduplicate("po_events", events, "po_ids", "po_id")

    invoices = []
    for row in raw["invoices"]:
        try:
            r = clean("invoices", row, ("po_id", "request_id"))
            if r["document_type"] not in {"INVOICE", "CREDIT_NOTE"}:
                raise ValueError("unsupported document type")
            if r["category"] not in CATEGORIES:
                raise ValueError("unknown purchase category")
            if r["document_type"] == "INVOICE" and r["amount_minor"] <= 0:
                raise ValueError("INVOICE amount must be positive; do not infer a credit note")
            if r["received_at"] < r["issued_at"]:
                raise ValueError("receipt precedes invoice issue time")
            invoices.append(r)
        except (ValueError, TypeError) as exc:
            issue("invoices", row, "INVALID_INVOICE_ROW", str(exc))
            counters["invoices_quarantined"] += 1
    data["invoices"] = deduplicate("invoices", invoices)
    by_invoice = {r["invoice_id"]: r for r in data["invoices"]}
    commercial = collections.defaultdict(list)
    for r in data["invoices"]:
        if r["document_type"] == "INVOICE" and (cutoff is None or r["received_at"] <= cutoff):
            commercial[(r["supplier_id"], r["supplier_invoice_no"])].append(r)
    for group in commercial.values():
        if len(group) > 1:
            for r in group:
                taint("invoice_ids", r["invoice_id"], "POSSIBLE_DUPLICATE_DOCUMENT")
                issue("invoices", r, "POSSIBLE_DUPLICATE_DOCUMENT", "different source IDs share a supplier/document reference; retained as UNKNOWN", "UNKNOWN")

    case_events = []
    for row in raw["case_events"]:
        invoice_id = str(row.get("invoice_id", "")).strip().upper()
        try:
            r = clean("case_events", row, ("po_id", "note"))
            if invoice_id not in by_invoice:
                raise ValueError("event has no assessable canonical invoice parent")
            if r["event_type"] not in CASE_TYPES:
                raise ValueError("unknown AP event type")
            if r["actor_role"] not in {"AP_PROCESSOR", "DEPARTMENT_BUYER"}:
                raise ValueError("unknown actor role")
            if r["event_type"] == "REFERENCE_CONFIRMED" and not r["po_id"]:
                raise ValueError("a reference confirmation requires a PO reference")
            if r["recorded_at"] < r["effective_at"] or r["effective_at"] < by_invoice[invoice_id]["received_at"]:
                raise ValueError("inconsistent AP event/recording/receipt chronology")
            case_events.append(r)
        except (ValueError, TypeError) as exc:
            issue("case_events", row, "INVALID_CASE_HISTORY", str(exc))
            counters["case_events_quarantined"] += 1
            if invoice_id in by_invoice and could_affect_cutoff(row):
                taint("invoice_ids", invoice_id, "INVALID_CASE_HISTORY")
    data["case_events"] = deduplicate("case_events", case_events, "invoice_ids", "invoice_id")

    control = {"normalization_count": len(fixes), "issue_count": len(issues)}
    for source, prefix in (("invoices", "invoice"), ("case_events", "case"), ("po_events", "po_event")):
        n_raw, n_clean = len(raw[source]), len(data[source])
        n_dup, n_bad = counters[source + "_duplicate"], counters[source + "_quarantined"]
        if n_raw != n_clean + n_dup + n_bad:
            raise ValidationError("record reconciliation failed for " + source)
        control.update({prefix + "_raw_rows": n_raw, prefix + "_canonical_rows": n_clean,
                        prefix + "_duplicate_rows_removed": n_dup, prefix + "_quarantined_rows": n_bad})
    data["_quality_controls"] = control
    profiles = {
        "before": {name: profile(raw[name], fields) for name, fields in TABLE_FIELDS.items()},
        "after": {name: profile(data[name], fields) for name, fields in TABLE_FIELDS.items()},
        "reconciliation": control,
        "issue_counts": dict(sorted(collections.Counter(i["rule"] for i in issues).items())),
        "uncertain_entities": taints,
        "policy": "Malformed rows are quarantined. Lost decision history taints affected entities. No missing values are guessed.",
    }
    return Validated(data, taints, profiles, issues, fixes)
