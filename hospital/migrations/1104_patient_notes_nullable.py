# Fix: allow NULL on hospital_patient.notes to avoid not-null constraint on insert

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1103_add_patient_notes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='notes',
            field=models.TextField(blank=True, default='', null=True),
        ),
    ]
