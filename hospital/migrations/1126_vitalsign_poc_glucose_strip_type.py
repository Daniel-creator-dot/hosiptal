# Generated manually for POC glucose strip type on vitals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1125_pharmacystockdeductionlog_vital_poc_glucose_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='vitalsign',
            name='poc_glucose_strip_type',
            field=models.CharField(
                blank=True,
                choices=[('', 'Not specified'), ('rbs', 'RBS (random blood sugar)'), ('fbs', 'FBS (fasting blood sugar)')],
                db_index=True,
                default='',
                help_text='When set at vitals, labels bedside glucose as RBS or FBS for consultation display and billing context.',
                max_length=8,
                verbose_name='POC glucose strip type',
            ),
        ),
    ]
