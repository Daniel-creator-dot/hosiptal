# Generated manually for lab/imaging result file attachments

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1084_fix_bank_account_invalid_account_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientdocument',
            name='lab_result',
            field=models.ForeignKey(
                blank=True,
                help_text='Lab result this document belongs to',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attached_documents',
                to='hospital.labresult'
            ),
        ),
        migrations.AddField(
            model_name='patientdocument',
            name='imaging_study',
            field=models.ForeignKey(
                blank=True,
                help_text='Imaging study this document belongs to',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attached_documents',
                to='hospital.imagingstudy'
            ),
        ),
    ]
