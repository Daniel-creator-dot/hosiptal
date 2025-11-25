"""
Queue Management Service
Intelligent patient queue and ticketing system
"""
import logging
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg, F
from django.db import transaction as db_transaction
from decimal import Decimal

logger = logging.getLogger(__name__)


class QueueService:
    """
    Core service for managing patient queues
    Handles queue number generation, position tracking, and workflow
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_queue_number(self, department, priority=3):
        """
        Generate next queue number for department
        
        Args:
            department: Department object
            priority: Priority level (1=Emergency, 3=Normal)
        
        Returns:
            tuple: (queue_number, sequence_number)
        """
        from hospital.models_queue import QueueEntry, QueueConfiguration
        
        try:
            today = timezone.now().date()
            
            # Get department prefix
            try:
                config = QueueConfiguration.objects.get(department=department)
                prefix = config.queue_prefix
            except QueueConfiguration.DoesNotExist:
                prefix = self._get_default_prefix(department)
            
            # Get next sequence number for today
            last_queue = QueueEntry.objects.filter(
                queue_date=today,
                department=department,
                is_deleted=False
            ).order_by('-sequence_number').first()
            
            sequence = (last_queue.sequence_number + 1) if last_queue else 1
            
            # Format queue number
            queue_number = f"{prefix}-{sequence:03d}"  # e.g., OPD-001
            
            self.logger.info(f"Generated queue number: {queue_number} (sequence: {sequence})")
            
            return queue_number, sequence
            
        except Exception as e:
            self.logger.error(f"Error generating queue number: {str(e)}", exc_info=True)
            # Fallback: use timestamp-based number
            import random
            fallback = f"Q-{int(timezone.now().timestamp())}{random.randint(10,99)}"
            return fallback, 1
    
    def create_queue_entry(self, patient, encounter, department, assigned_doctor=None, 
                          priority=3, notes=''):
        """
        Create a new queue entry for a patient
        
        Args:
            patient: Patient object
            encounter: Encounter object
            department: Department object
            assigned_doctor: Doctor user object (optional)
            priority: Priority level (1-4)
            notes: Additional notes
        
        Returns:
            QueueEntry object
        """
        from hospital.models_queue import QueueEntry
        
        from django.db import IntegrityError

        last_error = None
        for attempt in range(5):
            try:
                with db_transaction.atomic():
                    queue_number, sequence = self.generate_queue_number(department, priority=priority)
                    position = self.get_current_queue_length(department) + 1
                    estimated_wait = self.calculate_estimated_wait(department, position)

                    queue_entry = QueueEntry.objects.create(
                        queue_number=queue_number,
                        sequence_number=sequence,
                        patient=patient,
                        encounter=encounter,
                        department=department,
                        assigned_doctor=assigned_doctor,
                        priority=priority,
                        status='checked_in',
                        estimated_wait_minutes=estimated_wait,
                        notes=notes
                    )

                    self.logger.info(
                        f"✅ Queue entry created: {queue_number} for {patient.full_name} "
                        f"(Position: {position}, Est. wait: {estimated_wait} mins)"
                    )
                    return queue_entry
            except IntegrityError as ie:
                last_error = ie
                self.logger.warning(
                    "Queue number collision when creating entry for %s (attempt %s)",
                    patient.id,
                    attempt + 1,
                    exc_info=True
                )
                continue
            except Exception as e:
                self.logger.error(f"Error creating queue entry: {str(e)}", exc_info=True)
                raise

        self.logger.error("Unable to allocate unique queue number after multiple attempts.")
        raise IntegrityError("Unable to generate unique queue number") from last_error
    
    def calculate_estimated_wait(self, department, position_in_queue):
        """
        Calculate estimated wait time based on position and department settings
        
        Args:
            department: Department object
            position_in_queue: Position in queue (1-based)
        
        Returns:
            int: Estimated wait time in minutes
        """
        from hospital.models_queue import QueueConfiguration
        
        try:
            config = QueueConfiguration.objects.get(department=department)
            time_per_patient = config.average_consultation_minutes + config.buffer_time_minutes
        except QueueConfiguration.DoesNotExist:
            # Default: 15 min consultation + 5 min buffer = 20 min per patient
            time_per_patient = 20
        
        # Account for position (position 1 = next up = minimal wait)
        estimated_minutes = time_per_patient * max(0, position_in_queue - 1)
        
        return estimated_minutes
    
    def get_position_in_queue(self, queue_entry):
        """
        Get current position in queue for a specific entry
        Considers priority and check-in time
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            int: Current position (1-based)
        """
        from hospital.models_queue import QueueEntry
        
        # Count entries ahead of this one
        ahead_count = QueueEntry.objects.filter(
            queue_date=queue_entry.queue_date,
            department=queue_entry.department,
            status__in=['checked_in', 'called'],
            is_deleted=False
        ).filter(
            Q(priority__lt=queue_entry.priority) |  # Higher priority
            Q(
                priority=queue_entry.priority,
                sequence_number__lt=queue_entry.sequence_number  # Same priority, earlier check-in
            )
        ).count()
        
        return ahead_count + 1
    
    def get_current_queue_length(self, department, status='checked_in'):
        """
        Get current number of patients in queue
        
        Args:
            department: Department object
            status: Queue status (default: checked_in)
        
        Returns:
            int: Number of patients in queue
        """
        from hospital.models_queue import QueueEntry
        
        today = timezone.now().date()
        
        return QueueEntry.objects.filter(
            queue_date=today,
            department=department,
            status=status,
            is_deleted=False
        ).count()
    
    def get_next_patient(self, department, doctor=None):
        """
        Get next patient in queue considering priority
        
        Args:
            department: Department object
            doctor: Filter by assigned doctor (optional)
        
        Returns:
            QueueEntry object or None
        """
        from hospital.models_queue import QueueEntry
        
        today = timezone.now().date()
        
        queryset = QueueEntry.objects.filter(
            queue_date=today,
            department=department,
            status='checked_in',
            is_deleted=False
        ).order_by('priority', 'sequence_number')
        
        if doctor:
            queryset = queryset.filter(assigned_doctor=doctor)
        
        return queryset.first()
    
    def call_next_patient(self, queue_entry, room_number=''):
        """
        Mark patient as called and send notification
        
        Args:
            queue_entry: QueueEntry object
            room_number: Consultation room assignment
        
        Returns:
            QueueEntry object (updated)
        """
        try:
            queue_entry.status = 'called'
            queue_entry.called_time = timezone.now()
            if room_number:
                queue_entry.room_number = room_number
            queue_entry.save()
            
            self.logger.info(f"📢 Called patient: {queue_entry.queue_number}")
            
            # Send ready notification
            from .queue_notification_service import queue_notification_service
            queue_notification_service.send_ready_notification(queue_entry)
            
            return queue_entry
            
        except Exception as e:
            self.logger.error(f"Error calling patient: {str(e)}", exc_info=True)
            raise
    
    def start_consultation(self, queue_entry):
        """
        Mark consultation as started
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            QueueEntry object (updated)
        """
        try:
            queue_entry.status = 'in_progress'
            queue_entry.started_time = timezone.now()
            
            # Calculate actual wait time
            if queue_entry.check_in_time:
                wait_seconds = (queue_entry.started_time - queue_entry.check_in_time).total_seconds()
                queue_entry.actual_wait_minutes = int(wait_seconds / 60)
            
            queue_entry.save()
            
            self.logger.info(
                f"👨‍⚕️ Consultation started: {queue_entry.queue_number} "
                f"(Wait time: {queue_entry.actual_wait_minutes} mins)"
            )
            
            return queue_entry
            
        except Exception as e:
            self.logger.error(f"Error starting consultation: {str(e)}", exc_info=True)
            raise
    
    def complete_consultation(self, queue_entry):
        """
        Mark consultation as completed
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            QueueEntry object (updated)
        """
        try:
            queue_entry.status = 'completed'
            queue_entry.completed_time = timezone.now()
            
            # Calculate consultation duration
            if queue_entry.started_time:
                duration_seconds = (queue_entry.completed_time - queue_entry.started_time).total_seconds()
                queue_entry.consultation_duration_minutes = int(duration_seconds / 60)
            
            queue_entry.save()
            
            self.logger.info(
                f"✓ Consultation completed: {queue_entry.queue_number} "
                f"(Duration: {queue_entry.consultation_duration_minutes} mins)"
            )
            
            # Send completion notification
            from .queue_notification_service import queue_notification_service
            queue_notification_service.send_completion_notification(queue_entry)
            
            return queue_entry
            
        except Exception as e:
            self.logger.error(f"Error completing consultation: {str(e)}", exc_info=True)
            raise
    
    def mark_no_show(self, queue_entry):
        """
        Mark patient as no-show
        
        Args:
            queue_entry: QueueEntry object
        
        Returns:
            QueueEntry object (updated)
        """
        try:
            queue_entry.status = 'no_show'
            queue_entry.no_show = True
            queue_entry.save()
            
            self.logger.warning(f"❌ Patient no-show: {queue_entry.queue_number}")
            
            # Send no-show warning
            from .queue_notification_service import queue_notification_service
            queue_notification_service.send_no_show_warning(queue_entry)
            
            return queue_entry
            
        except Exception as e:
            self.logger.error(f"Error marking no-show: {str(e)}", exc_info=True)
            raise
    
    def get_queue_summary(self, department, date_filter=None):
        """
        Get comprehensive queue summary for a department
        
        Args:
            department: Department object
            date_filter: Date to filter (default: today)
        
        Returns:
            dict: Queue statistics
        """
        from hospital.models_queue import QueueEntry
        
        if not date_filter:
            date_filter = timezone.now().date()
        
        queryset = QueueEntry.objects.filter(
            queue_date=date_filter,
            department=department,
            is_deleted=False
        )
        
        stats = {
            'total': queryset.count(),
            'waiting': queryset.filter(status='checked_in').count(),
            'called': queryset.filter(status='called').count(),
            'in_progress': queryset.filter(status='in_progress').count(),
            'completed': queryset.filter(status='completed').count(),
            'no_show': queryset.filter(status='no_show').count(),
            'cancelled': queryset.filter(status='cancelled').count(),
        }
        
        # Calculate averages
        completed_entries = queryset.filter(status='completed')
        if completed_entries.exists():
            stats['avg_wait_time'] = completed_entries.aggregate(
                avg=Avg('actual_wait_minutes')
            )['avg'] or 0
            
            stats['avg_consultation_time'] = completed_entries.aggregate(
                avg=Avg('consultation_duration_minutes')
            )['avg'] or 0
        else:
            stats['avg_wait_time'] = 0
            stats['avg_consultation_time'] = 0
        
        return stats
    
    def get_doctor_queue(self, doctor, date_filter=None):
        """
        Get queue for a specific doctor
        
        Args:
            doctor: Doctor user object
            date_filter: Date to filter (default: today)
        
        Returns:
            QuerySet: QueueEntry objects
        """
        from hospital.models_queue import QueueEntry
        
        if not date_filter:
            date_filter = timezone.now().date()
        
        return QueueEntry.objects.filter(
            queue_date=date_filter,
            assigned_doctor=doctor,
            is_deleted=False
        ).order_by('priority', 'sequence_number')
    
    def _get_default_prefix(self, department):
        """Get default queue prefix based on department name"""
        dept_name = department.name.upper()
        
        if 'EMERGENCY' in dept_name or 'EMG' in dept_name:
            return 'EMG'
        elif 'OUTPATIENT' in dept_name or 'OPD' in dept_name:
            return 'OPD'
        elif 'INPATIENT' in dept_name or 'IPD' in dept_name:
            return 'IPD'
        elif 'SPECIALIST' in dept_name or 'SPL' in dept_name:
            return 'SPL'
        else:
            # Use first 3 letters of department name
            return dept_name[:3]


# Global instance
queue_service = QueueService()


















