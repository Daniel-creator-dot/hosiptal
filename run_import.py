#!/usr/bin/env python
"""Wrapper to run import command with proper encoding"""
import os
import sys

# Force UTF-8 encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
os.environ['PYTHONUNBUFFERED'] = '1'

import django
django.setup()

from django.core.management import call_command

try:
    call_command(
        'import_legacy_patients',
        '--sql-dir', 'import\\legacy',
        '--patients-only',
        '--limit', '1'
    )
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
