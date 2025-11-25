# Finance & Accounting Quick Reference Guide

## 🚀 Quick Start

### Daily Tasks

#### 1. Start Cashier Session
```python
from hospital.models_workflow import CashierSession

session = CashierSession.objects.create(
    cashier=request.user,
    opening_cash=Decimal('500.00')  # Starting cash in drawer
)
```

#### 2. Process Patient Payment
```python
# Method 1: Simple payment (one invoice)
invoice.mark_as_paid(
    amount=100.00,
    payment_method='cash',
    processed_by=request.user,
    reference_number='CHECK-12345'  # Optional
)

# Method 2: Payment allocation (multiple invoices)
from hospital.models_accounting import PaymentAllocation

transaction = Transaction.objects.create(
    transaction_type='payment_received',
    patient=patient,
    amount=500.00,
    payment_method='cash',
    processed_by=request.user
)

PaymentAllocation.allocate_payment(
    transaction=transaction,
    invoices_with_amounts=[
        (invoice1, 200.00),
        (invoice2, 300.00),
    ]
)
```

#### 3. Close Cashier Session
```python
session.status = 'closed'
session.closed_at = timezone.now()
session.actual_cash = Decimal('1200.00')  # Actual cash counted
session.save()

# Check for discrepancies
variance = session.actual_cash - session.expected_cash
if variance != 0:
    print(f"Cash variance: ${variance}")
```

#### 4. End of Day Reconciliation
```bash
python manage.py finance_reconcile --all
```

### Weekly Tasks

#### 1. Review AR Aging
```bash
python manage.py finance_report --ar-aging
```

#### 2. Update All AR Aging
```bash
python manage.py finance_reconcile --ar
```

#### 3. Send Payment Reminders
Check AR entries with `aging_bucket` = '31-60' or '61-90'

### Monthly Tasks

#### 1. Generate Revenue Report
```bash
python manage.py finance_report --revenue --start-date 2025-01-01 --end-date 2025-01-31
```

#### 2. Month-End Reconciliation
```bash
# Full reconciliation
python manage.py finance_reconcile --all --fix

# Verify GL balance
python manage.py finance_reconcile --gl
```

#### 3. Close Period
```python
# Review all journal entries
from hospital.models_accounting import JournalEntry

unposted = JournalEntry.objects.filter(is_posted=False)
for entry in unposted:
    if entry.validate_balanced():
        entry.post(user=request.user)
```

## 📊 Common Scenarios

### Scenario 1: Partial Payment
```python
# Patient pays $50 on a $200 invoice
invoice.mark_as_paid(
    amount=50.00,
    payment_method='cash',
    processed_by=cashier
)
# Result: Invoice status → 'partially_paid', balance → $150
```

### Scenario 2: Multiple Invoice Payment
```python
# Patient pays $300 total for multiple invoices
transaction = Transaction.objects.create(
    transaction_type='payment_received',
    patient=patient,
    amount=300.00,
    payment_method='cash',
    processed_by=cashier
)

PaymentAllocation.allocate_payment(
    transaction=transaction,
    invoices_with_amounts=[
        (invoice1, 100.00),  # Invoice 1: $100
        (invoice2, 150.00),  # Invoice 2: $150
        (invoice3, 50.00),   # Invoice 3: $50 (partial)
    ]
)
```

### Scenario 3: Refund Processing
```python
transaction = Transaction.objects.create(
    transaction_type='refund_issued',
    invoice=original_invoice,
    patient=patient,
    amount=50.00,
    payment_method='cash',
    processed_by=cashier,
    notes='Refund for cancelled service'
)
```

### Scenario 4: Manual Journal Entry
```python
from hospital.models_accounting import JournalEntry, JournalEntryLine

# Create journal entry
je = JournalEntry.objects.create(
    entry_date=date.today(),
    description='Adjustment for billing error',
    entered_by=request.user
)

# Add lines (must balance!)
JournalEntryLine.objects.create(
    journal_entry=je,
    account=debit_account,
    debit_amount=100.00,
    credit_amount=0,
    description='Correction'
)

JournalEntryLine.objects.create(
    journal_entry=je,
    account=credit_account,
    debit_amount=0,
    credit_amount=100.00,
    description='Correction'
)

# Validate and post
if je.validate_balanced():
    je.post(user=request.user)
```

### Scenario 5: Write-Off Bad Debt
```python
# Create write-off transaction
transaction = Transaction.objects.create(
    transaction_type='write_off',
    invoice=invoice,
    patient=patient,
    amount=invoice.balance,
    processed_by=finance_manager,
    notes='Uncollectable after 180 days'
)

# Update invoice
invoice.status = 'cancelled'
invoice.balance = 0
invoice.save()
```

## 🔍 Troubleshooting

### Issue: Invoice balance doesn't match payments

```python
# Check validation
from hospital.utils_finance import FinancialValidator

result = FinancialValidator.validate_invoice_balance_vs_transactions(invoice)
print(result)

# View all payments
payments = Transaction.objects.filter(
    invoice=invoice,
    transaction_type='payment_received'
)
total_paid = sum(p.amount for p in payments)
print(f"Total payments: ${total_paid}")
print(f"Invoice balance: ${invoice.balance}")
```

### Issue: AR entry doesn't match invoice

```python
# Check AR sync
result = FinancialValidator.validate_ar_vs_invoice(invoice)
print(result)

# Fix manually if needed
ar_entry = AccountsReceivable.objects.get(invoice=invoice)
ar_entry.outstanding_amount = invoice.balance
ar_entry.update_aging()
ar_entry.save()
```

### Issue: General Ledger not balanced

```bash
# Check GL balance
python manage.py finance_reconcile --gl

# Review recent entries
python manage.py shell
>>> from hospital.models_accounting import GeneralLedger
>>> recent = GeneralLedger.objects.all()[:20]
>>> for entry in recent:
...     print(f"{entry.entry_number}: DR {entry.debit_amount} CR {entry.credit_amount}")
```

### Issue: Cashier session variance

```python
# Check session details
from hospital.utils_finance import FinancialValidator

result = FinancialValidator.validate_cashier_session(session)
print(result)

# Review transactions
transactions = Transaction.objects.filter(
    processed_by=session.cashier,
    payment_method='cash',
    transaction_date__gte=session.opened_at,
    transaction_date__lte=session.closed_at
)
```

## 📋 Admin Interface Quick Actions

### Journal Entries
1. Go to: Admin → Accounting → Journal Entries
2. Select entries
3. Actions:
   - **Validate journal entries are balanced** - Check before posting
   - **Post journal entries to GL** - Post after validation

### Accounts Receivable
1. Go to: Admin → Accounting → Accounts Receivable
2. Select entries
3. Actions:
   - **Update aging buckets** - Refresh aging
   - **Reconcile with invoices** - Verify sync

### General Ledger
1. Go to: Admin → Accounting → General Ledger
2. Select any entries
3. Actions:
   - **Validate general ledger balance** - Check if balanced

## 🎯 Key Performance Indicators

### Monitor These Daily:
- Total AR outstanding
- AR by aging bucket
- Today's revenue
- Cashier session variances

### Monitor These Weekly:
- AR > 60 days
- Write-offs
- Revenue by service category

### Monitor These Monthly:
- Total revenue vs target
- Collection rate
- Days in AR
- Bad debt percentage

## 🔐 Security & Permissions

### Cashier Role
- Process payments
- Issue receipts
- Manage cashier sessions
- View patient invoices

### Accountant Role
- All cashier permissions
- Create journal entries
- Run reconciliations
- Generate reports
- Manage AR

### Finance Manager Role
- All accountant permissions
- Approve write-offs
- Post journal entries
- Access all financial reports

## 📞 Quick Help

### Command Not Working?
```bash
# Make sure you're in the right directory
cd C:\Users\user\chm

# Check Python is working
python --version

# Check Django is installed
python manage.py --version
```

### Data Looks Wrong?
```bash
# Run full reconciliation with fixes
python manage.py finance_reconcile --all --fix

# Check for issues without fixing
python manage.py finance_reconcile --all
```

### Need a Report?
```bash
# AR Aging
python manage.py finance_report --ar-aging

# Revenue (current month)
python manage.py finance_report --revenue

# Custom date range
python manage.py finance_report --revenue --start-date 2025-01-01 --end-date 2025-01-31
```

## 💡 Tips & Best Practices

1. **Always close cashier sessions** - Don't leave them open overnight
2. **Run reconciliation before month-end** - Catch issues early
3. **Validate journal entries** before posting - Can't unpost!
4. **Use payment allocation** for complex scenarios - Better audit trail
5. **Update AR aging weekly** - Keep reports accurate
6. **Review variance reports** - Investigate discrepancies promptly
7. **Back up before major changes** - Safety first!

## 🆘 Emergency Contacts

If you encounter critical issues:
1. Check this guide first
2. Run `python manage.py finance_reconcile --all`
3. Review error messages carefully
4. Document what you were doing when the issue occurred
5. Contact system administrator with details

---
**Last Updated**: November 2025
**Version**: 2.0
































