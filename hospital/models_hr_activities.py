"""
HR Activities and Events Models - Calendar, Recognition, Wellness, Recruitment
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import BaseModel, Staff, Department


class HospitalActivity(BaseModel):
    """Hospital-wide activities and events calendar"""
    ACTIVITY_TYPES = [
        ('meeting', 'Meeting'),
        ('training', 'Training Session'),
        ('workshop', 'Workshop'),
        ('conference', 'Conference'),
        ('social', 'Social Event'),
        ('announcement', 'Announcement'),
        ('holiday', 'Holiday'),
        ('maintenance', 'Maintenance'),
        ('drill', 'Emergency Drill'),
        ('celebration', 'Celebration'),
        ('other', 'Other'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='announcement')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    location = models.CharField(max_length=200, blank=True)
    organizer = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='organized_activities')
    
    # Target audience
    all_staff = models.BooleanField(default=True, help_text="Visible to all staff")
    departments = models.ManyToManyField(Department, blank=True, help_text="Specific departments (if not all staff)")
    specific_staff = models.ManyToManyField(Staff, blank=True, related_name='targeted_activities', help_text="Specific staff members")
    
    # Additional info
    is_mandatory = models.BooleanField(default=False)
    requires_rsvp = models.BooleanField(default=False)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    
    attachment = models.FileField(upload_to='activity_attachments/', null=True, blank=True)
    external_link = models.URLField(blank=True)
    
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date', '-start_time']
        verbose_name = 'Hospital Activity'
        verbose_name_plural = 'Hospital Activities'
    
    def __str__(self):
        return f"{self.title} - {self.start_date}"
    
    @property
    def is_past(self):
        """Check if activity is in the past"""
        return self.end_date < timezone.now().date()
    
    @property
    def is_today(self):
        """Check if activity is today"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
    
    @property
    def is_upcoming(self):
        """Check if activity is upcoming"""
        return self.start_date > timezone.now().date()


class ActivityRSVP(BaseModel):
    """RSVP responses for activities"""
    RESPONSE_CHOICES = [
        ('yes', 'Yes - Attending'),
        ('no', 'No - Not Attending'),
        ('maybe', 'Maybe'),
    ]
    
    activity = models.ForeignKey(HospitalActivity, on_delete=models.CASCADE, related_name='rsvps')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='activity_rsvps')
    response = models.CharField(max_length=10, choices=RESPONSE_CHOICES)
    notes = models.TextField(blank=True)
    responded_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['activity', 'staff']
        ordering = ['-responded_at']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.activity.title} ({self.get_response_display()})"


class StaffRecognition(BaseModel):
    """Staff awards and recognition"""
    RECOGNITION_TYPES = [
        ('employee_month', 'Employee of the Month'),
        ('excellence', 'Excellence Award'),
        ('innovation', 'Innovation Award'),
        ('customer_service', 'Customer Service Award'),
        ('teamwork', 'Teamwork Award'),
        ('safety', 'Safety Award'),
        ('attendance', 'Perfect Attendance'),
        ('years_service', 'Years of Service'),
        ('commendation', 'Commendation'),
        ('other', 'Other'),
    ]
    
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='recognitions')
    recognition_type = models.CharField(max_length=20, choices=RECOGNITION_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    awarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='awards_given')
    awarded_date = models.DateField(default=timezone.now)
    
    certificate = models.FileField(upload_to='recognition_certificates/', null=True, blank=True)
    prize_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Monetary value if applicable")
    
    is_public = models.BooleanField(default=True, help_text="Display on public recognition board")
    
    class Meta:
        ordering = ['-awarded_date']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.get_recognition_type_display()}"


class RecruitmentPosition(BaseModel):
    """Open positions for recruitment"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('on_hold', 'On Hold'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
    ]
    
    EMPLOYMENT_TYPES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
        ('intern', 'Internship'),
    ]
    
    position_title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='open_positions')
    
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default='full_time')
    number_of_positions = models.PositiveIntegerField(default=1)
    
    job_description = models.TextField()
    requirements = models.TextField()
    qualifications = models.TextField()
    
    salary_range_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_range_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    posted_date = models.DateField(default=timezone.now)
    closing_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    hiring_manager = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='managed_recruitments')
    
    is_urgent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-posted_date']
    
    def __str__(self):
        return f"{self.position_title} - {self.department.name if self.department else 'N/A'}"


class Candidate(BaseModel):
    """Job applicants/candidates"""
    STATUS_CHOICES = [
        ('applied', 'Application Received'),
        ('screening', 'Under Screening'),
        ('shortlisted', 'Shortlisted'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('interviewed', 'Interviewed'),
        ('offered', 'Offer Extended'),
        ('accepted', 'Offer Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    position = models.ForeignKey(RecruitmentPosition, on_delete=models.CASCADE, related_name='candidates')
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=17)
    
    resume = models.FileField(upload_to='candidate_resumes/', blank=True)
    cover_letter = models.TextField(blank=True)
    
    application_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    
    interview_date = models.DateTimeField(null=True, blank=True)
    interview_notes = models.TextField(blank=True)
    interview_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    offer_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    offer_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-application_date']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.position.position_title}"


class WellnessProgram(BaseModel):
    """Staff wellness programs and initiatives"""
    PROGRAM_TYPES = [
        ('fitness', 'Fitness Program'),
        ('mental_health', 'Mental Health'),
        ('nutrition', 'Nutrition'),
        ('stress_management', 'Stress Management'),
        ('health_screening', 'Health Screening'),
        ('vaccination', 'Vaccination Drive'),
        ('yoga', 'Yoga/Meditation'),
        ('counseling', 'Counseling Services'),
        ('other', 'Other'),
    ]
    
    program_name = models.CharField(max_length=200)
    program_type = models.CharField(max_length=20, choices=PROGRAM_TYPES)
    description = models.TextField()
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    organizer = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='wellness_programs_organized')
    location = models.CharField(max_length=200, blank=True)
    
    is_active = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.program_name} ({self.get_program_type_display()})"


class WellnessParticipation(BaseModel):
    """Track staff participation in wellness programs"""
    program = models.ForeignKey(WellnessProgram, on_delete=models.CASCADE, related_name='participants')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='wellness_participations')
    
    enrolled_date = models.DateField(default=timezone.now)
    completion_date = models.DateField(null=True, blank=True)
    
    is_completed = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)
    rating = models.PositiveIntegerField(null=True, blank=True, help_text="Rating out of 5")
    
    class Meta:
        unique_together = ['program', 'staff']
        ordering = ['-enrolled_date']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.program.program_name}"


class StaffSurvey(BaseModel):
    """Employee surveys and feedback"""
    SURVEY_TYPES = [
        ('engagement', 'Employee Engagement'),
        ('satisfaction', 'Job Satisfaction'),
        ('climate', 'Workplace Climate'),
        ('benefits', 'Benefits Feedback'),
        ('training', 'Training Needs'),
        ('exit', 'Exit Survey'),
        ('pulse', 'Pulse Check'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=200)
    survey_type = models.CharField(max_length=20, choices=SURVEY_TYPES)
    description = models.TextField()
    
    questions = models.JSONField(default=list, help_text="List of survey questions")
    
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()
    
    is_anonymous = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    target_departments = models.ManyToManyField(Department, blank=True)
    all_staff = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.title} ({self.get_survey_type_display()})"


class SurveyResponse(BaseModel):
    """Individual responses to surveys"""
    survey = models.ForeignKey(StaffSurvey, on_delete=models.CASCADE, related_name='responses')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True, related_name='survey_responses')
    
    answers = models.JSONField(default=dict, help_text="Survey answers")
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        staff_name = self.staff.user.get_full_name() if self.staff else "Anonymous"
        return f"{staff_name} - {self.survey.title}"


# ==================== STAFF DASHBOARD MODELS ====================
# These models support the staff personal dashboard

class StaffActivity(BaseModel):
    """Personal staff activities (for staff dashboard)"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='personal_activities', null=True, blank=True)
    title = models.CharField(max_length=200, default='Activity')
    description = models.TextField(blank=True)
    activity_date = models.DateField(default=timezone.now)
    activity_time = models.TimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['activity_date', 'activity_time']
        verbose_name_plural = 'Staff Activities'
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.title}"


class LeaveBalanceAlert(BaseModel):
    """Leave balance alerts for staff"""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='leave_alerts')
    alert_type = models.CharField(max_length=50, choices=[
        ('low_balance', 'Low Leave Balance'),
        ('expiring', 'Leave Expiring'),
        ('reminder', 'Leave Reminder'),
    ], default='low_balance')
    message = models.TextField(default='Leave balance alert')
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.get_alert_type_display()}"


class StaffLeaveCounter(BaseModel):
    """Leave countdown widget data for staff dashboard"""
    staff = models.OneToOneField(Staff, on_delete=models.CASCADE, related_name='leave_counter')
    days_until_next_leave = models.IntegerField(default=0)
    next_leave_date = models.DateField(null=True, blank=True)
    next_leave_type = models.CharField(max_length=50, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Staff Leave Counter'
        verbose_name_plural = 'Staff Leave Counters'
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - Leave Counter"
