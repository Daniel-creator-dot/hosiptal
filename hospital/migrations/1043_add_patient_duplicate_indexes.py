# Generated manually for duplicate prevention
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1042_remove_batchrecall_completed_by_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['first_name', 'last_name', 'date_of_birth'], name='patient_name_dob_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['first_name', 'last_name', 'phone_number'], name='patient_name_phone_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['email'], name='patient_email_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['national_id'], name='patient_national_id_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['phone_number'], name='patient_phone_idx'),
        ),
    ]

