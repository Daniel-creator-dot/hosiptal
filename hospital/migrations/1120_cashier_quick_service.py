# Admin-managed cashier add-services catalog (supplements built-in list in code)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1119_cashiersession_deposit_received_total'),
    ]

    operations = [
        migrations.CreateModel(
            name='CashierQuickService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('billing_code', models.CharField(db_index=True, help_text='Unique code on the invoice (e.g. EAR-WASH). Letters, numbers, hyphen.', max_length=80, unique=True)),
                ('label', models.CharField(help_text='Name cashiers and patients see', max_length=200)),
                ('amount_cash', models.DecimalField(decimal_places=2, max_digits=10)),
                ('amount_insurance', models.DecimalField(blank=True, decimal_places=2, help_text='Leave blank to use the same amount as cash', max_digits=10, null=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Cashier quick service',
                'verbose_name_plural': 'Cashier quick services',
                'db_table': 'hospital_cashier_quick_service',
                'ordering': ['sort_order', 'label'],
            },
        ),
    ]
