"""Tests for issuing store consumables to staff (stock reduces)."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from hospital.models import Staff, Department
from hospital.models_procurement import InventoryCategory, InventoryItem, Store
from hospital.services.inventory_accountability_service import InventoryAccountabilityService


class IssueConsumablesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f'iss_{uuid.uuid4().hex[:8]}',
            password='pw',
            first_name='Store',
            last_name='Keeper',
            is_staff=True,
        )
        self.dept = Department.objects.create(
            name=f'Stores {uuid.uuid4().hex[:4]}',
            code=f'ST{uuid.uuid4().hex[:4].upper()}',
        )
        self.staff = Staff.objects.create(
            user=self.user,
            profession='store_manager',
            employee_id=f'E{uuid.uuid4().hex[:6].upper()}',
            department=self.dept,
        )
        self.nurse_user = User.objects.create_user(
            username=f'nrs_{uuid.uuid4().hex[:8]}',
            password='pw',
            first_name='Ama',
            last_name='Nurse',
        )
        self.ward = Department.objects.create(
            name=f'Ward {uuid.uuid4().hex[:4]}',
            code=f'W{uuid.uuid4().hex[:4].upper()}',
        )
        self.nurse = Staff.objects.create(
            user=self.nurse_user,
            profession='nurse',
            employee_id=f'N{uuid.uuid4().hex[:6].upper()}',
            department=self.ward,
        )
        self.store = Store.objects.create(
            name=f'Main {uuid.uuid4().hex[:4]}',
            code=f'M{uuid.uuid4().hex[:4].upper()}',
            store_type='main',
        )
        self.category, _ = InventoryCategory.objects.get_or_create(
            code='GEN',
            defaults={'name': 'General Supplies'},
        )
        self.item = InventoryItem.objects.create(
            store=self.store,
            category=self.category,
            item_name='Toilet Rolls',
            item_code=f'TR-{uuid.uuid4().hex[:6].upper()}',
            quantity_on_hand=40,
            unit_cost=Decimal('2.50'),
            unit_of_measure='rolls',
        )

    def test_issue_reduces_stock(self):
        txn = InventoryAccountabilityService.issue_to_department(
            inventory_item=self.item,
            quantity=5,
            staff=self.staff,
            department_name='Maternity',
            recipient_name='Nurse Ama',
            issued_to_staff=self.nurse,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 35)
        self.assertEqual(txn.transaction_type, 'issue')
        self.assertEqual(txn.quantity, -5)
        self.assertIn('Nurse Ama', txn.to_location)

    def test_issue_via_post(self):
        client = Client()
        client.force_login(self.user)
        url = reverse('hospital:inventory:issue_consumables')
        resp = client.post(
            url,
            {
                'action': 'issue_to_staff',
                'item_id': str(self.item.id),
                'quantity': '3',
                'recipient_staff_id': str(self.nurse.id),
                'department_name': 'Ward A',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 37)

    def test_issue_to_lab_increases_reagent_stock(self):
        from hospital.models_lab_management import LabReagent, ReagentTransaction

        lab_cat, _ = InventoryCategory.objects.get_or_create(
            code='LAB',
            defaults={'name': 'Laboratory'},
        )
        kit_item = InventoryItem.objects.create(
            store=self.store,
            category=lab_cat,
            item_name='Typhoid kit',
            item_code=f'TYPH-{uuid.uuid4().hex[:6].upper()}',
            quantity_on_hand=4,
            unit_cost=Decimal('80.00'),
            unit_of_measure='box',
        )
        reagent = LabReagent.objects.create(
            item_code=kit_item.item_code,
            name='Typhoid IgG/IgM',
            category='consumable',
            quantity_on_hand=Decimal('0'),
            unit='pcs',
            stock_tracking='measurable',
            qty_per_box=25,
            qty_consumed_per_test=Decimal('1'),
            inventory_item_id=kit_item.id,
        )
        client = Client()
        client.force_login(self.user)
        resp = client.post(
            reverse('hospital:inventory:issue_consumables'),
            {
                'action': 'issue_to_staff',
                'destination': 'lab',
                'item_id': str(kit_item.id),
                'quantity': '1',
            },
        )
        self.assertEqual(resp.status_code, 302)
        kit_item.refresh_from_db()
        reagent.refresh_from_db()
        self.assertEqual(kit_item.quantity_on_hand, 3)
        self.assertEqual(reagent.quantity_on_hand, Decimal('25'))
        self.assertTrue(
            ReagentTransaction.objects.filter(
                reagent=reagent, transaction_type='received', is_deleted=False
            ).exists()
        )

    def test_staff_issue_from_main_store_does_not_change_lab_books(self):
        from hospital.models_lab_management import LabReagent

        lab_cat, _ = InventoryCategory.objects.get_or_create(
            code='LAB',
            defaults={'name': 'Laboratory'},
        )
        kit_item = InventoryItem.objects.create(
            store=self.store,
            category=lab_cat,
            item_name='HCG kit',
            item_code=f'HCG-{uuid.uuid4().hex[:6].upper()}',
            quantity_on_hand=5,
            unit_cost=Decimal('40.00'),
            unit_of_measure='box',
        )
        reagent = LabReagent.objects.create(
            item_code=kit_item.item_code,
            name='B-HCG kit',
            category='consumable',
            quantity_on_hand=Decimal('10'),
            unit='pcs',
            stock_tracking='measurable',
            qty_per_box=25,
            inventory_item_id=kit_item.id,
        )
        client = Client()
        client.force_login(self.user)
        resp = client.post(
            reverse('hospital:inventory:issue_consumables'),
            {
                'action': 'issue_to_staff',
                'destination': 'staff',
                'item_id': str(kit_item.id),
                'quantity': '1',
                'recipient_staff_id': str(self.nurse.id),
            },
        )
        self.assertEqual(resp.status_code, 302)
        kit_item.refresh_from_db()
        reagent.refresh_from_db()
        self.assertEqual(kit_item.quantity_on_hand, 4)
        self.assertEqual(reagent.quantity_on_hand, Decimal('10'))

    def test_non_procurement_cannot_issue(self):
        client = Client()
        client.force_login(self.nurse_user)
        resp = client.post(
            reverse('hospital:inventory:issue_consumables'),
            {
                'action': 'issue_to_staff',
                'item_id': str(self.item.id),
                'quantity': '2',
                'recipient_staff_id': str(self.nurse.id),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, 40)

    def test_lab_consume_after_issue_does_not_reduce_main_store(self):
        from hospital.models import Encounter, LabResult, LabTest, Order, Patient
        from hospital.models_lab_management import LabReagent

        lab_cat, _ = InventoryCategory.objects.get_or_create(
            code='LAB',
            defaults={'name': 'Laboratory'},
        )
        kit_item = InventoryItem.objects.create(
            store=self.store,
            category=lab_cat,
            item_name='Malaria kit',
            item_code=f'MAL-{uuid.uuid4().hex[:6].upper()}',
            quantity_on_hand=2,
            unit_cost=Decimal('50.00'),
            unit_of_measure='box',
        )
        reagent = LabReagent.objects.create(
            item_code=kit_item.item_code,
            name='Malaria Pf/Pv',
            category='consumable',
            quantity_on_hand=Decimal('0'),
            unit='pcs',
            stock_tracking='measurable',
            qty_per_box=25,
            qty_consumed_per_test=Decimal('1'),
            inventory_item_id=kit_item.id,
        )
        lab_test = LabTest.objects.create(
            code=f'MAL{uuid.uuid4().hex[:4]}',
            name='Malaria Rapid',
            specimen_type='Blood',
            price=Decimal('20'),
        )
        reagent.tests.add(lab_test)
        client = Client()
        client.force_login(self.user)
        client.post(
            reverse('hospital:inventory:issue_consumables'),
            {
                'action': 'issue_to_staff',
                'destination': 'lab',
                'item_id': str(kit_item.id),
                'quantity': '1',
            },
        )
        kit_item.refresh_from_db()
        self.assertEqual(kit_item.quantity_on_hand, 1)

        patient = Patient.objects.create(
            first_name='Lab', last_name='Issue', mrn=f'PMC-ISS-{uuid.uuid4().hex[:6]}'
        )
        encounter = Encounter.objects.create(
            patient=patient,
            encounter_type='outpatient',
            status='active',
            chief_complaint='Fever',
            provider=self.staff,
        )
        order = Order.objects.create(
            encounter=encounter,
            order_type='lab',
            status='pending',
            requested_by=self.staff,
        )
        result = LabResult.objects.create(order=order, test=lab_test, status='pending')
        result.status = 'completed'
        result.save()
        reagent.refresh_from_db()
        kit_item.refresh_from_db()
        self.assertEqual(reagent.quantity_on_hand, Decimal('24'))
        self.assertEqual(kit_item.quantity_on_hand, 1)
