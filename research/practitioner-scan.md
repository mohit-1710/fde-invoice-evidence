# Bounded practitioner scan: PO evidence and AP exceptions

Research date: **18 September 2026**. This supplements [the primary evidence ledger](evidence-ledger.md) and [the existing-tool check](existing-tools.md). It is discovery research for the synthetic prototype in [data contract](../docs/data-contract.md), not an interview study or evidence about BHT's internal systems.

## Decision and contribution

The scan adds two useful discovery leads: a supplier describes waiting for PO paperwork after completing work, and an SAP user reports uncertainty about whether a particular invoice extract includes no-PO invoices. Neither establishes a need for this dashboard. Official Microsoft documentation also provides a concrete counterexample to assuming that AP lacks exception queues, receipt matching, or approval visibility.

Keep the narrow PO-header prototype and its existing claims boundary. The useful additions are questions about **what never enters the invoice cohort**, **what the source extract omits**, and **what the installed ERP already does**. No exception prevalence, labour cost, payment improvement, or product demand is inferred from X.

## Method and bounded coverage

Used the installed x-recon scripts after reading both installed skill instructions. The shared account login check passed at approximately 13:57 UTC. All six searches ran sequentially on the same account, read-only, with the `latest` tab, no engagement threshold, and the exact queries below. No posting, following, messaging, outreach, profile sweep, or account rotation occurred. The requested limits sum to 150 posts; the searches returned **133 post records, 129 distinct URLs** after cross-query deduplication. Returned timestamps span 12 April 2023 to 18 September 2026. Counts describe inspected search coverage only.

| Query | Limit | Returned | Retrieval completed, UTC | Cache file |
| --- | ---: | ---: | --- | --- |
| Q1: missing/invalid PO reference | 30 | 27 | 2026-09-18 13:58:14 | `1a874fccf9d30a85.json` |
| Q2: chasing and department/PO/receipt | 30 | 30 | 2026-09-18 13:59:21 | `13722e6bf5f8e3b4.json` |
| Q3: goods receipt | 30 | 30 | 2026-09-18 14:00:26 | `c5e33cef6a646701.json` |
| Q4: existing ERP exception tooling | 20 | 20 | 2026-09-18 14:01:15 | `f5dd56cc7eec2672.json` |
| Q5: narrower AP chasing refinement | 20 | 20 | 2026-09-18 14:02:19 | `b6233b0c29bc011d.json` |
| Q6: narrower receipting refinement | 20 | 6 | 2026-09-18 14:03:04 | `73f907f01183e64a.json` |

Exact raw X queries:

```text
Q1 (invoice OR invoices) ("missing PO" OR "no PO" OR "invalid PO") lang:en since:2023-01-01 until:2026-09-19
Q2 ("accounts payable" OR invoice) (chasing OR chase) ("purchase order" OR department OR "goods receipt") lang:en since:2023-01-01 until:2026-09-19
Q3 (invoice OR invoices) ("goods receipt" OR "not receipted" OR unreceipted) lang:en since:2023-01-01 until:2026-09-19
Q4 (SAP OR Oracle OR Coupa OR Dynamics) invoice (exception OR blocked) lang:en since:2023-01-01 until:2026-09-19
Q5 "accounts payable" (chasing OR chase) lang:en since:2023-01-01 until:2026-09-19
Q6 invoice receipted lang:en since:2023-01-01 until:2026-09-19
```

Each query was passed to the installed x-recon search script with `--raw <query> --limit <limit> --tab latest`. Raw caches remain outside the project; their filenames above identify the local audit records. Raw tweet JSON was not copied into this research document. No search was served as a cache hit during this run.

These are X-visible search results, not an exhaustive or representative sample. Four queries hit their selected cap. Keyword ambiguity, long-form posts, promotional content, and unrelated results reduced relevance. Some visible texts were truncated; uninspected continuations were not treated as evidence. Account occupations and client relationships were not independently verified. No clearly attributable first-person **internal AP** account of goods-receipt delays or accepted department ownership was established in the inspected text. That is a bounded research gap, not evidence that those problems do not exist.

## Retained X leads

| Lead and exact timestamp | Evidence label and observed content | Implication and limit |
| --- | --- | --- |
| Sharon O'Dea, [25 April 2024, 07:27:09 UTC](https://x.com/sharonodea/status/1783397319079018695), and [related same-day post, 11:56:47 UTC](https://x.com/sharonodea/status/1783465175107981719) | **First-person supplier-side operational complaint; not an internal AP interview.** Describes chasing a PO for work completed weeks earlier and presents the missing reference as obstructing invoice issue/processing. The second post describes concern that an invoice without a PO number will disappear within finance. These are two related same-day posts, treated conservatively as one anecdotal lead. Their reply relationship was not verified. | **Inference:** work awaiting a PO before invoice intake may be absent from an invoice-arrival dataset. Our KPI cannot measure that upstream population. Ask whether supplier queries or unbilled work need a separate intake measure. This is an older, unverified anecdote outside the named study setting; it does not establish amount, duration to payment, responsible department, or cause. |
| Matt Harding, [31 October 2023, 03:12:07 UTC](https://x.com/mattharding/status/1719190485556945094) | **First-person technical extraction report; tentative and historical.** Reports trying `I_SupplierInvoiceAPI01` to obtain supplier invoices and apparently not receiving no-PO invoices. The author explicitly questions configuration and deployment assumptions. | **Discovery lead:** reconcile invoice origins/statuses and PO/non-PO populations before treating an ERP view as complete. Do not repeat this as a confirmed or current SAP product limitation. The post does not establish the customer's configuration, the root cause, or whether the issue was later resolved. |

No direct quotations are needed to support these limited observations. Neither lead supports BHT-specific attribution or changing synthetic scenario frequencies.

## Promotional material was not practitioner validation

For auditability, two examples show the distinction. [Polsia, 11 September 2026 at 17:43:47 UTC](https://x.com/polsia/status/2098467556931817783), promotes a forthcoming product covering invoice extraction, exceptions, approvals and follow-ups. [Refrens, 3 September 2026 at 06:31:25 UTC](https://x.com/RefrensApp/status/2095399246166200460), introduces a product with a general claim about accounting teams' bill-handling work. **Both are promotional claims**, not observed AP incidents or independent effectiveness evidence. Their workload and automation claims are not adopted here. Training, generic advice, political allegations, and unrelated uses of “PO” or “receipt” were also excluded from the retained evidence.

## Primary-source follow-up and counterevidence

The technical lead prompted an exact-view lookup (`site:help.sap.com "I_SupplierInvoiceAPI01" "Supplier Invoice"`). SAP's [Supplier Invoice CDS documentation](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/ee6ff9b281d8448f96b4fe6c89f2bdc8/9d726dde11a445f29cb5b705ec6433d4.html) identifies the view and lists invoice status, origin, company, dates and other metadata in indexed official content. The direct web reader returned an empty body, and the available official text did **not** resolve the reported no-PO coverage issue. It remains a question to test against a specific system and reconciled extract, not a verified limitation.

Official ERP follow-up also included `site:learn.microsoft.com "vendor invoice" "exceptions" "workspace"`. The following Microsoft pages were directly opened on 18 September 2026:

| Official documentation | Supported capability and qualification | Consequence for the prototype |
| --- | --- | --- |
| [Invoice automation for scanned documents](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/vendor-invoice-automation), updated 4 August 2026; “Exception processing” and “Shared service vs. organization-based exception processing” | Documents an invoice import-failure list, including PO number and error information, correction into pending invoices, and security by role, user or legal entity. These are import exceptions, not a claim that every missing-PO scenario receives the same treatment. | A separate review queue may duplicate existing functionality. Inspect existing intake and failure queues before specifying another one; an export of only successfully created invoices may omit failed intake. |
| [Vendor invoice center workspace overview](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/vendor-invoice-workspace), updated 4 August 2026; “Automation stage” and “Workflow stage” | Describes receipt-match errors after attempted matching, workflow failures, and pending approver/time/due-date visibility. **The page explicitly requires the Preview New vendor invoice center feature to be enabled.** It is not a claim that every tenant has this view. | Owner visibility and exception status are already documented product capabilities. A mapped department role in our report is weaker evidence than an actual configured approver or accepted owner. |
| [Set up options for vendor invoice automation](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/vnd-invoice-set-up-options), updated 11 June 2026; “Parameters for submitting imported vendor invoices to the workflow system” | Documents configurable matching of posted product receipts to invoice lines, attempt limits and workflow-submission rules. | A valid PO header does not settle the receipt question. Keep receipts and payment readiness outside `READY`; discover whether delayed receipt entry, configuration or another cause dominates actual cases. |

These are primary descriptions of product behaviour, not independent performance studies. They establish neither BHT's ERP/vendor/version nor enabled features, access rights, data quality, usability or adoption. They reinforce the existing-tool counterevidence without proving the incremental value of this prototype's historical reconstruction.

## Discovery work that remains

1. **Reconcile intake boundaries.** Identify emailed invoices, failed imports, returned invoices and supplier work waiting for a PO. Establish which are absent from the intended export and from an invoice-arrival denominator. The prototype cannot count unissued work as received invoices.
2. **Inspect the current exception view.** Walk through a small, authorised set of missing-reference, invalid-reference, late-approval and receipt-related cases with AP. Compare existing reason, history and routing fields with the proposed output. No such walkthrough or interview has occurred.
3. **Establish source completeness.** Validate document origins, legal entities, statuses, PO/non-PO handling and exclusion rules against source totals. A manifest completeness flag in generated data is a simulation contract, not evidence that a real export covers the same population.
4. **Separate routing from accountability.** Determine who can confirm the reference, amend an order, approve it and record receipt; then check escalation and ownership acceptance. A nonempty role mapping measures routing coverage only.
5. **Compare simpler interventions.** Earlier PO creation/renewal, supplier reference instructions, timely receipt recording, role maintenance or configuration of existing reports may address the cause more directly. Their relative value and any time-saving effect remain unmeasured.

This scan changes the discovery questions and strengthens the scope caveats. It does not justify expanding the implementation, claiming demand, or presenting synthetic clearance as an operational improvement.
