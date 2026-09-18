# Evidence ledger: supplier-invoice PO evidence review

Research cutoff: 18 September 2026. Public primary sources only; no interviews, client access, or outreach. This is evidence for a student simulation, not a commissioned BHT project.

## Decision

The case is credible enough for a small synthetic pipeline that identifies and explains procurement exceptions for AP review. The public evidence establishes an existing workflow problem and existing responses. It does **not** establish that another dashboard is wanted, that missing information is the root cause, that this is a priority problem, or that the proposed pipeline will improve payments.

Use synthetic operational records for invoice-level metrics. Keep public board figures in a separate context table with their original grain. Do not manufacture invoice records from published totals or describe generated data as BHT data.

## Latest-report check

The latest finance report **located in the official public board index** on the research date is the report for **30 June 2026**, linked from the **30 July 2026** meeting bundle. The bundle page gives **29 July 2026** as its document date. The 2026 index lists July, May, March, February and January; no later bundle was listed. This is a bounded finding about the public index, not proof that no newer internal or separately published report exists.

- [Official 2026 board index](https://www.buckshealthcare.nhs.uk/publications/trust-board-papers/trust-board-meetings-2026/)
- [July bundle and publication date](https://www.buckshealthcare.nhs.uk/documents/v-trust-board-papers-july-2026/)
- [Official index API, used to preserve its current entries](https://www.buckshealthcare.nhs.uk/wp-json/wp/v2/pages/43064)

Search indexing and the web reader missed several valid 2026 URLs. Direct HTTPS retrieval returned PDFs successfully. The saved index/API and bundle snapshots support the freshness check. Do not infer absence from search-engine results or from the empty WordPress media search response.

## Evidence ledger

Page numbers below are **one-based PDF page numbers**, not slide labels. The 2019 source has both locators. Dates distinguish reporting period from publication/meeting date.

| ID | Exact supported claim | Source and date | Locator | Caveat / permissible use |
|---|---|---|---|---|
| A1 | April register: 194 NHS plus 1,711 non-NHS invoices; total value £16.5m. Count increased by 228 from March. Management attributes the increase mainly to delayed 2026/27 PO setup. | [April finance report](https://www.buckshealthcare.nhs.uk/wp-content/uploads/2026/05/13.2-M01-Finance-Report.pdf), period 30 April 2026; [bundle dated 27 May](https://www.buckshealthcare.nhs.uk/documents/w-trust-board-papers-may-2026/) for 28 May meeting | p15, Tables 11–12 and accompanying text | Management attribution, not a causal estimate. The register includes several approval blockers. Do not label all 1,905 invoices as missing-PO invoices. |
| A2 | April reports 191 PO lines raised after invoice date, compared with 253 in March. It describes missing/invalid or exhausted POs and AP working with departments to arrange creation. | April report, same URL/date | p16, upper chart and narrative | Line counts, not invoice counts. Invoice issue date is not invoice receipt date. The report also proposes a targeted review, indicating underlying causes still need investigation. |
| A3 | April reports non-NHS BPPC of 94% by count and 92% by value; commentary says cash was sufficient. | April report, same URL/date | p16, BPPC section | These are payment-performance measures, not missing-PO incidence. They cannot isolate the effect of one exception category. |
| B1 | June register: 207 NHS plus 1,617 non-NHS invoices; £15.8m. Count fell by 110 from May while value rose £3m, mainly because large capital invoices awaited authorisation. | [June finance report](https://www.buckshealthcare.nhs.uk/wp-content/uploads/2026/07/11.2-M03-Finance-Report.pdf), period 30 June 2026; July bundle dated 29 July | p15, Tables 11–12 | Strong counterevidence to treating register value as a missing-PO backlog or reading count and value as the same outcome. |
| B2 | June reports 275 retrospective PO lines, versus 214 in May; Specialist Clinical Services improved while Integrated Medicine had the largest in-month increase. | June report, same URL/date | p16, upper chart and narrative | No line-to-invoice bridge, denominator, receipt timestamp or time-spent measure is published. Department differences do not prove cause. |
| B3 | June lists missing/invalid POs, unrecorded receipt and disputes as approval blockers; AP works with departments. | June report, same URL/date | p15–16 | Existing workaround and multiple failure modes. No evidence that AP lacks a queue or a reporting tool. |
| B4 | June non-NHS BPPC is 91% by count and 85% by value. The report labels these YTD figures and excludes disputed invoices. | June report, same URL/date | p16, BPPC section | Do not call these June-only rates or reproduce BPPC from an unrelated synthetic denominator. |
| C1 | Departmental training and P2P improvement work already existed; the report describes retrospective orders falling to 5.4% and an invoice-register reduction of nearly 2,000. | [January 2019 board papers](https://www.buckshealthcare.nhs.uk/wp-content/uploads/2021/05/1901_Trust-Board-papers_January-2019-compressed.pdf), meeting 30 January 2019 | PDF p95 / finance slide p20 | Historical counterevidence to claiming the process was never addressed. This does not establish current training availability, comparability with 2026, or training-caused improvement. The 2021 URL folder is not the report date. |
| D1 | HMRC describes PO approval before supply/invoice processing, change tracking, recorded receipt, two-/three-way matching, invoice uniqueness, and organisational-unit accuracy. | [HMRC GfC8, Procure to pay, part 4](https://www.gov.uk/government/publications/help-with-vat-compliance-controls-guidelines-for-compliance-gfc8/procure-to-pay-part-4), updated 27 July 2026 | HTML sections: Purchase order; Receipt of supply; Tax invoice | General control guidance, not BHT's configuration or a discovered source schema. Use as a domain basis for a simulation. |
| D2 | HMRC explicitly discusses legitimate non-PO purchases and matching those invoices to contract terms; services can have different receipt evidence from goods. | HMRC GfC8, same URL/date | Purchase order; Receipt of supply; Tax invoice | Missing PO is not universally an invalid invoice. The actual organisation's approved exemption policy remains unknown. |
| E1 | The assignment permits realistic synthetic data, requires at least two source types, and calls for one project KPI, 3–5 supporting metrics, and a repeatable retrieve → validate → model → metric pipeline with checks/logging. | Supplied assignment brief, undated; requirements mapped in [verification record](../docs/verification.md) | p1 | The deliverable is a small dependable workflow. Real client access is not a prerequisite; simulated stakeholder assumptions must stay explicit. |

## Short quotations for traceability

These are the only substantive verbatim excerpts in this ledger; each source remains below 25 quoted words.

- April p15: “The main reason for this is the delay in raising Purchase Orders for the 2026/27 financial year.”
- June p16: “275 PO lines where the PO had been raised after the corresponding invoice date”
- January 2019 PDF p95: “departmental training sessions are ongoing”
- HMRC, Tax invoice control point 2: “An invoice is recorded only once.”

## What the public data can and cannot support

**Supported:** a reproducible context table containing report month, published retrospective-PO-line count, register invoice counts/value, and carefully labelled payment percentages. The published retrospective-line observations available here are March 253 (reported as comparator), April 191, May 214 (comparator), June 275. These four points are not a causal trend study.

**Not supported by the inspected sources:** an invoice-level missing-PO-at-receipt rate; its denominator; days from receipt to owner assignment, PO resolution or payment; exception-specific overdue exposure; number of chases; AP labour cost; precision of automated classification; intervention effectiveness. They lack invoice/line IDs, PO links, usable-value history, receipt/issue distinctions, exemption flags and event histories. Published supplier subtotals do not fill these gaps.

Do not divide 275 retrospective PO lines by 1,824 registered invoices. They have different grains and populations: one is a monthly line measure, the other a stock of unapproved invoices at period end. Also do not equate a missing PO reference on an invoice with an absent PO in procurement.

No usable invoice-event-level BHT dataset was found in this bounded review. This is not a claim that no public procurement dataset exists anywhere. Paid-spend or award records would need their field definitions inspected before use; supplier/amount/payment-date alone cannot reconstruct exception history.

## Final synthetic data boundary, not an observed BHT schema

The final project implements **PO header evidence review**, not full PO usability or payment readiness. Earlier exploration considered line allocations, remaining value and goods receipts. Those would require additional authoritative ledgers and are outside this MVP. The authoritative field-level contract is [data contract](../docs/data-contract.md).

All schema names, statuses, distributions, fictional parties, owner mappings, exemptions and timing rules are project assumptions. Public sources motivate scenarios; they do not validate generated frequencies. Both source types originate in a single synthetic generator, not two independently observed enterprise systems.

| Data and grain | Authoritative source within the simulation | Main fields |
|---|---|---|
| One original invoice source record | AP CSV export | invoice_id, supplier_id, commercial invoice number, request_id, original po_id, issued_at, received_at, GBP pence, category, document_type |
| One request and one PO header | Procurement SQLite tables, retrieved with SQL | request_id, department_id, supplier_id, po_id, currency, created_at |
| One immutable PO status event | Procurement SQLite history | event_id, po_id, status, effective_at, recorded_at |
| One interaction or reference/case-state event | AP case-event CSV export | event_id, invoice_id, event_type, effective_at, recorded_at, confirmed reference, actor role |
| One department or supplier | Procurement SQLite masters | stable ID, fictional name, routing role where known |

One invoice may reference one PO; several invoices may share that PO. Amount capacity, invoice lines, tax, goods/service acceptance, disputes, invoice approval and payment are not assessed. READY means only the declared header checks passed. A CLOSED AP case is not a payment, and a synthetic follow-up is not proof of benefit.

### Classification and quality rules

1. Preserve issue, receipt, source effective and source recorded timestamps. Original receipt classification uses the original reference. Current reference corrections must not rewrite it.
2. Record late-arriving or equally timed decision evidence as UNKNOWN where ordering cannot be established. Do not replace historical state with today's state.
3. Under the declared complete source contract, blank reference, unknown reference, known party/request/currency mismatch and unapproved/cancelled/closed headers receive separate review reasons. A blank reference does not prove no other PO exists. A stale or incomplete extract cannot establish absence and fails the publication gate.
4. Restrict the primary population to positive routine GBP invoices in the stated arrival cohort. Credit notes, non-GBP documents and explicitly excluded categories remain visible outside that population. Unknown/invalid policy is not an invented exemption.
5. Log only safe text, identifier and timezone normalization. Preserve original bytes. Never infer missing identity, authority, time, amount or owner.
6. Collapse exact duplicate source rows with an audit; quarantine all conflicting versions of one source ID. Different IDs sharing a commercial invoice reference are retained as uncertain, not silently merged.
7. Quarantine malformed records. If discarded event evidence could change a decision, mark its parent UNKNOWN. A lost cancellation must not make an invoice look ready.
8. Aggregate event histories to one invoice-level assessment before metric joins. Reconcile raw, canonical, duplicate and quarantined records. Unknown cases stay visible alongside assessed cases.
9. Distinguish PO evidence clearance, formal AP case closure and payment. Only the first two are represented in this simulation, with separate evidence.
10. Output a proposed human review action. The pipeline does not contact suppliers, create or approve POs, assert receipt, release payment or claim a completed operational intervention.

### Selected KPI and supporting measures

**Primary:** confirmed PO-header exception records at receipt divided by assessable eligible canonical invoice records. Assessable means READY plus EXCEPTION. Always show the numerator, denominator, UNKNOWN count and assessment coverage. This is an invoice-arrival cohort measure, not BHT's PO-line/date measure or period-end register stock.

Exactly five supporting measures are current confirmed open exceptions by reason, their gross GBP invoice value, their median invoice age, department routing-role coverage, and arrival assessment coverage. Gross value is not unpaid/overdue/lost money; invoice age is not exception duration; role coverage is not accepted ownership. Zero denominators produce null and an explanation.

Success now means preserved SQL/CSV retrieval, independently expected edge-case classifications, correct invoice-grain joins, visible uncertainty, reconciled records, repeatable business artifacts and failed runs that do not replace successful output. Any reduction in actual workload or payment delay remains unmeasured.

## Existing responses and remaining discovery

The evidence rows already document departmental follow-up, procurement/receipting controls, reviews and historical training. Therefore compare a proposed exception view with simpler alternatives: earlier PO renewal, reminders, ownership clarification, targeted training or improvements to an existing ERP report. The research does not establish which option has highest value.

For stakeholder discovery, label roles rather than inventing interview statements: AP is a prospective user; procurement/budget holders are prospective resolution partners; finance management is a prospective sponsor. Current tooling, ownership authority, non-PO categories, extract access, reason-code reliability, renewal triggers, SLA and workload remain unknown. The finance report's authorship does not establish sponsorship of this student project.

## Saved evidence and verification

- The public repository includes the analysis, source URLs, page locators and verification hashes. Downloaded reference documents and full-text extracts are retained in the author's local audit folder; they are not redistributed in the repository. The source documents can be opened through their original publication links above.
- Downloaded primary PDFs in that local audit folder: `2026-04-finance.pdf`, `2026-06-finance.pdf`, `2026-06-finance-front.pdf`, `2019-01-board.pdf`.
- Supporting inspected papers: `2026-05-board-minutes.pdf`, `2026-07-finance-committee.pdf`. They did not provide additional current PO-training evidence in the inspected text; absence here is not proof of no training.
- `*.txt` files are local Poppler extracts. The relevant April/June pages 15–16 and historical page 95 were rendered and visually reviewed; June's source layout clips some upper-right prose, so numerical claims were checked against the embedded text as well as the visible chart/narrative. No chart bars were used to invent invoice-level figures.
- `bht-board-2026-api.json`, `board-index.html`, `july-board.html`, `may-board.html` preserve official index/bundle responses. `source-manifest.json` records source URLs and SHA-256 hashes of downloaded documents.
- The assignment was read from the supplied local PDF, without alteration. The domain guidance was opened through the official GOV.UK page.
