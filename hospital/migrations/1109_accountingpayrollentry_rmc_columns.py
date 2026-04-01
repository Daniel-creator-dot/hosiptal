# Generated manually for RMC salary sheet columns

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1108_accounting_payroll_rmc_breakdown'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='department_snapshot',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='medical_allowance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='personal_relief',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='pf_employer_contribution',
            field=models.DecimalField(
                decimal_places=2, default=0, help_text='5.0% PF employer (informational)', max_digits=15
            ),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='rank_snapshot',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='risk_emergency_allowance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='service_length_snapshot',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='sheet_serial',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='ssf_employer_contribution',
            field=models.DecimalField(
                decimal_places=2, default=0, help_text='13% SSF employer (informational)', max_digits=15
            ),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='taxable_income',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
        migrations.AddField(
            model_name='accountingpayrollentry',
            name='total_relief',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
        migrations.AlterField(
            model_name='accountingpayrollentry',
            name='other_allowances',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Other allowance / overtime (RMC column)',
                max_digits=15,
            ),
        ),
        migrations.AlterField(
            model_name='accountingpayrollentry',
            name='pension_employee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='5.0% PF employee',
                max_digits=15,
            ),
        ),
        migrations.AlterField(
            model_name='accountingpayrollentry',
            name='ssnit_employee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='5.5% SSF employee contribution',
                max_digits=15,
            ),
        ),
    ]
