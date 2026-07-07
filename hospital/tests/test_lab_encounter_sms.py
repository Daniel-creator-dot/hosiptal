"""Encounter-level lab SMS: partial results and final 'all ready' messages."""
import json
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hospital.models import (
    Department,
    Encounter,
    LabResult,
    LabTest,
    Order,
    Patient,
    Staff,
)
from hospital.models_advanced import SMSLog
from hospital.services.sms_service import SMSService, sms_service

User = get_user_model()


def _sms_success_response():
    class R:
        status_code = 200
        text = json.dumps({'success': True, 'code': 1000, 'message': 'ok'})

    return R()


class PendingLabsFollowupWordingTests(TestCase):
    def test_tomorrow_when_tat_at_least_one_day(self):
        dept = Department.objects.create(name='LabDept', code=f'LD-{uuid.uuid4().hex[:6]}')
        user = User.objects.create_user(username=f'u_{uuid.uuid4().hex[:8]}', password='x')
        staff = Staff.objects.create(user=user, profession='doctor', department=dept)
        patient = Patient.objects.create(
            first_name='Pat',
            last_name='One',
            phone_number='233200000011',
            date_of_birth=timezone.now().date(),
        )
        enc = Encounter.objects.create(
            patient=patient,
            encounter_type='outpatient',
            provider=staff,
            chief_complaint='labs',
        )
        order = Order.objects.create(
            encounter=enc,
            order_type='lab',
            requested_by=staff,
        )
        slow = LabTest.objects.create(
            code=f'SLOW-{uuid.uuid4().hex[:6]}',
            name='Culture',
            specimen_type='blood',
            tat_minutes=1440,
        )
        lr = LabResult.objects.create(order=order, test=slow, status='pending')
        pending = LabResult.objects.filter(pk=lr.pk)
        text = SMSService.pending_labs_followup_wording(pending)
        self.assertIn('tomorrow', text.lower())

    def test_neutral_when_short_tat_same_day(self):
        dept = Department.objects.create(name='LabDept2', code=f'L2-{uuid.uuid4().hex[:6]}')
        user = User.objects.create_user(username=f'u2_{uuid.uuid4().hex[:8]}', password='x')
        staff = Staff.objects.create(user=user, profession='doctor', department=dept)
        patient = Patient.objects.create(
            first_name='Pat',
            last_name='Two',
            phone_number='233200000012',
            date_of_birth=timezone.now().date(),
        )
        enc = Encounter.objects.create(
            patient=patient,
            encounter_type='outpatient',
            provider=staff,
            chief_complaint='labs',
        )
        order = Order.objects.create(
            encounter=enc,
            order_type='lab',
            requested_by=staff,
        )
        fast = LabTest.objects.create(
            code=f'FAST-{uuid.uuid4().hex[:6]}',
            name='Glucose',
            specimen_type='blood',
            tat_minutes=60,
        )
        lr = LabResult.objects.create(order=order, test=fast, status='pending')
        pending = LabResult.objects.filter(pk=lr.pk)
        text = SMSService.pending_labs_followup_wording(pending)
        self.assertNotIn('tomorrow', text.lower())
        self.assertIn('still being processed', text.lower())


class LabEncounterPartialSmsTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name='LabDeptSms', code=f'LS-{uuid.uuid4().hex[:6]}')
        self.user = User.objects.create_user(username=f'dr_{uuid.uuid4().hex[:8]}', password='x')
        self.staff = Staff.objects.create(user=self.user, profession='doctor', department=self.dept)
        self.patient = Patient.objects.create(
            first_name='Sms',
            last_name='Patient',
            phone_number='233200000099',
            date_of_birth=timezone.now().date(),
        )
        self.enc = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            provider=self.staff,
            chief_complaint='labs',
        )
        self.order = Order.objects.create(
            encounter=self.enc,
            order_type='lab',
            requested_by=self.staff,
        )
        self.test_a = LabTest.objects.create(
            code=f'TA-{uuid.uuid4().hex[:6]}',
            name='Test A',
            specimen_type='blood',
            tat_minutes=60,
        )
        self.test_b = LabTest.objects.create(
            code=f'TB-{uuid.uuid4().hex[:6]}',
            name='Test B',
            specimen_type='blood',
            tat_minutes=60,
        )
        self.lab_a = LabResult.objects.create(order=self.order, test=self.test_a, status='pending')
        self.lab_b = LabResult.objects.create(order=self.order, test=self.test_b, status='pending')

    @patch('hospital.services.sms_service.requests.get', return_value=_sms_success_response())
    def test_partial_then_final_sms_once_each(self, _mock_get):
        self.lab_a.status = 'completed'
        self.lab_a.save()
        partial_logs = SMSLog.objects.filter(
            message_type='encounter_lab_results_partial',
            related_object_type='Encounter',
            related_object_id=self.enc.id,
            status='sent',
        )
        self.assertEqual(partial_logs.count(), 1)
        self.assertIn('nurse', partial_logs.first().message.lower())
        ready_logs = SMSLog.objects.filter(
            message_type='encounter_lab_results_ready',
            related_object_type='Encounter',
            related_object_id=self.enc.id,
            status='sent',
        )
        self.assertEqual(ready_logs.count(), 0)

        self.lab_b.status = 'completed'
        self.lab_b.save()
        self.assertEqual(
            SMSLog.objects.filter(
                message_type='encounter_lab_results_partial',
                related_object_type='Encounter',
                related_object_id=self.enc.id,
                status='sent',
            ).count(),
            1,
        )
        final_logs = SMSLog.objects.filter(
            message_type='encounter_lab_results_ready',
            related_object_type='Encounter',
            related_object_id=self.enc.id,
            status='sent',
        )
        self.assertEqual(final_logs.count(), 1)
        self.assertIn('nurse', final_logs.first().message.lower())

    @patch('hospital.services.sms_service.requests.get', return_value=_sms_success_response())
    def test_partial_not_sent_twice_when_second_lab_completes_while_third_pending(self, _mock_get):
        test_c = LabTest.objects.create(
            code=f'TC-{uuid.uuid4().hex[:6]}',
            name='Test C',
            specimen_type='blood',
            tat_minutes=60,
        )
        lab_c = LabResult.objects.create(order=self.order, test=test_c, status='pending')

        self.lab_a.status = 'completed'
        self.lab_a.save()
        self.assertEqual(
            SMSLog.objects.filter(
                message_type='encounter_lab_results_partial',
                related_object_id=self.enc.id,
                status='sent',
            ).count(),
            1,
        )

        self.lab_b.status = 'completed'
        self.lab_b.save()
        self.assertEqual(
            SMSLog.objects.filter(
                message_type='encounter_lab_results_partial',
                related_object_id=self.enc.id,
                status='sent',
            ).count(),
            1,
        )

        lab_c.status = 'completed'
        lab_c.save()
        self.assertEqual(
            SMSLog.objects.filter(
                message_type='encounter_lab_results_ready',
                related_object_id=self.enc.id,
                status='sent',
            ).count(),
            1,
        )

    def test_send_encounter_lab_results_ready_includes_nurse_line(self):
        msg = None
        real_send = SMSService.send_sms

        def capture_send(self_inner, phone_number, message, message_type='', **kwargs):
            nonlocal msg
            if message_type == 'encounter_lab_results_ready':
                msg = message
            return real_send(
                self_inner,
                phone_number='233200000088',
                message=message,
                message_type=message_type,
                **kwargs,
            )

        patient = Patient.objects.create(
            first_name='Zed',
            last_name='Final',
            phone_number='233200000088',
            date_of_birth=timezone.now().date(),
        )
        enc = Encounter.objects.create(
            patient=patient,
            encounter_type='outpatient',
            provider=self.staff,
            chief_complaint='x',
        )
        with patch.object(SMSService, 'send_sms', capture_send):
            with patch('hospital.services.sms_service.requests.get', return_value=_sms_success_response()):
                sms_service.send_encounter_lab_results_ready(enc)
        self.assertIsNotNone(msg)
        self.assertIn('nurse', msg.lower())
