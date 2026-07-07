"""Dispense API: explicit JSON quantities must not imply missing Rx rows use full prescribed qty."""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import RequestFactory, SimpleTestCase, TestCase

from hospital.views_departments import (
    _explicit_json_quantities_provided,
    _resolved_pharmacy_rx_quantity,
)


class _DummyRx:
    def __init__(self, rx_id, qty=10):
        self.id = rx_id
        self.quantity = qty


class ResolvedPharmacyRxQuantityTests(SimpleTestCase):
    def test_explicit_json_missing_key_is_zero_not_prescribed_qty(self):
        rx_id = uuid.uuid4()
        rx = _DummyRx(rx_id, qty=30)
        request = MagicMock()
        request.POST.get = MagicMock(return_value=None)

        q = _resolved_pharmacy_rx_quantity(rx, {}, request, True)
        self.assertEqual(q, Decimal('0'))

        q_one = _resolved_pharmacy_rx_quantity(
            rx, {str(rx_id): '2'}, request, True
        )
        self.assertEqual(q_one, Decimal('2'))

    def test_legacy_no_explicit_payload_falls_back_to_prescribed(self):
        rx_id = uuid.uuid4()
        rx = _DummyRx(rx_id, qty=7)
        request = MagicMock()

        def _post_get(key, default=None):
            return default

        request.POST.get = _post_get

        q = _resolved_pharmacy_rx_quantity(rx, {}, request, False)
        self.assertEqual(q, Decimal('7'))

    def test_explicit_json_quantities_provided_empty_vs_nonempty(self):
        self.assertFalse(_explicit_json_quantities_provided({}))
        self.assertFalse(_explicit_json_quantities_provided({'quantities': {}}))
        self.assertTrue(
            _explicit_json_quantities_provided({'quantities': {'abc': 0}})
        )


class DispensePharmacyOrderIntegrationTests(TestCase):
    """
    Regression: POST body ``quantities`` with only some Rx ids must not treat omitted ids as
    positive dispense qty (would fail cash invoice-line validation).
    Uses corporate encounter invoice payer so insurance dispense path applies (no per-Rx invoice gate).
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from datetime import date, timedelta

        from hospital.models import (
            Department,
            Drug,
            Encounter,
            Invoice,
            Order,
            Patient,
            Payer,
            PharmacyStock,
            Prescription,
            Staff,
        )
        from hospital.models_payment_verification import PharmacyDispensing

        self.user = User.objects.create_user(
            username=f'ph_rx_{uuid.uuid4().hex[:8]}',
            password='test-pass-123',
            is_superuser=True,
        )

        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'PhDept{suf}', code=f'P{suf[:4]}')
        self.staff = Staff.objects.create(
            user=self.user, profession='doctor', department=self.dept
        )

        self.payer = Payer.objects.create(name=f'Corp{suf}', payer_type='corporate')
        self.patient = Patient.objects.create(
            first_name='Partial',
            last_name=f'Qty{suf}',
            mrn=f'PMC-PQ-{suf}',
        )
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            encounter_type='outpatient',
            chief_complaint='test',
            provider=self.staff,
        )
        # Signals may create a Cash encounter invoice; payer must be non-cash for pharmacy tests.
        inv = Invoice.all_objects.filter(encounter=self.encounter).first()
        if inv:
            inv.payer = self.payer
            inv.save(update_fields=['payer'])

        self.drug_a = Drug.objects.create(
            name=f'DrugA{suf}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('5.00'),
        )
        self.drug_b = Drug.objects.create(
            name=f'DrugB{suf}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            unit_price=Decimal('3.00'),
        )
        exp = date.today() + timedelta(days=365)
        for d in (self.drug_a, self.drug_b):
            PharmacyStock.objects.create(
                drug=d,
                batch_number=f'B-{suf}-{d.pk}',
                expiry_date=exp,
                quantity_on_hand=500,
            )

        self.order = Order.objects.create(
            encounter=self.encounter,
            order_type='medication',
            status='pending',
            requested_by=self.staff,
        )
        self.rx_a = Prescription.objects.create(
            order=self.order,
            drug=self.drug_a,
            quantity=10,
            dose='1',
            route='oral',
            frequency='od',
            duration='7d',
            prescribed_by=self.staff,
        )
        self.rx_b = Prescription.objects.create(
            order=self.order,
            drug=self.drug_b,
            quantity=20,
            dose='1',
            route='oral',
            frequency='bd',
            duration='7d',
            prescribed_by=self.staff,
        )
        for rx in (self.rx_a, self.rx_b):
            PharmacyDispensing.objects.create(
                prescription=rx,
                patient=self.patient,
                dispensing_status='ready_to_dispense',
                quantity_ordered=rx.quantity,
                quantity_dispensed=0,
            )

    def test_partial_quantities_json_only_dispenses_listed_rx(self):
        import json

        from hospital.views_departments import dispense_pharmacy_order

        body = {
            'quantities': {str(self.rx_a.id): 1},
            'substitutions': {},
        }
        factory = RequestFactory()
        req = factory.post(
            f'/hms/api/pharmacy/order/{self.order.pk}/dispense/',
            data=json.dumps(body),
            content_type='application/json',
        )
        req.user = self.user
        resp = dispense_pharmacy_order(req, self.order.pk)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'content', resp))
        data = json.loads(resp.content.decode())
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('dispensed_count'), 1)
