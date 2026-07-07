"""Pharmacy utilization analytics: channel maps, calendar window, view context."""
import uuid
from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from hospital.models import Drug
from hospital.models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem
from hospital.pharmacy_consumption_estimate import (
    _merge_qty_maps,
    compute_pharmacy_drug_movement_metrics,
    drug_outflow_channel_maps_in_window,
    drug_outflow_totals_in_window,
    global_outflow_by_channel_since,
    top_expensive_formulary_drugs,
    top_moving_drugs_ranked,
)


class PharmacyChannelMapsTests(TestCase):
    def setUp(self):
        self.drug = Drug.objects.create(
            name=f'UtilDrug {uuid.uuid4().hex[:6]}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            category='other',
        )
        self.sale = WalkInPharmacySale.objects.create(
            customer_name='Test Customer',
            is_dispensed=True,
            dispensed_at=timezone.now(),
            sale_date=timezone.now(),
            payment_status='paid',
            total_amount=Decimal('10.00'),
            subtotal=Decimal('10.00'),
        )
        WalkInPharmacySaleItem.objects.create(
            sale=self.sale,
            drug=self.drug,
            quantity=4,
            unit_price=Decimal('2.50'),
            line_total=Decimal('10.00'),
        )

    def test_channel_maps_sum_to_total(self):
        start = timezone.now() - timezone.timedelta(days=1)
        end = timezone.now() + timezone.timedelta(seconds=5)
        rx_m, walk_m, loss_m = drug_outflow_channel_maps_in_window(
            [self.drug.id], start, end_dt=end
        )
        merged = _merge_qty_maps(rx_m, walk_m, loss_m)
        total_fn = drug_outflow_totals_in_window([self.drug.id], start, end_dt=end)
        self.assertEqual(merged.get(self.drug.id, 0), 4)
        self.assertEqual(total_fn.get(self.drug.id, 0), 4)
        self.assertEqual(walk_m.get(self.drug.id, 0), 4)
        self.assertEqual(rx_m.get(self.drug.id, 0), 0)
        self.assertEqual(loss_m.get(self.drug.id, 0), 0)

    def test_metrics_channel_fields_match_total(self):
        start = timezone.now() - timezone.timedelta(days=1)
        end = timezone.now() + timezone.timedelta(seconds=5)
        m = compute_pharmacy_drug_movement_metrics(
            [self.drug.id],
            movement_window_days=30,
            cover_alert_days=14,
            window_start=start,
            window_end=end,
        )[self.drug.id]
        self.assertEqual(
            int(m['out_rx']) + int(m['out_walk_in']) + int(m['out_loss']),
            int(m['total_out_window']),
        )
        self.assertEqual(int(m['total_out_window']), 4)


class PharmacyTopDrugRankTests(TestCase):
    def test_top_expensive_orders_by_unit_price(self):
        cheap = Drug.objects.create(
            name=f'Cheap {uuid.uuid4().hex[:6]}',
            strength='100mg',
            form='Tablet',
            pack_size='10',
            category='other',
            unit_price=Decimal('5.00'),
        )
        pricey = Drug.objects.create(
            name=f'Pricey {uuid.uuid4().hex[:6]}',
            strength='500mg',
            form='Tablet',
            pack_size='10',
            category='other',
            unit_price=Decimal('250.00'),
        )
        rows = top_expensive_formulary_drugs(limit=40)
        ids = [r['drug'].id for r in rows]
        self.assertLess(ids.index(pricey.id), ids.index(cheap.id))

    def test_top_moving_includes_dispensed_walk_in_sale(self):
        drug = Drug.objects.create(
            name=f'Mover {uuid.uuid4().hex[:6]}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            category='other',
        )
        sale = WalkInPharmacySale.objects.create(
            customer_name='Mover Customer',
            is_dispensed=True,
            dispensed_at=timezone.now(),
            sale_date=timezone.now(),
            payment_status='paid',
            total_amount=Decimal('20.00'),
            subtotal=Decimal('20.00'),
        )
        WalkInPharmacySaleItem.objects.create(
            sale=sale,
            drug=drug,
            quantity=12,
            unit_price=Decimal('2.00'),
            line_total=Decimal('24.00'),
        )
        start = timezone.now() - timezone.timedelta(days=1)
        end = timezone.now() + timezone.timedelta(seconds=5)
        rows = top_moving_drugs_ranked(
            start,
            end_dt=end,
            movement_window_days=30,
            window_start=start,
            window_end=end,
            limit=40,
        )
        self.assertTrue(any(r['drug'].id == drug.id for r in rows))
        mover = next(r for r in rows if r['drug'].id == drug.id)
        self.assertEqual(int(mover['m']['total_out_window']), 12)


class PharmacyCalendarWindowTests(TestCase):
    def setUp(self):
        self.drug = Drug.objects.create(
            name=f'CalDrug {uuid.uuid4().hex[:6]}',
            strength='250mg',
            form='Tablet',
            pack_size='10',
            category='other',
        )

    def test_inclusive_local_day_count_for_calendar_window(self):
        tz = timezone.get_current_timezone()
        ws = timezone.make_aware(datetime(2026, 4, 1, 0, 0, 0), tz)
        we = timezone.make_aware(datetime(2026, 4, 10, 15, 30, 0), tz)
        m = compute_pharmacy_drug_movement_metrics(
            [self.drug.id],
            movement_window_days=30,
            window_start=ws,
            window_end=we,
        )[self.drug.id]
        self.assertEqual(m['window_days'], 10)


class PharmacyUtilizationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=f'rx_{uuid.uuid4().hex[:8]}',
            password='testpass123',
        )
        self.client = Client()

    def _force_login_without_login_signals(self):
        """Test client has no REMOTE_ADDR; login signals may write LoginHistory and break tests."""
        from django.contrib.auth.signals import user_logged_in

        from hospital.auth_session_utils import create_user_session
        from hospital.signals_login_tracking import track_successful_login

        user_logged_in.disconnect(track_successful_login)
        user_logged_in.disconnect(create_user_session)
        try:
            self.client.force_login(self.user)
        finally:
            user_logged_in.connect(track_successful_login)
            user_logged_in.connect(create_user_session)

    def test_utilization_view_renders_chart_payload(self):
        self._force_login_without_login_signals()
        url = reverse('hospital:pharmacy_stock_utilization')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pharmacy utilization analytics')
        self.assertContains(response, 'Top 40 expensive drugs')
        self.assertContains(response, 'Top 40 fast-moving drugs')
        self.assertContains(response, 'id="pharmacy-utilization-chart-data"')
        self.assertContains(response, 'channelDoughnut')
        self.assertContains(response, 'dailyTrend')

    def test_calendar_month_query_renders(self):
        self._force_login_without_login_signals()
        url = reverse('hospital:pharmacy_stock_utilization')
        response = self.client.get(url, {'period': 'calendar_month'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calendar month to date')

    def test_utilization_pdf_export(self):
        self._force_login_without_login_signals()
        url = reverse('hospital:pharmacy_stock_utilization_pdf')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(b'%PDF', response.content[:8])
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_utilization_excel_export(self):
        self._force_login_without_login_signals()
        url = reverse('hospital:pharmacy_stock_utilization_excel')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment', response.get('Content-Disposition', ''))
        self.assertTrue(len(response.content) > 1000)
