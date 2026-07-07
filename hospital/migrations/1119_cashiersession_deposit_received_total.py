# Generated manually for cashier session deposit intake totals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1118_pharmacystockloss'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashiersession',
            name='deposit_received_total',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Patient deposit intake recorded this session (PatientDeposit), not deposit applied to bills',
                max_digits=12,
            ),
        ),
    ]
