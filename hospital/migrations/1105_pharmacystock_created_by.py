# Add created_by to PharmacyStock so account can see who (e.g. store manager) added each stock

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hospital', '1104_patient_notes_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacystock',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                editable=False,
                help_text='User (e.g. store manager) who added this stock – visible to account for monitoring',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pharmacy_stock_added',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
