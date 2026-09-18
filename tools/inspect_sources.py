#!/usr/bin/env python3
"""Display actual source-retrieval and quality evidence from the verified run."""

import csv
import json
from pathlib import Path
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from po_review.pipeline import verify_run


def main():
    latest = json.loads((ROOT / 'artifacts/latest.json').read_text())
    run = ROOT / 'artifacts' / latest['path']
    verify_run(run)
    retrieval = json.loads((run / 'retrieval.json').read_text())
    print('SYNTHETIC SOURCES | verified run:', latest['run_id'])
    print('\nPreserved raw exports (hashes verified):')
    for name in sorted(retrieval['raw_hashes']):
        print('  {} ({} bytes)'.format(name, (run / 'raw' / name).stat().st_size))
    print('\nRecorded retrieval counts:')
    print(textwrap.fill(', '.join('{}: {}'.format(k, v) for k, v in retrieval['row_counts'].items()), width=90))
    print('\nOne actual retrieval query (procurement SQLite):')
    print(textwrap.fill(retrieval['sql_queries']['purchase_orders'], width=90))
    print('\nOne logged safe normalisation:')
    with (run / 'normalizations.csv').open(newline='') as stream:
        normal = next((row for row in csv.DictReader(stream)
                       if row['source'] == 'invoices' and row['field'] == 'currency'), None)
    if normal is None:
        print('  No invoice-currency normalisation in this run.')
    else:
        print('  {} | {}: {!r} -> {!r}'.format(normal['record_id'], normal['field'], normal['before'], normal['after']))
    print('\nOne recorded invoice-quality issue:')
    with (run / 'quality_issues.csv').open(newline='') as stream:
        issue = next((row for row in csv.DictReader(stream)
                      if row['source'] == 'invoices' and row['severity'] == 'QUARANTINE'), None)
    if issue is None:
        print('  No quarantined invoice issue in this run.')
    else:
        print('  {} | source row {} | {}'.format(issue['record_id'], issue['source_row'], issue['severity']))
        print('  {}: {}'.format(issue['rule'], issue['detail']))
    print('\nRead from retrieval.json, raw files, normalizations.csv and quality_issues.csv.')
    print('Complete provenance and quality logs remain in the saved run.')


if __name__ == '__main__':
    main()
