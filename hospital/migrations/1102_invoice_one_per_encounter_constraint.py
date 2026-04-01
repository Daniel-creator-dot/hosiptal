# One invoice per encounter: unique constraint on (encounter) when non-null and not deleted.

from django.db import migrations, models
from django.db.models import Q


def check_no_duplicate_encounter_invoices(apps, schema_editor):
    """Fail with a clear message if any encounter has more than one non-deleted invoice."""
    Invoice = apps.get_model("hospital", "Invoice")
    from django.db.models import Count

    # Use all_objects so we see every invoice (default manager may hide zero-amount ones)
    qs = getattr(Invoice, "all_objects", Invoice.objects)
    dupes = (
        qs.filter(encounter__isnull=False, is_deleted=False)
        .values("encounter")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    if dupes.exists():
        encounter_ids = [r["encounter"] for r in dupes]
        raise RuntimeError(
            "Cannot add one-invoice-per-encounter constraint: the following encounter IDs "
            "have more than one non-deleted invoice: {}. Merge or reassign invoices so "
            "each encounter has at most one non-deleted invoice, then run this migration again.".format(
                encounter_ids
            )
        )


class Migration(migrations.Migration):

    dependencies = [
        ("hospital", "1101_add_encounter_billing_closed_at"),
    ]

    operations = [
        migrations.RunPython(check_no_duplicate_encounter_invoices, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=Q(encounter__isnull=False, is_deleted=False),
                fields=("encounter",),
                name="hospital_invoice_one_per_encounter",
            ),
        ),
    ]
