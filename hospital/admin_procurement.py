"""
Admin interfaces for Procurement and Inventory Management System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models_procurement import (
    Store, InventoryItem, StoreTransfer, StoreTransferLine,
    ProcurementRequest, ProcurementRequestItem, InventoryCategory
)


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_for_pharmacy', 'display_order', 'is_active', 'item_count']
    list_filter = ['is_for_pharmacy', 'is_active']
    search_fields = ['name', 'code']
    ordering = ['display_order', 'name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Settings', {
            'fields': ('is_for_pharmacy', 'display_order', 'is_active')
        }),
    )
    
    def item_count(self, obj):
        return obj.items.filter(is_deleted=False).count()
    item_count.short_description = 'Items'


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'store_type', 'department', 'manager', 'get_total_items', 'get_total_value_display', 'is_active']
    list_filter = ['store_type', 'department', 'is_active']
    search_fields = ['name', 'code', 'location']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'store_type', 'department', 'location', 'description')
        }),
        ('Management', {
            'fields': ('manager', 'is_active')
        }),
    )
    
    def get_total_items(self, obj):
        return obj.get_total_items()
    get_total_items.short_description = 'Total Items'
    
    def get_total_value_display(self, obj):
        return f"GHS {obj.get_total_value():,.2f}"
    get_total_value_display.short_description = 'Total Value'


class ProcurementRequestItemInline(admin.TabularInline):
    model = ProcurementRequestItem
    extra = 1
    fields = ['item_name', 'item_code', 'drug', 'quantity', 'unit_of_measure', 'estimated_unit_price', 'line_total']
    readonly_fields = ['line_total']


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_number', 'requested_by_store', 'requested_by', 'request_date',
        'status_badge', 'priority', 'estimated_total_display', 'admin_approved_by', 'accounts_approved_by'
    ]
    list_filter = ['status', 'priority', 'request_date', 'requested_by_store']
    search_fields = ['request_number', 'requested_by_store__name', 'requested_by__user__username']
    readonly_fields = [
        'request_number', 'estimated_total', 'admin_approved_at', 'accounts_approved_at',
        'admin_approved_by', 'accounts_approved_by'
    ]
    fieldsets = (
        ('Request Information', {
            'fields': ('request_number', 'requested_by_store', 'requested_by', 'request_date', 'priority', 'status')
        }),
        ('Financial', {
            'fields': ('estimated_total', 'approved_budget')
        }),
        ('Approval Workflow', {
            'fields': (
                ('admin_approved_by', 'admin_approved_at'),
                ('admin_rejection_reason',),
                ('accounts_approved_by', 'accounts_approved_at'),
                ('accounts_rejection_reason',),
            )
        }),
        ('Additional Information', {
            'fields': ('justification', 'notes', 'purchase_order')
        }),
    )
    inlines = [ProcurementRequestItemInline]
    
    actions = ['approve_as_admin', 'approve_as_accounts', 'mark_payment_processed', 'mark_as_received']
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'submitted': 'blue',
            'admin_approved': 'orange',
            'accounts_approved': 'green',
            'payment_processed': 'purple',
            'ordered': 'teal',
            'received': 'darkgreen',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def estimated_total_display(self, obj):
        return f"GHS {obj.estimated_total:,.2f}"
    estimated_total_display.short_description = 'Estimated Total'
    
    def approve_as_admin(self, request, queryset):
        """Admin action to approve requests"""
        staff = request.user.staff if hasattr(request.user, 'staff_profile') else None
        if not staff:
            self.message_user(request, "Please link your user to a staff profile", level='error')
            return
        
        approved = 0
        for req in queryset.filter(status='submitted'):
            try:
                req.approve_by_admin(staff)
                approved += 1
            except ValueError as e:
                self.message_user(request, f"Error approving {req.request_number}: {str(e)}", level='error')
        
        self.message_user(request, f"{approved} request(s) approved by admin", level='success')
    approve_as_admin.short_description = "Approve by Admin"
    
    def approve_as_accounts(self, request, queryset):
        """Accounts action to approve requests"""
        staff = request.user.staff if hasattr(request.user, 'staff_profile') else None
        if not staff:
            self.message_user(request, "Please link your user to a staff profile", level='error')
            return
        
        approved = 0
        for req in queryset.filter(status='admin_approved'):
            try:
                req.approve_by_accounts(staff)
                approved += 1
            except ValueError as e:
                self.message_user(request, f"Error approving {req.request_number}: {str(e)}", level='error')
        
        self.message_user(request, f"{approved} request(s) approved by accounts", level='success')
    approve_as_accounts.short_description = "Approve by Accounts"
    
    def mark_payment_processed(self, request, queryset):
        """Mark requests as payment processed"""
        staff = request.user.staff if hasattr(request.user, 'staff_profile') else None
        if not staff:
            self.message_user(request, "Please link your user to a staff profile", level='error')
            return
        
        processed = 0
        for req in queryset.filter(status='accounts_approved'):
            try:
                req.process_payment(staff)
                processed += 1
            except ValueError as e:
                self.message_user(request, f"Error processing {req.request_number}: {str(e)}", level='error')
        
        self.message_user(request, f"{processed} request(s) marked as payment processed", level='success')
    mark_payment_processed.short_description = "Mark Payment Processed"
    
    def mark_as_received(self, request, queryset):
        """Mark requests as received"""
        staff = request.user.staff if hasattr(request.user, 'staff_profile') else None
        if not staff:
            self.message_user(request, "Please link your user to a staff profile", level='error')
            return
        
        received = 0
        for req in queryset.filter(status__in=['ordered', 'payment_processed']):
            try:
                req.mark_as_received(staff)
                received += 1
            except ValueError as e:
                self.message_user(request, f"Error receiving {req.request_number}: {str(e)}", level='error')
        
        self.message_user(request, f"{received} request(s) marked as received", level='success')
    mark_as_received.short_description = "Mark as Received"


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        'item_name', 'store', 'category', 'item_code', 'quantity_on_hand', 'reorder_level',
        'needs_reorder_badge', 'unit_cost', 'total_value_display'
    ]
    list_filter = ['store', 'category', 'is_active']
    search_fields = ['item_name', 'item_code', 'description']

    def has_change_permission(self, request, obj=None):
        """Only admins can edit inventory/stock - restrict procurement/pharmacy from changing quantities"""
        from .views_procurement import is_admin_user
        if not is_admin_user(request.user):
            return False
        return super().has_change_permission(request, obj)
    fieldsets = (
        ('Item Information', {
            'fields': ('store', 'category', 'item_name', 'item_code', 'description', 'drug'),
            'description': 'Item code will be auto-generated if left blank. Format: {CATEGORY}-{STORE}-{NUMBER}'
        }),
        ('Inventory', {
            'fields': ('quantity_on_hand', 'reorder_level', 'reorder_quantity', 'unit_of_measure')
        }),
        ('Pricing & Supplier', {
            'fields': ('unit_cost', 'preferred_supplier')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Ensure item code is generated if missing"""
        # If item_code is empty, let the save() method generate it
        if not obj.item_code or obj.item_code.strip() == '':
            obj.item_code = ''
        super().save_model(request, obj, form, change)
    
    def needs_reorder_badge(self, obj):
        if obj.needs_reorder():
            return format_html('<span style="background-color: #f59e0b; color: white; padding: 4px 8px; border-radius: 4px;">Low Stock</span>')
        return format_html('<span style="background-color: #10b981; color: white; padding: 4px 8px; border-radius: 4px;">In Stock</span>')
    needs_reorder_badge.short_description = 'Stock Status'
    
    def total_value_display(self, obj):
        return f"GHS {obj.get_total_value():,.2f}"
    total_value_display.short_description = 'Total Value'
    
    def needs_reorder(self, obj):
        return obj.needs_reorder()
    needs_reorder.boolean = True
    needs_reorder.short_description = 'Needs Reorder'


class StoreTransferLineInline(admin.TabularInline):
    model = StoreTransferLine
    extra = 1
    fields = ['item_code', 'item_name', 'quantity', 'unit_cost', 'unit_of_measure']


@admin.register(StoreTransfer)
class StoreTransferAdmin(admin.ModelAdmin):
    list_display = [
        'transfer_number', 'from_store', 'to_store', 'transfer_date',
        'status_badge', 'requested_by', 'approved_by'
    ]
    list_filter = ['status', 'transfer_date', 'from_store', 'to_store']
    search_fields = ['transfer_number', 'from_store__name', 'to_store__name']
    readonly_fields = ['transfer_number', 'approved_at', 'received_at']
    ordering = ['-transfer_date', '-created']  # Use 'created' and 'modified', not 'updated'
    fieldsets = (
        ('Transfer Information', {
            'fields': ('transfer_number', 'from_store', 'to_store', 'transfer_date', 'status')
        }),
        ('Workflow', {
            'fields': (
                ('requested_by',),
                ('approved_by', 'approved_at'),
                ('received_by', 'received_at'),
            )
        }),
        ('Additional', {
            'fields': ('notes',)
        }),
    )
    inlines = [StoreTransferLineInline]
    
    actions = ['approve_transfers', 'complete_transfers']
    
    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'approved': 'orange',
            'in_transit': 'blue',
            'completed': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approve_transfers(self, request, queryset):
        """Approve transfers"""
        staff = request.user.staff if hasattr(request.user, 'staff_profile') else None
        if not staff:
            self.message_user(request, "Please link your user to a staff profile", level='error')
            return
        
        approved = 0
        for transfer in queryset.filter(status='pending'):
            transfer.status = 'approved'
            transfer.approved_by = staff
            transfer.approved_at = timezone.now()
            transfer.save()
            approved += 1
        
        self.message_user(request, f"{approved} transfer(s) approved", level='success')
    approve_transfers.short_description = "Approve Transfers"
    
    def complete_transfers(self, request, queryset):
        """Complete transfers"""
        staff = request.user.staff if hasattr(request.user, 'staff_profile') else None
        if not staff:
            self.message_user(request, "Please link your user to a staff profile", level='error')
            return
        
        completed = 0
        for transfer in queryset.filter(status='approved'):
            try:
                transfer.complete_transfer(staff)
                completed += 1
            except ValueError as e:
                self.message_user(request, f"Error completing {transfer.transfer_number}: {str(e)}", level='error')
        
        self.message_user(request, f"{completed} transfer(s) completed", level='success')
    complete_transfers.short_description = "Complete Transfers"

