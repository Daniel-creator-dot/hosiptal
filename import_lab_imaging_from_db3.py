#!/usr/bin/env python
"""
Import Lab Tests and Imaging Studies from db_3.zip SQL files
This script extracts lab tests and imaging studies with their prices
and imports them into the Django database.
"""

import os
import sys
import django
import zipfile
import re
from decimal import Decimal
from collections import defaultdict

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import LabTest
from hospital.models_advanced import ImagingCatalog
from django.db import transaction
from django.utils import timezone

# Import path
IMPORT_DIR = os.path.join(os.path.dirname(__file__), 'import')
DB3_ZIP = os.path.join(IMPORT_DIR, 'db_3.zip')


def extract_sql_data(zip_file, sql_filename):
    """Extract and parse SQL INSERT statements from a SQL file"""
    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            if sql_filename not in z.namelist():
                print(f"Warning: {sql_filename} not found in zip file")
                return []
            
            content = z.read(sql_filename).decode('utf-8', errors='ignore')
            
            # Extract INSERT statements
            insert_pattern = r'INSERT INTO\s+\w+\s+VALUES\s*\((.*?)\);'
            matches = re.findall(insert_pattern, content, re.IGNORECASE | re.DOTALL)
            
            data = []
            for match in matches:
                # Parse the values - handle quoted strings and numbers
                values = []
                current_value = ''
                in_quotes = False
                quote_char = None
                i = 0
                
                while i < len(match):
                    char = match[i]
                    
                    if char in ('"', "'") and (i == 0 or match[i-1] != '\\'):
                        if not in_quotes:
                            in_quotes = True
                            quote_char = char
                        elif char == quote_char:
                            in_quotes = False
                            quote_char = None
                        current_value += char
                    elif char == ',' and not in_quotes:
                        # End of value
                        val = current_value.strip().strip('"').strip("'")
                        values.append(val)
                        current_value = ''
                    else:
                        current_value += char
                    
                    i += 1
                
                # Add last value
                if current_value.strip():
                    val = current_value.strip().strip('"').strip("'")
                    values.append(val)
                
                if values:
                    data.append(values)
            
            return data
    except Exception as e:
        print(f"Error extracting {sql_filename}: {str(e)}")
        return []


def get_prices_from_sql():
    """Extract prices from prices.sql"""
    prices = defaultdict(dict)  # {code: {level: price}}
    
    try:
        with zipfile.ZipFile(DB3_ZIP, 'r') as z:
            if 'prices.sql' not in z.namelist():
                print("Warning: prices.sql not found")
                return prices
            
            content = z.read('prices.sql').decode('utf-8', errors='ignore')
            
            # Extract INSERT statements
            insert_pattern = r'INSERT INTO\s+prices\s+VALUES\s*\((.*?)\);'
            matches = re.findall(insert_pattern, content, re.IGNORECASE | re.DOTALL)
            
            for match in matches:
                # Parse: pr_id, pr_selector, pr_level, pr_price, ...
                # Handle quoted values
                values = []
                current = ''
                in_quotes = False
                quote_char = None
                
                for char in match:
                    if char in ('"', "'") and (not current or current[-1] != '\\'):
                        if not in_quotes:
                            in_quotes = True
                            quote_char = char
                        elif char == quote_char:
                            in_quotes = False
                            quote_char = None
                        current += char
                    elif char == ',' and not in_quotes:
                        val = current.strip().strip('"').strip("'")
                        values.append(val)
                        current = ''
                    else:
                        current += char
                
                if current.strip():
                    val = current.strip().strip('"').strip("'")
                    values.append(val)
                
                if len(values) >= 4:
                    code = values[0]
                    name = values[1]
                    level = values[2]
                    try:
                        price = Decimal(values[3])
                        # Store by code and name (some items use code, some use name)
                        if code and code != '':
                            prices[code][level] = price
                        if name and name != '':
                            prices[name][level] = price
                    except (ValueError, IndexError):
                        pass
    
    except Exception as e:
        print(f"Error reading prices: {str(e)}")
    
    return prices


def import_lab_tests():
    """Import lab tests from lab_order_code.sql"""
    print("\n=== Importing Lab Tests ===")
    
    # Get prices
    prices = get_prices_from_sql()
    
    # Extract lab test data
    lab_data = extract_sql_data(DB3_ZIP, 'lab_order_code.sql')
    
    if not lab_data:
        print("No lab test data found")
        return
    
    # Extract unique tests by procedure_code
    unique_tests = {}
    for row in lab_data:
        if len(row) >= 4:
            code = row[2].strip() if len(row) > 2 else ''  # procedure_code
            name = row[3].strip() if len(row) > 3 else ''   # procedure_name
            
            if code and name:
                # Use code as key to avoid duplicates
                if code not in unique_tests or len(name) > len(unique_tests[code]['name']):
                    unique_tests[code] = {
                        'code': code,
                        'name': name,
                    }
    
    print(f"Found {len(unique_tests)} unique lab tests")
    
    # Import to database
    imported = 0
    updated = 0
    skipped = 0
    
    with transaction.atomic():
        for code, test_data in unique_tests.items():
            try:
                # Get price (prefer cash price, fallback to first available)
                price = Decimal('0.00')
                test_name = test_data['name']
                
                # Try to find price by code or name
                if code in prices:
                    price_dict = prices[code]
                    price = price_dict.get('cash', price_dict.get('corp', 
                        list(price_dict.values())[0] if price_dict else Decimal('0.00')))
                elif test_name in prices:
                    price_dict = prices[test_name]
                    price = price_dict.get('cash', price_dict.get('corp',
                        list(price_dict.values())[0] if price_dict else Decimal('0.00')))
                
                # Determine specimen type from name (common patterns)
                specimen_type = 'Blood'  # Default
                name_lower = test_name.lower()
                if 'urine' in name_lower or 'urinalysis' in name_lower:
                    specimen_type = 'Urine'
                elif 'stool' in name_lower or 'faeces' in name_lower:
                    specimen_type = 'Stool'
                elif 'sputum' in name_lower:
                    specimen_type = 'Sputum'
                elif 'swab' in name_lower:
                    specimen_type = 'Swab'
                elif 'csf' in name_lower or 'cerebrospinal' in name_lower:
                    specimen_type = 'CSF'
                
                # Create or update lab test
                lab_test, created = LabTest.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': test_name,
                        'specimen_type': specimen_type,
                        'price': price,
                        'tat_minutes': 60,  # Default turnaround time
                        'is_active': True,
                    }
                )
                
                if created:
                    imported += 1
                else:
                    updated += 1
                
            except Exception as e:
                print(f"Error importing lab test {code}: {str(e)}")
                skipped += 1
    
    print(f"Lab Tests: {imported} imported, {updated} updated, {skipped} skipped")


def import_imaging_studies():
    """Import imaging studies from diag_imaging_order_code.sql"""
    print("\n=== Importing Imaging Studies ===")
    
    # Get prices
    prices = get_prices_from_sql()
    
    # Extract imaging data
    imaging_data = extract_sql_data(DB3_ZIP, 'diag_imaging_order_code.sql')
    
    if not imaging_data:
        print("No imaging data found")
        return
    
    # Extract unique imaging studies by procedure_code
    unique_studies = {}
    for row in imaging_data:
        if len(row) >= 4:
            code = row[2].strip() if len(row) > 2 else ''  # procedure_code
            name = row[3].strip() if len(row) > 3 else ''   # procedure_name
            
            if code and name:
                if code not in unique_studies or len(name) > len(unique_studies[code]['name']):
                    unique_studies[code] = {
                        'code': code,
                        'name': name,
                    }
    
    print(f"Found {len(unique_studies)} unique imaging studies")
    
    # Import to database using ImagingCatalog
    imported = 0
    updated = 0
    skipped = 0
    
    with transaction.atomic():
        for code, study_data in sorted(unique_studies.items()):
            try:
                name = study_data['name']
                
                # Get price (prefer cash price, fallback to first available)
                price = Decimal('0.00')
                if code in prices:
                    price_dict = prices[code]
                    price = price_dict.get('cash', price_dict.get('corp',
                        list(price_dict.values())[0] if price_dict else Decimal('0.00')))
                elif name in prices:
                    price_dict = prices[name]
                    price = price_dict.get('cash', price_dict.get('corp',
                        list(price_dict.values())[0] if price_dict else Decimal('0.00')))
                
                # Determine modality and body part
                modality = 'xray'  # Default
                body_part = ''
                study_type = ''
                
                name_lower = name.lower()
                
                # Modality detection
                if 'ct' in name_lower or 'computed tomography' in name_lower:
                    modality = 'ct'
                elif 'mri' in name_lower or 'magnetic resonance' in name_lower:
                    modality = 'mri'
                elif 'ultrasound' in name_lower or 'us' in name_lower:
                    modality = 'ultrasound'
                elif 'mammography' in name_lower or 'mammo' in name_lower:
                    modality = 'mammography'
                elif 'fluoroscopy' in name_lower:
                    modality = 'fluoroscopy'
                elif 'nuclear' in name_lower:
                    modality = 'nuclear'
                elif 'pet' in name_lower:
                    modality = 'pet'
                elif 'dexa' in name_lower or 'bone density' in name_lower:
                    modality = 'dexa'
                
                # Body part detection
                body_parts = ['chest', 'abdomen', 'pelvis', 'skull', 'spine', 'limb', 'hand', 'foot', 
                             'knee', 'hip', 'shoulder', 'elbow', 'wrist', 'ankle', 'head', 'neck']
                for part in body_parts:
                    if part in name_lower:
                        body_part = part.title()
                        break
                
                # Extract study type from name
                study_type = name
                
                # Create or update imaging catalog entry
                imaging_catalog, created = ImagingCatalog.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'modality': modality,
                        'body_part': body_part,
                        'study_type': study_type,
                        'price': price,
                        'is_active': True,
                    }
                )
                
                if created:
                    imported += 1
                else:
                    updated += 1
                
            except Exception as e:
                print(f"Error importing imaging study {code}: {str(e)}")
                skipped += 1
    
    print(f"Imaging Studies: {imported} imported, {updated} updated, {skipped} skipped")


def main():
    """Main import function"""
    print("=" * 60)
    print("Lab Tests and Imaging Studies Import from db_3.zip")
    print("=" * 60)
    
    if not os.path.exists(DB3_ZIP):
        print(f"Error: {DB3_ZIP} not found!")
        return
    
    # Import lab tests
    import_lab_tests()
    
    # Import imaging studies
    import_imaging_studies()
    
    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
