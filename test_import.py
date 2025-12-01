#!/usr/bin/env python
"""Test script to debug import_legacy_patients command"""
import os
import sys
import traceback

# Force unbuffered output
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
os.environ['PYTHONUNBUFFERED'] = '1'

print("Script started", flush=True)
sys.stdout.flush()

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

try:
    print("Importing django...", flush=True)
    sys.stdout.flush()
    import django
    print("Setting up django...", flush=True)
    sys.stdout.flush()
    django.setup()
    print("Django setup successful", flush=True)
    sys.stdout.flush()
except Exception as e:
    print(f"Django setup failed: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from django.core.management import call_command
    from io import StringIO
    
    output = StringIO()
    error_output = StringIO()
    
    print("Calling command...", file=sys.stderr)
    sys.stderr.flush()
    
    call_command(
        'import_legacy_patients',
        '--sql-dir', 'import\\legacy',
        '--patients-only',
        '--limit', '1',
        stdout=output,
        stderr=error_output
    )
    
    print("Command completed", file=sys.stderr)
    sys.stderr.flush()
    
    output_str = output.getvalue()
    error_str = error_output.getvalue()
    
    print("=" * 60)
    print("STDOUT:")
    print("=" * 60)
    try:
        # Try to print with proper encoding
        if output_str:
            # Replace problematic Unicode characters
            safe_output = output_str.encode('ascii', 'replace').decode('ascii')
            print(safe_output)
        else:
            print("(empty)")
    except Exception as e:
        print(f"Error printing output: {e}")
        print(f"Output length: {len(output_str) if output_str else 0}")
        if output_str:
            print(repr(output_str[:500]))  # Show first 500 chars as repr
    
    print("\n" + "=" * 60)
    print("STDERR:")
    print("=" * 60)
    try:
        if error_str:
            safe_error = error_str.encode('ascii', 'replace').decode('ascii')
            print(safe_error)
        else:
            print("(empty)")
    except Exception as e:
        print(f"Error printing stderr: {e}")
        if error_str:
            print(repr(error_str[:500]))
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
