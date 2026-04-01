#!/usr/bin/env python
"""
Setup Ebenezer in Finance Department with Full Financial Access
"""
import os
import sys
import django
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from hospital.models import Staff, Department

def setup_ebenezer_finance():
    print("=" * 70)
    print("SETTING UP EBENEZER IN FINANCE DEPARTMENT")
    print("=" * 70)
    print()
    
    # 1. Find Ebenezer user
    print("[1/5] Finding Ebenezer user...")
    user = None
    
    # Search by username, first name, or last name
    all_users = User.objects.filter(
        username__icontains='ebenezer'
    ) | User.objects.filter(
        first_name__icontains='ebenezer'
    ) | User.objects.filter(
        last_name__icontains='ebenezer'
    )
    
    if all_users.exists():
        user = all_users.first()
        print(f"   [OK] Found user: {user.username} ({user.get_full_name()})")
    else:
        print("   [ERROR] User not found. Searching all users...")
        # Show first 10 users for reference
        print("   First 10 users in system:")
        for u in User.objects.all()[:10]:
            print(f"      - {u.username} ({u.get_full_name()})")
        return
    
    print()
    
    # 2. Get or create Finance/Accounting department
    print("[2/5] Setting up Finance department...")
    finance_dept = Department.objects.filter(
        name__icontains='finance'
    ).first()
    
    if not finance_dept:
        finance_dept = Department.objects.filter(
            name__icontains='account'
        ).first()
    
    if not finance_dept:
        # Create Finance department
        finance_dept = Department.objects.create(
            name='Finance',
            code='FIN',
            description='Finance and Accounting Department',
            is_active=True
        )
        print(f"   [OK] Created Finance department")
    else:
        print(f"   [OK] Found department: {finance_dept.name}")
    print()
    
    # 3. Create or update staff record
    print("[3/5] Creating/updating staff record...")
    staff, staff_created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'accountant',
            'department': finance_dept,
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not staff_created:
        # Update existing staff
        staff.profession = 'accountant'
        staff.department = finance_dept
        staff.is_active = True
        staff.is_deleted = False
        if not staff.employee_id:
            staff.employee_id = f'FIN-{user.username.upper()}'
        staff.save()
        print(f"   [OK] Updated staff record: {staff.employee_id}")
    else:
        if not staff.employee_id:
            staff.employee_id = f'FIN-{user.username.upper()}'
            staff.save()
        print(f"   [OK] Created staff record: {staff.employee_id}")
    print()
    
    # 4. Add to Accountant group
    print("[4/5] Adding to Accountant group...")
    accountant_group, created = Group.objects.get_or_create(name='Accountant')
    if created:
        print(f"   [OK] Created Accountant group")
    
    user.groups.add(accountant_group)
    print(f"   [OK] Added {user.username} to Accountant group")
    
    # Also add to Finance group if it exists
    finance_group, created = Group.objects.get_or_create(name='Finance')
    if created:
        print(f"   [OK] Created Finance group")
    user.groups.add(finance_group)
    print(f"   [OK] Added {user.username} to Finance group")
    print()
    
    # 5. Grant financial permissions
    print("[5/5] Granting financial permissions...")
    
    # Financial models that need permissions
    financial_models = [
        'account', 'costcenter', 'transaction', 'paymentreceipt',
        'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
        'paymentvoucher', 'receiptvoucher', 'cheque',
        'revenue', 'revenuecategory', 'expense', 'expensecategory',
        'advancedaccountsreceivable', 'accountspayable',
        'bankaccount', 'banktransaction', 'budget', 'budgetline',
        'cashbook', 'bankreconciliation', 'bankreconciliationitem',
        'insurancereceivable', 'procurementpurchase',
        'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
        'incomegroup', 'profitlossreport',
        'registrationfee', 'cashsale', 'accountingcorporateaccount',
        'withholdingreceivable', 'deposit', 'initialrevaluation',
        'accountcategory', 'fiscalyear', 'accountingperiod', 'journal',
        'undepositedfunds', 'insurancereceivableentry', 'insurancepaymentreceived',
        'invoice', 'invoiceline', 'payment', 'cashiersession',
        'revenuestream', 'departmentrevenue',
    ]
    
    permissions_granted = 0
    for model_name in financial_models:
        try:
            content_type = ContentType.objects.filter(
                app_label='hospital',
                model__iexact=model_name
            ).first()
            
            if content_type:
                # Add all permissions for this model
                perms = Permission.objects.filter(content_type=content_type)
                accountant_group.permissions.add(*perms)
                permissions_granted += perms.count()
        except Exception as e:
            pass
    
    print(f"   [OK] Granted {permissions_granted} financial permissions to Accountant group")
    print()
    
    # 6. Set user properties
    print("[6/6] Setting user properties...")
    user.is_staff = True
    user.is_active = True
    user.is_superuser = False  # Not superuser - restricted to finance
    user.save()
    print(f"   [OK] User is_staff=True, is_active=True, is_superuser=False")
    print()
    
    # Summary
    print("=" * 70)
    print("SETUP COMPLETE!")
    print("=" * 70)
    print()
    print(f"User: {user.username}")
    print(f"Name: {user.get_full_name()}")
    print(f"Email: {user.email}")
    print(f"Department: {finance_dept.name}")
    print(f"Profession: {staff.get_profession_display()}")
    print(f"Employee ID: {staff.employee_id}")
    print(f"Groups: {', '.join([g.name for g in user.groups.all()])}")
    print()
    print("Access URLs:")
    print("  - Comprehensive Dashboard: /hms/accountant/comprehensive-dashboard/")
    print("  - Accounting Dashboard: /hms/accounting/")
    print("  - Cashbook: /hms/accountant/cashbook/")
    print("  - Bank Reconciliation: /hms/accountant/bank-reconciliation/")
    print("  - Financial Reports: /hms/reports/financial/")
    print("  - Procurement Approvals: /hms/procurement/accounts/pending/")
    print()
    print("[OK] Ebenezer is now set up in Finance with full financial access!")
    print()

if __name__ == '__main__':
    setup_ebenezer_finance()

