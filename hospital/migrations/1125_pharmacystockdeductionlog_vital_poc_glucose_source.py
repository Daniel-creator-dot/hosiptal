# Generated manually: add vital_poc_glucose source for POC glucose strip stock deductions

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1124_insurancereceivableentry_invoice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pharmacystockdeductionlog',
            name='source_type',
            field=models.CharField(
                choices=[
                    ('dispense_history', 'Dispense history row'),
                    ('pharmacy_dispensing', 'Pharmacy dispensing record (API / no history)'),
                    ('walkin_sale_item', 'Walk-in prescribe sale line'),
                    ('vital_poc_glucose', 'Nurse vitals POC glucose strip'),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
