from django.core.management.base import BaseCommand
from hospital.models_accounting import PaymentReceipt
from hospital.services.payment_clearance_service import PaymentClearanceService


class Command(BaseCommand):
    help = "Re-run payment clearance linking for receipts (useful after logic updates)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--service-type",
            dest="service_type",
            help="Only process receipts with this service_type (e.g. pharmacy_prescription, combined).",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=0,
            help="Limit number of receipts to process (0 = all).",
        )

    def handle(self, *args, **options):
        service_type = options.get("service_type")
        limit = options.get("limit") or 0

        qs = PaymentReceipt.objects.filter(is_deleted=False).order_by("-receipt_date")
        if service_type:
            qs = qs.filter(service_type=service_type)

        total = qs.count()
        processed = 0

        self.stdout.write(f"Re-linking {total if not limit else min(total, limit)} receipt(s)...")

        for receipt in qs.iterator():
            PaymentClearanceService.link_receipt_to_services(receipt)
            processed += 1
            if limit and processed >= limit:
                break

            if processed % 25 == 0:
                self.stdout.write(f"Processed {processed} receipts...")

        self.stdout.write(self.style.SUCCESS(f"Done. Processed {processed} receipt(s)."))










