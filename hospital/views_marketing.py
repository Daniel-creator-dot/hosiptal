"""
Marketing Strategy Views
Task management, campaign tracking, and corporate partnerships
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from django.urls import reverse
from django.db import transaction, IntegrityError
from datetime import date, timedelta
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)

from .models_marketing import (
    MarketingObjective, MarketingTask, MarketingCampaign,
    MarketingMetric, CorporatePartnership, CallReport
)
from .models import Patient, Encounter
from django.contrib.auth.decorators import user_passes_test
from .utils_roles import get_user_role

def is_admin_or_marketing(user):
    """Check if user is admin, superuser, or has marketing role"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Do NOT treat is_staff as admin. Staff flag is used broadly (login-enabled accounts).
    user_role = get_user_role(user)
    return user_role in ['admin', 'marketing']

def marketing_access_required(view_func):
    """Decorator to require admin or marketing access"""
    return user_passes_test(is_admin_or_marketing)(view_func)


@login_required
@marketing_access_required
def marketing_dashboard(request):
    """Comprehensive marketing strategy dashboard"""
    today = timezone.now().date()
    this_month_start = date(today.year, today.month, 1)
    
    # Objectives Overview
    total_objectives = MarketingObjective.objects.count()
    active_objectives = MarketingObjective.objects.filter(status='active').count()
    completed_objectives = MarketingObjective.objects.filter(status='completed').count()
    overdue_objectives = MarketingObjective.objects.filter(
        status__in=['planning', 'active'],
        target_completion_date__lt=today
    ).count()
    
    # Tasks Overview
    total_tasks = MarketingTask.objects.count()
    pending_tasks = MarketingTask.objects.filter(status='pending').count()
    in_progress_tasks = MarketingTask.objects.filter(status='in_progress').count()
    completed_tasks = MarketingTask.objects.filter(status='completed').count()
    overdue_tasks = MarketingTask.objects.filter(
        status__in=['pending', 'in_progress'],
        due_date__lt=today
    ).count()
    
    # Campaigns Overview
    active_campaigns = MarketingCampaign.objects.filter(status='active').count()
    total_campaigns = MarketingCampaign.objects.count()
    campaign_budget_total = MarketingCampaign.objects.aggregate(
        total=Sum('budget')
    )['total'] or 0
    campaign_spent_total = MarketingCampaign.objects.aggregate(
        total=Sum('spent')
    )['total'] or 0
    
    # Recent Objectives
    recent_objectives = MarketingObjective.objects.select_related('owner').order_by('-created')[:5]
    
    # Upcoming Tasks
    upcoming_tasks = MarketingTask.objects.select_related(
        'objective', 'assigned_to'
    ).filter(
        status__in=['pending', 'in_progress'],
        due_date__gte=today
    ).order_by('due_date')[:10]
    
    # Active Campaigns
    active_campaigns_list = MarketingCampaign.objects.filter(
        status='active'
    ).select_related('owner').order_by('-start_date')[:5]
    
    # Corporate Partnerships
    active_partnerships = CorporatePartnership.objects.filter(status='active').count()
    total_partnerships = CorporatePartnership.objects.count()
    partnership_value = CorporatePartnership.objects.filter(
        status='active'
    ).aggregate(total=Sum('value'))['total'] or 0
    
    # Marketing Metrics (Last 30 days)
    metrics_start = today - timedelta(days=30)
    recent_metrics_raw = MarketingMetric.objects.filter(
        date__gte=metrics_start
    ).values('metric_type').annotate(
        total_value=Sum('value')
    ).order_by('-total_value')[:10]
    
    # Format metric types for display (replace underscores with spaces)
    recent_metrics = []
    for metric in recent_metrics_raw:
        metric['metric_type_display'] = metric['metric_type'].replace('_', ' ').title()
        recent_metrics.append(metric)
    
    # Call Reports Statistics
    total_call_reports = CallReport.objects.count()
    calls_today = CallReport.objects.filter(call_date__date=today).count()
    calls_this_week = CallReport.objects.filter(
        call_date__date__gte=today - timedelta(days=7)
    ).count()
    calls_this_month = CallReport.objects.filter(
        call_date__date__gte=this_month_start
    ).count()
    follow_ups_due = CallReport.objects.filter(
        follow_up_required=True,
        follow_up_date__lte=timezone.now()
    ).count()
    high_value_opportunities = CallReport.objects.filter(
        potential_value__gte=10000
    ).count()
    total_potential_value = CallReport.objects.aggregate(
        total=Sum('potential_value')
    )['total'] or 0
    total_actual_value = CallReport.objects.aggregate(
        total=Sum('actual_value')
    )['total'] or 0
    
    # Recent call reports
    recent_call_reports = CallReport.objects.select_related(
        'reported_by', 'assigned_to', 'campaign', 'objective', 'partnership'
    ).order_by('-call_date')[:10]
    
    # Call outcome statistics
    call_outcomes = CallReport.objects.values('call_outcome').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Calculate marketing ROI
    total_marketing_spend = campaign_spent_total
    # Estimate revenue from new patients in last 30 days (attributed to marketing)
    new_patients_30d = Patient.objects.filter(
        created__gte=metrics_start,
        is_deleted=False
    ).count()
    
    # Get revenue from new patients (estimate)
    try:
        from .models_accounting import PaymentReceipt
        new_patient_revenue = PaymentReceipt.objects.filter(
            receipt_date__gte=metrics_start,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
    except ImportError:
        new_patient_revenue = 0
    
    marketing_roi = 0
    if total_marketing_spend > 0:
        marketing_roi = ((new_patient_revenue - total_marketing_spend) / total_marketing_spend) * 100
    
    context = {
        'title': 'Marketing Strategy Dashboard',
        'total_objectives': total_objectives,
        'active_objectives': active_objectives,
        'completed_objectives': completed_objectives,
        'overdue_objectives': overdue_objectives,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'active_campaigns': active_campaigns,
        'total_campaigns': total_campaigns,
        'campaign_budget_total': campaign_budget_total,
        'campaign_spent_total': campaign_spent_total,
        'recent_objectives': recent_objectives,
        'upcoming_tasks': upcoming_tasks,
        'active_campaigns_list': active_campaigns_list,
        'active_partnerships': active_partnerships,
        'total_partnerships': total_partnerships,
        'partnership_value': partnership_value,
        'recent_metrics': recent_metrics,
        'new_patients_30d': new_patients_30d,
        'new_patient_revenue': new_patient_revenue,
        'marketing_roi': round(marketing_roi, 2),
        'today': today,
        # Call Reports Data
        'total_call_reports': total_call_reports,
        'calls_today': calls_today,
        'calls_this_week': calls_this_week,
        'calls_this_month': calls_this_month,
        'follow_ups_due': follow_ups_due,
        'high_value_opportunities': high_value_opportunities,
        'total_potential_value': total_potential_value,
        'total_actual_value': total_actual_value,
        'recent_call_reports': recent_call_reports,
        'call_outcomes': call_outcomes,
    }
    
    return render(request, 'hospital/marketing/marketing_dashboard_enhanced.html', context)


@login_required
@marketing_access_required
def marketing_objectives_list(request):
    """List all marketing objectives"""
    objectives = MarketingObjective.objects.select_related('owner').prefetch_related(
        'assigned_team', 'marketing_tasks'
    ).all()
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        objectives = objectives.filter(status=status_filter)
    
    # Filter by priority if provided
    priority_filter = request.GET.get('priority')
    if priority_filter:
        objectives = objectives.filter(priority=priority_filter)
    
    context = {
        'title': 'Marketing Objectives',
        'objectives': objectives,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
    }
    
    return render(request, 'hospital/marketing/objectives_list.html', context)


@login_required
@marketing_access_required
def create_marketing_objective(request):
    """Create a new marketing objective with duplicate prevention"""
    from django.db import transaction, IntegrityError
    
    if request.method == 'POST':
        # CRITICAL: Check if this is an auto-save request - IGNORE IT to prevent duplicates
        is_auto_save = request.POST.get('auto_save') == 'true' or \
                      request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        
        if is_auto_save:
            # Auto-save should NOT create objectives - return success but don't save
            logger.warning("Auto-save request detected on objective creation - ignoring to prevent duplicate creation")
            return JsonResponse({'status': 'ignored', 'message': 'Objective creation cannot be auto-saved'})
        
        # Check for duplicate submission using session token
        submission_token = request.POST.get('submission_token')
        if submission_token:
            session_key = f'objective_submission_{submission_token}'
            if request.session.get(session_key):
                logger.error(f"DUPLICATE SUBMISSION DETECTED! Token: {submission_token}")
                messages.error(request, 'This form was already submitted. Please do not refresh the page.')
                return redirect('hospital:marketing_objectives_list')
            # Mark this submission as processed
            request.session[session_key] = True
            request.session.set_expiry(300)  # 5 minutes
        
        try:
            with transaction.atomic():
                data = request.POST
                title = data.get('title', '').strip()
                
                if not title:
                    messages.error(request, 'Objective title is required.')
                    return redirect('hospital:create_marketing_objective')
                
                # DUPLICATE PREVENTION: Check for existing objective with same title
                # Use select_for_update to lock rows and prevent race conditions
                existing = MarketingObjective.objects.select_for_update().filter(
                    title__iexact=title,
                    is_deleted=False
                ).first()
                
                if existing:
                    messages.warning(
                        request,
                        f'An objective with the title "{title}" already exists. '
                        f'<a href="{reverse("hospital:marketing_objective_detail", args=[existing.id])}">View existing objective</a>'
                    )
                    return redirect('hospital:create_marketing_objective')
                
                # Get owner (default to current user)
                owner_id = data.get('owner')
                if owner_id:
                    from django.contrib.auth.models import User
                    owner = User.objects.get(id=owner_id)
                else:
                    owner = request.user
                
                # Final check right before creation (double safety)
                if MarketingObjective.objects.filter(title__iexact=title, is_deleted=False).exists():
                    messages.warning(request, f'An objective with this title already exists. Please use a different title.')
                    return redirect('hospital:create_marketing_objective')
                
                # Create objective
                # Log creation attempt
                logger.info(
                    f"Creating marketing objective - "
                    f"User: {request.user.username}, "
                    f"Title: {title}, "
                    f"Auto-save: {request.POST.get('auto_save') == 'true' or request.META.get('HTTP_X_AUTO_SAVE') == 'true'}, "
                    f"Timestamp: {timezone.now()}"
                )
                
                objective = MarketingObjective.objects.create(
                    title=title,
                    objective_type=data.get('objective_type', 'brand_awareness'),
                    description=data.get('description', ''),
                    target_audience=data.get('target_audience', ''),
                    budget_allocated=Decimal(data.get('budget_allocated', 0) or 0),
                    start_date=data.get('start_date'),
                    target_completion_date=data.get('target_completion_date'),
                    priority=data.get('priority', 'medium'),
                    status=data.get('status', 'planning'),
                    owner=owner,
                    target_metric_value=Decimal(data.get('target_metric_value', 0) or 0) if data.get('target_metric_value') else None,
                    metric_type=data.get('metric_type', ''),
                    notes=data.get('notes', ''),
                )
                
                # Add assigned team members
                team_members = request.POST.getlist('assigned_team')
                if team_members:
                    from django.contrib.auth.models import User
                    team_users = User.objects.filter(id__in=team_members)
                    objective.assigned_team.set(team_users)
                
                messages.success(request, f'Objective "{objective.title}" created successfully!')
                return redirect('hospital:marketing_objective_detail', objective_id=objective.id)
                
        except IntegrityError as e:
            messages.error(request, 'An objective with this title may already exist. Please check and try again.')
            logger.error(f"IntegrityError creating objective: {e}")
            return redirect('hospital:create_marketing_objective')
        except Exception as e:
            messages.error(request, f'Error creating objective: {str(e)}')
            logger.error(f"Error creating objective: {e}")
            return redirect('hospital:create_marketing_objective')
    
    # GET request - show form
    from django.contrib.auth.models import User
    staff_users = User.objects.filter(
        is_staff=True,
        is_active=True
    ).select_related('staff').order_by('first_name', 'last_name', 'username')
    
    # Get today's date for default values
    from datetime import date, timedelta
    today = date.today()
    default_end_date = today + timedelta(days=90)  # 3 months default
    
    context = {
        'title': 'Create New Marketing Objective',
        'staff_users': staff_users,
        'default_start_date': today.strftime('%Y-%m-%d'),
        'default_end_date': default_end_date.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'hospital/marketing/create_objective.html', context)


@login_required
@marketing_access_required
def marketing_objective_detail(request, objective_id):
    """View details of a marketing objective with tasks"""
    objective = get_object_or_404(
        MarketingObjective.objects.select_related('owner').prefetch_related(
            'assigned_team', 'marketing_tasks__assigned_to'
        ),
        id=objective_id
    )
    
    tasks = objective.marketing_tasks.all().order_by('-priority', 'due_date')
    
    # Task statistics
    task_stats = {
        'total': tasks.count(),
        'pending': tasks.filter(status='pending').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'completed': tasks.filter(status='completed').count(),
        'overdue': tasks.filter(
            status__in=['pending', 'in_progress'],
            due_date__lt=timezone.now().date()
        ).count(),
    }
    
    context = {
        'title': f'Objective: {objective.title}',
        'objective': objective,
        'tasks': tasks,
        'task_stats': task_stats,
    }
    
    return render(request, 'hospital/marketing/objective_detail.html', context)


@login_required
@marketing_access_required
@require_http_methods(["POST"])
def create_marketing_task(request, objective_id):
    """Create a new task for a marketing objective with duplicate prevention"""
    objective = get_object_or_404(MarketingObjective, id=objective_id)
    
    # CRITICAL: Check if this is an auto-save request - IGNORE IT to prevent duplicates
    is_auto_save = (
        (request.body and b'auto_save' in request.body and b'true' in request.body) or
        request.META.get('HTTP_X_AUTO_SAVE') == 'true' or
        (hasattr(request, 'POST') and request.POST.get('auto_save') == 'true')
    )
    
    if is_auto_save:
        logger.warning("Auto-save request detected on task creation - ignoring to prevent duplicate creation")
        return JsonResponse({'status': 'ignored', 'message': 'Task creation cannot be auto-saved'})
    
    try:
        with transaction.atomic():
            data = json.loads(request.body) if request.body else request.POST
            title = data.get('title', '').strip()
            
            if not title:
                return JsonResponse({
                    'success': False,
                    'error': 'Task title is required'
                }, status=400)
            
            # DUPLICATE PREVENTION: Check for existing task with same title for this objective
            existing = MarketingTask.objects.select_for_update().filter(
                objective=objective,
                title__iexact=title,
                is_deleted=False
            ).first()
            
            if existing:
                return JsonResponse({
                    'success': False,
                    'error': f'A task with the title "{title}" already exists for this objective.'
                }, status=400)
            
            # Final check before creation
            if MarketingTask.objects.filter(
                objective=objective,
                title__iexact=title,
                is_deleted=False
            ).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'A task with this title already exists for this objective.'
                }, status=400)
            
            task = MarketingTask.objects.create(
                objective=objective,
                title=title,
                task_type=data.get('task_type', 'other'),
                description=data.get('description', ''),
                assigned_to_id=data.get('assigned_to') if data.get('assigned_to') else None,
                due_date=data.get('due_date'),
                priority=data.get('priority', 'medium'),
                estimated_hours=data.get('estimated_hours'),
                budget_allocated=data.get('budget_allocated', 0),
            )
            
            messages.success(request, f'Task "{task.title}" created successfully')
            return JsonResponse({
                'success': True,
                'task_id': str(task.id),
                'message': 'Task created successfully'
            })
    except IntegrityError as e:
        logger.error(f"IntegrityError creating task: {e}")
        return JsonResponse({
            'success': False,
            'error': 'A task with this title may already exist for this objective.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@marketing_access_required
@require_http_methods(["POST"])
def update_task_status(request, task_id):
    """Update task status"""
    task = get_object_or_404(MarketingTask, id=task_id)
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        new_status = data.get('status')
        
        if new_status in dict(MarketingTask.STATUS_CHOICES):
            task.status = new_status
            if new_status == 'completed':
                task.completed_date = timezone.now().date()
                task.mark_completed()
            task.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Task status updated'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid status'
            }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@marketing_access_required
def marketing_campaigns_list(request):
    """List all marketing campaigns"""
    campaigns = MarketingCampaign.objects.select_related('owner').all()
    
    status_filter = request.GET.get('status')
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    
    context = {
        'title': 'Marketing Campaigns',
        'campaigns': campaigns,
        'status_filter': status_filter,
    }
    
    return render(request, 'hospital/marketing/campaigns_list.html', context)


@login_required
@marketing_access_required
def corporate_partnerships_list(request):
    """List all corporate partnerships"""
    partnerships = CorporatePartnership.objects.select_related('owner').all()
    
    status_filter = request.GET.get('status')
    if status_filter:
        partnerships = partnerships.filter(status=status_filter)
    
    context = {
        'title': 'Corporate Partnerships',
        'partnerships': partnerships,
        'status_filter': status_filter,
    }
    
    return render(request, 'hospital/marketing/partnerships_list.html', context)


@login_required
@marketing_access_required
def marketing_tasks_list(request):
    """List all marketing tasks"""
    tasks = MarketingTask.objects.select_related(
        'objective', 'assigned_to'
    ).all().order_by('-created')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    # Filter by priority if provided
    priority_filter = request.GET.get('priority')
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Filter by objective if provided
    objective_filter = request.GET.get('objective')
    if objective_filter:
        tasks = tasks.filter(objective_id=objective_filter)
    
    # Get all objectives for filter dropdown
    objectives = MarketingObjective.objects.filter(status__in=['planning', 'active']).order_by('title')
    
    context = {
        'title': 'Marketing Tasks',
        'tasks': tasks,
        'objectives': objectives,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'objective_filter': objective_filter,
    }
    
    return render(request, 'hospital/marketing/tasks_list.html', context)


@login_required
@marketing_access_required
def create_task_standalone(request):
    """Create a new task (standalone page, can select objective) with duplicate prevention"""
    if request.method == 'POST':
        # CRITICAL: Check if this is an auto-save request - IGNORE IT to prevent duplicates
        is_auto_save = request.POST.get('auto_save') == 'true' or \
                      request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        
        if is_auto_save:
            # Auto-save should NOT create tasks - return success but don't save
            logger.warning("Auto-save request detected on task creation - ignoring to prevent duplicate creation")
            return JsonResponse({'status': 'ignored', 'message': 'Task creation cannot be auto-saved'})
        
        # Check for duplicate submission
        submission_token = request.POST.get('submission_token')
        if submission_token:
            session_key = f'task_submission_{submission_token}'
            if request.session.get(session_key):
                logger.error(f"DUPLICATE SUBMISSION DETECTED! Token: {submission_token}")
                messages.error(request, 'This form was already submitted. Please do not refresh the page.')
                return redirect('hospital:marketing_tasks_list')
            request.session[session_key] = True
            request.session.set_expiry(300)
        
        try:
            with transaction.atomic():
                data = request.POST
                
                objective_id = data.get('objective')
                if not objective_id:
                    messages.error(request, 'Please select an objective for this task.')
                    return redirect('hospital:create_task_standalone')
                
                objective = get_object_or_404(MarketingObjective, id=objective_id)
                title = data.get('title', '').strip()
                
                if not title:
                    messages.error(request, 'Task title is required.')
                    return redirect('hospital:create_task_standalone')
                
                # DUPLICATE PREVENTION: Check for existing task
                existing = MarketingTask.objects.select_for_update().filter(
                    objective=objective,
                    title__iexact=title,
                    is_deleted=False
                ).first()
                
                if existing:
                    messages.warning(
                        request,
                        f'A task with the title "{title}" already exists for this objective. '
                        f'Please use a different title or view the existing task.'
                    )
                    return redirect('hospital:create_task_standalone')
                
                # Final check before creation
                if MarketingTask.objects.filter(
                    objective=objective,
                    title__iexact=title,
                    is_deleted=False
                ).exists():
                    messages.warning(request, 'A task with this title already exists for this objective.')
                    return redirect('hospital:create_task_standalone')
                
                # Log creation attempt
                logger.info(
                    f"Creating marketing task - "
                    f"User: {request.user.username}, "
                    f"Title: {data.get('title', 'N/A')}, "
                    f"Objective: {objective.id}, "
                    f"Auto-save: {request.POST.get('auto_save') == 'true' or request.META.get('HTTP_X_AUTO_SAVE') == 'true'}, "
                    f"Timestamp: {timezone.now()}"
                )
                
                task = MarketingTask.objects.create(
                    objective=objective,
                    title=title,
                    task_type=data.get('task_type', 'other'),
                    description=data.get('description', ''),
                    assigned_to_id=data.get('assigned_to') if data.get('assigned_to') else None,
                    due_date=data.get('due_date'),
                    priority=data.get('priority', 'medium'),
                    estimated_hours=data.get('estimated_hours'),
                    budget_allocated=data.get('budget_allocated', 0),
                )
                
                messages.success(request, f'Task "{task.title}" created successfully!')
                return redirect('hospital:marketing_tasks_list')
        except IntegrityError as e:
            logger.error(f"IntegrityError creating task: {e}")
            messages.error(request, 'A task with this title may already exist. Please check and try again.')
            return redirect('hospital:create_task_standalone')
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            messages.error(request, f'Error creating task: {str(e)}')
            return redirect('hospital:create_task_standalone')
    
    # GET request - show form
    # Show all objectives, prioritizing active/planning ones
    objectives = MarketingObjective.objects.all().order_by(
        'status',  # This will group by status
        'title'
    )
    
    # Get staff users for assignment
    from django.contrib.auth.models import User
    staff_users = User.objects.filter(
        is_staff=True,
        is_active=True
    ).select_related('staff').order_by('first_name', 'last_name', 'username')
    
    context = {
        'title': 'Create New Task',
        'objectives': objectives,
        'staff_users': staff_users,
    }
    
    return render(request, 'hospital/marketing/create_task.html', context)


@login_required
@marketing_access_required
def marketing_metrics_api(request):
    """API endpoint for marketing metrics data"""
    # If user opens this API directly in a browser, show a real UI instead of raw JSON.
    # Use ?raw=1 to force JSON in a browser.
    accept = request.META.get('HTTP_ACCEPT', '') or ''
    if ('text/html' in accept) and ('application/json' not in accept) and request.GET.get('raw') != '1':
        return redirect('hospital:marketing_metrics_dashboard')

    today = timezone.now().date()
    days = int(request.GET.get('days', 30))
    start_date = today - timedelta(days=days)
    
    metrics = MarketingMetric.objects.filter(
        date__gte=start_date
    ).values('date', 'metric_type').annotate(
        total_value=Sum('value')
    ).order_by('date')
    
    # Format for chart (always include known metric types even if empty)
    chart_data = {key: {'dates': [], 'values': []} for key, _label in getattr(MarketingMetric, 'METRIC_TYPES', [])}
    for metric in metrics:
        metric_type = metric['metric_type']
        if metric_type not in chart_data:
            chart_data[metric_type] = {'dates': [], 'values': []}
        chart_data[metric_type]['dates'].append(metric['date'].strftime('%Y-%m-%d'))
        chart_data[metric_type]['values'].append(float(metric['total_value']))

    # Add derived summary metrics so the endpoint is useful even when no MarketingMetric records exist yet.
    # This is safe/defaulted and supports the enhanced dashboard.
    try:
        objectives_total = MarketingObjective.objects.filter(is_deleted=False).count()
        objectives_active = MarketingObjective.objects.filter(is_deleted=False, status__in=['planning', 'active']).count()
        objectives_completed = MarketingObjective.objects.filter(is_deleted=False, status='completed').count()
    except Exception:
        objectives_total = objectives_active = objectives_completed = 0

    try:
        tasks_total = MarketingTask.objects.filter(is_deleted=False).count()
        tasks_completed = MarketingTask.objects.filter(is_deleted=False, status='completed').count()
        tasks_overdue = MarketingTask.objects.filter(
            is_deleted=False,
            status__in=['pending', 'in_progress', 'review', 'blocked'],
            due_date__lt=today,
        ).count()
    except Exception:
        tasks_total = tasks_completed = tasks_overdue = 0

    try:
        campaigns_active = MarketingCampaign.objects.filter(is_deleted=False, status='active').count()
        campaign_budget = MarketingCampaign.objects.filter(is_deleted=False).aggregate(total=Sum('budget'))['total'] or 0
        campaign_spent = MarketingCampaign.objects.filter(is_deleted=False).aggregate(total=Sum('spent'))['total'] or 0
    except Exception:
        campaigns_active = 0
        campaign_budget = 0
        campaign_spent = 0

    try:
        partnerships_active = CorporatePartnership.objects.filter(is_deleted=False, status='active').count()
        partnerships_total = CorporatePartnership.objects.filter(is_deleted=False).count()
    except Exception:
        partnerships_active = 0
        partnerships_total = 0

    try:
        from django.db.models.functions import TruncDate
        calls_qs = CallReport.objects.filter(is_deleted=False, call_date__date__gte=start_date, call_date__date__lte=today)
        calls_total_period = calls_qs.count()
        followups_due = calls_qs.filter(follow_up_required=True, follow_up_date__isnull=False, follow_up_date__lte=timezone.now()).count()
        value_agg = calls_qs.aggregate(
            potential_total=Sum('potential_value'),
            actual_total=Sum('actual_value'),
        )
        potential_total = value_agg.get('potential_total') or 0
        actual_total = value_agg.get('actual_total') or 0

        calls_series = calls_qs.annotate(d=TruncDate('call_date')).values('d').annotate(count=models.Count('id')).order_by('d')
        calls_series_formatted = [
            {'date': row['d'].strftime('%Y-%m-%d'), 'count': int(row['count'])}
            for row in calls_series
            if row.get('d')
        ]
    except Exception:
        calls_total_period = 0
        followups_due = 0
        potential_total = 0
        actual_total = 0
        calls_series_formatted = []
    
    return JsonResponse({
        'success': True,
        'data': chart_data,
        'period': {
            'days': days,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': today.strftime('%Y-%m-%d'),
        },
        'summary': {
            'objectives': {
                'total': objectives_total,
                'active': objectives_active,
                'completed': objectives_completed,
            },
            'tasks': {
                'total': tasks_total,
                'completed': tasks_completed,
                'overdue': tasks_overdue,
            },
            'campaigns': {
                'active': campaigns_active,
                'budget_total': float(campaign_budget) if campaign_budget is not None else 0,
                'spent_total': float(campaign_spent) if campaign_spent is not None else 0,
            },
            'partnerships': {
                'total': partnerships_total,
                'active': partnerships_active,
            },
            'call_reports': {
                'total_in_period': calls_total_period,
                'followups_due': followups_due,
                'potential_value_total': float(potential_total) if potential_total is not None else 0,
                'actual_value_total': float(actual_total) if actual_total is not None else 0,
            },
        },
        'series': {
            'call_reports_per_day': calls_series_formatted,
        }
    })


@login_required
@marketing_access_required
def marketing_metrics_dashboard(request):
    """UI dashboard for marketing metrics (charts + summaries)."""
    return render(request, 'hospital/marketing/metrics_dashboard.html', {
        'title': 'Marketing Metrics & Analytics',
    })


# ==================== CALL REPORTS ====================

@login_required
@marketing_access_required
def call_reports_list(request):
    """List all call reports with filtering and search"""
    call_reports = CallReport.objects.select_related(
        'reported_by', 'assigned_to', 'campaign', 'objective', 'partnership'
    ).all().order_by('-call_date')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        call_reports = call_reports.filter(
            Q(contact_name__icontains=search_query) |
            Q(contact_phone__icontains=search_query) |
            Q(company_name__icontains=search_query) |
            Q(call_summary__icontains=search_query)
        )
    
    # Filters
    call_type_filter = request.GET.get('call_type')
    if call_type_filter:
        call_reports = call_reports.filter(call_type=call_type_filter)
    
    outcome_filter = request.GET.get('outcome')
    if outcome_filter:
        call_reports = call_reports.filter(call_outcome=outcome_filter)
    
    follow_up_filter = request.GET.get('follow_up')
    if follow_up_filter == 'required':
        call_reports = call_reports.filter(follow_up_required=True)
    elif follow_up_filter == 'due':
        call_reports = call_reports.filter(
            follow_up_required=True,
            follow_up_date__lte=timezone.now()
        )
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        call_reports = call_reports.filter(call_date__date__gte=date_from)
    if date_to:
        call_reports = call_reports.filter(call_date__date__lte=date_to)
    
    # Statistics
    today = date.today()
    total_calls = call_reports.count()
    calls_today = CallReport.objects.filter(call_date__date=today).count()
    follow_ups_due = CallReport.objects.filter(
        follow_up_required=True,
        follow_up_date__lte=timezone.now()
    ).count()
    high_value_opportunities = CallReport.objects.filter(
        potential_value__gte=10000
    ).count()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(call_reports, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Call Reports',
        'call_reports': page_obj,
        'total_calls': total_calls,
        'calls_today': calls_today,
        'follow_ups_due': follow_ups_due,
        'high_value_opportunities': high_value_opportunities,
        'search_query': search_query,
        'call_type_filter': call_type_filter,
        'outcome_filter': outcome_filter,
        'follow_up_filter': follow_up_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'hospital/marketing/call_reports_list.html', context)


@login_required
@marketing_access_required
def create_call_report(request):
    """Create a new call report"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                data = request.POST
                
                # Parse call date and time
                call_date_str = data.get('call_date')
                call_time_str = data.get('call_time', '00:00')
                if call_date_str:
                    from datetime import datetime
                    try:
                        call_datetime = datetime.strptime(
                            f"{call_date_str} {call_time_str}",
                            "%Y-%m-%d %H:%M"
                        )
                        call_datetime = timezone.make_aware(call_datetime)
                    except:
                        call_datetime = timezone.now()
                else:
                    call_datetime = timezone.now()
                
                # Parse follow-up date if provided
                follow_up_date = None
                if data.get('follow_up_required') == 'on' and data.get('follow_up_date'):
                    follow_up_date_str = data.get('follow_up_date')
                    follow_up_time_str = data.get('follow_up_time', '09:00')
                    try:
                        follow_up_datetime = datetime.strptime(
                            f"{follow_up_date_str} {follow_up_time_str}",
                            "%Y-%m-%d %H:%M"
                        )
                        follow_up_date = timezone.make_aware(follow_up_datetime)
                    except:
                        pass
                
                call_report = CallReport.objects.create(
                    call_date=call_datetime,
                    call_type=data.get('call_type', 'cold_call'),
                    call_duration_minutes=int(data.get('call_duration_minutes', 0) or 0),
                    contact_name=data.get('contact_name', '').strip(),
                    contact_phone=data.get('contact_phone', '').strip(),
                    contact_email=data.get('contact_email', '').strip(),
                    company_name=data.get('company_name', '').strip(),
                    contact_title=data.get('contact_title', '').strip(),
                    call_outcome=data.get('call_outcome', 'other'),
                    call_summary=data.get('call_summary', '').strip(),
                    key_points=data.get('key_points', '').strip(),
                    objections_raised=data.get('objections_raised', '').strip(),
                    next_steps=data.get('next_steps', '').strip(),
                    follow_up_required=data.get('follow_up_required') == 'on',
                    follow_up_date=follow_up_date,
                    follow_up_notes=data.get('follow_up_notes', '').strip(),
                    priority=data.get('priority', 'medium'),
                    potential_value=Decimal(data.get('potential_value', 0) or 0) if data.get('potential_value') else None,
                    actual_value=Decimal(data.get('actual_value', 0) or 0) if data.get('actual_value') else None,
                    service_interest=data.get('service_interest', '').strip(),
                    relationship_stage=data.get('relationship_stage', 'new'),
                    campaign_id=data.get('campaign') if data.get('campaign') else None,
                    objective_id=data.get('objective') if data.get('objective') else None,
                    partnership_id=data.get('partnership') if data.get('partnership') else None,
                    reported_by=request.user,
                    assigned_to_id=data.get('assigned_to') if data.get('assigned_to') else None,
                    internal_notes=data.get('internal_notes', '').strip(),
                    tags=data.get('tags', '').strip(),
                )
                
                messages.success(request, f'Call report for {call_report.contact_name} created successfully!')
                return redirect('hospital:call_report_detail', report_id=call_report.id)
        except Exception as e:
            logger.error(f"Error creating call report: {e}")
            messages.error(request, f'Error creating call report: {str(e)}')
    
    # GET request - show form
    from django.contrib.auth.models import User
    staff_users = User.objects.filter(
        is_staff=True,
        is_active=True
    ).select_related('staff').order_by('first_name', 'last_name', 'username')
    
    campaigns = MarketingCampaign.objects.filter(status__in=['active', 'scheduled']).order_by('title')
    objectives = MarketingObjective.objects.filter(status__in=['planning', 'active']).order_by('title')
    partnerships = CorporatePartnership.objects.filter(status__in=['prospect', 'negotiating', 'active']).order_by('company_name')
    
    context = {
        'title': 'Create Call Report',
        'staff_users': staff_users,
        'campaigns': campaigns,
        'objectives': objectives,
        'partnerships': partnerships,
    }
    
    return render(request, 'hospital/marketing/create_call_report.html', context)


@login_required
@marketing_access_required
def call_report_detail(request, report_id):
    """View details of a call report"""
    call_report = get_object_or_404(
        CallReport.objects.select_related(
            'reported_by', 'assigned_to', 'campaign', 'objective', 'partnership'
        ),
        id=report_id
    )
    
    context = {
        'title': f'Call Report: {call_report.contact_name}',
        'call_report': call_report,
    }
    
    return render(request, 'hospital/marketing/call_report_detail.html', context)


@login_required
@marketing_access_required
def edit_call_report(request, report_id):
    """Edit a call report"""
    call_report = get_object_or_404(CallReport, id=report_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                data = request.POST
                
                # Parse call date and time
                call_date_str = data.get('call_date')
                call_time_str = data.get('call_time', '00:00')
                if call_date_str:
                    from datetime import datetime
                    try:
                        call_datetime = datetime.strptime(
                            f"{call_date_str} {call_time_str}",
                            "%Y-%m-%d %H:%M"
                        )
                        call_datetime = timezone.make_aware(call_datetime)
                        call_report.call_date = call_datetime
                    except:
                        pass
                
                # Parse follow-up date if provided
                if data.get('follow_up_required') == 'on' and data.get('follow_up_date'):
                    follow_up_date_str = data.get('follow_up_date')
                    follow_up_time_str = data.get('follow_up_time', '09:00')
                    from datetime import datetime
                    try:
                        follow_up_datetime = datetime.strptime(
                            f"{follow_up_date_str} {follow_up_time_str}",
                            "%Y-%m-%d %H:%M"
                        )
                        call_report.follow_up_date = timezone.make_aware(follow_up_datetime)
                    except:
                        call_report.follow_up_date = None
                else:
                    call_report.follow_up_date = None
                
                call_report.call_type = data.get('call_type', call_report.call_type)
                call_report.call_duration_minutes = int(data.get('call_duration_minutes', 0) or 0)
                call_report.contact_name = data.get('contact_name', '').strip()
                call_report.contact_phone = data.get('contact_phone', '').strip()
                call_report.contact_email = data.get('contact_email', '').strip()
                call_report.company_name = data.get('company_name', '').strip()
                call_report.contact_title = data.get('contact_title', '').strip()
                call_report.call_outcome = data.get('call_outcome', call_report.call_outcome)
                call_report.call_summary = data.get('call_summary', '').strip()
                call_report.key_points = data.get('key_points', '').strip()
                call_report.objections_raised = data.get('objections_raised', '').strip()
                call_report.next_steps = data.get('next_steps', '').strip()
                call_report.follow_up_required = data.get('follow_up_required') == 'on'
                call_report.follow_up_notes = data.get('follow_up_notes', '').strip()
                call_report.priority = data.get('priority', call_report.priority)
                call_report.potential_value = Decimal(data.get('potential_value', 0) or 0) if data.get('potential_value') else None
                call_report.actual_value = Decimal(data.get('actual_value', 0) or 0) if data.get('actual_value') else None
                call_report.service_interest = data.get('service_interest', '').strip()
                call_report.relationship_stage = data.get('relationship_stage', call_report.relationship_stage)
                call_report.campaign_id = data.get('campaign') if data.get('campaign') else None
                call_report.objective_id = data.get('objective') if data.get('objective') else None
                call_report.partnership_id = data.get('partnership') if data.get('partnership') else None
                call_report.assigned_to_id = data.get('assigned_to') if data.get('assigned_to') else None
                call_report.internal_notes = data.get('internal_notes', '').strip()
                call_report.tags = data.get('tags', '').strip()
                
                call_report.save()
                
                messages.success(request, 'Call report updated successfully!')
                return redirect('hospital:call_report_detail', report_id=call_report.id)
        except Exception as e:
            logger.error(f"Error updating call report: {e}")
            messages.error(request, f'Error updating call report: {str(e)}')
    
    # GET request - show form
    from django.contrib.auth.models import User
    staff_users = User.objects.filter(
        is_staff=True,
        is_active=True
    ).select_related('staff').order_by('first_name', 'last_name', 'username')
    
    campaigns = MarketingCampaign.objects.filter(status__in=['active', 'scheduled']).order_by('title')
    objectives = MarketingObjective.objects.filter(status__in=['planning', 'active']).order_by('title')
    partnerships = CorporatePartnership.objects.filter(status__in=['prospect', 'negotiating', 'active']).order_by('company_name')
    
    context = {
        'title': f'Edit Call Report: {call_report.contact_name}',
        'call_report': call_report,
        'staff_users': staff_users,
        'campaigns': campaigns,
        'objectives': objectives,
        'partnerships': partnerships,
    }
    
    return render(request, 'hospital/marketing/edit_call_report.html', context)


@login_required
@marketing_access_required
@require_http_methods(["POST"])
def delete_call_report(request, report_id):
    """Delete a call report (soft delete)"""
    call_report = get_object_or_404(CallReport, id=report_id)
    call_report.is_deleted = True
    call_report.save()
    messages.success(request, 'Call report deleted successfully!')
    return redirect('hospital:call_reports_list')






