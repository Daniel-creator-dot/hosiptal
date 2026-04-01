"""
Management command to seed common service codes with prices for Ghanaian healthcare
"""
from django.core.management.base import BaseCommand
from hospital.models import ServiceCode, Payer
from hospital.models_pricing import DefaultPrice, PayerPrice
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed common service codes with prices for billing in Ghanaian healthcare facilities'

    def handle(self, *args, **options):
        # Common service codes with categories and typical prices in Ghana
        service_codes = [
            # Consultation Services
            {'code': 'CONS-GEN', 'description': 'General Consultation', 'category': 'Consultation', 'price': Decimal('50.00')},
            {'code': 'CONS-SPEC', 'description': 'Specialist Consultation', 'category': 'Consultation', 'price': Decimal('100.00')},
            {'code': 'CONS-DENT', 'description': 'Dental Consultation', 'category': 'Consultation', 'price': Decimal('80.00')},
            {'code': 'CONS-EYE', 'description': 'Eye Consultation', 'category': 'Consultation', 'price': Decimal('80.00')},
            {'code': 'CONS-CARD', 'description': 'Cardiology Consultation', 'category': 'Consultation', 'price': Decimal('120.00')},
            {'code': 'CONS-EMER', 'description': 'Emergency Consultation', 'category': 'Consultation', 'price': Decimal('100.00')},
            {'code': 'CONS-FOLLOW', 'description': 'Follow-up Consultation', 'category': 'Consultation', 'price': Decimal('30.00')},
            
            # Registration & Administrative
            {'code': 'REG', 'description': 'Patient Registration Fee', 'category': 'Registration', 'price': Decimal('50.00')},
            {'code': 'REG-NEW', 'description': 'New Patient Registration', 'category': 'Administration', 'price': Decimal('10.00')},
            {'code': 'REG-FILE', 'description': 'Medical Records Retrieval', 'category': 'Administration', 'price': Decimal('5.00')},
            {'code': 'REG-CERT', 'description': 'Medical Certificate', 'category': 'Administration', 'price': Decimal('20.00')},
            {'code': 'REG-SICK', 'description': 'Sick Leave Certificate', 'category': 'Administration', 'price': Decimal('15.00')},
            
            # Vital Signs & Monitoring
            {'code': 'VITALS', 'description': 'Vital Signs Recording', 'category': 'Monitoring', 'price': Decimal('5.00')},
            {'code': 'BP-CHECK', 'description': 'Blood Pressure Check', 'category': 'Monitoring', 'price': Decimal('5.00')},
            {'code': 'ECG', 'description': 'Electrocardiogram (ECG)', 'category': 'Diagnostic', 'price': Decimal('40.00')},
            {'code': 'ECHO', 'description': 'Echocardiogram', 'category': 'Diagnostic', 'price': Decimal('150.00')},
            
            # Imaging Services
            {'code': 'XRAY-CHEST', 'description': 'Chest X-Ray', 'category': 'Imaging', 'price': Decimal('60.00')},
            {'code': 'XRAY-LIMB', 'description': 'Limb X-Ray', 'category': 'Imaging', 'price': Decimal('50.00')},
            {'code': 'XRAY-SKULL', 'description': 'Skull X-Ray', 'category': 'Imaging', 'price': Decimal('70.00')},
            {'code': 'XRAY-SPINE', 'description': 'Spine X-Ray', 'category': 'Imaging', 'price': Decimal('80.00')},
            {'code': 'ULTRASOUND-ABD', 'description': 'Abdominal Ultrasound', 'category': 'Imaging', 'price': Decimal('100.00')},
            {'code': 'ULTRASOUND-PELV', 'description': 'Pelvic Ultrasound', 'category': 'Imaging', 'price': Decimal('100.00')},
            {'code': 'ULTRASOUND-PREG', 'description': 'Pregnancy Ultrasound', 'category': 'Imaging', 'price': Decimal('80.00')},
            {'code': 'CT-SCAN', 'description': 'CT Scan', 'category': 'Imaging', 'price': Decimal('300.00')},
            {'code': 'MRI', 'description': 'MRI Scan', 'category': 'Imaging', 'price': Decimal('500.00')},
            
            # Laboratory Services (processing fees)
            {'code': 'LAB-PROC', 'description': 'Laboratory Processing Fee', 'category': 'Laboratory', 'price': Decimal('10.00')},
            {'code': 'LAB-URGENT', 'description': 'Urgent Lab Test Processing', 'category': 'Laboratory', 'price': Decimal('20.00')},
            
            # Pharmacy Services
            {'code': 'PHARM-DISP', 'description': 'Pharmacy Dispensing Fee', 'category': 'Pharmacy', 'price': Decimal('5.00')},
            {'code': 'PHARM-COUNSEL', 'description': 'Pharmacy Counseling', 'category': 'Pharmacy', 'price': Decimal('10.00')},
            
            # Admission & Ward Services (Detention vs Admission)
            {'code': 'DETENTION', 'description': 'Detention (< 12 hours)', 'category': 'accommodation', 'price': Decimal('120.00')},
            {'code': 'ADM-ACCOM', 'description': 'Admission accommodation (≥ 12 hrs)', 'category': 'accommodation', 'price': Decimal('150.00')},
            {'code': 'ADM-DOCTOR-CARE', 'description': 'Doctor care (admission)', 'category': 'accommodation', 'price': Decimal('80.00')},
            {'code': 'ADM-NURSING-CARE', 'description': 'Nursing care (admission)', 'category': 'accommodation', 'price': Decimal('70.00')},
            {'code': 'ADM-FEE', 'description': 'Admission Fee', 'category': 'Administration', 'price': Decimal('50.00')},
            {'code': 'WARD-GEN', 'description': 'General Ward Daily Charge', 'category': 'Ward', 'price': Decimal('30.00')},
            {'code': 'WARD-PRIVATE', 'description': 'Private Ward Daily Charge', 'category': 'Ward', 'price': Decimal('80.00')},
            {'code': 'WARD-SEMI', 'description': 'Semi-Private Ward Daily Charge', 'category': 'Ward', 'price': Decimal('50.00')},
            {'code': 'WARD-ICU', 'description': 'ICU Daily Charge', 'category': 'Ward', 'price': Decimal('200.00')},
            {'code': 'WARD-MAT', 'description': 'Maternity Ward Daily Charge', 'category': 'Ward', 'price': Decimal('60.00')},
            
            # Procedures
            {'code': 'PROC-DRESS', 'description': 'Wound Dressing', 'category': 'Procedure', 'price': Decimal('25.00')},
            {'code': 'PROC-SUTURE', 'description': 'Suture Removal', 'category': 'Procedure', 'price': Decimal('20.00')},
            {'code': 'PROC-INJECT', 'description': 'Injection Administration', 'category': 'Procedure', 'price': Decimal('10.00')},
            {'code': 'PROC-IV', 'description': 'IV Cannulation', 'category': 'Procedure', 'price': Decimal('15.00')},
            {'code': 'PROC-BLOOD', 'description': 'Blood Sampling', 'category': 'Procedure', 'price': Decimal('10.00')},
            {'code': 'PROC-NEBUL', 'description': 'Nebulization', 'category': 'Procedure', 'price': Decimal('25.00')},
            {'code': 'PROC-OXYGEN', 'description': 'Oxygen Administration', 'category': 'Procedure', 'price': Decimal('30.00')},
            
            # Dental Procedures
            {'code': 'DENT-CLEAN', 'description': 'Teeth Cleaning', 'category': 'Dental', 'price': Decimal('80.00')},
            {'code': 'DENT-EXTR', 'description': 'Tooth Extraction', 'category': 'Dental', 'price': Decimal('50.00')},
            {'code': 'DENT-FILL', 'description': 'Tooth Filling', 'category': 'Dental', 'price': Decimal('100.00')},
            {'code': 'DENT-ROOT', 'description': 'Root Canal Treatment', 'category': 'Dental', 'price': Decimal('300.00')},
            {'code': 'DENT-CROWN', 'description': 'Dental Crown', 'category': 'Dental', 'price': Decimal('500.00')},
            {'code': 'DENT-SCALE', 'description': 'Scaling & Polishing', 'category': 'Dental', 'price': Decimal('80.00')},
            
            # Maternity Services
            {'code': 'MAT-ANC', 'description': 'Antenatal Care Visit', 'category': 'Maternity', 'price': Decimal('50.00')},
            {'code': 'MAT-DELIVER', 'description': 'Delivery Fee', 'category': 'Maternity', 'price': Decimal('2800.00')},
            {'code': 'MAT-MIDWIFE', 'description': 'Midwife Care', 'category': 'Maternity', 'price': Decimal('300.00')},
            {'code': 'MAT-CSECT', 'description': 'Caesarean Section', 'category': 'Maternity', 'price': Decimal('1500.00')},
            {'code': 'MAT-PNC', 'description': 'Postnatal Care Visit', 'category': 'Maternity', 'price': Decimal('40.00')},
            
            # Surgery & Theatre
            {'code': 'SURG-MINOR', 'description': 'Minor Surgery', 'category': 'Surgery', 'price': Decimal('300.00')},
            {'code': 'SURG-MAJOR', 'description': 'Major Surgery', 'category': 'Surgery', 'price': Decimal('1000.00')},
            {'code': 'THEATRE', 'description': 'Theatre Fee', 'category': 'Surgery', 'price': Decimal('200.00')},
            {'code': 'ANESTH', 'description': 'Anesthesia Fee', 'category': 'Surgery', 'price': Decimal('300.00')},
            
            # Emergency Services
            {'code': 'EMER-TRIAGE', 'description': 'Emergency Triage', 'category': 'Emergency', 'price': Decimal('20.00')},
            {'code': 'EMER-STAB', 'description': 'Emergency Stabilization', 'category': 'Emergency', 'price': Decimal('100.00')},
            {'code': 'AMBULANCE', 'description': 'Ambulance Service', 'category': 'Emergency', 'price': Decimal('150.00')},
            
            # Other Services
            {'code': 'EYE-TEST', 'description': 'Eye Test/Vision Screening', 'category': 'Diagnostic', 'price': Decimal('30.00')},
            {'code': 'HEAR-TEST', 'description': 'Hearing Test', 'category': 'Diagnostic', 'price': Decimal('50.00')},
            # Physiotherapy – cash patient prices
            {'code': 'PHYSIO', 'description': 'Physiotherapy (First Time)', 'category': 'Therapy', 'price': Decimal('250.00')},
            {'code': 'PHYSIO-SUB', 'description': 'Physiotherapy (Subsequent)', 'category': 'Therapy', 'price': Decimal('150.00')},
            {'code': 'NUTRITION', 'description': 'Nutrition Consultation', 'category': 'Consultation', 'price': Decimal('50.00')},
        ]
        
        # Get or create default payer (Cash/Self-pay)
        default_payer, _ = Payer.objects.get_or_create(
            name='Cash / Self-Pay',
            defaults={
                'payer_type': 'self_pay',
                'is_active': True,
            }
        )
        
        created_count = 0
        updated_count = 0
        
        for service_data in service_codes:
            # Create or update ServiceCode
            service_code, created = ServiceCode.objects.update_or_create(
                code=service_data['code'],
                defaults={
                    'description': service_data['description'],
                    'category': service_data['category'],
                    'is_active': True,
                }
            )
            
            # Create PriceBook entry for default payer
            from hospital.models import PriceBook
            price_book, pb_created = PriceBook.objects.update_or_create(
                payer=default_payer,
                service_code=service_code,
                defaults={
                    'unit_price': service_data['price'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {service_code.code} - {service_code.description} - GHS {service_data["price"]}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {service_code.code} - {service_code.description} - GHS {service_data["price"]}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully seeded service codes with prices!\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Total: {len(service_codes)}'
            )
        )





































