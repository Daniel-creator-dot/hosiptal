from django.db import migrations, models


def backfill_initial_quantity(apps, schema_editor):
    PharmacyStock = apps.get_model('hospital', 'PharmacyStock')
    for stock in PharmacyStock.objects.all().iterator():
        if not stock.initial_quantity:
            stock.initial_quantity = stock.quantity_on_hand or 0
            stock.save(update_fields=['initial_quantity'])


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1110_accountingpayroll_deduction_percentages'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacystock',
            name='initial_quantity',
            field=models.IntegerField(
                default=0,
                help_text='Initial quantity added for this batch (before any dispensing)',
            ),
        ),
        migrations.RunPython(backfill_initial_quantity, migrations.RunPython.noop),
    ]

