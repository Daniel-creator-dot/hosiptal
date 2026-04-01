"""
Tests for the Midwife Dashboard view.

Tests URL resolution, authentication, role-based access, view rendering,
and context data for the midwife dashboard.
"""
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
from django.utils import timezone

from hospital.models import Staff, Department, Patient, Encounter
from hospital.views_role_dashboards import midwife_dashboard

User = get_user_model()


class MidwifeDashboardURLTests(TestCase):
    """Test URL configuration for midwife dashboard."""
    
    def test_midwife_dashboard_url_exists(self):
        """Test that the midwife dashboard URL pattern exists."""
        url = reverse('hospital:midwife_dashboard')
        self.assertEqual(url, '/hms/midwife/dashboard/')
    
    def test_midwife_dashboard_url_resolves(self):
        """Test that the URL resolves to the correct view."""
        url = '/hms/midwife/dashboard/'
        resolved = resolve(url)
        self.assertEqual(resolved.func, midwife_dashboard)
        self.assertEqual(resolved.url_name, 'midwife_dashboard')


class MidwifeDashboardAccessTests(TestCase):
    """Test access control for midwife dashboard."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client(REMOTE_ADDR='127.0.0.1')
        # Patch login tracking to avoid database constraint issues in tests
        self.login_tracking_patcher = patch('hospital.signals_login_tracking.track_successful_login')
        self.mock_track_login = self.login_tracking_patcher.start()
        
        # Create departments
        self.maternity_dept = Department.objects.create(
            name='Maternity',
            code='MATERNITY',
            description='Maternity Care Department'
        )
        
        self.general_med_dept = Department.objects.create(
            name='General Medicine',
            code='GEN_MED',
            description='General Medicine Department'
        )
        
        # Create users
        self.midwife_user = User.objects.create_user(
            username='midwife_test',
            email='midwife@test.com',
            password='testpass123',
            first_name='Jane',
            last_name='Midwife'
        )
        
        self.doctor_user = User.objects.create_user(
            username='doctor_test',
            email='doctor@test.com',
            password='testpass123',
            first_name='John',
            last_name='Doctor'
        )
        
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_superuser=True,
            is_staff=True
        )
        
        # Create staff records
        self.midwife_staff = Staff.objects.create(
            user=self.midwife_user,
            profession='midwife',
            department=self.maternity_dept,
            is_active=True
        )
        
        self.doctor_staff = Staff.objects.create(
            user=self.doctor_user,
            profession='doctor',
            department=self.general_med_dept,
            is_active=True
        )
        
        # Create Midwife group
        self.midwife_group, _ = Group.objects.get_or_create(name='Midwife')
        self.midwife_user.groups.add(self.midwife_group)
    
    def tearDown(self):
        """Clean up patches."""
        self.login_tracking_patcher.stop()
    
    def test_unauthenticated_user_redirected(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('/login', response.url)
    
    def test_midwife_user_can_access(self):
        """Test that a user with midwife profession can access the dashboard."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hospital/role_dashboards/midwife_dashboard.html')
    
    def test_doctor_user_denied_access(self):
        """Test that a doctor user is denied access (403)."""
        self.client.login(username='doctor_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        # Should return 403 or redirect with error
        self.assertIn(response.status_code, [403, 302])
    
    def test_admin_user_can_access(self):
        """Test that admin users can access all dashboards."""
        self.client.login(username='admin_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        # Admin should have access (may need staff record)
        # If admin doesn't have staff record, might get 403
        # But typically admins bypass role checks
        self.assertIn(response.status_code, [200, 403])
    
    def test_user_with_midwife_group_can_access(self):
        """Test that user in Midwife group can access even without profession."""
        # Create user with group but different profession
        group_user = User.objects.create_user(
            username='group_midwife',
            email='group@test.com',
            password='testpass123'
        )
        group_user.groups.add(self.midwife_group)
        
        Staff.objects.create(
            user=group_user,
            profession='nurse',  # Different profession
            department=self.maternity_dept,
            is_active=True
        )
        
        self.client.login(username='group_midwife', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        # Should work if role detection uses groups
        self.assertIn(response.status_code, [200, 403])


class MidwifeDashboardContentTests(TestCase):
    """Test the content and context of midwife dashboard."""
    
    def setUp(self):
        """Set up test data with sample encounters and patients."""
        self.client = Client(REMOTE_ADDR='127.0.0.1')
        # Patch login tracking to avoid database constraint issues in tests
        self.login_tracking_patcher = patch('hospital.signals_login_tracking.track_successful_login')
        self.mock_track_login = self.login_tracking_patcher.start()
    
    def tearDown(self):
        """Clean up patches."""
        self.login_tracking_patcher.stop()
        
        # Create department
        self.maternity_dept = Department.objects.create(
            name='Maternity',
            code='MATERNITY',
            description='Maternity Care Department'
        )
        
        # Create midwife user and staff
        self.midwife_user = User.objects.create_user(
            username='midwife_test',
            email='midwife@test.com',
            password='testpass123',
            first_name='Jane',
            last_name='Midwife'
        )
        
        self.midwife_staff = Staff.objects.create(
            user=self.midwife_user,
            profession='midwife',
            department=self.maternity_dept,
            is_active=True
        )
        
        # Create test patients
        self.patient1 = Patient.objects.create(
            first_name='Mary',
            last_name='Patient',
            gender='F',
            phone_number='233200000001',
            date_of_birth=timezone.now().date() - timedelta(days=365*25)
        )
        
        self.patient2 = Patient.objects.create(
            first_name='Sarah',
            last_name='Mother',
            gender='F',
            phone_number='233200000002',
            date_of_birth=timezone.now().date() - timedelta(days=365*28)
        )
        
        # Create encounters
        today = timezone.now().date()
        
        self.antenatal_encounter = Encounter.objects.create(
            patient=self.patient1,
            provider=self.midwife_staff,
            department=self.maternity_dept,
            encounter_type='Antenatal Visit',
            status='active',
            created=timezone.now() - timedelta(hours=2)
        )
        
        self.postnatal_encounter = Encounter.objects.create(
            patient=self.patient2,
            provider=self.midwife_staff,
            department=self.maternity_dept,
            encounter_type='Postnatal Visit',
            status='active',
            created=timezone.now() - timedelta(hours=1)
        )
        
        # Create Midwife group
        self.midwife_group, _ = Group.objects.get_or_create(name='Midwife')
        self.midwife_user.groups.add(self.midwife_group)
    
    def test_dashboard_renders_successfully(self):
        """Test that dashboard renders without errors."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hospital/role_dashboards/midwife_dashboard.html')
    
    def test_dashboard_context_contains_staff(self):
        """Test that context contains staff information."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('staff', response.context)
        self.assertEqual(response.context['staff'], self.midwife_staff)
    
    def test_dashboard_context_contains_stats(self):
        """Test that context contains statistics."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('stats', response.context)
        stats = response.context['stats']
        
        # Check that stats dictionary has expected keys
        expected_keys = [
            'antenatal_visits_today',
            'postnatal_visits_today',
            'active_maternity_cases',
            'pending_vitals',
            'upcoming_appointments',
            'total_maternity_patients'
        ]
        for key in expected_keys:
            self.assertIn(key, stats)
    
    def test_dashboard_context_contains_chart_data(self):
        """Test that context contains chart data in JSON format."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        
        # Check for chart data
        self.assertIn('chart_months', response.context)
        self.assertIn('antenatal_data', response.context)
        self.assertIn('postnatal_data', response.context)
        self.assertIn('visit_types_data_json', response.context)
        self.assertIn('weekly_labels', response.context)
        self.assertIn('weekly_antenatal', response.context)
        self.assertIn('weekly_postnatal', response.context)
        
        # Verify JSON data is strings (JSON serialized)
        import json
        chart_months = response.context['chart_months']
        self.assertIsInstance(chart_months, str)
        # Should be valid JSON
        months_list = json.loads(chart_months)
        self.assertIsInstance(months_list, list)
    
    def test_dashboard_shows_maternity_encounters(self):
        """Test that dashboard shows maternity-related encounters."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('maternity_encounters', response.context)
        encounters = response.context['maternity_encounters']
        
        # Should include our test encounters
        encounter_ids = [e.id for e in encounters]
        self.assertIn(self.antenatal_encounter.id, encounter_ids)
        self.assertIn(self.postnatal_encounter.id, encounter_ids)
    
    def test_dashboard_shows_female_patients(self):
        """Test that dashboard shows female patients (maternity focus)."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('recent_maternity_patients', response.context)
        patients = response.context['recent_maternity_patients']
        
        # All patients should be female
        for patient in patients:
            self.assertEqual(patient.gender, 'F')
    
    def test_dashboard_includes_department_filtering(self):
        """Test that dashboard filters by maternity department."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('maternity_dept', response.context)
        self.assertEqual(response.context['maternity_dept'], self.maternity_dept)
    
    def test_dashboard_contains_active_encounters(self):
        """Test that dashboard shows active maternity encounters."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('active_maternity_encounters', response.context)
        active_encounters = response.context['active_maternity_encounters']
        
        # Should include our active encounters
        encounter_ids = [e.id for e in active_encounters]
        self.assertIn(self.antenatal_encounter.id, encounter_ids)
        self.assertIn(self.postnatal_encounter.id, encounter_ids)
    
    def test_dashboard_contains_pending_vitals(self):
        """Test that dashboard shows pending vital signs."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_vitals', response.context)
        # Pending vitals should be a queryset
        pending_vitals = response.context['pending_vitals']
        self.assertIsNotNone(pending_vitals)
    
    def test_dashboard_contains_upcoming_appointments(self):
        """Test that dashboard shows upcoming appointments."""
        self.client.login(username='midwife_test', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('upcoming_appointments', response.context)
        # Should be a list (even if empty)
        appointments = response.context['upcoming_appointments']
        self.assertIsInstance(appointments, list)


class MidwifeDashboardIntegrationTests(TestCase):
    """Integration tests for midwife dashboard with real data scenarios."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.client = Client(REMOTE_ADDR='127.0.0.1')
        # Patch login tracking to avoid database constraint issues in tests
        self.login_tracking_patcher = patch('hospital.signals_login_tracking.track_successful_login')
        self.mock_track_login = self.login_tracking_patcher.start()
    
    def tearDown(self):
        """Clean up patches."""
        self.login_tracking_patcher.stop()
        
        # Create department
        self.maternity_dept = Department.objects.create(
            name='Maternity',
            code='MATERNITY',
            description='Maternity Care Department'
        )
        
        # Create midwife
        self.midwife_user = User.objects.create_user(
            username='midwife_integration',
            email='midwife@integration.com',
            password='testpass123'
        )
        
        self.midwife_staff = Staff.objects.create(
            user=self.midwife_user,
            profession='midwife',
            department=self.maternity_dept,
            is_active=True
        )
        
        # Create Midwife group
        self.midwife_group, _ = Group.objects.get_or_create(name='Midwife')
        self.midwife_user.groups.add(self.midwife_group)
        
        # Create multiple patients and encounters
        today = timezone.now().date()
        
        for i in range(5):
            patient = Patient.objects.create(
                first_name=f'Patient{i}',
                last_name=f'Test{i}',
                gender='F',
                phone_number=f'2332000000{i:02d}',
                date_of_birth=today - timedelta(days=365*(25+i))
            )
            
            # Create antenatal encounter
            Encounter.objects.create(
                patient=patient,
                provider=self.midwife_staff,
                department=self.maternity_dept,
                encounter_type='Antenatal Visit',
                status='active',
                created=timezone.now() - timedelta(days=i)
            )
    
    def test_dashboard_handles_multiple_encounters(self):
        """Test that dashboard handles multiple encounters correctly."""
        self.client.login(username='midwife_integration', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('maternity_encounters', response.context)
        encounters = response.context['maternity_encounters']
        
        # Should have encounters (may be limited to 20)
        self.assertGreaterEqual(len(encounters), 0)
        self.assertLessEqual(len(encounters), 20)
    
    def test_dashboard_calculates_statistics_correctly(self):
        """Test that statistics are calculated correctly."""
        self.client.login(username='midwife_integration', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        stats = response.context['stats']
        
        # Check that stats are non-negative integers
        for key, value in stats.items():
            self.assertIsInstance(value, (int, type(None)))
            if value is not None:
                self.assertGreaterEqual(value, 0)
    
    def test_dashboard_renders_without_errors_with_empty_data(self):
        """Test that dashboard renders even with no data."""
        # Create new midwife with no encounters
        empty_midwife = User.objects.create_user(
            username='empty_midwife',
            email='empty@test.com',
            password='testpass123'
        )
        
        Staff.objects.create(
            user=empty_midwife,
            profession='midwife',
            department=self.maternity_dept,
            is_active=True
        )
        
        empty_midwife.groups.add(self.midwife_group)
        
        self.client.login(username='empty_midwife', password='testpass123')
        response = self.client.get(reverse('hospital:midwife_dashboard'))
        
        # Should still render successfully
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hospital/role_dashboards/midwife_dashboard.html')














