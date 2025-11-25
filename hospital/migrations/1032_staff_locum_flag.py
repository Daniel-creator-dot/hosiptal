from django.db import migrations, models


def mark_existing_locums(apps, schema_editor):
    Staff = apps.get_model('hospital', 'Staff')
    LocumDoctorService = apps.get_model('hospital', 'LocumDoctorService')
    locum_ids = (
        LocumDoctorService.objects.filter(is_deleted=False)
        .values_list('doctor_id', flat=True)
        .distinct()
    )
    if locum_ids:
        Staff.objects.filter(id__in=locum_ids).update(is_locum=True)


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1031_add_locum_doctor_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='staff',
            name='is_locum',
            field=models.BooleanField(default=False, help_text='Mark as locum/visiting staff for payment tracking'),
        ),
        migrations.RunPython(mark_existing_locums, migrations.RunPython.noop),
    ]

