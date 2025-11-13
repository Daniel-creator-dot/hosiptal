# Generated manually on 2025-10-28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hospital", "0014_add_consultation_auto_billing"),
    ]

    operations = [
        migrations.AddField(
            model_name="encounter",
            name="current_activity",
            field=models.CharField(
                blank=True,
                null=True,
                help_text="Current department activity: Consulting, Lab, Pharmacy",
                max_length=50,
                default='',
            ),
        ),
    ]

