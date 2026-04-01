"""
Django Management Command to Import Insurance Companies and Plans from db_3
Extracts insurance companies from insurance_companies.sql and creates InsuranceCompany and InsurancePlan records
"""
import re
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import date
from hospital.models_insurance_companies import InsuranceCompany, InsurancePlan


class Command(BaseCommand):
    help = 'Import insurance companies and plans from db_3 insurance_companies.sql file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/db_3_extracted/insurance_companies.sql',
            help='Path to insurance_companies.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually importing data'
        )
        parser.add_argument(
            '--create-plans',
            action='store_true',
            default=True,
            help='Create default insurance plans for each company'
        )
    
    def handle(self, *args, **options):
        sql_file = options['file']
        dry_run = options['dry_run']
        create_plans = options['create_plans']
        
        # Resolve file path
        if not os.path.isabs(sql_file):
            # Relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            sql_file = os.path.join(project_root, sql_file)
        
        if not os.path.exists(sql_file):
            raise CommandError(f'SQL file does not exist: {sql_file}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        self.stdout.write(f'Reading insurance companies from: {sql_file}')
        
        # Read and parse SQL file
        companies_data = self.parse_insurance_companies_sql(sql_file)
        
        self.stdout.write(f'Found {len(companies_data)} insurance companies')
        
        if dry_run:
            self.stdout.write('\n=== DRY RUN - Companies that would be imported ===')
            for company in companies_data[:10]:  # Show first 10
                self.stdout.write(f"  - {company['name']} (ID: {company['id']}, Code: {company['code']}, Type: {company['pricelevel']})")
            if len(companies_data) > 10:
                self.stdout.write(f"  ... and {len(companies_data) - 10} more")
            return
        
        # Import companies and plans
        with transaction.atomic():
            imported_count = 0
            updated_count = 0
            plan_count = 0
            
            for company_data in companies_data:
                try:
                    company, created = self.import_insurance_company(company_data)
                    if created:
                        imported_count += 1
                    else:
                        updated_count += 1
                    
                    # Create default plan if requested
                    if create_plans:
                        plan, plan_created = self.create_default_plan(company, company_data)
                        if plan_created:
                            plan_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error importing {company_data.get("name", "Unknown")}: {str(e)}')
                    )
                    continue
            
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Import complete!'
                f'\n   Companies imported: {imported_count}'
                f'\n   Companies updated: {updated_count}'
                f'\n   Plans created: {plan_count}'
            ))
    
    def parse_insurance_companies_sql(self, file_path):
        """Parse insurance_companies.sql file and extract company data"""
        companies = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
        # Format: INSERT INTO insurance_companies VALUES("id","name","attn","cms_id",...);
        insert_pattern = r'INSERT INTO insurance_companies VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                # Parse values - handle quoted strings and NULL
                values = self.parse_sql_values(match)
                
                if len(values) < 16:
                    continue
                
                def clean_value(v):
                    """Clean and strip quotes from value"""
                    if not v:
                        return ''
                    v = v.strip().strip('"\'')
                    return v
                
                def clean_int(v, default=0):
                    """Clean and convert to int"""
                    v = clean_value(v)
                    if not v or v == 'NULL':
                        return default
                    try:
                        return int(v)
                    except (ValueError, TypeError):
                        return default
                
                company_id = clean_value(values[0])
                name = clean_value(values[1])
                attn = clean_value(values[2])
                cms_id = clean_value(values[3])
                ins_type_code = clean_value(values[4])
                x12_receiver_id = clean_value(values[5])
                x12_default_partner_id = clean_value(values[6])
                alt_cms_id = clean_value(values[7])
                inactive = clean_int(values[8], 0)
                export_type = clean_int(values[9], 0)
                policy_mandatory = clean_int(values[10], 0)
                alert = clean_value(values[11])
                pricelevel = clean_value(values[12])
                claim_policy = clean_value(values[13])
                copay_service = clean_value(values[14])
                copay_drug = clean_value(values[15])
                
                # Skip invalid entries
                if not name or name.lower() == 'error' or not name.strip():
                    continue
                
                # Generate code from cms_id or name
                code = cms_id if cms_id else self.generate_code_from_name(name)
                
                companies.append({
                    'id': company_id,
                    'name': name,
                    'attn': attn,
                    'code': code,
                    'cms_id': cms_id,
                    'pricelevel': pricelevel,
                    'inactive': inactive,
                    'alert': alert,
                    'copay_service': copay_service,
                    'copay_drug': copay_drug,
                })
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Error parsing company record: {str(e)}')
                )
                continue
        
        return companies
    
    def parse_sql_values(self, values_string):
        """Parse SQL VALUES string handling quotes and NULL"""
        values = []
        current = ''
        in_quotes = False
        quote_char = None
        i = 0
        
        while i < len(values_string):
            char = values_string[i]
            
            if char in ['"', "'"] and (i == 0 or values_string[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current += char
            elif char == ',' and not in_quotes:
                values.append(current.strip())
                current = ''
            else:
                current += char
            
            i += 1
        
        if current.strip():
            values.append(current.strip())
        
        return values
    
    def generate_code_from_name(self, name):
        """Generate a short code from company name"""
        # Remove common words and take first letters
        words = name.upper().split()
        code = ''
        
        for word in words:
            if word not in ['LTD', 'LIMITED', 'COMPANY', 'HEALTH', 'INSURANCE', 'CARE', 'MUTUAL']:
                if word:
                    code += word[0]
                if len(code) >= 4:
                    break
        
        # If still too short, use first 4 chars
        if len(code) < 3:
            code = name[:4].upper().replace(' ', '')
        
        return code[:20]  # Max 20 chars
    
    def map_pricelevel_to_status(self, pricelevel):
        """Map pricelevel to company status"""
        if not pricelevel:
            return 'active'
        
        pricelevel_lower = pricelevel.lower()
        
        # Active insurance types
        if pricelevel_lower in ['ins', 'nhis', 'gab', 'nmh']:
            return 'active'
        elif pricelevel_lower == 'corp':
            return 'active'  # Corporate accounts are active
        elif pricelevel_lower == 'cash':
            return 'inactive'  # Cash is not an insurance company
        else:
            return 'active'
    
    @transaction.atomic
    def import_insurance_company(self, company_data):
        """Import or update an insurance company"""
        name = company_data['name']
        code = company_data['code']
        pricelevel = company_data['pricelevel']
        inactive = company_data['inactive']
        
        # Determine status
        status = 'inactive' if inactive else self.map_pricelevel_to_status(pricelevel)
        
        # Try to get by code first, then by name
        try:
            company = InsuranceCompany.objects.get(code=code)
            created = False
            # Update existing
            company.name = name
            company.status = status
            company.is_active = not inactive
            if company_data.get('alert'):
                company.notes = company_data.get('alert', '')
            company.save()
        except InsuranceCompany.DoesNotExist:
            # Try by name
            try:
                company = InsuranceCompany.objects.get(name=name)
                created = False
                # Update existing
                company.code = code  # Update code if different
                company.status = status
                company.is_active = not inactive
                if company_data.get('alert'):
                    company.notes = company_data.get('alert', '')
                company.save()
            except InsuranceCompany.DoesNotExist:
                # Create new
                company = InsuranceCompany.objects.create(
                    name=name,
                    code=code,
                    status=status,
                    is_active=not inactive,
                    notes=company_data.get('alert', ''),
                )
                created = True
        
        return company, created
    
    def create_default_plan(self, company, company_data):
        """Create a default insurance plan for the company"""
        pricelevel = company_data.get('pricelevel', '').lower()
        
        # Skip cash - not an insurance company
        if pricelevel == 'cash':
            return None, False
        
        # Generate plan code
        plan_code = f"{company.code}-PLAN-001"
        
        # Determine plan type based on pricelevel
        if pricelevel == 'corp':
            plan_type = 'corporate'
            plan_name = f"{company.name} Corporate Plan"
        elif pricelevel == 'nhis':
            plan_type = 'basic'
            plan_name = f"{company.name} NHIS Plan"
        else:
            plan_type = 'standard'
            plan_name = f"{company.name} Standard Plan"
        
        # Check if plan already exists
        plan, created = InsurancePlan.objects.get_or_create(
            plan_code=plan_code,
            defaults={
                'insurance_company': company,
                'plan_name': plan_name,
                'plan_type': plan_type,
                'description': f"Default plan for {company.name}",
                'consultation_coverage': Decimal('100.00'),
                'lab_coverage': Decimal('100.00'),
                'imaging_coverage': Decimal('100.00'),
                'pharmacy_coverage': Decimal('100.00'),
                'surgery_coverage': Decimal('100.00'),
                'admission_coverage': Decimal('100.00'),
                'is_active': company.is_active,
                'effective_date': date.today(),
            }
        )
        
        return plan, created
