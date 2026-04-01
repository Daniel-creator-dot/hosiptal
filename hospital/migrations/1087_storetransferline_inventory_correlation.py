# Generated manually for store transfer line inventory correlation

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1086_ensure_undepositedfunds_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='storetransferline',
            name='from_inventory_item',
            field=models.ForeignKey(
                blank=True,
                help_text='Source inventory item; used for exact quantity deduction.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transfer_lines_as_source',
                to='hospital.inventoryitem',
            ),
        ),
        migrations.AddField(
            model_name='storetransferline',
            name='to_inventory_item',
            field=models.ForeignKey(
                blank=True,
                help_text='Destination inventory item after completion.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transfer_lines_as_dest',
                to='hospital.inventoryitem',
            ),
        ),
    ]
