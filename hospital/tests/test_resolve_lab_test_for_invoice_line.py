"""Lab catalog resolution for LAB-* / LABTEST-* invoice lines (corporate pack merge, pricing)."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from hospital.utils_invoice_line import (
    _lab_test_code_lookup_variants,
    _resolve_lab_test_from_suffix,
    resolve_lab_test_for_invoice_line,
)


class _StubServiceCode:
    def __init__(self, code, description=''):
        self.code = code
        self.description = description


class _StubLine:
    def __init__(self, code, description=''):
        self.service_code = _StubServiceCode(code, description)
        self.description = description
        self.prescription = None


class LabTestCodeVariantTests(SimpleTestCase):
    def test_numeric_suffix_yields_zero_padded_variants(self):
        variants = list(_lab_test_code_lookup_variants('000185'))
        self.assertIn('000185', variants)
        self.assertIn('185', variants)
        self.assertIn('0185', variants)

    def test_non_numeric_suffix_only_exact(self):
        variants = list(_lab_test_code_lookup_variants('CBC'))
        self.assertEqual(variants, ['CBC'])


class ResolveLabTestFromSuffixTests(SimpleTestCase):
    @patch('hospital.utils_invoice_line._lookup_lab_test_by_code_variants')
    @patch('hospital.utils_invoice_line._lookup_lab_test_by_descriptions')
    def test_tries_code_before_uuid(self, mock_by_desc, mock_by_code):
        mock_by_code.return_value = None
        lab_pk = uuid4()
        with patch('hospital.models.LabTest.objects') as mock_objects:
            mock_objects.filter.return_value.first.return_value = MagicMock(pk=lab_pk)
            result = _resolve_lab_test_from_suffix(str(lab_pk))
        self.assertIsNotNone(result)
        mock_by_code.assert_called_once()
        mock_by_desc.assert_not_called()

    @patch('hospital.utils_invoice_line._lookup_lab_test_by_code_variants')
    @patch('hospital.utils_invoice_line._lookup_lab_test_by_descriptions')
    def test_non_uuid_numeric_falls_back_to_description(self, mock_by_desc, mock_by_code):
        mock_by_code.return_value = None
        lab = MagicMock()
        mock_by_desc.return_value = lab
        result = _resolve_lab_test_from_suffix('000185', description_hints=['Full blood count'])
        self.assertIs(result, lab)
        mock_by_desc.assert_called_once()


class ResolveLabTestForInvoiceLineTests(SimpleTestCase):
    @patch('hospital.utils_invoice_line._resolve_lab_test_from_suffix')
    def test_lab_prefix_delegates_to_suffix_resolver(self, mock_resolve):
        mock_resolve.return_value = MagicMock()
        line = _StubLine('LAB-000185', 'FBC')
        resolve_lab_test_for_invoice_line(line)
        mock_resolve.assert_called_once_with('000185', description_hints=('FBC', 'FBC'))

    @patch('hospital.utils_invoice_line._resolve_lab_test_from_suffix')
    def test_labtest_prefix_delegates_to_suffix_resolver(self, mock_resolve):
        mock_resolve.return_value = MagicMock()
        line = _StubLine('LABTEST-000185', 'FBC')
        resolve_lab_test_for_invoice_line(line)
        mock_resolve.assert_called_once_with('000185', description_hints=('FBC', 'FBC'))

    @patch('hospital.models.LabTest.objects')
    def test_lab_numeric_code_suffix_does_not_raise_validation_error(self, mock_objects):
        """LAB-000185 is a catalog code, not a UUID pk."""
        mock_qs = MagicMock()
        mock_objects.filter.return_value = mock_qs
        mock_qs.filter.return_value.first.return_value = None

        result = resolve_lab_test_for_invoice_line(_StubLine('LAB-000185'))

        self.assertIsNone(result)
        for call in mock_objects.filter.call_args_list:
            kwargs = call[1]
            if 'pk' in kwargs and kwargs['pk'] == '000185':
                self.fail('pk filter must not receive non-UUID lab code suffix')

    @patch('hospital.utils_invoice_line._lookup_lab_test_by_code_variants')
    def test_resolves_when_catalog_code_uses_unpadded_digits(self, mock_by_code):
        """Service code LAB-000185 should match LabTest.code 185 via variant lookup."""
        lab = MagicMock()
        mock_by_code.return_value = lab
        result = resolve_lab_test_for_invoice_line(_StubLine('LAB-000185'))
        self.assertIs(result, lab)
        mock_by_code.assert_called_once_with('000185')

    @patch('hospital.utils_invoice_line._lookup_lab_test_by_code_variants')
    @patch('hospital.models.LabTest.objects')
    def test_lab_uuid_suffix_queries_by_pk(self, mock_objects, mock_by_code):
        lab_pk = uuid4()
        mock_lab = MagicMock(pk=lab_pk)
        mock_by_code.return_value = None
        mock_objects.filter.return_value.first.return_value = mock_lab
        result = resolve_lab_test_for_invoice_line(_StubLine(f'LAB-{lab_pk}'))
        self.assertIs(result, mock_lab)
        mock_objects.filter.assert_called_with(pk=lab_pk, is_deleted=False)
