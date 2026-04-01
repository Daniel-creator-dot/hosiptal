"""
Diagnosis and ICD-10 Code Models
WHO International Classification of Diseases (ICD-10) support
Tuned for Africa, especially Ghana
"""
from django.db import models
from django.contrib.auth.models import User
from .models import BaseModel


class DiagnosisCode(BaseModel):
    """
    ICD-10 Diagnosis Codes Bank
    WHO International Classification of Diseases, 10th Revision
    """
    CATEGORY_CHOICES = [
        ('infectious', 'Infectious and Parasitic Diseases'),
        ('neoplasms', 'Neoplasms'),
        ('blood', 'Diseases of Blood and Blood-forming Organs'),
        ('endocrine', 'Endocrine, Nutritional and Metabolic Diseases'),
        ('mental', 'Mental and Behavioral Disorders'),
        ('nervous', 'Diseases of the Nervous System'),
        ('eye', 'Diseases of the Eye and Adnexa'),
        ('ear', 'Diseases of the Ear and Mastoid Process'),
        ('circulatory', 'Diseases of the Circulatory System'),
        ('respiratory', 'Diseases of the Respiratory System'),
        ('digestive', 'Diseases of the Digestive System'),
        ('skin', 'Diseases of the Skin and Subcutaneous Tissue'),
        ('musculoskeletal', 'Diseases of the Musculoskeletal System'),
        ('genitourinary', 'Diseases of the Genitourinary System'),
        ('pregnancy', 'Pregnancy, Childbirth and the Puerperium'),
        ('perinatal', 'Conditions Originating in the Perinatal Period'),
        ('congenital', 'Congenital Malformations'),
        ('symptoms', 'Symptoms, Signs and Abnormal Clinical Findings'),
        ('injury', 'Injury, Poisoning and External Causes'),
        ('external', 'External Causes of Morbidity'),
        ('other', 'Other Factors'),
    ]
    
    code = models.CharField(max_length=10, unique=True, db_index=True, 
                           help_text="ICD-10 Code (e.g., J18.9)")
    description = models.CharField(max_length=500, 
                                  help_text="Full description of the diagnosis")
    short_description = models.CharField(max_length=200, blank=True,
                                         help_text="Short/Common name")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, 
                               db_index=True)
    chapter = models.CharField(max_length=10, blank=True, 
                              help_text="ICD-10 Chapter (e.g., J00-J99)")
    is_common = models.BooleanField(default=False, db_index=True,
                                   help_text="Mark as commonly used diagnosis")
    is_active = models.BooleanField(default=True, db_index=True)
    usage_count = models.IntegerField(default=0, 
                                     help_text="Track how often this code is used")
    
    # Track who created and updated this diagnosis code
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnosis_codes_created',
        help_text="User who added this diagnosis code to the system"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnosis_codes_updated',
        help_text="User who last updated this diagnosis code"
    )
    
    # Ghana/Africa-specific fields
    is_ghana_common = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Commonly seen in Ghana healthcare settings"
    )
    is_africa_common = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Commonly seen in African healthcare settings"
    )
    local_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Local/Ghanaian name for this condition (if applicable)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this diagnosis in Ghana context"
    )
    
    class Meta:
        ordering = ['code']
        verbose_name = "Diagnosis Code (ICD-10)"
        verbose_name_plural = "Diagnosis Codes (ICD-10)"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['category', 'is_common']),
            models.Index(fields=['is_active', 'is_common']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.short_description or self.description}"
    
    def increment_usage(self):
        """Increment usage counter when diagnosis is used"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])
    
    @classmethod
    def get_common_diagnoses(cls):
        """Get frequently used diagnoses"""
        return cls.objects.filter(
            is_active=True, 
            is_deleted=False, 
            is_common=True
        ).order_by('code')
    
    @classmethod
    def get_by_category(cls, category):
        """Get diagnoses by category"""
        return cls.objects.filter(
            is_active=True,
            is_deleted=False,
            category=category
        ).order_by('code')
    
    @classmethod
    def search(cls, query):
        """Search diagnoses by code or description"""
        from django.db.models import Q
        return cls.objects.filter(
            Q(code__icontains=query) | 
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(local_name__icontains=query),
            is_active=True,
            is_deleted=False
        ).order_by('-is_ghana_common', '-is_africa_common', '-is_common', 'code')[:50]
    
    @classmethod
    def get_ghana_common(cls):
        """Get diagnoses commonly seen in Ghana"""
        return cls.objects.filter(
            is_active=True,
            is_deleted=False,
            is_ghana_common=True
        ).order_by('code')
    
    @classmethod
    def get_africa_common(cls):
        """Get diagnoses commonly seen in Africa"""
        return cls.objects.filter(
            is_active=True,
            is_deleted=False,
            is_africa_common=True
        ).order_by('code')
    
    def save(self, *args, **kwargs):
        """Override save to track who updated"""
        # If this is an update and updated_by is not set, try to get from kwargs
        if self.pk and not self.updated_by:
            # Will be set by views/admin
            pass
        super().save(*args, **kwargs)



























