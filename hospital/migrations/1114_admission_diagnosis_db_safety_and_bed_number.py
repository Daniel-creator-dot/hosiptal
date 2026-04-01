# Widen diagnosis_icd10 if DB still has varchar(10); widen bed_number for long labels.

from django.db import migrations, models


def widen_admission_diagnosis_if_needed(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != 'postgresql':
        return
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hospital_admission'
              AND column_name = 'diagnosis_icd10'
            """
        )
        row = cursor.fetchone()
        if row and row[0] is not None and row[0] < 255:
            cursor.execute(
                'ALTER TABLE hospital_admission ALTER COLUMN diagnosis_icd10 TYPE VARCHAR(255)'
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1113_admission_diagnosis_icd10_max_length'),
    ]

    operations = [
        migrations.RunPython(widen_admission_diagnosis_if_needed, noop_reverse),
        migrations.AlterField(
            model_name='bed',
            name='bed_number',
            field=models.CharField(max_length=50),
        ),
    ]
