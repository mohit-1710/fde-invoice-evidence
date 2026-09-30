# Own-voice recording script

Recording version updated 30 September 2026, 22:45 IST. Read only the spoken paragraphs below.

## Recording instructions — do not read aloud

- Use your normal conversational voice. Record one continuous take and stay at a steady distance from the microphone.
- Pause for two seconds between numbered sections. Do not read section numbers, headings or delivery cues aloud.
- If you stumble, stay quiet for three seconds and repeat the complete sentence. Keep recording.
- Keep the sentences flowing; give numbers a little more time. The video will follow your actual recording.
- SQLite: “S-Q-L-ite”; SQL: “S-Q-L”; CSV: “C-S-V”; AP: “A-P”.
- Save your original M4A, WAV, AIFF or MP3. Extra pauses and repeated takes can be edited later.

## 1. Opening — scene: opening

Hi, I'm Mohit Kumar. I built this invoice review queue to answer two questions: what needs checking on an invoice, and who should check it next?

## 2. Why this problem first — scene: handoff

I started with a specific handoff in accounts payable. Buckinghamshire Healthcare's June report identifies two hundred and seventy-five purchase-order lines raised after invoice dates, and delays in finding the right department. I chose this problem because a missing reference or approval needs a clear follow-up action. That is the decision this queue supports.

## 3. Scope — scene: scope

The queue is designed for the accounts-payable team. It covers routine invoices in British pounds within the August window shown here. Each invoice is checked for its order reference, supplier, request, currency and approval evidence. READY means those purchase-order checks passed.

## 4. Sources — scene: sources

The order records come from SQLite; invoices and case updates come from CSV. Here's the SQL query used to read the orders. I preserve the original exports, along with the queries, row counts and hashes, so results can be traced back to their source.

## 5. Cleaning — scene: cleaning

Here, I trim and capitalise the currency code. The amount below needs whole-number pence, so that row is quarantined. The original stays untouched. One hundred and two raw rows become ninety-seven retained, one duplicate removed and four quarantined. Seven exclusions leave ninety eligible invoices.

## 6. Model — scene: model

The model links suppliers, departments, requests, purchase orders and invoices. Several events can describe one invoice, so I reduce the history to one assessment row before calculating totals. Each row has an arrival result and a cutoff result, using both the effective and recorded times.

## 7. One invoice — scene: case

Here's one example. This invoice arrived on the tenth of August without an order reference. The buyer confirmed one two days later. At the cutoff, the purchase-order checks pass. The AP case stays open until a closure event is recorded. The original reference stays visible on the left, so the change is traceable.

## 8. Results — scene: metrics

At arrival, thirty-seven of seventy-nine assessable invoices have confirmed exceptions: forty-six point eight four percent. Eleven are unknown; assessment coverage includes all ninety eligible invoices. Alongside that arrival KPI, the report shows exception reasons, gross value, invoice age, department-role coverage and assessment coverage.

## 9. Next action — scene: routing

At the cutoff, twenty-eight confirmed open exceptions and nine uncertain cases need review. Five confirmed cases lack a department role. Look at this blank field: the queue directs AP to identify that role first, then ask the buyer to review approval evidence.

## 10. Verification — scene: verification

I checked reliability in three ways: repeat runs, file hashes and automated tests. The runs produced the same business outputs, the hashes verified, and all fifty-two tests passed. These include forty separately specified scenarios.

## 11. Failure handling — scene: failure

I also tested failure handling by changing a temporary CSV while keeping its old hash. The pipeline rejected it and preserved both the rejected input and the previous successful report. Restoring the input reproduced the same successful run.

## 12. Why this problem first, and what comes next — scene: next

That's why I chose this problem first: it connects a missing piece of evidence to a specific next action. The result is a working queue with a traceable decision for each invoice. Next, I'd compare review time and routing accuracy against the existing AP report on the same cases.

## Edit handover — do not read aloud

- The spoken script is frozen for recording. Preserve the original audio and match the final spoken takes to the 12 scene IDs.
- Align scene reveals, pointer cues and captions to the actual recording. Leave reading time for the supporting metrics.
- Preserve the existing backup. Create the new own-voice export separately.
- Show the actual project outputs, precise dates, cohort and metric populations. Keep the original invoice evidence and later events distinct.
- Saved command captures remain saved captures. The on-screen proposed action is a recommendation produced by the queue.
- Verify audible numbers, caption text, audio levels, synchronization and complete playback. The final demo must be under five minutes.
