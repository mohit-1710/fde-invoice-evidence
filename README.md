# Supplier-invoice PO evidence review

**Mohit Kumar · 24bcs10222 · Internship-exempted FDE assignment**

A small, offline Python pipeline that retrieves procurement records from SQLite and accounts-payable (AP) exports from CSV, validates them, and produces an invoice-level review queue with one KPI and five supporting metrics. It preserves the original invoice-receipt assessment separately from the assessment at the report cutoff.

**All operational records are synthetic.** Fictional parties and deliberately selected scenarios exercise the rules; this is not a representative sample or an estimate of any organisation's workload. Public Buckinghamshire Healthcare NHS Trust (BHT) reports motivate the problem. BHT is not a client and none of its operational records are used. There were no interviews, deployment or measured benefits.

The intended decisions are separate: AP would use the current cohort queue to decide which records need review and where to route them; finance would use the arrival KPI to diagnose upstream PO-evidence conditions. These are assumed roles, not findings from field discovery. Later queue handling cannot improve an invoice's original arrival condition, so the primary KPI cannot measure that handling's benefit. Success demonstrated here is technical: correct, traceable, repeatable results and visible failures, not a reduced KPI or an operational outcome.

## Run locally

Use **Python 3.9 or later**, with its standard-library `sqlite3` module. No installation, API key, package download or network connection is required. Run these commands from this repository's root:

```sh
python3 --version
python3 run.py run
python3 run.py verify
python3 -m unittest discover -s tests -v
```

The first command after the version check prints `SUCCESS`, the run directory and the path to `report.html`. Open that HTML file locally in a browser. The report is self-contained. `verify` checks the saved raw and business-artifact hashes; the test suite should report **51 tests, OK**.

The supplied inputs already exist; `run` never generates them. To create a fresh synthetic fixture in a new directory:

```sh
python3 run.py generate --sources demo/sources --seed 20260918
python3 run.py run --sources demo/sources --artifacts demo/artifacts
python3 run.py verify --artifacts demo/artifacts
```

Generation refuses to replace existing input files unless `--force` is explicitly supplied. The seed changes ordinary examples deterministically; the 40 named scenarios stay fixed. The three supported subcommands are `generate`, `run` and `verify`.

## Supplied result

The receipt cohort runs from **1 August 2026 00:00 UTC to 31 August 2026 18:00 UTC**, including both endpoints. The cutoff is also the time of the current assessment. The queue and supporting exception measures cover only this selected arrival cohort, not the whole AP backlog. The [saved report](artifacts/runs/01751fcc02b6294b34f3/report.html) and [machine-readable metrics](artifacts/runs/01751fcc02b6294b34f3/metrics.json) contain:

| Measure | Result | Interpretation |
| --- | --- | --- |
| **Primary: confirmed arrival exception rate** | **37 / 79 = 46.84%** | Assessable means READY or EXCEPTION; 11 UNKNOWN records are outside this denominator. |
| Current open confirmed exceptions, by reason | 28 total | One exclusive reason per invoice; breakdown in the report. |
| Gross value of those exceptions | £42,454.05 | Invoice value, not unpaid value or loss. |
| Median invoice age for those exceptions | 21.33 days | Receipt to cutoff, not exception duration. |
| Department routing-role coverage for those exceptions | 23 / 28 = 82.14% | For five AP triage cases, AP must establish and confirm the responsible role before the reason-specific action; a listed role is not accepted ownership. |
| Arrival assessment coverage | 79 / 90 = 87.78% | All 90 eligible canonical records form this denominator, including 11 UNKNOWN. |

Quality controls reconcile **102 raw invoice rows = 97 canonical + 1 exact duplicate removed + 4 quarantined**. Seven canonical records are excluded by date, document type, currency or declared category. The 37-row review queue also includes uncertain cases, so it is larger than the 28 confirmed open exceptions.

## Evidence and outputs

[`artifacts/latest.json`](artifacts/latest.json) locates the last successful run; [`artifacts/last_attempt.json`](artifacts/last_attempt.json) records whether the most recent attempt succeeded. Within each run:

| File | Purpose |
| --- | --- |
| `report.html`, `metrics.json` | Readable results and exact metric definitions/values. |
| `invoice_trace.csv`, `review_queue.csv` | Original/current decisions, evidence IDs, routing and proposed actions. |
| `model.sqlite` | Canonical entities, events, interactions and one assessment per invoice. |
| `raw/`, `retrieval.json` | Preserved source bytes, hashes, actual SQL queries and source counts. |
| `quality_profile.json`, `quality_issues.csv`, `normalizations.csv` | Before/after profiles, quarantine reasons and logged safe fixes. |
| `artifact_manifest.json`, `run.jsonl` | Run identity, output hashes and stage log. |

The [two-page submission PDF](output/pdf/10222_Mohit_Kumar.pdf) gives the problem brief and implementation evidence. The [methods](docs/methods.md) explain source authority, relationships, temporal rules and failure handling. The [own-voice recording kit](docs/recording-kit.md), [timed cue sheet](docs/walkthrough.md) and [speaking notes](docs/demo-script.md) prepare the five-minute demo; no video has been recorded yet. The [evidence ledger](research/evidence-ledger.md) records public sources and their limits. A bounded [practitioner scan](research/practitioner-scan.md) adds intake/completeness questions without inferring demand. The [existing-tool check](research/existing-tools.md) and [proposed discovery plan](docs/discovery-plan.md) explain what would need validation before a real trial; the [data contract](docs/data-contract.md) specifies the fields and rules. The [verification record](docs/verification.md) maps the assignment requirements to artifacts and explains the passing 51-test suite and **40 separately specified named scenarios**.

**READY means only that the declared PO header evidence checks passed.** Remaining order value, quantities, receipt of goods/services, disputes, tax, invoice approval and payment are outside scope. A closed AP case does not mean paid. Recommendations are unexecuted; the pipeline sends no messages and authorises no payment.
