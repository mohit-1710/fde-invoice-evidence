# Five-minute demo cue sheet

This is the original command-oriented preparation sheet. The delivered edited walkthrough follows the [current recording script](own-voice-script.md); its link is in the [README](../README.md). Use the [recording kit](recording-kit.md) to reproduce this command order. The [speaking draft](demo-script.md) follows this exact order. This is a cue sheet for your own explanation, not an additional set of scenes.

| Time | Show | Say in your own words |
| --- | --- | --- |
| 0:00–0:40 | PDF page one: evidence and workflow | Publicly documented handoff. AP chooses the next check; finance investigates arrival conditions. All operational data is synthetic; no client access. |
| 0:40–1:25 | Real run, then source inspector | SQLite + CSV, preserved files, recorded SQL, safe currency correction and quarantined amount. One model assessment per invoice. |
| 1:25–2:10 | Reference-repair case | 10 Aug blank reference; 12 Aug confirmation; current header passes; AP case stays OPEN. No permission to pay. |
| 2:10–3:05 | Report measures, then Find `INV-CASE-ABSENT-OWNER` | August cohort; 37/79 = 46.84%; 11 UNKNOWN; coverage 79/90. Queue = 28 confirmed + 9 uncertain. Show the route and owner-first action. |
| 3:05–3:50 | Rerun, verification, test summary | Same run ID; hashes verified; 52 tests; 40 known scenarios. 102 = 97 + 1 + 4. |
| 3:50–4:55 | Failure/recovery result | Temporary copy; rejected input preserved; previous success retained; restoration reproduces output. Check existing tools and earlier PO/receipt work before deployment. |

Allow the final five seconds for a clean finish. Use pauses to make the actual outputs readable, not to fill time.

## Commands in recording order

Run these individually from the project root. Paste one command, wait for its real output and explain it before moving on.

At 0:40:

```sh
python3 run.py run
python3 tools/inspect_sources.py
```

At 1:25:

```sh
python3 tools/inspect_case.py INV-CASE-REFERENCE-REPAIR
```

At 2:10, switch to the report already opened during setup. At 3:05, return to the terminal:

```sh
python3 run.py run
python3 run.py verify
python3 -m unittest discover -s tests -q
```

At 3:50:

```sh
python3 tools/demonstrate_failure.py
```

Expect `DEMONSTRATION_PASSED` and all eight checks true. This command runs against temporary copies; it leaves project inputs and saved artifacts unchanged. The inspector commands read the verified saved files. None of these commands sends messages or authorises payment.

## Numbers to recognise, not all to read aloud

| On screen | Meaning |
| --- | --- |
| 37 / 79 = 46.84% | Confirmed arrival exceptions among assessable eligible arrivals. |
| 79 / 90 = 87.78% | Arrival assessment coverage; 11 remain UNKNOWN. |
| 28 | Current confirmed open exceptions within the arrival cohort. |
| £42,454.05 | Gross invoice value of those 28, not unpaid cash or loss. |
| 21.33 days | Median age since invoice receipt, not duration in exception. |
| 23 / 28 = 82.14% | Department-role routing coverage; not accepted ownership. |
| 37 review rows | 28 confirmed exceptions plus 9 uncertain items. This is a different population from the 37 arrival exceptions. |

## Optional examples for later questions

These are outside the timed recording. Use them only if asked or while practising.

```sh
python3 tools/inspect_case.py INV-CASE-LATE-RECORDED
python3 tools/inspect_case.py INV-CASE-ABSENT-OWNER
```

The first illustrates why recording time matters to the arrival assessment. The second shows AP triage when the department role is missing. Neither establishes a deployed outcome or payment readiness.
