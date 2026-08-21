"""IT Operations can remove duplicate patients and staff logins."""
import uuid
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from hospital.models import Department, Patient, Staff


class RecordsCleanupTests(TestCase):
    def setUp(self):
        suf = uuid.uuid4().hex[:8]
        self.dept = Department.objects.create(name=f'IT {suf}', code=f'IT{suf[:4]}')
        self.it_user = User.objects.create_user(
            username=f'itops_{suf}', password='pw', first_name='Ops', last_name='User'
        )
        group, _ = Group.objects.get_or_create(name='IT Operations')
        self.it_user.groups.add(group)
        self.it_staff = Staff.objects.create(
            user=self.it_user, profession='admin', department=self.dept
        )
        self.ward = Department.objects.create(name=f'Ward {suf}', code=f'W{suf[:4]}')
        self.nurse_user = User.objects.create_user(
            username=f'nrs_{suf}', password='pw', first_name='Ama', last_name='Nurse'
        )
        self.nurse_staff = Staff.objects.create(
            user=self.nurse_user, profession='nurse', department=self.ward
        )
        self.dup_user = User.objects.create_user(
            username=f'dup_{suf}', password='pw', first_name='Dup', last_name='Account'
        )
        self.dup_staff = Staff.objects.create(
            user=self.dup_user, profession='receptionist', department=self.dept
        )
        self.patient = Patient.objects.create(
            first_name='Ama',
            last_name=f'Dup{suf}',
            mrn=f'PMC-DUP-{suf}',
            date_of_birth=date(1990, 1, 1),
            phone_number='0241234567',
        )
        self.client = Client()

    def test_it_can_remove_patient(self):
        self.client.force_login(self.it_user)
        url = reverse('hospital:it_delete_patient', args=[self.patient.pk])
        resp = self.client.post(url, {'confirm_mrn': self.patient.mrn, 'reason': 'Duplicate'})
        self.assertEqual(resp.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_deleted)

    def test_wrong_mrn_does_not_remove_patient(self):
        self.client.force_login(self.it_user)
        url = reverse('hospital:it_delete_patient', args=[self.patient.pk])
        resp = self.client.post(url, {'confirm_mrn': 'WRONG'})
        self.assertEqual(resp.status_code, 200)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_deleted)

    def test_nurse_cannot_remove_patient(self):
        self.client.force_login(self.nurse_user)
        url = reverse('hospital:it_delete_patient', args=[self.patient.pk])
        self.client.post(url, {'confirm_mrn': self.patient.mrn})
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_deleted)

    def test_it_can_remove_duplicate_login(self):
        self.client.force_login(self.it_user)
        url = reverse('hospital:it_delete_staff_account', args=[self.dup_staff.pk])
        resp = self.client.post(url, {'confirm_username': self.dup_user.username, 'reason': 'Duplicate login'})
        self.assertEqual(resp.status_code, 302)
        self.dup_user.refresh_from_db()
        self.dup_staff.refresh_from_db()
        self.assertFalse(self.dup_user.is_active)
        self.assertTrue(self.dup_staff.is_deleted)

    def test_cannot_delete_own_account(self):
        self.client.force_login(self.it_user)
        url = reverse('hospital:it_delete_staff_account', args=[self.it_staff.pk])
        self.client.post(url, {'confirm_username': self.it_user.username})
        self.it_user.refresh_from_db()
        self.it_staff.refresh_from_db()
        self.assertTrue(self.it_user.is_active)
        self.assertFalse(self.it_staff.is_deleted)

    def test_cannot_delete_superuser(self):
        boss = User.objects.create_superuser(
            username=f'root_{uuid.uuid4().hex[:6]}', email='r@x.com', password='pw'
        )
        boss_staff = Staff.objects.create(user=boss, profession='admin', department=self.dept)
        self.client.force_login(self.it_user)
        url = reverse('hospital:it_delete_staff_account', args=[boss_staff.pk])
        self.client.post(url, {'confirm_username': boss.username})
        boss.refresh_from_db()
        boss_staff.refresh_from_db()
        self.assertTrue(boss.is_active)
        self.assertFalse(boss_staff.is_deleted)

    def test_cleanup_search_page_ok(self):
        self.client.force_login(self.it_user)
        resp = self.client.get(reverse('hospital:records_cleanup'), {'q': self.patient.last_name[:4]})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.patient.mrn)
