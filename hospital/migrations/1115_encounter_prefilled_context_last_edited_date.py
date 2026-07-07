# Generated manually for prefilled-context edit lock

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1114_admission_diagnosis_db_safety_and_bed_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='encounter',
            name='prefilled_context_last_edited_date',
            field=models.DateField(
                blank=True,
                help_text='Local calendar date when the doctor last saved edits to the prefilled (triage/history) block; further edits until the next day are disabled.',
                null=True,
            ),
        ),
    ]
