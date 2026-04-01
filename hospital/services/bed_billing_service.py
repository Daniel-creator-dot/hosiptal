"""
Automatic Bed Billing Service

Billing logic:
- DETENTION: Stay < 12 hours → detention fee (GHS 120) + doctor care + nursing care + consumables (1 day equivalent each)
- ADMISSION: Stay >= 12 hours → count by **nights** (each 12-hour period after admission threshold = 1 night), not 24-hour days
  - Accommodation: GHS 150 per night (regular), GHS 300 per night (VIP)
  - Doctor care, nursing care, consumables: same per-night count × their rates
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging
import math

logger = logging.getLogger(__name__)

# Service codes for accommodation-related charges
ACCOM_SERVICE_CODES = ['DETENTION', 'ADM-ACCOM', 'ADM-DOCTOR-CARE', 'ADM-NURSING-CARE', 'ADM-CONSUMABLES']


class BedBillingService:
    """Service for automatic bed billing with detention vs admission logic."""

    # Pricing (GHS) – per **night** for admission (stay >= 12h); night = 12-hour billing unit
    DETENTION_RATE = Decimal('120.00')           # Stay < 12 hours (flat)
    ADMISSION_NIGHTLY_RATE = Decimal('150.00')   # Stay >= 12 hours, regular ward (per night)
    VIP_ADMISSION_NIGHTLY_RATE = Decimal('300.00')  # VIP ward (per night)
    DOCTOR_CARE_PER_NIGHT = Decimal('80.00')
    NURSING_CARE_PER_NIGHT = Decimal('70.00')
    CONSUMABLES_PER_NIGHT = Decimal('50.00')

    DETENTION_THRESHOLD_HOURS = 12
    # Backwards-compatible aliases (same values)
    ADMISSION_DAILY_RATE = ADMISSION_NIGHTLY_RATE
    VIP_ADMISSION_DAILY_RATE = VIP_ADMISSION_NIGHTLY_RATE
    DOCTOR_CARE_PER_DAY = DOCTOR_CARE_PER_NIGHT
    NURSING_CARE_PER_DAY = NURSING_CARE_PER_NIGHT
    CONSUMABLES_PER_DAY = CONSUMABLES_PER_NIGHT

    @staticmethod
    def _is_vip_ward(admission):
        """Check if ward is VIP (name contains 'vip')."""
        if admission and admission.ward:
            return 'vip' in (admission.ward.name or '').lower()
        return False

    @staticmethod
    def _get_admission_daily_rate(admission):
        """Return accommodation nightly rate: 150 regular, 300 VIP."""
        return (
            BedBillingService.VIP_ADMISSION_NIGHTLY_RATE
            if BedBillingService._is_vip_ward(admission)
            else BedBillingService.ADMISSION_NIGHTLY_RATE
        )

    @staticmethod
    def _admission_night_count(total_hours):
        """
        Nights for admission (>= 12h): each 12-hour block counts as one night, minimum 1.
        Example: 12–24h → 1 night; 25–36h → 2 nights; 48h → 3 nights.
        """
        if total_hours < BedBillingService.DETENTION_THRESHOLD_HOURS:
            return 0
        # ceil(h/12) - 1 gives nights after the first 12h block; min 1 for any stay >= 12h
        n = int(math.ceil(total_hours / 12.0)) - 1
        return max(1, n)

    @staticmethod
    def _get_or_create_service_code(code, description, unit_price, category='accommodation'):
        """Get or create a ServiceCode. Unit_price used for InvoiceLine; ServiceCode has no default_price."""
        from hospital.models import ServiceCode
        desc = (description or '')[:200]
        return ServiceCode.objects.get_or_create(
            code=code,
            defaults={
                'description': desc,
                'category': category,
                'is_active': True,
            }
        )[0]

    @staticmethod
    def _get_stay_hours(admission):
        """Return total stay hours. Uses discharge_date if set, else now."""
        end = admission.discharge_date or timezone.now()
        delta = end - admission.admit_date
        return delta.total_seconds() / 3600

    @staticmethod
    def calculate_admission_charges(admission, include_partial_days=True):
        """
        Calculate charges based on stay duration (detention vs admission).

        Returns dict with:
        - is_detention: bool
        - total_hours: float
        - days: int (for admission: nights billed; key kept for compatibility)
        - nights: int (same as days when admission)
        - daily_rate: Decimal (nightly accommodation rate)
        - total_charge: Decimal
        - line_items: list of {code, description, quantity, unit_price, line_total}
        """
        _ = include_partial_days  # API compatibility; billing uses 12h night units
        total_hours = BedBillingService._get_stay_hours(admission)
        is_detention = total_hours < BedBillingService.DETENTION_THRESHOLD_HOURS

        bed_num = admission.bed.bed_number if admission.bed else 'N/A'
        ward_name = admission.ward.name if admission.ward else 'N/A'

        if is_detention:
            # Detention: base fee + doctor care + nursing care + consumables (1 night equivalent each)
            doctor_care_total = BedBillingService.DOCTOR_CARE_PER_NIGHT * 1
            nursing_care_total = BedBillingService.NURSING_CARE_PER_NIGHT * 1
            consumables_total = BedBillingService.CONSUMABLES_PER_NIGHT * 1
            total_detention_charge = (
                BedBillingService.DETENTION_RATE
                + doctor_care_total
                + nursing_care_total
                + consumables_total
            )
            line_items = [
                {
                    'code': 'DETENTION',
                    'description': f'Detention (< 12 hrs) - {ward_name} - Bed {bed_num}',
                    'quantity': 1,
                    'unit_price': BedBillingService.DETENTION_RATE,
                    'line_total': BedBillingService.DETENTION_RATE,
                },
                {
                    'code': 'ADM-DOCTOR-CARE',
                    'description': f'Doctor Care (detention) @ GHS {BedBillingService.DOCTOR_CARE_PER_NIGHT}/night',
                    'quantity': 1,
                    'unit_price': BedBillingService.DOCTOR_CARE_PER_NIGHT,
                    'line_total': doctor_care_total,
                },
                {
                    'code': 'ADM-NURSING-CARE',
                    'description': f'Nursing Care (detention) @ GHS {BedBillingService.NURSING_CARE_PER_NIGHT}/night',
                    'quantity': 1,
                    'unit_price': BedBillingService.NURSING_CARE_PER_NIGHT,
                    'line_total': nursing_care_total,
                },
                {
                    'code': 'ADM-CONSUMABLES',
                    'description': f'Consumables (detention) @ GHS {BedBillingService.CONSUMABLES_PER_NIGHT}/night',
                    'quantity': 1,
                    'unit_price': BedBillingService.CONSUMABLES_PER_NIGHT,
                    'line_total': consumables_total,
                },
            ]
            return {
                'is_detention': True,
                'total_hours': total_hours,
                'days': 0,
                'nights': 0,
                'daily_rate': BedBillingService.DETENTION_RATE,
                'total_charge': total_detention_charge,
                'admission_date': admission.admit_date,
                'discharge_date': admission.discharge_date or timezone.now(),
                'bed': bed_num,
                'ward': ward_name,
                'line_items': line_items,
            }

        # Admission: bill by nights (12-hour units), not 24-hour calendar days
        nights = BedBillingService._admission_night_count(total_hours)

        nightly_rate = BedBillingService._get_admission_daily_rate(admission)
        accom_total = nightly_rate * nights
        doctor_care_total = BedBillingService.DOCTOR_CARE_PER_NIGHT * nights
        nursing_care_total = BedBillingService.NURSING_CARE_PER_NIGHT * nights
        consumables_total = BedBillingService.CONSUMABLES_PER_NIGHT * nights

        line_items = [
            {
                'code': 'ADM-ACCOM',
                'description': (
                    f'Admission - {ward_name} - Bed {bed_num} '
                    f'({nights} night{"s" if nights != 1 else ""} @ GHS {nightly_rate}/night)'
                ),
                'quantity': nights,
                'unit_price': nightly_rate,
                'line_total': accom_total,
            },
            {
                'code': 'ADM-DOCTOR-CARE',
                'description': f'Doctor Care ({nights} night{"s" if nights != 1 else ""} @ GHS {BedBillingService.DOCTOR_CARE_PER_NIGHT}/night)',
                'quantity': nights,
                'unit_price': BedBillingService.DOCTOR_CARE_PER_NIGHT,
                'line_total': doctor_care_total,
            },
            {
                'code': 'ADM-NURSING-CARE',
                'description': f'Nursing Care ({nights} night{"s" if nights != 1 else ""} @ GHS {BedBillingService.NURSING_CARE_PER_NIGHT}/night)',
                'quantity': nights,
                'unit_price': BedBillingService.NURSING_CARE_PER_NIGHT,
                'line_total': nursing_care_total,
            },
            {
                'code': 'ADM-CONSUMABLES',
                'description': f'Consumables ({nights} night{"s" if nights != 1 else ""} @ GHS {BedBillingService.CONSUMABLES_PER_NIGHT}/night)',
                'quantity': nights,
                'unit_price': BedBillingService.CONSUMABLES_PER_NIGHT,
                'line_total': consumables_total,
            },
        ]

        total_charge = accom_total + doctor_care_total + nursing_care_total + consumables_total

        return {
            'is_detention': False,
            'total_hours': total_hours,
            'days': nights,
            'nights': nights,
            'daily_rate': nightly_rate,
            'total_charge': total_charge,
            'admission_date': admission.admit_date,
            'discharge_date': admission.discharge_date or timezone.now(),
            'bed': bed_num,
            'ward': ward_name,
            'line_items': line_items,
        }

    @staticmethod
    def _clear_accommodation_lines(invoice, admission):
        """
        Remove all accommodation-related invoice lines (BED-*, DETENTION, ADM-*, etc.).
        Returns total amount removed.
        """
        from hospital.models import InvoiceLine, ServiceCode

        removed = Decimal('0.00')
        codes_to_remove = list(ACCOM_SERVICE_CODES)
        # Include legacy BED-* and accommodation codes (don't filter is_deleted on ServiceCode - lines may reference old codes)
        bed_codes = ServiceCode.objects.filter(code__startswith='BED-').values_list('id', flat=True)
        accom_codes = ServiceCode.objects.filter(code__in=codes_to_remove).values_list('id', flat=True)
        code_ids = list(bed_codes) + list(accom_codes)

        lines = InvoiceLine.objects.filter(
            invoice=invoice,
            service_code_id__in=code_ids,
            is_deleted=False,
        )
        for line in lines:
            removed += line.line_total or Decimal('0.00')
        lines.delete()
        return removed

    @staticmethod
    def _add_accommodation_lines(invoice, admission, charge_breakdown):
        """Add invoice lines from charge_breakdown['line_items']."""
        from hospital.models import InvoiceLine

        added = Decimal('0.00')
        for item in charge_breakdown['line_items']:
            sc = BedBillingService._get_or_create_service_code(
                item['code'],
                item['description'],
                item['unit_price'],
            )
            InvoiceLine.objects.create(
                invoice=invoice,
                service_code=sc,
                description=(item['description'] or '')[:200],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                line_total=item['line_total'],
            )
            added += item['line_total']
        return added

    @staticmethod
    def create_admission_bill(admission, days=1):
        """
        Create provisional bed/accommodation charges on admission.
        Uses detention rate (GHS 120) as placeholder; final charges applied on discharge.
        """
        from hospital.models import Invoice, InvoiceLine

        try:
            with transaction.atomic():
                patient = admission.encounter.patient
                encounter = admission.encounter
                if getattr(encounter, 'billing_closed_at', None):
                    return {
                        'success': False,
                        'error': 'Billing is closed for this encounter',
                        'message': 'No new accommodation charges can be added after discharge.',
                    }

                # Provisional: detention rate (120) until discharge recalculates
                total_charge = BedBillingService.DETENTION_RATE
                sc = BedBillingService._get_or_create_service_code(
                    'DETENTION',
                    'Accommodation (provisional - final on discharge)',
                    BedBillingService.DETENTION_RATE,
                )

                from hospital.models import Payer
                payer = patient.primary_insurance or Payer.objects.filter(
                    payer_type='cash', is_active=True, is_deleted=False
                ).first() or Payer.objects.filter(is_active=True, is_deleted=False).first()
                if not payer:
                    raise ValueError('No payer configured. Please add a Cash payer in the system.')

                invoice, _ = Invoice.all_objects.get_or_create(
                    patient=patient,
                    encounter=encounter,
                    is_deleted=False,
                    defaults={
                        'payer': payer,
                        'issued_at': timezone.now(),
                        'total_amount': Decimal('0.00'),
                        'balance': Decimal('0.00'),
                        'status': 'draft',
                    },
                )

                # Avoid duplicate provisional line
                existing = invoice.lines.filter(
                    service_code=sc,
                    is_deleted=False,
                ).exists()
                if existing:
                    return {
                        'success': True,
                        'invoice': invoice,
                        'days': 1,
                        'daily_rate': BedBillingService.DETENTION_RATE,
                        'total_charge': total_charge,
                        'message': 'Provisional accommodation charge already exists; final charges on discharge.',
                    }

                ward_name = admission.ward.name if admission.ward else 'N/A'
                bed_num = admission.bed.bed_number if admission.bed else 'N/A'
                desc = f'Accommodation (provisional) - {ward_name} - Bed {bed_num}'[:200]

                InvoiceLine.objects.create(
                    invoice=invoice,
                    service_code=sc,
                    description=desc,
                    quantity=1,
                    unit_price=BedBillingService.DETENTION_RATE,
                    line_total=total_charge,
                )
                invoice.update_totals()
                invoice.status = 'issued'
                invoice.save(update_fields=['status'])

                logger.info(
                    f"✅ Provisional accommodation billing created: {patient.full_name} - "
                    f"GHS {total_charge} (final on discharge)"
                )

                return {
                    'success': True,
                    'invoice': invoice,
                    'days': 1,
                    'daily_rate': BedBillingService.DETENTION_RATE,
                    'total_charge': total_charge,
                    'message': (
                        f'Provisional charge GHS {total_charge}. '
                        'Final charges (detention or admission + care) applied on discharge.'
                    ),
                }

        except Exception as e:
            logger.error(f"Error creating admission bill: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': str(e),
            }

    @staticmethod
    def update_bed_charges_on_discharge(admission):
        """
        Finalize accommodation charges on discharge.
        Applies detention (120) or full admission (accommodation + doctor + nursing care).
        """
        from hospital.models import Invoice, InvoiceLine

        try:
            with transaction.atomic():
                patient = admission.encounter.patient
                encounter = admission.encounter

                charge_breakdown = BedBillingService.calculate_admission_charges(
                    admission,
                    include_partial_days=True,
                )

                try:
                    invoice = Invoice.all_objects.get(
                        patient=patient,
                        encounter=encounter,
                        is_deleted=False,
                    )
                except Invoice.DoesNotExist:
                    from hospital.models import Payer
                    payer = patient.primary_insurance or Payer.objects.filter(
                        payer_type='cash', is_active=True, is_deleted=False
                    ).first() or Payer.objects.filter(is_active=True, is_deleted=False).first()
                    if not payer:
                        raise ValueError('No payer configured. Please add a Cash payer in the system.')
                    invoice = Invoice.objects.create(
                        patient=patient,
                        encounter=encounter,
                        payer=payer,
                        issued_at=timezone.now(),
                        total_amount=Decimal('0.00'),
                        balance=Decimal('0.00'),
                        status='draft',
                    )

                removed = BedBillingService._clear_accommodation_lines(invoice, admission)
                BedBillingService._add_accommodation_lines(invoice, admission, charge_breakdown)

                invoice.update_totals()
                if invoice.balance > 0:
                    invoice.status = 'issued'
                if not invoice.issued_at:
                    invoice.issued_at = timezone.now()
                invoice.save(update_fields=['status', 'issued_at'])

                from django.db.models.signals import post_save
                post_save.send(sender=Invoice, instance=invoice, created=False)

                logger.info(
                    f"✅ Accommodation charges finalized on discharge: {patient.full_name} - "
                    f"{'Detention' if charge_breakdown['is_detention'] else 'Admission'} "
                    f"GHS {charge_breakdown['total_charge']}"
                )

                return {
                    'success': True,
                    'invoice': invoice,
                    'charge_breakdown': charge_breakdown,
                    'message': (
                        f"{'Detention' if charge_breakdown['is_detention'] else 'Admission'} charges: "
                        f"GHS {charge_breakdown['total_charge']}"
                    ),
                }

        except Exception as e:
            logger.error(f"Error updating bed charges on discharge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': str(e),
            }

    @staticmethod
    def get_bed_charges_summary(admission):
        """Return summary dict for display."""
        breakdown = BedBillingService.calculate_admission_charges(admission)

        return {
            'days_admitted': breakdown['days'] if not breakdown['is_detention'] else 0,
            'nights_admitted': breakdown.get('nights', breakdown['days']) if not breakdown['is_detention'] else 0,
            'daily_rate': breakdown['daily_rate'],
            'current_charges': breakdown['total_charge'],
            'bed_number': breakdown['bed'],
            'ward_name': breakdown['ward'],
            'admission_date': breakdown['admission_date'],
            'discharge_date': breakdown['discharge_date'],
            'is_discharged': admission.status == 'discharged',
            'is_detention': breakdown['is_detention'],
            'total_hours': breakdown.get('total_hours', 0),
        }


bed_billing_service = BedBillingService()
