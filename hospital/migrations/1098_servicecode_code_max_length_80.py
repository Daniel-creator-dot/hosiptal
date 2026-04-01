# Support DRUG-<uuid> and other long service codes (varchar(20) was too short)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1097_pharmacystock_allow_negative_quantity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicecode',
            name='code',
            field=models.CharField(max_length=80, unique=True),
        ),
    ]
