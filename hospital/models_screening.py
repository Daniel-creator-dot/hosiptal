"""
Pre-employment and Pre-admission screening models.
Templates define lab + imaging packages; reports capture fit/unfit and summary.
"""
from django.db import models
from django.utils import timezone

from .models import BaseModel, Encounter, Staff, Patient
from .models import Order, LabTest, LabResult
from .models_advanced import ImagingStudy, ImagingCatalog


class ScreeningCheckTemplate(BaseModel):
    """
    Reusable template for pre-employment (company) or pre-admission (school) checks.
    Doctor selects a template to send lab + imaging requests in one click.
    """
    CATEGORY_CHOICES = [
        ('pre_employment', 'Pre-employment (Company)'),
        ('pre_admission', 'Pre-admission (School)'),
    ]

    name = models.CharField(max_length=200, help_text='e.g. Basic Pre-employment, School Entry, Executive Check')
    code = models.CharField(max_length=50, unique=True, blank=True, help_text='Short code e.g. PREEMP-BASIC')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True, help_text='When to use this template')

    # Optional: restrict this template to a specific company/institution (blank = general use)
    for_company = models.CharField(
        max_length=255,
        blank=True,
        help_text='Specific company or institution name. Leave blank for general institutional use.'
    )

    # Lab: which tests are included
    lab_tests = models.ManyToManyField(
        LabTest,
        related_name='screening_templates',
        blank=True,
        help_text='Lab tests to order when this template is applied'
    )

    # Imaging: which imaging studies (from catalog) are included
    imaging_items = models.ManyToManyField(
        ImagingCatalog,
        related_name='screening_templates',
        blank=True,
        help_text='Imaging studies to order when this template is applied'
    )

    # Optional: physical exam sections to remind doctor (stored as JSON list of section names)
    # e.g. ["General", "Cardiovascular", "Vision", "Hearing"]
    physical_exam_sections = models.JSONField(
        default=list,
        blank=True,
        help_text='Physical exam sections to include in the report (list of strings)'
    )

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0, help_text='Display order in list')

    class Meta:
        ordering = ['category', 'sort_order', 'name']
        verbose_name = 'Screening check template'
        verbose_name_plural = 'Screening check templates'

    def __str__(self):
        return f"{self.get_category_display()}: {self.name}"

    @property
    def lab_test_count(self):
        return self.lab_tests.filter(is_active=True, is_deleted=False).count()

    @property
    def imaging_count(self):
        return self.imaging_items.filter(is_active=True, is_deleted=False).count()


class ScreeningReport(BaseModel):
    """
    Final screening report for one encounter (pre-employment or pre-admission).
    Compiled after lab and imaging results are back; doctor completes and signs.
    """
    RESULT_CHOICES = [
        ('fit', 'Fit'),
        ('unfit', 'Unfit'),
        ('fit_with_restrictions', 'Fit with restrictions'),
        ('pending', 'Pending review'),
    ]

    encounter = models.OneToOneField(
        Encounter,
        on_delete=models.CASCADE,
        related_name='screening_report',
        help_text='The encounter this report belongs to'
    )
    template_used = models.ForeignKey(
        ScreeningCheckTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )

    # Overall outcome
    overall_result = models.CharField(
        max_length=30,
        choices=RESULT_CHOICES,
        default='pending'
    )
    result_notes = models.TextField(
        blank=True,
        help_text='Explanation for fit/unfit or restrictions'
    )

    # Structured summary (can be auto-filled from results, then edited)
    lab_summary = models.TextField(
        blank=True,
        help_text='Summary of laboratory findings'
    )
    imaging_summary = models.TextField(
        blank=True,
        help_text='Summary of imaging/radiology findings'
    )
    physical_exam_notes = models.TextField(
        blank=True,
        help_text='Physical examination findings'
    )
    general_remarks = models.TextField(
        blank=True,
        help_text='Any other remarks for employer/school'
    )
    recommended_actions = models.TextField(
        blank=True,
        help_text='Follow-up or recommendations'
    )

    # Optional: employer/school details for letterhead
    requesting_organization = models.CharField(max_length=255, blank=True)
    requesting_contact = models.CharField(max_length=255, blank=True)

    reported_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='screening_reports_authored'
    )
    reported_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='screening_reports_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-reported_at', '-created']
        verbose_name = 'Screening report'
        verbose_name_plural = 'Screening reports'

    def __str__(self):
        return f"Screening report: {self.encounter.patient.full_name} - {self.get_overall_result_display()}"

    @property
    def patient(self):
        return self.encounter.patient
