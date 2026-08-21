# Generated manually for PharmacyStock.supplier_invoice_number

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1139_aiclinicalchatmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacystock',
            name='supplier_invoice_number',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Supplier invoice # for this batch — used on supplier accounts when recording payment',
                max_length=120,
            ),
        ),
    ]
