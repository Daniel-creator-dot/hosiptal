"""
Doctor-Specific Consultation Pricing Utility
Handles pricing for specialist doctors based on their names and specialties
"""
import logging
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class DoctorPricingService:
    """
    Service to determine consultation fees for specific doctors
    """
    
    # Doctor pricing configuration
    DOCTOR_PRICING = {
        # Physician Specialist
        'dr. awah': {
            'first_visit': Decimal('300.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Physician Specialist',
            'show_price': True,
        },
        # Dietitian
        'ofosu sylvester': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Dietitian',
            'show_price': True,
        },
        # Dental Surgeon – GHS 150 (frontdesk: select Dr Kumah or Dental for correct price)
        'dr. elikem kumah': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Dental Surgeon',
            'show_price': True,
        },
        'dr. kumah': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Dental Surgeon',
            'show_price': True,
        },
        'elikem kumah': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Dental Surgeon',
            'show_price': True,
        },
        'kumah elikem': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Dental Surgeon',
            'show_price': True,
        },
        # ENT Specialist
        'dr. eugene owusu-achaw': {
            'first_visit': Decimal('260.00'),
            'subsequent_visit': Decimal('260.00'),
            'specialty': 'ENT Specialist',
            'show_price': True,
        },
        'dr. eugene owusu-achiaw': {  # Alternative spelling
            'first_visit': Decimal('260.00'),
            'subsequent_visit': Decimal('260.00'),
            'specialty': 'ENT Specialist',
            'show_price': True,
        },
        # Gynaecology + Antenatal: base tariffs (+8 sustainability applied in _apply_sustainability…).
        # UI shows two specialty groups (see _expand_antenatal_doctor_cards_for_quick_visit in views).
        'dr. ali samba': {
            'first_visit': Decimal('260.00'),  # Gynae / Special → 268 billed
            'subsequent_visit': Decimal('260.00'),
            'anc_visit': Decimal('235.00'),  # Antenatal / ANC → 243 billed
            'specialty': 'Gynaecology (Special) — 268 GHS',
            'show_price': True,
        },
        # Physiotherapist - GHS 250 first time, GHS 150 subsequent
        'titiati edem': {
            'first_visit': Decimal('250.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Physiotherapist',
            'show_price': True,
        },
        'edem titiati': {
            'first_visit': Decimal('250.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Physiotherapist',
            'show_price': True,
        },
        # Urologist
        'dr. boakye': {
            'first_visit': Decimal('250.00'),
            'subsequent_visit': Decimal('250.00'),
            'specialty': 'Urologist',
            'show_price': True,
        },
        # Ophthalmologist
        'dr. brako emmanuel': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'Ophthalmologist (Eye Specialist)',
            'show_price': True,
        },
        # General Surgeon
        'dr. adigah boniface': {
            'first_visit': Decimal('260.00'),
            'subsequent_visit': Decimal('260.00'),
            'specialty': 'General Surgeon',
            'show_price': True,
        },
        # Psychiatrists — new 350 / subsequent 300 (+8 sustainability applied below)
        'dr. sheila appiah-pippim': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'dr. shelia appiah-pippim': {  # Alternative spelling
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'sheila appiah-pippim': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'dr. rebecca abalo': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'rebecca abalo': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'dr. lartey lorna': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'lorna lartey': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'dr. mustapha dadzie': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        'mustapha dadzie': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': True,
        },
        # Paediatrician
        'dr. kojo ahor-essel': {
            'first_visit': Decimal('260.00'),
            'subsequent_visit': Decimal('260.00'),
            'specialty': 'Paediatrician',
            'show_price': True,
        },
        'dr. kojo essel-ahor': {  # Reversed name order
            'first_visit': Decimal('260.00'),
            'subsequent_visit': Decimal('260.00'),
            'specialty': 'Paediatrician',
            'show_price': True,
        },
        # Dr. Kwadwo Ayisi
        'dr. kwadwo ayisi': {
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'General Consultation',
            'show_price': False,  # Don't show price for general doctors
        },
        'dr kwadwo ayisi': {  # Alternative format
            'first_visit': Decimal('150.00'),
            'subsequent_visit': Decimal('150.00'),
            'specialty': 'General Consultation',
            'show_price': False,
        },
    }
    
    # Default consultation fee for other doctors
    DEFAULT_CONSULTATION_FEE = Decimal('150.00')
    
    @classmethod
    def normalize_doctor_name(cls, name):
        """
        Normalize doctor name for matching
        Removes extra spaces, converts to lowercase, handles variations
        """
        if not name:
            return ''
        # Remove 'Dr.', 'Dr', extra spaces, convert to lowercase
        normalized = name.lower().strip()
        normalized = normalized.replace('dr.', '').replace('dr', '').strip()
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        return normalized
    
    @classmethod
    def get_doctor_pricing_info(cls, doctor_staff):
        """
        Get pricing information for a specific doctor
        
        Args:
            doctor_staff: Staff object representing the doctor
            
        Returns:
            dict: Pricing information with keys:
                - first_visit: Decimal price for first visit
                - subsequent_visit: Decimal price for subsequent visit
                - specialty: str specialty name
                - show_price: bool whether to show price in UI
                - is_specialist: bool whether this is a specialist with custom pricing
        """
        if not doctor_staff or not doctor_staff.user:
            return {
                'first_visit': cls.DEFAULT_CONSULTATION_FEE,
                'subsequent_visit': cls.DEFAULT_CONSULTATION_FEE,
                'specialty': 'General Consultation',
                'show_price': False,
                'is_specialist': False,
            }
        
        # Get doctor's full name
        full_name = doctor_staff.user.get_full_name() or ''
        if not full_name:
            full_name = f"{doctor_staff.user.first_name} {doctor_staff.user.last_name}".strip()
        
        # Normalize name for matching
        normalized_name = cls.normalize_doctor_name(full_name)
        last_name = ''
        if doctor_staff.user.last_name:
            last_name = doctor_staff.user.last_name.lower().strip()

        matched = cls._lookup_configured_pricing(normalized_name, last_name)
        if matched:
            pricing = matched.copy()
            pricing['is_specialist'] = True
            return cls._apply_sustainability_to_specialist_pricing(pricing)

        # Match by specialization / department (covers psychiatrists not in the name list)
        specialization = (doctor_staff.specialization or '').lower()
        specialty_name = ''
        dept_name = ''
        try:
            if hasattr(doctor_staff, 'specialist_profile') and doctor_staff.specialist_profile:
                specialty_name = (doctor_staff.specialist_profile.specialty.name or '').lower()
        except Exception:
            pass
        try:
            if getattr(doctor_staff, 'department', None):
                dept_name = (doctor_staff.department.name or '').lower()
        except Exception:
            pass
        combined_spec = f'{specialization} {specialty_name} {dept_name}'
        if any(x in combined_spec for x in ('psychiatr', 'psychiatry', 'mental health')):
            return cls._apply_sustainability_to_specialist_pricing({
                'first_visit': Decimal('350.00'),
                'subsequent_visit': Decimal('300.00'),
                'specialty': 'Psychiatrist',
                'show_price': True,
                'is_specialist': True,
            })
        # Dental consultation (e.g. Dr Kumah) = GHS 150 so frontdesk input shows correct price
        if 'dental' in combined_spec:
            return cls._apply_sustainability_to_specialist_pricing({
                'first_visit': Decimal('150.00'),
                'subsequent_visit': Decimal('150.00'),
                'specialty': 'Dental Surgeon',
                'show_price': True,
                'is_specialist': True,
            })
        if 'physio' in combined_spec or 'physiotherapy' in combined_spec:
            return cls._apply_sustainability_to_specialist_pricing({
                'first_visit': Decimal('250.00'),
                'subsequent_visit': Decimal('150.00'),
                'specialty': 'Physiotherapist',
                'show_price': True,
                'is_specialist': True,
            })
        
        # Default pricing for other doctors
        return {
            'first_visit': cls.DEFAULT_CONSULTATION_FEE,
            'subsequent_visit': cls.DEFAULT_CONSULTATION_FEE,
            'specialty': doctor_staff.specialization or 'General Consultation',
            'show_price': False,  # Don't show prices for general doctors
            'is_specialist': False,
        }

    @classmethod
    def _lookup_configured_pricing(cls, normalized_name, last_name=''):
        """Match DOCTOR_PRICING keys after stripping Dr. from both sides."""
        if normalized_name:
            for key, pricing in cls.DOCTOR_PRICING.items():
                if cls.normalize_doctor_name(key) == normalized_name:
                    return pricing
            for key, pricing in cls.DOCTOR_PRICING.items():
                nk = cls.normalize_doctor_name(key)
                if nk and (nk in normalized_name or normalized_name in nk):
                    return pricing
        last = cls.normalize_doctor_name(last_name or '')
        if last and len(last) >= 4:
            for key, pricing in cls.DOCTOR_PRICING.items():
                if last in cls.normalize_doctor_name(key):
                    return pricing
        return None

    @classmethod
    def is_specialist_doctor(cls, doctor_staff):
        """True when this doctor uses specialist first/subsequent consultation tariffs."""
        if not doctor_staff:
            return False
        return bool(cls.get_doctor_pricing_info(doctor_staff).get('is_specialist'))

    @classmethod
    def _apply_sustainability_to_specialist_pricing(cls, pricing):
        """
        Specialist / gynae / ANC consultation tariffs include GHS 8 Sustainability and Insurance.
        """
        if not pricing or not pricing.get('is_specialist'):
            return pricing
        from hospital.utils_billing import SUSTAINABILITY_FEE
        out = pricing.copy()
        for key in ('first_visit', 'subsequent_visit', 'anc_visit'):
            if key in out and out[key] is not None:
                amt = Decimal(str(out[key]))
                if amt > 0:
                    out[key] = (amt + SUSTAINABILITY_FEE).quantize(Decimal('0.01'))
        return out

    @classmethod
    def is_first_visit_to_doctor(cls, patient, doctor_staff, exclude_encounter=None):
        """
        Check if this is the patient's first visit to this specific doctor.
        exclude_encounter: the visit being billed now (must not count as a prior visit).
        """
        if not patient or not doctor_staff:
            return True
        
        from .models import Encounter
        
        previous = Encounter.objects.filter(
            patient=patient,
            provider=doctor_staff,
            is_deleted=False
        ).exclude(status='cancelled')
        exclude_id = getattr(exclude_encounter, 'pk', None) or exclude_encounter
        if exclude_id:
            previous = previous.exclude(pk=exclude_id)
        return not previous.exists()
    
    @classmethod
    def get_consultation_fee(
        cls,
        patient,
        doctor_staff,
        encounter_type=None,
        is_review_visit=False,
        encounter=None,
    ):
        """
        Get the appropriate consultation fee for a patient visiting a doctor.
        Specialists (e.g. psychiatric) use first vs subsequent even on a follow-up visit.
        """
        if is_review_visit and not cls.is_specialist_doctor(doctor_staff):
            return Decimal('0.00')
        
        pricing_info = cls.get_doctor_pricing_info(doctor_staff)
        
        # Antenatal is always 235 + 8 sustainability = 243
        if encounter_type and 'antenatal' in encounter_type.lower():
            from hospital.utils_billing import ANC_VISIT
            return ANC_VISIT
        
        is_first = cls.is_first_visit_to_doctor(
            patient, doctor_staff, exclude_encounter=encounter
        )
        
        if is_first:
            return pricing_info['first_visit']
        return pricing_info['subsequent_visit']
    
    @classmethod
    def get_doctor_display_info(cls, doctor_staff):
        """
        Get display information for a doctor in the UI
        
        Returns:
            dict: Display info with pricing text, specialty, etc.
        """
        pricing_info = cls.get_doctor_pricing_info(doctor_staff)
        
        display_info = {
            'specialty': pricing_info['specialty'],
            'is_specialist': pricing_info['is_specialist'],
            'show_price': pricing_info['show_price'],
            'price_text': '',
        }
        
        if pricing_info['show_price']:
            if pricing_info['first_visit'] == pricing_info['subsequent_visit']:
                # Same price for first and subsequent
                display_info['price_text'] = f"GHS {pricing_info['first_visit']:.2f}"
            else:
                # Different prices
                display_info['price_text'] = f"First: GHS {pricing_info['first_visit']:.2f} | Subsequent: GHS {pricing_info['subsequent_visit']:.2f}"
        else:
            display_info['price_text'] = 'Consultation Fee'
        
        return display_info
