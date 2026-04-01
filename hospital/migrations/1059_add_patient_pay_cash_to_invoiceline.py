# Generated manually for insurance exclusion cash payment feature

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hospital", "1058_add_drug_accountability_system"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceline",
            name="patient_pay_cash",
            field=models.BooleanField(
                default=False,
                help_text="If True, this item requires cash payment from patient (insurance excluded but patient can pay)"
            ),
        ),
        migrations.AddField(
            model_name="invoiceline",
            name="prescription",
            field=models.ForeignKey(
                blank=True,
                help_text="Link to prescription if this line item is for a drug",
                null=True,
                on_delete=models.SET_NULL,
                related_name="invoice_lines",
                to="hospital.prescription",
            ),
        ),
    ]







