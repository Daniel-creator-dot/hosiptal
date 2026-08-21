from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1143_labtest_insurance_exclusion_companies'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtest',
            name='nhis_covered',
            field=models.BooleanField(
                default=False,
                help_text='When set, this lab test is on the NHIS panel and can be ordered for NHIS patients without cash pay',
            ),
        ),
        migrations.AddField(
            model_name='imagingcatalog',
            name='nhis_covered',
            field=models.BooleanField(
                default=False,
                help_text='When set, this scan is on the NHIS list and can be ordered for NHIS patients without cash pay',
            ),
        ),
        migrations.AddIndex(
            model_name='labtest',
            index=models.Index(fields=['is_active', 'nhis_covered'], name='hospital_lb_is_acti_nhis_idx'),
        ),
    ]
