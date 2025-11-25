# Cashbook - Next Day Hold Implementation

## Overview
The Cashbook feature has been updated to hold receipts and payments until the **next calendar day** before they can be classified to revenue/expense accounts.

## Key Changes

### 1. Hold Period
- **Previous**: 24 hours from creation time
- **Current**: Until the next calendar day (entry_date + 1 day)

### 2. Field Changes
- `held_until` changed from `DateTimeField` to `DateField`
- Automatically set to `entry_date + 1 day` when entry is created
- Example: Entry on 2025-01-15 → Can be classified from 2025-01-16

### 3. Classification Logic
- `can_classify()` method checks if today's date >= `held_until` date
- Entries can only be classified on or after the next day
- Status must be 'pending' to be classified

## Usage

### Creating a Cashbook Entry

```python
from hospital.models_accounting_advanced import Cashbook, Account
from django.utils import timezone

# Create a receipt entry
cashbook_entry = Cashbook.objects.create(
    entry_type='receipt',
    entry_date=timezone.now().date(),  # e.g., 2025-01-15
    amount=Decimal('1000.00'),
    payee_or_payer='John Doe',
    description='Consultation payment',
    cash_account=Account.objects.get(account_code='CASH001'),
    revenue_account=Account.objects.get(account_code='REV001'),
    status='pending'
)

# held_until is automatically set to 2025-01-16 (next day)
```

### Checking if Entry Can Be Classified

```python
# Check if entry can be classified
if cashbook_entry.can_classify():
    # Entry can be classified (today >= held_until)
    cashbook_entry.classify_to_revenue(
        user=request.user,
        revenue_account=cashbook_entry.revenue_account
    )
else:
    # Entry is still held until next day
    print(f"Can be classified from: {cashbook_entry.held_until}")
```

### Classification Process

1. **Entry Created** (e.g., 2025-01-15)
   - Status: `pending`
   - `held_until`: 2025-01-16 (automatically set)

2. **Next Day Arrives** (2025-01-16 or later)
   - `can_classify()` returns `True`
   - Entry can be classified to revenue/expense

3. **Classification**
   - Creates journal entry
   - Updates status to `classified`
   - Records classification timestamp and user

## Admin Interface Features

### List Display
- Shows `can_classify_now` column (boolean indicator)
- Displays `held_until` date
- Filters by status, entry type, date

### Bulk Actions
- **"Classify ready entries"** action available
- Automatically classifies all entries that:
  - Have status = 'pending'
  - Can be classified (today >= held_until)
  - Have required accounts set (revenue_account for receipts, expense_account for payments)

### Fieldsets
- Entry Information
- Payment Details
- Links (patient, invoice)
- Account Classification (with `can_classify_now` indicator)
- Accounting (journal entry)

## Example Workflow

### Day 1 (2025-01-15)
```
09:00 AM - Cash receipt of GHS 1,000 received
09:05 AM - Cashbook entry created:
  - entry_date: 2025-01-15
  - held_until: 2025-01-16 (auto-set)
  - status: pending
  
10:00 AM - Attempt to classify → ERROR: "Entry cannot be classified yet. Can be classified from 2025-01-16. Today is 2025-01-15."
```

### Day 2 (2025-01-16)
```
09:00 AM - Check entry → can_classify() = True
09:05 AM - Classify entry:
  - Creates journal entry
  - Status → classified
  - classified_at: 2025-01-16 09:05:00
  - classified_by: current user
```

## Benefits

1. **Clear Day-Based Hold**: Easier to understand and manage
2. **Batch Processing**: Can classify all entries from previous day at once
3. **Audit Trail**: Clear record of when entries were held and when classified
4. **Flexible**: Can still manually classify individual entries when ready

## Database Schema

```python
class Cashbook(BaseModel):
    entry_number = CharField(unique=True)
    entry_type = CharField(choices=['receipt', 'payment'])
    entry_date = DateField(default=timezone.now)
    amount = DecimalField()
    payee_or_payer = CharField()
    description = TextField()
    
    # Accounts
    revenue_account = ForeignKey(Account, null=True)
    expense_account = ForeignKey(Account, null=True)
    cash_account = ForeignKey(Account)
    
    # Status & Timing
    status = CharField(choices=['pending', 'classified', 'void'])
    held_until = DateField()  # Next day after entry_date
    classified_at = DateTimeField(null=True)
    classified_by = ForeignKey(User, null=True)
```

## Migration Notes

When running migrations, existing entries will need to have `held_until` set. The `save()` method automatically sets this to `entry_date + 1 day` for new entries.

For existing entries, you may want to run a data migration:

```python
from django.db import migrations
from datetime import timedelta

def set_held_until_dates(apps, schema_editor):
    Cashbook = apps.get_model('hospital', 'Cashbook')
    for entry in Cashbook.objects.filter(held_until__isnull=True):
        if entry.entry_date:
            entry.held_until = entry.entry_date + timedelta(days=1)
        else:
            entry.held_until = timezone.now().date() + timedelta(days=1)
        entry.save()
```

## Testing

Test scenarios:
1. ✅ Entry created today → `held_until` = tomorrow
2. ✅ Entry cannot be classified on same day
3. ✅ Entry can be classified on next day
4. ✅ Bulk classification works for multiple entries
5. ✅ Error handling for missing accounts

## Summary

The Cashbook now holds entries until the **next calendar day** instead of 24 hours, making it easier to:
- Process all previous day's entries in one batch
- Have clear day-based boundaries
- Understand when entries become available for classification

All entries are automatically set with `held_until = entry_date + 1 day` and can be classified starting from that date.

