"""
Role-Based Access Control Utilities
Detect user roles and provide appropriate permissions
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


# Role definitions with their features
ROLE_FEATURES = {
    'admin': {
        'name': 'Administrator',
        'color': '#ef4444',
        'icon': 'shield-fill-check',
        'features': 'all',  # Access to everything
        'dashboards': [
            'patient_management',
            'encounters',
            'accounting',
            'hr',
            'medical',
            'pharmacy',
            'laboratory',
            'imaging',
            'inventory',
            'reports',
        ]
    },
    'accountant': {
        'name': 'Accountant',
        'color': '#10b981',
        'icon': 'calculator',
        'dashboards': [
            'accounting',
            'invoices',
            'payments',
            'cashier',
            'reports_financial',
            'revenue_streams',
        ],
        'features': [
            'view_invoice',
            'add_invoice',
            'change_invoice',
            'view_payment',
            'add_payment',
            'view_cashiersession',
            'view_journalentry',
            'view_account',
            'view_corporateaccount',
            'view_revenuestream',
            'view_departmentrevenue',
            'view_revenue',
            'can_approve_procurement_accounts',
            'view_procurementrequest',
            'view_procurementrequestitem',
        ]
    },
    'account_personnel': {
        'name': 'Account Personnel',
        'color': '#6366f1',
        'icon': 'person-badge',
        'dashboards': [
            'accounting',
            'petty_cash',
        ],
        'features': [
            'view_account',
            'view_journalentry',
            'view_pettycashtransaction',
            'add_pettycashtransaction',
            'change_pettycashtransaction',
        ]
    },
    'account_officer': {
        'name': 'Account Officer',
        'color': '#f59e0b',
        'icon': 'shield-check',
        'dashboards': [
            'accounting',
            'petty_cash',
            'approvals',
        ],
        'features': [
            'view_account',
            'view_journalentry',
            'view_pettycashtransaction',
            'add_pettycashtransaction',
            'change_pettycashtransaction',
            'approve_pettycashtransaction',
            'can_approve_procurement_accounts',
            'view_procurementrequest',
        ]
    },
    'senior_account_officer': {
        'name': 'Senior Account Officer',
        'color': '#059669',
        'icon': 'shield-check',
        'dashboards': [
            'senior_accounting',
            'accounting',
            'account_staff_management',
            'petty_cash',
            'approvals',
            'reports_financial',
        ],
        'features': [
            # Full accounting access
            'view_account',
            'add_account',
            'change_account',
            'view_journalentry',
            'add_journalentry',
            'change_journalentry',
            'view_pettycashtransaction',
            'add_pettycashtransaction',
            'change_pettycashtransaction',
            'approve_pettycashtransaction',
            'can_approve_procurement_accounts',
            'view_procurementrequest',
            'view_invoice',
            'add_invoice',
            'change_invoice',
            'view_payment',
            'add_payment',
            'view_cashiersession',
            'view_corporateaccount',
            'view_revenuestream',
            'view_departmentrevenue',
            'view_revenue',
            # Account staff management (ONLY account-related staff)
            'view_account_staff',  # Custom permission for account staff only
            'change_account_staff',  # Can update account staff records
            # NO access to general staff (HR function)
        ]
    },
    'hr_manager': {
        'name': 'HR Manager',
        'color': '#8b5cf6',
        'icon': 'people-fill',
        'dashboards': [
            'hr',
            'staff',
            'payroll',
            'leave',
            'attendance',
            'performance',
            'recruitment',
        ],
        'features': [
            'view_staff',
            'add_staff',
            'change_staff',
            'view_payroll',
            'view_leaverequest',
            'change_leaverequest',
            'view_staffshift',
            'view_performancereview',
            'view_staffcontract',
            'view_hospitalactivity',
            'add_hospitalactivity',
            'change_hospitalactivity',
        ]
    },
    'hr': {
        'name': 'HR Services',
        'color': '#a855f7',
        'icon': 'person-rolodex',
        'dashboards': [
            'hr_service_center',
            'staff_directory',
            'leave_management',
            'attendance',
            'payroll',
        ],
        'features': [
            'view_staff',
            'change_staff',
            'view_payroll',
            'view_leaverequest',
            'change_leaverequest',
            'view_staffshift',
            'view_staffcontract',
            'view_hospitalactivity',
        ]
    },
    'doctor': {
        'name': 'Doctor',
        'color': '#3b82f6',
        'icon': 'heart-pulse-fill',
        'dashboards': [
            'patient_management',
            'encounters',
            'medical_records',
            'prescriptions',
            'orders',
            'triage',
        ],
        'features': [
            'view_patient',
            'add_patient',
            'change_patient',
            'view_encounter',
            'add_encounter',
            'change_encounter',
            'view_medicalrecord',
            'add_medicalrecord',
            'view_prescription',
            'add_prescription',
            'view_order',
            'add_order',
            'view_vitalsign',
        ]
    },
    'nurse': {
        'name': 'Nurse',
        'color': '#06b6d4',
        'icon': 'heart-fill',
        'dashboards': [
            'patient_management',
            'encounters',
            'triage',
            'vitals',
            'orders',
        ],
        'features': [
            'view_patient',
            'view_encounter',
            'change_encounter',
            'view_vitalsign',
            'add_vitalsign',
            'change_vitalsign',
            'view_order',
            'change_order',
        ]
    },
    'midwife': {
        'name': 'Midwife',
        'color': '#ec4899',
        'icon': 'heart-pulse-fill',
        'dashboards': [
            'maternity_care',
            'patient_management',
            'encounters',
            'triage',  # Added: Midwives can access triage
            'vitals',
            'orders',  # Added: Midwives can view orders
        ],
        'features': [
            'view_patient',
            'view_encounter',
            'change_encounter',
            'view_vitalsign',
            'add_vitalsign',
            'change_vitalsign',
            'view_order',  # Added: Midwives can view orders
            'change_order',  # Added: Midwives can change orders
            'view_maternity_record',
            'add_maternity_record',
            'change_maternity_record',
        ]
    },
    'pharmacist': {
        'name': 'Pharmacist',
        'color': '#f59e0b',
        'icon': 'capsule-pill',
        'dashboards': [
            'pharmacy_dispensing',
            'payment_verification',
        ],
        'features': [
            'view_prescription',
            'change_prescription',
            'view_drug',
            'add_drug',
            'change_drug',
            'view_inventoryitem',
        ]
    },
    'procurement_officer': {
        'name': 'Procurement Officer',
        'color': '#f59e0b',
        'icon': 'cart-check',
        'dashboards': [
            'procurement',
            'pharmacy',
            'inventory',
            'stores',
            'transfers',
            'requisitions',
            'suppliers',
            'procurement_requests',
            'approvals',
        ],
        'features': [
            'view_store',
            'view_inventoryitem',
            'add_inventoryitem',
            'change_inventoryitem',
            'delete_inventoryitem',
            'view_storetransfer',
            'add_storetransfer',
            'change_storetransfer',
            'view_inventoryrequisition',
            'add_inventoryrequisition',
            'change_inventoryrequisition',
            'view_inventorytransaction',
            'view_inventorybatch',
            'add_inventorybatch',
            'view_stockalert',
            'change_stockalert',
            'view_procurementrequest',
            'add_procurementrequest',
            'change_procurementrequest',
            'view_procurementrequestitem',
            'add_procurementrequestitem',
            'change_procurementrequestitem',
            'view_supplier',
            'add_supplier',
            'change_supplier',
            'view_purchaseorder',
            'add_purchaseorder',
            'change_purchaseorder',
        ]
    },
    'store_manager': {
        'name': 'Store Manager',
        'color': '#8b5cf6',
        'icon': 'box-seam',
        'dashboards': [
            'pharmacy',
            'inventory',
            'stores',
            'transfers',
            'requisitions',
            'procurement',
        ],
        'features': [
            'view_store',
            'view_inventoryitem',
            'add_inventoryitem',
            'change_inventoryitem',
            'delete_inventoryitem',
            'view_storetransfer',
            'add_storetransfer',
            'change_storetransfer',
            'view_inventoryrequisition',
            'add_inventoryrequisition',
            'change_inventoryrequisition',
            'view_inventorytransaction',
            'view_inventorybatch',
            'add_inventorybatch',
            'view_stockalert',
            'change_stockalert',
            'view_procurementrequest',
            'add_procurementrequest',
        ]
    },
    'inventory_stores_manager': {
        'name': 'Inventory & Stores Manager',
        'color': '#10b981',
        'icon': 'boxes',
        'dashboards': [
            'pharmacy',
            'inventory',
            'stores',
            'transfers',
            'requisitions',
            'stock_alerts',
            'analytics',
        ],
        'features': [
            'view_store',
            'add_store',
            'change_store',
            'view_inventoryitem',
            'add_inventoryitem',
            'change_inventoryitem',
            'delete_inventoryitem',
            'view_storetransfer',
            'add_storetransfer',
            'change_storetransfer',
            'view_inventoryrequisition',
            'add_inventoryrequisition',
            'change_inventoryrequisition',
            'view_inventorytransaction',
            'add_inventorytransaction',
            'view_inventorybatch',
            'add_inventorybatch',
            'change_inventorybatch',
            'view_stockalert',
            'add_stockalert',
            'change_stockalert',
            'view_supplier',
            'view_procurementrequest',
        ]
    },
    'lab_technician': {
        'name': 'Lab Technician',
        'color': '#ec4899',
        'icon': 'clipboard2-pulse',
        'dashboards': [
            'laboratory',
            'lab_results',
            'lab_orders',
        ],
        'features': [
            'view_labresult',
            'add_labresult',
            'change_labresult',
            'view_labtest',
            'view_order',
        ]
    },
    'receptionist': {
        'name': 'Receptionist',
        'color': '#14b8a6',
        'icon': 'person-workspace',
        'dashboards': [
            'appointments',
            'patients',
            'registration',
        ],
        'features': [
            'view_patient',
            'add_patient',
            'change_patient',
            'view_appointment',
            'add_appointment',
            'change_appointment',
        ]
    },
    'cashier': {
        'name': 'Cashier',
        'color': '#84cc16',
        'icon': 'cash-stack',
        'dashboards': [
            'cashier',
            'payments',
            'invoices',
        ],
        'features': [
            'view_invoice',
            'view_payment',
            'add_payment',
            'view_cashiersession',
            'add_cashiersession',
            'change_cashiersession',
        ]
    },
    'it': {
        'name': 'IT Staff',
        'color': '#6366f1',
        'icon': 'motherboard',
        'dashboards': [
            'it_operations',
            'system_health',
            'backups',
            'security',
        ],
        'features': [
            'view_auditlog',
            'view_activitylog',
            'view_usersession',
            'view_backup',
        ]
    },
    'it_staff': {
        'name': 'IT Staff',
        'color': '#6366f1',
        'icon': 'motherboard',
        'dashboards': [
            'it_operations',
            'system_health',
            'backups',
            'security',
        ],
        'features': [
            'view_auditlog',
            'view_activitylog',
            'view_usersession',
            'view_backup',
        ]
    },
    'marketing': {
        'name': 'Marketing & Business Development',
        'color': '#ec4899',
        'icon': 'megaphone',
        'dashboards': [
            'marketing',
            'marketing_objectives',
            'marketing_campaigns',
            'marketing_partnerships',
            'marketing_metrics',
        ],
        'features': [
            'view_marketingobjective',
            'add_marketingobjective',
            'change_marketingobjective',
            'view_marketingtask',
            'add_marketingtask',
            'change_marketingtask',
            'view_marketingcampaign',
            'add_marketingcampaign',
            'change_marketingcampaign',
            'view_marketingmetric',
            'add_marketingmetric',
            'change_marketingmetric',
            'view_corporatepartnership',
            'add_corporatepartnership',
            'change_corporatepartnership',
        ]
    },
}


def ensure_staff_profile(request, role_label, expected_profession=None):
    """
    Ensure the requesting user has a Staff profile (and optionally the expected profession).
    expected_profession may be a single string or a sequence of allowed professions.
    Returns tuple (staff, error_response)
    """
    from django.shortcuts import render
    from .models import Staff
    
    staff = None
    try:
        staff = Staff.objects.filter(user=request.user, is_deleted=False).order_by('-created').first()
    except Exception:
        pass
    
    def _profession_ok():
        if not expected_profession:
            return True
        if isinstance(expected_profession, (list, tuple, set)):
            return staff.profession in expected_profession
        return staff.profession == expected_profession

    if not staff or (expected_profession and not _profession_ok()):
        message = f"Access denied. {role_label} role required."
        try:
            response = render(request, 'hospital/access_denied.html', {
                'message': message,
                'dashboard_url': '/hms/',
                'login_url': '/hms/login/',
            }, status=403)
            return None, response
        except Exception:
            from django.http import HttpResponse
            return None, HttpResponse(f"<h1>{message}</h1>", status=403)
    
    return staff, None


def _ensure_staff_flag(user, ensure_superuser=False):
    """Make sure authenticated users retain staff flag so they can log in."""
    if not user or not hasattr(user, 'is_staff'):
        return
    
    try:
        updated = False
        if not user.is_staff:
            user.is_staff = True
            updated = True
        
        if ensure_superuser and not user.is_superuser:
            user.is_superuser = True
            updated = True
        
        if updated:
            user.save(update_fields=['is_staff', 'is_superuser'] if ensure_superuser else ['is_staff'])
    except Exception as e:
        # Log but don't break - this is a helper function
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error ensuring staff flag for {getattr(user, 'username', 'unknown')}: {e}", exc_info=True)


def is_doctor(user):
    """Check if user is a doctor"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    return role == 'doctor'


def is_procurement_staff(user):
    """Check if user has procurement access"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Role-based access (do NOT rely on is_staff, which is used for "can log in")
    try:
        role = get_user_role(user)
        if role in {'admin', 'procurement_officer', 'inventory_stores_manager'}:
            return True
    except Exception:
        pass

    # Explicit group-based access (legacy support)
    if user.groups.filter(name__in=[
        'Admin', 'Administrator',
        'Store Manager', 'Inventory Stores Manager',
        'Procurement', 'Procurement Officer'
    ]).exists():
        return True

    # Staff profile fallback (department/profession)
    try:
        from .models import Staff
        staff = Staff.objects.filter(user=user, is_deleted=False).order_by('-created').first()
        if staff and staff.profession in ['store_manager', 'inventory_manager', 'procurement_officer']:
            return True
        if staff and staff.department and staff.department.name:
            dept_name = staff.department.name.lower()
            if 'procurement' in dept_name or 'store' in dept_name:
                return True
    except Exception:
        pass

    return False


def get_user_role(user):
    """
    Detect user's primary role based on groups and staff profession
    Returns role slug (e.g., 'accountant', 'hr_manager', etc.)
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return 'staff'
    
    if user.is_superuser:
        _ensure_staff_flag(user, ensure_superuser=True)
        return 'admin'

    def _is_lab_profession(prof_norm):
        """Treat common lab profession variants as lab_technician role."""
        if not prof_norm:
            return False
        lab_aliases = {
            'lab_technician',
            'lab_tech',
            'laboratory_technician',
            'laboratory_tech',
            'laboratory_scientist',
            'medical_laboratory_scientist',
            'mls',
            'lab',
            'laboratory',
        }
        return prof_norm in lab_aliases or ('lab' in prof_norm and 'assistant' not in prof_norm)

    # Staff profession wins over generic Django groups (e.g. user in "Nurse" group but job is lab tech → lab)
    try:
        from .models import Staff
        _staff_for_role = Staff.objects.filter(user=user, is_deleted=False).order_by('-created').first()
        if _staff_for_role:
            _prof = getattr(_staff_for_role, 'profession', None)
            _prof_norm = (_prof or '').strip().lower().replace(' ', '_').replace('-', '_')
            if _prof_norm == 'midwife':
                _ensure_staff_flag(user)
                return 'midwife'
            if _is_lab_profession(_prof_norm):
                _ensure_staff_flag(user)
                return 'lab_technician'
    except Exception:
        pass

    # Check Django groups first
    user_groups = user.groups.values_list('name', flat=True)
    
    # PRIORITY 1: Check for Procurement/Store Manager groups FIRST (before other groups)
    procurement_groups = ['procurement', 'procurement_officer', 'store_manager', 'inventory_manager', 'inventory_stores_manager']
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_').replace('&', '_')
        if group_lower in procurement_groups:
            _ensure_staff_flag(user)
            # Map to the correct role
            if group_lower in ['store_manager', 'inventory_manager', 'inventory_stores_manager']:
                return 'inventory_stores_manager'
            elif group_lower in ['procurement', 'procurement_officer']:
                return 'procurement_officer'
    
    # PRIORITY 2: Check for Marketing/Business Development groups (before admin)
    marketing_groups = ['marketing', 'business_development', 'bd', 'marketer']
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_').replace('&', '_')
        if group_lower in marketing_groups:
            _ensure_staff_flag(user)
            return 'marketing'
    
    # PRIORITY 3: Prioritize Accountant group over Account Personnel
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_')
        if group_lower == 'accountant':  # Check for Accountant first
            _ensure_staff_flag(user)
            return 'accountant'
    
    # PRIORITY 4: Then check other groups (but exclude admin for marketing users)
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_').replace('&', '_')
        # Treat "Admin"/"Administrator" groups as system admin role
        if group_lower in ['admin', 'administrator']:
            _ensure_staff_flag(user)
            return 'admin'
        # Skip admin group if user has marketing profession
        if group_lower == 'admin':
            try:
                from .models import Staff
                staff = Staff.objects.filter(user=user, is_deleted=False).first()
                if staff and staff.profession in ['marketer', 'marketing', 'business_development', 'bd']:
                    continue  # Skip admin group for marketing users
            except:
                pass
        if group_lower in ROLE_FEATURES:
            _ensure_staff_flag(user)
            return group_lower
    
    # Fall back to staff profession
    try:
        from .models import Staff
        # Use filter().first() instead of get() to handle multiple staff records
        # This prevents MultipleObjectsReturned errors
        staff = Staff.objects.filter(user=user, is_deleted=False).order_by('-created').first()
        
        if not staff:
            _ensure_staff_flag(user)
            return 'staff'
        
        profession_role_map = {
            'doctor': 'doctor',
            'nurse': 'nurse',
            'midwife': 'midwife',
            'pharmacist': 'pharmacist',
            'lab_technician': 'lab_technician',
            'lab_tech': 'lab_technician',
            'lab': 'lab_technician',
            'laboratory': 'lab_technician',
            'laboratory_technician': 'lab_technician',
            'laboratory_scientist': 'lab_technician',
            'medical_laboratory_scientist': 'lab_technician',
            'mls': 'lab_technician',
            'radiologist': 'radiologist',
            'receptionist': 'receptionist',
            'cashier': 'cashier',
            'store_manager': 'inventory_stores_manager',  # Store managers are inventory/stores managers
            'inventory_manager': 'inventory_stores_manager',
            'procurement_officer': 'procurement_officer',
            'hr_manager': 'hr_manager',
            'accountant': 'accountant',
            'senior_account_officer': 'senior_account_officer',
            'it': 'it',
            'it_staff': 'it',
            'it_support': 'it',  # IT Support profession maps to IT role
            'it_operations': 'it',  # IT Operations profession maps to IT role
            'marketing': 'marketing',  # Marketing profession maps to marketing role
            'marketer': 'marketing',  # Marketer profession maps to marketing role
            'business_development': 'marketing',  # Business Development profession maps to marketing role
            'bd': 'marketing',  # BD profession maps to marketing role
        }
        
        prof_norm = (staff.profession or '').strip().lower().replace(' ', '_').replace('-', '_')

        if _is_lab_profession(prof_norm):
            _ensure_staff_flag(user)
            return 'lab_technician'

        # PRIORITY: Check profession FIRST for procurement/store_manager/marketing (before groups)
        if prof_norm in ['store_manager', 'inventory_manager', 'procurement_officer', 'marketer', 'marketing', 'business_development', 'bd']:
            role = profession_role_map.get(prof_norm, 'staff')
            if role in ['inventory_stores_manager', 'procurement_officer', 'marketing']:
                _ensure_staff_flag(user)
                return role
        
        # Check if user is in IT group
        for group_name in user_groups:
            group_lower = group_name.lower().replace(' ', '_')
            if group_lower in ['it', 'it_staff', 'it_operations', 'it_support']:
                _ensure_staff_flag(user)
                return 'it'
        
        # Check if user is in Marketing group
        for group_name in user_groups:
            group_lower = group_name.lower().replace(' ', '_')
            if group_lower in ['marketing', 'marketing_&_business_development', 'business_development', 'bd']:
                _ensure_staff_flag(user)
                return 'marketing'
        
        # Now check profession (for other roles)
        role = profession_role_map.get(prof_norm, 'staff')
        
        # Special case: If profession contains "it" or "support" and user is staff, map to IT
        if role == 'staff' and prof_norm:
            profession_lower = prof_norm
            if 'it' in profession_lower or ('support' in profession_lower and 'it' in str(staff.department).lower() if staff.department else False):
                role = 'it'
        
        _ensure_staff_flag(user)
        return role
        
    except Exception as e:
        # Log the error for debugging but don't break the app
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error getting user role for {user.username}: {e}", exc_info=True)
        _ensure_staff_flag(user)
        return 'staff'  # Default fallback


def get_user_dashboard_url(user, role=None):
    """
    Get the appropriate dashboard URL for a user based on their role
    """
    role = role or get_user_role(user)
    
    role_urls = {
        'admin': '/hms/admin-dashboard/',
        'accountant': '/hms/accountant/comprehensive-dashboard/',
        'senior_account_officer': '/hms/senior-account-officer/dashboard/',
        'hr_manager': '/hms/hr/worldclass/',
        'hr': '/hms/hr/service-desk/',
        'doctor': '/hms/medical-dashboard/',
        'nurse': '/hms/triage/',
        'midwife': '/hms/dashboard/midwife/',  # Midwives have their own dashboard
        'pharmacist': '/hms/pharmacy/',
        'procurement_officer': '/hms/procurement/',
        'store_manager': '/hms/inventory-stores/dashboard/',
        'inventory_stores_manager': '/hms/inventory-stores/dashboard/',
        'lab_technician': '/hms/laboratory/',
        'radiologist': '/hms/dashboard/radiology/',
        'receptionist': '/hms/reception-dashboard/',
        'cashier': '/hms/cashier/dashboard/',
        'it': '/hms/admin/it-operations/',
        'it_staff': '/hms/admin/it-operations/',
        'marketing': '/hms/marketing/',
    }
    
    return role_urls.get(role, '/hms/staff/dashboard/')


def get_user_features(user):
    """
    Get list of features/dashboards accessible to user
    """
    role = get_user_role(user)
    
    if role not in ROLE_FEATURES:
        return []
    
    role_config = ROLE_FEATURES[role]
    
    if role_config.get('features') == 'all':
        # Admin gets everything
        return list(ROLE_FEATURES.keys())
    
    return role_config.get('dashboards', [])


def user_has_role_access(user, required_role):
    """
    Check if user has access to a specific role's features
    """
    user_role = get_user_role(user)
    
    # Admins have access to everything
    if user_role == 'admin':
        return True
    
    # Check if user's role matches required role
    return user_role == required_role


def is_pharmacy_user(user):
    """
    True if user is pharmacy staff (pharmacist or pharmacy technician).
    Used to block pharmacy from invoice and payment access.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return False
    if get_user_role(user) == 'pharmacist':
        return True
    try:
        from .models import Staff
        staff = Staff.objects.filter(user=user, is_deleted=False).first()
        if staff and getattr(staff, 'profession', None) in ('pharmacist', 'pharmacy_technician'):
            return True
    except Exception:
        pass
    return user.groups.filter(name__in=['Pharmacy', 'Pharmacist']).exists()


def get_role_navigation(user):
    """
    Get navigation items for a user based on their role
    Returns list of dicts with 'title', 'url', 'icon'
    """
    role = get_user_role(user)
    
    navigation = {
        'admin': [
            {'title': 'Dashboard', 'url': '/hms/admin-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Chat Channel', 'url': '/hms/admin/chat/', 'icon': 'chat-dots'},
            {'title': 'IT Operations', 'url': '/hms/admin/it-operations/', 'icon': 'motherboard'},
            {'title': 'Marketing & BD', 'url': '/hms/marketing/', 'icon': 'megaphone'},
            {'title': 'Procurement Approvals', 'url': '/hms/procurement/admin/pending/', 'icon': 'clipboard-check'},
            {'title': 'Pharmacy Requests', 'url': '/hms/procurement/approval/dashboard/', 'icon': 'capsule-pill'},
            {'title': 'Bulk SMS', 'url': '/hms/sms/bulk/dashboard/', 'icon': 'chat-dots'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Admitted Patients', 'url': '/hms/admitted-patients/', 'url_name': 'admitted_patients_list', 'icon': 'hospital'},
            {'title': 'Encounters', 'url': '/hms/encounters/', 'icon': 'card-list'},
            {'title': 'Inventory Management', 'url': '/hms/inventory/dashboard/', 'icon': 'box-seam'},
            {'title': 'Accounting', 'url': '/hms/accountant/comprehensive-dashboard/', 'icon': 'calculator'},
            {'title': 'HR Management', 'url': '/hms/hr/worldclass/', 'icon': 'people'},
            {'title': 'Medical Chits', 'url': '/hms/hr/medical-chits/', 'icon': 'heart-pulse'},
            {'title': 'Pharmacy', 'url': '/hms/pharmacy/', 'icon': 'capsule'},
            {'title': 'Laboratory', 'url': '/hms/laboratory/', 'icon': 'clipboard2-pulse'},
            {'title': 'Pre-employment / Pre-admission', 'url': '/hms/screening/', 'url_name': 'screening_dashboard', 'icon': 'clipboard2-check'},
            {'title': 'Reports', 'url': '/hms/reports/', 'icon': 'graph-up'},
            {'title': 'Settings', 'url': '/hms/settings/', 'icon': 'gear'},
        ],
        'accountant': [
            {'title': 'Comprehensive Dashboard', 'url': '/hms/accountant/comprehensive-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Cashier — Patients & Create Bill', 'url': '/hms/cashier/central/patients/', 'icon': 'people', 'url_name': 'cashier_patient_list'},
            {'title': 'Create Billing', 'url': '/hms/cashier/central/create-billing/', 'icon': 'file-earmark-plus', 'url_name': 'cashier_create_billing'},
            {'title': 'Claims Bills', 'url': '/hms/accountant/billing/claims-hub/', 'icon': 'file-earmark-text', 'path_prefix': '/hms/accountant/billing/'},
            {'title': 'Revenue / Payment Analysis', 'url': '/hms/accountant/billing/revenue-payment-analysis/', 'icon': 'graph-up-arrow', 'path_prefix': '/hms/accountant/billing/'},
            {'title': 'Waiver audit', 'url': '/hms/accountant/billing/waiver-audit/', 'icon': 'journal-minus', 'path_prefix': '/hms/accountant/billing/'},
            {'title': 'Cashbook', 'url': '/hms/accountant/cashbook/', 'icon': 'journal-text'},
            {'title': 'Bank Reconciliation', 'url': '/hms/accountant/bank-reconciliation/', 'icon': 'bank'},
            {'title': 'Insurance Receivable', 'url': '/hms/accountant/insurance-receivable/', 'icon': 'file-earmark-medical'},
            {'title': 'Procurement Purchases', 'url': '/hms/accountant/procurement-purchases/', 'icon': 'cart'},
            {'title': 'Payroll', 'url': '/hms/accountant/payroll/', 'icon': 'people'},
            {'title': 'Doctor Commissions', 'url': '/hms/accountant/doctor-commissions/', 'icon': 'person-badge'},
            {'title': 'Profit & Loss', 'url': '/hms/accountant/profit-loss/', 'icon': 'graph-up'},
            {'title': 'Detailed Financial Report', 'url': '/hms/accountant/detailed-financial-report/', 'icon': 'file-earmark-spreadsheet'},
            {'title': 'Registration Fees', 'url': '/hms/accountant/registration-fees/', 'icon': 'cash-coin'},
            {'title': 'Cash Sales', 'url': '/hms/accountant/cash-sales/', 'icon': 'currency-dollar'},
            {'title': 'Corporate Accounts', 'url': '/hms/accountant/corporate-accounts/', 'icon': 'building'},
            {'title': 'Withholding Receivable', 'url': '/hms/accountant/withholding-receivable/', 'icon': 'file-earmark-lock'},
            {'title': 'Deposits', 'url': '/hms/accountant/deposits/', 'icon': 'arrow-down-circle'},
            {'title': 'Revaluations', 'url': '/hms/accountant/revaluations/', 'icon': 'arrow-repeat'},
            {'title': 'Chart of Accounts', 'url': '/hms/accountant/chart-of-accounts/', 'icon': 'list-ul'},
            {'title': 'Payment Vouchers', 'url': '/hms/accounting/payment-vouchers/', 'icon': 'receipt-cutoff'},
            {'title': 'Cheques', 'url': '/hms/accounting/cheques/', 'icon': 'file-earmark-check'},
            {'title': 'Journal Entries', 'url': '/hms/accounting/general-ledger/', 'icon': 'journal'},
            {'title': 'Financial Reports', 'url': '/hms/accounting/reports/', 'icon': 'graph-up'},
            {'title': 'Invoices', 'url': '/hms/invoices/', 'icon': 'receipt', 'url_name': 'invoice_list'},
            {'title': 'Payments', 'url': '/hms/cashier/receipts/', 'icon': 'credit-card', 'url_name': 'cashier_receipts_list'},
        ],
        'senior_account_officer': [
            {'title': 'Senior Dashboard', 'url': '/hms/senior-account-officer/dashboard/', 'icon': 'speedometer2'},
            {'title': 'Account Staff', 'url': '/hms/senior-account-officer/account-staff/', 'icon': 'people'},
            {'title': 'Claims Bills', 'url': '/hms/accountant/billing/claims-hub/', 'icon': 'file-earmark-text', 'path_prefix': '/hms/accountant/billing/'},
            {'title': 'Revenue / Payment Analysis', 'url': '/hms/accountant/billing/revenue-payment-analysis/', 'icon': 'graph-up-arrow', 'path_prefix': '/hms/accountant/billing/'},
            {'title': 'Comprehensive Dashboard', 'url': '/hms/accountant/comprehensive-dashboard/', 'icon': 'calculator'},
            {'title': 'Cashbook', 'url': '/hms/accountant/cashbook/', 'icon': 'journal-text'},
            {'title': 'Bank Reconciliation', 'url': '/hms/accountant/bank-reconciliation/', 'icon': 'bank'},
            {'title': 'Insurance Receivable', 'url': '/hms/accountant/insurance-receivable/', 'icon': 'file-earmark-medical'},
            {'title': 'Procurement Purchases', 'url': '/hms/accountant/procurement-purchases/', 'icon': 'cart'},
            {'title': 'Payroll', 'url': '/hms/accountant/payroll/', 'icon': 'people'},
            {'title': 'Doctor Commissions', 'url': '/hms/accountant/doctor-commissions/', 'icon': 'person-badge'},
            {'title': 'Profit & Loss', 'url': '/hms/accountant/profit-loss/', 'icon': 'graph-up'},
            {'title': 'Chart of Accounts', 'url': '/hms/accountant/chart-of-accounts/', 'icon': 'list-ul'},
            {'title': 'Payment Vouchers', 'url': '/hms/accounting/payment-vouchers/', 'icon': 'receipt-cutoff'},
            {'title': 'Journal Entries', 'url': '/hms/accounting/general-ledger/', 'icon': 'journal'},
            {'title': 'Petty Cash', 'url': '/hms/accounting/petty-cash/', 'icon': 'wallet'},
            {'title': 'Financial Reports', 'url': '/hms/accounting/reports/', 'icon': 'graph-up'},
        ],
        'hr_manager': [
            {'title': 'HR Dashboard', 'url': '/hms/hr/worldclass/', 'icon': 'speedometer2'},
            {'title': 'Staff Management', 'url': '/hms/staff/', 'icon': 'people'},
            {'title': 'Activity Calendar', 'url': '/hms/hr/activities/', 'icon': 'calendar-event'},
            {'title': 'Leave Management', 'url': '/hms/hr/leave-calendar/', 'icon': 'calendar3'},
            {'title': 'Medical Chits', 'url': '/hms/hr/medical-chits/', 'icon': 'heart-pulse'},
            {'title': 'Attendance', 'url': '/hms/hr/attendance-calendar/', 'icon': 'calendar-check'},
            {'title': 'Login Attendance', 'url': '/hms/hr/attendance/login-sessions/', 'icon': 'fingerprint'},
            {'title': 'Live Sessions', 'url': '/hms/hr/live-sessions/', 'icon': 'broadcast-pin'},
            {'title': 'Payroll', 'url': '/hms/payroll/', 'icon': 'cash'},
            {'title': 'Performance', 'url': '/hms/performance-reviews/', 'icon': 'star'},
            {'title': 'Recruitment', 'url': '/hms/hr/recruitment/', 'icon': 'person-plus'},
            {'title': 'Recognition', 'url': '/hms/hr/recognition-board/', 'icon': 'award'},
            {'title': 'HR Reports', 'url': '/hms/hr/reports/', 'icon': 'graph-up'},
        ],
        'hr': [
            {'title': 'Service Desk', 'url': '/hms/hr/service-desk/', 'icon': 'headset'},
            {'title': 'Staff Directory', 'url': '/hms/staff/', 'icon': 'people'},
            {'title': 'Leave Board', 'url': '/hms/hr/leave-calendar/', 'icon': 'calendar3'},
            {'title': 'Attendance', 'url': '/hms/hr/attendance-calendar/', 'icon': 'calendar-check'},
            {'title': 'Payroll Center', 'url': '/hms/payroll/', 'icon': 'cash'},
            {'title': 'Contracts', 'url': '/hms/contracts/', 'icon': 'file-earmark-text'},
        ],
        'doctor': [
            {'title': 'Medical Dashboard', 'url': '/hms/medical-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Patient Flowboard', 'url': '/hms/doctor/flowboard/', 'url_name': 'doctor_patient_flowboard', 'icon': 'diagram-3'},
            {'title': 'My Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Admitted Patients', 'url': '/hms/admitted-patients/', 'url_name': 'admitted_patients_list', 'icon': 'hospital'},
            {'title': 'Consultations', 'url': '/hms/my-consultations/', 'icon': 'clipboard-pulse'},
            {'title': 'Triage', 'url': '/hms/triage/dashboard/', 'icon': 'heartbeat'},
            {'title': 'Medical Records', 'url': '/hms/medical-records/', 'icon': 'file-medical'},
            {'title': 'Prescriptions', 'url': '/hms/pharmacy/prescription/', 'icon': 'prescription2'},
            {'title': 'Lab Orders', 'url': '/hms/orders/', 'icon': 'clipboard-check'},
            {'title': 'Pre-employment / Pre-admission', 'url': '/hms/screening/', 'url_name': 'screening_dashboard', 'icon': 'clipboard2-check'},
            {'title': 'Drug Classification Guide', 'url': '/hms/drug-classification-guide/', 'icon': 'book'},
        ],
        'nurse': [
            {'title': 'Nursing Dashboard', 'url': '/hms/triage/', 'icon': 'speedometer2'},
            {'title': 'Nurse Flowboard', 'url': '/hms/nurse/flowboard/', 'url_name': 'nurse_patient_flowboard', 'icon': 'people'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Admitted Patients', 'url': '/hms/admitted-patients/', 'url_name': 'admitted_patients_list', 'icon': 'hospital'},
            {'title': 'Bed Manager', 'url': '/hms/beds/management/', 'url_name': 'bed_management_worldclass', 'icon': 'columns-gap'},
            {'title': 'Admissions', 'url': '/hms/admissions/', 'url_name': 'admission_list', 'icon': 'hospital'},
            {'title': 'Medical Records', 'url': '/hms/medical-records/', 'icon': 'file-medical'},
            {'title': 'Triage', 'url': '/hms/triage/', 'icon': 'heart-pulse'},
            {'title': 'Vital Signs', 'url': '/hms/vitals/', 'icon': 'thermometer-half'},
            {'title': 'Orders', 'url': '/hms/orders/', 'icon': 'clipboard-check'},
            {'title': 'Pre-employment / Pre-admission', 'url': '/hms/screening/', 'url_name': 'screening_dashboard', 'icon': 'clipboard2-check'},
        ],
        'midwife': [
            {'title': 'Midwife Dashboard', 'url': '/hms/dashboard/midwife/', 'icon': 'speedometer2'},
            {'title': 'Nursing Dashboard', 'url': '/hms/triage/', 'icon': 'speedometer2'},
            {'title': 'Nurse Flowboard', 'url': '/hms/nurse/flowboard/', 'url_name': 'nurse_patient_flowboard', 'icon': 'people'},
            {'title': 'Maternity Records', 'url': '/hms/midwife/records/', 'icon': 'file-medical'},
            {'title': 'Medical Records', 'url': '/hms/medical-records/', 'icon': 'file-earmark-medical'},
            {'title': 'Antenatal Care', 'url': '/hms/midwife/antenatal/', 'icon': 'heart-pulse'},
            {'title': 'Bill Antenatal Items', 'url': '/hms/midwife/antenatal-items/', 'icon': 'capsule'},
            {'title': 'Postnatal Care', 'url': '/hms/midwife/postnatal/', 'icon': 'heart-fill'},
            {'title': 'Delivery Records', 'url': '/hms/midwife/delivery/', 'icon': 'hospital'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Admitted Patients', 'url': '/hms/admitted-patients/', 'url_name': 'admitted_patients_list', 'icon': 'hospital'},
            {'title': 'Bed Manager', 'url': '/hms/beds/management/', 'url_name': 'bed_management_worldclass', 'icon': 'columns-gap'},
            {'title': 'Admissions', 'url': '/hms/admissions/', 'url_name': 'admission_list', 'icon': 'hospital'},
            {'title': 'Triage', 'url': '/hms/triage/', 'icon': 'heart-pulse'},
            {'title': 'Vital Signs', 'url': '/hms/vitals/', 'icon': 'thermometer-half'},
            {'title': 'Orders', 'url': '/hms/orders/', 'icon': 'clipboard-check'},
            {'title': 'Pre-employment / Pre-admission', 'url': '/hms/screening/', 'url_name': 'screening_dashboard', 'icon': 'clipboard2-check'},
        ],
        'pharmacist': [
            {'title': 'Pharmacy Flowboard', 'url': '/hms/pharmacy/flowboard/', 'url_name': 'pharmacy_flowboard', 'icon': 'diagram-3'},
            {'title': 'Dispensing Queue', 'url': '/hms/pharmacy/pending-dispensing/', 'icon': 'bag-check'},
            {'title': 'My Sales (Verify)', 'url': '/hms/pharmacy/my-sales/', 'url_name': 'pharmacy_my_sales', 'icon': 'receipt-cutoff'},
            {'title': 'Payment Verification', 'url': '/hms/payment/pharmacy/dispensing/', 'icon': 'lock'},
            {'title': 'Drug Classification Guide', 'url': '/hms/drug-classification-guide/', 'icon': 'book'},
        ],
        'procurement_officer': [
            {'title': 'Procurement Dashboard', 'url': '/hms/procurement/', 'icon': 'speedometer2'},
            {'title': 'Pharmacy', 'url': '/hms/pharmacy/', 'icon': 'capsule'},
            {'title': 'Procurement Requests', 'url': '/hms/procurement/requests/', 'icon': 'file-earmark-text'},
            {'title': 'Create Request', 'url': '/hms/procurement/requests/new/', 'icon': 'plus-circle'},
            {'title': 'Pending Approvals', 'url': '/hms/procurement/approval/dashboard/', 'icon': 'clipboard-check'},
            {'title': 'Workflow Dashboard', 'url': '/hms/procurement/workflow/', 'icon': 'diagram-3'},
            {'title': 'Stores', 'url': '/hms/procurement/stores/', 'icon': 'shop'},
            {'title': 'Inventory', 'url': '/hms/procurement/inventory/', 'icon': 'boxes'},
            {'title': 'Low Stock Alerts', 'url': '/hms/procurement/reports/low-stock/', 'icon': 'exclamation-triangle'},
            {'title': 'Store Transfers', 'url': '/hms/procurement/transfers/', 'icon': 'arrow-left-right'},
            {'title': 'Suppliers', 'url': '/hms/procurement/suppliers/', 'icon': 'truck'},
            {'title': 'Inventory Analytics', 'url': '/hms/inventory/analytics/', 'icon': 'graph-up'},
            {'title': 'Find Duplicates', 'url': '/hms/procurement/inventory/duplicates/', 'icon': 'exclamation-triangle'},
        ],
        'store_manager': [
            {'title': 'Procurement Dashboard', 'url': '/hms/procurement/', 'icon': 'speedometer2'},
            {'title': 'Pharmacy', 'url': '/hms/pharmacy/', 'icon': 'capsule'},
            {'title': 'Inventory Dashboard', 'url': '/hms/inventory-stores/dashboard/', 'icon': 'box-seam'},
            {'title': 'All Items', 'url': '/hms/inventory/items/', 'icon': 'box-seam'},
            {'title': 'Add Item', 'url': '/hms/procurement/inventory-items/new/', 'icon': 'plus-circle'},
            {'title': 'Procurement Requests', 'url': '/hms/procurement/requests/', 'icon': 'file-earmark-text'},
            {'title': 'Create Request', 'url': '/hms/procurement/requests/new/', 'icon': 'plus-circle'},
            {'title': 'Store Transfers', 'url': '/hms/procurement/transfers/', 'icon': 'arrow-left-right'},
            {'title': 'Create Transfer', 'url': '/hms/procurement/transfers/create-modern/', 'icon': 'arrow-left-right'},
            {'title': 'Receiving Dashboard', 'url': '/hms/procurement/receiving/dashboard/', 'icon': 'truck'},
            {'title': 'Stores', 'url': '/hms/procurement/stores/', 'icon': 'shop'},
            {'title': 'Stock Alerts', 'url': '/hms/inventory/alerts/', 'icon': 'bell'},
            {'title': 'Low Stock Report', 'url': '/hms/procurement/reports/low-stock/', 'icon': 'exclamation-triangle'},
            {'title': 'Suppliers', 'url': '/hms/procurement/suppliers/', 'icon': 'truck'},
            {'title': 'Analytics', 'url': '/hms/inventory/analytics/', 'icon': 'graph-up'},
            {'title': 'Find Duplicates', 'url': '/hms/procurement/inventory/duplicates/', 'icon': 'exclamation-triangle'},
        ],
        'inventory_stores_manager': [
            {'title': 'Procurement Dashboard', 'url': '/hms/procurement/', 'icon': 'speedometer2'},
            {'title': 'Pharmacy', 'url': '/hms/pharmacy/', 'icon': 'capsule'},
            {'title': 'Inventory Dashboard', 'url': '/hms/inventory-stores/dashboard/', 'icon': 'box-seam'},
            {'title': 'All Stores', 'url': '/hms/procurement/stores/', 'icon': 'shop'},
            {'title': 'Inventory Items', 'url': '/hms/inventory/items/', 'icon': 'box-seam'},
            {'title': 'Add Item', 'url': '/hms/procurement/inventory-items/new/', 'icon': 'plus-circle'},
            {'title': 'Procurement Requests', 'url': '/hms/procurement/requests/', 'icon': 'file-earmark-text'},
            {'title': 'Create Request', 'url': '/hms/procurement/requests/new/', 'icon': 'plus-circle'},
            {'title': 'Store Transfers', 'url': '/hms/procurement/transfers/', 'icon': 'arrow-left-right'},
            {'title': 'Create Transfer', 'url': '/hms/procurement/transfers/create-modern/', 'icon': 'arrow-left-right'},
            {'title': 'Receiving Dashboard', 'url': '/hms/procurement/receiving/dashboard/', 'icon': 'truck'},
            {'title': 'Stock Alerts', 'url': '/hms/inventory/alerts/', 'icon': 'bell'},
            {'title': 'Low Stock Report', 'url': '/hms/procurement/reports/low-stock/', 'icon': 'exclamation-triangle'},
            {'title': 'Suppliers', 'url': '/hms/procurement/suppliers/', 'icon': 'truck'},
            {'title': 'Analytics', 'url': '/hms/inventory/analytics/', 'icon': 'graph-up'},
            {'title': 'Find Duplicates', 'url': '/hms/procurement/inventory/duplicates/', 'icon': 'exclamation-triangle'},
        ],
        'lab_technician': [
            {'title': 'Dashboard', 'url': '/hms/laboratory/', 'url_name': 'laboratory_dashboard', 'icon': 'speedometer2'},
            {'title': 'Lab team summary', 'url': '/hms/dashboard/lab/', 'url_name': 'lab_technician_dashboard', 'icon': 'people'},
            {'title': 'Patient Flowboard', 'url': '/hms/flow/dashboard/', 'url_name': 'flow_dashboard', 'icon': 'diagram-3'},
            {'title': 'Lab Results', 'url': '/hms/lab-results/', 'icon': 'clipboard2-pulse'},
            {'title': 'Lab Tests catalog', 'url': '/hms/lab-tests/', 'icon': 'flask'},
        ],
        'radiologist': [
            {'title': 'Radiology Dashboard', 'url': '/hms/dashboard/radiology/', 'url_name': 'radiologist_dashboard', 'icon': 'camera-reels-fill'},
            {'title': 'Imaging Dashboard', 'url': '/hms/imaging/', 'url_name': 'imaging_dashboard', 'icon': 'camera'},
            {'title': 'Patient Flowboard', 'url': '/hms/flow/dashboard/', 'url_name': 'flow_dashboard', 'icon': 'diagram-3'},
            {'title': 'Pending Orders', 'url': '/hms/imaging/pending/', 'url_name': 'radiologist_pending_orders', 'icon': 'clock-history'},
            {'title': 'My Studies', 'url': '/hms/imaging/my-studies/', 'url_name': 'radiologist_my_studies', 'icon': 'person-badge'},
            {'title': 'Report Queue', 'url': '/hms/imaging/report-queue/', 'url_name': 'radiologist_report_queue', 'icon': 'file-earmark-text'},
            {'title': 'Completed Studies', 'url': '/hms/imaging/completed/', 'url_name': 'radiologist_completed_studies', 'icon': 'check-circle'},
            {'title': 'Medical Records', 'url': '/hms/medical-records/', 'url_name': 'medical_records_list', 'icon': 'file-medical'},
            {'title': 'Patients', 'url': '/hms/patients/', 'url_name': 'patient_list', 'icon': 'person'},
            {'title': 'Chat', 'url': '/hms/chat/', 'url_name': 'chat_dashboard', 'icon': 'chat-dots'},
        ],
        'receptionist': [
            {'title': 'Reception Dashboard', 'url': '/hms/reception-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Patient Flowboard', 'url': '/hms/flow/dashboard/', 'url_name': 'flow_dashboard', 'icon': 'diagram-3'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Appointments', 'url': '/hms/appointments/', 'icon': 'calendar-event'},
            {'title': 'Registration', 'url': '/hms/patient-registration/', 'icon': 'person-plus'},
        ],
        'cashier': [
            {'title': 'Cashier Dashboard', 'url': '/hms/cashier/dashboard/', 'icon': 'speedometer2'},
            {'title': 'Patients — Create Bill', 'url': '/hms/cashier/central/patients/', 'icon': 'people', 'url_name': 'cashier_patient_list'},
            {'title': 'Create Billing', 'url': '/hms/cashier/central/create-billing/', 'icon': 'file-earmark-plus', 'url_name': 'cashier_create_billing'},
            {'title': 'Payments', 'url': '/hms/cashier/receipts/', 'icon': 'credit-card', 'url_name': 'cashier_receipts_list'},
            {'title': 'Invoices', 'url': '/hms/cashier/invoices/', 'icon': 'receipt', 'url_name': 'cashier_invoices'},
            {'title': 'My Session', 'url': '/hms/cashier/session/', 'icon': 'cash-stack'},
        ],
        'it': [
            {'title': 'IT Operations', 'url': '/hms/admin/it-operations/', 'icon': 'motherboard'},
            {'title': 'Chat Channel', 'url': '/hms/admin/chat/', 'icon': 'chat-dots'},
            {'title': 'System Health', 'url': '/hms/system-health/', 'icon': 'heart-pulse'},
            {'title': 'Backups', 'url': '/hms/admin/backups/', 'icon': 'database'},
            {'title': 'Security Alerts', 'url': '/hms/security-alerts/', 'icon': 'shield-exclamation'},
            {'title': 'Audit Logs', 'url': '/hms/audit-logs/', 'icon': 'file-earmark-text'},
            {'title': 'User Sessions', 'url': '/hms/admin/sessions/', 'icon': 'people'},
        ],
        'it_staff': [
            {'title': 'IT Operations', 'url': '/hms/admin/it-operations/', 'icon': 'motherboard'},
            {'title': 'Chat Channel', 'url': '/hms/admin/chat/', 'icon': 'chat-dots'},
            {'title': 'System Health', 'url': '/hms/system-health/', 'icon': 'heart-pulse'},
            {'title': 'Backups', 'url': '/hms/admin/backups/', 'icon': 'database'},
            {'title': 'Security Alerts', 'url': '/hms/security-alerts/', 'icon': 'shield-exclamation'},
            {'title': 'Audit Logs', 'url': '/hms/audit-logs/', 'icon': 'file-earmark-text'},
            {'title': 'User Sessions', 'url': '/hms/admin/sessions/', 'icon': 'people'},
        ],
        'marketing': [
            {'title': 'Marketing Dashboard', 'url': '/hms/marketing/', 'icon': 'speedometer2'},
            {'title': 'Objectives', 'url': '/hms/marketing/objectives/', 'icon': 'bullseye'},
            {'title': 'Tasks', 'url': '/hms/marketing/tasks/', 'icon': 'list-check'},
            {'title': 'Campaigns', 'url': '/hms/marketing/campaigns/', 'icon': 'megaphone'},
            {'title': 'Partnerships', 'url': '/hms/marketing/partnerships/', 'icon': 'handshake'},
            {'title': 'Metrics', 'url': '/hms/marketing/api/metrics/', 'icon': 'graph-up'},
        ],
    }
    
    # Get base navigation for role
    nav_items = navigation.get(role, [
        {'title': 'My Dashboard', 'url': '/hms/staff/dashboard/', 'icon': 'speedometer2'},
        {'title': 'Staff Portal', 'url': '/hms/staff/portal/', 'icon': 'person-badge'},
    ])
    
    # Add Medical Director links if user is Medical Director
    if role == 'doctor' and user:
        try:
            from .models import Staff
            staff = Staff.objects.filter(user=user, is_deleted=False).first()
            if staff:
                specialization = (staff.specialization or '').lower()
                is_medical_director = (
                    'medical director' in specialization or
                    (user.is_staff and staff.profession == 'doctor' and 'director' in specialization)
                )
                if is_medical_director or user.is_superuser:
                    # Add Medical Director authorization section
                    nav_items.extend([
                        {'title': 'Drug Returns', 'url': '/hms/drug-returns/', 'icon': 'arrow-return-left'},
                        {'title': 'Deletion History', 'url': '/hms/deletion-history/', 'icon': 'trash'},
                        {'title': 'Accountability', 'url': '/hms/drug-accountability/dashboard/', 'icon': 'shield-check'},
                        {'title': 'Hospital Settings', 'url': '/hms/settings/', 'icon': 'gear'},
                    ])
        except Exception:
            pass
    
    return nav_items


def create_default_groups():
    """
    Create default role groups with appropriate permissions
    Called during setup
    """
    from django.apps import apps
    
    # Create groups
    for role_slug, role_config in ROLE_FEATURES.items():
        if role_slug == 'admin':
            continue  # Admins use superuser, not groups
        
        group, created = Group.objects.get_or_create(name=role_config['name'])
        
        if role_config.get('features') != 'all':
            # Ensure permissions exist on the group (idempotent; safe to rerun)
            for perm_codename in role_config.get('features', []):
                try:
                    permission = Permission.objects.get(
                        codename=perm_codename,
                        content_type__app_label='hospital'
                    )
                    group.permissions.add(permission)
                except Permission.DoesNotExist:
                    print(f"Permission {perm_codename} not found")
    
    return True


def assign_user_to_role(user, role_slug):
    """
    Assign a user to a specific role group
    """
    if role_slug not in ROLE_FEATURES:
        return False
    
    role_config = ROLE_FEATURES[role_slug]
    
    # Clear existing groups
    user.groups.clear()
    
    if role_slug == 'admin':
        user.is_staff = True
        user.is_superuser = True
        user.save()
    else:
        # Add to appropriate group
        group, created = Group.objects.get_or_create(name=role_config['name'])
        user.groups.add(group)
        user.is_staff = True
        user.is_superuser = False
        user.save(update_fields=['is_staff', 'is_superuser'])
    
    return True


def get_role_display_info(user):
    """
    Get role display information for UI
    """
    role = get_user_role(user)
    role_config = ROLE_FEATURES.get(role, {
        'name': 'Staff',
        'color': '#6b7280',
        'icon': 'person'
    })
    
    return {
        'slug': role,
        'name': role_config.get('name', 'Staff'),
        'color': role_config.get('color', '#6b7280'),
        'icon': role_config.get('icon', 'person'),
        'dashboards': role_config.get('dashboards', []),
    }


# ----------------------------------------------------------------------
# Access helpers for sensitive modules (e.g., cashier)
# ----------------------------------------------------------------------
CASHIER_ACCESS_ROLES = {'admin', 'accountant', 'cashier'}

# Roles that can add manual charges (reception adds charges for cashier to collect)
MANUAL_CHARGE_ACCESS_ROLES = {'admin', 'accountant', 'cashier', 'receptionist'}


def user_has_cashier_access(user):
    """
    Only Administrators and Accounting can access cashier features.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    user_role = get_user_role(user)
    return user_role in CASHIER_ACCESS_ROLES


def user_can_add_manual_charges(user):
    """Reception and cashier can add charges (reception adds for cashier to collect)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    user_role = get_user_role(user)
    return user_role in MANUAL_CHARGE_ACCESS_ROLES


# Who may remove an invoice from the total bill or waive Prescribe Sales (must match
# cashier_patient_total_bill.html). Uses **group names**, not get_user_role(), so users
# with multiple groups (e.g. Procurement + Accountant) are not denied when they have Accountant.
INVOICE_FROM_BILL_REMOVER_GROUPS = frozenset({'Accountant', 'Admin', 'Administrator'})


def user_can_remove_invoice_from_bill(user):
    """True if user may POST remove-from-bill / waive prescribe (same as total-bill UI)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    groups = set(user.groups.values_list('name', flat=True))
    return bool(groups & INVOICE_FROM_BILL_REMOVER_GROUPS)


# Waiver of invoice lines / prescribe sales: Admin / Administrator group or resolved admin role only.
# get_user_role() checks "Accountant" before "Admin"/"Administrator", so users in both groups
# resolve as accountant — we must also check Django groups (same idea as INVOICE_FROM_BILL_REMOVER_GROUPS).
WAIVER_ACCESS_ROLES = {'admin'}
WAIVER_ADMIN_GROUP_SLUGS = frozenset({'admin', 'administrator'})


def user_has_waiver_admin_group(user):
    """True if user is in Admin or Administrator Django group (normalized name)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    for name in user.groups.values_list('name', flat=True):
        g = name.lower().replace(' ', '_').replace('&', '_')
        if g in WAIVER_ADMIN_GROUP_SLUGS:
            return True
    return False


def user_can_waive(user):
    """Only administrators can waive invoice lines and prescribe-sale charges. Accountants cannot waive."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    if user_has_waiver_admin_group(user):
        return True
    user_role = get_user_role(user)
    return user_role in WAIVER_ACCESS_ROLES


def user_can_edit_invoice_line_amounts(user):
    """
    Who may set or override invoice monetary amounts (custom GHS, unit price overrides from Add Services, etc.).
    Cashiers collect payment and must use catalog/system prices; accountants and other roles may enter custom amounts.
    (Line quantity is separate and may still be adjusted where the workflow allows.)
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) != 'cashier'


# Account and finance roles: can view price but only admin can change it
ACCOUNT_FINANCE_ROLES = {'accountant', 'senior_account_officer', 'account_personnel', 'account_officer'}


def is_account_or_finance(user):
    """True if user is in account/finance role (can view prices, not edit)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    user_role = get_user_role(user)
    return user_role in ACCOUNT_FINANCE_ROLES


# ----------------------------------------------------------------------
# Staff Query Helpers - Centralized duplicate prevention
# ----------------------------------------------------------------------
def get_deduplicated_staff_queryset(base_filter=None):
    """
    Get a staff queryset with duplicate prevention.
    Returns only the most recent staff record per user.
    
    Args:
        base_filter: Optional Q object or dict to add additional filters
    
    Returns:
        QuerySet of Staff objects (one per user, most recent)
    """
    from django.db.models import OuterRef, Subquery
    from django.db import connection
    from .models import Staff
    
    # Build base queryset
    qs = Staff.objects.filter(is_deleted=False)
    
    if base_filter:
        if isinstance(base_filter, dict):
            qs = qs.filter(**base_filter)
        else:
            qs = qs.filter(base_filter)
    
    # Use PostgreSQL DISTINCT ON for reliable deduplication
    if connection.vendor == 'postgresql':
        # Get IDs of most recent staff per user using raw SQL
        # Build WHERE clause dynamically based on filters
        sql = """
            SELECT DISTINCT ON (user_id) id
            FROM hospital_staff
            WHERE is_deleted = false
        """
        params = []
        
        # Add additional WHERE conditions if base_filter has them
        if base_filter and isinstance(base_filter, dict):
            if 'is_active' in base_filter:
                sql += " AND is_active = %s"
                params.append(base_filter['is_active'])
        
        sql += " ORDER BY user_id, created DESC"
        
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            staff_ids = [row[0] for row in cursor.fetchall()]
        
        # Return queryset filtered by the IDs, with select_related for performance
        result = Staff.objects.filter(
            id__in=staff_ids,
            is_deleted=False
        ).select_related('user', 'department')
        
        # Apply any additional filters that weren't in the SQL
        if base_filter and isinstance(base_filter, dict):
            # is_active was already handled in SQL, but apply any other filters
            other_filters = {k: v for k, v in base_filter.items() if k != 'is_active'}
            if other_filters:
                result = result.filter(**other_filters)
        
        return result
    else:
        # Fallback for other databases
        latest_staff = Staff.objects.filter(
            is_deleted=False,
            user=OuterRef('user')
        )
        
        if base_filter and isinstance(base_filter, dict):
            if 'is_active' in base_filter:
                latest_staff = latest_staff.filter(is_active=base_filter['is_active'])
        
        latest_staff = latest_staff.order_by('-created')[:1]
        
        latest_staff_ids = qs.annotate(
            latest_id=Subquery(latest_staff.values('id'))
        ).values_list('latest_id', flat=True).distinct()
        
        return Staff.objects.filter(
            id__in=latest_staff_ids,
            is_deleted=False
        ).select_related('user', 'department')





