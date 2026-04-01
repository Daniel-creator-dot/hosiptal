#!/usr/bin/env python
"""
Lookup script for Request ID: a723dbe4-c2bd-486f-b131-a562d56e8add
Searches across all request models in the system.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_procurement import ProcurementRequest
from hospital.models_blood_bank import TransfusionRequest
from hospital.models_workflow import PaymentRequest, Bill
from hospital.models_advanced import LeaveRequest
from hospital.models import Patient, Encounter, Staff
from hospital.models_accounting import Transaction, PaymentReceipt
from hospital.models_accounting_advanced import Expense
from hospital.models_audit import AuditLog, ActivityLog
from hospital.models_telemedicine import TelemedicineConsultation
import uuid

REQUEST_ID = "a723dbe4-c2bd-486f-b131-a562d56e8add"

def lookup_request(request_id):
    """Lookup request ID across all request models and other UUID models"""
    print(f"\n{'='*80}")
    print(f"Searching for Request ID: {request_id}")
    print(f"{'='*80}\n")
    
    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        print(f"❌ Invalid UUID format: {request_id}")
        return
    
    found = False
    
    # 1. ProcurementRequest (including deleted)
    print("1. Checking ProcurementRequest (active and deleted)...")
    try:
        procurement = ProcurementRequest.objects.filter(id=request_uuid).first()
        if procurement:
            found = True
            print(f"   ✅ FOUND: ProcurementRequest")
            print(f"   Request Number: {procurement.request_number}")
            print(f"   Status: {procurement.status}")
            print(f"   Requested By: {procurement.requested_by}")
            print(f"   Store: {procurement.requested_by_store}")
            print(f"   Request Date: {procurement.request_date}")
            print(f"   Priority: {procurement.priority}")
            print(f"   Estimated Total: {procurement.estimated_total}")
            print(f"   Is Deleted: {procurement.is_deleted}")
            print(f"   URL: /hms/procurement/requests/{request_id}/")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 2. TransfusionRequest (including deleted)
    print("\n2. Checking TransfusionRequest (active and deleted)...")
    try:
        transfusion = TransfusionRequest.objects.filter(id=request_uuid).first()
        if transfusion:
            found = True
            print(f"   ✅ FOUND: TransfusionRequest")
            print(f"   Request Number: {transfusion.request_number}")
            print(f"   Status: {transfusion.status}")
            print(f"   Patient: {transfusion.patient}")
            print(f"   Blood Type: {transfusion.blood_type}")
            print(f"   Units Requested: {transfusion.units_requested}")
            print(f"   Request Date: {transfusion.request_date}")
            print(f"   Is Deleted: {transfusion.is_deleted}")
            print(f"   URL: /hms/blood-bank/transfusion-request/{request_id}/")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 3. PaymentRequest (including deleted)
    print("\n3. Checking PaymentRequest (active and deleted)...")
    try:
        payment = PaymentRequest.objects.filter(id=request_uuid).first()
        if payment:
            found = True
            print(f"   ✅ FOUND: PaymentRequest")
            print(f"   Request Number: {payment.request_number}")
            print(f"   Status: {payment.status}")
            print(f"   Amount: {payment.amount}")
            print(f"   Requested By: {payment.requested_by}")
            print(f"   Request Date: {payment.request_date}")
            print(f"   Is Deleted: {payment.is_deleted}")
            print(f"   URL: /hms/cashier/payments/process/{request_id}/")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 4. LeaveRequest (including deleted)
    print("\n4. Checking LeaveRequest (active and deleted)...")
    try:
        leave = LeaveRequest.objects.filter(id=request_uuid).first()
        if leave:
            found = True
            print(f"   ✅ FOUND: LeaveRequest")
            print(f"   Staff: {leave.staff}")
            print(f"   Leave Type: {leave.leave_type}")
            print(f"   Start Date: {leave.start_date}")
            print(f"   End Date: {leave.end_date}")
            print(f"   Status: {leave.status}")
            print(f"   Days Requested: {leave.days_requested}")
            print(f"   Is Deleted: {leave.is_deleted}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 5. Patient (in case it's a patient ID)
    print("\n5. Checking Patient...")
    try:
        patient = Patient.objects.filter(id=request_uuid).first()
        if patient:
            found = True
            print(f"   ✅ FOUND: Patient")
            print(f"   MRN: {patient.mrn}")
            print(f"   Name: {patient.full_name}")
            print(f"   Is Deleted: {patient.is_deleted}")
            print(f"   URL: /hms/patients/{request_id}/")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 6. Encounter (in case it's an encounter ID)
    print("\n6. Checking Encounter...")
    try:
        encounter = Encounter.objects.filter(id=request_uuid).first()
        if encounter:
            found = True
            print(f"   ✅ FOUND: Encounter")
            print(f"   Patient: {encounter.patient}")
            print(f"   Department: {encounter.department}")
            print(f"   Status: {encounter.status}")
            print(f"   Visit Date: {encounter.visit_date}")
            print(f"   Is Deleted: {encounter.is_deleted}")
            print(f"   URL: /hms/encounters/{request_id}/")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 7. Staff
    print("\n7. Checking Staff...")
    try:
        staff = Staff.objects.filter(id=request_uuid).first()
        if staff:
            found = True
            print(f"   ✅ FOUND: Staff")
            print(f"   Name: {staff.full_name}")
            print(f"   Employee ID: {staff.employee_id}")
            print(f"   Department: {staff.department}")
            print(f"   Profession: {staff.profession}")
            print(f"   Is Deleted: {staff.is_deleted}")
            print(f"   URL: /hms/staff/{request_id}/")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 8. Bill
    print("\n8. Checking Bill...")
    try:
        bill = Bill.objects.filter(id=request_uuid).first()
        if bill:
            found = True
            print(f"   ✅ FOUND: Bill")
            print(f"   Bill Number: {bill.bill_number}")
            print(f"   Patient: {bill.patient}")
            print(f"   Amount: {bill.total_amount}")
            print(f"   Status: {bill.status}")
            print(f"   Is Deleted: {bill.is_deleted}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 9. Transaction
    print("\n9. Checking Transaction...")
    try:
        transaction = Transaction.objects.filter(id=request_uuid).first()
        if transaction:
            found = True
            print(f"   ✅ FOUND: Transaction")
            print(f"   Transaction Number: {transaction.transaction_number}")
            print(f"   Amount: {transaction.amount}")
            print(f"   Type: {transaction.transaction_type}")
            print(f"   Date: {transaction.transaction_date}")
            print(f"   Is Deleted: {transaction.is_deleted}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 10. PaymentReceipt
    print("\n10. Checking PaymentReceipt...")
    try:
        receipt = PaymentReceipt.objects.filter(id=request_uuid).first()
        if receipt:
            found = True
            print(f"   ✅ FOUND: PaymentReceipt")
            print(f"   Receipt Number: {getattr(receipt, 'receipt_number', 'N/A')}")
            print(f"   Patient: {getattr(receipt, 'patient', 'N/A')}")
            print(f"   Amount: {getattr(receipt, 'amount', 'N/A')}")
            print(f"   Date: {getattr(receipt, 'receipt_date', 'N/A')}")
            print(f"   Is Deleted: {receipt.is_deleted}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 11. Expense
    print("\n11. Checking Expense...")
    try:
        expense = Expense.objects.filter(id=request_uuid).first()
        if expense:
            found = True
            print(f"   ✅ FOUND: Expense")
            print(f"   Expense Number: {expense.expense_number}")
            print(f"   Amount: {expense.amount}")
            print(f"   Category: {expense.category}")
            print(f"   Date: {expense.expense_date}")
            print(f"   Is Deleted: {expense.is_deleted}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 12. AuditLog
    print("\n12. Checking AuditLog...")
    try:
        audit = AuditLog.objects.filter(id=request_uuid).first()
        if audit:
            found = True
            print(f"   ✅ FOUND: AuditLog")
            print(f"   User: {audit.user}")
            print(f"   Action: {audit.action_type}")
            print(f"   Model: {audit.model_name}")
            print(f"   Timestamp: {audit.created_at}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 13. ActivityLog
    print("\n13. Checking ActivityLog...")
    try:
        activity = ActivityLog.objects.filter(id=request_uuid).first()
        if activity:
            found = True
            print(f"   ✅ FOUND: ActivityLog")
            print(f"   User: {activity.user}")
            print(f"   Activity Type: {activity.activity_type}")
            print(f"   Description: {activity.description}")
            print(f"   Timestamp: {activity.created_at}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # 14. TelemedicineConsultation
    print("\n14. Checking TelemedicineConsultation...")
    try:
        telemed = TelemedicineConsultation.objects.filter(id=request_uuid).first()
        if telemed:
            found = True
            print(f"   ✅ FOUND: TelemedicineConsultation")
            print(f"   Patient: {telemed.patient}")
            print(f"   Doctor: {telemed.doctor}")
            print(f"   Status: {telemed.status}")
            print(f"   Consultation Date: {telemed.consultation_date}")
            print(f"   Is Deleted: {telemed.is_deleted}")
        else:
            print("   ❌ Not found")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Summary
    print(f"\n{'='*80}")
    if found:
        print(f"✅ Request ID found in database!")
    else:
        print(f"❌ Request ID not found in any request model")
        print(f"\nPossible reasons:")
        print(f"  - Request was deleted (is_deleted=True)")
        print(f"  - Request ID doesn't exist")
        print(f"  - Request is in a different model")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    lookup_request(REQUEST_ID)

