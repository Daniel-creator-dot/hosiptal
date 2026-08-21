"""EDTA / visit consumables: one tube per completed lab, plus issuing stock to staff."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from hospital.models import Department, Encounter, LabResult, LabTest, Order, Patient, Staff
from hospital.models_lab_management import LabReagent, ReagentTransaction
from hospital.services.lab_reagent_usage_service import (
    consume_visit_consumables_for_lab_result,
    issue_reagent_to_staff,
)


class LabVisitConsumableTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'Lab{suf}', code=f'L{suf[:4]}')
        self.user = User.objects.create_user(
            username=f'lt_{suf}', password='pw', first_name='Lab', last_name='Tech'
        )
        self.staff = Staff.objects.create(
            user=self.user, profession='lab_technician', department=self.dept
        )
        self.patient = Patient.objects.create(
            first_name='Ada', last_name=f'Tube{suf}', mrn=f'PMC-EDT-{suf}'
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Labs',
            provider=self.staff,
        )
        self.edta = LabReagent.objects.create(
            item_code=f'EDTA-{suf[:6]}',
            name=f'EDTA Tube {suf}',
            category='consumable',
            quantity_on_hand=Decimal('20'),
            unit='tube',
            unit_cost=Decimal('1.50'),
            deduct_per_lab_visit=True,
            qty_per_lab_visit=Decimal('1'),
        )
        self.lab_test = LabTest.objects.create(
            code=f'CBC{suf[:4]}',
            name=f'CBC {suf}',
            specimen_type='Blood',
            price=Decimal('30'),
        )
        self.other_test = LabTest.objects.create(
            code=f'HB{suf[:4]}',
            name=f'HB {suf}',
            specimen_type='Blood',
            price=Decimal('10'),
        )
        self.order = Order.objects.create(
            encounter=self.encounter,
            order_type='lab',
            status='pending',
            requested_by=self.staff,
        )

    def _edta_used_count(self):
        return ReagentTransaction.objects.filter(
            reagent=self.edta,
            transaction_type='used',
            reference__startswith='AUTO-EDTA',
            is_deleted=False,
        ).count()

    def test_pending_lab_does_not_deduct(self):
        result = LabResult.objects.create(order=self.order, test=self.lab_test, status='pending')
        consume_visit_consumables_for_lab_result(result, performed_by=self.staff)
        self.edta.refresh_from_db()
        self.assertEqual(self.edta.quantity_on_hand, Decimal('20'))
        self.assertEqual(self._edta_used_count(), 0)

    def test_two_completed_labs_deduct_two_tubes(self):
        first = LabResult.objects.create(order=self.order, test=self.lab_test, status='pending')
        second = LabResult.objects.create(order=self.order, test=self.other_test, status='pending')
        first.status = 'completed'
        first.save()
        second.status = 'completed'
        second.save()
        self.edta.refresh_from_db()
        self.assertEqual(self.edta.quantity_on_hand, Decimal('18'))
        self.assertEqual(self._edta_used_count(), 2)

    def test_completing_same_result_twice_does_not_double_deduct(self):
        result = LabResult.objects.create(order=self.order, test=self.lab_test, status='pending')
        result.status = 'completed'
        result.save()
        consume_visit_consumables_for_lab_result(result, performed_by=self.staff)
        result.save()
        self.edta.refresh_from_db()
        self.assertEqual(self.edta.quantity_on_hand, Decimal('19'))
        self.assertEqual(self._edta_used_count(), 1)

    def test_issue_to_staff_reduces_stock(self):
        txn = issue_reagent_to_staff(
            reagent=self.edta,
            quantity=3,
            performed_by=self.staff,
            recipient_staff=self.staff,
        )
        self.edta.refresh_from_db()
        self.assertEqual(self.edta.quantity_on_hand, Decimal('17'))
        self.assertEqual(txn.transaction_type, 'transferred')

    def test_issue_page_post(self):
        client = Client()
        client.force_login(self.user)
        url = reverse('hospital:issue_lab_consumables')
        resp = client.post(url, {
            'action': 'issue_to_staff',
            'reagent_id': str(self.edta.id),
            'quantity': '2',
            'recipient_staff_id': str(self.staff.id),
        })
        self.assertEqual(resp.status_code, 302)
        self.edta.refresh_from_db()
        self.assertEqual(self.edta.quantity_on_hand, Decimal('20'))
