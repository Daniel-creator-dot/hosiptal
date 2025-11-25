# Manual migration to update StaffLeaveCounter fields
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '0043_add_new_hr_features'),
    ]

    operations = [
        # Rename existing fields
        migrations.RenameField(
            model_name='staffleavecounter',
            old_name='next_reset_date',
            new_name='next_leave_date',
        ),
        
        # Remove old fields that are no longer needed
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='annual_leave_total',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='annual_leave_used',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='annual_leave_pending',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='sick_leave_total',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='sick_leave_used',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='sick_leave_pending',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='casual_leave_total',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='casual_leave_used',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='casual_leave_pending',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='last_reset_date',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='enable_sms_alerts',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='low_balance_threshold',
        ),
        migrations.RemoveField(
            model_name='staffleavecounter',
            name='critical_balance_threshold',
        ),
        
        # Add new fields
        migrations.AddField(
            model_name='staffleavecounter',
            name='days_until_next_leave',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='staffleavecounter',
            name='next_leave_type',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='staffleavecounter',
            name='last_updated',
            field=models.DateTimeField(auto_now=True),
        ),
    ]























