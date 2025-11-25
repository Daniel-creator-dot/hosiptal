"""
Legacy System ID Mapping Models
Tracks mapping between old system IDs and new Django model IDs
"""
from django.db import models
from .models import BaseModel


class LegacyIDMapping(BaseModel):
    """
    Maps legacy system IDs to new Django model IDs
    Essential for maintaining relationships during migration
    """
    
    # Legacy System
    legacy_table = models.CharField(
        max_length=100,
        help_text="Name of the legacy table (e.g., patient_data, users, drugs)"
    )
    legacy_id = models.CharField(
        max_length=50,
        help_text="ID in the legacy system"
    )
    
    # New System
    new_model = models.CharField(
        max_length=100,
        help_text="Django model name (e.g., Patient, CustomUser, Drug)"
    )
    new_id = models.UUIDField(
        help_text="UUID in the new system"
    )
    
    # Metadata
    migrated_at = models.DateTimeField(auto_now_add=True)
    migration_batch = models.CharField(
        max_length=50,
        blank=True,
        help_text="Migration batch identifier"
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['legacy_table', 'legacy_id']
        indexes = [
            models.Index(fields=['legacy_table', 'legacy_id']),
            models.Index(fields=['new_model', 'new_id']),
        ]
        verbose_name = 'Legacy ID Mapping'
        verbose_name_plural = 'Legacy ID Mappings'
    
    def __str__(self):
        return f"{self.legacy_table}:{self.legacy_id} → {self.new_model}:{self.new_id}"


class MigrationLog(BaseModel):
    """
    Logs all migration activities for audit and troubleshooting
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]
    
    batch_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique batch identifier"
    )
    
    migration_type = models.CharField(
        max_length=50,
        help_text="Type of migration (patients, users, drugs, etc.)"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Counts
    total_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    skipped_records = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Details
    error_log = models.TextField(
        blank=True,
        help_text="Detailed error messages"
    )
    success_log = models.TextField(
        blank=True,
        help_text="Success messages and warnings"
    )
    
    # User
    initiated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Migration Log'
        verbose_name_plural = 'Migration Logs'
    
    def __str__(self):
        return f"{self.batch_id} - {self.migration_type} ({self.status})"
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_records > 0:
            return (self.successful_records / self.total_records) * 100
        return 0
    
    @property
    def duration_seconds(self):
        """Calculate migration duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
























