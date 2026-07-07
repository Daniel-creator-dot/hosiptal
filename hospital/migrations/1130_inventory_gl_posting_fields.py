# Generated for perpetual inventory GL posting

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1129_cashier_charge_bundle'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacystockdeductionlog',
            name='cogs_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='FIFO cost of units deducted (for GL COGS posting)',
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='pharmacystockdeductionlog',
            name='cogs_posted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pharmacystockdeductionlog',
            name='gl_journal_entry',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pharmacy_stock_deduction_logs',
                to='hospital.advancedjournalentry',
            ),
        ),
        migrations.AddField(
            model_name='reagenttransaction',
            name='cogs_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Cost of reagent units consumed (for GL COGS posting)',
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='reagenttransaction',
            name='cogs_posted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reagenttransaction',
            name='gl_journal_entry',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reagent_transactions',
                to='hospital.advancedjournalentry',
            ),
        ),
    ]
