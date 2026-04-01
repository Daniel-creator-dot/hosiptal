"""
Import prices from billing.sql
Extracts consultation prices (S00023), lab test prices, and other service prices
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from hospital.models import ServiceCode, LabTest
from hospital.models_enterprise_billing import ServicePricing
from hospital.models import Payer


class Command(BaseCommand):
    help = 'Import prices from billing.sql file (consultation, lab tests, and other services)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/billing.sql',
            help='Path to billing.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Reading prices from: {file_path}'))
        
        # Ensure payers exist
        cash_payer, _ = Payer.objects.get_or_create(
            name='Cash',
            defaults={'payer_type': 'cash', 'is_active': True}
        )
        corp_payer, _ = Payer.objects.get_or_create(
            name='Corporate',
            defaults={'payer_type': 'corporate', 'is_active': True}
        )
        ins_payer, _ = Payer.objects.get_or_create(
            name='Insurance',
            defaults={'payer_type': 'insurance', 'is_active': True}
        )
        
        # Get or create consultation service code (S00023)
        consultation_code, _ = ServiceCode.objects.get_or_create(
            code='S00023',
            defaults={
                'description': 'CONSULTATION',
                'category': 'Clinical Services',
                'is_active': True,
                'default_price': Decimal('100.00')
            }
        )
        
        # Parse billing.sql to extract prices
        price_data = {}  # {code: {cash: price, corp: price, ins: price, description: desc}}
        stats = {
            'total_lines': 0,
            'consultation_prices': 0,
            'lab_prices': 0,
            'other_prices': 0,
            'errors': 0
        }
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                if line_num % 10000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                # Parse INSERT INTO billing VALUES line
                # Format: INSERT INTO billing VALUES("id","date","code_type","code","pid","provider_id","user","groupname","authorized","encounter","code_text","billed","activity","payer_id","bill_process","bill_date","process_date","process_file","modifier","units","fee","justify","target","x12_partner_id","ndc_info","notecodes","external_id","pricelevel","procedure_order_id","consultation_service_id","admission_service_id","surgery_service_id","topup","formdir","deleted","deleted_by","deleted_at","cost","provider","insurance_id","discount");
                match = re.search(r'INSERT INTO billing VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)"\);', line)
                if not match:
                    continue
                
                code = match.group(4)  # Service code
                code_text = match.group(11)  # Description
                fee_str = match.group(20)  # Price
                pricelevel = match.group(27)  # Payer type: cash, corp, ins
                
                if not code or not fee_str:
                    continue
                
                try:
                    fee = Decimal(fee_str)
                    if fee <= 0:
                        continue
                except (ValueError, TypeError):
                    stats['errors'] += 1
                    continue
                
                # Store price data
                if code not in price_data:
                    price_data[code] = {
                        'description': code_text or code,
                        'cash': None,
                        'corp': None,
                        'ins': None
                    }
                
                # Map pricelevel to payer type
                pricelevel_lower = (pricelevel or '').lower().strip()
                if pricelevel_lower in ['cash', '']:
                    if price_data[code]['cash'] is None or fee > price_data[code]['cash']:
                        price_data[code]['cash'] = fee
                elif pricelevel_lower in ['corp', 'corporate']:
                    if price_data[code]['corp'] is None or fee > price_data[code]['corp']:
                        price_data[code]['corp'] = fee
                elif pricelevel_lower in ['ins', 'insurance', 'private', 'nhis']:
                    if price_data[code]['ins'] is None or fee > price_data[code]['ins']:
                        price_data[code]['ins'] = fee
        
        self.stdout.write(f'\nFound {len(price_data)} unique service codes')
        self.stdout.write('Processing prices...\n')
        
        # Process consultation prices (S00023)
        if 'S00023' in price_data:
            data = price_data['S00023']
            if not dry_run:
                with transaction.atomic():
                    # Update consultation service code description
                    consultation_code.description = data['description']
                    consultation_code.save()
                    
                    # Create/update pricing for cash payer
                    if data['cash']:
                        ServicePricing.objects.update_or_create(
                            service_code=consultation_code,
                            payer=cash_payer,
                            defaults={
                                'cash_price': data['cash'],
                                'is_active': True,
                                'effective_from': timezone.now().date()
                            }
                        )
                        stats['consultation_prices'] += 1
                    
                    # Create/update pricing for corporate payer
                    if data['corp']:
                        ServicePricing.objects.update_or_create(
                            service_code=consultation_code,
                            payer=corp_payer,
                            defaults={
                                'corporate_price': data['corp'],
                                'is_active': True,
                                'effective_from': timezone.now().date()
                            }
                        )
                        stats['consultation_prices'] += 1
                    
                    # Create/update pricing for insurance payer
                    if data['ins']:
                        ServicePricing.objects.update_or_create(
                            service_code=consultation_code,
                            payer=ins_payer,
                            defaults={
                                'insurance_price': data['ins'],
                                'is_active': True,
                                'effective_from': timezone.now().date()
                            }
                        )
                        stats['consultation_prices'] += 1
                    
                    # Also create default pricing (no payer)
                    ServicePricing.objects.update_or_create(
                        service_code=consultation_code,
                        payer__isnull=True,
                        defaults={
                            'cash_price': data['cash'] or Decimal('100.00'),
                            'corporate_price': data['corp'] or data['cash'] or Decimal('120.00'),
                            'insurance_price': data['ins'] or data['cash'] or Decimal('120.00'),
                            'is_active': True,
                            'effective_from': timezone.now().date()
                        }
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Consultation (S00023): Cash={data['cash']}, Corp={data['corp']}, Ins={data['ins']}"
                )
            )
        
        # Process lab test prices (codes starting with numbers or SL)
        lab_codes = [code for code in price_data.keys() if code and (code[0].isdigit() or code.startswith('SL'))]
        for code in lab_codes:
            data = price_data[code]
            
            # Try to find matching lab test
            lab_test = LabTest.objects.filter(code=code, is_deleted=False).first()
            
            if lab_test:
                # Update lab test price (use cash price as default)
                new_price = data['cash'] or data['corp'] or data['ins'] or lab_test.price
                if not dry_run:
                    lab_test.price = new_price
                    lab_test.save(update_fields=['price'])
                stats['lab_prices'] += 1
                
                if line_num <= 10:  # Log first few
                    self.stdout.write(
                        f"Lab Test {code}: {data['description']} - Price: {new_price}"
                    )
        
        # Process other service codes
        other_codes = [code for code in price_data.keys() 
                      if code not in ['S00023'] and code not in lab_codes]
        
        for code in other_codes[:100]:  # Limit to first 100 other services
            data = price_data[code]
            
            # Get or create service code
            if not dry_run:
                service_code, created = ServiceCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'description': data['description'],
                        'category': 'Clinical Services',
                        'is_active': True,
                        'default_price': data['cash'] or data['corp'] or data['ins'] or Decimal('0.00')
                    }
                )
                
                if not created:
                    # Update description and default price
                    service_code.description = data['description']
                    if data['cash']:
                        service_code.default_price = data['cash']
                    service_code.save()
                
                # Create pricing entries
                if data['cash']:
                    ServicePricing.objects.update_or_create(
                        service_code=service_code,
                        payer=cash_payer,
                        defaults={
                            'cash_price': data['cash'],
                            'is_active': True,
                            'effective_from': timezone.now().date()
                        }
                    )
                
                if data['corp']:
                    ServicePricing.objects.update_or_create(
                        service_code=service_code,
                        payer=corp_payer,
                        defaults={
                            'corporate_price': data['corp'],
                            'is_active': True,
                            'effective_from': timezone.now().date()
                        }
                    )
                
                if data['ins']:
                    ServicePricing.objects.update_or_create(
                        service_code=service_code,
                        payer=ins_payer,
                        defaults={
                            'insurance_price': data['ins'],
                            'is_active': True,
                            'effective_from': timezone.now().date()
                        }
                    )
            
            stats['other_prices'] += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Import Summary ==='))
        self.stdout.write(f'Total lines processed: {stats["total_lines"]}')
        self.stdout.write(f'Consultation prices: {stats["consultation_prices"]}')
        self.stdout.write(f'Lab test prices: {stats["lab_prices"]}')
        self.stdout.write(f'Other service prices: {stats["other_prices"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No prices were actually imported'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Prices imported successfully!'))
