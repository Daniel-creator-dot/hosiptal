"""
Management command to clean up duplicate invoice lines
Merges duplicate medication/service entries on the same invoice
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import transaction
from hospital.models import Invoice, InvoiceLine
from decimal import Decimal


class Command(BaseCommand):
    help = 'Clean up duplicate invoice lines - merge duplicates for same service_code on same invoice'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned without making changes',
        )
        parser.add_argument(
            '--invoice',
            type=str,
            help='Clean specific invoice by invoice number',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        invoice_filter = options.get('invoice')
        
        self.stdout.write(self.style.SUCCESS('Starting duplicate invoice line cleanup...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find invoices with duplicate service codes
        if invoice_filter:
            invoices = Invoice.objects.filter(invoice_number=invoice_filter, is_deleted=False)
        else:
            # Get all invoices that might have duplicates
            invoices = Invoice.objects.filter(is_deleted=False)
        
        total_merged = 0
        total_invoices_fixed = 0
        
        for invoice in invoices:
            # Group invoice lines by service_code
            lines_by_service = {}
            
            for line in invoice.lines.filter(is_deleted=False):
                service_code_id = line.service_code.id if line.service_code else None
                key = (service_code_id, line.description.split(' x')[0] if ' x' in line.description else line.description)
                
                if key not in lines_by_service:
                    lines_by_service[key] = []
                lines_by_service[key].append(line)
            
            # Find duplicates
            duplicates_found = False
            merged_count = 0
            
            for key, lines in lines_by_service.items():
                if len(lines) > 1:
                    duplicates_found = True
                    self.stdout.write(
                        f"\nInvoice {invoice.invoice_number}: Found {len(lines)} duplicate lines for {lines[0].service_code.code if lines[0].service_code else 'Unknown'}"
                    )
                    
                    if not dry_run:
                        with transaction.atomic():
                            # Keep the first line, merge others into it
                            primary_line = lines[0]
                            
                            for duplicate_line in lines[1:]:
                                # Merge quantities
                                primary_line.quantity += duplicate_line.quantity
                                primary_line.line_total = primary_line.quantity * primary_line.unit_price
                                
                                # Update description to reflect total
                                base_desc = primary_line.description.split(' x')[0] if ' x' in primary_line.description else primary_line.description
                                primary_line.description = f"{base_desc} x{int(primary_line.quantity)}"
                                
                                # Keep the most recent prescription if both have one
                                if duplicate_line.prescription and primary_line.prescription:
                                    if duplicate_line.prescription.created > primary_line.prescription.created:
                                        primary_line.prescription = duplicate_line.prescription
                                elif duplicate_line.prescription and not primary_line.prescription:
                                    primary_line.prescription = duplicate_line.prescription
                                
                                # Mark duplicate as deleted
                                duplicate_line.is_deleted = True
                                duplicate_line.save()
                                merged_count += 1
                            
                            primary_line.save()
                            
                            # Recalculate invoice totals
                            invoice.calculate_totals()
                            invoice.save()
                    
                    total_merged += merged_count
                    self.stdout.write(
                        f"  {'Would merge' if dry_run else 'Merged'} {merged_count} duplicate(s) into primary line"
                    )
            
            if duplicates_found and not dry_run:
                total_invoices_fixed += 1
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('CLEANUP SUMMARY'))
        self.stdout.write('='*80)
        self.stdout.write(f"Invoices processed: {invoices.count()}")
        self.stdout.write(f"Duplicates {'would be merged' if dry_run else 'merged'}: {total_merged}")
        self.stdout.write(f"Invoices {'would be fixed' if dry_run else 'fixed'}: {total_invoices_fixed}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nRun without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('\nCleanup complete!'))




