# Add stock_reduced_at to PharmacyDispensing (set when stock reduced at Send to Payer)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1105_pharmacystock_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacydispensing',
            name='stock_reduced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
