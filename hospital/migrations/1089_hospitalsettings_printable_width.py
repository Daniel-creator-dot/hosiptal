# Add printable width for POS receipt (avoids right side cut off on thermal printers)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1088_hospitalsettings_printer_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_printable_width_mm',
            field=models.PositiveSmallIntegerField(
                default=72,
                help_text='Printable area width in mm. Use 72 for 80mm paper (avoids right side cut off), 48 for 58mm.'
            ),
        ),
    ]
