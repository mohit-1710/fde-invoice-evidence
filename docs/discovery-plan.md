# Discovery if operational access becomes available

This is a proposed plan, not completed research. No organisation has agreed to a meeting or supplied operational records.

## First conversation

Ask the AP manager and one processor to walk through a recently delayed invoice in their existing system. Establish the actual decision owner rather than assuming the proposed roles in the brief are correct.

1. What prevented the next step, and which screen or record showed it?
2. What did AP need from another person? How was that person found, and what happened when ownership was unclear?
3. Which parts of this information already appear in the exception report? What requires another search or manual reconstruction?
4. Which purchases legitimately have no PO? Who maintains that policy and the department-role mapping?
5. Are retrospective PO setup, missing receipt entry, exhausted order value or disputed invoices responsible for more review effort than missing reference/approval evidence?

Inspect both an ordinary case and an unresolved or contradictory one. A memorable difficult example can reveal a failure mode but cannot establish its frequency.

Also ask what never becomes a received invoice: unissued supplier work waiting for a PO, emailed documents returned before entry and failed imports. These are possible gaps in an invoice-arrival export, not populations measured by this prototype. The [practitioner scan](../research/practitioner-scan.md) records the limited evidence behind this question.

## Evidence needed before proposing a pilot

Request an authorised, minimised export of consecutive invoice arrivals over an agreed interval, with stable pseudonymous invoice, supplier, request, PO and department IDs. Preserve creation, receipt, effective and recorded timestamps and the extract boundary. Agree category exclusions, completeness limits and which system owns each field. Do not use names, bank details or invoice documents when IDs and event fields are sufficient.

Have AP annotate a sample using existing records and explain unresolved cases. Compare the current report and the prototype on those same records: do they identify the same evidence and responsible route, and what extra work does each require? Keep disagreements visible and review them with the process owner. This is a proposed evaluation, not a claimed result or a representative sample already obtained.

## Decision after discovery

Before any trial, the AP process owner would approve the eligible invoice types, evidence rules and named escalation roles. Use consecutive eligible cases from an agreed interval, and record every exclusion and missing history. This protocol is proposed; it has not been carried out.

Compare the existing report and prototype on the same cases. Have an AP reviewer first establish the supported next action from the underlying records, allowing UNKNOWN where the evidence is insufficient. Counterbalance which view processors see first to reduce practice effects. Measure elapsed time to a review decision, compare its action and route with the agreed review, and record unresolved cases rather than treating them as successes. Summarise paired time differences and the count and details of wrong routes. A small feasibility sample cannot establish an organisation-wide savings estimate.

The owner must set the acceptable error and effort thresholds before inspecting results. Any recommendation to authorise payment is outside the prototype's scope and would stop the trial. Consider broader use only if the comparison shows a useful time reduction without exceeding the agreed routing-error limit, and an accountable owner accepts unresolved cases. This is a future usefulness test; it does not change the prototype's one diagnostic KPI and five supporting measures.

- If the present system already gives equivalent trustworthy evidence and routing, improve its use or configuration instead of introducing another queue.
- If annual PO setup or receipt entry consumes more review effort, prioritise that handoff. The public reports make both plausible alternatives.
- If missing or inconsistent histories prevent reliable classification, fix the source contract and event capture before using the metric to judge performance.
- Consider a limited review trial only if a named owner can identify a specific unmet decision and accepts the field definitions, uncertainty handling and scope exclusions.

The synthetic rate cannot estimate the size of that opportunity or set a justified improvement target. Real usefulness, authority, workload and payment effects remain unknown.
