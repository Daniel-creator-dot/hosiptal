from decimal import Decimal
from django.test import SimpleTestCase

from hospital.utils_invoice_line import (
    align_invoice_breakdown_to_balance,
    clean_bill_line_description,
    drug_label_for_bill,
)


class CleanBillLineDescriptionTests(SimpleTestCase):
    def test_strips_sale_ps_marker(self):
        self.assertEqual(
            clean_bill_line_description('Oxytocin Injection  (Sale PS202608061433220008)'),
            'Oxytocin Injection',
        )

    def test_strips_trailing_zero_strength(self):
        self.assertEqual(
            clean_bill_line_description('Vitamin K Injection 0 (Sale PS202608061738480013)'),
            'Vitamin K Injection',
        )
        self.assertEqual(
            clean_bill_line_description('Surgical Gloves 7.5 0'),
            'Surgical Gloves 7.5',
        )
        self.assertEqual(clean_bill_line_description('CORD CLAMP  0'), 'CORD CLAMP')

    def test_dedupes_repeated_size_token(self):
        self.assertEqual(clean_bill_line_description('SYRINGE 2ML  2ML'), 'SYRINGE 2ML')
        self.assertEqual(clean_bill_line_description('Syringe 10ML  10ml'), 'Syringe 10ML')
        self.assertEqual(clean_bill_line_description('Vicryl - Sutures 1 1'), 'Vicryl - Sutures 1')
        self.assertEqual(
            clean_bill_line_description('Vicryl - Sutures 2./0 2./0'),
            'Vicryl - Sutures 2./0',
        )

    def test_keeps_real_strength(self):
        self.assertEqual(
            clean_bill_line_description('Misoprostol ( Cytotec ) Tablet 200mg'),
            'Misoprostol ( Cytotec ) Tablet 200mg',
        )

    def test_drug_label_skips_zero_strength(self):
        self.assertEqual(drug_label_for_bill('Vitamin K Injection', '0'), 'Vitamin K Injection')
        self.assertEqual(drug_label_for_bill('Paracetamol', '500mg'), 'Paracetamol 500mg')


class AlignInvoiceBreakdownTests(SimpleTestCase):
    def test_scales_lines_to_balance(self):
        rows = [
            {'description': 'A', 'quantity': Decimal('2'), 'unit_price': Decimal('64.25'), 'amount': Decimal('128.50')},
            {'description': 'B', 'quantity': Decimal('1'), 'unit_price': Decimal('65.00'), 'amount': Decimal('65.00')},
        ]
        align_invoice_breakdown_to_balance(rows, Decimal('62.50'))
        self.assertEqual(sum(r['amount'] for r in rows), Decimal('62.50'))
        self.assertEqual(rows[0]['amount'] + rows[1]['amount'], Decimal('62.50'))
