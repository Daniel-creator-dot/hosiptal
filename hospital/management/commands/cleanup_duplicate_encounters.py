"""
Management command to cleanup duplicate encounters
1) Same patient + same day + same chief_complaint: keep oldest, soft-delete rest.
2) Same patient + same day (any complaint): keep one per day (prefer with provider, non-registration), soft-delete rest.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q, DateTimeField
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone

from hospital.models import Encounter


class Command(BaseCommand):
    help = 'Cleanup duplicate encounters (same patient same day); keeps one per day, soft-deletes rest'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of duplicates',
        )
        parser.add_argument(
            '--same-day-only',
            action='store_true',
            help='Only run same-patient-same-day dedup (one per day); skip same-complaint groups',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        confirm = options.get('confirm', False)
        same_day_only = options.get('same_day_only', False)
        
        if not dry_run and not confirm:
            self.stdout.write(
                self.style.WARNING(
                    '\n*** WARNING: This will soft-delete duplicate encounters!\n'
                    '   - Same patient + same day: keeps ONE encounter (prefer with provider, non-registration)\n'
                    '   - Same patient + same day + same complaint: keeps oldest\n'
                    '\n'
                    'To see what would be deleted: python manage.py cleanup_duplicate_encounters --dry-run\n'
                    'To actually delete: python manage.py cleanup_duplicate_encounters --confirm\n'
                )
            )
            return
        
        self.stdout.write(self.style.WARNING('\n*** Checking for duplicate encounters...\n'))
        total_deleted = 0
        
        # --- PASS 1: Same patient + same day (any chief_complaint) -> keep one per day ---
        # Group by patient and date (use started_at or created for date)
        qs = Encounter.objects.filter(is_deleted=False).annotate(
            encounter_date=TruncDate(Coalesce('started_at', 'created', output_field=DateTimeField()))
        ).values('patient', 'encounter_date').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        same_day_groups = list(qs)
        self.stdout.write(f'Found {len(same_day_groups)} patient-days with multiple encounters (pass 1: one per day)')
        
        for group in same_day_groups:
            patient_id = group['patient']
            encounter_date = group['encounter_date']
            count = group['count']
            encounters = list(
                Encounter.objects.filter(
                    patient_id=patient_id,
                    is_deleted=False,
                ).filter(
                    Q(started_at__date=encounter_date) | Q(started_at__isnull=True, created__date=encounter_date)
                ).select_related('patient').order_by('created')
            )
            if len(encounters) < 2:
                continue
            # Keep one: prefer has provider and not "New patient registration", then most recent
            def score(e):
                has_provider = 2 if e.provider_id else 0
                is_reg = -2 if (e.chief_complaint or '').strip().lower() == 'new patient registration' else 0
                return (has_provider + is_reg, -(e.created or timezone.now()).timestamp())
            encounters_sorted = sorted(encounters, key=score, reverse=True)
            keep_enc = encounters_sorted[0]
            to_delete = [e for e in encounters_sorted[1:] if e.id != keep_enc.id]
            patient = keep_enc.patient
            patient_name = patient.full_name if patient else str(patient_id)
            patient_mrn = getattr(patient, 'mrn', 'N/A') if patient else 'N/A'
            self.stdout.write(f'\nPatient: {patient_name} ({patient_mrn}) Date: {encounter_date} -> keeping 1, removing {len(to_delete)}')
            self.stdout.write(f'  Keeping: {keep_enc.id} complaint="{getattr(keep_enc, "chief_complaint", "")[:40]}" provider={bool(keep_enc.provider_id)}')
            for dup in to_delete:
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would delete: {dup.id}'))
                else:
                    try:
                        with transaction.atomic():
                            dup.is_deleted = True
                            dup.save(update_fields=['is_deleted'])
                        self.stdout.write(self.style.SUCCESS(f'  [DELETED] {dup.id}'))
                        total_deleted += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  [ERROR] {dup.id}: {e}'))
        
        if same_day_only:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(self.style.SUCCESS(f'\n[COMPLETE] Pass 1 only. Soft-deleted {total_deleted} duplicates\n'))
            return
        
        # --- PASS 2: Same patient + same day + same chief_complaint (original logic) ---
        duplicates_same_day = Encounter.objects.filter(
            is_deleted=False
        ).annotate(
            encounter_date=TruncDate(Coalesce('started_at', 'created', output_field=DateTimeField()))
        ).values(
            'patient', 'encounter_date', 'chief_complaint'
        ).annotate(
            count=Count('id')
        ).filter(
            count__gt=1
        ).order_by('-count', '-encounter_date')
        
        total_groups = list(duplicates_same_day)
        
        if not total_groups:
            self.stdout.write('\n[Pass 2] No same-complaint duplicate groups left.')
        else:
            self.stdout.write(f'\n[Pass 2] Found {len(total_groups)} duplicate groups (same patient+date+complaint)\n')
        
        total_kept = 0
        for dup_group in total_groups:
            patient_id = dup_group['patient']
            encounter_date = dup_group['encounter_date']
            chief_complaint = dup_group['chief_complaint']
            count = dup_group['count']
            
            # Get all encounters in this duplicate group (same patient + date + chief_complaint)
            encounters = Encounter.objects.filter(
                patient_id=patient_id,
                chief_complaint=chief_complaint,
                is_deleted=False
            ).filter(
                Q(started_at__date=encounter_date) | Q(started_at__isnull=True, created__date=encounter_date)
            ).select_related('patient').order_by('created', 'started_at')
            
            if encounters.count() < 2:
                continue
            
            patient = encounters.first().patient if encounters.exists() else None
            patient_name = patient.full_name if patient else f"Patient ID: {patient_id}"
            patient_mrn = patient.mrn if patient else "N/A"
            
            # Keep the first (oldest) encounter
            keep_encounter = encounters.first()
            duplicates_to_delete = list(encounters[1:])
            
            self.stdout.write(f'\nPatient: {patient_name} ({patient_mrn})')
            self.stdout.write(f'  Date: {encounter_date}')
            self.stdout.write(f'  Complaint: {chief_complaint[:50]}')
            self.stdout.write(f'  Total: {count} encounters')
            self.stdout.write(f'  Keeping: {keep_encounter.id} (created: {keep_encounter.created})')
            
            delete_count = 0
            for dup in duplicates_to_delete:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  [DRY RUN] Would delete: {dup.id} (created: {dup.created})'
                        )
                    )
                else:
                    try:
                        with transaction.atomic():
                            # Mark as deleted instead of actually deleting (soft delete)
                            dup.is_deleted = True
                            dup.save(update_fields=['is_deleted'])
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  [DELETED] {dup.id} (created: {dup.created})'
                                )
                            )
                            total_deleted += 1
                            delete_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'  [ERROR] Failed to delete {dup.id}: {e}'
                            )
                        )
            
            if dry_run:
                delete_count = len(duplicates_to_delete)
            
            total_kept += 1
        
        self.stdout.write('\n' + '=' * 70)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Would keep {total_kept} encounters, would delete {total_deleted} duplicates\n'
                    'Run with --confirm to actually delete duplicates\n'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[COMPLETE] Kept {total_kept} encounters, deleted {total_deleted} duplicates\n'
                )
            )
        self.stdout.write('=' * 70 + '\n')
