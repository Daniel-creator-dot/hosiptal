from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1144_labtest_imagingcatalog_nhis_covered'),
    ]

    operations = [
        migrations.AddField(
            model_name='labreagent',
            name='deduct_per_lab_visit',
            field=models.BooleanField(
                default=False,
                help_text='Deduct once for each patient who comes to the lab (e.g. EDTA tube), not once per test.',
            ),
        ),
        migrations.AddField(
            model_name='labreagent',
            name='qty_per_lab_visit',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('1'),
                help_text='Quantity to deduct for each lab patient when deduct_per_lab_visit is set.',
                max_digits=10,
            ),
        ),
    ]
