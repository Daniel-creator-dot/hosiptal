from django.test import SimpleTestCase

from hospital.pharmacy_consumption_estimate import (
    _merge_qty_maps,
    parse_positive_int,
)


class PharmacyConsumptionEstimateTests(SimpleTestCase):
    def test_parse_positive_int(self):
        self.assertEqual(parse_positive_int(None, 30), 30)
        self.assertEqual(parse_positive_int('45', 30), 45)
        self.assertEqual(parse_positive_int('0', 30), 30)
        self.assertEqual(parse_positive_int('9999', 30, max_val=100), 100)

    def test_merge_qty_maps(self):
        self.assertEqual(
            _merge_qty_maps({1: 5}, {1: 3, 2: 10}),
            {1: 8, 2: 10},
        )
