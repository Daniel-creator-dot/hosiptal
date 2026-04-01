# Generated manually for Drug Accountability System

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1057_add_direct_chat_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='DrugReturn',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('return_number', models.CharField(db_index=True, max_length=50, unique=True)),
                ('return_date', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('batch_number', models.CharField(blank=True, db_index=True, max_length=50)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('quantity_returned', models.PositiveIntegerField()),
                ('quantity_original', models.PositiveIntegerField(help_text='Original quantity dispensed')),
                ('return_reason', models.CharField(choices=[('mistakenly_dispensed', 'Mistakenly Dispensed'), ('unpaid', 'Unpaid - Patient Could Not Pay'), ('patient_refused', 'Patient Refused Medication'), ('wrong_drug', 'Wrong Drug Dispensed'), ('expired_drug', 'Expired Drug Found'), ('damaged', 'Damaged Drug'), ('over_dispensed', 'Over Dispensed Quantity'), ('prescription_cancelled', 'Prescription Cancelled'), ('patient_discharged', 'Patient Discharged Before Administration'), ('other', 'Other (Specify in Notes)')], max_length=50)),
                ('reason_details', models.TextField(blank=True, help_text='Detailed reason for return')),
                ('original_unit_price', models.DecimalField(decimal_places=2, help_text='Price at time of dispensing', max_digits=10)),
                ('refund_amount', models.DecimalField(decimal_places=2, default=0, help_text='Amount to refund to patient', max_digits=10)),
                ('return_to_inventory', models.BooleanField(default=True, help_text='Return drug to inventory stock')),
                ('status', models.CharField(choices=[('pending', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('completed', 'Completed - Returned to Inventory'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=20)),
                ('requested_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('approval_notes', models.TextField(blank=True)),
                ('rejected_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('condition_on_return', models.CharField(choices=[('good', 'Good Condition'), ('damaged', 'Damaged'), ('expired', 'Expired'), ('opened', 'Opened Package'), ('sealed', 'Sealed/Unopened')], default='sealed', max_length=50)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_drug_returns', to='hospital.staff')),
                ('dispensing_record', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='drug_returns', to='hospital.pharmacydispensing')),
                ('drug', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to='hospital.drug')),
                ('inventory_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drug_returns', to='hospital.inventoryitem')),
                ('inventory_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drug_return', to='hospital.inventorytransaction')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='drug_returns', to='hospital.patient')),
                ('prescription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='drug_returns', to='hospital.prescription')),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_drug_returns', to='hospital.staff')),
                ('rejected_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rejected_drug_returns', to='hospital.staff')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='requested_drug_returns', to='hospital.staff')),
                ('store', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='drug_returns', to='hospital.store')),
            ],
            options={
                'verbose_name': 'Drug Return',
                'verbose_name_plural': 'Drug Returns',
                'ordering': ['-return_date', '-created'],
            },
        ),
        migrations.CreateModel(
            name='DrugAdministrationInventory',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('batch_number', models.CharField(blank=True, db_index=True, max_length=50)),
                ('quantity_administered', models.PositiveIntegerField(help_text='Quantity of drug units administered')),
                ('unit_cost', models.DecimalField(decimal_places=2, help_text='Cost per unit at time of administration', max_digits=10)),
                ('total_cost', models.DecimalField(decimal_places=2, help_text='Total cost of administered drug', max_digits=10)),
                ('administered_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('ward', models.CharField(blank=True, help_text='Ward/location where drug was administered', max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('administered_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='drug_administrations', to='hospital.staff')),
                ('drug', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='administration_inventory', to='hospital.drug')),
                ('inventory_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='administrations', to='hospital.inventoryitem')),
                ('inventory_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drug_administration', to='hospital.inventorytransaction')),
                ('mar_record', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_tracking', to='hospital.medicationadministrationrecord')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='drug_administrations', to='hospital.patient')),
                ('prescription', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='administration_inventory', to='hospital.prescription')),
                ('store', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='drug_administrations', to='hospital.store')),
            ],
            options={
                'verbose_name': 'Drug Administration Inventory',
                'verbose_name_plural': 'Drug Administration Inventory Records',
                'ordering': ['-administered_at'],
            },
        ),
        migrations.CreateModel(
            name='InventoryHistorySummary',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('period_start', models.DateField(db_index=True)),
                ('period_end', models.DateField(db_index=True)),
                ('opening_balance', models.IntegerField(default=0)),
                ('receipts', models.IntegerField(default=0)),
                ('issues', models.IntegerField(default=0)),
                ('transfers_in', models.IntegerField(default=0)),
                ('transfers_out', models.IntegerField(default=0)),
                ('returns', models.IntegerField(default=0)),
                ('adjustments', models.IntegerField(default=0)),
                ('closing_balance', models.IntegerField(default=0)),
                ('opening_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('receipts_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('issues_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('closing_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('transaction_count', models.PositiveIntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history_summaries', to='hospital.inventoryitem')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history_summaries', to='hospital.store')),
            ],
            options={
                'verbose_name': 'Inventory History Summary',
                'verbose_name_plural': 'Inventory History Summaries',
                'ordering': ['-period_start', 'inventory_item'],
                'unique_together': {('inventory_item', 'period_start', 'period_end')},
            },
        ),
        migrations.AddIndex(
            model_name='drugreturn',
            index=models.Index(fields=['-return_date', 'status'], name='hospital_dr_return_d_status_idx'),
        ),
        migrations.AddIndex(
            model_name='drugreturn',
            index=models.Index(fields=['patient', '-return_date'], name='hospital_dr_patient__return_d_idx'),
        ),
        migrations.AddIndex(
            model_name='drugreturn',
            index=models.Index(fields=['drug', '-return_date'], name='hospital_dr_drug_id_return_d_idx'),
        ),
        migrations.AddIndex(
            model_name='drugreturn',
            index=models.Index(fields=['status', '-return_date'], name='hospital_dr_status_return_d_idx'),
        ),
        migrations.AddIndex(
            model_name='drugadministrationinventory',
            index=models.Index(fields=['-administered_at', 'patient'], name='hospital_dr_administered_patient_idx'),
        ),
        migrations.AddIndex(
            model_name='drugadministrationinventory',
            index=models.Index(fields=['drug', '-administered_at'], name='hospital_dr_drug_id_administered_idx'),
        ),
        migrations.AddIndex(
            model_name='drugadministrationinventory',
            index=models.Index(fields=['batch_number'], name='hospital_dr_batch_nu_idx'),
        ),
        migrations.AddIndex(
            model_name='inventoryhistorysummary',
            index=models.Index(fields=['-period_start', 'store'], name='hospital_in_period__store_idx'),
        ),
        migrations.AddIndex(
            model_name='inventoryhistorysummary',
            index=models.Index(fields=['inventory_item', '-period_start'], name='hospital_in_inventor_period__idx'),
        ),
    ]







