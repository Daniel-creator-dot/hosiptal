# Generated for fix: TransactionManagementError due to duplicate empty entry_number

from django.db import migrations


def backfill_empty_entry_numbers(apps, schema_editor):
    """Set a unique entry_number for any InsuranceReceivableEntry with empty entry_number."""
    InsuranceReceivableEntry = apps.get_model("hospital", "InsuranceReceivableEntry")
    from datetime import datetime

    empty_entries = list(InsuranceReceivableEntry.objects.filter(entry_number=""))
    for i, entry in enumerate(empty_entries):
        # Use timestamp + index so each row gets a unique value in one pass
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        candidate = f"IRE{ts}{i:06d}"
        entry.entry_number = candidate
        entry.save(update_fields=["entry_number"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hospital", "1106_pharmacydispensing_stock_reduced_at"),
    ]

    operations = [
        migrations.RunPython(backfill_empty_entry_numbers, noop),
    ]
