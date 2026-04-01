"""
Payment clearance helpers
Link payment receipts to lab result releases, pharmacy dispensing, and imaging
so frontline teams can verify by receipt number immediately.
"""
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone


class PaymentClearanceService:
    LAB_TYPES = {'lab', 'lab_test', 'lab_result', 'laboratory'}
    PHARMACY_TYPES = {'pharmacy', 'pharmacy_prescription', 'pharmacy_walkin', 'medication', 'drug'}
    IMAGING_TYPES = {'imaging', 'radiology', 'imaging_study'}

    @classmethod
    def link_receipt_to_services(cls, payment_receipt):
        """
        Called whenever a PaymentReceipt is created.
        Connects the receipt to any pending service release records so patients
        can present the receipt number at Lab/Pharmacy/Imaging.
        """
        service_type = (payment_receipt.service_type or '').lower()

        link_lab = service_type in cls.LAB_TYPES
        link_pharmacy = service_type in cls.PHARMACY_TYPES
        link_imaging = service_type in cls.IMAGING_TYPES

        # Combined or unspecified receipts should clear every pending service
        if service_type in {'combined', 'other', ''}:
            link_lab = link_pharmacy = link_imaging = True

        try:
            if link_lab:
                cls._link_lab_release(payment_receipt)
            if link_pharmacy:
                if service_type == 'pharmacy_walkin':
                    cls._link_walkin_sale(payment_receipt)
                else:
                    cls._link_pharmacy_dispensing(payment_receipt)
            if link_imaging:
                cls._link_imaging_study(payment_receipt)

            cls._send_receipt_sms(payment_receipt, service_type)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Payment clearance error for receipt %s: %s",
                payment_receipt.receipt_number,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _link_lab_release(payment_receipt):
        from hospital.models_payment_verification import (
            LabResultRelease,
            PaymentVerification,
        )

        encounter = payment_receipt.invoice.encounter if payment_receipt.invoice else None
        qs = LabResultRelease.objects.filter(
            patient=payment_receipt.patient,
            payment_receipt__isnull=True,
            release_status__in=['pending_payment', 'ready_for_release'],
        )

        if encounter:
            qs = qs.filter(lab_result__order__encounter=encounter)

        lab_ids = payment_receipt.service_details.get('lab_result_ids') if isinstance(payment_receipt.service_details, dict) else None
        if lab_ids:
            qs = qs.filter(lab_result_id__in=lab_ids)

        releases = list(qs[:5])
        if not releases:
            return

        with transaction.atomic():
            for release in releases:
                release.payment_receipt = payment_receipt
                release.payment_verified_at = timezone.now()
                release.payment_verified_by = payment_receipt.received_by
                release.release_status = 'ready_for_release'
                release.save(update_fields=['payment_receipt', 'payment_verified_at', 'payment_verified_by', 'release_status'])

                PaymentVerification.objects.create(
                    receipt=payment_receipt,
                    service_type='lab_result',
                    lab_result=release.lab_result,
                    verification_status='verified',
                    verified_by=payment_receipt.received_by,
                    verified_at=timezone.now(),
                    verification_method='receipt_number',
                    verification_notes='Auto-verified via cashier receipt',
                )

    @staticmethod
    def _link_pharmacy_dispensing(payment_receipt):
        from hospital.models_payment_verification import (
            PharmacyDispensing,
            PaymentVerification,
        )

        encounter = payment_receipt.invoice.encounter if payment_receipt.invoice else None
        qs = PharmacyDispensing.objects.filter(
            patient=payment_receipt.patient,
            payment_receipt__isnull=True,
            dispensing_status='pending_payment',
        )
        if encounter:
            qs = qs.filter(prescription__order__encounter=encounter)

        rx_ids = payment_receipt.service_details.get('prescription_ids') if isinstance(payment_receipt.service_details, dict) else None
        if rx_ids:
            qs = qs.filter(prescription_id__in=rx_ids)

        records = list(qs[:5])
        if not records:
            return

        with transaction.atomic():
            for record in records:
                record.payment_receipt = payment_receipt
                record.payment_verified_at = timezone.now()
                record.payment_verified_by = payment_receipt.received_by
                record.dispensing_status = 'ready_to_dispense'
                record.save(update_fields=['payment_receipt', 'payment_verified_at', 'payment_verified_by', 'dispensing_status'])

                PaymentVerification.objects.create(
                    receipt=payment_receipt,
                    service_type='pharmacy_prescription',
                    prescription=record.prescription,
                    verification_status='verified',
                    verified_by=payment_receipt.received_by,
                    verified_at=timezone.now(),
                    verification_method='receipt_number',
                    verification_notes='Auto-verified via cashier receipt',
                )

    @staticmethod
    def _link_imaging_study(payment_receipt):
        from hospital.models_advanced import ImagingStudy
        from hospital.models_payment_verification import ImagingRelease

        encounter = payment_receipt.invoice.encounter if payment_receipt.invoice else None
        qs = ImagingStudy.objects.filter(
            patient=payment_receipt.patient,
            is_deleted=False,
        )
        if encounter:
            qs = qs.filter(encounter=encounter)

        imaging_ids = payment_receipt.service_details.get('imaging_ids') if isinstance(payment_receipt.service_details, dict) else None
        if imaging_ids:
            qs = qs.filter(id__in=imaging_ids)

        studies = list(qs[:5])
        if not studies:
            return

        with transaction.atomic():
            for study in studies:
                # Update legacy fields if they exist
                if hasattr(study, 'is_paid'):
                    study.is_paid = True
                if hasattr(study, 'paid_amount'):
                    study.paid_amount = payment_receipt.amount_paid
                if hasattr(study, 'paid_at'):
                    study.paid_at = timezone.now()
                if hasattr(study, 'payment_receipt_number'):
                    study.payment_receipt_number = payment_receipt.receipt_number
                    study.save(update_fields=['is_paid', 'paid_amount', 'paid_at', 'payment_receipt_number'])
                
                # Create or update ImagingRelease record
                release_record, created = ImagingRelease.objects.get_or_create(
                    imaging_study=study,
                    defaults={
                        'patient': payment_receipt.patient,
                        'release_status': 'pending_payment',
                    }
                )
                
                # Link payment receipt and mark as ready for release
                release_record.payment_receipt = payment_receipt
                release_record.payment_verified_at = timezone.now()
                release_record.payment_verified_by = payment_receipt.received_by
                release_record.release_status = 'ready_for_release'
                release_record.save()
                
                # Create PaymentVerification record
                from hospital.models_payment_verification import PaymentVerification
                PaymentVerification.objects.get_or_create(
                    receipt=payment_receipt,
                    imaging_study=study,
                    defaults={
                        'service_type': 'imaging_study',
                        'verification_status': 'verified',
                        'verified_by': payment_receipt.received_by,
                        'verified_at': timezone.now(),
                        'verification_method': 'receipt_number',
                        'verification_notes': 'Auto-verified via cashier receipt',
                    }
                )

    @staticmethod
    def _send_receipt_sms(payment_receipt, service_type):
        patient = payment_receipt.patient
        phone = getattr(patient, 'phone_number', None)
        if not phone:
            return

        if service_type in PaymentClearanceService.LAB_TYPES:
            instruction = "Present this receipt at the Laboratory to complete your tests or collect results."
        elif service_type in PaymentClearanceService.PHARMACY_TYPES:
            instruction = "Present this receipt at the Pharmacy counter to receive your medication."
        elif service_type in PaymentClearanceService.IMAGING_TYPES:
            instruction = "Present this receipt at Imaging/Radiology to complete your scan or pick the report."
        else:
            instruction = "Present this receipt at the service desk to continue your service."

        message = (
            f"PrimeCare: Payment received (GHS {payment_receipt.amount_paid}) for receipt "
            f"{payment_receipt.receipt_number}. {instruction} Thank you."
        )

        from hospital.services.sms_service import sms_service

        sms_service.send_sms(
            phone_number=phone,
            message=message,
            message_type='payment_receipt',
            recipient_name=patient.full_name,
            related_object_id=getattr(payment_receipt, 'id', None),
            related_object_type='PaymentReceipt',
        )

    @staticmethod
    def _link_walkin_sale(payment_receipt):
        from hospital.models_pharmacy_walkin import WalkInPharmacySale

        details = payment_receipt.service_details if isinstance(payment_receipt.service_details, dict) else {}
        sale_id = details.get('sale_id')
        if not sale_id:
            return

        try:
            sale = WalkInPharmacySale.objects.get(id=sale_id, is_deleted=False)
        except WalkInPharmacySale.DoesNotExist:
            return

        # Sale already updated in walk-in payment workflow.
        # This hook ensures patient linkage exists (in case cashier processed payment centrally)
        from hospital.services.pharmacy_walkin_service import WalkInPharmacyService
        WalkInPharmacyService.ensure_sale_patient(sale)

