from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1141_supplierstockreceiptcorrectionrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='drug',
            name='nhis_covered',
            field=models.BooleanField(
                default=False,
                help_text='When set, this drug is on the NHIS formulary and can be prescribed for NHIS patients',
            ),
        ),
        migrations.AddIndex(
            model_name='drug',
            index=models.Index(fields=['is_active', 'nhis_covered'], name='hospital_dr_is_acti_nhis_idx'),
        ),
    ]
