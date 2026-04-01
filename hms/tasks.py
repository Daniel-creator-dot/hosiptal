from celery import shared_task
from django.core.management import call_command
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task
def health_check_task():
    """Periodic health check task"""
    try:
        logger.info("Health check task executed successfully")
        return "Health check completed"
    except Exception as e:
        logger.error(f"Health check task failed: {e}")
        raise

@shared_task
def cleanup_expired_sessions_realtime():
    """Real-time cleanup of expired sessions (runs every 5 minutes)"""
    try:
        from django.contrib.sessions.models import Session
        from hospital.models import UserSession
        
        # Close UserSession records for expired Django sessions (real-time cleanup)
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        expired_session_keys = list(expired_sessions.values_list('session_key', flat=True))
        
        closed_count = 0
        if expired_session_keys:
            # Close UserSession records for expired sessions
            closed_count = UserSession.objects.filter(
                session_key__in=expired_session_keys,
                is_active=True,
                logout_time__isnull=True
            ).update(
                is_active=False,
                logout_time=timezone.now()
            )
            if closed_count > 0:
                logger.info(f"[REALTIME] Closed {closed_count} expired UserSession records")
        
        # Close orphaned UserSession records (no corresponding Django session)
        all_active_user_sessions = UserSession.objects.filter(
            is_active=True,
            logout_time__isnull=True
        ).select_related('user')[:100]  # Limit to prevent performance issues
        
        orphaned_count = 0
        for user_session in all_active_user_sessions:
            # Check if Django session still exists
            try:
                Session.objects.get(session_key=user_session.session_key)
            except Session.DoesNotExist:
                # Django session doesn't exist, close UserSession
                user_session.end()
                orphaned_count += 1
        
        if orphaned_count > 0:
            logger.info(f"[REALTIME] Closed {orphaned_count} orphaned UserSession records")
        
        total = closed_count + orphaned_count
        if total > 0:
            return f"Closed {total} expired/orphaned sessions ({closed_count} expired, {orphaned_count} orphaned)"
        return "No expired sessions to clean"
    except Exception as e:
        logger.error(f"Real-time session cleanup task failed: {e}")
        raise

@shared_task
def cleanup_old_sessions():
    """Clean up old sessions and close expired UserSession records (real-time cleanup)"""
    try:
        from django.contrib.sessions.models import Session
        from hospital.models import UserSession
        
        # Delete expired Django sessions (older than 30 days)
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = Session.objects.filter(expire_date__lt=cutoff_date).delete()[0]
        logger.info(f"Cleaned up {deleted_count} old Django sessions")
        
        # Close UserSession records for expired Django sessions (real-time cleanup)
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        expired_session_keys = list(expired_sessions.values_list('session_key', flat=True))
        
        closed_count = 0
        if expired_session_keys:
            # Close UserSession records for expired sessions
            closed_count = UserSession.objects.filter(
                session_key__in=expired_session_keys,
                is_active=True,
                logout_time__isnull=True
            ).update(
                is_active=False,
                logout_time=timezone.now()
            )
            if closed_count > 0:
                logger.info(f"Closed {closed_count} expired UserSession records (real-time cleanup)")
        
        # Also close UserSession records that don't have a corresponding Django session (orphaned)
        all_active_user_sessions = UserSession.objects.filter(
            is_active=True,
            logout_time__isnull=True
        )
        orphaned_count = 0
        for user_session in all_active_user_sessions:
            # Check if Django session still exists
            try:
                Session.objects.get(session_key=user_session.session_key)
            except Session.DoesNotExist:
                # Django session doesn't exist, close UserSession
                user_session.end()
                orphaned_count += 1
        
        if orphaned_count > 0:
            logger.info(f"Closed {orphaned_count} orphaned UserSession records (no Django session)")
        
        # Safety net: Close sessions older than 24 hours (should have been caught by timeout)
        old_cutoff = timezone.now() - timedelta(hours=24)
        very_old_sessions = UserSession.objects.filter(
            is_active=True,
            logout_time__isnull=True,
            login_time__lt=old_cutoff
        )
        very_old_count = very_old_sessions.update(
            is_active=False,
            logout_time=timezone.now()
        )
        if very_old_count > 0:
            logger.info(f"Closed {very_old_count} very old UserSession records (safety cleanup - >24h)")
        
        total_closed = closed_count + orphaned_count + very_old_count
        return f"Cleaned up {deleted_count} Django sessions, closed {total_closed} UserSessions ({closed_count} expired, {orphaned_count} orphaned, {very_old_count} old)"
    except Exception as e:
        logger.error(f"Session cleanup task failed: {e}")
        raise

@shared_task
def send_email_task(subject, message, recipient_list):
    """Send email asynchronously"""
    from django.core.mail import send_mail
    try:
        send_mail(subject, message, None, recipient_list)
        logger.info(f"Email sent successfully to {recipient_list}")
        return "Email sent successfully"
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        raise

@shared_task
def generate_report_task(report_type, user_id):
    """Generate reports asynchronously"""
    try:
        # This is a placeholder for report generation
        logger.info(f"Generating {report_type} report for user {user_id}")
        # Add your report generation logic here
        return f"Report {report_type} generated successfully"
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise


@shared_task
def send_birthday_wishes():
    """Send birthday wishes to staff with birthdays today"""
    from hospital.models import Staff
    from hospital.services.sms_service import sms_service
    
    try:
        # Get staff with birthdays today
        birthday_staff = Staff.get_birthdays_today()
        
        sent_count = 0
        failed_count = 0
        
        for staff in birthday_staff:
            try:
                # Send birthday wish to staff
                result = sms_service.send_birthday_wish(staff)
                
                if result.status == 'sent':
                    sent_count += 1
                else:
                    failed_count += 1
                
                # Also notify department head
                sms_service.send_birthday_reminder_to_department(staff)
                
            except Exception as e:
                logger.error(f"Failed to send birthday wish to {staff.user.get_full_name()}: {e}")
                failed_count += 1
        
        logger.info(f"Birthday wishes sent: {sent_count} successful, {failed_count} failed")
        return f"Sent {sent_count} birthday wishes, {failed_count} failed"
        
    except Exception as e:
        logger.error(f"Birthday wishes task failed: {e}")
        raise


@shared_task
def upcoming_birthday_reminders():
    """Send reminder about upcoming birthdays (tomorrow)"""
    from hospital.models import Staff
    from hospital.services.sms_service import sms_service
    
    try:
        # Get staff with birthdays in next 1 day (tomorrow)
        upcoming = Staff.get_upcoming_birthdays(days=1)
        
        # Notify HR or management about tomorrow's birthdays
        if upcoming:
            # Could send to HR email or create notification
            logger.info(f"Upcoming birthdays tomorrow: {len(upcoming)} staff members")
            
            # Send to department heads
            for staff in upcoming:
                try:
                    sms_service.send_birthday_reminder_to_department(staff)
                except Exception as e:
                    logger.error(f"Failed to send birthday reminder for {staff.user.get_full_name()}: {e}")
        
        return f"Processed {len(upcoming)} upcoming birthday reminders"
        
    except Exception as e:
        logger.error(f"Upcoming birthday reminders task failed: {e}")
        raise


@shared_task
def automated_database_backup():
    """Automated daily database backup"""
    try:
        logger.info("Starting automated database backup...")
        call_command('backup_database', '--output-dir=backups/automated')
        logger.info("Automated database backup completed successfully")
        return "Database backup completed"
    except Exception as e:
        logger.error(f"Automated database backup failed: {e}")
        raise


@shared_task
def verify_database_integrity():
    """Verify database integrity periodically"""
    try:
        logger.info("Running database integrity check...")
        call_command('verify_database')
        logger.info("Database integrity check completed")
        return "Database integrity verified"
    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        raise


@shared_task(ignore_result=True)
def persist_audit_activity_log(
    user_id,
    activity_type,
    description,
    ip_address=None,
    user_agent=None,
    session_key=None,
    metadata=None,
):
    """Write ActivityLog in the background so request threads are not blocked on INSERT."""
    from django.contrib.auth import get_user_model
    from hospital.models_audit import ActivityLog

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('persist_audit_activity_log: user_id=%s not found', user_id)
        return
    ActivityLog.log_activity(
        user=user,
        activity_type=activity_type,
        description=(description or '')[:255],
        ip_address=ip_address,
        user_agent=user_agent or '',
        session_key=session_key or '',
        metadata=metadata or {},
    )


@shared_task
def refresh_staff_performance_snapshot(staff_id):
    """Recompute StaffPerformanceSnapshot off the request thread (consultation prescribe / lab order)."""
    if not staff_id:
        return
    try:
        from hospital.models import Staff
        from hospital.services.performance_analytics import performance_analytics_service

        if not performance_analytics_service:
            return
        staff = Staff.objects.filter(pk=staff_id, is_deleted=False).first()
        if staff:
            performance_analytics_service.generate_snapshot(staff)
    except Exception as e:
        logger.warning('refresh_staff_performance_snapshot failed for %s: %s', staff_id, e)