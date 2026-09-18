#!/usr/bin/env python3
"""Read one verified synthetic invoice trace for the demonstration."""

import argparse
import csv
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from po_review.pipeline import verify_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('invoice_id')
    args = parser.parse_args()
    latest = json.loads((ROOT / 'artifacts/latest.json').read_text())
    run = ROOT / 'artifacts' / latest['path']
    verify_run(run)
    with (run / 'invoice_trace.csv').open(newline='') as stream:
        row = next((r for r in csv.DictReader(stream) if r['invoice_id'] == args.invoice_id), None)
    if row is None:
        parser.error('Invoice ID not found in the verified canonical trace.')
    print('SYNTHETIC CASE:', row['invoice_id'])
    print('Verified run:', latest['run_id'])
    for label, key in [('Invoice arrived', 'received_at'), ('Original PO', 'original_po_id'),
                       ('Current PO', 'current_po_id'), ('Arrival state', 'arrival_status'),
                       ('Arrival reason', 'arrival_reason'), ('Current state', 'current_status'),
                       ('Current reason', 'current_reason'), ('AP case', 'case_state'),
                       ('Department role', 'owner_role'), ('Route', 'routing')]:
        print('{:18} {}'.format(label + ':', row[key] or '(blank)'))
    print('Next action:', row['proposed_action'])
    print('\nCase events in the model:')
    with sqlite3.connect((run / 'model.sqlite').as_uri() + '?mode=ro', uri=True) as connection:
        events = connection.execute('SELECT event_id,event_type,effective_at,recorded_at FROM case_events WHERE invoice_id=? ORDER BY effective_at,event_id', (args.invoice_id,)).fetchall()
    for event_id, event_type, effective, recorded in events:
        print(' ', event_id, event_type)
        print('   effective:', effective, '| recorded:', recorded)
    if not events:
        print('  No canonical case events.')
    print('\nPO header evidence is not payment approval.')


if __name__ == '__main__':
    main()
