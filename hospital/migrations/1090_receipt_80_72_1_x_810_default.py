# Default receipt size: 80 (72.1) × 810 mm - printable width 72.1, length 810

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1089_hospitalsettings_printable_width'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hospitalsettings',
            name='pos_receipt_printable_width_mm',
            field=models.FloatField(
                default=72.1,
                help_text='Printable area width in mm. Default 72.1 for 80mm paper (avoids right side cut off).'
            ),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_length_mm',
            field=models.PositiveIntegerField(
                default=810,
                help_text='Receipt length in mm. Standard default 810 for 80×810mm thermal roll.'
            ),
        ),
    ]
