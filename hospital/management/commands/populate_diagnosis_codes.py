"""
Management command to populate WHO ICD-10 diagnosis codes
Common diagnoses used in clinical practice
"""
from django.core.management.base import BaseCommand
from hospital.models_diagnosis import DiagnosisCode


class Command(BaseCommand):
    help = 'Populate diagnosis bank with common WHO ICD-10 codes'

    def handle(self, *args, **options):
        self.stdout.write('Populating WHO ICD-10 Diagnosis Codes...')
        
        # Common diagnoses organized by category
        diagnoses = [
            # RESPIRATORY DISEASES (J00-J99)
            {'code': 'J00', 'description': 'Acute nasopharyngitis (common cold)', 
             'short_description': 'Common Cold', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J01.90', 'description': 'Acute sinusitis, unspecified', 
             'short_description': 'Acute Sinusitis', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J02.9', 'description': 'Acute pharyngitis, unspecified', 
             'short_description': 'Acute Pharyngitis', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J03.90', 'description': 'Acute tonsillitis, unspecified', 
             'short_description': 'Acute Tonsillitis', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J06.9', 'description': 'Acute upper respiratory infection, unspecified', 
             'short_description': 'Upper Respiratory Infection', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J18.9', 'description': 'Pneumonia, unspecified organism', 
             'short_description': 'Pneumonia', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J20.9', 'description': 'Acute bronchitis, unspecified', 
             'short_description': 'Acute Bronchitis', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J40', 'description': 'Bronchitis, not specified as acute or chronic', 
             'short_description': 'Bronchitis', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J45.9', 'description': 'Asthma, unspecified', 
             'short_description': 'Asthma', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            {'code': 'J44.9', 'description': 'Chronic obstructive pulmonary disease, unspecified', 
             'short_description': 'COPD', 'category': 'respiratory', 'chapter': 'J00-J99', 'is_common': True},
            
            # INFECTIOUS DISEASES (A00-B99)
            {'code': 'A09', 'description': 'Infectious gastroenteritis and colitis, unspecified', 
             'short_description': 'Gastroenteritis', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': True},
            {'code': 'A41.9', 'description': 'Sepsis, unspecified organism', 
             'short_description': 'Sepsis', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': True},
            {'code': 'B34.9', 'description': 'Viral infection, unspecified', 
             'short_description': 'Viral Infection', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': True},
            {'code': 'A15.0', 'description': 'Tuberculosis of lung', 
             'short_description': 'Pulmonary Tuberculosis', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': True},
            {'code': 'B19.9', 'description': 'Unspecified viral hepatitis', 
             'short_description': 'Viral Hepatitis', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': False},
            {'code': 'A06.0', 'description': 'Acute amebic dysentery', 
             'short_description': 'Amebic Dysentery', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': False},
            {'code': 'B50.9', 'description': 'Plasmodium falciparum malaria, unspecified', 
             'short_description': 'Malaria (Falciparum)', 'category': 'infectious', 'chapter': 'A00-B99', 'is_common': True},
            
            # CIRCULATORY SYSTEM (I00-I99)
            {'code': 'I10', 'description': 'Essential (primary) hypertension', 
             'short_description': 'Hypertension', 'category': 'circulatory', 'chapter': 'I00-I99', 'is_common': True},
            {'code': 'I25.10', 'description': 'Atherosclerotic heart disease of native coronary artery without angina pectoris', 
             'short_description': 'Coronary Artery Disease', 'category': 'circulatory', 'chapter': 'I00-I99', 'is_common': True},
            {'code': 'I21.9', 'description': 'Acute myocardial infarction, unspecified', 
             'short_description': 'Heart Attack (MI)', 'category': 'circulatory', 'chapter': 'I00-I99', 'is_common': True},
            {'code': 'I50.9', 'description': 'Heart failure, unspecified', 
             'short_description': 'Heart Failure', 'category': 'circulatory', 'chapter': 'I00-I99', 'is_common': True},
            {'code': 'I48.91', 'description': 'Unspecified atrial fibrillation', 
             'short_description': 'Atrial Fibrillation', 'category': 'circulatory', 'chapter': 'I00-I99', 'is_common': True},
            {'code': 'I63.9', 'description': 'Cerebral infarction, unspecified', 
             'short_description': 'Stroke (Ischemic)', 'category': 'circulatory', 'chapter': 'I00-I99', 'is_common': True},
            
            # ENDOCRINE AND METABOLIC (E00-E89)
            {'code': 'E11.9', 'description': 'Type 2 diabetes mellitus without complications', 
             'short_description': 'Type 2 Diabetes', 'category': 'endocrine', 'chapter': 'E00-E89', 'is_common': True},
            {'code': 'E10.9', 'description': 'Type 1 diabetes mellitus without complications', 
             'short_description': 'Type 1 Diabetes', 'category': 'endocrine', 'chapter': 'E00-E89', 'is_common': True},
            {'code': 'E66.9', 'description': 'Obesity, unspecified', 
             'short_description': 'Obesity', 'category': 'endocrine', 'chapter': 'E00-E89', 'is_common': True},
            {'code': 'E78.5', 'description': 'Hyperlipidemia, unspecified', 
             'short_description': 'High Cholesterol', 'category': 'endocrine', 'chapter': 'E00-E89', 'is_common': True},
            {'code': 'E03.9', 'description': 'Hypothyroidism, unspecified', 
             'short_description': 'Hypothyroidism', 'category': 'endocrine', 'chapter': 'E00-E89', 'is_common': True},
            {'code': 'E05.90', 'description': 'Thyrotoxicosis, unspecified', 
             'short_description': 'Hyperthyroidism', 'category': 'endocrine', 'chapter': 'E00-E89', 'is_common': False},
            
            # DIGESTIVE SYSTEM (K00-K95)
            {'code': 'K21.9', 'description': 'Gastro-esophageal reflux disease without esophagitis', 
             'short_description': 'GERD', 'category': 'digestive', 'chapter': 'K00-K95', 'is_common': True},
            {'code': 'K29.70', 'description': 'Gastritis, unspecified, without bleeding', 
             'short_description': 'Gastritis', 'category': 'digestive', 'chapter': 'K00-K95', 'is_common': True},
            {'code': 'K35.80', 'description': 'Unspecified acute appendicitis', 
             'short_description': 'Acute Appendicitis', 'category': 'digestive', 'chapter': 'K00-K95', 'is_common': True},
            {'code': 'K52.9', 'description': 'Noninfective gastroenteritis and colitis, unspecified', 
             'short_description': 'Gastroenteritis (Non-infectious)', 'category': 'digestive', 'chapter': 'K00-K95', 'is_common': True},
            {'code': 'K80.20', 'description': 'Calculus of gallbladder without cholecystitis without obstruction', 
             'short_description': 'Gallstones', 'category': 'digestive', 'chapter': 'K00-K95', 'is_common': True},
            
            # GENITOURINARY SYSTEM (N00-N99)
            {'code': 'N39.0', 'description': 'Urinary tract infection, site not specified', 
             'short_description': 'Urinary Tract Infection (UTI)', 'category': 'genitourinary', 'chapter': 'N00-N99', 'is_common': True},
            {'code': 'N18.9', 'description': 'Chronic kidney disease, unspecified', 
             'short_description': 'Chronic Kidney Disease', 'category': 'genitourinary', 'chapter': 'N00-N99', 'is_common': True},
            {'code': 'N20.0', 'description': 'Calculus of kidney', 
             'short_description': 'Kidney Stone', 'category': 'genitourinary', 'chapter': 'N00-N99', 'is_common': True},
            
            # MUSCULOSKELETAL (M00-M99)
            {'code': 'M54.5', 'description': 'Low back pain', 
             'short_description': 'Low Back Pain', 'category': 'musculoskeletal', 'chapter': 'M00-M99', 'is_common': True},
            {'code': 'M25.50', 'description': 'Pain in unspecified joint', 
             'short_description': 'Joint Pain', 'category': 'musculoskeletal', 'chapter': 'M00-M99', 'is_common': True},
            {'code': 'M79.1', 'description': 'Myalgia', 
             'short_description': 'Muscle Pain', 'category': 'musculoskeletal', 'chapter': 'M00-M99', 'is_common': True},
            {'code': 'M19.90', 'description': 'Unspecified osteoarthritis, unspecified site', 
             'short_description': 'Osteoarthritis', 'category': 'musculoskeletal', 'chapter': 'M00-M99', 'is_common': True},
            
            # NERVOUS SYSTEM (G00-G99)
            {'code': 'G43.909', 'description': 'Migraine, unspecified, not intractable, without status migrainosus', 
             'short_description': 'Migraine', 'category': 'nervous', 'chapter': 'G00-G99', 'is_common': True},
            {'code': 'G44.1', 'description': 'Vascular headache, not elsewhere classified', 
             'short_description': 'Headache', 'category': 'nervous', 'chapter': 'G00-G99', 'is_common': True},
            {'code': 'G40.909', 'description': 'Epilepsy, unspecified, not intractable, without status epilepticus', 
             'short_description': 'Epilepsy', 'category': 'nervous', 'chapter': 'G00-G99', 'is_common': True},
            
            # MENTAL AND BEHAVIORAL (F00-F99)
            {'code': 'F32.9', 'description': 'Major depressive disorder, single episode, unspecified', 
             'short_description': 'Depression', 'category': 'mental', 'chapter': 'F00-F99', 'is_common': True},
            {'code': 'F41.9', 'description': 'Anxiety disorder, unspecified', 
             'short_description': 'Anxiety Disorder', 'category': 'mental', 'chapter': 'F00-F99', 'is_common': True},
            
            # SYMPTOMS AND SIGNS (R00-R99)
            {'code': 'R50.9', 'description': 'Fever, unspecified', 
             'short_description': 'Fever', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R51', 'description': 'Headache', 
             'short_description': 'Headache', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R10.9', 'description': 'Unspecified abdominal pain', 
             'short_description': 'Abdominal Pain', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R05', 'description': 'Cough', 
             'short_description': 'Cough', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R06.00', 'description': 'Dyspnea, unspecified', 
             'short_description': 'Shortness of Breath', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R11.0', 'description': 'Nausea', 
             'short_description': 'Nausea', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R11.10', 'description': 'Vomiting, unspecified', 
             'short_description': 'Vomiting', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            {'code': 'R19.7', 'description': 'Diarrhea, unspecified', 
             'short_description': 'Diarrhea', 'category': 'symptoms', 'chapter': 'R00-R99', 'is_common': True},
            
            # INJURY AND POISONING (S00-T88)
            {'code': 'S06.0X0A', 'description': 'Concussion without loss of consciousness, initial encounter', 
             'short_description': 'Concussion', 'category': 'injury', 'chapter': 'S00-T98', 'is_common': True},
            {'code': 'S82.90XA', 'description': 'Unspecified fracture of unspecified lower leg, initial encounter', 
             'short_description': 'Leg Fracture', 'category': 'injury', 'chapter': 'S00-T98', 'is_common': False},
            {'code': 'T14.90', 'description': 'Injury, unspecified', 
             'short_description': 'Injury (Unspecified)', 'category': 'injury', 'chapter': 'S00-T98', 'is_common': False},
            
            # PREGNANCY AND CHILDBIRTH (O00-O9A)
            {'code': 'O80', 'description': 'Encounter for full-term uncomplicated delivery', 
             'short_description': 'Normal Delivery', 'category': 'pregnancy', 'chapter': 'O00-O9A', 'is_common': True},
            {'code': 'O21.9', 'description': 'Vomiting of pregnancy, unspecified', 
             'short_description': 'Morning Sickness', 'category': 'pregnancy', 'chapter': 'O00-O9A', 'is_common': True},
        ]
        
        created_count = 0
        updated_count = 0
        
        for diag_data in diagnoses:
            code = diag_data.pop('code')
            diagnosis, created = DiagnosisCode.objects.update_or_create(
                code=code,
                defaults=diag_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'  [+] Created: {diagnosis.code} - {diagnosis.short_description}')
            else:
                updated_count += 1
                self.stdout.write(f'  [~] Updated: {diagnosis.code} - {diagnosis.short_description}')
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[SUCCESS] Populated diagnosis bank:'
            f'\n  - Created: {created_count} new diagnoses'
            f'\n  - Updated: {updated_count} existing diagnoses'
            f'\n  - Total: {DiagnosisCode.objects.filter(is_deleted=False).count()} diagnoses in bank'
        ))

