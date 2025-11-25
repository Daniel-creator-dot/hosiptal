"""
Department Budget Management Views
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Q, F
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta

from .models import Department
from .models_department_budgeting import (
    BudgetPeriod, DepartmentBudget, BudgetLineItem,
    BudgetExpense, BudgetTransfer, BudgetAlert,
    BudgetVariance, BudgetRevision
)


def is_accountant(user):
    """Check if user is an accountant"""
    return user.groups.filter(name__in=['Cashier', 'Admin', 'Accountant']).exists() or user.is_staff


@login_required
def budget_dashboard(request):
    """
    Main budget dashboard - overview of all departments
    """
    # Get current active budget period
    current_period = BudgetPeriod.objects.filter(
        status='active',
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date(),
        is_deleted=False
    ).first()
    
    if not current_period:
        # Try to get most recent approved period
        current_period = BudgetPeriod.objects.filter(
            status__in=['approved', 'active'],
            is_deleted=False
        ).order_by('-start_date').first()
    
    # Get all budget periods for dropdown
    all_periods = BudgetPeriod.objects.filter(is_deleted=False).order_by('-start_date')[:12]
    
    # Allow period selection
    selected_period_id = request.GET.get('period')
    if selected_period_id:
        try:
            current_period = BudgetPeriod.objects.get(pk=selected_period_id, is_deleted=False)
        except BudgetPeriod.DoesNotExist:
            pass
    
    department_budgets = []
    total_budget = Decimal('0.00')
    total_spent = Decimal('0.00')
    total_available = Decimal('0.00')
    
    if current_period:
        # Get all department budgets for this period
        budgets = DepartmentBudget.objects.filter(
            budget_period=current_period,
            is_deleted=False
        ).select_related('department').order_by('department__name')
        
        for budget in budgets:
            available = budget.get_available_amount()
            utilization = budget.get_utilization_percentage()
            
            # Determine status
            if budget.is_overbudget():
                status = 'over'
                status_class = 'danger'
            elif utilization >= 90:
                status = 'critical'
                status_class = 'warning'
            elif utilization >= 75:
                status = 'caution'
                status_class = 'info'
            else:
                status = 'good'
                status_class = 'success'
            
            department_budgets.append({
                'id': budget.id,
                'department': budget.department,
                'allocated': budget.allocated_amount,
                'spent': budget.spent_amount,
                'committed': budget.committed_amount,
                'available': available,
                'utilization': utilization,
                'status': status,
                'status_class': status_class,
            })
            
            total_budget += budget.allocated_amount
            total_spent += budget.spent_amount
            total_available += available
    
    # Overall utilization
    overall_utilization = (total_spent / total_budget * 100) if total_budget > 0 else 0
    
    # Get recent alerts
    recent_alerts = []
    if current_period:
        recent_alerts = BudgetAlert.objects.filter(
            department_budget__budget_period=current_period,
            is_acknowledged=False,
            is_deleted=False
        ).select_related('department_budget__department').order_by('-created')[:10]
    
    # Get departments over budget
    over_budget_depts = [b for b in department_budgets if b['status'] == 'over']
    
    # Top spenders
    top_spenders = sorted(department_budgets, key=lambda x: x['spent'], reverse=True)[:5]
    
    context = {
        'current_period': current_period,
        'all_periods': all_periods,
        'department_budgets': department_budgets,
        'total_budget': total_budget,
        'total_spent': total_spent,
        'total_available': total_available,
        'overall_utilization': overall_utilization,
        'recent_alerts': recent_alerts,
        'over_budget_depts': over_budget_depts,
        'top_spenders': top_spenders,
        'alert_count': len(recent_alerts),
    }
    
    return render(request, 'hospital/budget/dashboard.html', context)


@login_required
def department_budget_detail(request, budget_id):
    """
    Detailed view of a department's budget
    """
    budget = get_object_or_404(DepartmentBudget, pk=budget_id, is_deleted=False)
    
    # Get line items
    line_items = budget.line_items.filter(is_deleted=False).order_by('category', 'item_name')
    
    # Category totals
    category_totals = {}
    for item in line_items:
        if item.category not in category_totals:
            category_totals[item.category] = {
                'budgeted': Decimal('0.00'),
                'spent': Decimal('0.00'),
            }
        category_totals[item.category]['budgeted'] += item.budgeted_amount
        category_totals[item.category]['spent'] += item.spent_amount
    
    # Recent expenses
    recent_expenses = budget.expenses.filter(is_deleted=False).order_by('-expense_date')[:20]
    
    # Alerts for this budget
    alerts = budget.alerts.filter(is_acknowledged=False, is_deleted=False).order_by('-created')
    
    # Spending trend (last 30 days)
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    daily_spending = budget.expenses.filter(
        expense_date__gte=thirty_days_ago,
        is_deleted=False
    ).values('expense_date').annotate(total=Sum('amount')).order_by('expense_date')
    
    context = {
        'budget': budget,
        'line_items': line_items,
        'category_totals': category_totals,
        'recent_expenses': recent_expenses,
        'alerts': alerts,
        'daily_spending': list(daily_spending),
        'available': budget.get_available_amount(),
        'utilization': budget.get_utilization_percentage(),
    }
    
    return render(request, 'hospital/budget/department_detail.html', context)


@login_required
def create_budget_period(request):
    """
    Create a new budget period
    """
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            period_type = request.POST.get('period_type')
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            total_budget = Decimal(request.POST.get('total_budget', '0'))
            
            budget_period = BudgetPeriod.objects.create(
                name=name,
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                total_budget=total_budget,
                created_by=request.user,
                notes=request.POST.get('notes', '')
            )
            
            messages.success(request, f'✅ Budget period "{name}" created successfully!')
            return redirect('hospital:budget_dashboard')
            
        except Exception as e:
            messages.error(request, f'❌ Error creating budget period: {str(e)}')
    
    return render(request, 'hospital/budget/create_period.html')


@login_required
def allocate_department_budgets(request, period_id):
    """
    Allocate budgets to departments for a period
    """
    period = get_object_or_404(BudgetPeriod, pk=period_id, is_deleted=False)
    departments = Department.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    if request.method == 'POST':
        try:
            total_allocated = Decimal('0.00')
            
            for dept in departments:
                allocated = request.POST.get(f'budget_{dept.id}')
                if allocated:
                    allocated = Decimal(allocated)
                    
                    # Get category breakdowns
                    personnel = Decimal(request.POST.get(f'personnel_{dept.id}', '0'))
                    operational = Decimal(request.POST.get(f'operational_{dept.id}', '0'))
                    supplies = Decimal(request.POST.get(f'supplies_{dept.id}', '0'))
                    capital = Decimal(request.POST.get(f'capital_{dept.id}', '0'))
                    
                    # Create or update department budget
                    dept_budget, created = DepartmentBudget.objects.update_or_create(
                        budget_period=period,
                        department=dept,
                        defaults={
                            'personnel_budget': personnel,
                            'operational_budget': operational,
                            'supplies_budget': supplies,
                            'capital_budget': capital,
                            'justification': request.POST.get(f'justification_{dept.id}', ''),
                            'status': 'approved',
                        }
                    )
                    
                    total_allocated += dept_budget.allocated_amount
            
            # Update period total
            period.total_allocated = total_allocated
            period.save()
            
            messages.success(request, f'✅ Budgets allocated successfully! Total: GHS {total_allocated:,}')
            return redirect('hospital:budget_dashboard')
            
        except Exception as e:
            messages.error(request, f'❌ Error allocating budgets: {str(e)}')
    
    # Get existing allocations
    existing_budgets = {}
    for budget in period.department_budgets.filter(is_deleted=False):
        existing_budgets[budget.department.id] = budget
    
    context = {
        'period': period,
        'departments': departments,
        'existing_budgets': existing_budgets,
    }
    
    return render(request, 'hospital/budget/allocate_budgets.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/admin/login/')
def budget_vs_actual_report(request):
    """
    Budget vs Actual spending report
    Accountants should have access to this report for financial analysis
    """
    # Get period
    period_id = request.GET.get('period')
    if period_id:
        period = get_object_or_404(BudgetPeriod, pk=period_id, is_deleted=False)
    else:
        period = BudgetPeriod.objects.filter(status='active', is_deleted=False).first()
    
    if not period:
        messages.warning(request, 'No active budget period found.')
        return redirect('hospital:budget_dashboard')
    
    # Get all department budgets
    budgets = DepartmentBudget.objects.filter(
        budget_period=period,
        is_deleted=False
    ).select_related('department').order_by('department__name')
    
    report_data = []
    for budget in budgets:
        variance = budget.allocated_amount - budget.spent_amount
        variance_percentage = ((variance / budget.allocated_amount) * 100) if budget.allocated_amount > 0 else 0
        
        report_data.append({
            'department': budget.department.name,
            'budgeted': budget.allocated_amount,
            'spent': budget.spent_amount,
            'variance': variance,
            'variance_percentage': variance_percentage,
            'utilization': budget.get_utilization_percentage(),
            'status': 'Favorable' if variance >= 0 else 'Unfavorable',
        })
    
    # Calculate totals
    total_budgeted = sum(item['budgeted'] for item in report_data)
    total_spent = sum(item['spent'] for item in report_data)
    total_variance = total_budgeted - total_spent
    
    context = {
        'period': period,
        'report_data': report_data,
        'total_budgeted': total_budgeted,
        'total_spent': total_spent,
        'total_variance': total_variance,
        'overall_utilization': (total_spent / total_budgeted * 100) if total_budgeted > 0 else 0,
    }
    
    return render(request, 'hospital/budget/budget_vs_actual.html', context)


@login_required
def my_department_budget(request):
    """
    View budget for logged-in user's department
    """
    # Get user's staff profile and department
    try:
        staff = request.user.staff
        department = staff.department
    except:
        messages.error(request, 'You must be registered as staff to view department budget.')
        return redirect('hospital:dashboard')
    
    # Get current active period
    current_period = BudgetPeriod.objects.filter(
        status='active',
        is_deleted=False
    ).first()
    
    if not current_period:
        messages.warning(request, 'No active budget period.')
        return redirect('hospital:dashboard')
    
    # Get department budget
    try:
        budget = DepartmentBudget.objects.get(
            budget_period=current_period,
            department=department,
            is_deleted=False
        )
    except DepartmentBudget.DoesNotExist:
        messages.warning(request, f'No budget allocated for {department.name} in current period.')
        return redirect('hospital:dashboard')
    
    return redirect('hospital:department_budget_detail', budget_id=budget.id)












