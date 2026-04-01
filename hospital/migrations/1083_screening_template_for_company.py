# Generated manually for company-specific screening templates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1082_add_screening_pre_employment_pre_admission'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningchecktemplate',
            name='for_company',
            field=models.CharField(
                blank=True,
                help_text='Specific company or institution name. Leave blank for general institutional use.',
                max_length=255,
                default=''
            ),
        ),
    ]
