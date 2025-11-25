# 🎫 World-Class Patient Queue Management System
## Hospital Management System - Queue & Ticketing Feature

---

## 🎯 Vision Statement

Transform the patient visit creation process into an intelligent, automated queue management system that:
- **Assigns daily queue numbers** to patients upon check-in
- **Sends real-time SMS/WhatsApp notifications** about queue status
- **Manages patient flow** across multiple departments
- **Provides live queue displays** for waiting areas
- **Estimates wait times** intelligently
- **Tracks patient journey** from check-in to completion

---

## 📋 System Overview

### Patient Journey Flow
```
1. Patient Arrives/Calls → Receptionist Creates Visit
                          ↓
2. System Assigns Queue Number (e.g., OPD-042)
                          ↓
3. SMS Sent: "Your queue number is OPD-042. Current position: 12. Est. wait: 35 mins"
                          ↓
4. Patient Waits → System sends updates every 5 patients
                          ↓
5. SMS: "You're now #5 in queue. Est. wait: 15 mins"
                          ↓
6. Doctor marks "Call Next Patient" → System identifies next in queue
                          ↓
7. SMS: "It's your turn! Queue #OPD-042. Please proceed to Room 3"
                          ↓
8. Patient in consultation → Status: "In Progress"
                          ↓
9. Consultation ends → Status: "Completed"
```

---

## 🏗️ Core Components

### 1. Queue Number Generation
- **Format**: `{DEPT}-{SEQ}`
  - OPD-001, OPD-002, ... (Outpatient)
  - EMG-001, EMG-002, ... (Emergency)
  - SPL-001, SPL-002, ... (Specialist)
- **Daily Reset**: Counters reset at midnight
- **Department-specific**: Each department has its own queue
- **Priority Levels**:
  - 🔴 Emergency (Priority 1) - Jump to front
  - 🟠 Urgent (Priority 2) - Inserted ahead of normal
  - 🟢 Normal (Priority 3) - Standard queue
  - 🔵 Follow-up (Priority 4) - Lower priority

### 2. Queue Status States
```python
QUEUE_STATES = [
    ('checked_in', '✅ Checked In - Waiting'),
    ('called', '📢 Called - Please Proceed'),
    ('in_progress', '👨‍⚕️ In Consultation'),
    ('completed', '✓ Completed'),
    ('no_show', '❌ No Show'),
    ('cancelled', '🚫 Cancelled'),
]
```

### 3. SMS Notification Events

#### Event 1: Check-in Confirmation
```
🏥 {HOSPITAL_NAME}

Welcome! Your queue number is: OPD-042

📍 Department: Outpatient
👥 Position: 12 in queue
⏱️ Estimated wait: 35 minutes
📅 Date: Nov 7, 2025

Please wait in the OPD waiting area.
You'll receive updates via SMS.
```

#### Event 2: Progress Update (Every 5 positions)
```
🏥 Queue Update

Queue #OPD-042
Current position: 5
⏱️ Estimated wait: 15 minutes

Thank you for your patience!
```

#### Event 3: Your Turn - Ready for Consultation
```
🏥 READY FOR CONSULTATION

Queue #OPD-042 - It's your turn!

📍 Please proceed to:
   Room 3 - Dr. Johnson

⚠️ Please arrive within 5 minutes
```

#### Event 4: Missed/No Show Warning
```
🏥 ATTENTION REQUIRED

Queue #OPD-042
You were called but did not respond.

Please report to reception immediately
or you may lose your queue position.
```

#### Event 5: Completion Notification
```
🏥 Thank you for visiting!

Queue #OPD-042 - Consultation completed

💊 Next steps:
- Pharmacy: Room 5
- Lab: Floor 2
- Cashier: Ground Floor

📱 Questions? Call: 0123456789
```

---

## 🖥️ User Interfaces

### A. Reception Dashboard - Queue Check-in
```
┌─────────────────────────────────────────────────────────────┐
│  🎫 Patient Check-In & Queue Assignment                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Patient: John Doe (MRN: MRN00123)                         │
│  Phone: +233 24 123 4567 ✓ Verified                        │
│                                                              │
│  📍 Department: [▼ Outpatient Department    ]              │
│  👨‍⚕️ Doctor: [▼ Dr. Sarah Johnson         ]              │
│  🚨 Priority: [▼ Normal                     ]              │
│  📝 Visit Type: [▼ Consultation             ]              │
│                                                              │
│  ───────────────────────────────────────────────────────    │
│                                                              │
│  Queue Preview:                                             │
│  ┌────────────────────────────────────────┐                │
│  │  Queue Number: OPD-043                 │                │
│  │  Current Position: 13 in queue         │                │
│  │  Estimated Wait: 38 minutes            │                │
│  │  Ahead of you: 12 patients             │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ☐ Send SMS notification                                   │
│  ☐ Send WhatsApp notification                              │
│  ☐ Print queue ticket                                      │
│                                                              │
│  [CHECK IN & ASSIGN QUEUE NUMBER]                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### B. Doctor Dashboard - Queue Management
```
┌─────────────────────────────────────────────────────────────┐
│  👨‍⚕️ Dr. Sarah Johnson - OPD Queue                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 Today's Queue Status                                    │
│  ├─ Total: 42 patients                                      │
│  ├─ Completed: 28 ✓                                         │
│  ├─ Waiting: 12 ⏳                                          │
│  ├─ In Progress: 1 👨‍⚕️                                     │
│  └─ No Show: 1 ❌                                           │
│                                                              │
│  ─────────────────────────────────────────────────────      │
│                                                              │
│  🔴 CURRENT PATIENT                                         │
│  ┌─────────────────────────────────────────┐               │
│  │  Queue: OPD-029                         │               │
│  │  Name: Mary Smith                       │               │
│  │  Age: 45 years                          │               │
│  │  Chief Complaint: Fever, headache       │               │
│  │  Wait Time: 12 minutes                  │               │
│  │                                          │               │
│  │  [COMPLETE CONSULTATION]                │               │
│  └─────────────────────────────────────────┘               │
│                                                              │
│  📋 NEXT IN QUEUE                                           │
│  ┌─────────────────────────────────────────┐               │
│  │  OPD-030 | John Doe | 32M              │ [CALL NEXT]   │
│  │  OPD-031 | Jane Wilson | 28F           │               │
│  │  OPD-032 | Peter Brown | 55M           │               │
│  │  🔴 EMG-005 | Sarah Lee | 67F (EMG)    │ [CALL]        │
│  │  OPD-033 | David Clark | 41M           │               │
│  └─────────────────────────────────────────┘               │
│                                                              │
│  [🔴 CALL EMERGENCY PATIENT]  [📢 CALL NEXT PATIENT]       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### C. Public Queue Display (TV Screen in Waiting Area)
```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│        🏥 GENERAL HOSPITAL PATIENT QUEUE                    │
│                                                              │
│  ════════════════════════════════════════════════════════   │
│                                                              │
│  🟢 NOW SERVING                                             │
│                                                              │
│         OPD-029                                             │
│      📍 Room 3 - Dr. Johnson                                │
│                                                              │
│  ────────────────────────────────────────────────────────   │
│                                                              │
│  📋 UPCOMING                                                │
│                                                              │
│     OPD-030  →  Room 3                                      │
│     OPD-031  →  Room 3                                      │
│     OPD-032  →  Room 3                                      │
│     SPL-012  →  Room 5 (Specialist)                         │
│                                                              │
│  ────────────────────────────────────────────────────────   │
│                                                              │
│  ⏱️ Average Wait Time: 28 minutes                           │
│  📅 Date: November 7, 2025  🕐 Time: 10:45 AM              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### D. Mobile Patient App View (Optional)
```
┌──────────────────────┐
│  🏥 My Queue         │
├──────────────────────┤
│                      │
│  Your Number:        │
│                      │
│    📋 OPD-042        │
│                      │
│  Status: Waiting     │
│                      │
│  ▓▓▓▓▓▓▓▓▓░░░░  75% │
│                      │
│  👥 Position: 5/20   │
│  ⏱️ Est. Wait: 15min │
│                      │
│  Now Serving:        │
│  OPD-029             │
│                      │
│  ──────────────────  │
│                      │
│  📍 OPD - Room 3     │
│  👨‍⚕️ Dr. Johnson     │
│                      │
│  [REFRESH]           │
│                      │
└──────────────────────┘
```

---

## 🗄️ Database Schema

### New Model: `QueueEntry`
```python
class QueueEntry(BaseModel):
    """Patient queue entry for daily visit management"""
    
    # Queue Identification
    queue_number = models.CharField(max_length=20, unique=True)  # OPD-042
    queue_date = models.DateField(auto_now_add=True)
    sequence_number = models.IntegerField()  # Daily sequence: 1, 2, 3...
    
    # Relationships
    visit = models.OneToOneField('Visit', on_delete=models.CASCADE, related_name='queue_entry')
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    encounter = models.ForeignKey('Encounter', on_delete=models.CASCADE, null=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True)
    assigned_doctor = models.ForeignKey('Doctor', on_delete=models.SET_NULL, null=True)
    
    # Queue Management
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)  # 1=Emergency, 3=Normal
    status = models.CharField(max_length=20, choices=QUEUE_STATUS_CHOICES, default='checked_in')
    
    # Timestamps
    check_in_time = models.DateTimeField(auto_now_add=True)
    called_time = models.DateTimeField(null=True, blank=True)
    started_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(null=True, blank=True)
    
    # Wait Time Tracking
    estimated_wait_minutes = models.IntegerField(default=0)
    actual_wait_minutes = models.IntegerField(null=True, blank=True)
    consultation_duration_minutes = models.IntegerField(null=True, blank=True)
    
    # Notification Tracking
    sms_sent = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    notification_count = models.IntegerField(default=0)
    
    # Room Assignment
    room_number = models.CharField(max_length=20, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    no_show = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['queue_date', 'priority', 'sequence_number']
        indexes = [
            models.Index(fields=['queue_date', 'department', 'status']),
            models.Index(fields=['queue_number']),
        ]
```

### New Model: `QueueNotification`
```python
class QueueNotification(BaseModel):
    """Track all queue-related notifications"""
    
    queue_entry = models.ForeignKey('QueueEntry', on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    # Types: check_in, progress_update, ready, no_show, completed
    
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    # Channels: sms, whatsapp, email
    
    message_content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)
    
    external_id = models.CharField(max_length=100, blank=True)  # SMS provider ID
```

### New Model: `QueueConfiguration`
```python
class QueueConfiguration(BaseModel):
    """Configuration for queue management per department"""
    
    department = models.OneToOneField('Department', on_delete=models.CASCADE)
    
    # Queue Settings
    queue_prefix = models.CharField(max_length=5, default='OPD')  # OPD, EMG, SPL
    enable_queue = models.BooleanField(default=True)
    
    # Timing
    average_consultation_minutes = models.IntegerField(default=15)
    buffer_time_minutes = models.IntegerField(default=5)
    
    # Notifications
    send_check_in_sms = models.BooleanField(default=True)
    send_progress_updates = models.BooleanField(default=True)
    send_ready_notification = models.BooleanField(default=True)
    notification_interval_patients = models.IntegerField(default=5)  # Update every 5 patients
    
    # Display
    show_on_public_display = models.BooleanField(default=True)
    display_upcoming_count = models.IntegerField(default=5)
```

---

## 🔧 Technical Implementation

### Queue Number Generator Service
```python
# hospital/services/queue_service.py

class QueueService:
    """Intelligent queue management service"""
    
    def generate_queue_number(self, department, priority=3):
        """Generate next queue number for department"""
        today = timezone.now().date()
        prefix = self._get_department_prefix(department)
        
        # Get next sequence for today
        last_queue = QueueEntry.objects.filter(
            queue_date=today,
            department=department
        ).order_by('-sequence_number').first()
        
        sequence = (last_queue.sequence_number + 1) if last_queue else 1
        queue_number = f"{prefix}-{sequence:03d}"  # OPD-001
        
        return queue_number, sequence
    
    def calculate_estimated_wait(self, department, position_in_queue):
        """Calculate estimated wait time"""
        config = QueueConfiguration.objects.get(department=department)
        avg_time = config.average_consultation_minutes
        buffer = config.buffer_time_minutes
        
        estimated_minutes = (avg_time + buffer) * position_in_queue
        return estimated_minutes
    
    def get_position_in_queue(self, queue_entry):
        """Get current position in queue"""
        return QueueEntry.objects.filter(
            queue_date=queue_entry.queue_date,
            department=queue_entry.department,
            status__in=['checked_in', 'called'],
            priority__lte=queue_entry.priority,
            check_in_time__lt=queue_entry.check_in_time
        ).count() + 1
    
    def get_next_patient(self, department, doctor=None):
        """Get next patient in queue considering priority"""
        today = timezone.now().date()
        
        queryset = QueueEntry.objects.filter(
            queue_date=today,
            department=department,
            status='checked_in'
        ).order_by('priority', 'sequence_number')
        
        if doctor:
            queryset = queryset.filter(assigned_doctor=doctor)
        
        return queryset.first()
    
    def call_next_patient(self, queue_entry, room_number=''):
        """Mark patient as called and send notification"""
        queue_entry.status = 'called'
        queue_entry.called_time = timezone.now()
        queue_entry.room_number = room_number
        queue_entry.save()
        
        # Send SMS notification
        self._send_ready_notification(queue_entry)
        
        return queue_entry
    
    def start_consultation(self, queue_entry):
        """Mark consultation as started"""
        queue_entry.status = 'in_progress'
        queue_entry.started_time = timezone.now()
        
        if queue_entry.called_time:
            wait_time = (queue_entry.started_time - queue_entry.check_in_time).seconds // 60
            queue_entry.actual_wait_minutes = wait_time
        
        queue_entry.save()
    
    def complete_consultation(self, queue_entry):
        """Mark consultation as completed"""
        queue_entry.status = 'completed'
        queue_entry.completed_time = timezone.now()
        
        if queue_entry.started_time:
            duration = (queue_entry.completed_time - queue_entry.started_time).seconds // 60
            queue_entry.consultation_duration_minutes = duration
        
        queue_entry.save()
        
        # Send completion notification
        self._send_completion_notification(queue_entry)
```

---

## 📱 SMS Notification Templates

### Template System
```python
# hospital/services/queue_notification_service.py

class QueueNotificationService:
    """Handle all queue-related notifications"""
    
    TEMPLATES = {
        'check_in': """🏥 {hospital_name}

Welcome! Your queue number is: {queue_number}

📍 Department: {department}
👥 Position: {position} in queue
⏱️ Estimated wait: {wait_time} minutes
📅 Date: {date}

Please wait in the {department} waiting area.
You'll receive updates via SMS.""",

        'progress_update': """🏥 Queue Update

Queue #{queue_number}
Current position: {position}
⏱️ Estimated wait: {wait_time} minutes

Thank you for your patience!""",

        'ready': """🏥 READY FOR CONSULTATION

Queue #{queue_number} - It's your turn!

📍 Please proceed to:
   {room_info}

⚠️ Please arrive within 5 minutes""",

        'no_show': """🏥 ATTENTION REQUIRED

Queue #{queue_number}
You were called but did not respond.

Please report to reception immediately
or you may lose your queue position.""",

        'completed': """🏥 Thank you for visiting!

Queue #{queue_number} - Consultation completed

💊 Next steps:
{next_steps}

📱 Questions? Call: {phone}"""
    }
    
    def send_check_in_notification(self, queue_entry):
        """Send check-in SMS"""
        # Implementation...
```

---

## 📊 Analytics & Reporting

### Queue Performance Metrics
1. **Average Wait Time** per department
2. **Peak Hours** analysis
3. **No-Show Rate**
4. **Doctor Performance** (avg consultation time)
5. **Daily Throughput** (patients served per day)
6. **Patient Satisfaction** (wait time vs expected)

### Reports Dashboard
- Real-time queue status
- Historical trends
- Department comparison
- Doctor productivity

---

## 🚀 Implementation Phases

### Phase 1: Core Queue System (Week 1)
- [x] Database models
- [x] Queue number generation
- [x] Basic check-in flow
- [x] Position calculation

### Phase 2: Notifications (Week 2)
- [ ] SMS integration
- [ ] WhatsApp integration
- [ ] Notification templates
- [ ] Automated triggers

### Phase 3: Doctor Dashboard (Week 3)
- [ ] Queue management UI
- [ ] Call next patient
- [ ] Start/complete consultation
- [ ] Queue status display

### Phase 4: Public Display (Week 4)
- [ ] TV screen display
- [ ] Real-time updates
- [ ] Auto-refresh
- [ ] Multi-department view

### Phase 5: Advanced Features (Week 5)
- [ ] Priority queue management
- [ ] Mobile app integration
- [ ] Queue analytics
- [ ] Performance reports

---

## ✅ Success Criteria

1. ✅ Every patient gets a unique daily queue number
2. ✅ SMS sent within 30 seconds of check-in
3. ✅ Wait time estimates accurate within 10 minutes
4. ✅ Zero queue number conflicts
5. ✅ Public display updates in real-time
6. ✅ Doctors can easily call next patient
7. ✅ Patients notified before their turn
8. ✅ System handles 500+ patients/day

---

## 🎯 Expected Benefits

### For Patients:
- ✅ Know exact queue position
- ✅ Reduce waiting room congestion
- ✅ Can step out and return when ready
- ✅ Transparent wait times
- ✅ Professional experience

### For Staff:
- ✅ Organized patient flow
- ✅ Easy queue management
- ✅ Reduced conflicts
- ✅ Better time management
- ✅ Performance insights

### For Hospital:
- ✅ Improved efficiency
- ✅ Better patient satisfaction
- ✅ Data-driven decisions
- ✅ Professional image
- ✅ Reduced complaints

---

**This is a world-class queue management system that will transform patient experience!** 🎉
























