"""
Lab Analyzer Interface Service
Handles integration with lab analyzers via CSV, HL7, FHIR, etc.
"""
import csv
import json
import os
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from ..models import Order, LabTest, LabResult, Staff
from ..models_missing_features import LabAnalyzerInterface


class LabAnalyzerService:
    """Service for lab analyzer interface management"""
    
    @staticmethod
    def import_csv_results(file_path, analyzer_name=None):
        """
        Import lab results from CSV file
        
        CSV Format expected:
        OrderID,TestCode,Result,Units,ReferenceRange,Status,VerifiedBy,VerifiedAt
        
        Returns:
            dict with 'success', 'imported', 'errors'
        """
        imported = 0
        errors = []
        
        try:
            analyzer = None
            if analyzer_name:
                analyzer = LabAnalyzerInterface.objects.filter(
                    analyzer_name=analyzer_name,
                    is_active=True
                ).first()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        with transaction.atomic():
                            # Find order by ID or order number
                            order_id = row.get('OrderID', '').strip()
                            if not order_id:
                                errors.append(f"Row missing OrderID: {row}")
                                continue
                            
                            try:
                                order = Order.objects.get(pk=order_id, order_type='lab', is_deleted=False)
                            except Order.DoesNotExist:
                                errors.append(f"Order not found: {order_id}")
                                continue
                            
                            # Find test by code
                            test_code = row.get('TestCode', '').strip()
                            if not test_code:
                                errors.append(f"Row missing TestCode: {row}")
                                continue
                            
                            try:
                                test = LabTest.objects.get(code=test_code, is_active=True)
                            except LabTest.DoesNotExist:
                                errors.append(f"Test not found: {test_code}")
                                continue
                            
                            # Check if result already exists
                            lab_result, created = LabResult.objects.get_or_create(
                                order=order,
                                test=test,
                                is_deleted=False,
                                defaults={
                                    'value': row.get('Result', '').strip(),
                                    'units': row.get('Units', '').strip(),
                                    'range_low': row.get('ReferenceRange', '').split('-')[0].strip() if '-' in row.get('ReferenceRange', '') else '',
                                    'range_high': row.get('ReferenceRange', '').split('-')[1].strip() if '-' in row.get('ReferenceRange', '') else '',
                                    'status': row.get('Status', 'completed').lower(),
                                }
                            )
                            
                            if not created:
                                # Update existing result
                                lab_result.value = row.get('Result', '').strip()
                                lab_result.units = row.get('Units', '').strip()
                                
                                # Parse reference range
                                ref_range = row.get('ReferenceRange', '')
                                if '-' in ref_range:
                                    parts = ref_range.split('-')
                                    lab_result.range_low = parts[0].strip()
                                    lab_result.range_high = parts[1].strip() if len(parts) > 1 else ''
                                
                                lab_result.status = row.get('Status', 'completed').lower()
                            
                            # Handle verification
                            verified_by_name = row.get('VerifiedBy', '').strip()
                            if verified_by_name:
                                try:
                                    # Try to find staff by username or full name
                                    verified_by = Staff.objects.filter(
                                        user__username__icontains=verified_by_name
                                    ).first()
                                    if verified_by:
                                        lab_result.verified_by = verified_by
                                        lab_result.verified_at = timezone.now()
                                except Exception:
                                    pass
                            
                            # Parse verified_at if provided
                            verified_at_str = row.get('VerifiedAt', '').strip()
                            if verified_at_str:
                                try:
                                    lab_result.verified_at = datetime.fromisoformat(verified_at_str.replace('Z', '+00:00'))
                                except Exception:
                                    pass
                            
                            # Check if value is abnormal (basic check)
                            if lab_result.range_low and lab_result.range_high:
                                try:
                                    value_float = float(lab_result.value)
                                    low_float = float(lab_result.range_low)
                                    high_float = float(lab_result.range_high)
                                    lab_result.is_abnormal = not (low_float <= value_float <= high_float)
                                except ValueError:
                                    pass
                            
                            lab_result.save()
                            
                            # Create critical alert if needed
                            if lab_result.is_abnormal:
                                from ..models_missing_features import CriticalResultAlert
                                CriticalResultAlert.objects.create(
                                    lab_result=lab_result,
                                    alert_level='warning' if not lab_result.is_abnormal else 'critical',
                                    status='pending'
                                )
                            
                            imported += 1
                    
                    except Exception as e:
                        errors.append(f"Error processing row {row}: {str(e)}")
                        continue
            
            # Update analyzer last sync
            if analyzer:
                analyzer.last_sync = timezone.now()
                analyzer.save()
            
            return {
                'success': True,
                'imported': imported,
                'errors': errors
            }
        
        except Exception as e:
            return {
                'success': False,
                'imported': imported,
                'errors': [f"File error: {str(e)}"]
            }
    
    @staticmethod
    def import_hl7_results(hl7_message):
        """
        Import lab results from HL7 message
        This is a simplified implementation - full HL7 parsing would require a library
        
        Args:
            hl7_message: HL7 message string
            
        Returns:
            dict with 'success', 'imported', 'errors'
        """
        # This is a placeholder - full HL7 implementation would use a library like hl7
        # For now, return error suggesting CSV import
        return {
            'success': False,
            'imported': 0,
            'errors': ['HL7 import not yet fully implemented. Please use CSV import or contact system administrator.']
        }
    
    @staticmethod
    def export_results_csv(orders, output_path):
        """
        Export lab results to CSV format
        
        Args:
            orders: QuerySet of Order objects
            output_path: Path to save CSV file
            
        Returns:
            bool success
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'OrderID', 'PatientMRN', 'PatientName', 'TestCode', 'TestName',
                    'Result', 'Units', 'ReferenceRange', 'Status', 'IsAbnormal',
                    'VerifiedBy', 'VerifiedAt', 'OrderDate'
                ])
                
                for order in orders.filter(order_type='lab', is_deleted=False):
                    results = LabResult.objects.filter(order=order, is_deleted=False)
                    patient = order.encounter.patient if order.encounter else None
                    
                    for result in results:
                        ref_range = f"{result.range_low}-{result.range_high}" if result.range_low and result.range_high else ""
                        verified_by = result.verified_by.user.username if result.verified_by else ""
                        verified_at = result.verified_at.isoformat() if result.verified_at else ""
                        
                        writer.writerow([
                            str(order.id),
                            patient.mrn if patient else '',
                            patient.full_name if patient else '',
                            result.test.code,
                            result.test.name,
                            result.value,
                            result.units,
                            ref_range,
                            result.status,
                            'Yes' if result.is_abnormal else 'No',
                            verified_by,
                            verified_at,
                            order.requested_at.isoformat() if order.requested_at else ''
                        ])
            
            return True
        except Exception as e:
            return False

