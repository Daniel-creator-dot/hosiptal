# Generated manually for new HR features
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '0042_add_hr_activities_and_leave_tracking'),
    ]

    operations = [
        # Hospital Activity (Calendar)
        migrations.CreateModel(
            name='HospitalActivity',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('activity_type', models.CharField(choices=[('meeting', 'Meeting'), ('training', 'Training Session'), ('workshop', 'Workshop'), ('conference', 'Conference'), ('social', 'Social Event'), ('announcement', 'Announcement'), ('holiday', 'Holiday'), ('maintenance', 'Maintenance'), ('drill', 'Emergency Drill'), ('celebration', 'Celebration'), ('other', 'Other')], default='announcement', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], default='normal', max_length=10)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('start_time', models.TimeField(blank=True, null=True)),
                ('end_time', models.TimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=200)),
                ('all_staff', models.BooleanField(default=True, help_text='Visible to all staff')),
                ('is_mandatory', models.BooleanField(default=False)),
                ('requires_rsvp', models.BooleanField(default=False)),
                ('max_participants', models.PositiveIntegerField(blank=True, null=True)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='activity_attachments/')),
                ('external_link', models.URLField(blank=True)),
                ('is_published', models.BooleanField(default=True)),
                ('published_at', models.DateTimeField(auto_now_add=True)),
                ('organizer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='organized_activities', to='hospital.staff')),
            ],
            options={
                'verbose_name': 'Hospital Activity',
                'verbose_name_plural': 'Hospital Activities',
                'ordering': ['-start_date', '-start_time'],
            },
        ),
        migrations.CreateModel(
            name='ActivityRSVP',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('response', models.CharField(choices=[('yes', 'Yes - Attending'), ('no', 'No - Not Attending'), ('maybe', 'Maybe')], max_length=10)),
                ('notes', models.TextField(blank=True)),
                ('responded_at', models.DateTimeField(auto_now=True)),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rsvps', to='hospital.hospitalactivity')),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_rsvps', to='hospital.staff')),
            ],
            options={
                'ordering': ['-responded_at'],
            },
        ),
        migrations.CreateModel(
            name='StaffRecognition',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False)),
                ('recognition_type', models.CharField(choices=[('employee_month', 'Employee of the Month'), ('excellence', 'Excellence Award'), ('innovation', 'Innovation Award'), ('customer_service', 'Customer Service Award'), ('teamwork', 'Teamwork Award'), ('safety', 'Safety Award'), ('attendance', 'Perfect Attendance'), ('years_service', 'Years of Service'), ('commendation', 'Commendation'), ('other', 'Other')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('awarded_date', models.DateField(default=django.utils.timezone.now)),
                ('certificate', models.FileField(blank=True, null=True, upload_to='recognition_certificates/')),
                ('prize_value', models.DecimalField(blank=True, decimal_places=2, help_text='Monetary value if applicable', max_digits=10, null=True)),
                ('is_public', models.BooleanField(default=True, help_text='Display on public recognition board')),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recognitions', to='hospital.staff')),
                ('awarded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='awards_given', to='auth.user')),
            ],
            options={
                'ordering': ['-awarded_date'],
                'abstract': False,
            },
        ),
        # Many-to-many relationships
        migrations.AddField(
            model_name='hospitalactivity',
            name='departments',
            field=models.ManyToManyField(blank=True, help_text='Specific departments (if not all staff)', to='hospital.department'),
        ),
        migrations.AddField(
            model_name='hospitalactivity',
            name='specific_staff',
            field=models.ManyToManyField(blank=True, help_text='Specific staff members', related_name='targeted_activities', to='hospital.staff'),
        ),
        migrations.AlterUniqueTogether(
            name='activityrsvp',
            unique_together={('activity', 'staff')},
        ),
    ]























