"""
Management command to audit billing system
Validates invoices and reconciles discrepancies
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from hospital.models import Invoice
from hospital.services.billing_validation_service import billing_validator


class Command(BaseCommand):
    help = 'Audit billing system - validate invoices and fix discrepancies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix errors by reconciling invoices',
        )
        parser.add_argument(
            '--payer-type',
            type=str,
            choices=['cash', 'corporate', 'nhis', 'private'],
            help='Filter by payer type',
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['draft', 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled'],
            help='Filter by invoice status',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of invoices to process',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting billing audit...'))
        
        # Build query
        query = Q(is_deleted=False)
        
        if options['payer_type']:
            query &= Q(payer__payer_type=options['payer_type'])
        
        if options['status']:
            query &= Q(status=options['status'])
        
        invoices = Invoice.objects.filter(query).select_related('patient', 'payer')[:options['limit']]
        
        self.stdout.write(f'Found {invoices.count()} invoice(s) to audit')
        
        # Validate batch
        results = billing_validator.validate_invoice_batch(
            invoices=invoices,
            fix_errors=options['fix']
        )
        
        # Display results
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('AUDIT RESULTS'))
        self.stdout.write('='*80)
        self.stdout.write(f"Total invoices checked: {results['total']}")
        self.stdout.write(f"Valid invoices: {results['valid']}")
        self.stdout.write(f"Invalid invoices: {results['invalid']}")
        self.stdout.write(f"Total errors: {results['errors_count']}")
        self.stdout.write(f"Total warnings: {results['warnings_count']}")
        if options['fix']:
            self.stdout.write(f"Invoices fixed: {results['fixed']}")
        
        # Display details for invalid invoices
        if results['invalid'] > 0:
            self.stdout.write('\n' + '-'*80)
            self.stdout.write(self.style.ERROR('INVALID INVOICES:'))
            self.stdout.write('-'*80)
            for detail in results['details']:
                if not detail['valid']:
                    self.stdout.write(f"\nInvoice: {detail['invoice_number']}")
                    self.stdout.write(f"Patient: {detail['patient']}")
                    self.stdout.write(f"Errors ({detail['error_count']}):")
                    for error in detail['errors']:
                        self.stdout.write(f"  - {error}")
                    if detail['warnings']:
                        self.stdout.write(f"Warnings ({detail['warning_count']}):")
                        for warning in detail['warnings']:
                            self.stdout.write(f"  - {warning}")
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('Audit complete!'))





