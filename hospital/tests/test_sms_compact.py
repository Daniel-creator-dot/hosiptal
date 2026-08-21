"""SMS cost helpers: compact text and drop emoji so messages stay GSM-7."""
from django.test import SimpleTestCase

from hospital.services.sms_service import compact_sms_text


class CompactSmsTextTests(SimpleTestCase):
    def test_collapses_spaces_and_newlines(self):
        raw = "Hi  John,\n\n  Your  results   are ready.\n\nThank you."
        out = compact_sms_text(raw)
        self.assertEqual(out, "Hi John, Your results are ready. Thank you.")
        self.assertNotIn("\n", out)
        self.assertNotIn("  ", out)

    def test_strips_emoji(self):
        raw = "🏥 PrimeCare\n📍 OPD\nTicket 12"
        out = compact_sms_text(raw)
        self.assertNotIn("🏥", out)
        self.assertNotIn("📍", out)
        self.assertIn("PrimeCare", out)
        self.assertIn("Ticket 12", out)
        self.assertLess(len(out), len(raw))

    def test_queue_check_in_fits_one_gsm_segment(self):
        # Typical queue check-in after compact should stay under 160 GSM chars
        msg = (
            "PrimeCare Medical Center: Ticket 42. Outpatient. "
            "Place #3, wait ~15 min (Aug 08, 2026). "
            "Stay in waiting area until called. Pay at Cashier first if required."
        )
        out = compact_sms_text(msg)
        self.assertLessEqual(len(out), 160)
