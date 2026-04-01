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
from django.conf import settings

logger = logging.getLogger(__name__)

# Prefixes that read badly on SMS / displays (e.g. first 3 letters of "Accounts" → ACC)
_BLOCKED_QUEUE_PREFIXES = frozenset({'ACC', 'XXX', 'ASS'})


class QueueService:
    """
    Core service for managing patient queues
    Handles queue number generation, position tracking, and workflow
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_queue_number(self, department, priority=3):
        """
        Generate next queue number for department with race condition protection
        
        Args:
            department: Department object
            priority: Priority level (1=Emergency, 3=Normal)
        
        Returns:
            tuple: (queue_number, sequence_number)
        """
        from hospital.models_queue import QueueEntry, QueueConfiguration
        from django.db import transaction
        import random
        
        try:
            today = timezone.now().date()
            
            prefix = self._resolve_prefix_for_department(department)

            # Use select_for_update to prevent race conditions
            # Lock the last queue entry to ensure atomic sequence generation
            with transaction.atomic():
                # Get the maximum sequence number for today with lock
                last_queue = QueueEntry.objects.filter(
                    queue_date=today,
                    department=department,
                    is_deleted=False
                ).select_for_update().order_by('-sequence_number', '-id').first()
                
                sequence = (last_queue.sequence_number + 1) if last_queue else 1
                
                # Generate base queue number
                base_queue_number = f"{prefix}-{sequence:03d}"  # e.g., OPD-001
                queue_number = base_queue_number
                
                # Check if this queue number already exists (with lock to prevent race conditions)
                # Use select_for_update to lock existing entries during check
                max_attempts = 50  # Reasonable limit
                attempt = 0
                
                # Lock and check for existing queue number
                while attempt < max_attempts:
                    # Use select_for_update to lock any existing entry with this queue_number
                    existing = QueueEntry.objects.filter(
                        queue_number=queue_number, 
                        is_deleted=False
                    ).select_for_update().first()
                    
                    if not existing:
                        # Queue number is available, break out of loop
                        break
                    
                    attempt += 1
                    if attempt <= 20:
                        # Try incrementing sequence first (most common case)
                        sequence += 1
                        queue_number = f"{prefix}-{sequence:03d}"
                    elif attempt <= 40:
                        # Add microsecond-based suffix
                        import time
                        microsecond_suffix = int(time.time() * 1000000) % 10000  # Last 4 digits
                        queue_number = f"{prefix}-{sequence:03d}-{microsecond_suffix}"
                    else:
                        # Last resort: use timestamp + random for guaranteed uniqueness
                        timestamp = int(timezone.now().timestamp() * 1000000) % 1000000
                        random_suffix = random.randint(1000, 9999)
                        queue_number = f"{prefix}-{timestamp}{random_suffix}"
                        self.logger.warning(
                            f"Queue number collision after {attempt} attempts, using timestamp-based: {queue_number}"
                        )
                        break
                
                if attempt >= max_attempts:
                    # Absolute last resort: use UUID-like suffix
                    import uuid
                    uuid_suffix = str(uuid.uuid4())[:8].replace('-', '').upper()
                    queue_number = f"{prefix}-{uuid_suffix}"
                    self.logger.error(f"Exhausted queue number generation attempts, using UUID suffix: {queue_number}")
                
                self.logger.info(f"Generated queue number: {queue_number} (sequence: {sequence}, attempts: {attempt})")
                
                return queue_number, sequence
            
        except Exception as e:
            self.logger.error(f"Error generating queue number: {str(e)}", exc_info=True)
            # Fallback: use timestamp-based number with random suffix
            import random
            timestamp = int(timezone.now().timestamp() * 1000) % 1000000  # Last 6 digits
            random_suffix = random.randint(100, 999)
            fallback = f"Q-{timestamp}{random_suffix}"
            return fallback, 1
    
    def create_queue_entry(self, patient, encounter, department, assigned_doctor=None, 
                          priority=3, notes='', room_number='', consulting_room=None):
        """
        Create a new queue entry for a patient
        
        Args:
            patient: Patient object
            encounter: Encounter object
            department: Department object
            assigned_doctor: Doctor user object (optional)
            priority: Priority level (1-4)
            notes: Additional notes
            room_number: Room number string (optional)
            consulting_room: ConsultingRoom object (optional) - if provided, extracts room_number
        
        Returns:
            QueueEntry object
        """
        from hospital.models_queue import QueueEntry
        
        from django.db import IntegrityError

        # Extract room number from consulting_room if provided
        if consulting_room and not room_number:
            room_number = consulting_room.room_number if hasattr(consulting_room, 'room_number') else ''
        
        # If assigned_doctor has a room assignment, use that room
        if assigned_doctor and not room_number:
            try:
                from hospital.models_consulting_rooms import DoctorRoomAssignment
                today = timezone.now().date()
                assignment = DoctorRoomAssignment.objects.filter(
                    doctor=assigned_doctor,
                    assignment_date=today,
                    is_active=True,
                    is_deleted=False
                ).select_related('room').first()
                if assignment and assignment.room:
                    room_number = assignment.room.room_number
            except Exception:
                pass

        last_error = None
        max_retries = 30  # Increased retries for better collision handling
        
        for attempt in range(max_retries):
            try:
                with db_transaction.atomic():
                    # Check if queue entry already exists for this patient/encounter today
                    today = timezone.now().date()
                    existing_entry = QueueEntry.objects.filter(
                        patient=patient,
                        encounter=encounter,
                        queue_date=today,
                        is_deleted=False
                    ).select_for_update().first()
                    
                    if existing_entry:
                        self.logger.info(
                            f"Queue entry already exists for patient {patient.mrn}: {existing_entry.queue_number}"
                        )
                        return existing_entry
                    
                    # Guard against ticket churn: if the same patient already has an active
                    # queue entry today (possibly from a different encounter path), reuse it.
                    patient_active_entry = QueueEntry.objects.filter(
                        patient=patient,
                        queue_date=today,
                        status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
                        is_deleted=False,
                    ).select_for_update().order_by('-check_in_time', '-created').first()
                    if patient_active_entry:
                        # If data already has multiple active rows for this patient today,
                        # keep the earliest ticket and retire the rest to stop ticket flipping.
                        active_qs = QueueEntry.objects.filter(
                            patient=patient,
                            queue_date=today,
                            status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
                            is_deleted=False,
                        ).order_by('sequence_number', 'check_in_time', 'created')
                        canonical_entry = active_qs.first()
                        if canonical_entry and canonical_entry.id != patient_active_entry.id:
                            patient_active_entry = canonical_entry
                        duplicate_ids = list(
                            active_qs.exclude(pk=patient_active_entry.pk).values_list('pk', flat=True)
                        )
                        if duplicate_ids:
                            QueueEntry.objects.filter(pk__in=duplicate_ids).update(status='cancelled')

                        fields_to_update = []
                        if encounter and patient_active_entry.encounter_id != getattr(encounter, 'id', None):
                            patient_active_entry.encounter = encounter
                            fields_to_update.append('encounter')
                        if department and patient_active_entry.department_id != getattr(department, 'id', None):
                            patient_active_entry.department = department
                            fields_to_update.append('department')
                        if assigned_doctor and patient_active_entry.assigned_doctor_id != getattr(assigned_doctor, 'id', None):
                            patient_active_entry.assigned_doctor = assigned_doctor
                            fields_to_update.append('assigned_doctor')
                        if room_number and patient_active_entry.room_number != room_number:
                            patient_active_entry.room_number = room_number
                            fields_to_update.append('room_number')
                        if fields_to_update:
                            patient_active_entry.save(update_fields=fields_to_update + ['modified'])
                        self.logger.info(
                            "Reusing active queue entry for patient %s to keep stable ticket: %s",
                            patient.mrn,
                            patient_active_entry.queue_number,
                        )
                        return patient_active_entry
                    
                    # Generate queue number WITHIN the transaction
                    # This ensures atomicity between generation and creation
                    queue_number, sequence = self._generate_queue_number_atomic(
                        department, priority=priority, attempt=attempt
                    )
                    
                    # Final check with lock - if it exists, we'll get IntegrityError and retry
                    # This check is redundant but provides extra safety
                    if QueueEntry.objects.filter(queue_number=queue_number, is_deleted=False).select_for_update().exists():
                        # This should rarely happen due to atomic generation, but if it does, retry
                        self.logger.warning(
                            f"Queue number {queue_number} exists after generation, will retry (attempt {attempt + 1})"
                        )
                        raise IntegrityError(f"Queue number {queue_number} collision detected")
                    
                    position = self.get_current_queue_length(department) + 1
                    estimated_wait = self.calculate_estimated_wait(department, position)

                    # Create the queue entry
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
                        notes=notes,
                        room_number=room_number
                    )

                    self.logger.info(
                        f"✅ Queue entry created: {queue_number} for {patient.full_name} "
                        f"(Position: {position}, Est. wait: {estimated_wait} mins)"
                    )
                    return queue_entry
                    
            except IntegrityError as ie:
                last_error = ie
                error_str = str(ie)
                
                # Check if it's a queue_number collision
                if 'queue_number' in error_str.lower() or 'unique' in error_str.lower() or 'duplicate' in error_str.lower():
                    self.logger.warning(
                        f"Queue number collision for patient {patient.id} (attempt {attempt + 1}/{max_retries})"
                    )
                    # Wait a small random amount before retry to reduce collision probability
                    import time
                    import random
                    time.sleep(random.uniform(0.05, 0.15))  # Longer wait to reduce collisions
                    # Will retry with new queue number on next iteration
                    continue
                else:
                    # Different integrity error (e.g., patient/encounter constraint)
                    self.logger.error(f"Integrity error (not queue_number): {error_str}", exc_info=True)
                    raise
            except Exception as e:
                self.logger.error(f"Error creating queue entry: {str(e)}", exc_info=True)
                raise

        self.logger.error(
            f"Unable to allocate unique queue number after {max_retries} attempts for patient {patient.id}"
        )
        raise IntegrityError("Unable to generate unique queue number") from last_error
    
    def _generate_queue_number_atomic(self, department, priority=3, attempt=0):
        """
        Generate queue number atomically within a transaction
        This is called from within create_queue_entry's transaction
        """
        from hospital.models_queue import QueueEntry, QueueConfiguration
        import random
        import time
        
        today = timezone.now().date()
        
        prefix = self._resolve_prefix_for_department(department)

        # Get the maximum sequence number for today with lock
        last_queue = QueueEntry.objects.filter(
            queue_date=today,
            department=department,
            is_deleted=False
        ).select_for_update().order_by('-sequence_number', '-id').first()
        
        base_sequence = (last_queue.sequence_number + 1) if last_queue else 1
        
        # Adjust sequence based on attempt number to reduce collisions
        sequence = base_sequence + attempt
        
        # Generate base queue number
        queue_number = f"{prefix}-{sequence:03d}"
        
        # If this is a retry attempt, add suffix to ensure uniqueness
        if attempt > 0:
            # Add microsecond-based suffix for retries
            microsecond_suffix = int(time.time() * 1000000) % 100000  # Last 5 digits
            random_suffix = random.randint(100, 999)
            queue_number = f"{prefix}-{sequence:03d}-{microsecond_suffix}{random_suffix}"
        
        # Final check with lock - if exists, add more randomness
        if QueueEntry.objects.filter(queue_number=queue_number, is_deleted=False).select_for_update().exists():
            # Add UUID suffix as absolute guarantee
            import uuid
            uuid_suffix = str(uuid.uuid4())[:8].replace('-', '').upper()
            queue_number = f"{prefix}-{uuid_suffix}"
            self.logger.warning(f"Queue number collision, using UUID suffix: {queue_number}")
        
        self.logger.info(f"Generated queue number: {queue_number} (sequence: {sequence}, attempt: {attempt})")
        
        return queue_number, sequence
    
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
            status__in=['checked_in', 'called', 'vitals_completed'],
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
    
    def call_next_patient(self, queue_entry, room_number='', doctor=None):
        """
        Mark patient as called and send notification
        
        Args:
            queue_entry: QueueEntry object
            room_number: Consultation room assignment (optional, auto-detected if not provided)
            doctor: Doctor user object (optional, for auto-detecting room)
        
        Returns:
            QueueEntry object (updated)
        """
        try:
            # Auto-detect room if not provided but doctor is
            if not room_number and doctor:
                try:
                    from hospital.models_consulting_rooms import DoctorRoomAssignment
                    today = timezone.now().date()
                    assignment = DoctorRoomAssignment.objects.filter(
                        doctor=doctor,
                        assignment_date=today,
                        is_active=True,
                        is_deleted=False
                    ).select_related('room').first()
                    if assignment and assignment.room:
                        room_number = assignment.room.room_number
                except Exception as e:
                    self.logger.warning(f"Could not auto-detect room for doctor: {str(e)}")
            
            # Use existing room_number from queue_entry if not provided
            if not room_number:
                room_number = queue_entry.room_number or ''
            
            queue_entry.status = 'called'
            queue_entry.called_time = timezone.now()
            if room_number:
                queue_entry.room_number = room_number
            # Who called is who patients should see on the board / hear in callouts
            if doctor:
                queue_entry.assigned_doctor = doctor
            queue_entry.save()
            
            self.logger.info(f"📢 Called patient: {queue_entry.queue_number} (Room: {room_number or 'N/A'})")
            
            # Send ready notification with room and doctor info
            try:
                from .queue_notification_service import queue_notification_service
                sms_sent = queue_notification_service.send_ready_notification(queue_entry)
                if sms_sent:
                    self.logger.info(f"✅ SMS notification sent successfully to patient {queue_entry.patient.full_name}")
                else:
                    self.logger.warning(
                        f"⚠️ SMS notification failed for patient {queue_entry.patient.full_name} "
                        f"(Queue: {queue_entry.queue_number}). "
                        f"Phone: {getattr(queue_entry.patient, 'phone_number', 'Not set')}"
                    )
            except Exception as sms_error:
                self.logger.error(
                    f"❌ Error sending SMS notification for queue {queue_entry.queue_number}: {str(sms_error)}",
                    exc_info=True
                )
                # Don't fail the queue action if SMS fails
            
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
            # Ensure in-progress entries have a call marker used by live display ordering.
            if not getattr(queue_entry, 'called_time', None):
                queue_entry.called_time = queue_entry.started_time
            
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
        dept_name = (department.name or '').upper().replace(' ', '')
        
        if 'EMERGENCY' in dept_name or 'EMG' in dept_name:
            return 'EMG'
        elif 'OUTPATIENT' in dept_name or 'OPD' in dept_name:
            return 'OPD'
        elif 'INPATIENT' in dept_name or 'IPD' in dept_name:
            return 'IPD'
        elif 'SPECIALIST' in dept_name or 'SPL' in dept_name:
            return 'SPL'
        elif 'PEDIATRIC' in dept_name or 'PEDS' in dept_name:
            return 'PED'
        else:
            base = dept_name[:3]
            if base in _BLOCKED_QUEUE_PREFIXES:
                code = (getattr(department, 'code', None) or '').strip().upper()
                code = ''.join(c for c in code if c.isalnum())[:5]
                if code and code not in _BLOCKED_QUEUE_PREFIXES:
                    return code
                return (getattr(settings, 'QUEUE_TICKET_PREFIX_FALLBACK', None) or 'VIS').strip().upper()[:5]
            return base[:5]

    def _normalize_ticket_prefix(self, raw_prefix, department):
        """
        Ensure SMS-friendly ticket prefixes (avoid ACC- and similar from name truncation).
        Respects QueueConfiguration max_length=5.
        """
        p = (raw_prefix or '').strip().upper().replace(' ', '')
        p = ''.join(c for c in p if c.isalnum())[:5]
        if len(p) < 2:
            p = 'VIS'
        fallback = (getattr(settings, 'QUEUE_TICKET_PREFIX_FALLBACK', None) or 'VIS').strip().upper()[:5]
        if p in _BLOCKED_QUEUE_PREFIXES:
            code = (getattr(department, 'code', None) or '').strip().upper()
            code = ''.join(c for c in code if c.isalnum())[:5]
            if code and code not in _BLOCKED_QUEUE_PREFIXES:
                return code
            return fallback
        return p

    def _resolve_prefix_for_department(self, department):
        """Prefix from QueueConfiguration when set, else default; then normalize for patient-facing tickets."""
        from hospital.models_queue import QueueConfiguration
        raw = None
        try:
            cfg = QueueConfiguration.objects.get(department=department)
            raw = (cfg.queue_prefix or '').strip()
        except QueueConfiguration.DoesNotExist:
            pass
        if not raw:
            raw = self._get_default_prefix(department)
        return self._normalize_ticket_prefix(raw, department)


# Global instance
queue_service = QueueService()


















