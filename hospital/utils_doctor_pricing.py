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
        # Gynaecology + Antenatal: two cashier prices — 260 (Gynae) and 235 (ANC).
        # UI shows two specialty groups (see _expand_antenatal_doctor_cards_for_quick_visit in views).
        'dr. ali samba': {
            'first_visit': Decimal('260.00'),  # Gynae / Special
            'subsequent_visit': Decimal('260.00'),
            'anc_visit': Decimal('235.00'),  # Antenatal / ANC
            'specialty': 'Gynaecology (Special) — 260 GHS',
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
        # Psychiatrists (don't show prices)
        'dr. sheila appiah-pippim': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': False,  # Don't show prices for psychiatrists
        },
        'dr. shelia appiah-pippim': {  # Alternative spelling
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': False,
        },
        'dr. rebecca abalo': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': False,
        },
        'dr. lartey lorna': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': False,
        },
        'dr. mustapha dadzie': {
            'first_visit': Decimal('350.00'),
            'subsequent_visit': Decimal('300.00'),
            'specialty': 'Psychiatrist',
            'show_price': False,
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
        
        # Try exact match first
        if normalized_name in cls.DOCTOR_PRICING:
            pricing = cls.DOCTOR_PRICING[normalized_name].copy()
            pricing['is_specialist'] = True
            return pricing
        
        # Match by specialization - Physiotherapist gets GHS 250 first time, GHS 150 subsequent
        specialization = (doctor_staff.specialization or '').lower()
        specialty_name = ''
        try:
            if hasattr(doctor_staff, 'specialist_profile') and doctor_staff.specialist_profile:
                specialty_name = (doctor_staff.specialist_profile.specialty.name or '').lower()
        except Exception:
            pass
        combined_spec = f'{specialization} {specialty_name}'
        # Dental consultation (e.g. Dr Kumah) = GHS 150 so frontdesk input shows correct price
        if 'dental' in combined_spec:
            return {
                'first_visit': Decimal('150.00'),
                'subsequent_visit': Decimal('150.00'),
                'specialty': 'Dental Surgeon',
                'show_price': True,
                'is_specialist': True,
            }
        if 'physio' in combined_spec or 'physiotherapy' in combined_spec:
            return {
                'first_visit': Decimal('250.00'),
                'subsequent_visit': Decimal('150.00'),
                'specialty': 'Physiotherapist',
                'show_price': True,
                'is_specialist': True,
            }
        
        # Try partial matching (e.g., "Awah" matches "Dr. Awah")
        for key, pricing in cls.DOCTOR_PRICING.items():
            # Check if normalized name contains key or key contains normalized name
            if key in normalized_name or normalized_name in key:
                result = pricing.copy()
                result['is_specialist'] = True
                return result
        
        # Check by last name only (for cases like "Dr. Boakye")
        last_name = doctor_staff.user.last_name.lower().strip() if doctor_staff.user.last_name else ''
        for key, pricing in cls.DOCTOR_PRICING.items():
            if last_name and last_name in key:
                result = pricing.copy()
                result['is_specialist'] = True
                return result
        
        # Default pricing for other doctors
        return {
            'first_visit': cls.DEFAULT_CONSULTATION_FEE,
            'subsequent_visit': cls.DEFAULT_CONSULTATION_FEE,
            'specialty': doctor_staff.specialization or 'General Consultation',
            'show_price': False,  # Don't show prices for general doctors
            'is_specialist': False,
        }
    
    @classmethod
    def is_first_visit_to_doctor(cls, patient, doctor_staff):
        """
        Check if this is the patient's first visit to this specific doctor
        
        Args:
            patient: Patient object
            doctor_staff: Staff object representing the doctor
            
        Returns:
            bool: True if this is the first visit, False otherwise
        """
        if not patient or not doctor_staff:
            return True
        
        from .models import Encounter
        
        # Check if patient has any previous encounters with this doctor
        previous_encounters = Encounter.objects.filter(
            patient=patient,
            provider=doctor_staff,
            is_deleted=False
        ).exclude(status='cancelled').count()
        
        return previous_encounters == 0
    
    @classmethod
    def get_consultation_fee(cls, patient, doctor_staff, encounter_type=None, is_review_visit=False):
        """
        Get the appropriate consultation fee for a patient visiting a doctor
        
        Args:
            patient: Patient object
            doctor_staff: Staff object representing the doctor
            encounter_type: Optional encounter type (e.g., 'antenatal' for ANC pricing)
            is_review_visit: bool indicating if this is a review visit (no charge)
            
        Returns:
            Decimal: Consultation fee amount
        """
        if is_review_visit:
            return Decimal('0.00')
        
        pricing_info = cls.get_doctor_pricing_info(doctor_staff)
        
        # Special handling for Dr. Ali Samba - ANC visits
        if encounter_type and 'antenatal' in encounter_type.lower():
            full_name = (doctor_staff.user.get_full_name() or '').lower() if doctor_staff.user else ''
            if 'ali' in full_name and 'samba' in full_name:
                if 'anc_visit' in pricing_info:
                    return pricing_info['anc_visit']
        
        # Check if first visit
        is_first = cls.is_first_visit_to_doctor(patient, doctor_staff)
        
        if is_first:
            return pricing_info['first_visit']
        else:
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
