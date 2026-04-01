"""
Marketing Strategy & Corporate Growth Models
Task management and monitoring for marketing initiatives
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import BaseModel

User = get_user_model()


class MarketingObjective(BaseModel):
    """
    Marketing strategic objectives aligned with corporate goals
    """
    OBJECTIVE_TYPES = [
        ('brand_awareness', 'Brand Awareness & Recognition'),
        ('patient_acquisition', 'Patient Acquisition & Growth'),
        ('corporate_partnerships', 'Corporate Partnerships'),
        ('digital_marketing', 'Digital Marketing & Online Presence'),
        ('community_outreach', 'Community Outreach & Engagement'),
        ('referral_programs', 'Referral Programs'),
        ('service_promotion', 'Service Promotion & Campaigns'),
        ('reputation_management', 'Reputation & Review Management'),
    ]
    
    PRIORITY_LEVELS = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    objective_type = models.CharField(max_length=50, choices=OBJECTIVE_TYPES)
    description = models.TextField()
    target_audience = models.CharField(max_length=200, blank=True)
    budget_allocated = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_date = models.DateField()
    target_completion_date = models.DateField()
    actual_completion_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marketing_objectives')
    assigned_team = models.ManyToManyField(User, related_name='marketing_team_objectives', blank=True)
    
    # Success Metrics
    target_metric_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_metric_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    metric_type = models.CharField(max_length=50, blank=True, help_text="e.g., 'new_patients', 'revenue', 'website_visits'")
    
    # Progress Tracking
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-priority', '-created']
        verbose_name = 'Marketing Objective'
        verbose_name_plural = 'Marketing Objectives'
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def is_overdue(self):
        if self.status not in ['completed', 'cancelled']:
            return timezone.now().date() > self.target_completion_date
        return False
    
    @property
    def budget_utilization(self):
        if self.budget_allocated > 0:
            return (self.budget_spent / self.budget_allocated) * 100
        return 0
    
    @property
    def days_remaining(self):
        if self.status in ['completed', 'cancelled']:
            return 0
        delta = self.target_completion_date - timezone.now().date()
        return max(0, delta.days)
    
    def update_progress(self):
        """Calculate progress based on completed tasks"""
        total_tasks = self.marketing_tasks.count()
        if total_tasks == 0:
            self.progress_percentage = 0
        else:
            completed_tasks = self.marketing_tasks.filter(status='completed').count()
            self.progress_percentage = (completed_tasks / total_tasks) * 100
        self.save(update_fields=['progress_percentage', 'modified'])


class MarketingTask(BaseModel):
    """
    Individual tasks for marketing objectives
    """
    TASK_TYPES = [
        ('content_creation', 'Content Creation'),
        ('campaign_setup', 'Campaign Setup'),
        ('event_planning', 'Event Planning'),
        ('partnership_outreach', 'Partnership Outreach'),
        ('social_media', 'Social Media Management'),
        ('seo_optimization', 'SEO Optimization'),
        ('advertising', 'Advertising & Promotion'),
        ('analytics_review', 'Analytics & Reporting'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
        ('cancelled', 'Cancelled'),
    ]
    
    objective = models.ForeignKey(MarketingObjective, on_delete=models.CASCADE, related_name='marketing_tasks')
    title = models.CharField(max_length=200)
    task_type = models.CharField(max_length=50, choices=TASK_TYPES, default='other')
    description = models.TextField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_marketing_tasks')
    due_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=MarketingObjective.PRIORITY_LEVELS, default='medium')
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    budget_allocated = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    budget_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='dependent_tasks')
    
    class Meta:
        ordering = ['-priority', 'due_date']
        verbose_name = 'Marketing Task'
        verbose_name_plural = 'Marketing Tasks'
    
    def __str__(self):
        return f"{self.title} - {self.objective.title}"
    
    @property
    def is_overdue(self):
        if self.status not in ['completed', 'cancelled']:
            return timezone.now().date() > self.due_date
        return False
    
    @property
    def days_remaining(self):
        if self.status in ['completed', 'cancelled']:
            return 0
        delta = self.due_date - timezone.now().date()
        return max(0, delta.days)
    
    def mark_completed(self):
        """Mark task as completed and update objective progress"""
        self.status = 'completed'
        self.completed_date = timezone.now().date()
        self.save(update_fields=['status', 'completed_date', 'modified'])
        self.objective.update_progress()


class MarketingCampaign(BaseModel):
    """
    Marketing campaigns and initiatives
    """
    CAMPAIGN_TYPES = [
        ('digital', 'Digital Campaign'),
        ('print', 'Print Media'),
        ('radio', 'Radio'),
        ('tv', 'Television'),
        ('event', 'Event-Based'),
        ('social_media', 'Social Media'),
        ('email', 'Email Marketing'),
        ('referral', 'Referral Program'),
        ('corporate', 'Corporate Partnership'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    campaign_type = models.CharField(max_length=50, choices=CAMPAIGN_TYPES)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_campaigns')
    
    # Performance Metrics
    target_reach = models.IntegerField(null=True, blank=True, help_text="Target audience reach")
    actual_reach = models.IntegerField(default=0)
    target_conversions = models.IntegerField(null=True, blank=True, help_text="Target conversions (e.g., appointments)")
    actual_conversions = models.IntegerField(default=0)
    target_revenue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # ROI Calculation
    roi_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Return on Investment %")
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Marketing Campaign'
        verbose_name_plural = 'Marketing Campaigns'
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def is_active(self):
        today = timezone.now().date()
        return self.status == 'active' and self.start_date <= today <= self.end_date
    
    @property
    def conversion_rate(self):
        if self.actual_reach > 0:
            return (self.actual_conversions / self.actual_reach) * 100
        return 0
    
    @property
    def cost_per_conversion(self):
        if self.actual_conversions > 0:
            return self.spent / self.actual_conversions
        return 0
    
    def calculate_roi(self):
        """Calculate Return on Investment"""
        if self.spent > 0 and self.actual_revenue > 0:
            self.roi_percentage = ((self.actual_revenue - self.spent) / self.spent) * 100
        else:
            self.roi_percentage = 0
        self.save(update_fields=['roi_percentage', 'modified'])


class MarketingMetric(BaseModel):
    """
    Track marketing KPIs and metrics over time
    """
    METRIC_TYPES = [
        ('new_patients', 'New Patients Acquired'),
        ('website_visits', 'Website Visits'),
        ('social_media_followers', 'Social Media Followers'),
        ('email_subscribers', 'Email Subscribers'),
        ('referrals', 'Referrals Generated'),
        ('appointment_bookings', 'Appointment Bookings'),
        ('revenue', 'Revenue Generated'),
        ('brand_mentions', 'Brand Mentions'),
        ('lead_generation', 'Leads Generated'),
        ('conversion_rate', 'Conversion Rate'),
    ]
    
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES)
    date = models.DateField()
    value = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=100, blank=True, help_text="e.g., 'Google Ads', 'Facebook', 'Referral Program'")
    campaign = models.ForeignKey(MarketingCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='metrics')
    objective = models.ForeignKey(MarketingObjective, on_delete=models.SET_NULL, null=True, blank=True, related_name='metrics')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date', '-created']
        unique_together = [['metric_type', 'date', 'source']]
        verbose_name = 'Marketing Metric'
        verbose_name_plural = 'Marketing Metrics'
    
    def __str__(self):
        return f"{self.get_metric_type_display()}: {self.value} on {self.date}"


class CorporatePartnership(BaseModel):
    """
    Corporate partnerships and collaborations
    """
    PARTNERSHIP_TYPES = [
        ('insurance', 'Insurance Provider'),
        ('corporate_wellness', 'Corporate Wellness Program'),
        ('referral_network', 'Referral Network'),
        ('sponsorship', 'Sponsorship Agreement'),
        ('joint_venture', 'Joint Venture'),
        ('supplier', 'Preferred Supplier'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('prospect', 'Prospect'),
        ('negotiating', 'Negotiating'),
        ('active', 'Active'),
        ('renewal', 'Renewal Pending'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ]
    
    company_name = models.CharField(max_length=200)
    partnership_type = models.CharField(max_length=50, choices=PARTNERSHIP_TYPES)
    contact_person = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='prospect')
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Partnership value/revenue")
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_partnerships')
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Corporate Partnership'
        verbose_name_plural = 'Corporate Partnerships'
    
    def __str__(self):
        return f"{self.company_name} - {self.get_partnership_type_display()}"


class CallReport(BaseModel):
    """
    Marketing call reports for tracking sales calls, follow-ups, and client interactions
    """
    CALL_TYPES = [
        ('cold_call', 'Cold Call'),
        ('warm_call', 'Warm Call'),
        ('follow_up', 'Follow-up Call'),
        ('consultation', 'Consultation Call'),
        ('partnership', 'Partnership Discussion'),
        ('customer_service', 'Customer Service Call'),
        ('other', 'Other'),
    ]
    
    CALL_OUTCOMES = [
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('follow_up_scheduled', 'Follow-up Scheduled'),
        ('meeting_scheduled', 'Meeting Scheduled'),
        ('quote_requested', 'Quote Requested'),
        ('sale_closed', 'Sale Closed'),
        ('objection_raised', 'Objection Raised'),
        ('callback_requested', 'Callback Requested'),
        ('no_answer', 'No Answer'),
        ('voicemail', 'Voicemail Left'),
        ('wrong_number', 'Wrong Number'),
        ('other', 'Other'),
    ]
    
    PRIORITY_LEVELS = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    # Call Information
    call_date = models.DateTimeField(default=timezone.now)
    call_type = models.CharField(max_length=50, choices=CALL_TYPES, default='cold_call')
    call_duration_minutes = models.PositiveIntegerField(default=0, help_text="Call duration in minutes")
    
    # Contact Information
    contact_name = models.CharField(max_length=200)
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField(blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    contact_title = models.CharField(max_length=100, blank=True)
    
    # Call Details
    call_outcome = models.CharField(max_length=50, choices=CALL_OUTCOMES)
    call_summary = models.TextField(help_text="Summary of the call conversation")
    key_points = models.TextField(blank=True, help_text="Key discussion points")
    objections_raised = models.TextField(blank=True, help_text="Any objections or concerns raised")
    next_steps = models.TextField(blank=True, help_text="Agreed next steps")
    
    # Follow-up Information
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    
    # Sales/Revenue Information
    potential_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Potential deal value")
    actual_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Actual closed value")
    service_interest = models.CharField(max_length=200, blank=True, help_text="Services they're interested in")
    
    # Relationship Information
    relationship_stage = models.CharField(
        max_length=50,
        choices=[
            ('new', 'New Contact'),
            ('prospect', 'Prospect'),
            ('qualified', 'Qualified Lead'),
            ('proposal', 'Proposal Sent'),
            ('negotiation', 'Negotiation'),
            ('closed_won', 'Closed Won'),
            ('closed_lost', 'Closed Lost'),
        ],
        default='new'
    )
    
    # Marketing Context
    campaign = models.ForeignKey(MarketingCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_reports')
    objective = models.ForeignKey(MarketingObjective, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_reports')
    partnership = models.ForeignKey(CorporatePartnership, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_reports')
    
    # Tracking
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='call_reports')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_call_reports')
    
    # Additional Notes
    internal_notes = models.TextField(blank=True, help_text="Internal notes (not shared with client)")
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags for categorization")
    
    class Meta:
        ordering = ['-call_date', '-created']
        verbose_name = 'Call Report'
        verbose_name_plural = 'Call Reports'
        indexes = [
            models.Index(fields=['call_date', 'reported_by']),
            models.Index(fields=['contact_phone']),
            models.Index(fields=['call_outcome']),
            models.Index(fields=['follow_up_required', 'follow_up_date']),
        ]
    
    def __str__(self):
        return f"Call Report: {self.contact_name} - {self.call_date.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def is_follow_up_due(self):
        """Check if follow-up is due"""
        if self.follow_up_required and self.follow_up_date:
            return timezone.now() >= self.follow_up_date
        return False
    
    @property
    def days_since_call(self):
        """Days since the call was made"""
        delta = timezone.now() - self.call_date
        return delta.days
    
    @property
    def is_high_value(self):
        """Check if this is a high-value opportunity"""
        return self.potential_value and self.potential_value >= 10000  # GHS 10,000+






