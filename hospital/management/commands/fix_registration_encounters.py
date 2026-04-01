"""
One-time fix: Remove front-desk staff from "New patient registration" encounters
and hide their auto-created medical records so they no longer appear as
"Attending Physician" or "Created By" in patient/medical record views.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from hospital.models import Encounter, MedicalRecord


class Command(BaseCommand):
    help = (
        'Set provider=None on registration-only encounters and soft-delete '
        'their medical records so front desk staff do not appear in patient records.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made'))

        # Encounters with chief complaint "New patient registration" (case-insensitive)
        registration_encounters = Encounter.objects.filter(
            is_deleted=False,
            chief_complaint__iexact='New patient registration',
        )

        count = registration_encounters.count()
        self.stdout.write(f'Found {count} encounter(s) with chief complaint "New patient registration"')

        updated_encounters = 0
        for enc in registration_encounters:
            if enc.provider_id is not None:
                if not dry_run:
                    enc.provider_id = None
                    enc.save(update_fields=['provider_id', 'modified'])
                updated_encounters += 1
                self.stdout.write(
                    f'  Encounter {enc.id} (patient {enc.patient_id}): cleared provider'
                )

        if updated_encounters:
            self.stdout.write(
                self.style.SUCCESS(f'Cleared provider on {updated_encounters} encounter(s)')
            )
        else:
            self.stdout.write('No encounters had provider set; nothing to clear.')

        # MedicalRecord linked to those encounters: soft-delete so they disappear from lists
        encounter_ids = list(registration_encounters.values_list('id', flat=True))
        if not encounter_ids:
            self.stdout.write('No registration encounters; skipping medical records.')
            return

        records_to_hide = MedicalRecord.objects.filter(
            is_deleted=False,
            encounter_id__in=encounter_ids,
        )
        record_count = records_to_hide.count()
        self.stdout.write(f'Found {record_count} medical record(s) linked to registration encounters')

        if record_count and not dry_run:
            updated = records_to_hide.update(is_deleted=True)
            self.stdout.write(
                self.style.SUCCESS(f'Soft-deleted {updated} medical record(s) (no longer shown in lists)')
            )
        elif record_count and dry_run:
            self.stdout.write(self.style.WARNING(f'Would soft-delete {record_count} medical record(s)'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN complete. Run without --dry-run to apply.'))
