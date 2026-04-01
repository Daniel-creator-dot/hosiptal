"""
Lab-specific management models: Equipment, Reagents, and Quality Control
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import BaseModel, Staff, Department


class LabEquipment(BaseModel):
    """Laboratory equipment and analyzers"""
    EQUIPMENT_TYPES = [
        ('analyzer', 'Analyzer'),
        ('centrifuge', 'Centrifuge'),
        ('microscope', 'Microscope'),
        ('incubator', 'Incubator'),
        ('refrigerator', 'Refrigerator/Freezer'),
        ('autoclave', 'Autoclave'),
        ('water_bath', 'Water Bath'),
        ('balance', 'Balance/Scale'),
        ('pcr', 'PCR Machine'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('in_use', 'In Use'),
        ('maintenance', 'Under Maintenance'),
        ('calibration', 'Calibration Due'),
        ('out_of_order', 'Out of Order'),
        ('reserved', 'Reserved'),
    ]
    
    equipment_code = models.CharField(max_length=50, unique=True, help_text="Unique equipment identifier")
    name = models.CharField(max_length=200)
    equipment_type = models.CharField(max_length=20, choices=EQUIPMENT_TYPES)
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, unique=True, null=True)
    location = models.CharField(max_length=100, help_text="Lab section or room")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='operational')
    
    # Purchase and warranty
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Maintenance tracking
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance_due = models.DateField(null=True, blank=True)
    last_calibration = models.DateField(null=True, blank=True)
    next_calibration_due = models.DateField(null=True, blank=True)
    calibration_interval_days = models.IntegerField(default=90, help_text="Days between calibrations")
    
    # Usage tracking
    total_tests_run = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_equipment')
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Lab Equipment"
    
    def __str__(self):
        return f"{self.name} ({self.equipment_code})"
    
    @property
    def is_available(self):
        return self.status == 'operational'
    
    @property
    def needs_maintenance(self):
        if not self.next_maintenance_due:
            return False
        return timezone.now().date() >= self.next_maintenance_due
    
    @property
    def needs_calibration(self):
        if not self.next_calibration_due:
            return False
        return timezone.now().date() >= self.next_calibration_due
    
    @property
    def days_until_calibration(self):
        if not self.next_calibration_due:
            return None
        delta = self.next_calibration_due - timezone.now().date()
        return delta.days


class EquipmentMaintenanceLog(BaseModel):
    """Maintenance and calibration records for lab equipment"""
    MAINTENANCE_TYPES = [
        ('preventive', 'Preventive Maintenance'),
        ('corrective', 'Corrective Maintenance'),
        ('calibration', 'Calibration'),
        ('repair', 'Repair'),
        ('inspection', 'Inspection'),
    ]
    
    equipment = models.ForeignKey(LabEquipment, on_delete=models.CASCADE, related_name='maintenance_logs')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    service_date = models.DateField()
    service_provider = models.CharField(max_length=100, blank=True, help_text="Internal staff or external vendor")
    technician = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_work')
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    next_service_due = models.DateField(null=True, blank=True)
    is_calibration = models.BooleanField(default=False)
    calibration_certificate = models.FileField(upload_to='lab/calibration_certs/', null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-service_date']
        verbose_name_plural = "Equipment Maintenance Logs"
    
    def __str__(self):
        return f"{self.equipment.name} - {self.get_maintenance_type_display()} - {self.service_date}"


class LabReagent(BaseModel):
    """Laboratory reagents and consumables inventory"""
    CATEGORIES = [
        ('reagent', 'Reagent'),
        ('control', 'Control Material'),
        ('calibrator', 'Calibrator'),
        ('consumable', 'Consumable'),
        ('media', 'Culture Media'),
        ('stain', 'Stain'),
        ('buffer', 'Buffer'),
        ('other', 'Other'),
    ]
    
    item_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='reagent')
    manufacturer = models.CharField(max_length=100, blank=True)
    catalog_number = models.CharField(max_length=100, blank=True)
    
    # Link to procurement/inventory system (optional - for reagents added via procurement)
    # Using UUID field to link to InventoryItem without foreign key (avoids circular import)
    inventory_item_id = models.UUIDField(null=True, blank=True, help_text="Link to InventoryItem if added via procurement")
    
    # Inventory tracking
    quantity_on_hand = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=20, default='bottle', help_text="bottle, box, pack, etc.")
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier = models.CharField(max_length=100, blank=True)
    
    # Expiry tracking
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    storage_conditions = models.CharField(max_length=200, blank=True, help_text="e.g., 2-8°C, Room Temperature")
    location = models.CharField(max_length=100, blank=True, help_text="Storage location in lab")
    
    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    total_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Link to lab tests that use this reagent
    tests = models.ManyToManyField('LabTest', related_name='required_reagents', blank=True, 
                                   help_text="Lab tests that require this reagent")
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Lab Reagents"
    
    def __str__(self):
        return f"{self.name} ({self.item_code})"
    
    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.reorder_level
    
    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return timezone.now().date() > self.expiry_date
    
    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        days_until_expiry = (self.expiry_date - timezone.now().date()).days
        return 0 <= days_until_expiry <= 30
    
    @property
    def stock_value(self):
        if self.unit_cost and self.quantity_on_hand:
            return self.unit_cost * self.quantity_on_hand
        return Decimal('0.00')
    
    @property
    def inventory_item(self):
        """Get linked inventory item if exists"""
        if self.inventory_item_id:
            try:
                from .models_procurement import InventoryItem
                return InventoryItem.objects.get(pk=self.inventory_item_id, is_deleted=False)
            except:
                return None
        return None


class ReagentTransaction(BaseModel):
    """Track reagent usage and stock movements with full accountability"""
    TRANSACTION_TYPES = [
        ('received', 'Received'),
        ('used', 'Used'),
        ('adjusted', 'Stock Adjustment'),
        ('expired', 'Expired/Discarded'),
        ('transferred', 'Transferred'),
    ]
    
    reagent = models.ForeignKey(LabReagent, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    performed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="PO number, test ID, etc.")
    notes = models.TextField(blank=True)
    
    # Accountability fields - Required when used by lab tech
    patient = models.ForeignKey('Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='reagent_usage', help_text="Patient for whom reagent was used")
    lab_result = models.ForeignKey('LabResult', on_delete=models.SET_NULL, null=True, blank=True, related_name='reagent_transactions', help_text="Lab result/test for which reagent was used")
    purpose = models.TextField(blank=True, help_text="Purpose/clinical indication for reagent usage")
    test_name = models.CharField(max_length=200, blank=True, help_text="Name of test performed (for quick reference)")
    
    class Meta:
        ordering = ['-created']
        verbose_name_plural = "Reagent Transactions"
    
    def __str__(self):
        return f"{self.reagent.name} - {self.get_transaction_type_display()} - {self.quantity} {self.reagent.unit}"


class QualityControlTest(BaseModel):
    """Quality control test results for lab equipment"""
    QC_TYPES = [
        ('daily', 'Daily QC'),
        ('weekly', 'Weekly QC'),
        ('monthly', 'Monthly QC'),
        ('calibration', 'Calibration QC'),
        ('proficiency', 'Proficiency Testing'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
    ]
    
    equipment = models.ForeignKey(LabEquipment, on_delete=models.CASCADE, related_name='qc_tests')
    qc_type = models.CharField(max_length=20, choices=QC_TYPES, default='daily')
    test_date = models.DateField(default=timezone.now)
    test_time = models.TimeField(default=timezone.now)
    
    # Control material used
    control_material = models.ForeignKey(LabReagent, on_delete=models.SET_NULL, null=True, blank=True, 
                                        limit_choices_to={'category': 'control'})
    batch_number = models.CharField(max_length=100, blank=True)
    
    # Test parameters
    test_name = models.CharField(max_length=200, help_text="Name of the QC test/parameter")
    expected_value = models.CharField(max_length=100, blank=True, help_text="Expected/Mean value")
    observed_value = models.CharField(max_length=100, blank=True, help_text="Observed/Measured value")
    units = models.CharField(max_length=20, blank=True)
    
    # QC rules (Westgard rules)
    within_range = models.BooleanField(default=True)
    rule_1_2s = models.BooleanField(default=False, help_text="1-2s rule violation")
    rule_1_3s = models.BooleanField(default=False, help_text="1-3s rule violation")
    rule_2_2s = models.BooleanField(default=False, help_text="2-2s rule violation")
    rule_r_4s = models.BooleanField(default=False, help_text="R-4s rule violation")
    rule_4_1s = models.BooleanField(default=False, help_text="4-1s rule violation")
    rule_10x = models.BooleanField(default=False, help_text="10x rule violation")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Staff
    performed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='qc_tests_performed')
    reviewed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='qc_tests_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Actions taken
    corrective_action = models.TextField(blank=True, help_text="Action taken if QC failed")
    equipment_status_after_qc = models.CharField(max_length=20, choices=LabEquipment.STATUS_CHOICES, 
                                                 default='operational', help_text="Equipment status after QC")
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-test_date', '-test_time']
        verbose_name_plural = "Quality Control Tests"
        indexes = [
            models.Index(fields=['equipment', 'test_date']),
            models.Index(fields=['status', 'test_date']),
        ]
    
    def __str__(self):
        return f"{self.equipment.name} - {self.test_name} - {self.test_date}"
    
    @property
    def has_violations(self):
        return any([
            self.rule_1_2s, self.rule_1_3s, self.rule_2_2s,
            self.rule_r_4s, self.rule_4_1s, self.rule_10x
        ])
    
    @property
    def is_critical_failure(self):
        return any([self.rule_1_3s, self.rule_2_2s, self.rule_r_4s, self.rule_4_1s])
    
    def save(self, *args, **kwargs):
        # Auto-determine status based on QC rules
        if self.has_violations:
            if self.is_critical_failure:
                self.status = 'failed'
            else:
                self.status = 'warning'
        elif self.within_range and not self.has_violations:
            self.status = 'passed'
        
        super().save(*args, **kwargs)


class QCAlert(BaseModel):
    """Alerts for QC failures and equipment issues"""
    ALERT_TYPES = [
        ('qc_failure', 'QC Test Failed'),
        ('calibration_due', 'Calibration Due'),
        ('maintenance_due', 'Maintenance Due'),
        ('reagent_low', 'Reagent Low Stock'),
        ('reagent_expired', 'Reagent Expired'),
        ('equipment_down', 'Equipment Out of Order'),
    ]
    
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    equipment = models.ForeignKey(LabEquipment, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    reagent = models.ForeignKey(LabReagent, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    qc_test = models.ForeignKey(QualityControlTest, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Notification
    notified_staff = models.ManyToManyField(Staff, blank=True, related_name='qc_alerts_received')
    
    class Meta:
        ordering = ['-created', 'priority']
        verbose_name_plural = "QC Alerts"
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.title}"










