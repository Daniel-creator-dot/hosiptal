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
    'pharmacist': {
        'name': 'Pharmacist',
        'color': '#f59e0b',
        'icon': 'capsule-pill',
        'dashboards': [
            'pharmacy',
            'prescriptions',
            'inventory_drugs',
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
    'store_manager': {
        'name': 'Store Manager',
        'color': '#8b5cf6',
        'icon': 'box-seam',
        'dashboards': [
            'inventory',
            'stores',
            'transfers',
            'requisitions',
        ],
        'features': [
            'view_store',
            'view_inventoryitem',
            'add_inventoryitem',
            'change_inventoryitem',
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
}


def get_user_role(user):
    """
    Detect user's primary role based on groups and staff profession
    Returns role slug (e.g., 'accountant', 'hr_manager', etc.)
    """
    if user.is_superuser:
        return 'admin'
    
    # Check Django groups first
    user_groups = user.groups.values_list('name', flat=True)
    
    for group_name in user_groups:
        group_lower = group_name.lower().replace(' ', '_')
        if group_lower in ROLE_FEATURES:
            return group_lower
    
    # Fall back to staff profession
    try:
        from .models import Staff
        staff = Staff.objects.get(user=user, is_deleted=False)
        
        profession_role_map = {
            'doctor': 'doctor',
            'nurse': 'nurse',
            'pharmacist': 'pharmacist',
            'lab_technician': 'lab_technician',
            'receptionist': 'receptionist',
            'cashier': 'cashier',
            'store_manager': 'store_manager',
        }
        
        return profession_role_map.get(staff.profession, 'staff')
        
    except:
        return 'staff'  # Default fallback


def get_user_dashboard_url(user):
    """
    Get the appropriate dashboard URL for a user based on their role
    """
    role = get_user_role(user)
    
    role_urls = {
        'admin': '/hms/admin-dashboard/',
        'accountant': '/hms/accounting-dashboard/',
        'hr_manager': '/hms/hr/worldclass/',
        'doctor': '/hms/medical-dashboard/',
        'nurse': '/hms/triage/',
        'pharmacist': '/hms/pharmacy-dashboard/',
        'store_manager': '/hms/inventory/dashboard/',
        'lab_technician': '/hms/lab-dashboard/',
        'receptionist': '/hms/reception-dashboard/',
        'cashier': '/hms/cashier/dashboard/',
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


def get_role_navigation(user):
    """
    Get navigation items for user based on their role
    """
    role = get_user_role(user)
    
    navigation = {
        'admin': [
            {'title': 'Dashboard', 'url': '/hms/admin-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Inventory Management', 'url': '/hms/inventory/dashboard/', 'icon': 'box-seam'},
            {'title': 'Procurement Approvals', 'url': '/hms/procurement/admin/pending/', 'icon': 'clipboard-check'},
            {'title': 'Accounting', 'url': '/hms/accounting-dashboard/', 'icon': 'calculator'},
            {'title': 'HR Management', 'url': '/hms/hr/worldclass/', 'icon': 'people'},
            {'title': 'Pharmacy', 'url': '/hms/pharmacy-dashboard/', 'icon': 'capsule'},
            {'title': 'Laboratory', 'url': '/hms/lab-dashboard/', 'icon': 'clipboard2-pulse'},
            {'title': 'Reports', 'url': '/hms/reports/', 'icon': 'graph-up'},
            {'title': 'Settings', 'url': '/hms/settings/', 'icon': 'gear'},
        ],
        'accountant': [
            {'title': 'Accounting Dashboard', 'url': '/hms/accounting-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Invoices', 'url': '/hms/invoices/', 'icon': 'receipt'},
            {'title': 'Payments', 'url': '/hms/payments/', 'icon': 'credit-card'},
            {'title': 'Revenue Streams', 'url': '/hms/accounting/revenue-streams/', 'icon': 'graph-up-arrow'},
            {'title': 'Procurement Approvals', 'url': '/hms/procurement/accounts/pending/', 'icon': 'clipboard-check'},
            {'title': 'Cashier Sessions', 'url': '/hms/cashier-sessions/', 'icon': 'cash-stack'},
            {'title': 'Accounts', 'url': '/hms/accounts/', 'icon': 'wallet2'},
            {'title': 'Financial Reports', 'url': '/hms/accounting/reports/', 'icon': 'graph-up'},
        ],
        'hr_manager': [
            {'title': 'HR Dashboard', 'url': '/hms/hr/worldclass/', 'icon': 'speedometer2'},
            {'title': 'Staff Management', 'url': '/hms/staff/', 'icon': 'people'},
            {'title': 'Activity Calendar', 'url': '/hms/hr/activities/', 'icon': 'calendar-event'},
            {'title': 'Leave Management', 'url': '/hms/hr/leave-calendar/', 'icon': 'calendar3'},
            {'title': 'Attendance', 'url': '/hms/hr/attendance-calendar/', 'icon': 'calendar-check'},
            {'title': 'Payroll', 'url': '/hms/payroll/', 'icon': 'cash'},
            {'title': 'Performance', 'url': '/hms/performance-reviews/', 'icon': 'star'},
            {'title': 'Recruitment', 'url': '/hms/hr/recruitment/', 'icon': 'person-plus'},
            {'title': 'Recognition', 'url': '/hms/hr/recognition-board/', 'icon': 'award'},
            {'title': 'HR Reports', 'url': '/hms/hr/reports/', 'icon': 'graph-up'},
        ],
        'doctor': [
            {'title': 'Medical Dashboard', 'url': '/hms/medical-dashboard/', 'icon': 'speedometer2'},
            {'title': 'My Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Consultations', 'url': '/hms/consultations/', 'icon': 'clipboard-pulse'},
            {'title': 'Triage', 'url': '/hms/triage/', 'icon': 'heartbeat'},
            {'title': 'Medical Records', 'url': '/hms/medical-records/', 'icon': 'file-medical'},
            {'title': 'Prescriptions', 'url': '/hms/prescriptions/', 'icon': 'prescription2'},
            {'title': 'Lab Orders', 'url': '/hms/orders/', 'icon': 'clipboard-check'},
        ],
        'nurse': [
            {'title': 'Nursing Dashboard', 'url': '/hms/triage/', 'icon': 'speedometer2'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Triage', 'url': '/hms/triage/', 'icon': 'heart-pulse'},
            {'title': 'Vital Signs', 'url': '/hms/vitals/', 'icon': 'thermometer-half'},
            {'title': 'Orders', 'url': '/hms/orders/', 'icon': 'clipboard-check'},
        ],
        'pharmacist': [
            {'title': 'Pharmacy Dashboard', 'url': '/hms/pharmacy-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Prescriptions', 'url': '/hms/prescriptions/', 'icon': 'prescription2'},
            {'title': 'Drug Inventory', 'url': '/hms/drugs/', 'icon': 'capsule'},
            {'title': 'Dispensing', 'url': '/hms/dispensing/', 'icon': 'bag-check'},
        ],
        'store_manager': [
            {'title': 'Inventory Dashboard', 'url': '/hms/inventory/dashboard/', 'icon': 'speedometer2'},
            {'title': 'All Items', 'url': '/hms/inventory/items/', 'icon': 'box-seam'},
            {'title': 'Stock Alerts', 'url': '/hms/inventory/alerts/', 'icon': 'bell'},
            {'title': 'Requisitions', 'url': '/hms/inventory/requisitions/', 'icon': 'clipboard-check'},
            {'title': 'Store Transfers', 'url': '/hms/inventory/transfers/', 'icon': 'truck'},
            {'title': 'Analytics', 'url': '/hms/inventory/analytics/', 'icon': 'graph-up'},
        ],
        'lab_technician': [
            {'title': 'Lab Dashboard', 'url': '/hms/lab-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Lab Results', 'url': '/hms/lab-results/', 'icon': 'clipboard2-pulse'},
            {'title': 'Lab Orders', 'url': '/hms/lab-orders/', 'icon': 'clipboard-check'},
            {'title': 'Lab Tests', 'url': '/hms/lab-tests/', 'icon': 'flask'},
        ],
        'receptionist': [
            {'title': 'Reception Dashboard', 'url': '/hms/reception-dashboard/', 'icon': 'speedometer2'},
            {'title': 'Patients', 'url': '/hms/patients/', 'icon': 'person'},
            {'title': 'Appointments', 'url': '/hms/appointments/', 'icon': 'calendar-event'},
            {'title': 'Registration', 'url': '/hms/patient-registration/', 'icon': 'person-plus'},
        ],
        'cashier': [
            {'title': 'Cashier Dashboard', 'url': '/hms/cashier/dashboard/', 'icon': 'speedometer2'},
            {'title': 'Payments', 'url': '/hms/payments/', 'icon': 'credit-card'},
            {'title': 'Invoices', 'url': '/hms/invoices/', 'icon': 'receipt'},
            {'title': 'My Session', 'url': '/hms/cashier/session/', 'icon': 'cash-stack'},
        ],
    }
    
    return navigation.get(role, [
        {'title': 'My Dashboard', 'url': '/hms/staff/dashboard/', 'icon': 'speedometer2'},
    ])


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
        
        if created and role_config.get('features') != 'all':
            # Add permissions to group
            for perm_codename in role_config.get('features', []):
                try:
                    # Get the permission
                    app_label = 'hospital'
                    permission = Permission.objects.get(
                        codename=perm_codename,
                        content_type__app_label=app_label
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
        user.save()
    
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





