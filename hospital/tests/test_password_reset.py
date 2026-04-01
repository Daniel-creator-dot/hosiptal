from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hospital.models_login_attempts import PasswordResetOTP


class PasswordResetOTPTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='resetuser', password='OldPassword!23')

    def test_hashed_code_validates_and_marks_used(self):
        raw_code = PasswordResetOTP.generate_code()
        otp = PasswordResetOTP.objects.create(
            user=self.user,
            code=PasswordResetOTP.hash_code(raw_code),
            expires_at=timezone.now() + timedelta(minutes=5),
            phone_snapshot='233200000000',
            sent_via='sms',
        )

        self.assertTrue(otp.is_valid(raw_code))

        otp.mark_used()
        otp.refresh_from_db()
        self.assertFalse(otp.is_valid(raw_code))

    def test_plaintext_backward_compatibility(self):
        otp = PasswordResetOTP.objects.create(
            user=self.user,
            code='123456',  # legacy un-hashed storage
            expires_at=timezone.now() + timedelta(minutes=5),
            phone_snapshot='233200000000',
            sent_via='sms',
        )

        self.assertTrue(otp.is_valid('123456'))
        self.assertFalse(otp.is_valid('000000'))

    def test_expired_codes_are_rejected(self):
        otp = PasswordResetOTP.objects.create(
            user=self.user,
            code=PasswordResetOTP.hash_code('654321'),
            expires_at=timezone.now() - timedelta(minutes=1),
            phone_snapshot='233200000000',
            sent_via='sms',
        )

        self.assertFalse(otp.is_valid('654321'))
















