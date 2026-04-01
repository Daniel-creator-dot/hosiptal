from django.db import migrations, models
import django.db.models.deletion
import uuid
import model_utils.fields
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1047_patient_deposits'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordResetOTP',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('code', models.CharField(max_length=6, db_index=True)),
                ('expires_at', models.DateTimeField()),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('is_used', models.BooleanField(default=False)),
                ('sent_via', models.CharField(max_length=10, default='sms')),
                ('phone_snapshot', models.CharField(max_length=32, blank=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='password_reset_otps', to='auth.user')),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.AddIndex(
            model_name='passwordresetotp',
            index=models.Index(fields=['user', 'code', 'is_used'], name='hospital_pa_user_id_3f1e15_idx'),
        ),
    ]
















