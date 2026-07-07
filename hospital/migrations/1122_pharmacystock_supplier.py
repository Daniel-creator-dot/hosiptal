# Generated manually for PharmacyStock.supplier

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1121_drug_preferred_supplier'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacystock',
            name='supplier',
            field=models.ForeignKey(
                blank=True,
                help_text='Vendor this batch was received from (optional; for accounts / procurement)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pharmacy_stock_batches',
                to='hospital.supplier',
            ),
        ),
    ]
