"""
Import Ghana and Africa-specific ICD-10 diagnosis codes
Common diagnoses seen in Ghana healthcare settings
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from hospital.models_diagnosis import DiagnosisCode


class Command(BaseCommand):
    help = 'Import common Ghana and Africa-specific ICD-10 diagnosis codes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username of user creating these codes (default: first superuser)',
        )

    def handle(self, *args, **options):
        # Get user for tracking
        username = options.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User {username} not found'))
                return
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.first()
        
        if not user:
            self.stdout.write(self.style.ERROR('No user found to assign as creator'))
            return

        # Common Ghana/Africa diagnoses - MALARIA FIRST (Most Common in West Africa)
        ghana_diagnoses = [
            # ===== MALARIA - MOST COMMON IN WEST AFRICA (PRIORITY) =====
            {
                'code': 'B50.9',
                'description': 'Plasmodium falciparum malaria, unspecified',
                'short_description': 'Malaria (Falciparum)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Malaria',
                'notes': 'Most common disease in West Africa. Plasmodium falciparum is the most severe form.',
            },
            {
                'code': 'B54',
                'description': 'Unspecified malaria',
                'short_description': 'Malaria',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Malaria',
                'notes': 'Most common disease in West Africa',
            },
            {
                'code': 'B51.9',
                'description': 'Plasmodium vivax malaria without complication',
                'short_description': 'Malaria (Vivax)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B50.0',
                'description': 'Plasmodium falciparum malaria with cerebral complications',
                'short_description': 'Malaria (Cerebral)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'notes': 'Severe form of malaria with neurological complications',
            },
            
            # ===== OTHER COMMON WEST AFRICAN INFECTIOUS DISEASES =====
            {
                'code': 'A09.9',
                'description': 'Gastroenteritis and colitis of unspecified origin',
                'short_description': 'Gastroenteritis',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A01.9',
                'description': 'Typhoid fever, unspecified',
                'short_description': 'Typhoid Fever',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Typhoid',
            },
            {
                'code': 'A00.9',
                'description': 'Cholera, unspecified',
                'short_description': 'Cholera',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Cholera',
            },
            {
                'code': 'A15.9',
                'description': 'Respiratory tuberculosis, unspecified',
                'short_description': 'Tuberculosis (TB)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A06.9',
                'description': 'Amoebiasis, unspecified',
                'short_description': 'Amoebiasis',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Amoebic Dysentery',
            },
            {
                'code': 'A07.1',
                'description': 'Giardiasis',
                'short_description': 'Giardiasis',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B65.9',
                'description': 'Schistosomiasis, unspecified',
                'short_description': 'Schistosomiasis (Bilharzia)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Bilharzia',
            },
            {
                'code': 'B73',
                'description': 'Onchocerciasis',
                'short_description': 'Onchocerciasis (River Blindness)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'River Blindness',
            },
            {
                'code': 'B56.9',
                'description': 'African trypanosomiasis, unspecified',
                'short_description': 'Trypanosomiasis (Sleeping Sickness)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Sleeping Sickness',
            },
            {
                'code': 'B74.9',
                'description': 'Filariasis, unspecified',
                'short_description': 'Filariasis',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B76.9',
                'description': 'Hookworm disease, unspecified',
                'short_description': 'Hookworm Infection',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B77.9',
                'description': 'Ascariasis, unspecified',
                'short_description': 'Ascariasis (Roundworm)',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A95.9',
                'description': 'Yellow fever, unspecified',
                'short_description': 'Yellow Fever',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A90',
                'description': 'Dengue fever',
                'short_description': 'Dengue Fever',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A96.2',
                'description': 'Lassa fever',
                'short_description': 'Lassa Fever',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'G00.9',
                'description': 'Bacterial meningitis, unspecified',
                'short_description': 'Meningitis (Bacterial)',
                'category': 'nervous',
                'chapter': 'G00-G99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'notes': 'Common in West Africa, especially during dry season',
            },
            {
                'code': 'A39.0',
                'description': 'Meningococcal meningitis',
                'short_description': 'Meningococcal Meningitis',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B05.9',
                'description': 'Measles without complication',
                'short_description': 'Measles',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B26.9',
                'description': 'Mumps without complication',
                'short_description': 'Mumps',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'B06.9',
                'description': 'Rubella without complication',
                'short_description': 'Rubella',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'A35',
                'description': 'Tetanus',
                'short_description': 'Tetanus',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A82.9',
                'description': 'Rabies, unspecified',
                'short_description': 'Rabies',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A31.1',
                'description': 'Cutaneous mycobacterial infection',
                'short_description': 'Buruli Ulcer',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Buruli Ulcer',
            },
            {
                'code': 'A66.9',
                'description': 'Yaws, unspecified',
                'short_description': 'Yaws',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A71.9',
                'description': 'Trachoma, unspecified',
                'short_description': 'Trachoma',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A30.9',
                'description': 'Leprosy, unspecified',
                'short_description': 'Leprosy',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B15.9',
                'description': 'Hepatitis A without hepatic coma',
                'short_description': 'Hepatitis A',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'B16.9',
                'description': 'Acute hepatitis B without delta-agent and without hepatic coma',
                'short_description': 'Hepatitis B',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'B20',
                'description': 'Human immunodeficiency virus [HIV] disease',
                'short_description': 'HIV Disease',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'A02.0',
                'description': 'Salmonella enteritis',
                'short_description': 'Salmonella Infection',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'B16.9',
                'description': 'Acute hepatitis B without delta-agent and without hepatic coma',
                'short_description': 'Hepatitis B',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'B20',
                'description': 'Human immunodeficiency virus [HIV] disease',
                'short_description': 'HIV Disease',
                'category': 'infectious',
                'chapter': 'A00-B99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            
            # ===== BLOOD DISORDERS (Common in West Africa) =====
            {
                'code': 'D57.1',
                'description': 'Sickle-cell disease without crisis',
                'short_description': 'Sickle Cell Disease',
                'category': 'blood',
                'chapter': 'D50-D89',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Sickle Cell',
                'notes': 'Very common genetic disorder in West Africa',
            },
            {
                'code': 'D57.0',
                'description': 'Sickle-cell disorder with crisis',
                'short_description': 'Sickle Cell Crisis',
                'category': 'blood',
                'chapter': 'D50-D89',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'D50.9',
                'description': 'Iron deficiency anemia, unspecified',
                'short_description': 'Iron Deficiency Anemia',
                'category': 'blood',
                'chapter': 'D50-D89',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'D64.9',
                'description': 'Anemia, unspecified',
                'short_description': 'Anemia',
                'category': 'blood',
                'chapter': 'D50-D89',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            
            # ===== NUTRITIONAL DISORDERS (Common in West Africa) =====
            {
                'code': 'E46',
                'description': 'Unspecified protein-energy malnutrition',
                'short_description': 'Malnutrition',
                'category': 'endocrine',
                'chapter': 'E00-E90',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'E40',
                'description': 'Kwashiorkor',
                'short_description': 'Kwashiorkor',
                'category': 'endocrine',
                'chapter': 'E00-E90',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Kwashiorkor',
            },
            {
                'code': 'E41',
                'description': 'Nutritional marasmus',
                'short_description': 'Marasmus',
                'category': 'endocrine',
                'chapter': 'E00-E90',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'E50.9',
                'description': 'Vitamin A deficiency, unspecified',
                'short_description': 'Vitamin A Deficiency',
                'category': 'endocrine',
                'chapter': 'E00-E90',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            
            # ===== RESPIRATORY DISEASES =====
            {
                'code': 'J18.9',
                'description': 'Pneumonia, unspecified organism',
                'short_description': 'Pneumonia',
                'category': 'respiratory',
                'chapter': 'J00-J99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'J06.9',
                'description': 'Acute upper respiratory infection, unspecified',
                'short_description': 'Upper Respiratory Infection',
                'category': 'respiratory',
                'chapter': 'J00-J99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'J44.9',
                'description': 'Chronic obstructive pulmonary disease, unspecified',
                'short_description': 'COPD',
                'category': 'respiratory',
                'chapter': 'J00-J99',
                'is_common': True,
            },
            
            # Digestive System
            {
                'code': 'K29.9',
                'description': 'Gastroduodenitis, unspecified',
                'short_description': 'Gastritis',
                'category': 'digestive',
                'chapter': 'K00-K95',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'K59.0',
                'description': 'Constipation',
                'short_description': 'Constipation',
                'category': 'digestive',
                'chapter': 'K00-K95',
                'is_common': True,
            },
            {
                'code': 'K92.2',
                'description': 'Gastrointestinal hemorrhage, unspecified',
                'short_description': 'GI Bleeding',
                'category': 'digestive',
                'chapter': 'K00-K95',
                'is_common': True,
            },
            
            # Genitourinary
            {
                'code': 'N39.0',
                'description': 'Urinary tract infection, site not specified',
                'short_description': 'Urinary Tract Infection (UTI)',
                'category': 'genitourinary',
                'chapter': 'N00-N99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'N70.9',
                'description': 'Salpingitis and oophoritis, unspecified',
                'short_description': 'Pelvic Inflammatory Disease',
                'category': 'genitourinary',
                'chapter': 'N00-N99',
                'is_common': True,
            },
            
            # Circulatory System
            {
                'code': 'I10',
                'description': 'Essential (primary) hypertension',
                'short_description': 'Hypertension',
                'category': 'circulatory',
                'chapter': 'I00-I99',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'I20.9',
                'description': 'Angina pectoris, unspecified',
                'short_description': 'Angina',
                'category': 'circulatory',
                'chapter': 'I00-I99',
                'is_common': True,
            },
            {
                'code': 'I50.9',
                'description': 'Heart failure, unspecified',
                'short_description': 'Heart Failure',
                'category': 'circulatory',
                'chapter': 'I00-I99',
                'is_common': True,
            },
            
            # Endocrine
            {
                'code': 'E11.9',
                'description': 'Type 2 diabetes mellitus without complications',
                'short_description': 'Type 2 Diabetes',
                'category': 'endocrine',
                'chapter': 'E00-E90',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'E10.9',
                'description': 'Type 1 diabetes mellitus without complications',
                'short_description': 'Type 1 Diabetes',
                'category': 'endocrine',
                'chapter': 'E00-E90',
                'is_common': True,
            },
            
            # Pregnancy
            {
                'code': 'O80',
                'description': 'Single spontaneous delivery',
                'short_description': 'Normal Delivery',
                'category': 'pregnancy',
                'chapter': 'O00-O9A',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'O36.4',
                'description': 'Maternal care for other specified fetal problems',
                'short_description': 'Pregnancy Complication',
                'category': 'pregnancy',
                'chapter': 'O00-O9A',
                'is_common': True,
            },
            
            # Symptoms and Signs
            {
                'code': 'R50.9',
                'description': 'Fever, unspecified',
                'short_description': 'Fever',
                'category': 'symptoms',
                'chapter': 'R00-R94',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
            },
            {
                'code': 'R51',
                'description': 'Headache',
                'short_description': 'Headache',
                'category': 'symptoms',
                'chapter': 'R00-R94',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'R06.0',
                'description': 'Dyspnea',
                'short_description': 'Shortness of Breath',
                'category': 'symptoms',
                'chapter': 'R00-R94',
                'is_common': True,
            },
            {
                'code': 'R11',
                'description': 'Nausea and vomiting',
                'short_description': 'Nausea and Vomiting',
                'category': 'symptoms',
                'chapter': 'R00-R94',
                'is_common': True,
            },
            
            # ===== INJURIES AND POISONING (Common in West Africa) =====
            {
                'code': 'T63.0',
                'description': 'Toxic effect of snake venom',
                'short_description': 'Snake Bite',
                'category': 'injury',
                'chapter': 'S00-T88',
                'is_common': True,
                'is_ghana_common': True,
                'is_africa_common': True,
                'local_name': 'Snake Bite',
            },
            {
                'code': 'S00.9',
                'description': 'Superficial injury of head, part unspecified',
                'short_description': 'Head Injury',
                'category': 'injury',
                'chapter': 'S00-T88',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'T14.9',
                'description': 'Injury, unspecified',
                'short_description': 'Injury',
                'category': 'injury',
                'chapter': 'S00-T88',
                'is_common': True,
            },
            
            # Skin
            {
                'code': 'L08.9',
                'description': 'Local infection of skin and subcutaneous tissue, unspecified',
                'short_description': 'Skin Infection',
                'category': 'skin',
                'chapter': 'L00-L99',
                'is_common': True,
                'is_ghana_common': True,
            },
            {
                'code': 'L70.9',
                'description': 'Acne, unspecified',
                'short_description': 'Acne',
                'category': 'skin',
                'chapter': 'L00-L99',
                'is_common': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for diag_data in ghana_diagnoses:
            code = diag_data.pop('code')
            diag_data['created_by'] = user
            diag_data['updated_by'] = user
            
            diagnosis_code, created = DiagnosisCode.objects.update_or_create(
                code=code,
                defaults=diag_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'[+] Created: {code} - {diagnosis_code.short_description}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'[*] Updated: {code} - {diagnosis_code.short_description}')
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n[DONE] Import complete! Created: {created_count}, Updated: {updated_count}'
        ))
        self.stdout.write(
            self.style.SUCCESS(
                f'Total Ghana/Africa common diagnoses: {DiagnosisCode.objects.filter(is_ghana_common=True).count()}'
            )
        )

