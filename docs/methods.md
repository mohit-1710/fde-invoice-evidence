# Methods and reproducibility

This document describes the implemented synthetic PO header evidence review. Field-level definitions are in [the data contract](data-contract.md); results are in the run selected by [`artifacts/latest.json`](../artifacts/latest.json).

## Research and synthetic provenance

Public BHT finance reports identify retrospective purchase orders and several invoice-approval blockers. HMRC procure-to-pay guidance supplies general control context. These sources motivate a review workflow; they do not establish demand for this tool, an invoice-level exception rate or the effect of an intervention. The [evidence ledger](../research/evidence-ledger.md) records source URLs, reporting/publication dates, page locators, counterevidence and research limits. Downloaded evidence and its [source manifest](../research/source-manifest.json) are retained separately from operational inputs.

The pipeline uses no BHT operational data. [`generate.py`](../src/po_review/generate.py) creates the fictional Alder Vale Services exports: 60 ordinary illustrative invoices plus 40 named scenarios, with duplicate rows bringing the raw invoice count to 102. Dates, amounts, parties, roles, category policy and scenario frequencies are project assumptions. This is a test fixture, **not a representative sample**. Both source types come from one generator; they are not independently observed enterprise systems.

The default seed is `20260918`. Limited seeded randomness affects ordinary examples; named scenarios remain fixed. Generation is an explicit operation and imports no model or validation logic. [`data/scenario_expectations.json`](../data/scenario_expectations.json) is a hand-specified test oracle, kept outside the input manifest and never read as a business input.

## Intended decisions and evidence of success

The prototype serves two assumed decisions. AP would use the current cohort queue to identify records requiring review and choose a routing/action sequence. Finance would use the arrival KPI and its uncertainty/coverage to diagnose upstream PO-evidence conditions at receipt. These prospective user roles and decisions have not been confirmed through interviews or field discovery.

The primary KPI is a diagnostic arrival-condition measure. The original invoice reference stays immutable. Arrival evidence is reconstructed using the stated report cutoff, so newly available late or invalid history can change what is assessable. Later correction of a current case does not demonstrate better conditions at receipt, and a change in this KPI cannot by itself measure the benefit of handling those cases. Success demonstrated by this assignment is technical validation: agreement with independently specified scenarios, reconciled records, visible uncertainty, reproducible artifacts and failure containment. Neither passing those checks nor synthetic changes between arrival and cutoff demonstrate KPI improvement, workload savings or payment benefit.

## Source authority and relationships

`data/sources/export_manifest.json` declares schema version 1, synthetic provenance, the seed, three file hashes, export/history dates and completeness flags. The default history starts on 1 July 2026; the export is dated 1 September 2026 12:00 UTC. The completeness flags define the bounds of this fixture, not evidence that a real system is complete.

| Source/table | Grain and key | Authority within this simulation |
| --- | --- | --- |
| SQLite `departments` | One department; `department_id` | Department name and optional `owner_role`. A blank role stays unresolved. |
| SQLite `suppliers` | One supplier; `supplier_id` | Supplier identity. |
| SQLite `requests` | One request; `request_id` | Supplier, department, request time and category. |
| SQLite `purchase_orders` | One PO header; `po_id` | Linked request, supplier, currency and creation time. |
| SQLite `po_events` | One immutable state event; `event_id` | PO state, `effective_at` and `recorded_at`. |
| `ap_invoices.csv` | One invoice source record; `invoice_id` | Commercial document number, original request/PO references, issue/receipt time, amount, currency, category and document type. |
| `ap_case_events.csv` | One case event; `event_id` | Follow-up, reference confirmation, case closure or reopening, with both timestamps and actor role. |

A department has many requests; a supplier can have many requests and POs. Each PO links to one request and supplier and can have many state events. Several invoices may reference one PO. Each invoice has many AP case events but exactly one derived `invoice_assessments` row. The optional invoice request and PO references may be missing or unresolved; they are evidence to assess, not mandatory foreign keys that would discard these invoices. Known core procurement links are validated and enforced in the modeled database.

The pipeline copies source bytes into the attempt's `raw/` directory and checks the snapshot. It opens the copied SQLite file read-only, checks integrity/schema and executes explicit `SELECT` queries. It reads the two copied CSVs using `csv.DictReader` with required named columns. `retrieval.json` retains the queries, counts and hashes. Research PDFs and oracle labels are not pipeline inputs.

## Validation and record accounting

Safe changes are logged: surrounding whitespace is trimmed, contract-defined identifiers/codes are uppercased and timezone-aware timestamps are normalized to UTC. Missing identity, owner, reference, timestamp or money is never guessed. Amounts are integer minor units; supported invoice values are positive GBP pence.

| Condition | Treatment |
| --- | --- |
| Missing/unreadable source, bad schema/version/hash, incomplete declarations, stale export, insufficient history or invalid cohort | Fail the run; no new successful publication. |
| Invalid or duplicate core identity, unresolved core procurement parent or inconsistent PO/request supplier | Fail the run. |
| Malformed invoice field, category, document type, timestamp or amount | Quarantine the row. Nonpositive INVOICE amounts are invalid; negative credit notes can remain parseable exclusions. |
| Exact duplicate after normalization | Retain one canonical row; log removed duplicates. |
| Conflicting rows with the same invoice ID, including a malformed competing version | Quarantine every competing row. |
| Different invoice IDs with the same supplier/commercial-number pair | Retain records and mark eligible assessments UNKNOWN. Compare INVOICE records received by cutoff, including pre-cohort invoices; future arrivals and credit notes do not cause collisions. |
| Invalid PO/case history with an identifiable parent | Quarantine and mark the affected evidence UNKNOWN when it could affect the cutoff. A provably future event cannot contaminate an earlier report; unresolvable timing stays conservative. |

For invoices, PO events and case events, validation checks `raw = canonical + duplicates removed + quarantined`. The default invoice reconciliation is `102 = 97 + 1 + 4`. An explicitly empty feed can produce a report with null ratios. A nonempty feed whose invoices are all quarantined fails instead of presenting an empty success.

## Point-in-time assessment

The default cohort includes receipt timestamps from `2026-08-01T00:00:00Z` through `2026-08-31T18:00:00Z`, both inclusive. Eligible canonical records are positive GBP `INVOICE` records in category `ROUTINE`. Credit notes, other currencies, `EMERGENCY`, `CAPITAL`, `PO_EXEMPT` and receipts outside the interval are visible exclusions. Unknown categories are invalid, not inferred exemptions. The supplied run has seven excluded canonical records, one for each of these seven exclusion reasons.

The current queue and all supporting exception measures remain restricted to this selected arrival cohort. They are not a whole-AP-backlog view: for example, an invoice received before cohort start is outside the queue even if its AP case would still be open at cutoff. Pre-cohort records may provide commercial-collision evidence without entering the cohort's counts or value.

Each eligible invoice receives two assessments:

1. **Arrival:** use its immutable original PO reference and assess the header at receipt, using only evidence knowable by report cutoff. A pre-receipt state recorded after receipt makes arrival UNKNOWN; a state transition exactly at receipt also has unknown ordering.
2. **Current:** use the latest eligible `REFERENCE_CONFIRMED` event, if present, and assess the header at cutoff. Evidence must be both effective and recorded by cutoff. The latest effective state wins; different states or confirmed references tied at that timestamp are UNKNOWN. Later evidence cannot rewrite an earlier cutoff.

Under the declared complete registry, a missing reference or nonexistent referenced PO is an EXCEPTION; neither proves no other PO exists. Known supplier/request/currency mismatches, a PO created after the assessment time, or a latest state of CREATED, CLOSED or CANCELLED are exceptions. Unresolved identity, absent/invalid/ambiguous state history and commercial collisions yield UNKNOWN. Only matching header evidence with latest state APPROVED can be READY.

The implementation chooses one exclusive reason using this precedence: invalid invoice history, commercial collision, ambiguous current reference, missing/nonexistent reference, invalid PO history, unresolved identity, supplier mismatch, request mismatch, currency mismatch, creation chronology, receipt-time uncertainty, then latest PO state. The trace retains the reason and evidence IDs.

Every AP case starts OPEN at receipt. Explicit closure/reopening determines its state; conflicting or invalid case history stays UNKNOWN. The cohort queue contains eligible OPEN cases with current EXCEPTION/UNKNOWN evidence and cases with UNKNOWN case state. Unknowns route to `AP_DATA_INVESTIGATION`. Confirmed exceptions use the invoice's known request department, or the PO's request when the invoice request is blank; an absent role routes to `AP_TRIAGE`. For those cases, AP must first establish and confirm the responsible department role, then pursue the reason-specific action. The proposed action states this sequence; no owner is invented or treated as already contacted. A supplied unknown request never borrows another request's owner.

`po_condition_cleared` means arrival EXCEPTION became current READY. It is distinct from formal AP case closure. Neither state implies payment, and a FOLLOW_UP event proves no resolution.

## One KPI and five supporting measures

Histories are reduced to one invoice assessment before SQL joins and aggregation. Raw many-side events never enter invoice sums. `model.sqlite` preserves canonical tables, assessments, metadata and an `interactions` view of synthetic follow-up/reference events.

| Measure | Definition | Default result |
| --- | --- | --- |
| **Primary: arrival confirmed exception rate** | Arrival EXCEPTION / arrival assessable eligible canonical records; assessable = READY + EXCEPTION. | 37 / 79 = **46.84%**; 11 UNKNOWN. |
| 1. Open exceptions by reason | Eligible records in the selected arrival cohort with case OPEN and current EXCEPTION, grouped by one reason per invoice. | **28**: missing reference 9; cancelled 7; not approved 7; currency mismatch, closed PO, PO not found, request mismatch and supplier mismatch 1 each. |
| 2. Gross open-exception value | Sum of `amount_minor` for that same confirmed-open population. | **4,245,405 pence (£42,454.05)**. |
| 3. Median invoice age | Median of `(cutoff − received_at)` in days for that population. | **21.33 days**. |
| 4. Owner-role coverage | Confirmed open exceptions linked to a department with a nonempty owner role / all confirmed open exceptions. | **23 / 28 = 82.14%**; five AP triage cases. |
| 5. Arrival assessment coverage | Arrival READY + EXCEPTION / all eligible canonical records. | **79 / 90 = 87.78%**. |

UNKNOWN is absent from the primary assessable denominator and present in the coverage denominator. Quarantine, duplicates, exclusions and the 37-row review queue are quality controls, not additional project KPIs. Zero-denominator ratios and an empty-population median return JSON `null` with explanations; percentages display two decimals. Gross value is not unpaid/overdue exposure or loss; invoice age is not exception duration; a routing role is not accepted ownership.

## Reproduction, verification and failure handling

Run from the repository root with Python 3.9+; the commands use only the standard library:

```sh
python3 run.py run --start 2026-08-01T00:00:00Z --as-of 2026-08-31T18:00:00Z
python3 run.py run --start 2026-08-01T00:00:00Z --as-of 2026-08-31T18:00:00Z
python3 run.py verify
python3 -m unittest discover -s tests -v
```

The run ID hashes the preserved input hashes, normalized cohort/cutoff, schema version and package-code fingerprint. Repeated runs of unchanged inputs/code reproduce identical business artifacts. Logs, attempt IDs and completion times may differ. The [saved command transcript](reproducible-run.json) records successful reruns and verification; the current supplied run is `01751fcc02b6294b34f3`.

Outputs are staged and verified before publication. `latest.json` is replaced atomically as the final commit point. A handled failure exits with code 2, records FAILED in `last_attempt.json`, retains available raw bytes/diagnostics and leaves the prior successful pointer intact. Available rejected file bytes are copied before hash checking. A run directory marked VERIFIED may exist without having been published. Consult both pointers: verifying old output hashes does not make a failed latest attempt successful.

`verify` checks the exact expected raw/business file inventories and their saved hashes. These local, unsigned manifests detect inconsistency; they do not independently prove source authenticity or real-world completeness. Publication guarantees cover the tested handled failures of this local workflow, not every possible process or filesystem failure.

On 18 September 2026 the current implementation passed all **51 tests** and saved-artifact verification. The [verification record](verification.md) describes checks against all **40 named oracle cases**, offline rerun byte equality, invoice-grain counts/value, raw preservation, null denominators, malformed data and failed publication. The adversarial regression suite checks temporal leakage, conflicting records, artifact tampering and failed publication. The [live walkthrough](walkthrough.md) uses `python3 tools/demonstrate_failure.py` to demonstrate rejection and recovery with temporary copies.

## Interpretation limits

This is a tested student prototype, with no client engagement, operational deployment, measured time savings or demonstrated intervention effect. Public retrospective-PO counts are line-level figures and cannot supply this synthetic invoice KPI's numerator or denominator. Exemption policy, routing roles and complete histories would require agreement and evidence before any real use.

READY establishes only the declared PO header conditions. The model does not test remaining PO value, quantities, goods/service acceptance, disputes, tax, invoice approval or payment; multiple invoices can share a PO without any capacity check. Proposed actions are recommendations only. No output is payment-ready evidence or permission to pay.
