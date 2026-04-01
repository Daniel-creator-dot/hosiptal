"""
Admin configuration for accounting models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models_accounting import (
    CostCenter, Account, Transaction, PaymentReceipt, AccountsReceivable,
    GeneralLedger, JournalEntry, JournalEntryLine, PaymentAllocation
)
from .utils_finance import FinancialValidator, FinancialReconciliation


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']  # For autocomplete
    ordering = ['code']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['account_code', 'account_name', 'account_type_badge', 'parent_account', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['account_code', 'account_name']  # For autocomplete
    ordering = ['account_code']

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # Force display name in admin index and breadcrumbs
        self.model._meta.verbose_name = 'Chart of Accounts (Account)'
        self.model._meta.verbose_name_plural = 'Chart of Accounts'

    def account_type_badge(self, obj):
        colors = {
            'asset': 'primary',
            'liability': 'warning',
            'equity': 'info',
            'revenue': 'success',
            'expense': 'danger',
        }
        color = colors.get(obj.account_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_account_type_display())
    account_type_badge.short_description = 'Type'


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2
    fields = ['account', 'cost_center', 'debit_amount', 'credit_amount', 'description', 'ext_ref']
    autocomplete_fields = ['account', 'cost_center']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'entry_date', 'ref', 'source', 'description', 'is_posted_badge', 'entered_by_display', 'approved_by_display']
    list_filter = ['is_posted', 'entry_date', 'source']
    search_fields = ['entry_number', 'description', 'ref']
    ordering = ['-entry_date']
    readonly_fields = ['entry_number', 'approved_by', 'approved_at']
    inlines = [JournalEntryLineInline]
    actions = ['validate_journal_entries', 'post_journal_entries']
    
    def entered_by_display(self, obj):
        return obj.entered_by.username if obj.entered_by else "-"
    entered_by_display.short_description = 'Entered By'
    
    def approved_by_display(self, obj):
        return obj.approved_by.username if obj.approved_by else "-"
    approved_by_display.short_description = 'Approved By'
    
    def is_posted_badge(self, obj):
        if obj.is_posted:
            return format_html('<span class="badge bg-success">Posted</span>')
        return format_html('<span class="badge bg-warning">Draft</span>')
    is_posted_badge.short_description = 'Status'
    
    def validate_journal_entries(self, request, queryset):
        """Validate selected journal entries are balanced"""
        errors = 0
        for entry in queryset:
            result = FinancialValidator.validate_journal_entry_balance(entry)
            if not result['valid']:
                self.message_user(request, f"Journal Entry {entry.entry_number}: {result['error']}", level=messages.ERROR)
                errors += 1
        
        if errors == 0:
            self.message_user(request, f"All {queryset.count()} journal entries are balanced!", level=messages.SUCCESS)
    validate_journal_entries.short_description = "Validate journal entries are balanced"
    
    def post_journal_entries(self, request, queryset):
        """Post selected journal entries to general ledger"""
        posted = 0
        errors = 0
        
        for entry in queryset.filter(is_posted=False):
            try:
                entry.post(user=request.user)
                posted += 1
            except Exception as e:
                self.message_user(request, f"Error posting {entry.entry_number}: {str(e)}", level=messages.ERROR)
                errors += 1
        
        if posted > 0:
            self.message_user(request, f"Successfully posted {posted} journal entries", level=messages.SUCCESS)
    post_journal_entries.short_description = "Post journal entries to GL"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_number', 'transaction_type_badge', 'patient_link', 'amount', 'payment_method', 'status_badge', 'transaction_date']
    list_filter = ['transaction_type', 'payment_method', 'transaction_date']
    search_fields = ['transaction_number', 'patient__first_name', 'patient__last_name', 'reference_number']
    ordering = ['-transaction_date']
    readonly_fields = ['transaction_number']
    
    def transaction_type_badge(self, obj):
        colors = {
            'payment_received': 'success',
            'refund_issued': 'warning',
            'adjustment': 'info',
            'write_off': 'danger',
            'transfer': 'secondary',
        }
        color = colors.get(obj.transaction_type, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_transaction_type_display())
    transaction_type_badge.short_description = 'Type'
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return "-"
    patient_link.short_description = 'Patient'
    
    def status_badge(self, obj):
        return format_html('<span class="badge bg-success">Processed</span>')
    status_badge.short_description = 'Status'


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'patient_display', 'invoice_display', 'amount_paid', 'payment_method', 'receipt_date']
    list_filter = ['payment_method', 'receipt_date']
    search_fields = ['receipt_number', 'patient__first_name', 'patient__last_name']
    ordering = ['-receipt_date']
    readonly_fields = ['receipt_number']
    
    def patient_display(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return "-"
    patient_display.short_description = 'Patient'
    
    def invoice_display(self, obj):
        if obj.invoice:
            url = reverse('admin:hospital_invoice_change', args=[obj.invoice.pk])
            return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
        return "-"
    invoice_display.short_description = 'Invoice'


@admin.register(AccountsReceivable)
class AccountsReceivableAdmin(admin.ModelAdmin):
    list_display = ['invoice_link', 'patient_link', 'outstanding_amount', 'due_date', 'days_overdue', 'aging_bucket_badge']
    list_filter = ['aging_bucket', 'due_date']
    search_fields = ['invoice__invoice_number', 'patient__first_name', 'patient__last_name']
    ordering = ['due_date']
    actions = ['update_aging', 'reconcile_with_invoices']
    
    def invoice_link(self, obj):
        if obj.invoice:
            url = reverse('admin:hospital_invoice_change', args=[obj.invoice.pk])
            return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
        return "-"
    invoice_link.short_description = 'Invoice'
    
    def patient_link(self, obj):
        if obj.patient:
            url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
        return "-"
    patient_link.short_description = 'Patient'
    
    def aging_bucket_badge(self, obj):
        colors = {
            'current': 'success',
            '31-60': 'warning',
            '61-90': 'warning',
            '90+': 'danger',
        }
        color = colors.get(obj.aging_bucket, 'secondary')
        return format_html('<span class="badge bg-{}">{}</span>', color, obj.get_aging_bucket_display())
    aging_bucket_badge.short_description = 'Aging'
    
    def update_aging(self, request, queryset):
        """Update aging for selected AR entries"""
        count = 0
        for ar in queryset:
            ar.update_aging()
            count += 1
        self.message_user(request, f"Updated aging for {count} AR entries", level=messages.SUCCESS)
    update_aging.short_description = "Update aging buckets"
    
    def reconcile_with_invoices(self, request, queryset):
        """Reconcile selected AR entries with their invoices"""
        issues = 0
        for ar in queryset:
            result = FinancialValidator.validate_ar_vs_invoice(ar.invoice)
            if not result['valid']:
                self.message_user(request, f"AR {ar.invoice.invoice_number}: {result['error']}", level=messages.ERROR)
                issues += 1
        
        if issues == 0:
            self.message_user(request, f"All {queryset.count()} AR entries match their invoices!", level=messages.SUCCESS)
    reconcile_with_invoices.short_description = "Reconcile with invoices"


@admin.register(GeneralLedger)
class GeneralLedgerAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'transaction_date', 'account_link', 'debit_amount', 'credit_amount', 'description']
    list_filter = ['transaction_date', 'account']
    search_fields = ['entry_number', 'description', 'account__account_code']
    ordering = ['-transaction_date', '-created']
    readonly_fields = ['entry_number']
    actions = ['validate_gl_balance']
    
    def account_link(self, obj):
        if obj.account:
            url = reverse('admin:hospital_account_change', args=[obj.account.pk])
            return format_html('<a href="{}">{} - {}</a>', url, obj.account.account_code, obj.account.account_name)
        return "-"
    account_link.short_description = 'Account'
    
    def validate_gl_balance(self, request, queryset):
        """Validate that general ledger is balanced"""
        result = FinancialValidator.validate_general_ledger_balance()
        if result['valid']:
            self.message_user(
                request, 
                f"General Ledger is balanced! Total Debits: GHS {result['total_debits']}, Total Credits: ${result['total_credits']}", 
                level=messages.SUCCESS
            )
        else:
            self.message_user(request, result['error'], level=messages.ERROR)
    validate_gl_balance.short_description = "Validate general ledger balance"


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ['payment_transaction_link', 'invoice_link', 'allocated_amount', 'allocation_date']
    list_filter = ['allocation_date']
    search_fields = ['payment_transaction__transaction_number', 'invoice__invoice_number']
    ordering = ['-allocation_date']
    
    def payment_transaction_link(self, obj):
        if obj.payment_transaction:
            url = reverse('admin:hospital_transaction_change', args=[obj.payment_transaction.pk])
            return format_html('<a href="{}">{}</a>', url, obj.payment_transaction.transaction_number)
        return "-"
    payment_transaction_link.short_description = 'Transaction'
    
    def invoice_link(self, obj):
        if obj.invoice:
            url = reverse('admin:hospital_invoice_change', args=[obj.invoice.pk])
            return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
        return "-"
    invoice_link.short_description = 'Invoice'

