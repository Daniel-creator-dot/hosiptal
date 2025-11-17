"""
Django signals for Hospital Management System
Handles automated tasks and notifications
"""
from django.db.models.signals import post_save, pre_save
from django.db.models import Sum, F
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import (
    Admission, InvoiceLine, Appointment, LabResult, Invoice, Prescription, Encounter, VitalSign, Order,
    PharmacyStock, UserSession, Patient, PatientQRCode
)
from .models_advanced import SMSLog
from .services.sms_service import sms_service


@receiver(post_save, sender=Admission)
def handle_admission_save(sender, instance, created, **kwargs):
    """Handle bed occupancy when admission is created/updated"""
    if created:
        # Occupy bed when admission is created
        if instance.bed and instance.bed.status == 'available':
            instance.bed.occupy()
    elif instance.status == 'discharged' and instance.bed:
        # Vacate bed when patient is discharged
        if instance.bed.status == 'occupied':
            instance.bed.vacate()


@receiver(post_save, sender=InvoiceLine)
def handle_invoice_line_save(sender, instance, created, **kwargs):
    """Recalculate invoice totals when line items are added/updated"""
    if instance.invoice:
        instance.invoice.calculate_totals()
        instance.invoice.save()


@receiver(post_save, sender=Appointment)
def handle_appointment_created(sender, instance, created, **kwargs):
    """
    Send SMS reminder when appointment is created
    NOTE: This signal sends a simple reminder. 
    The view should handle booking confirmation SMS with confirmation link.
    To avoid duplicate SMS, we skip if appointment was just created via form (view handles it)
    """
    # Skip if this is a signal from form save (view will handle SMS)
    # Only send reminder if created programmatically (API, admin, etc.)
    if created and instance.patient.phone_number:
        # Check if we should skip (to avoid duplicate with view)
        # The view will send booking confirmation SMS, so we skip the signal reminder
        # Only send if explicitly needed (e.g., created via admin or API without view handling)
        try:
            # Only send basic reminder if not handled by view
            # View handles booking confirmation with link, so we skip here
            pass  # Disabled to avoid duplicate SMS - view handles it
            # sms_service.send_appointment_reminder(instance)
        except Exception as e:
            # Log error but don't fail the appointment creation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send appointment reminder SMS: {e}")


@receiver(post_save, sender=LabResult)
def handle_lab_result_ready(sender, instance, created, **kwargs):
    """Send SMS notification when lab result is verified"""
    if instance.status == 'verified' and instance.order and instance.order.encounter:
        patient = instance.order.encounter.patient
        if patient and patient.phone_number:
            try:
                sms_service.send_lab_result_ready(instance)
            except Exception as e:
                print(f"Failed to send lab result SMS: {e}")


@receiver(post_save, sender=Invoice)
def handle_invoice_overdue(sender, instance, **kwargs):
    """Send payment reminder when invoice becomes overdue"""
    from django.utils import timezone
    
    if instance.status == 'overdue' and instance.balance > 0:
        patient = instance.patient
        if patient and patient.phone_number:
            try:
                sms_service.send_payment_reminder(instance)
            except Exception as e:
                print(f"Failed to send payment reminder SMS: {e}")


@receiver(post_save, sender=Patient)
def ensure_patient_qr_profile(sender, instance, created, **kwargs):
    """Automatically provision patient QR credentials"""
    if instance.is_deleted:
        return
    
    qr_profile, _ = PatientQRCode.objects.get_or_create(patient=instance)
    needs_refresh = created or not qr_profile.qr_token or not qr_profile.qr_code_image
    if needs_refresh:
        qr_profile.refresh_qr(force_token=True)
    else:
        qr_profile.save(update_fields=['modified'])


@receiver(post_save, sender=Prescription)
def handle_prescription_created(sender, instance, created, **kwargs):
    """Update encounter activity when doctor prescribes medication"""
    if created and instance.order and instance.order.encounter:
        encounter = instance.order.encounter
        if encounter.status == 'active':
            encounter.update_activity('consulting')
            # Update notes to track prescription
            prescription_note = f"\n[Consulting] Prescription issued: {instance.drug.name} - {instance.dose} {instance.frequency} ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
            if not encounter.notes or '[Consulting]' not in encounter.notes:
                encounter.notes = (encounter.notes or '') + prescription_note
                encounter.save(update_fields=['notes'])


@receiver(post_save, sender=LabResult)
def handle_lab_result_activity(sender, instance, created, **kwargs):
    """Update encounter activity when lab processes results"""
    if instance.order and instance.order.encounter:
        encounter = instance.order.encounter
        if encounter.status == 'active':
            if created:
                # Lab work started
                encounter.update_activity('lab')
                lab_note = f"\n[Lab] Test ordered: {instance.test.name} - Status: {instance.get_status_display()} ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
                if not encounter.notes or f'[Lab] {instance.test.name}' not in encounter.notes:
                    encounter.notes = (encounter.notes or '') + lab_note
                    encounter.save(update_fields=['notes'])
            elif instance.status == 'completed':
                # Lab work completed
                encounter.update_activity('lab')
                lab_note = f"\n[Lab] Test completed: {instance.test.name} - Result: {instance.value} {instance.units} ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
                encounter.notes = (encounter.notes or '') + lab_note
                encounter.save(update_fields=['notes'])


@receiver(post_save, sender=Order)
def handle_pharmacy_order(sender, instance, created, **kwargs):
    """Update encounter activity when pharmacy order is processed"""
    if instance.order_type == 'medication' and instance.encounter:
        encounter = instance.encounter
        if encounter.status == 'active' and instance.status == 'completed':
            # Pharmacy dispensed medication
            encounter.update_activity('pharmacy')
            pharmacy_note = f"\n[Pharmacy] Medication dispensed - Order #{instance.id} ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
            encounter.notes = (encounter.notes or '') + pharmacy_note
            encounter.save(update_fields=['notes'])


@receiver(post_save, sender=VitalSign)
def handle_vitals_recorded(sender, instance, created, **kwargs):
    """Update encounter notes when vitals are recorded"""
    if created and instance.encounter and instance.encounter.status == 'active':
        encounter = instance.encounter
        vitals_summary = f"BP: {instance.systolic_bp}/{instance.diastolic_bp}" if instance.systolic_bp else ""
        if instance.pulse:
            vitals_summary += f", Pulse: {instance.pulse}"
        if instance.temperature:
            vitals_summary += f", Temp: {instance.temperature}°C"
        
        if vitals_summary:
            vitals_note = f"\n[Vitals] {vitals_summary} ({instance.recorded_at.strftime('%Y-%m-%d %H:%M')})"
            encounter.notes = (encounter.notes or '') + vitals_note
            encounter.save(update_fields=['notes'])


@receiver(post_save, sender=PharmacyStock)
def sync_pharmacy_stock_to_inventory(sender, instance, created, **kwargs):
    """Sync PharmacyStock to InventoryItem for unified inventory tracking"""
    if instance.is_deleted:
        return
    
    try:
        from .models_procurement import Store, InventoryItem
        
        # Find or create pharmacy store
        pharmacy_store = Store.objects.filter(
            store_type='pharmacy',
            name__icontains='pharmacy'
        ).first()
        
        if not pharmacy_store:
            # Create a default pharmacy store if it doesn't exist
            from .models import Department
            pharmacy_dept = Department.objects.filter(name__icontains='pharmacy').first()
            pharmacy_store = Store.objects.create(
                name='Pharmacy Store',
                code='PHARM',
                store_type='pharmacy',
                department=pharmacy_dept,
                is_active=True
            )
        
        # Get or create inventory item for this drug
        inventory_item = InventoryItem.objects.filter(
            store=pharmacy_store,
            drug=instance.drug,
            is_deleted=False
        ).first()
        
        # Get or create pharmacy category
        from .models_procurement import InventoryCategory
        pharmacy_category = InventoryCategory.objects.filter(
            is_for_pharmacy=True,
            is_active=True
        ).first()
        
        if not pharmacy_category:
            pharmacy_category = InventoryCategory.objects.create(
                name='Pharmacy / Pharmaceuticals',
                code='PHARM',
                is_for_pharmacy=True,
                display_order=1,
                is_active=True,
                description='Pharmaceuticals, drugs, and medications'
            )
        
        if inventory_item:
            # Update existing inventory item
            # Ensure category is set
            if not inventory_item.category:
                inventory_item.category = pharmacy_category
            
            # Aggregate quantities from all PharmacyStock batches for this drug
            total_quantity = PharmacyStock.objects.filter(
                drug=instance.drug,
                is_deleted=False
            ).aggregate(
                total=Sum('quantity_on_hand')
            )['total'] or 0
            
            # Calculate weighted average cost
            total_cost = PharmacyStock.objects.filter(
                drug=instance.drug,
                is_deleted=False
            ).aggregate(
                total=Sum(F('quantity_on_hand') * F('unit_cost'))
            )['total'] or 0
            
            inventory_item.quantity_on_hand = total_quantity
            inventory_item.unit_cost = total_cost / total_quantity if total_quantity > 0 else inventory_item.unit_cost
            inventory_item.reorder_level = instance.reorder_level
            inventory_item.save()
        else:
            # Create new inventory item (item_code will be auto-generated by save() method)
            inventory_item = InventoryItem.objects.create(
                store=pharmacy_store,
                category=pharmacy_category,
                drug=instance.drug,
                item_name=f"{instance.drug.name} {instance.drug.strength} {instance.drug.form}",
                item_code='',  # Will be auto-generated by save() method
                description=f"{instance.drug.name} - {instance.drug.generic_name or ''}",
                quantity_on_hand=total_quantity,
                reorder_level=instance.reorder_level,
                unit_cost=avg_cost,
                unit_of_measure=instance.drug.form or 'units',
                is_active=True
            )
    except Exception as e:
        # Don't fail if syncing fails - log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync PharmacyStock to InventoryItem: {e}")
