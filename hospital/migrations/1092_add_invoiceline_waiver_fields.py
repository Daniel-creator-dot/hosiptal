# Generated for cashier waiver feature - patients migrating from old system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hospital', '1091_add_pharmacy_dispensing_substitute_drug'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceline',
            name='waived_at',
            field=models.DateTimeField(blank=True, null=True, help_text='When this line was waived (e.g. patient from old system)'),
        ),
        migrations.AddField(
            model_name='invoiceline',
            name='waived_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='waived_invoice_lines', to=settings.AUTH_USER_MODEL, help_text='User (cashier) who waived this line'),
        ),
        migrations.AddField(
            model_name='invoiceline',
            name='waiver_reason',
            field=models.CharField(blank=True, max_length=255, help_text='Reason for waiver (e.g. Migrated from old system - already paid)'),
        ),
    ]
