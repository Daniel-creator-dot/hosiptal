from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1029_loginattempt_block_expires_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffPerformanceSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('role', models.CharField(choices=[('doctor', 'Doctor'), ('nurse', 'Nurse'), ('pharmacist', 'Pharmacist'), ('lab_technician', 'Lab Technician'), ('radiologist', 'Radiologist'), ('admin', 'Administrator'), ('receptionist', 'Receptionist'), ('cashier', 'Cashier')], max_length=30)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('metrics', models.JSONField(blank=True, default=dict)),
                ('productivity_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('quality_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('engagement_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('overall_index', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('data_points', models.PositiveIntegerField(default=0)),
                ('sync_source', models.CharField(default='dashboard_sync', max_length=50)),
                ('synced_at', models.DateTimeField(auto_now=True)),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='performance_snapshots', to='hospital.staff')),
            ],
            options={
                'ordering': ['-period_end', '-created'],
                'unique_together': {('staff', 'role', 'period_start', 'period_end')},
            },
        ),
    ]

