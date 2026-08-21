# Generated manually for SupplierStockReceiptCorrectionRequest

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
import model_utils.fields
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hospital', '1140_pharmacystock_supplier_invoice_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupplierStockReceiptCorrectionRequest',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('pending', 'Pending approval'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='pending', max_length=16)),
                ('proposed_quantity', models.PositiveIntegerField()),
                ('proposed_unit_cost', models.DecimalField(decimal_places=4, max_digits=15)),
                ('proposed_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('current_quantity', models.PositiveIntegerField()),
                ('current_unit_cost', models.DecimalField(decimal_places=4, max_digits=15)),
                ('current_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_note', models.CharField(blank=True, max_length=200)),
                ('payable_line', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='correction_requests', to='hospital.supplierpayableline')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_receipt_corrections_requested', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_receipt_corrections_reviewed', to=settings.AUTH_USER_MODEL)),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_receipt_correction_requests', to='hospital.supplier')),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.AddIndex(
            model_name='supplierstockreceiptcorrectionrequest',
            index=models.Index(fields=['supplier', 'status', 'is_deleted'], name='hospital_su_supplie_corr_idx'),
        ),
        migrations.AddIndex(
            model_name='supplierstockreceiptcorrectionrequest',
            index=models.Index(fields=['payable_line', 'status', 'is_deleted'], name='hospital_su_payable_corr_idx'),
        ),
    ]
