from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1128_invoice_nonpatient_and_receipt_patient_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='CashierChargeBundle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bundle_code', models.CharField(db_index=True, help_text='Unique identifier (e.g. PRIME-PACK-ANC). Used for upsert on import.', max_length=80, unique=True)),
                ('label', models.CharField(help_text='Display name in search and browse', max_length=200)),
                ('lines', models.JSONField(default=list, help_text='Ordered line items; each row needs billing_code, description, amount_cash.')),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Cashier charge bundle',
                'verbose_name_plural': 'Cashier charge bundles',
                'db_table': 'hospital_cashier_charge_bundle',
                'ordering': ['sort_order', 'label'],
            },
        ),
    ]
