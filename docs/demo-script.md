# Five-minute demo speaking notes

Use these as rehearsal notes, then explain the project in your own words. The timing includes space for real commands, screen changes and readable pauses. Start with the [recording setup](recording-kit.md); keep the shorter [cue sheet](walkthrough.md) beside you during the take. No video has been recorded yet.

## 0:00–0:40 · Why this problem

Show PDF page one. Point to the public evidence and workflow.

“I'm Mohit Kumar. This project examines supplier invoices that need purchase-order evidence. Buckinghamshire Healthcare's June report records 275 PO lines raised after invoice date and describes departmental follow-up.

“AP would use the review queue to choose the next check. Finance would use the arrival KPI to investigate upstream problems. These are proposed uses. The Trust is not my client, and all operational records are synthetic. A real deployment would first need stakeholder validation.”

## 0:40–1:25 · Run and inspect the sources

Run `python3 run.py run`, then `python3 tools/inspect_sources.py`. Pause on the source names, SQL query and quality issue.

“The pipeline reads procurement records from SQLite and AP records from CSV. It preserves the exports, validates them and builds one assessment per invoice. Here are the actual source counts and a recorded SQL query.

“The quality log shows a safe currency-format correction and an invoice quarantined for an invalid amount. Original values are preserved. Missing or ambiguous evidence stays visible as uncertainty when it prevents an assessment.”

## 1:25–2:10 · Follow one invoice

Run `python3 tools/inspect_case.py INV-CASE-REFERENCE-REPAIR`. Point to original PO, arrival/current state and AP case.

“This invoice arrived on 10 August without a PO reference. A buyer confirmed the reference on 12 August. At the report cutoff, the header checks pass, while the original field remains blank.

“The AP case is still open. Those are separate states. Passing a header check does not authorise payment. Remaining order value, goods receipt, tax and disputes are outside this prototype.”

## 2:10–3:05 · Explain the results

Switch to the saved HTML report. Show the primary result, coverage and all five supporting measures. Then use browser Find for `INV-CASE-ABSENT-OWNER` and point to its route and next action.

“This report covers eligible August arrivals through the 31 August cutoff. Date, category, currency and document rules determine eligibility. Thirty-seven of 79 assessable arrivals have exceptions: 46.84 percent. Eleven are unknown; coverage is 79 of all 90 eligible arrivals.

“The queue has 28 confirmed open exceptions and nine uncertain cases. Five confirmed cases lack a role, so AP must identify an owner. Value means gross invoice value, age starts at invoice receipt, and routing means a role mapping. These cohort results do not measure time saved.”

## 3:05–3:50 · Reproduce and check

Run `python3 run.py run`, `python3 run.py verify`, then `python3 -m unittest discover -s tests -q`. Pause on the repeated run ID, verification status and test summary.

“Rerunning selects the same run ID. Verification checks the saved files and their hashes. All 51 tests pass, including checks against 40 separately specified scenarios.

“The model reduces event histories before aggregation to avoid multiplying invoice totals. The row counts also reconcile: 102 raw rows become 97 retained, one duplicate removed and four quarantined.”

## 3:50–4:55 · Show failure and state the next decision

Run `python3 tools/demonstrate_failure.py`. Leave the actual result visible while explaining the checks and remaining work. Allow up to five seconds at the end for a clear finish.

“This check uses temporary copies. It alters a CSV without updating its declared hash. The run fails, preserves the rejected data and keeps the last successful output. Restoring the input reproduces the same run.

“Before deployment, I would compare this with the existing AP report and investigate the work behind its exceptions. Earlier PO setup or better receipt capture may be more useful. Work waiting for a PO before an invoice is issued is also outside this dataset.

“This demonstrates a repeatable data workflow. Its additional value to a real team still needs to be established.”

Do one timed rehearsal with the actual screen changes. Keep the final recording close to five minutes without speaking faster to compensate for extra scenes. Do not add the optional cases from the cue sheet to the main take. If trimming is needed, preserve the synthetic-data disclosure, source retrieval, one quality issue, repaired-invoice distinction, UNKNOWN denominator and failure demonstration.
