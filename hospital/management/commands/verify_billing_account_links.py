"""
Django Management Command to Verify Billing Account Links
Ensures all invoices are properly linked to company accounts (insurance/corporate)
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from hospital.models import Invoice
from hospital.services.billing_account_link_service import BillingAccountLinkService


class Command(BaseCommand):
    help = 'Verify all invoices are properly linked to company accounts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix any issues found'
        )
    
    def handle(self, *args, **options):
        fix_issues = options['fix']
        
        self.stdout.write('='*80)
        self.stdout.write('VERIFYING BILLING ACCOUNT LINKS')
        self.stdout.write('='*80)
        
        # Get all invoices
        invoices = Invoice.objects.filter(is_deleted=False).select_related('payer', 'patient')
        
        self.stdout.write(f'\nChecking {invoices.count()} invoices...\n')
        
        insurance_invoices = 0
        corporate_invoices = 0
        cash_invoices = 0
        issues = []
        fixed = 0
        
        for invoice in invoices:
            if not invoice.payer:
                issues.append({
                    'invoice': invoice.invoice_number,
                    'patient': invoice.patient.mrn if invoice.patient else 'N/A',
                    'issue': 'No payer assigned',
                    'type': 'missing_payer'
                })
                continue
            
            payer_type = invoice.payer.payer_type
            
            if payer_type == 'cash':
                cash_invoices += 1
            elif payer_type == 'corporate':
                corporate_invoices += 1
                # Verify corporate link
                result = BillingAccountLinkService.ensure_invoice_linked_to_account(invoice)
                if not result['success']:
                    issues.append({
                        'invoice': invoice.invoice_number,
                        'patient': invoice.patient.mrn if invoice.patient else 'N/A',
                        'payer': invoice.payer.name,
                        'issue': result['message'],
                        'type': 'corporate_link'
                    })
            elif payer_type in ['insurance', 'private', 'nhis']:
                insurance_invoices += 1
                # Verify insurance link
                result = BillingAccountLinkService.ensure_invoice_linked_to_account(invoice)
                if not result['success']:
                    issues.append({
                        'invoice': invoice.invoice_number,
                        'patient': invoice.patient.mrn if invoice.patient else 'N/A',
                        'payer': invoice.payer.name,
                        'issue': result['message'],
                        'type': 'insurance_link'
                    })
            else:
                issues.append({
                    'invoice': invoice.invoice_number,
                    'patient': invoice.patient.mrn if invoice.patient else 'N/A',
                    'payer': invoice.payer.name,
                    'issue': f'Unknown payer type: {payer_type}',
                    'type': 'unknown_payer'
                })
        
        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write('SUMMARY')
        self.stdout.write('='*80)
        self.stdout.write(f'  Total invoices: {invoices.count()}')
        self.stdout.write(f'  Insurance invoices: {insurance_invoices}')
        self.stdout.write(f'  Corporate invoices: {corporate_invoices}')
        self.stdout.write(f'  Cash invoices: {cash_invoices}')
        self.stdout.write(f'  Issues found: {len(issues)}')
        
        if issues:
            self.stdout.write('\n' + '='*80)
            self.stdout.write('ISSUES FOUND')
            self.stdout.write('='*80)
            for issue in issues[:20]:  # Show first 20
                self.stdout.write(
                    self.style.WARNING(
                        f"  Invoice {issue['invoice']} (Patient: {issue['patient']}, Payer: {issue.get('payer', 'N/A')})"
                    )
                )
                self.stdout.write(f"    Issue: {issue['issue']}")
            
            if len(issues) > 20:
                self.stdout.write(f'\n  ... and {len(issues) - 20} more issues')
        
        # Final verification
        verification = BillingAccountLinkService.verify_all_invoices_linked()
        self.stdout.write('\n' + '='*80)
        self.stdout.write('VERIFICATION RESULTS')
        self.stdout.write('='*80)
        self.stdout.write(f'  Total invoices: {verification['total_invoices']}')
        self.stdout.write(f'  Verified: {verification['verified']}')
        self.stdout.write(f'  Success rate: {verification['success_rate']:.1f}%')
        
        if verification['issues']:
            self.stdout.write(f'\n  Issues: {len(verification['issues'])}')
        
        self.stdout.write('='*80)
        
        if issues:
            self.stdout.write(self.style.WARNING('\n⚠️  Some issues found. Review the list above.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ All invoices properly linked!'))
