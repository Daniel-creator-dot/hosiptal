"""
Merge duplicate encounters for a patient - combines vitals, clinical notes, and related data.
Use case: Patient has 2 encounters same day - one with vitals, one with clinical notes.
Keeps one encounter, moves all data to it, soft-deletes the duplicate(s).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from hospital.models import (
    Patient, Encounter, VitalSign, Order, Invoice,
)
from hospital.models_workflow import PatientFlowStage

# Optional imports for extended merge
try:
    from hospital.models_advanced import ClinicalNote, Diagnosis, Procedure, ImagingStudy
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False
    ClinicalNote = None

try:
    from hospital.models_specialists import Referral
    HAS_REFERRAL = True
except ImportError:
    HAS_REFERRAL = False
    Referral = None


# Models with encounter FK that we'll reassign (model, fk_field)
MERGE_MODELS = [
    ('VitalSign', VitalSign, 'encounter'),
    ('Order', Order, 'encounter'),
    ('Invoice', Invoice, 'encounter'),
    ('PatientFlowStage', PatientFlowStage, 'encounter'),
]
if HAS_ADVANCED:
    MERGE_MODELS.extend([
        ('ClinicalNote', ClinicalNote, 'encounter'),
        ('Diagnosis', Diagnosis, 'encounter'),
        ('Procedure', Procedure, 'encounter'),
        ('ImagingStudy', ImagingStudy, 'encounter'),
    ])
if HAS_REFERRAL and Referral:
    MERGE_MODELS.append(('Referral', Referral, 'encounter'))


class Command(BaseCommand):
    help = 'Merge duplicate encounters for a patient (e.g. Janet Asaah) - combines vitals + clinical notes into one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patient',
            type=str,
            help='Patient name to search (e.g. "Janet Asaah" or "Asaah")',
        )
        parser.add_argument(
            '--patient-id',
            type=str,
            help='Patient UUID (exact match)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be merged without making changes',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm merge (required to execute)',
        )

    def handle(self, *args, **options):
        patient_name = (options.get('patient') or '').strip()
        patient_id = (options.get('patient_id') or '').strip()
        dry_run = options.get('dry_run', False)
        confirm = options.get('confirm', False)

        if not patient_name and not patient_id:
            self.stdout.write(
                self.style.ERROR('Please provide --patient "Name" or --patient-id UUID')
            )
            return

        # Find patient
        if patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id, is_deleted=False)
            except Patient.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Patient not found: {patient_id}'))
                return
        else:
            parts = patient_name.split()
            if len(parts) >= 2:
                q = Q(first_name__icontains=parts[0]) & Q(last_name__icontains=parts[1])
            else:
                q = Q(first_name__icontains=patient_name) | Q(last_name__icontains=patient_name) | Q(mrn__icontains=patient_name)
            patients = list(Patient.objects.filter(q, is_deleted=False)[:10])
            if not patients:
                self.stdout.write(self.style.ERROR(f'No patient found for: {patient_name}'))
                return
            if len(patients) > 1:
                self.stdout.write(f'Multiple patients found. Using first: {patients[0].full_name} (MRN: {patients[0].mrn})')
            patient = patients[0]

        self.stdout.write(self.style.SUCCESS(f'\nPatient: {patient.full_name} (MRN: {patient.mrn}, ID: {patient.id})'))

        # Find duplicate encounters (same patient, last 7 days, active)
        from datetime import timedelta
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        encounters = list(
            Encounter.objects.filter(
                patient=patient,
                is_deleted=False,
            ).filter(
                Q(started_at__date__gte=week_ago) | Q(started_at__isnull=True, created__date__gte=week_ago)
            ).select_related('patient', 'provider__user').order_by('-created')[:20]
        )

        if len(encounters) < 2:
            self.stdout.write(
                self.style.WARNING(
                    f'No duplicate encounters found for {patient.full_name} in last 7 days. '
                    f'Found {len(encounters)} encounter(s).'
                )
            )
            return

        self.stdout.write(f'\nFound {len(encounters)} encounter(s):')
        for e in encounters:
            vitals_count = VitalSign.objects.filter(encounter=e, is_deleted=False).count()
            notes_count = 0
            if HAS_ADVANCED and ClinicalNote:
                notes_count = ClinicalNote.objects.filter(encounter=e, is_deleted=False).count()
            provider = e.provider.user.get_full_name() if e.provider and e.provider.user else 'None'
            self.stdout.write(
                f'  - {e.id} | created: {e.created} | complaint: {(e.chief_complaint or "")[:40]} | '
                f'vitals: {vitals_count} | notes: {notes_count} | provider: {provider}'
            )

        # Pick keeper: prefer one with vitals AND notes, else with provider, else most data
        def score_encounter(e):
            vitals = VitalSign.objects.filter(encounter=e, is_deleted=False).count()
            notes = 0
            if HAS_ADVANCED and ClinicalNote:
                notes = ClinicalNote.objects.filter(encounter=e, is_deleted=False).count()
            has_provider = 10 if e.provider_id else 0
            has_vitals = 5 if vitals > 0 else 0
            has_notes = 5 if notes > 0 else 0
            has_complaint = 2 if (e.chief_complaint or '').strip() else 0
            return (has_provider + has_vitals + has_notes + has_complaint, -e.created.timestamp())

        encounters_sorted = sorted(encounters, key=score_encounter, reverse=True)
        keeper = encounters_sorted[0]
        duplicates = [e for e in encounters_sorted[1:] if e.id != keeper.id]

        self.stdout.write(self.style.SUCCESS(f'\nKeeping encounter: {keeper.id}'))
        self.stdout.write(self.style.WARNING(f'Merging and removing: {[str(d.id) for d in duplicates]}'))

        if not dry_run and not confirm:
            self.stdout.write(
                self.style.WARNING(
                    '\nRun with --dry-run to preview, or --confirm to execute merge.\n'
                )
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Would perform:'))
            for dup in duplicates:
                self.stdout.write(f'\n  From duplicate {dup.id}:')
                for name, model, fk_field in MERGE_MODELS:
                    try:
                        qs = model.objects.filter(**{fk_field: dup})
                        if hasattr(model, 'is_deleted'):
                            qs = qs.filter(is_deleted=False)
                        count = qs.count()
                        if count:
                            self.stdout.write(f'    - Move {name}: {count} record(s) -> keeper {keeper.id}')
                    except Exception as ex:
                        self.stdout.write(f'    - {name}: error ({ex})')
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes made.\n'))
            return

        # Execute merge
        with transaction.atomic():
            for dup in duplicates:
                # Move all related records to keeper
                for name, model, fk_field in MERGE_MODELS:
                    try:
                        qs = model.objects.filter(**{fk_field: dup})
                        if hasattr(model, 'is_deleted'):
                            qs = qs.filter(is_deleted=False)
                        n = qs.update(**{fk_field: keeper})
                        if n:
                            self.stdout.write(self.style.SUCCESS(f'  Moved {n} {name}(s) to keeper'))
                    except Exception as ex:
                        self.stdout.write(self.style.ERROR(f'  Error moving {name}: {ex}'))

                # Merge encounter text fields from duplicate if keeper is empty
                if not keeper.chief_complaint and dup.chief_complaint:
                    keeper.chief_complaint = dup.chief_complaint
                if not keeper.diagnosis and dup.diagnosis:
                    keeper.diagnosis = dup.diagnosis
                if not keeper.notes and dup.notes:
                    keeper.notes = dup.notes
                if not keeper.provider_id and dup.provider_id:
                    keeper.provider = dup.provider

                # Soft-delete duplicate
                dup.is_deleted = True
                dup.save(update_fields=['is_deleted'])
                self.stdout.write(self.style.SUCCESS(f'  Soft-deleted duplicate encounter {dup.id}'))

            # Save keeper if we merged any fields
            keeper.save(update_fields=['chief_complaint', 'diagnosis', 'notes', 'provider'])

        self.stdout.write(self.style.SUCCESS(f'\nMerge complete. Kept encounter {keeper.id} with all data.\n'))
