"""
Forms for Procurement and Inventory Management
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Fieldset, HTML
from .models_procurement import (
    Store, InventoryItem, StoreTransfer, StoreTransferLine,
    ProcurementRequest, ProcurementRequestItem, InventoryCategory
)
from .models_missing_features import Supplier
from .models import Department, Staff, Drug


class SupplierForm(forms.ModelForm):
    """Supplier creation/edit form"""
    class Meta:
        model = Supplier
        fields = [
            'name', 'contact_person', 'phone', 'email',
            'address', 'tax_id', 'payment_terms', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'supplier@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Net 30, Net 60'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset('Supplier Information',
                Row(Column('name', css_class='form-group col-md-8'),
                    Column('is_active', css_class='form-group col-md-4')),
                Row(Column('contact_person', css_class='form-group col-md-6'),
                    Column('phone', css_class='form-group col-md-6')),
                'email',
                'address',
                Row(Column('tax_id', css_class='form-group col-md-6'),
                    Column('payment_terms', css_class='form-group col-md-6')),
            ),
            Submit('submit', 'Save Supplier', css_class='btn btn-primary btn-modern')
        )


class StoreForm(forms.ModelForm):
    """Store creation/edit form"""
    class Meta:
        model = Store
        fields = [
            'name', 'code', 'store_type', 'department',
            'location', 'manager', 'description', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'store_type': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(is_active=True, is_deleted=False)
        self.fields['manager'].queryset = Staff.objects.filter(is_active=True, is_deleted=False)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset('Store Information',
                Row(Column('name', css_class='form-group col-md-8'),
                    Column('code', css_class='form-group col-md-4')),
                Row(Column('store_type', css_class='form-group col-md-6'),
                    Column('department', css_class='form-group col-md-6')),
                Row(Column('location', css_class='form-group col-md-6'),
                    Column('manager', css_class='form-group col-md-6')),
                'description',
                'is_active',
            ),
            Submit('submit', 'Save Store', css_class='btn btn-primary btn-modern')
        )


class InventoryItemForm(forms.ModelForm):
    """Inventory item creation/edit form with duplicate detection"""
    class Meta:
        model = InventoryItem
        fields = [
            'store', 'category', 'item_name', 'item_code', 'description', 'drug',
            'quantity_on_hand', 'reorder_level', 'reorder_quantity',
            'unit_cost', 'unit_of_measure', 'preferred_supplier', 'is_active'
        ]
        widgets = {
            'store': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'item_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'item_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated if left blank'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'drug': forms.Select(attrs={'class': 'form-select'}),
            'quantity_on_hand': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1}),
            'reorder_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., units, boxes, packs'}),
            'preferred_supplier': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['store'].queryset = Store.objects.filter(is_active=True, is_deleted=False)
        self.fields['category'].queryset = InventoryCategory.objects.filter(is_active=True, is_deleted=False)
        self.fields['drug'].queryset = Drug.objects.filter(is_deleted=False).order_by('name')
        self.fields['preferred_supplier'].queryset = Supplier.objects.filter(is_active=True, is_deleted=False)
        self.fields['drug'].required = False
        self.fields['category'].required = False
        self.fields['preferred_supplier'].required = False
        
        # Add help text with link to classification guide
        self.fields['drug'].help_text = 'Select a drug from the formulary. If the drug has a category, it will be auto-filled. <a href="/hms/drug-classification-guide/" target="_blank" class="btn btn-sm btn-outline-info ms-2"><i class="bi bi-book"></i> Browse Categories</a>'
        self.fields['drug'].widget.attrs.update({
            'class': 'form-select drug-select',
            'onchange': 'updateCategoryFromDrug(this)'
        })
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset('Item Information',
                Row(Column('store', css_class='form-group col-md-6'),
                    Column('category', css_class='form-group col-md-6')),
                Row(Column('item_name', css_class='form-group col-md-8'),
                    Column('item_code', css_class='form-group col-md-4')),
                'description',
                'drug',
            ),
            Fieldset('Inventory Details',
                Row(Column('quantity_on_hand', css_class='form-group col-md-4'),
                    Column('reorder_level', css_class='form-group col-md-4'),
                    Column('reorder_quantity', css_class='form-group col-md-4')),
                Row(Column('unit_cost', css_class='form-group col-md-6'),
                    Column('unit_of_measure', css_class='form-group col-md-6')),
            ),
            Fieldset('Supplier & Status',
                'preferred_supplier',
                'is_active',
            ),
            Submit('submit', 'Save Item', css_class='btn btn-primary btn-modern')
        )


class ProcurementRequestForm(forms.ModelForm):
    """Procurement request creation form"""
    class Meta:
        model = ProcurementRequest
        fields = [
            'requested_by_store', 'priority', 'justification', 'notes'
        ]
        widgets = {
            'requested_by_store': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'justification': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Explain why this procurement is needed...'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['requested_by_store'].queryset = Store.objects.filter(is_active=True, is_deleted=False)
        self.helper = FormHelper()
        # This form is rendered inside a <form> tag in the template.
        # If we let crispy render its own <form>, the browser ends up with nested forms,
        # and the inline formset management fields (items-TOTAL_FORMS/INITIAL_FORMS)
        # won't be submitted — causing "ManagementForm data is missing" errors.
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset('Request Information',
                Row(Column('requested_by_store', css_class='form-group col-md-6'),
                    Column('priority', css_class='form-group col-md-6')),
                'justification',
                'notes',
            ),
            HTML('<p class="text-muted small">Add request items below, then click <strong>Save Request</strong>.</p>'),
        )


class ProcurementRequestItemForm(forms.ModelForm):
    """Procurement request item form (for inline items)"""
    class Meta:
        model = ProcurementRequestItem
        fields = [
            'item_name', 'item_code', 'description', 'drug', 'quantity',
            'unit_of_measure', 'estimated_unit_price', 'preferred_supplier', 'specifications'
        ]
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'item_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated if blank'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'drug': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., units, boxes'}),
            'estimated_unit_price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'preferred_supplier': forms.Select(attrs={'class': 'form-select'}),
            'specifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['drug'].queryset = Drug.objects.filter(is_deleted=False).order_by('name')
        self.fields['preferred_supplier'].queryset = Supplier.objects.filter(is_active=True, is_deleted=False)
        self.fields['drug'].required = False
        self.fields['preferred_supplier'].required = False
        # Important UX: this form is used in a 20-row formset.
        # If these are required at the HTML level, the browser forces users to fill ALL rows.
        # We validate "completeness" in clean() only for rows the user started filling.
        self.fields['item_name'].required = False
        self.fields['quantity'].required = False
        self.fields['estimated_unit_price'].required = False
        
        # Add help text with link to classification guide
        self.fields['drug'].help_text = 'Select a drug from the formulary. <a href="/hms/drug-classification-guide/" target="_blank" class="btn btn-sm btn-outline-info ms-2"><i class="bi bi-book"></i> Browse Categories</a>'
        self.fields['drug'].widget.attrs.update({
            'class': 'form-select drug-select',
            'onchange': 'updateItemNameFromDrug(this)'
        })

    def clean(self):
        cleaned_data = super().clean()

        item_name = (cleaned_data.get('item_name') or '').strip()
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('estimated_unit_price')
        delete = cleaned_data.get('DELETE', False)

        # If user marks the row for deletion, skip completeness validation.
        if delete:
            return cleaned_data

        # Treat the row as "started" if any of the key fields has a value.
        started = bool(item_name) or bool(quantity) or (unit_price is not None and unit_price != '')

        if started:
            errors = {}
            if not item_name:
                errors['item_name'] = 'Item name is required for this line.'
            if not quantity:
                errors['quantity'] = 'Quantity is required for this line.'
            if unit_price is None:
                errors['estimated_unit_price'] = 'Unit price is required for this line.'

            for field, msg in errors.items():
                self.add_error(field, msg)

        return cleaned_data


ProcurementRequestItemFormSet = forms.inlineformset_factory(
    ProcurementRequest,
    ProcurementRequestItem,
    form=ProcurementRequestItemForm,
    extra=20,
    max_num=20,
    validate_max=True,
    can_delete=True,
    min_num=1,
    validate_min=False  # Set to False to allow saving draft requests without items
)


class StoreTransferForm(forms.ModelForm):
    """Store transfer creation form"""
    class Meta:
        model = StoreTransfer
        fields = [
            'from_store', 'to_store', 'transfer_date', 'notes'
        ]
        widgets = {
            'from_store': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'to_store': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'transfer_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        stores = Store.objects.filter(is_active=True, is_deleted=False)
        self.fields['from_store'].queryset = stores
        self.fields['to_store'].queryset = stores
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset('Transfer Information',
                Row(Column('from_store', css_class='form-group col-md-6'),
                    Column('to_store', css_class='form-group col-md-6')),
                Row(Column('transfer_date', css_class='form-group col-md-6')),
                'notes',
            ),
            HTML('<p class="text-muted small">After saving, you can add items to this transfer.</p>'),
            Submit('submit', 'Create Transfer', css_class='btn btn-primary btn-modern')
        )
    
    def clean(self):
        cleaned_data = super().clean()
        from_store = cleaned_data.get('from_store')
        to_store = cleaned_data.get('to_store')
        
        if from_store and to_store and from_store == to_store:
            raise forms.ValidationError("From store and To store cannot be the same.")
        
        return cleaned_data


class StoreTransferLineForm(forms.ModelForm):
    """Store transfer line item form"""
    class Meta:
        model = StoreTransferLine
        fields = [
            'item_code', 'item_name', 'quantity', 'unit_cost', 'unit_of_measure', 'notes'
        ]
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control'}),
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'form-control', 'value': 'units'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields not required - we'll validate on the backend
        for field in self.fields:
            self.fields[field].required = False


StoreTransferLineFormSet = forms.inlineformset_factory(
    StoreTransfer,
    StoreTransferLine,
    form=StoreTransferLineForm,
    extra=3,
    can_delete=True,
    min_num=0,
    validate_min=False
)


