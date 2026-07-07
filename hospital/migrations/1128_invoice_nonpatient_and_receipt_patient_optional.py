from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1127_cashierquickservice_amount_corporate'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='counterparty_name',
            field=models.CharField(blank=True, default='', max_length=255, help_text='Who is being billed when there is no patient (e.g. supplier name).'),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='patient',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='invoices',
                to='hospital.patient',
            ),
        ),
        migrations.AlterField(
            model_name='paymentreceipt',
            name='patient',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='receipts',
                to='hospital.patient',
            ),
        ),
    ]
