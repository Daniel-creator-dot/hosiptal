# Generated for HospitalSettings printer preferences and extended settings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1087_storetransferline_inventory_correlation'),
    ]

    operations = [
        # POS / Thermal receipt
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_width_mm',
            field=models.PositiveSmallIntegerField(default=80, help_text='Receipt paper width in mm. Standard: 80mm (common) or 58mm (narrow).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_font_size_body',
            field=models.PositiveSmallIntegerField(default=10, help_text='Body text size in px for POS receipt (e.g. 9–11).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_font_size_header',
            field=models.PositiveSmallIntegerField(default=12, help_text='Header/title font size in px for POS receipt (e.g. 11–14).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_font_size_footer',
            field=models.PositiveSmallIntegerField(default=8, help_text='Footer text size in px for POS receipt (e.g. 7–9).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_margin_mm',
            field=models.PositiveSmallIntegerField(default=4, help_text='Left/right margin in mm for POS receipt.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_padding_mm',
            field=models.PositiveSmallIntegerField(default=3, help_text='Inner padding in mm for POS receipt.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_show_qr',
            field=models.BooleanField(default=True, help_text='Show QR code on POS receipt for verification.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='pos_receipt_qr_size_px',
            field=models.PositiveSmallIntegerField(default=56, help_text='QR code size in pixels on POS receipt (e.g. 50–64).'),
        ),
        # General printing
        migrations.AddField(
            model_name='hospitalsettings',
            name='default_print_copies',
            field=models.PositiveSmallIntegerField(default=1, help_text='Default number of copies when printing documents.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='invoice_paper_size',
            field=models.CharField(choices=[('A4', 'A4'), ('Letter', 'Letter')], default='A4', help_text='Paper size for invoices and full-page reports.', max_length=20),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='label_printer_width_mm',
            field=models.PositiveSmallIntegerField(default=60, help_text='Default label width in mm for pharmacy labels (e.g. 40–70).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='report_paper_orientation',
            field=models.CharField(choices=[('portrait', 'Portrait'), ('landscape', 'Landscape')], default='portrait', help_text='Default orientation for reports.', max_length=10),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='default_printer_name',
            field=models.CharField(blank=True, help_text='Optional: default printer name (as in OS). Leave blank for system default.', max_length=200),
        ),
        # Session & Security
        migrations.AddField(
            model_name='hospitalsettings',
            name='session_timeout_minutes',
            field=models.PositiveSmallIntegerField(default=30, help_text='Minutes of inactivity before session timeout (e.g. 15–120).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='require_login_for_receipt_verify',
            field=models.BooleanField(default=False, help_text='Require login to verify receipt by number/QR (public verify can still work if disabled).'),
        ),
        # Business & Display
        migrations.AddField(
            model_name='hospitalsettings',
            name='timezone',
            field=models.CharField(default='Africa/Accra', help_text='Timezone for display (e.g. Africa/Accra, UTC).', max_length=50),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='business_hours_start',
            field=models.CharField(default='08:00', help_text='Opening time (HH:MM, 24h).', max_length=5),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='business_hours_end',
            field=models.CharField(default='17:00', help_text='Closing time (HH:MM, 24h).', max_length=5),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='max_login_attempts',
            field=models.PositiveSmallIntegerField(default=5, help_text='Max failed login attempts before lockout.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='lockout_duration_minutes',
            field=models.PositiveSmallIntegerField(default=15, help_text='Account lockout duration in minutes.'),
        ),
        # Notifications & Integrations
        migrations.AddField(
            model_name='hospitalsettings',
            name='sms_enabled',
            field=models.BooleanField(default=False, help_text='Enable SMS notifications.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='email_notifications_enabled',
            field=models.BooleanField(default=True, help_text='Enable email notifications.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='backup_retention_days',
            field=models.PositiveSmallIntegerField(default=30, help_text='Keep backups for this many days (0 = no auto cleanup).'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='patient_portal_enabled',
            field=models.BooleanField(default=True, help_text='Allow patients to use the portal.'),
        ),
        migrations.AddField(
            model_name='hospitalsettings',
            name='show_prices_to_patient',
            field=models.BooleanField(default=True, help_text='Show service/item prices to patient on receipts and portal where applicable.'),
        ),
    ]
