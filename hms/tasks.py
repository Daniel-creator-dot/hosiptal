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
def cleanup_old_sessions():
    """Clean up old sessions"""
    try:
        # Delete sessions older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = Session.objects.filter(expire_date__lt=cutoff_date).delete()[0]
        logger.info(f"Cleaned up {deleted_count} old sessions")
        return f"Cleaned up {deleted_count} old sessions"
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