from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1134_account_subgroup'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='clinical_indication',
            field=models.TextField(
                blank=True,
                help_text='Diagnosis / clinical reason sent with the order (visible to laboratory).',
            ),
        ),
    ]
