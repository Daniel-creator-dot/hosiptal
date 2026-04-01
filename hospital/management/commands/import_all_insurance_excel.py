"""
Django Management Command to Import ALL Insurance Adjudication Reports from Excel Folder
Processes all Excel files in the insurance excel folder automatically
"""
import os
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

# Try to import Excel reading libraries
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    try:
        import xlrd
        HAS_XLRD = True
    except ImportError:
        HAS_XLRD = False
        try:
            import openpyxl
            HAS_OPENPYXL = True
        except ImportError:
            HAS_OPENPYXL = False

from hospital.models import Patient, Invoice, Payer
from hospital.models_accounting import Account
from hospital.models_accounting_advanced import (
    InsuranceReceivable, AdvancedJournalEntry, AdvancedJournalEntryLine,
    Journal
)


class Command(BaseCommand):
    help = 'Import all insurance adjudication reports from Excel folder automatically'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--folder',
            type=str,
            default='insurance excel',
            help='Folder containing Excel files (default: insurance excel)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually importing data'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip files that have already been imported'
        )
        parser.add_argument(
            '--create-journal-entries',
            action='store_true',
            default=True,
            help='Create journal entries for accounting (default: True)'
        )
    
    def handle(self, *args, **options):
        folder_path = options['folder']
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']
        
        # Check if Excel libraries are available
        if not HAS_PANDAS and not HAS_XLRD and not HAS_OPENPYXL:
            raise CommandError(
                'No Excel reading library found. Please install one of: pandas, xlrd, or openpyxl\n'
                'Run: pip install pandas xlrd openpyxl'
            )
        
        if not os.path.exists(folder_path):
            raise CommandError(f'Folder not found: {folder_path}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        # Find all Excel files
        excel_files = []
        for filename in os.listdir(folder_path):
            if filename.endswith(('.xls', '.xlsx', '.XLS', '.XLSX')):
                excel_files.append(os.path.join(folder_path, filename))
        
        if not excel_files:
            raise CommandError(f'No Excel files found in {folder_path}')
        
        self.stdout.write(self.style.SUCCESS(f'Found {len(excel_files)} Excel file(s)'))
        
        # Process each file
        total_stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'files_errors': 0,
            'total_rows': 0,
            'total_created': 0,
            'total_updated': 0,
            'total_errors': 0,
        }
        
        for file_path in excel_files:
            try:
                self.stdout.write(f'\n{"="*60}')
                self.stdout.write(f'Processing: {os.path.basename(file_path)}')
                self.stdout.write(f'{"="*60}')
                
                # Detect insurance company from filename
                insurance_company_name = self.detect_insurance_company(file_path)
                if not insurance_company_name:
                    self.stdout.write(self.style.WARNING(f'  WARNING: Could not detect insurance company from filename. Skipping...'))
                    total_stats['files_skipped'] += 1
                    continue
                
                self.stdout.write(f'  Detected Insurance: {insurance_company_name}')
                
                # Get insurance company
                try:
                    insurance_company = Payer.objects.get(
                        name__icontains=insurance_company_name,
                        payer_type__in=['insurance', 'private', 'nhis']
                    )
                except Payer.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  WARNING: Insurance company not found: {insurance_company_name}'))
                    self.stdout.write(self.style.WARNING(f'  Creating new payer...'))
                    insurance_company = Payer.objects.create(
                        name=insurance_company_name,
                        payer_type='insurance',
                        is_active=True
                    )
                    self.stdout.write(self.style.SUCCESS(f'  SUCCESS: Created: {insurance_company.name}'))
                except Payer.MultipleObjectsReturned:
                    matches = Payer.objects.filter(
                        name__icontains=insurance_company_name,
                        payer_type__in=['insurance', 'private', 'nhis']
                    )
                    insurance_company = matches.first()
                    self.stdout.write(self.style.WARNING(f'  WARNING: Multiple matches found, using: {insurance_company.name}'))
                
                # Process file
                file_stats = self.process_file(
                    file_path, 
                    insurance_company, 
                    options,
                    skip_existing
                )
                
                # Update totals
                total_stats['files_processed'] += 1
                total_stats['total_rows'] += file_stats['total_rows']
                total_stats['total_created'] += file_stats['created']
                total_stats['total_updated'] += file_stats['updated']
                total_stats['total_errors'] += file_stats['errors']
                
                self.stdout.write(self.style.SUCCESS(
                    f'  SUCCESS: File processed: {file_stats["created"]} created, '
                    f'{file_stats["updated"]} updated, {file_stats["errors"]} errors'
                ))
                
            except Exception as e:
                total_stats['files_errors'] += 1
                self.stdout.write(self.style.ERROR(f'  ERROR: Error processing file: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
        
        # Print final summary
        self.print_final_summary(total_stats, dry_run)
    
    def detect_insurance_company(self, file_path):
        """Detect insurance company name from filename"""
        filename = os.path.basename(file_path)
        
        # Common insurance company patterns
        patterns = [
            r'(COSMO|COSMOPOLITAN)',
            r'(EQUITY)',
            r'(GAB)',
            r'(NHIS)',
            r'(ACACIA)',
            r'(APEX)',
            r'(BEIGE)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                name = match.group(1).upper()
                # Map abbreviations to full names
                name_map = {
                    'COSMO': 'COSMOPOLITAN HEALTH INSURANCE',
                    'EQUITY': 'EQUITY HEALTH INSURANCE',
                    'GAB': 'GAB HEALTH INSURANCE',
                    'NHIS': 'NHIS',
                    'ACACIA': 'ACACIA HEALTH INSURANCE',
                    'APEX': 'APEX MUTUAL HEALTH',
                    'BEIGE': 'BEIGE CARE',
                }
                return name_map.get(name, name)
        
        return None
    
    def process_file(self, file_path, insurance_company, options, skip_existing):
        """Process a single Excel file"""
        stats = {
            'total_rows': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'errors_list': []
        }
        
        try:
            # Read Excel file
            excel_data = self.read_excel_file(file_path)
            
            # Handle both DataFrame and dict format
            if isinstance(excel_data, dict) and excel_data.get('use_dict'):
                # Use dict format directly - convert to list of dicts for processing
                headers = excel_data['headers']
                data_rows = excel_data['data']
                # Convert to list of dicts
                df_data = []
                for row in data_rows:
                    row_dict = {}
                    for i, header in enumerate(headers):
                        row_dict[header] = row[i] if i < len(row) else ''
                    df_data.append(row_dict)
                # Create a simple DataFrame-like object
                class SimpleDF:
                    def __init__(self, data):
                        self.data = data
                        self.columns = headers
                    def __len__(self):
                        return len(self.data)
                    def iterrows(self):
                        for idx, row in enumerate(self.data):
                            yield idx, row
                    @property
                    def empty(self):
                        return len(self.data) == 0
                df = SimpleDF(df_data)
            else:
                df = excel_data
            
            if hasattr(df, 'empty') and df.empty or len(df) == 0:
                self.stdout.write(self.style.WARNING('  WARNING: File is empty'))
                return stats
            
            stats['total_rows'] = len(df)
            self.stdout.write(f'  Found {len(df)} rows')
            
            # Detect column mappings
            column_mapping = self.detect_column_mappings(df)
            self.stdout.write(f'  Columns detected: {len(column_mapping)} mappings')
            
            # Validate required columns
            if 'patient_identifier' not in column_mapping or 'amount' not in column_mapping:
                self.stdout.write(self.style.ERROR('  ERROR: Missing required columns'))
                return stats
            
            # Process rows
            if not options.get('dry_run', False):
                with transaction.atomic():
                    for idx, row in df.iterrows():
                        try:
                            # Convert row to dict-like access if needed
                            if hasattr(row, 'to_dict'):
                                row_dict = row.to_dict()
                            elif isinstance(row, dict):
                                row_dict = row
                            else:
                                # Convert Series or list to dict
                                row_dict = {}
                                for col in df.columns:
                                    if hasattr(row, col):
                                        row_dict[col] = getattr(row, col)
                                    elif isinstance(row, (list, tuple)) and col in df.columns:
                                        col_idx = list(df.columns).index(col)
                                        row_dict[col] = row[col_idx] if col_idx < len(row) else ''
                            
                            result = self.process_row(
                                type('Row', (), row_dict),  # Create object with dict attributes
                                column_mapping, 
                                insurance_company, 
                                options,
                                idx + 1
                            )
                            if result == 'created':
                                stats['created'] += 1
                            elif result == 'updated':
                                stats['updated'] += 1
                        except Exception as e:
                            stats['errors'] += 1
                            if stats['errors'] <= 5:  # Only show first 5 errors
                                stats['errors_list'].append(f'Row {idx + 1}: {str(e)}')
            else:
                # Dry run - just validate
                for idx, row in df.iterrows():
                    try:
                        # Convert row to dict-like access if needed
                        if hasattr(row, 'to_dict'):
                            row_dict = row.to_dict()
                        elif isinstance(row, dict):
                            row_dict = row
                        else:
                            row_dict = {}
                            for col in df.columns:
                                if hasattr(row, col):
                                    row_dict[col] = getattr(row, col)
                        
                        self.validate_row(type('Row', (), row_dict), column_mapping, insurance_company, idx + 1)
                    except Exception as e:
                        stats['errors'] += 1
                        if stats['errors'] <= 5:
                            stats['errors_list'].append(f'Row {idx + 1}: {str(e)}')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ERROR: Error reading file: {str(e)}'))
            stats['errors'] += 1
        
        return stats
    
    def read_excel_file(self, file_path):
        """Read Excel file using available library"""
        # Try xlrd first for .xls files (most reliable)
        if file_path.endswith('.xls') or file_path.endswith('.XLS'):
            try:
                import xlrd
                workbook = xlrd.open_workbook(file_path)
                sheet = workbook.sheet_by_index(0)
                headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
                data = []
                for row_idx in range(1, sheet.nrows):
                    row_data = [sheet.cell_value(row_idx, col) for col in range(sheet.ncols)]
                    data.append(row_data)
                # Return as dict format (pandas may be blocked by Windows policy)
                return {'headers': headers, 'data': data, 'use_dict': True}
            except ImportError:
                raise CommandError('xlrd is required for .xls files. Install with: pip install xlrd')
            except Exception as e:
                raise CommandError(f'Error reading .xls file: {str(e)}')
        
        # Try openpyxl for .xlsx files
        elif file_path.endswith('.xlsx') or file_path.endswith('.XLSX'):
            try:
                import openpyxl
                workbook = openpyxl.load_workbook(file_path, read_only=True)
                sheet = workbook.active
                headers = [str(cell.value).strip() if cell.value else f'Column{idx+1}'
                          for idx, cell in enumerate(sheet[1])]
                data = []
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if any(cell is not None for cell in row):
                        data.append([cell if cell is not None else '' for cell in row])
                # Return as dict format (pandas may be blocked by Windows policy)
                return {'headers': headers, 'data': data, 'use_dict': True}
            except ImportError:
                raise CommandError('openpyxl is required for .xlsx files. Install with: pip install openpyxl')
            except Exception as e:
                raise CommandError(f'Error reading .xlsx file: {str(e)}')
        
        # Try pandas as last resort (if available and not blocked)
        if HAS_PANDAS:
            try:
                df = pd.read_excel(file_path, header=0)
                df.columns = [str(col).strip() for col in df.columns]
                return df
            except Exception as e:
                pass
        
        raise CommandError('No suitable library found to read this file format')
    
    def detect_column_mappings(self, df):
        """Detect column mappings from Excel headers"""
        columns = [str(col).lower().strip() for col in df.columns]
        
        default_mappings = {
            'patient_identifier': ['patient', 'patient name', 'patient_name', 'name', 'member', 'member name', 'member_name', 'mrn', 'patient id', 'patient_id'],
            'invoice_number': ['invoice', 'invoice number', 'invoice_number', 'inv', 'bill', 'bill number', 'bill_number'],
            'claim_number': ['claim', 'claim number', 'claim_number', 'claim no', 'claim_no'],
            'claim_date': ['claim date', 'claim_date', 'date', 'service date', 'service_date', 'visit date', 'visit_date'],
            'amount': ['amount', 'total', 'total amount', 'total_amount', 'billed amount', 'billed_amount', 'charge', 'charges'],
            'amount_paid': ['paid', 'amount paid', 'amount_paid', 'approved', 'approved amount', 'approved_amount'],
            'amount_rejected': ['rejected', 'rejection', 'amount rejected', 'amount_rejected', 'denied', 'denied amount'],
            'withholding_tax': ['wht', 'withholding tax', 'withholding_tax', 'tax', 'tax withheld'],
        }
        
        mapping = {}
        for key, possible_names in default_mappings.items():
            for col in columns:
                if any(name in col for name in possible_names):
                    for orig_col in df.columns:
                        if str(orig_col).lower().strip() == col:
                            mapping[key] = orig_col
                            break
                    break
        
        return mapping
    
    def validate_row(self, row, column_mapping, insurance_company, row_num):
        """Validate a single row of data"""
        patient_col = column_mapping.get('patient_identifier')
        if not patient_col or patient_col not in row.index:
            raise ValueError('Patient identifier column not found')
        
        patient_identifier = str(row[patient_col]).strip()
        if not patient_identifier or patient_identifier.lower() in ['nan', 'none', '']:
            raise ValueError('Patient identifier is empty')
        
        amount_col = column_mapping.get('amount')
        if not amount_col or amount_col not in row.index:
            raise ValueError('Amount column not found')
        
        try:
            amount = Decimal(str(row[amount_col]).replace(',', ''))
            if amount <= 0:
                raise ValueError('Amount must be greater than zero')
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f'Invalid amount: {row[amount_col]}')
        
        return True
    
    def process_row(self, row, column_mapping, insurance_company, options, row_num):
        """Process a single row and create/update records"""
        patient_col = column_mapping.get('patient_identifier')
        patient_identifier = str(row[patient_col]).strip()
        
        amount_col = column_mapping.get('amount')
        amount = Decimal(str(row[amount_col]).replace(',', ''))
        
        claim_number = None
        if 'claim_number' in column_mapping:
            claim_col = column_mapping['claim_number']
            if claim_col in row.index:
                claim_number = str(row[claim_col]).strip()
        
        claim_date = timezone.now().date()
        if 'claim_date' in column_mapping:
            date_col = column_mapping['claim_date']
            if date_col in row.index:
                date_val = row[date_col]
                if isinstance(date_val, (datetime, date)):
                    claim_date = date_val if isinstance(date_val, date) else date_val.date()
                elif date_val:
                    try:
                        claim_date = pd.to_datetime(date_val).date()
                    except:
                        pass
        
        amount_paid = amount
        if 'amount_paid' in column_mapping:
            paid_col = column_mapping['amount_paid']
            if paid_col in row.index:
                try:
                    amount_paid = Decimal(str(row[paid_col]).replace(',', ''))
                except:
                    pass
        
        # Find patient
        patient = self.find_patient(patient_identifier)
        if not patient:
            raise ValueError(f'Patient not found: {patient_identifier}')
        
        # Get or create receivable account
        receivable_account, _ = Account.objects.get_or_create(
            account_code=f'1200-{insurance_company.id}',
            defaults={
                'account_name': f'Accounts Receivable - {insurance_company.name}',
                'account_type': 'asset',
            }
        )
        
        # Create or update InsuranceReceivable
        receivable, created = InsuranceReceivable.objects.get_or_create(
            claim_number=claim_number or f'AUTO-{row_num}',
            insurance_company=insurance_company,
            defaults={
                'patient': patient,
                'invoice': None,
                'claim_date': claim_date,
                'total_amount': amount,
                'amount_paid': amount_paid,
                'balance_due': amount - amount_paid,
                'due_date': claim_date + timezone.timedelta(days=30),
                'status': 'paid' if amount_paid >= amount else 'partial',
                'payment_date': claim_date if amount_paid >= amount else None,
                'receivable_account': receivable_account,
            }
        )
        
        if not created:
            receivable.total_amount = amount
            receivable.amount_paid = amount_paid
            receivable.balance_due = amount - amount_paid
            receivable.status = 'paid' if amount_paid >= amount else 'partial'
            receivable.save()
        
        # Create journal entry if requested
        if options.get('create_journal_entries', True) and not receivable.journal_entry:
            self.create_journal_entry(receivable, insurance_company, receivable_account)
        
        return 'created' if created else 'updated'
    
    def find_patient(self, identifier):
        """Find patient by various identifiers"""
        identifier = identifier.strip()
        
        # Try MRN first
        try:
            return Patient.objects.get(mrn=identifier, is_deleted=False)
        except Patient.DoesNotExist:
            pass
        
        # Try by name (split if possible)
        name_parts = identifier.split()
        if len(name_parts) >= 2:
            try:
                return Patient.objects.get(
                    first_name__icontains=name_parts[0],
                    last_name__icontains=name_parts[-1],
                    is_deleted=False
                )
            except (Patient.DoesNotExist, Patient.MultipleObjectsReturned):
                pass
        
        # Try phone number
        if identifier.isdigit():
            try:
                return Patient.objects.get(phone_number=identifier, is_deleted=False)
            except Patient.DoesNotExist:
                pass
        
        return None
    
    def create_journal_entry(self, receivable, insurance_company, receivable_account):
        """Create journal entry for insurance receivable"""
        journal, _ = Journal.objects.get_or_create(
            code='AR',
            defaults={
                'name': 'Accounts Receivable Journal',
                'journal_type': 'general'
            }
        )
        
        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=receivable.claim_date,
            description=f"Insurance Receivable - {insurance_company.name} - {receivable.receivable_number}",
            reference=receivable.receivable_number,
            status='posted',
            total_debit=receivable.total_amount,
            total_credit=receivable.total_amount,
        )
        
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=1,
            account=receivable_account,
            description=f"AR - {insurance_company.name} - {receivable.receivable_number}",
            debit_amount=receivable.total_amount,
            credit_amount=Decimal('0.00'),
            patient=receivable.patient,
        )
        
        revenue_account, _ = Account.objects.get_or_create(
            account_code='4100',
            defaults={
                'account_name': 'Service Revenue',
                'account_type': 'revenue',
            }
        )
        
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=2,
            account=revenue_account,
            description=f"Revenue - {insurance_company.name} - {receivable.receivable_number}",
            debit_amount=Decimal('0.00'),
            credit_amount=receivable.total_amount,
            patient=receivable.patient,
        )
        
        receivable.journal_entry = je
        receivable.save()
        
        return je
    
    def print_final_summary(self, stats, dry_run):
        """Print final import summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('FINAL IMPORT SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Files processed: {stats["files_processed"]}')
        self.stdout.write(f'Files skipped: {stats["files_skipped"]}')
        self.stdout.write(f'Files with errors: {stats["files_errors"]}')
        self.stdout.write(f'Total rows: {stats["total_rows"]}')
        
        if not dry_run:
            self.stdout.write(f'Records created: {stats["total_created"]}')
            self.stdout.write(f'Records updated: {stats["total_updated"]}')
        
        self.stdout.write(f'Total errors: {stats["total_errors"]}')
        self.stdout.write('='*60)
        
        if stats['total_errors'] > 0:
            self.stdout.write(self.style.WARNING(f'\nWARNING: {stats["total_errors"]} errors occurred during import'))

