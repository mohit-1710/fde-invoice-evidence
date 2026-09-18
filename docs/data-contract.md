# Synthetic source-data contract

Version 1. This specifies the supplied fixture, not an observed enterprise schema. The [methods](methods.md) define classification, timing, joins, metrics and reliability.

## Honest scope

Desk-researched supplier-invoice PO evidence review. BHT public reports motivate the problem but BHT is not our client and its records are not used. All operational rows are explicitly synthetic, with fictional departments/suppliers and deliberately chosen scenarios, not estimated BHT distributions. No interviews, deployment, time savings or intervention benefit have occurred.

The prototype tests PO reference, existence, supplier/request identity, currency and approval evidence at invoice receipt and at a report cutoff. It does NOT test remaining order value, quantities, receipts, disputes, tax, invoice approval or payment. READY means only PO header evidence ready under these declared rules. It does not mean a usable fully matched PO, payment-ready invoice or permission to pay. Multiple invoices may reference one PO; capacity is deliberately out of scope.

## Sources and columns

Two genuinely retrieved source types: procurement SQLite read with SQL and AP CSV exports read with csv.DictReader. Generation is a separate explicit command, never silently run during pipeline execution. Default seed 20260918. Default cohort start 2026-08-01T00:00:00Z; default cutoff 2026-08-31T18:00:00Z. History starts 2026-07-01T00:00:00Z; source export time 2026-09-01T12:00:00Z. All timestamps must include a timezone and normalize to UTC. All supported money is integer GBP pence.

`data/sources/procurement.sqlite` tables:

- departments(department_id TEXT, name TEXT, owner_role TEXT). Empty owner_role means unresolved owner; do not invent one.
- suppliers(supplier_id TEXT, name TEXT).
- requests(request_id TEXT, supplier_id TEXT, department_id TEXT, requested_at TEXT, category TEXT).
- purchase_orders(po_id TEXT, request_id TEXT, supplier_id TEXT, currency TEXT, created_at TEXT).
- po_events(event_id TEXT, po_id TEXT, status TEXT, effective_at TEXT, recorded_at TEXT). Status CREATED, APPROVED, CLOSED, CANCELLED. State events are immutable, including backdated/late-recorded examples.

`data/sources/ap_invoices.csv` columns:

invoice_id,supplier_id,supplier_invoice_no,request_id,po_id,issued_at,received_at,amount_minor,currency,category,document_type

`request_id` and `po_id` may be empty. invoice_id is the source record key; supplier_invoice_no is the commercial document reference. category ROUTINE is in scope; EMERGENCY, CAPITAL, PO_EXEMPT are explicit exclusions. Unknown category is invalid. document_type INVOICE or CREDIT_NOTE; credit notes are excluded. Only positive INVOICE GBP rows are supported. Arrival references are immutable; current reference changes live in case events.

`data/sources/ap_case_events.csv` columns:

event_id,invoice_id,event_type,effective_at,recorded_at,po_id,actor_role,note

Types FOLLOW_UP, REFERENCE_CONFIRMED, CASE_CLOSED, CASE_REOPENED. Actors AP_PROCESSOR or DEPARTMENT_BUYER. REFERENCE_CONFIRMED requires a nonempty PO reference; other types may leave it empty. All interactions are synthetic historical events, never real messages. Effective time must be on/after invoice receipt; recorded_at must not precede effective_at. Every invoice starts with an AP case OPEN at receipt; explicit closure/reopen events determine case state at cutoff. CASE_CLOSED does not mean paid. FOLLOW_UP does not prove resolution. Proposed next actions in outputs are recommendations, not executed interventions.

`data/sources/export_manifest.json` contains schema_version=1, dataset_kind=synthetic, seed, organisation, history_start, exported_at, default_start, default_as_of, completeness booleans (po_registry_complete, po_history_complete, invoice_feed_complete, case_history_complete), and a files mapping with sha256 for each of the three input files. All complete flags must be true for this bounded prototype. Manifest and file hashes form the declared snapshot contract, not proof that a real system is complete.

## Validation

Fatal: missing/unreadable source, bad schema/version, hash mismatch, inconsistent/missing core SQL identity/foreign keys, incomplete declared source history, source export older than cutoff, or history start after cohort start. Preserve raw snapshots and failure logs; no successful publication on failure.

Safe, logged fixes: trim surrounding whitespace, uppercase contract-defined identifier/status/currency fields, normalize timezone-aware timestamps. Never fuzzy-match parties or invent timestamps, PO references, owners or money.

AP invoice validation: invalid mandatory fields/date/amount/category/document type -> row quarantine. Exact duplicates after safe normalization collapse with audit; conflicting duplicate invoice_id quarantines all competing rows. Different invoice IDs sharing a supplier/commercial-number key are retained but classification UNKNOWN, never silently merged. Negative amounts in CREDIT_NOTE records remain parseable exclusions; nonpositive INVOICE amounts are invalid. Record-level reconciliation raw = canonical + duplicate rows removed + quarantined rows.

Invalid PO event rows with an identifiable existing PO taint that PO; its assessments become UNKNOWN rather than treating a discarded approval/cancellation as absent. Invalid reference/closure history with an identifiable invoice taints that invoice. Unknown SQL parent identities or duplicate primary identities are fatal. Unknown but well-formed invoice supplier/request IDs remain invoice rows and become UNKNOWN where evidence is insufficient. Source rows must not silently disappear.

