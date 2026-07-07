"""Audit {% url %} names in templates and report NoReverseMatch failures."""
import os
import re
import sys
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.urls import NoReverseMatch, reverse

BASE = Path(__file__).resolve().parent.parent
url_pattern = re.compile(r"""{%\s*url\s+['\"]([^'\"]+)['\"]""")

names = {}
for root in [BASE / 'hospital' / 'templates', BASE / 'hms' / 'templates']:
    if not root.exists():
        continue
    for fp in root.rglob('*.html'):
        try:
            text = fp.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for m in url_pattern.finditer(text):
            name = m.group(1).strip()
            if name.startswith('admin:'):
                continue
            rel = str(fp.relative_to(BASE))
            names.setdefault(name, set()).add(rel)

DUMMY_KWARGS = {
    'pk': '00000000-0000-0000-0000-000000000001',
    'patient_id': '00000000-0000-0000-0000-000000000001',
    'result_id': '00000000-0000-0000-0000-000000000001',
    'entry_id': '00000000-0000-0000-0000-000000000001',
    'payer_id': '00000000-0000-0000-0000-000000000001',
    'service_id': '00000000-0000-0000-0000-000000000001',
    'service_type': 'invoice',
    'encounter_id': '00000000-0000-0000-0000-000000000001',
    'receipt_id': '00000000-0000-0000-0000-000000000001',
    'year': '2026',
    'month': '1',
    'supplier_id': '00000000-0000-0000-0000-000000000001',
    'account_id': '00000000-0000-0000-0000-000000000001',
    'payment_id': '00000000-0000-0000-0000-000000000001',
    'drug_id': '00000000-0000-0000-0000-000000000001',
    'order_id': '00000000-0000-0000-0000-000000000001',
    'prescription_id': '00000000-0000-0000-0000-000000000001',
    'lab_result_id': '00000000-0000-0000-0000-000000000001',
    'invoice_id': '00000000-0000-0000-0000-000000000001',
    'id': '00000000-0000-0000-0000-000000000001',
    'admission_id': '00000000-0000-0000-0000-000000000001',
    'deposit_id': '00000000-0000-0000-0000-000000000001',
    'document_id': '00000000-0000-0000-0000-000000000001',
    'month_key': '2026-01',
    'line_id': '00000000-0000-0000-0000-000000000001',
    'staff_id': '00000000-0000-0000-0000-000000000001',
    'template_id': '00000000-0000-0000-0000-000000000001',
}

def try_reverse(name):
    """Try reverse with no args, then common dummy kwargs."""
    attempts = [
        lambda: reverse(name),
        lambda: reverse(name, args=['00000000-0000-0000-0000-000000000001']),
        lambda: reverse(name, args=['2026', '1']),
        lambda: reverse(name, kwargs=DUMMY_KWARGS),
    ]
    last_exc = None
    for attempt in attempts:
        try:
            attempt()
            return None
        except NoReverseMatch as exc:
            last_exc = exc
    return last_exc


failures = []
for name in sorted(names):
    exc = try_reverse(name)
    if exc is not None:
        failures.append((name, str(exc)[:140], sorted(names[name])[0]))

print(f'TOTAL unique url names: {len(names)}')
print(f'FAILURES: {len(failures)}')
for name, err, tpl in failures:
    print(f'  {name}')
    print(f'    template: {tpl}')
    print(f'    error: {err}')

sys.exit(1 if failures else 0)
