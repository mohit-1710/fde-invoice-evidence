# Verification record

Verified on 18 September 2026. This record concerns the supplied synthetic fixture and declared rules, not operational performance at BHT.

## What was checked

- **51 automated tests passed.** The suite covers source generation, temporal decisions, invoice-grain aggregation, validation, and failure/publication behaviour.
- **40 named scenarios matched their separate expected results.** The expectations in `data/scenario_expectations.json` are specified separately from the classifier and are never pipeline inputs. This checks known cases, not accuracy on a representative real dataset.
- **Repeated runs reproduced the same business artifacts.** `docs/reproducible-run.json` preserves the actual CLI commands and results. `artifacts/latest.json` selects the run; its manifest records the input and output hashes.
- **A rejected input did not replace a successful result.** `docs/failure-demonstration.json` records an executed demonstration: alter a temporary CSV without changing its declared hash, observe exit 2 and FAILED, verify the previous successful run, restore the CSV, and reproduce the same run ID. Rejected raw bytes are retained. The original sources are not altered.

## Assignment evidence map

| Required area | Evidence to inspect |
| --- | --- |
| Stakeholders and framing | PDF page 1; `docs/problem-reasoning.md`. Roles and goals are assumptions, with no invented interviews. |
| Workflow and problem | PDF workflow and priority/reversal reasoning; primary source URLs in `research/evidence-ledger.md`. |
| KPI and scope | PDF; `docs/methods.md`; saved `metrics.json` definitions. One primary diagnostic KPI and five supports. |
| Data and source authority | `docs/data-contract.md`, `docs/methods.md`, `data/sources/export_manifest.json`. |
| Two-source retrieval | `src/po_review/pipeline.py`; saved `retrieval.json` SQL queries and CSV provenance; untouched `raw/` files. |
| Profiling and cleaning | `quality_profile.json`, `quality_issues.csv`, `normalizations.csv`; row reconciliations and reason codes. |
| Workflow model and metrics | `model.sqlite` entities/events/interactions and invoice assessments; `invoice_trace.csv`; SQL aggregations in `model.py`. |
| Dependable pipeline | Stage logs, manifests, repeated-run transcript, failure demonstration, and tests. |

## Reproduce the checks

```sh
python3 -m unittest discover -s tests -v
python3 run.py run
python3 run.py run
python3 run.py verify
python3 tools/demonstrate_failure.py
```

The two pipeline runs should select the same run ID with unchanged code, inputs and cutoff. Logs and attempt timestamps may differ. `verify` checks the saved expected file inventories and hashes; it does not independently authenticate the source system. Read `last_attempt.json` as well as `latest.json`, because a verified old result can coexist with a failed newer attempt.

These are local, single-user prototype guarantees for the tested handled failures. They do not cover every possible operating-system crash, concurrent writer or enterprise deployment condition. No stakeholder acceptance, time savings, payment benefit or usefulness beyond existing tools has been established.
