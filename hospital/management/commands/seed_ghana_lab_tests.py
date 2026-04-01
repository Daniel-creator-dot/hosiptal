"""
Management command to seed common laboratory tests used in Ghana
"""
from django.core.management.base import BaseCommand
from hospital.models import LabTest
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed common laboratory tests used in Ghanaian healthcare facilities'

    def handle(self, *args, **options):
        # Common lab tests in Ghana with typical pricing in GHS
        lab_tests = [
            # Hematology
            {'code': 'CBC', 'name': 'Complete Blood Count (CBC)', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'FBC', 'name': 'Full Blood Count', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'HB', 'name': 'Hemoglobin (Hb)', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('15.00')},
            {'code': 'HCT', 'name': 'Hematocrit (PCV)', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('15.00')},
            {'code': 'PLT', 'name': 'Platelet Count', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('20.00')},
            {'code': 'ESR', 'name': 'Erythrocyte Sedimentation Rate (ESR)', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('25.00')},
            {'code': 'RBC', 'name': 'Red Blood Cell Count', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('20.00')},
            {'code': 'WBC', 'name': 'White Blood Cell Count', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('20.00')},
            {'code': 'DIFF', 'name': 'Blood Film/Differential Count', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'RETIC', 'name': 'Reticulocyte Count', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'BF', 'name': 'Blood Film', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'BF-MP', 'name': 'Blood Film for Malaria Parasite (Microscopy)', 'specimen_type': 'Whole Blood', 'tat_minutes': 45, 'price': Decimal('30.00')},
            
            # Malaria Tests
            {'code': 'MP-RDT', 'name': 'Malaria Rapid Diagnostic Test (RDT)', 'specimen_type': 'Whole Blood', 'tat_minutes': 15, 'price': Decimal('25.00')},
            {'code': 'MP-BS', 'name': 'Malaria Blood Smear (Microscopy)', 'specimen_type': 'Whole Blood', 'tat_minutes': 45, 'price': Decimal('30.00')},
            {'code': 'MP-QBC', 'name': 'Malaria Quantitative Buffy Coat', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('40.00')},
            
            # Blood Chemistry
            {'code': 'FBS', 'name': 'Fasting Blood Sugar (FBS)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('25.00')},
            {'code': 'RBS', 'name': 'Random Blood Sugar (RBS)', 'specimen_type': 'Serum', 'tat_minutes': 30, 'price': Decimal('25.00')},
            {'code': 'OGTT', 'name': 'Oral Glucose Tolerance Test (OGTT)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'HBA1C', 'name': 'Hemoglobin A1C (HbA1c)', 'specimen_type': 'Whole Blood', 'tat_minutes': 120, 'price': Decimal('60.00')},
            {'code': 'CREAT', 'name': 'Creatinine', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'UREA', 'name': 'Urea', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'BUN', 'name': 'Blood Urea Nitrogen (BUN)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'KFT', 'name': 'Kidney Function Test (Urea & Creatinine)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'LFT', 'name': 'Liver Function Test (LFT)', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('80.00')},
            {'code': 'ALT', 'name': 'Alanine Aminotransferase (ALT/SGPT)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'AST', 'name': 'Aspartate Aminotransferase (AST/SGOT)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'ALP', 'name': 'Alkaline Phosphatase (ALP)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('35.00')},
            {'code': 'TBIL', 'name': 'Total Bilirubin', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'DBIL', 'name': 'Direct Bilirubin', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'TPROT', 'name': 'Total Protein', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('35.00')},
            {'code': 'ALB', 'name': 'Albumin', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('35.00')},
            
            # Lipid Profile
            {'code': 'CHOL', 'name': 'Total Cholesterol', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'HDL', 'name': 'High Density Lipoprotein (HDL)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'LDL', 'name': 'Low Density Lipoprotein (LDL)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'TG', 'name': 'Triglycerides', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'LIPID', 'name': 'Lipid Profile (Complete)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('140.00')},
            
            # Electrolytes
            {'code': 'NA', 'name': 'Sodium (Na)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'K', 'name': 'Potassium (K)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'CL', 'name': 'Chloride (Cl)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'HCO3', 'name': 'Bicarbonate (HCO3)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'UEC', 'name': 'Urea, Electrolytes & Creatinine (UEC)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('80.00')},
            {'code': 'ELECT', 'name': 'Electrolytes Panel', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('100.00')},
            
            # Infectious Diseases
            {'code': 'HIV', 'name': 'HIV Test (Rapid)', 'specimen_type': 'Whole Blood/Serum', 'tat_minutes': 20, 'price': Decimal('50.00')},
            {'code': 'HIV-ELISA', 'name': 'HIV ELISA', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'HBsAg', 'name': 'Hepatitis B Surface Antigen (HBsAg)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'HBV', 'name': 'Hepatitis B Profile', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('150.00')},
            {'code': 'HBV-VL', 'name': 'Hepatitis B Viral Load', 'specimen_type': 'Plasma', 'tat_minutes': 2880, 'price': Decimal('450.00')},
            {'code': 'HCV', 'name': 'Hepatitis C Antibody', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('60.00')},
            {'code': 'VDRL', 'name': 'VDRL (Syphilis Screening)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'TPHA', 'name': 'TPHA (Syphilis Confirmation)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('60.00')},
            {'code': 'TYPH-RDT', 'name': 'Typhoid Rapid Test', 'specimen_type': 'Whole Blood', 'tat_minutes': 20, 'price': Decimal('35.00')},
            {'code': 'WIDAL', 'name': 'Widal Test (Typhoid)', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('60.00')},
            {'code': 'TB-MAN', 'name': 'Mantoux Test (TB)', 'specimen_type': 'Intradermal', 'tat_minutes': 2880, 'price': Decimal('40.00')},
            {'code': 'TB-GENE', 'name': 'TB GeneXpert', 'specimen_type': 'Sputum', 'tat_minutes': 120, 'price': Decimal('150.00')},
            {'code': 'AFB', 'name': 'Acid Fast Bacilli (AFB)', 'specimen_type': 'Sputum', 'tat_minutes': 120, 'price': Decimal('50.00')},
            {'code': 'H-PYLORI', 'name': 'H. pylori (Helicobacter pylori)', 'specimen_type': 'Stool', 'tat_minutes': 60, 'price': Decimal('135.00')},
            {'code': 'CRP', 'name': 'C-Reactive Protein (CRP)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'ASO', 'name': 'Anti-Streptolysin O (ASO)', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('60.00')},
            {'code': 'RF', 'name': 'Rheumatoid Factor (RF)', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('60.00')},
            
            # Urine Tests
            {'code': 'URINE', 'name': 'Urinalysis (Routine)', 'specimen_type': 'Urine', 'tat_minutes': 30, 'price': Decimal('25.00')},
            {'code': 'URINE-MS', 'name': 'Urine Microscopy', 'specimen_type': 'Urine', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'URINE-C&S', 'name': 'Urine Culture & Sensitivity', 'specimen_type': 'Urine', 'tat_minutes': 4320, 'price': Decimal('80.00')},
            {'code': 'URINE-PREGN', 'name': 'Urine Pregnancy Test', 'specimen_type': 'Urine', 'tat_minutes': 15, 'price': Decimal('20.00')},
            {'code': 'URINE-24H', 'name': '24-Hour Urine Collection', 'specimen_type': 'Urine', 'tat_minutes': 60, 'price': Decimal('40.00')},
            
            # Stool Tests
            {'code': 'STOOL-R/E', 'name': 'Stool Routine Examination', 'specimen_type': 'Stool', 'tat_minutes': 60, 'price': Decimal('30.00')},
            {'code': 'STOOL-MCS', 'name': 'Stool Microscopy & Culture', 'specimen_type': 'Stool', 'tat_minutes': 4320, 'price': Decimal('80.00')},
            {'code': 'STOOL-OCC', 'name': 'Stool Occult Blood', 'specimen_type': 'Stool', 'tat_minutes': 60, 'price': Decimal('35.00')},
            {'code': 'STOOL-O&P', 'name': 'Stool Ova & Parasites', 'specimen_type': 'Stool', 'tat_minutes': 60, 'price': Decimal('40.00')},
            
            # Blood Grouping & Transfusion
            {'code': 'BG', 'name': 'Blood Grouping', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('25.00')},
            {'code': 'RH', 'name': 'Rhesus Factor', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('20.00')},
            {'code': 'BG-RH', 'name': 'Blood Group & Rhesus Factor', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('40.00')},
            {'code': 'CROSS', 'name': 'Cross Matching', 'specimen_type': 'Whole Blood', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'COOMBS', 'name': 'Coombs Test (Direct)', 'specimen_type': 'Whole Blood', 'tat_minutes': 120, 'price': Decimal('60.00')},
            
            # Sickle Cell Tests
            {'code': 'HB-S', 'name': 'Sickle Cell Test (Solubility)', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('35.00')},
            {'code': 'HB-ELEC', 'name': 'Hemoglobin Electrophoresis', 'specimen_type': 'Whole Blood', 'tat_minutes': 120, 'price': Decimal('100.00')},
            {'code': 'SCREEN', 'name': 'Sickle Cell Screening', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('35.00')},
            
            # Hormones
            {'code': 'TSH', 'name': 'Thyroid Stimulating Hormone (TSH)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('70.00')},
            {'code': 'T3', 'name': 'Triiodothyronine (T3)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('70.00')},
            {'code': 'T4', 'name': 'Thyroxine (T4)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('70.00')},
            {'code': 'TFT', 'name': 'Thyroid Function Test (TFT)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('200.00')},
            {'code': 'FREE-T3', 'name': 'Free T3', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'FREE-T4', 'name': 'Free T4', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'PSA', 'name': 'Prostate Specific Antigen (PSA)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('100.00')},
            {'code': 'HCG', 'name': 'Beta HCG (Pregnancy)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'PROL', 'name': 'Prolactin', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'TESTO', 'name': 'Testosterone', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('100.00')},
            {'code': 'PROG', 'name': 'Progesterone', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('100.00')},
            {'code': 'FSH', 'name': 'Follicle Stimulating Hormone (FSH)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'LH', 'name': 'Luteinizing Hormone (LH)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            
            # Tumor Markers
            {'code': 'CEA', 'name': 'Carcinoembryonic Antigen (CEA)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('120.00')},
            {'code': 'AFP', 'name': 'Alpha Fetoprotein (AFP)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('120.00')},
            {'code': 'CA125', 'name': 'CA 125', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('150.00')},
            {'code': 'CA199', 'name': 'CA 19-9', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('150.00')},
            
            # Vitamins & Minerals
            {'code': 'VIT-D', 'name': 'Vitamin D', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('150.00')},
            {'code': 'VIT-B12', 'name': 'Vitamin B12', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('120.00')},
            {'code': 'FOLATE', 'name': 'Folate/Folic Acid', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('120.00')},
            {'code': 'FERR', 'name': 'Ferritin', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('100.00')},
            {'code': 'IRON', 'name': 'Serum Iron', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('60.00')},
            {'code': 'TIBC', 'name': 'Total Iron Binding Capacity (TIBC)', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('70.00')},
            {'code': 'CALC', 'name': 'Calcium', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('35.00')},
            {'code': 'PHOS', 'name': 'Phosphorus', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('35.00')},
            {'code': 'MAG', 'name': 'Magnesium', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('40.00')},
            
            # Coagulation
            {'code': 'PT', 'name': 'Prothrombin Time (PT)', 'specimen_type': 'Citrated Plasma', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'APTT', 'name': 'Activated Partial Thromboplastin Time (APTT)', 'specimen_type': 'Citrated Plasma', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'INR', 'name': 'International Normalized Ratio (INR)', 'specimen_type': 'Citrated Plasma', 'tat_minutes': 60, 'price': Decimal('40.00')},
            {'code': 'D-DIM', 'name': 'D-Dimer', 'specimen_type': 'Citrated Plasma', 'tat_minutes': 120, 'price': Decimal('80.00')},
            {'code': 'CLOT-Q', 'name': 'Clothing Profile - Quantitative', 'specimen_type': 'Citrated Plasma', 'tat_minutes': 120, 'price': Decimal('120.00')},
            
            # Microbiology
            {'code': 'BLOOD-C&S', 'name': 'Blood Culture & Sensitivity', 'specimen_type': 'Blood', 'tat_minutes': 5760, 'price': Decimal('150.00')},
            {'code': 'SPUTUM-C&S', 'name': 'Sputum Culture & Sensitivity', 'specimen_type': 'Sputum', 'tat_minutes': 4320, 'price': Decimal('100.00')},
            {'code': 'CSF-C&S', 'name': 'CSF Culture & Sensitivity', 'specimen_type': 'CSF', 'tat_minutes': 4320, 'price': Decimal('150.00')},
            {'code': 'WOUND-C&S', 'name': 'Wound Swab Culture & Sensitivity', 'specimen_type': 'Swab', 'tat_minutes': 4320, 'price': Decimal('100.00')},
            {'code': 'THROAT-C&S', 'name': 'Throat Swab Culture & Sensitivity', 'specimen_type': 'Swab', 'tat_minutes': 4320, 'price': Decimal('80.00')},
            
            # Serology
            {'code': 'BRUCELL', 'name': 'Brucellosis Test', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('80.00')},
            {'code': 'LEPTOSP', 'name': 'Leptospirosis Test', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('100.00')},
            
            # Other Common Tests
            {'code': 'AMYL', 'name': 'Amylase', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'LIPASE', 'name': 'Lipase', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('50.00')},
            {'code': 'LDH', 'name': 'Lactate Dehydrogenase (LDH)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('60.00')},
            {'code': 'CK', 'name': 'Creatine Kinase (CK)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('60.00')},
            {'code': 'CK-MB', 'name': 'CK-MB (Cardiac)', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': Decimal('100.00')},
            {'code': 'TROP', 'name': 'Troponin', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('200.00')},
            {'code': 'BNP', 'name': 'Brain Natriuretic Peptide (BNP)', 'specimen_type': 'Serum', 'tat_minutes': 180, 'price': Decimal('200.00')},
            {'code': 'URIC', 'name': 'Uric Acid', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': Decimal('35.00')},
            {'code': 'LACT', 'name': 'Lactate', 'specimen_type': 'Whole Blood', 'tat_minutes': 30, 'price': Decimal('60.00')},
            # Synovial fluid / crystal identification (qualitative: Seen / Not seen)
            {'code': 'KNEE-UA', 'name': 'Knee joint aspirate for uric acid crystals, qualitative', 'specimen_type': 'Synovial fluid (knee aspirate)', 'tat_minutes': 60, 'price': Decimal('80.00')},
            
            # Semen Analysis
            {'code': 'SEMEN', 'name': 'Semen Analysis', 'specimen_type': 'Semen', 'tat_minutes': 120, 'price': Decimal('80.00')},
            
            # PAP Smear
            {'code': 'PAP', 'name': 'Pap Smear', 'specimen_type': 'Cervical Swab', 'tat_minutes': 2880, 'price': Decimal('100.00')},
        ]
        
        created_count = 0
        updated_count = 0
        
        for test_data in lab_tests:
            test, created = LabTest.objects.update_or_create(
                code=test_data['code'],
                defaults={
                    'name': test_data['name'],
                    'specimen_type': test_data['specimen_type'],
                    'tat_minutes': test_data['tat_minutes'],
                    'price': test_data['price'],
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {test.code} - {test.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {test.code} - {test.name}'))
        
        # Invalidate lab tests cache so doctors see new tests in consultation
        try:
            from django.core.cache import cache
            cache.delete('hms:active_lab_tests')
            self.stdout.write(self.style.SUCCESS('Lab tests cache invalidated.'))
            self.stdout.write(
                self.style.WARNING(
                    'If the new test does not appear on the consultation page: '
                    'restart the Django server, or run: python manage.py invalidate_lab_tests_cache'
                )
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not invalidate cache: {e}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully seeded lab tests!\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Total: {len(lab_tests)}'
            )
        )

