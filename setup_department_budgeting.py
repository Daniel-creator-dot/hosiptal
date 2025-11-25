#!/usr/bin/env python
"""
Setup Department Budgeting System
Creates budget periods and initializes department budgets
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from hospital.models import Department
from hospital.models_department_budgeting import BudgetPeriod, DepartmentBudget, BudgetLineItem

def setup_budgeting_system():
    print("=" * 70)
    print("Department Budgeting System Setup")
    print("=" * 70)
    print()
    
    # Get admin user
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        print("[ERROR] No admin user found. Please create a superuser first.")
        return
    
    # Create current fiscal year budget period
    current_year = datetime.now().year
    start_date = datetime(current_year, 1, 1).date()
    end_date = datetime(current_year, 12, 31).date()
    
    period, created = BudgetPeriod.objects.get_or_create(
        name=f"FY {current_year}",
        period_type='annual',
        start_date=start_date,
        defaults={
            'end_date': end_date,
            'total_budget': Decimal('5000000.00'),  # GHS 5 million total
            'status': 'active',
            'created_by': admin_user,
            'approved_by': admin_user,
            'approved_at': datetime.now(),
        }
    )
    
    if created:
        print(f"[+] Created budget period: {period.name}")
    else:
        print(f"[i] Budget period already exists: {period.name}")
    
    # Get all active departments
    departments = Department.objects.filter(is_active=True, is_deleted=False)
    dept_count = departments.count()
    
    print(f"\n[i] Found {dept_count} active departments")
    print()
    
    # Define budget allocations (percentage of total budget)
    budget_allocations = {
        'Emergency': {'percentage': 15, 'personnel': 60, 'operational': 25, 'supplies': 10, 'capital': 5},
        'Surgery': {'percentage': 20, 'personnel': 50, 'operational': 20, 'supplies': 20, 'capital': 10},
        'Outpatient': {'percentage': 12, 'personnel': 55, 'operational': 30, 'supplies': 10, 'capital': 5},
        'Inpatient': {'percentage': 15, 'personnel': 55, 'operational': 25, 'supplies': 15, 'capital': 5},
        'Laboratory': {'percentage': 10, 'personnel': 40, 'operational': 25, 'supplies': 30, 'capital': 5},
        'Pharmacy': {'percentage': 10, 'personnel': 35, 'operational': 20, 'supplies': 40, 'capital': 5},
        'Radiology': {'percentage': 8, 'personnel': 45, 'operational': 20, 'supplies': 25, 'capital': 10},
        'Imaging': {'percentage': 8, 'personnel': 45, 'operational': 20, 'supplies': 25, 'capital': 10},
        'Pediatrics': {'percentage': 5, 'personnel': 60, 'operational': 25, 'supplies': 10, 'capital': 5},
        'Maternity': {'percentage': 5, 'personnel': 60, 'operational': 25, 'supplies': 10, 'capital': 5},
    }
    
    # Default allocation for departments not in the list
    default_allocation = {'percentage': 2, 'personnel': 60, 'operational': 25, 'supplies': 10, 'capital': 5}
    
    total_allocated = Decimal('0.00')
    created_count = 0
    
    for dept in departments:
        # Get allocation or use default
        allocation = budget_allocations.get(dept.name, default_allocation)
        
        # Calculate total budget for this department
        total_budget = period.total_budget * Decimal(str(allocation['percentage'] / 100))
        
        # Calculate category budgets
        personnel = total_budget * Decimal(str(allocation['personnel'] / 100))
        operational = total_budget * Decimal(str(allocation['operational'] / 100))
        supplies = total_budget * Decimal(str(allocation['supplies'] / 100))
        capital = total_budget * Decimal(str(allocation['capital'] / 100))
        
        # Create or update department budget
        dept_budget, created = DepartmentBudget.objects.get_or_create(
            budget_period=period,
            department=dept,
            defaults={
                'personnel_budget': personnel,
                'operational_budget': operational,
                'supplies_budget': supplies,
                'capital_budget': capital,
                'status': 'active',
                'justification': f'Annual budget allocation for {dept.name} department',
            }
        )
        
        if created:
            print(f"[+] {dept.name:20s} - GHS {dept_budget.allocated_amount:>12,.2f} ({allocation['percentage']}%)")
            created_count += 1
            
            # Create sample line items
            line_items = [
                {'category': 'personnel', 'name': 'Salaries & Wages', 'amount': personnel * Decimal('0.7')},
                {'category': 'personnel', 'name': 'Benefits & Allowances', 'amount': personnel * Decimal('0.3')},
                {'category': 'operational', 'name': 'Utilities', 'amount': operational * Decimal('0.3')},
                {'category': 'operational', 'name': 'Maintenance', 'amount': operational * Decimal('0.4')},
                {'category': 'operational', 'name': 'Administrative', 'amount': operational * Decimal('0.3')},
                {'category': 'supplies', 'name': 'Medical Supplies', 'amount': supplies * Decimal('0.7')},
                {'category': 'supplies', 'name': 'Office Supplies', 'amount': supplies * Decimal('0.3')},
                {'category': 'capital', 'name': 'Equipment Purchases', 'amount': capital},
            ]
            
            for item_data in line_items:
                if item_data['amount'] > 0:
                    BudgetLineItem.objects.create(
                        department_budget=dept_budget,
                        category=item_data['category'],
                        item_name=item_data['name'],
                        budgeted_amount=item_data['amount'],
                        description=f"{item_data['name']} for {dept.name}"
                    )
        else:
            print(f"[i] {dept.name:20s} - Budget already exists")
        
        total_allocated += dept_budget.allocated_amount
    
    # Update period total
    period.total_allocated = total_allocated
    period.save()
    
    print()
    print("=" * 70)
    print("[SUCCESS] Department Budgeting System Setup Complete!")
    print("=" * 70)
    print()
    print(f"Budget Period: {period.name}")
    print(f"Total Budget: GHS {period.total_budget:,.2f}")
    print(f"Total Allocated: GHS {total_allocated:,.2f}")
    print(f"Departments: {dept_count}")
    print(f"New Budgets Created: {created_count}")
    print()
    print("Access the budget dashboard at:")
    print("  http://127.0.0.1:8000/hms/budget/")
    print()
    print("=" * 70)

if __name__ == '__main__':
    setup_budgeting_system()













