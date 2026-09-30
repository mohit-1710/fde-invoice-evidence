# Recording preparation notes

These notes preserve the original recording plan. The current narrated walkthrough and recording script are linked from the [project README](../README.md). Use the [cue sheet and command order](walkthrough.md) during the take, and the [spoken draft](demo-script.md) for rehearsal. Keep the cue sheet outside the captured area or on paper. Explain it in your own words once you are comfortable with the decisions.

## Set up once

Open a terminal in the project root. On Mohit's current Mac, that is:

```sh
cd /Users/mohit/sst/fde/assignment_1_exempted
```

If using a downloaded repository, use its extracted folder instead. Check the supplied output and find its report:

```sh
python3 run.py verify
```

```sh
FDE_DEMO_RUN="$(python3 -c 'import json; print("artifacts/" + json.load(open("artifacts/latest.json"))["path"])')"
open "$FDE_DEMO_RUN/report.html"
open output/pdf/10222_Mohit_Kumar.pdf
```

The `open` commands are for macOS. Elsewhere, open these files using a browser and PDF viewer. The runtime itself remains Python 3.9+ with no extra packages.

Arrange three views in advance: PDF page one, terminal, and the saved report. Start the report at the KPI and supporting measures. Make the terminal text large enough to read in a small playback window; use roughly 20-point text as a starting point, with space for the source inspector's 25 lines. Try 125% browser zoom for the report and widen the captured area until the queue's route and full action column are visible. Confirm this in the short test recording. Keep a fixed window size while switching views. The cue sheet tells you when to switch.

Run the source inspector once before recording so you recognise the evidence:

```sh
python3 tools/inspect_sources.py
```

It checks the raw and business-output hashes, then displays preserved SQLite/CSV exports, recorded source counts and a SQL query, a safe currency-format correction and one quarantined invoice issue. The full files remain available; this is a readable view of their contents, not a substitute or mock output. `retrieval.json` is recorded provenance metadata; it is not itself covered by `verify`. Its counts have been independently checked against the supplied source files.

## Record on the Mac

Press **Shift-Command-5**, select **Record Selected Portion**, and frame the presentation area. Under **Options**, choose your microphone and save location. Make a 15-second test with your voice and one view change, stop, and play it back. Then record the full take. These controls are documented in [Apple's screen-recording guide](https://support.apple.com/en-in/guide/mac-help/mh26782/mac), checked 18 September 2026.

Keep notifications and unrelated windows out of the frame. A clean screen capture and your voice are sufficient for this walkthrough. Use your normal pace, and pause briefly on each actual result so it can be read.

Aim to finish around **4:50 to 5:00**. This is a rehearsal target, not permission to exceed a stated five-minute limit. The draft is deliberately shorter than the earlier version to leave time for commands and switching. Your first timed rehearsal, rather than a word-count estimate, determines the final pace.

## Evidence that must survive any trimming

- Explain the public evidence, the two intended decisions and the synthetic-data boundary.
- Run the pipeline and show that SQL and CSV sources were actually retrieved, preserved and checked. Show one quality issue.
- Follow the reference-repair invoice: arrival exception, later header clearance, AP case still open.
- Explain `37/79`, the 11 UNKNOWN arrivals, and assessment coverage. Show the five supporting measures, then the absent-owner queue row and its proposed action.
- Show the repeated run, hash verification, passing tests and actual failure/recovery demonstration.
- End with what has not been established and what would make you choose a different intervention.

If rehearsal runs long, remove repeated explanations of individual supporting metrics first. Keep the denominator, one traced case and failure demonstration. The late-recorded case and absent-owner case are useful for questions, but are not extra scenes in the five-minute take.

## Rehearse the reasoning

Be able to answer these without reading the script:

| Likely question | The point to explain |
| --- | --- |
| Why this problem first? | Public evidence describes a real handoff; a narrow evidence check can be tested. Priority in a real organisation is still conditional on workload and existing tools. |
| Is 46.84% a real organisation's exception rate? | No. It is 37 of 79 assessable records in a deliberately constructed synthetic fixture. |
| Why leave 11 records out of that denominator? | Their arrival evidence is insufficient or ambiguous. Coverage separately reports 79 of all 90 eligible arrivals, so uncertainty stays visible. |
| Why can an invoice pass checks and still be open? | Header evidence and AP case disposition are separate. Receipt, remaining order value, approval and payment require other checks. |
| Would a good PO reference prove a PO was in place at arrival? | No. Both event time and recorded time matter. A late record does not prove earlier evidence was available. |
| Why not use the existing ERP? | That may be the better choice. Discovery must compare the installed report, earlier PO setup and receipt capture before proposing another queue. |

## After the take

Save the untouched recording as `10222_Mohit_Kumar_Demo_original.mov`. A suggested local location is `output/video/`; create it when saving. Watch the complete take once, checking voice clarity, readable results, sequence and duration. Confirm that the spoken numbers match what is on screen. The expected test result is **52 tests, OK** and the failure demonstration is **DEMONSTRATION_PASSED** with all eight checks true.

The recording can then be trimmed and exported for sharing, with the original retained. The delivered narrated walkthrough is linked from the [project README](../README.md).
