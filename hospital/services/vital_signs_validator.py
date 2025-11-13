"""
Vital Signs Validation Service
Automatically validates vital signs against normal ranges based on patient demographics
"""
from decimal import Decimal
from typing import Dict, Tuple, Optional


class VitalSignsValidator:
    """Validates vital signs against normal ranges based on age and gender"""
    
    @staticmethod
    def get_bp_normal_range(age: int, gender: str = None) -> Tuple[int, int, int, int]:
        """
        Get normal blood pressure range based on age
        Returns: (systolic_min, systolic_max, diastolic_min, diastolic_max)
        """
        if age < 1:
            # Infants
            return (70, 100, 40, 60)
        elif age < 3:
            # Toddlers
            return (80, 110, 50, 70)
        elif age < 6:
            # Preschool
            return (85, 115, 55, 75)
        elif age < 13:
            # School age
            return (95, 115, 60, 75)
        elif age < 18:
            # Adolescents
            return (105, 130, 65, 80)
        elif age < 65:
            # Adults
            return (90, 120, 60, 80)
        else:
            # Elderly (65+)
            return (90, 140, 60, 90)
    
    @staticmethod
    def get_pulse_normal_range(age: int) -> Tuple[int, int]:
        """
        Get normal heart rate range based on age
        Returns: (min, max)
        """
        if age < 1:
            return (100, 160)  # Infants
        elif age < 3:
            return (80, 130)   # Toddlers
        elif age < 6:
            return (75, 120)   # Preschool
        elif age < 13:
            return (70, 110)   # School age
        elif age < 18:
            return (60, 100)   # Adolescents
        else:
            return (60, 100)   # Adults
    
    @staticmethod
    def get_temp_normal_range() -> Tuple[float, float]:
        """Get normal temperature range (Celsius)"""
        return (36.1, 37.2)  # Normal body temperature
    
    @staticmethod
    def get_respiratory_rate_normal_range(age: int) -> Tuple[int, int]:
        """
        Get normal respiratory rate range based on age
        Returns: (min, max)
        """
        if age < 1:
            return (30, 50)   # Infants
        elif age < 3:
            return (24, 40)   # Toddlers
        elif age < 6:
            return (22, 34)   # Preschool
        elif age < 13:
            return (18, 30)   # School age
        elif age < 18:
            return (12, 20)   # Adolescents
        else:
            return (12, 20)   # Adults
    
    @staticmethod
    def get_spo2_normal_range() -> Tuple[int, int]:
        """Get normal SpO2 range"""
        return (95, 100)  # Normal oxygen saturation
    
    @staticmethod
    def validate_bp(systolic: Optional[Decimal], diastolic: Optional[Decimal], 
                   age: int, gender: str = None) -> Dict[str, any]:
        """
        Validate blood pressure
        Returns: {
            'status': 'normal' | 'high' | 'low' | 'critical_high' | 'critical_low',
            'message': str,
            'is_ok': bool
        }
        """
        if systolic is None or diastolic is None:
            return {'status': 'missing', 'message': 'Blood pressure not recorded', 'is_ok': None}
        
        sys_min, sys_max, dia_min, dia_max = VitalSignsValidator.get_bp_normal_range(age, gender)
        systolic = float(systolic)
        diastolic = float(diastolic)
        
        # Critical hypertension
        if systolic >= 180 or diastolic >= 120:
            return {
                'status': 'critical_high',
                'message': f'⚠️ CRITICAL: Hypertension Crisis (Systolic {systolic} ≥ 180 or Diastolic {diastolic} ≥ 120)',
                'is_ok': False
            }
        # Stage 2 Hypertension
        elif systolic >= 140 or diastolic >= 90:
            return {
                'status': 'high',
                'message': f'⚠️ HIGH: Stage 2 Hypertension (Normal: {sys_min}-{sys_max}/{dia_min}-{dia_max})',
                'is_ok': False
            }
        # Stage 1 Hypertension
        elif systolic >= 130 or diastolic >= 80:
            return {
                'status': 'high',
                'message': f'⚠️ ELEVATED: Stage 1 Hypertension (Normal: {sys_min}-{sys_max}/{dia_min}-{dia_max})',
                'is_ok': False
            }
        # Hypotension
        elif systolic < sys_min or diastolic < dia_min:
            if systolic < 90 or diastolic < 60:
                return {
                    'status': 'critical_low',
                    'message': f'⚠️ CRITICAL: Hypotension (Systolic {systolic} < 90 or Diastolic {diastolic} < 60)',
                    'is_ok': False
                }
            return {
                'status': 'low',
                'message': f'⚠️ LOW: Below normal range (Normal: {sys_min}-{sys_max}/{dia_min}-{dia_max})',
                'is_ok': False
            }
        # Normal
        else:
            return {
                'status': 'normal',
                'message': f'✅ NORMAL: Blood pressure is within normal range ({sys_min}-{sys_max}/{dia_min}-{dia_max})',
                'is_ok': True
            }
    
    @staticmethod
    def validate_pulse(pulse: Optional[int], age: int) -> Dict[str, any]:
        """Validate heart rate/pulse"""
        if pulse is None:
            return {'status': 'missing', 'message': 'Pulse not recorded', 'is_ok': None}
        
        min_rate, max_rate = VitalSignsValidator.get_pulse_normal_range(age)
        
        if pulse > max_rate:
            if pulse > max_rate + 20:
                return {
                    'status': 'critical_high',
                    'message': f'⚠️ CRITICAL: Severe Tachycardia ({pulse} bpm, Normal: {min_rate}-{max_rate})',
                    'is_ok': False
                }
            return {
                'status': 'high',
                'message': f'⚠️ HIGH: Tachycardia ({pulse} bpm, Normal: {min_rate}-{max_rate})',
                'is_ok': False
            }
        elif pulse < min_rate:
            if pulse < min_rate - 20:
                return {
                    'status': 'critical_low',
                    'message': f'⚠️ CRITICAL: Severe Bradycardia ({pulse} bpm, Normal: {min_rate}-{max_rate})',
                    'is_ok': False
                }
            return {
                'status': 'low',
                'message': f'⚠️ LOW: Bradycardia ({pulse} bpm, Normal: {min_rate}-{max_rate})',
                'is_ok': False
            }
        else:
            return {
                'status': 'normal',
                'message': f'✅ NORMAL: Heart rate is within normal range ({min_rate}-{max_rate} bpm)',
                'is_ok': True
            }
    
    @staticmethod
    def validate_temperature(temp: Optional[Decimal]) -> Dict[str, any]:
        """Validate temperature"""
        if temp is None:
            return {'status': 'missing', 'message': 'Temperature not recorded', 'is_ok': None}
        
        min_temp, max_temp = VitalSignsValidator.get_temp_normal_range()
        temp_float = float(temp)
        
        if temp_float >= 38.0:
            if temp_float >= 39.5:
                return {
                    'status': 'critical_high',
                    'message': f'⚠️ CRITICAL: High Fever ({temp_float}°C, Normal: {min_temp}-{max_temp}°C)',
                    'is_ok': False
                }
            return {
                'status': 'high',
                'message': f'⚠️ HIGH: Fever ({temp_float}°C, Normal: {min_temp}-{max_temp}°C)',
                'is_ok': False
            }
        elif temp_float < min_temp:
            return {
                'status': 'critical_low',
                'message': f'⚠️ CRITICAL: Hypothermia ({temp_float}°C, Normal: {min_temp}-{max_temp}°C)',
                'is_ok': False
            }
        else:
            return {
                'status': 'normal',
                'message': f'✅ NORMAL: Temperature is within normal range ({min_temp}-{max_temp}°C)',
                'is_ok': True
            }
    
    @staticmethod
    def validate_respiratory_rate(rr: Optional[int], age: int) -> Dict[str, any]:
        """Validate respiratory rate"""
        if rr is None:
            return {'status': 'missing', 'message': 'Respiratory rate not recorded', 'is_ok': None}
        
        min_rate, max_rate = VitalSignsValidator.get_respiratory_rate_normal_range(age)
        
        if rr > max_rate:
            if rr > max_rate + 10:
                return {
                    'status': 'critical_high',
                    'message': f'⚠️ CRITICAL: Severe Tachypnea ({rr}/min, Normal: {min_rate}-{max_rate}/min)',
                    'is_ok': False
                }
            return {
                'status': 'high',
                'message': f'⚠️ HIGH: Tachypnea ({rr}/min, Normal: {min_rate}-{max_rate}/min)',
                'is_ok': False
            }
        elif rr < min_rate:
            return {
                'status': 'critical_low',
                'message': f'⚠️ CRITICAL: Bradypnea ({rr}/min, Normal: {min_rate}-{max_rate}/min)',
                'is_ok': False
            }
        else:
            return {
                'status': 'normal',
                'message': f'✅ NORMAL: Respiratory rate is within normal range ({min_rate}-{max_rate}/min)',
                'is_ok': True
            }
    
    @staticmethod
    def validate_spo2(spo2: Optional[int]) -> Dict[str, any]:
        """Validate oxygen saturation"""
        if spo2 is None:
            return {'status': 'missing', 'message': 'SpO2 not recorded', 'is_ok': None}
        
        min_sat, max_sat = VitalSignsValidator.get_spo2_normal_range()
        
        if spo2 < 90:
            return {
                'status': 'critical_low',
                'message': f'⚠️ CRITICAL: Severe Hypoxia ({spo2}%, Normal: {min_sat}-{max_sat}%)',
                'is_ok': False
            }
        elif spo2 < min_sat:
            return {
                'status': 'low',
                'message': f'⚠️ LOW: Mild Hypoxia ({spo2}%, Normal: {min_sat}-{max_sat}%)',
                'is_ok': False
            }
        else:
            return {
                'status': 'normal',
                'message': f'✅ NORMAL: Oxygen saturation is within normal range ({min_sat}-{max_sat}%)',
                'is_ok': True
            }
    
    @staticmethod
    def validate_all_vitals(vitals: Dict, patient_age: int, patient_gender: str = None) -> Dict[str, Dict]:
        """
        Validate all vital signs for a patient
        Returns dictionary with validation results for each vital sign
        """
        results = {}
        
        # Blood Pressure
        results['bp'] = VitalSignsValidator.validate_bp(
            vitals.get('systolic_bp'),
            vitals.get('diastolic_bp'),
            patient_age,
            patient_gender
        )
        
        # Pulse
        results['pulse'] = VitalSignsValidator.validate_pulse(
            vitals.get('pulse'),
            patient_age
        )
        
        # Temperature
        results['temperature'] = VitalSignsValidator.validate_temperature(
            vitals.get('temperature')
        )
        
        # Respiratory Rate
        results['respiratory_rate'] = VitalSignsValidator.validate_respiratory_rate(
            vitals.get('respiratory_rate'),
            patient_age
        )
        
        # SpO2
        results['spo2'] = VitalSignsValidator.validate_spo2(
            vitals.get('spo2')
        )
        
        # Overall status
        all_statuses = [r['status'] for r in results.values() if r.get('is_ok') is not None]
        critical_count = sum(1 for s in all_statuses if 'critical' in s)
        abnormal_count = sum(1 for s in all_statuses if s not in ['normal', 'missing'])
        
        if critical_count > 0:
            results['overall'] = {
                'status': 'critical',
                'message': f'⚠️ CRITICAL: {critical_count} critical vital sign(s) detected',
                'is_ok': False
            }
        elif abnormal_count > 0:
            results['overall'] = {
                'status': 'abnormal',
                'message': f'⚠️ WARNING: {abnormal_count} abnormal vital sign(s) detected',
                'is_ok': False
            }
        else:
            results['overall'] = {
                'status': 'normal',
                'message': '✅ All vital signs are within normal range',
                'is_ok': True
            }
        
        return results

