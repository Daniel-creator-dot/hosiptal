# Generated manually for receivables allocation

from django.db import migrations, models
import django.db.models.deletion


def _ire_table_exists(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.hospital_insurancereceivableentry')")
        return cursor.fetchone()[0] is not None


def add_invoice_column_if_table_exists(apps, schema_editor):
    if not _ire_table_exists(schema_editor):
        return
    schema_editor.execute(
        """
        ALTER TABLE hospital_insurancereceivableentry
        ADD COLUMN IF NOT EXISTS invoice_id uuid NULL
        REFERENCES hospital_invoice(id) DEFERRABLE INITIALLY DEFERRED;
        """
    )
    schema_editor.execute(
        """
        CREATE INDEX IF NOT EXISTS hospital_insurancereceivableentry_invoice_id_idx
        ON hospital_insurancereceivableentry (invoice_id);
        """
    )


def backfill_ire_invoice(apps, schema_editor):
    if not _ire_table_exists(schema_editor):
        return
    InsuranceReceivableEntry = apps.get_model('hospital', 'InsuranceReceivableEntry')
    Invoice = apps.get_model('hospital', 'Invoice')
    for ire in InsuranceReceivableEntry.objects.filter(invoice_id__isnull=True).iterator():
        notes = ire.notes or ''
        inv_num = None
        if 'from invoice ' in notes:
            part = notes.split('from invoice ', 1)[1]
            inv_num = part.split(' for patient', 1)[0].strip()
        elif 'Auto-updated from invoice ' in notes:
            part = notes.split('Auto-updated from invoice ', 1)[1]
            inv_num = part.split(' for patient', 1)[0].strip()
        if not inv_num:
            continue
        inv = Invoice.objects.filter(
            invoice_number=inv_num,
            payer_id=ire.payer_id,
            is_deleted=False,
        ).first()
        if not inv:
            inv = Invoice.objects.filter(invoice_number=inv_num, is_deleted=False).first()
        if inv:
            ire.invoice_id = inv.id
            ire.save(update_fields=['invoice_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1123_supplier_payable_line'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='insurancereceivableentry',
                    name='invoice',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='Source invoice for allocation and reporting (set automatically from billing).',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='insurance_receivable_entries',
                        to='hospital.invoice',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_invoice_column_if_table_exists, migrations.RunPython.noop),
            ],
        ),
        migrations.RunPython(backfill_ire_invoice, migrations.RunPython.noop),
    ]
