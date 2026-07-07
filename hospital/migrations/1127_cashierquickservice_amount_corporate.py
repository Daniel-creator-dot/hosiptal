# Generated manually for HMS cashier price book

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1126_vitalsign_poc_glucose_strip_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashierquickservice',
            name='amount_corporate',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Corporate / company scheme price. Leave blank to use the insurance amount for corporate patients (legacy behaviour).',
                max_digits=10,
                null=True,
            ),
        ),
    ]
