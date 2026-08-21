"""Tests for medical consumables GL category resolution (5120 / 5600)."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from hospital.services.inventory_account_mapping import (
    CLOSING_INVENTORY_CODE,
    MEDICAL_SUPPLIES_PURCHASES_CODE,
    get_inventory_accounts,
    procurement_item_is_lab_reagent,
    resolve_inventory_category_from_item,
    uses_closing_inventory_posting,
)


class MedicalSuppliesGLMappingTests(SimpleTestCase):
    def test_lab_and_consumables_use_closing_inventory_accounts(self):
        lab_accounts = get_inventory_accounts('lab')
        self.assertEqual(lab_accounts['receipt_debit'], CLOSING_INVENTORY_CODE)
        self.assertEqual(lab_accounts['cogs'], MEDICAL_SUPPLIES_PURCHASES_CODE)
        self.assertEqual(lab_accounts['cogs_credit'], CLOSING_INVENTORY_CODE)

        consumables_accounts = get_inventory_accounts('consumables')
        self.assertEqual(consumables_accounts['receipt_debit'], CLOSING_INVENTORY_CODE)
        self.assertEqual(consumables_accounts['cogs'], MEDICAL_SUPPLIES_PURCHASES_CODE)

    def test_uses_closing_inventory_posting(self):
        self.assertTrue(uses_closing_inventory_posting('lab'))
        self.assertTrue(uses_closing_inventory_posting('consumables'))
        self.assertFalse(uses_closing_inventory_posting('pharmacy'))

    def test_resolve_category_from_inventory_category_name(self):
        item = MagicMock()
        item.drug_id = None
        item.category = MagicMock(is_for_pharmacy=False, name='Medical Supplies', code='SUPPLY')
        item.store = None
        self.assertEqual(resolve_inventory_category_from_item(item), 'consumables')

    def test_resolve_category_lab_store_fallback(self):
        item = MagicMock()
        item.drug_id = None
        item.category = None
        item.store = MagicMock(store_type='lab')
        self.assertEqual(resolve_inventory_category_from_item(item), 'lab')

    def test_resolve_category_main_store_non_drug_fallback(self):
        item = MagicMock()
        item.drug_id = None
        item.category = None
        item.store = MagicMock(store_type='main')
        self.assertEqual(resolve_inventory_category_from_item(item), 'consumables')

    def test_procurement_item_is_lab_reagent(self):
        proc_item = MagicMock()
        proc_item.specifications = '{"is_lab_reagent": true}'
        self.assertTrue(procurement_item_is_lab_reagent(proc_item))
        proc_item.specifications = '{}'
        self.assertFalse(procurement_item_is_lab_reagent(proc_item))


class MedicalSuppliesGLPostingTests(SimpleTestCase):
    @patch('hospital.services.inventory_gl_service.inventory_gl_enabled', return_value=True)
    @patch('hospital.services.inventory_gl_service._post_balanced_journal')
    @patch('hospital.services.inventory_gl_service._ensure_account')
    @patch('hospital.services.inventory_gl_service._existing_posted_entry', return_value=None)
    @patch('hospital.services.inventory_gl_service._gl_reference_lock', return_value=True)
    @patch('hospital.services.inventory_gl_service._gl_reference_unlock')
    def test_receipt_posts_dr_5120_cr_2100_for_lab(
        self, _unlock, _lock, _existing, ensure_account, post_journal, _enabled
    ):
        from hospital.services.inventory_gl_service import post_inventory_receipt_gl

        debit = MagicMock()
        credit = MagicMock()
        ensure_account.side_effect = [debit, credit]
        post_journal.return_value = MagicMock()

        result = post_inventory_receipt_gl(
            category_key='lab',
            amount=Decimal('100.00'),
            reference='STOCK-RCV-ITEM-test',
            description='Test lab receipt',
        )
        self.assertTrue(result.get('posted'))
        post_journal.assert_called_once()
        kwargs = post_journal.call_args.kwargs
        self.assertIs(kwargs['debit_account'], debit)
        self.assertIs(kwargs['credit_account'], credit)

    @patch('hospital.services.inventory_gl_service.inventory_gl_enabled', return_value=True)
    @patch('hospital.services.inventory_gl_service._post_balanced_journal')
    @patch('hospital.services.inventory_gl_service._ensure_account')
    @patch('hospital.services.inventory_gl_service._existing_posted_entry', return_value=None)
    @patch('hospital.services.inventory_gl_service._gl_reference_lock', return_value=True)
    @patch('hospital.services.inventory_gl_service._gl_reference_unlock')
    def test_cogs_posts_dr_5600_cr_5120_for_consumables(
        self, _unlock, _lock, _existing, ensure_account, post_journal, _enabled
    ):
        from hospital.services.inventory_gl_service import post_inventory_cogs_gl

        debit = MagicMock()
        credit = MagicMock()
        ensure_account.side_effect = [debit, credit]
        post_journal.return_value = MagicMock()

        result = post_inventory_cogs_gl(
            category_key='consumables',
            amount=Decimal('50.00'),
            reference='COGS-XFER-test',
            description='Test consumables COGS',
        )
        self.assertTrue(result.get('posted'))
        post_journal.assert_called_once()


class SyncClosingStockUrlTests(SimpleTestCase):
    def test_trial_balance_sync_url_reverses(self):
        self.assertEqual(
            reverse('hospital:sync_closing_stock'),
            '/hms/accounting/trial-balance/sync-closing-stock/',
        )
