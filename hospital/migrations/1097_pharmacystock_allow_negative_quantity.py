# Allow negative quantity_on_hand for PharmacyStock when dispensed without stock
# (accountability - record shortfalls until restocked)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1096_imaging_image_filefield_dicom'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pharmacystock',
            name='quantity_on_hand',
            field=models.IntegerField(default=0, help_text='Can be negative when dispensed without stock (shortfall)'),
        ),
    ]
