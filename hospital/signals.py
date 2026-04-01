"""
Django signals for Hospital Management System
Handles automated tasks and notifications
"""
from django.db.models.signals import post_save, pre_save
from django.db.models import Sum, F, Q
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import (
    Admission, InvoiceLine, Appointment, LabResult, Invoice, Prescription, Encounter, VitalSign, Order,
    PharmacyStock, UserSession, Patient, PatientQRCode, LabTest, Drug, ServiceCode
)
from .models_advanced import SMSLog
from .services.sms_service import sms_service
import json
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def _invalidate_pricing_catalog_cache():
    """Ensure UI picks latest catalog prices immediately after updates."""
    try:
        from django.core.cache import cache
        cache.delete('hms:active_lab_tests')
        cache.delete('hms:active_drugs')
    except Exception:
        pass


def _sync_catalog_price_to_flexible_pricing(service_code, new_price):
    """
    Keep flexible pricing in sync with catalog prices.
    Enforces updated catalog prices across all active pricing categories.
    """
    if service_code is None:
        return
    try:
        from .models_flexible_pricing import PricingCategory, ServicePrice
    except Exception:
        return

    today = timezone.now().date()
    categories = PricingCategory.objects.filter(
        is_active=True,
        is_deleted=False,
    )

    for category in categories:
        current = (
            ServicePrice.objects.filter(
                service_code=service_code,
                pricing_category=category,
                is_active=True,
                is_deleted=False,
                effective_from__lte=today,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .order_by('-effective_from')
            .first()
        )
        if current:
            if current.price != new_price:
                current.price = new_price
                current.save(update_fields=['price', 'modified'])
            continue

        ServicePrice.objects.create(
            service_code=service_code,
            pricing_category=category,
            price=new_price,
            effective_from=today,
            is_active=True,
        )


@receiver(post_save, sender=LabTest)
def sync_labtest_price_to_pricing_engine(sender, instance, **kwargs):
    """When lab catalog price changes, enforce it across pricing engine records."""
    if instance.is_deleted or not instance.is_active:
        return
    if instance.price is None:
        return

    service_code, _ = ServiceCode.objects.get_or_create(
        code=f"LAB-{instance.code}",
        defaults={
            'description': instance.name,
            'category': 'Laboratory',
            'is_active': True,
        },
    )
    updates = []
    if service_code.description != instance.name:
        service_code.description = instance.name
        updates.append('description')
    if (service_code.category or '').strip().lower() != 'laboratory':
        service_code.category = 'Laboratory'
        updates.append('category')
    if not service_code.is_active:
        service_code.is_active = True
        updates.append('is_active')
    if updates:
        service_code.save(update_fields=updates + ['modified'])

    _sync_catalog_price_to_flexible_pricing(service_code, instance.price)
    _invalidate_pricing_catalog_cache()


@receiver(post_save, sender=Drug)
def sync_drug_price_to_pricing_engine(sender, instance, **kwargs):
    """When drug unit price changes, enforce it across pricing engine records."""
    if instance.is_deleted or not instance.is_active:
        return
    unit_price = getattr(instance, 'unit_price', None)
    if unit_price is None:
        return

    drug_code = getattr(instance, 'code', None) or str(instance.id)
    service_code, _ = ServiceCode.objects.get_or_create(
        code=f"DRUG-{drug_code}",
        defaults={
            'description': instance.name,
            'category': 'Pharmacy',
            'is_active': True,
        },
    )
    updates = []
    if service_code.description != instance.name:
        service_code.description = instance.name
        updates.append('description')
    if (service_code.category or '').strip().lower() != 'pharmacy':
        service_code.category = 'Pharmacy'
        updates.append('category')
    if not service_code.is_active:
        service_code.is_active = True
        updates.append('is_active')
    if updates:
        service_code.save(update_fields=updates + ['modified'])

    _sync_catalog_price_to_flexible_pricing(service_code, unit_price)
    _invalidate_pricing_catalog_cache()


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
    """Send SMS to patient and in-app notification to ordering doctor, nurses, and front desk when lab result is complete"""
    if instance.status not in ('completed', 'verified'):
        return
    if not instance.order or not instance.order.encounter:
        return

    patient = instance.order.encounter.patient
    test_name = instance.test.name if instance.test else 'Lab test'
    patient_name = patient.full_name if patient else 'Unknown'

    # SMS to patient when status is verified (legacy) or completed
    if patient and getattr(patient, 'phone_number', None):
        try:
            sms_service.send_lab_result_ready(instance)
        except Exception as e:
            logger.warning(f"Failed to send lab result SMS: {e}")

    # In-app notification to: ordering doctor, all nurses, and front desk (receptionists)
    try:
        from .models import Notification, Staff
        recent = timezone.now() - timedelta(hours=1)
        obj_id_str = str(instance.id)
        message = f'Lab result for {test_name} is ready for patient {patient_name}.'
        title = 'Lab Result Ready'

        def already_notified(user_id):
            return Notification.objects.filter(
                recipient_id=user_id,
                notification_type='lab_result_ready',
                related_object_id=obj_id_str,
                related_object_type='LabResult',
                created__gte=recent,
                is_deleted=False,
            ).exists()

        def create_notification_for_user(user):
            if not user or not user.pk or already_notified(user.pk):
                return
            Notification.objects.create(
                recipient=user,
                notification_type='lab_result_ready',
                title=title,
                message=message,
                related_object_id=instance.id,
                related_object_type='LabResult',
            )

        # 1) Ordering doctor
        ordering_doctor = getattr(instance.order, 'requested_by', None)
        if ordering_doctor and ordering_doctor.user_id:
            create_notification_for_user(ordering_doctor.user)

        # 2) All nurses and 3) Front desk (receptionists) - active staff with user
        for staff in Staff.objects.filter(
            is_deleted=False,
            user__isnull=False,
            profession__in=('nurse', 'receptionist', 'doctor'),
        ).select_related('user'):
            if not staff.user_id:
                continue
            # Avoid duplicate for ordering doctor (already notified above)
            if ordering_doctor and staff.pk == ordering_doctor.pk:
                continue
            create_notification_for_user(staff.user)
    except Exception as e:
        logger.warning(f"Failed to create lab result notifications: {e}", exc_info=True)


def _notify_doctor_imaging_result_ready(sender, instance, **kwargs):
    """Notify ordering doctor when imaging study report is complete"""
    if instance.status not in ('reported', 'verified'):
        return
    try:
        from .models import Notification
        ordering_doctor = None
        if instance.order and instance.order.requested_by_id:
            ordering_doctor = instance.order.requested_by
        if ordering_doctor and ordering_doctor.user_id:
            recent = timezone.now() - timedelta(hours=1)
            if Notification.objects.filter(
                recipient=ordering_doctor.user,
                notification_type='imaging_result_ready',
                related_object_id=str(instance.id),
                related_object_type='ImagingStudy',
                created__gte=recent,
                is_deleted=False,
            ).exists():
                return
            patient_name = instance.patient.full_name if instance.patient else 'Unknown'
            Notification.objects.create(
                recipient=ordering_doctor.user,
                notification_type='imaging_result_ready',
                title='Imaging Result Ready',
                message=f'Imaging report ({instance.get_modality_display()} - {instance.body_part}) is ready for patient {patient_name}.',
                related_object_id=str(instance.id),
                related_object_type='ImagingStudy',
            )
    except Exception as e:
        logger.warning(f"Failed to create imaging result notification for doctor: {e}")


try:
    from .models_advanced import ImagingStudy
    post_save.connect(_notify_doctor_imaging_result_ready, sender=ImagingStudy)
except ImportError:
    pass


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
    import logging
    logger = logging.getLogger(__name__)
    
    if instance.is_deleted:
        return
    
    try:
        qr_profile, profile_created = PatientQRCode.objects.get_or_create(patient=instance)
        needs_refresh = profile_created or not qr_profile.qr_token or not qr_profile.qr_code_image or not qr_profile.qr_code_data
        
        if needs_refresh:
            logger.info(f"[QR SIGNAL] Generating QR code for patient {instance.mrn} (created: {created}, profile_created: {profile_created})")
            qr_profile.refresh_qr(force_token=True)
            logger.info(f"[QR SIGNAL] QR code generated successfully for patient {instance.mrn}")
        else:
            qr_profile.save(update_fields=['modified'])
    except Exception as e:
        logger.error(f"[QR SIGNAL] Failed to create/generate QR code for patient {instance.mrn}: {str(e)}", exc_info=True)
        # Don't raise - allow patient creation to succeed even if QR generation fails


@receiver(post_save, sender=Prescription)
def handle_prescription_created(sender, instance, created, **kwargs):
    """Update encounter activity when doctor prescribes medication"""
    if created:
        try:
            from hospital.consultation_batch import skip_prescription_encounter_note
            if skip_prescription_encounter_note():
                return
        except Exception:
            pass
        try:
            if instance.order and instance.order.encounter:
                encounter = instance.order.encounter
                if encounter.status == 'active':
                    encounter.update_activity('consulting')
                    # Update notes to track prescription
                    drug_name = getattr(instance.drug, 'name', 'Unknown drug')[:50]
                    dose = getattr(instance, 'dose', '')[:50]
                    frequency = getattr(instance, 'frequency', '')[:50]
                    # Use module-level timezone import (line 8)
                    prescription_note = f"\n[Consulting] Prescription issued: {drug_name} - {dose} {frequency} ({timezone.now().strftime('%Y-%m-%d %H:%M')})"
                    if not encounter.notes or '[Consulting]' not in encounter.notes:
                        encounter.notes = (encounter.notes or '') + prescription_note
                        encounter.save(update_fields=['notes'])
        except Exception as e:
            # Don't let activity tracking break prescription creation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error updating encounter activity for prescription {instance.id}: {str(e)}")


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


@receiver(post_save, sender=LabResult)
def handle_lab_result_reagent_consumption(sender, instance, created, **kwargs):
    """Auto-consume required reagents when a lab result is completed."""
    if instance.status != 'completed':
        return
    try:
        from .services.lab_reagent_usage_service import consume_reagents_for_completed_lab_result

        consume_reagents_for_completed_lab_result(
            instance,
            performed_by=getattr(instance, 'verified_by', None),
        )
    except Exception as e:
        logger.warning(f"Auto reagent consumption failed for lab result {instance.id}: {e}")


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


@receiver(post_save, sender=Encounter)
def create_consultation_charge_on_visit(sender, instance, created, **kwargs):
    """
    Consultation and registration fees are NOT added automatically.
    Staff add them via Add Services / Add Manual Payment when applicable.
    (Previously: auto-created consultation charge on encounter creation — disabled by request.)
    """
    return


@receiver(post_save, sender=VitalSign)
def handle_vitals_recorded(sender, instance, created, **kwargs):
    """Update encounter notes when vitals are recorded"""
    if created and instance.encounter and instance.encounter.status == 'active':
        encounter = instance.encounter
        vitals_parts = []
        
        # Only add BP if both systolic and diastolic are valid
        if instance.systolic_bp is not None and instance.diastolic_bp is not None:
            vitals_parts.append(f"BP: {instance.systolic_bp}/{instance.diastolic_bp}")
        if instance.pulse is not None:
            vitals_parts.append(f"Pulse: {instance.pulse}")
        if instance.temperature is not None:
            vitals_parts.append(f"Temp: {instance.temperature}°C")
        
        if vitals_parts:
            vitals_summary = ", ".join(vitals_parts)
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
        
        # Aggregate quantities from all PharmacyStock batches for this drug
        total_quantity = PharmacyStock.objects.filter(
            drug=instance.drug,
            is_deleted=False
        ).aggregate(
            total=Sum('quantity_on_hand')
        )['total'] or 0
        
        # InventoryItem does not allow negative - clamp for sync (PharmacyStock can be negative for shortfalls)
        sync_quantity = max(0, total_quantity)
        
        # Calculate weighted average cost (only from positive stock for cost calc)
        total_cost = PharmacyStock.objects.filter(
            drug=instance.drug,
            is_deleted=False,
            quantity_on_hand__gt=0
        ).aggregate(
            total=Sum(F('quantity_on_hand') * F('unit_cost'))
        )['total'] or 0
        total_positive = PharmacyStock.objects.filter(
            drug=instance.drug,
            is_deleted=False,
            quantity_on_hand__gt=0
        ).aggregate(t=Sum('quantity_on_hand'))['t'] or 0
        avg_cost = total_cost / total_positive if total_positive > 0 else instance.unit_cost
        
        if inventory_item:
            # Update existing inventory item
            # Ensure category is set
            if not inventory_item.category:
                inventory_item.category = pharmacy_category
            
            inventory_item.quantity_on_hand = sync_quantity
            inventory_item.unit_cost = avg_cost
            inventory_item.reorder_level = instance.reorder_level
            inventory_item.save()
        else:
            # Check for duplicate before creating (prevent duplicates from concurrent saves)
            existing_item = InventoryItem.objects.filter(
                store=pharmacy_store,
                drug=instance.drug,
                is_deleted=False
            ).first()
            
            if not existing_item:
                # Create new inventory item (item_code will be auto-generated by save() method)
                inventory_item = InventoryItem.objects.create(
                    store=pharmacy_store,
                    category=pharmacy_category,
                    drug=instance.drug,
                    item_name=f"{instance.drug.name} {instance.drug.strength} {instance.drug.form}",
                    item_code='',  # Will be auto-generated by save() method
                    description=f"{instance.drug.name} - {instance.drug.generic_name or ''}",
                    quantity_on_hand=sync_quantity,
                    reorder_level=instance.reorder_level,
                    unit_cost=avg_cost,
                    unit_of_measure=instance.drug.form or 'units',
                    is_active=True
                )
                
                # Auto-sync to Drug Store (DRUGS) - create item there with 0 quantity
                sync_item_to_drug_store(inventory_item)
            else:
                # Duplicate found - update existing instead
                existing_item.quantity_on_hand = sync_quantity
                existing_item.unit_cost = avg_cost
                existing_item.reorder_level = instance.reorder_level
                if not existing_item.category:
                    existing_item.category = pharmacy_category
                existing_item.save()
    except Exception as e:
        # Don't fail if syncing fails - log the error
        logger.error(f"Failed to sync PharmacyStock to InventoryItem: {e}")


def sync_item_to_drug_store(pharmacy_item):
    """
    Sync an inventory item from Pharmacy Store (PHARM) to Drug Store (DRUGS)
    Creates item in Drug Store with 0 quantity if it doesn't exist
    Updates metadata if it exists (but preserves Drug Store's quantity)
    """
    try:
        from .models_procurement import Store, InventoryItem
        
        # Get Drug Store
        drug_store = Store.objects.filter(code='DRUGS', is_deleted=False).first()
        if not drug_store:
            logger.warning("Drug Store (DRUGS) not found - cannot sync item")
            return None
        
        # Check if item already exists in Drug Store
        lookup_kwargs = {
            'store': drug_store,
            'is_deleted': False
        }
        
        if pharmacy_item.item_code:
            lookup_kwargs['item_code'] = pharmacy_item.item_code
        else:
            lookup_kwargs['item_name'] = pharmacy_item.item_name
            if pharmacy_item.drug:
                lookup_kwargs['drug'] = pharmacy_item.drug
        
        existing_drug_item = InventoryItem.objects.filter(**lookup_kwargs).first()
        
        if existing_drug_item:
            # Update metadata but preserve Drug Store quantity
            existing_drug_item.item_name = pharmacy_item.item_name
            existing_drug_item.description = pharmacy_item.description
            existing_drug_item.category = pharmacy_item.category
            existing_drug_item.drug = pharmacy_item.drug
            existing_drug_item.unit_of_measure = pharmacy_item.unit_of_measure
            existing_drug_item.preferred_supplier = pharmacy_item.preferred_supplier
            existing_drug_item.reorder_level = pharmacy_item.reorder_level
            existing_drug_item.reorder_quantity = pharmacy_item.reorder_quantity
            # Don't update quantity_on_hand - keep Drug Store's quantity
            # Don't update unit_cost - keep Drug Store's cost
            existing_drug_item.is_active = pharmacy_item.is_active
            existing_drug_item.save()
            return existing_drug_item
        else:
            # Create new item in Drug Store with 0 quantity
            new_item = InventoryItem.objects.create(
                store=drug_store,
                category=pharmacy_item.category,
                item_name=pharmacy_item.item_name,
                item_code=pharmacy_item.item_code or '',
                description=pharmacy_item.description,
                drug=pharmacy_item.drug,
                quantity_on_hand=0,  # Start with 0 - quantities added when purchased
                reorder_level=pharmacy_item.reorder_level,
                reorder_quantity=pharmacy_item.reorder_quantity,
                unit_cost=pharmacy_item.unit_cost,  # Keep cost for reference
                unit_of_measure=pharmacy_item.unit_of_measure,
                preferred_supplier=pharmacy_item.preferred_supplier,
                is_active=pharmacy_item.is_active
            )
            logger.info(f"Synced item '{pharmacy_item.item_name}' to Drug Store (DRUGS)")
            return new_item
    except Exception as e:
        logger.error(f"Failed to sync item to Drug Store: {e}")
        return None


@receiver(post_save, sender='hospital.InventoryItem')
def sync_pharmacy_item_to_drug_store(sender, instance, created, **kwargs):
    """
    Auto-sync items from Pharmacy Store (PHARM) to Drug Store (DRUGS)
    When a new item is added to Pharmacy Store, create it in Drug Store with 0 quantity
    When an item in Pharmacy Store is updated, sync metadata to Drug Store
    Ensures proper linking to prevent duplicates
    """
    if instance.is_deleted:
        return
    
    try:
        from .models_procurement import Store, InventoryItem
        
        # Only sync if item is in Pharmacy Store (PHARM)
        if not hasattr(instance.store, 'code') or instance.store.code != 'PHARM':
            return
        
        # Get Drug Store
        drug_store = Store.objects.filter(code='DRUGS', is_deleted=False).first()
        if not drug_store:
            return
        
        # Check if item already exists in Drug Store using multiple lookup strategies
        lookup_kwargs = {
            'store': drug_store,
            'is_deleted': False
        }
        
        existing_item = None
        
        # Strategy 1: Match by item_code if available (most reliable)
        if instance.item_code and instance.item_code.strip():
            lookup_kwargs['item_code'] = instance.item_code
            existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
        
        # Strategy 2: Match by drug if available
        if not existing_item and instance.drug:
            lookup_kwargs = {
                'store': drug_store,
                'drug': instance.drug,
                'is_deleted': False
            }
            existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
        
        # Strategy 3: Match by exact item_name
        if not existing_item:
            lookup_kwargs = {
                'store': drug_store,
                'item_name': instance.item_name,
                'is_deleted': False
            }
            existing_item = InventoryItem.objects.filter(**lookup_kwargs).first()
        
        if existing_item:
            # Item exists - update metadata but preserve Drug Store quantity
            existing_item.item_name = instance.item_name
            existing_item.description = instance.description
            existing_item.category = instance.category
            existing_item.drug = instance.drug
            existing_item.unit_of_measure = instance.unit_of_measure
            existing_item.preferred_supplier = instance.preferred_supplier
            existing_item.reorder_level = instance.reorder_level
            existing_item.reorder_quantity = instance.reorder_quantity
            # Ensure item_code matches if Pharmacy has one
            if instance.item_code and instance.item_code.strip() and not existing_item.item_code:
                existing_item.item_code = instance.item_code
            # Don't update quantity_on_hand - keep Drug Store's quantity
            # Don't update unit_cost - keep Drug Store's cost
            existing_item.is_active = instance.is_active
            existing_item.save()
        else:
            # Item doesn't exist - create it with 0 quantity
            InventoryItem.objects.create(
                store=drug_store,
                category=instance.category,
                item_name=instance.item_name,
                item_code=instance.item_code or '',
                description=instance.description,
                drug=instance.drug,
                quantity_on_hand=0,  # Start with 0 - quantities added when purchased
                reorder_level=instance.reorder_level,
                reorder_quantity=instance.reorder_quantity,
                unit_cost=instance.unit_cost,  # Keep cost for reference
                unit_of_measure=instance.unit_of_measure,
                preferred_supplier=instance.preferred_supplier,
                is_active=instance.is_active
            )
            logger.info(f"Auto-synced item '{instance.item_name}' to Drug Store (DRUGS) with 0 quantity")
    except Exception as e:
        logger.error(f"Failed to auto-sync Pharmacy item to Drug Store: {e}")


@receiver(post_save, sender='hospital.ProcurementRequest')
def create_lab_reagent_on_procurement_received(sender, instance, **kwargs):
    """Create LabReagent when procurement request for lab reagents is received"""
    
    # Only process if status is 'received' and store is Laboratory Store
    if instance.status != 'received':
        return
    
    if not instance.requested_by_store or instance.requested_by_store.store_type not in ('laboratory', 'lab'):
        return
    
    try:
        from .models_procurement import InventoryItem
        from .models_lab_management import LabReagent
        
        # Process each item in the request
        for item in instance.items.filter(is_deleted=False):
            # Check if this is a lab reagent request (stored in specifications)
            try:
                if item.specifications:
                    metadata = json.loads(item.specifications)
                    if not metadata.get('is_lab_reagent', False):
                        continue
                else:
                    continue
            except (json.JSONDecodeError, KeyError):
                continue
            
            # Find the inventory item that was created for this procurement item
            inventory_item = InventoryItem.objects.filter(
                store=instance.requested_by_store,
                item_name=item.item_name,
                is_deleted=False
            ).first()
            
            if not inventory_item:
                continue
            
            # Check if LabReagent already exists for this inventory item
            existing_reagent = LabReagent.objects.filter(
                inventory_item_id=inventory_item.id,
                is_deleted=False
            ).first()
            
            if existing_reagent:
                # Update existing reagent
                existing_reagent.quantity_on_hand = Decimal(str(inventory_item.quantity_on_hand))
                existing_reagent.unit_cost = inventory_item.unit_cost
                existing_reagent.save()
                continue
            
            # Create new LabReagent from procurement metadata
            reagent_data = {
                'item_code': item.item_code or inventory_item.item_code,
                'name': item.item_name,
                'category': metadata.get('category', 'reagent'),
                'manufacturer': metadata.get('manufacturer', ''),
                'catalog_number': metadata.get('catalog_number', ''),
                'inventory_item_id': inventory_item.id,
                'quantity_on_hand': Decimal(str(inventory_item.quantity_on_hand)),
                'unit': item.unit_of_measure,
                'reorder_level': Decimal(metadata.get('reorder_level', '0')),
                'reorder_quantity': Decimal(metadata.get('reorder_quantity', '0')),
                'unit_cost': inventory_item.unit_cost,
                'supplier': item.preferred_supplier.name if item.preferred_supplier else '',
                'batch_number': metadata.get('batch_number', ''),
                'expiry_date': metadata.get('expiry_date') or None,
                'storage_conditions': metadata.get('storage_conditions', ''),
                'location': metadata.get('location', ''),
                'notes': f'Created from procurement request {instance.request_number}',
            }
            
            # Parse expiry_date if it's a string
            if reagent_data['expiry_date'] and isinstance(reagent_data['expiry_date'], str):
                from datetime import datetime
                try:
                    reagent_data['expiry_date'] = datetime.strptime(reagent_data['expiry_date'], '%Y-%m-%d').date()
                except ValueError:
                    reagent_data['expiry_date'] = None
            
            LabReagent.objects.create(**reagent_data)
            
    except Exception as e:
        # Log error but don't fail the procurement process
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create LabReagent from procurement request: {e}")
