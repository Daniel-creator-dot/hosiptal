"""
Django Management Command to Import Insurance Adjudication Reports from Excel
Imports insurance receivable data and creates proper accounting entries
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
    Journal, AccountCategory
)
from hospital.models_primecare_accounting import InsuranceReceivableEntry


class Command(BaseCommand):
    help = 'Import insurance adjudication reports from Excel files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to Excel file (supports .xls and .xlsx)'
        )
        parser.add_argument(
            '--insurance-company',
            type=str,
            required=True,
            help='Name of insurance company (must match Payer name)'
        )
        parser.add_argument(
            '--sheet-name',
            type=str,
            default=None,
            help='Sheet name to read (default: first sheet)'
        )
        parser.add_argument(
            '--header-row',
            type=int,
            default=0,
            help='Row number containing headers (0-indexed, default: 0)'
        )
        parser.add_argument(
            '--start-row',
            type=int,
            default=None,
            help='Row number to start reading data (default: header_row + 1)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually importing data'
        )
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip data validation (not recommended)'
        )
        parser.add_argument(
            '--create-journal-entries',
            action='store_true',
            default=True,
            help='Create journal entries for accounting (default: True)'
        )
        parser.add_argument(
            '--column-mapping',
            type=str,
            default=None,
            help='JSON string with column mappings (e.g., \'{"patient_name": "Patient Name", "amount": "Amount"}\')'
        )
    
    def handle(self, *args, **options):
        file_path = options['file_path']
        insurance_company_name = options['insurance_company']
        dry_run = options['dry_run']
        
        # Check if Excel libraries are available
        if not HAS_PANDAS and not HAS_XLRD and not HAS_OPENPYXL:
            raise CommandError(
                'No Excel reading library found. Please install one of: pandas, xlrd, or openpyxl\n'
                'Run: pip install pandas xlrd openpyxl'
            )
        
        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        # Get insurance company
        try:
            insurance_company = Payer.objects.get(
                name__icontains=insurance_company_name,
                payer_type__in=['insurance', 'private', 'nhis']
            )
        except Payer.DoesNotExist:
            raise CommandError(
                f'Insurance company not found: {insurance_company_name}\n'
                f'Available insurance companies: {", ".join(Payer.objects.filter(payer_type__in=["insurance", "private", "nhis"]).values_list("name", flat=True)[:10])}'
            )
        except Payer.MultipleObjectsReturned:
            matches = Payer.objects.filter(
                name__icontains=insurance_company_name,
                payer_type__in=['insurance', 'private', 'nhis']
            )
            raise CommandError(
                f'Multiple insurance companies found matching "{insurance_company_name}":\n'
                f'{chr(10).join(f"  - {p.name} (ID: {p.id})" for p in matches)}'
            )
        
        self.stdout.write(self.style.SUCCESS(f'Using insurance company: {insurance_company.name}'))
        
        # Read Excel file
        self.stdout.write(f'Reading Excel file: {file_path}')
        try:
            df = self.read_excel_file(file_path, options)
        except Exception as e:
            raise CommandError(f'Error reading Excel file: {e}')
        
        if df.empty:
            raise CommandError('Excel file is empty or no data rows found')
        
        self.stdout.write(f'Found {len(df)} rows in Excel file')
        self.stdout.write(f'Columns: {", ".join(df.columns.tolist())}')
        
        # Detect column mappings
        column_mapping = self.detect_column_mappings(df, options.get('column_mapping'))
        self.stdout.write(f'Detected column mappings: {column_mapping}')
        
        # Validate required columns
        required_columns = ['patient_identifier', 'amount']
        missing = [col for col in required_columns if column_mapping.get(col) not in df.columns]
        if missing:
            raise CommandError(f'Missing required columns: {missing}')
        
        # Process data
        stats = {
            'total_rows': len(df),
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'errors_list': []
        }
        
        if not dry_run:
            with transaction.atomic():
                for idx, row in df.iterrows():
                    try:
                        result = self.process_row(
                            row, 
                            column_mapping, 
                            insurance_company, 
                            options,
                            idx + 1
                        )
                        stats['processed'] += 1
                        if result == 'created':
                            stats['created'] += 1
                        elif result == 'updated':
                            stats['updated'] += 1
                        elif result == 'skipped':
                            stats['skipped'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f'Row {idx + 1}: {str(e)}'
                        stats['errors_list'].append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))
        else:
            # Dry run - just validate
            for idx, row in df.iterrows():
                try:
                    self.validate_row(row, column_mapping, insurance_company, idx + 1)
                    stats['processed'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f'Row {idx + 1}: {str(e)}'
                    stats['errors_list'].append(error_msg)
                    self.stdout.write(self.style.ERROR(error_msg))
        
        # Print summary
        self.print_summary(stats, dry_run)
        
        if stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f'\n{stats["errors"]} errors occurred. Check output above.'))
            if stats['errors'] <= 10:
                for error in stats['errors_list']:
                    self.stdout.write(self.style.ERROR(f'  - {error}'))
    
    def read_excel_file(self, file_path, options):
        """Read Excel file using available library"""
        sheet_name = options.get('sheet_name')
        header_row = options.get('header_row', 0)
        start_row = options.get('start_row')
        
        if HAS_PANDAS:
            # Use pandas (supports both .xls and .xlsx)
            if file_path.endswith('.xls') and not HAS_XLRD:
                # pandas needs xlrd for .xls files
                self.stdout.write(self.style.WARNING('Installing xlrd for .xls support...'))
                raise CommandError('Please install xlrd: pip install xlrd')
            
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=header_row,
                skiprows=start_row - header_row - 1 if start_row and start_row > header_row else None
            )
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            return df
        elif HAS_XLRD and file_path.endswith('.xls'):
            # Use xlrd for .xls files
            workbook = xlrd.open_workbook(file_path)
            if sheet_name:
                sheet = workbook.sheet_by_name(sheet_name)
            else:
                sheet = workbook.sheet_by_index(0)
            
            # Read headers
            headers = [str(sheet.cell_value(header_row, col)).strip() 
                      for col in range(sheet.ncols)]
            
            # Read data
            data_start = start_row if start_row else header_row + 1
            data = []
            for row_idx in range(data_start, sheet.nrows):
                row_data = [sheet.cell_value(row_idx, col) for col in range(sheet.ncols)]
                data.append(row_data)
            
            import pandas as pd
            df = pd.DataFrame(data, columns=headers)
            return df
        elif HAS_OPENPYXL and file_path.endswith('.xlsx'):
            # Use openpyxl for .xlsx files
            workbook = openpyxl.load_workbook(file_path, read_only=True)
            if sheet_name:
                sheet = workbook[sheet_name]
            else:
                sheet = workbook.active
            
            # Read headers
            header_row_num = header_row + 1  # openpyxl uses 1-indexed
            headers = [str(cell.value).strip() if cell.value else f'Column{idx+1}'
                      for idx, cell in enumerate(sheet[header_row_num])]
            
            # Read data
            data_start = start_row + 1 if start_row else header_row + 2
            data = []
            for row in sheet.iter_rows(min_row=data_start, values_only=True):
                if any(cell is not None for cell in row):  # Skip empty rows
                    data.append([cell if cell is not None else '' for cell in row])
            
            import pandas as pd
            df = pd.DataFrame(data, columns=headers)
            return df
        else:
            raise CommandError('No suitable library found to read this file format')
    
    def detect_column_mappings(self, df, custom_mapping=None):
        """Detect column mappings from Excel headers"""
        columns = [str(col).lower().strip() for col in df.columns]
        
        # Default mappings (common column names)
        default_mappings = {
            'patient_identifier': ['patient', 'patient name', 'patient_name', 'name', 'member', 'member name', 'member_name', 'mrn', 'patient id', 'patient_id'],
            'invoice_number': ['invoice', 'invoice number', 'invoice_number', 'inv', 'bill', 'bill number', 'bill_number'],
            'claim_number': ['claim', 'claim number', 'claim_number', 'claim no', 'claim_no'],
            'claim_date': ['claim date', 'claim_date', 'date', 'service date', 'service_date', 'visit date', 'visit_date'],
            'amount': ['amount', 'total', 'total amount', 'total_amount', 'billed amount', 'billed_amount', 'charge', 'charges'],
            'amount_paid': ['paid', 'amount paid', 'amount_paid', 'approved', 'approved amount', 'approved_amount'],
            'amount_rejected': ['rejected', 'rejection', 'amount rejected', 'amount_rejected', 'denied', 'denied amount'],
            'withholding_tax': ['wht', 'withholding tax', 'withholding_tax', 'tax', 'tax withheld'],
            'service_type': ['service', 'service type', 'service_type', 'category', 'department'],
        }
        
        mapping = {}
        
        if custom_mapping:
            import json
            try:
                custom = json.loads(custom_mapping)
                for key, value in custom.items():
                    if value in df.columns:
                        mapping[key] = value
            except:
                pass
        
        # Auto-detect remaining mappings
        for key, possible_names in default_mappings.items():
            if key not in mapping:
                for col in columns:
                    if any(name in col for name in possible_names):
                        # Find original column name (case-insensitive)
                        for orig_col in df.columns:
                            if str(orig_col).lower().strip() == col:
                                mapping[key] = orig_col
                                break
                        break
        
        return mapping
    
    def validate_row(self, row, column_mapping, insurance_company, row_num):
        """Validate a single row of data"""
        # Get patient identifier
        patient_col = column_mapping.get('patient_identifier')
        if not patient_col or patient_col not in row.index:
            raise ValueError('Patient identifier column not found')
        
        patient_identifier = str(row[patient_col]).strip()
        if not patient_identifier or patient_identifier.lower() in ['nan', 'none', '']:
            raise ValueError('Patient identifier is empty')
        
        # Get amount
        amount_col = column_mapping.get('amount')
        if not amount_col or amount_col not in row.index:
            raise ValueError('Amount column not found')
        
        try:
            amount = Decimal(str(row[amount_col]).replace(',', ''))
            if amount <= 0:
                raise ValueError('Amount must be greater than zero')
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f'Invalid amount: {row[amount_col]}')
        
        # Validate patient exists (optional - can create if needed)
        # For now, we'll require patient to exist
        
        return True
    
    def process_row(self, row, column_mapping, insurance_company, options, row_num):
        """Process a single row and create/update records"""
        # Get values from row
        patient_col = column_mapping.get('patient_identifier')
        patient_identifier = str(row[patient_col]).strip()
        
        amount_col = column_mapping.get('amount')
        amount = Decimal(str(row[amount_col]).replace(',', ''))
        
        # Get optional fields
        invoice_number = None
        if 'invoice_number' in column_mapping:
            inv_col = column_mapping['invoice_number']
            if inv_col in row.index:
                invoice_number = str(row[inv_col]).strip()
        
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
        
        amount_paid = amount  # Default: assume full amount paid
        if 'amount_paid' in column_mapping:
            paid_col = column_mapping['amount_paid']
            if paid_col in row.index:
                try:
                    amount_paid = Decimal(str(row[paid_col]).replace(',', ''))
                except:
                    pass
        
        amount_rejected = Decimal('0.00')
        if 'amount_rejected' in column_mapping:
            rej_col = column_mapping['amount_rejected']
            if rej_col in row.index:
                try:
                    amount_rejected = Decimal(str(row[rej_col]).replace(',', ''))
                except:
                    pass
        
        withholding_tax = Decimal('0.00')
        if 'withholding_tax' in column_mapping:
            wht_col = column_mapping['withholding_tax']
            if wht_col in row.index:
                try:
                    withholding_tax = Decimal(str(row[wht_col]).replace(',', ''))
                except:
                    pass
        
        # Find patient
        patient = self.find_patient(patient_identifier)
        if not patient:
            raise ValueError(f'Patient not found: {patient_identifier}')
        
        # Find invoice if provided
        invoice = None
        if invoice_number:
            try:
                invoice = Invoice.objects.get(invoice_number=invoice_number, is_deleted=False)
            except Invoice.DoesNotExist:
                pass  # Invoice not required
        
        # Get or create receivable account (try common account code patterns)
        receivable_account = None
        for code_pattern in [f'1200-{insurance_company.id}', f'1100-{insurance_company.id}', '1100', '1200']:
            receivable_account = Account.objects.filter(account_code=code_pattern).first()
            if receivable_account:
                break
        
        if not receivable_account:
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
                'invoice': invoice,
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
            # Update existing
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
        from hospital.models_accounting_advanced import Journal
        
        # Get or create journal
        journal, _ = Journal.objects.get_or_create(
            code='AR',
            defaults={
                'name': 'Accounts Receivable Journal',
                'journal_type': 'general'
            }
        )
        
        # Create journal entry
        je = AdvancedJournalEntry.objects.create(
            journal=journal,
            entry_date=receivable.claim_date,
            description=f"Insurance Receivable - {insurance_company.name} - {receivable.receivable_number}",
            reference=receivable.receivable_number,
            status='posted',
            total_debit=receivable.total_amount,
            total_credit=receivable.total_amount,
        )
        
        # Debit: Accounts Receivable
        AdvancedJournalEntryLine.objects.create(
            journal_entry=je,
            line_number=1,
            account=receivable_account,
            description=f"AR - {insurance_company.name} - {receivable.receivable_number}",
            debit_amount=receivable.total_amount,
            credit_amount=Decimal('0.00'),
            patient=receivable.patient,
        )
        
        # Credit: Revenue (use default revenue account)
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
        
        # Link to receivable
        receivable.journal_entry = je
        receivable.save()
        
        return je
    
    def print_summary(self, stats, dry_run):
        """Print import summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total rows in file: {stats["total_rows"]}')
        self.stdout.write(f'Rows processed: {stats["processed"]}')
        
        if not dry_run:
            self.stdout.write(f'Records created: {stats["created"]}')
            self.stdout.write(f'Records updated: {stats["updated"]}')
            self.stdout.write(f'Records skipped: {stats["skipped"]}')
        
        self.stdout.write(f'Errors: {stats["errors"]}')
        self.stdout.write('='*60)

