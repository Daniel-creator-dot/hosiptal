"""
Check whether a chart-of-accounts row can be soft-deleted.
"""
from django.apps import apps


def _count(model_label, **filters):
    Model = apps.get_model(model_label)
    return Model.objects.filter(**filters).count()


def get_account_delete_blockers(account):
    """
    Return list of human-readable reasons why account cannot be deleted.
    Empty list means delete is allowed.
    """
    reasons = []
    account_id = account.pk

    if account.sub_accounts.filter(is_deleted=False).exists():
        child_count = account.sub_accounts.filter(is_deleted=False).count()
        reasons.append(f'Has {child_count} child sub-account(s)')

    gl_count = _count('hospital.GeneralLedger', account_id=account_id, is_deleted=False)
    if gl_count:
        reasons.append(f'Has {gl_count} general ledger entr{"y" if gl_count == 1 else "ies"}')

    adv_count = _count(
        'hospital.AdvancedGeneralLedger',
        account_id=account_id,
        is_deleted=False,
    )
    if adv_count:
        reasons.append(f'Has {adv_count} advanced ledger entr{"y" if adv_count == 1 else "ies"}')

    je_line_count = _count(
        'hospital.AdvancedJournalEntryLine',
        account_id=account_id,
        is_deleted=False,
    )
    if je_line_count:
        reasons.append(f'Used on {je_line_count} journal entry line(s)')

    fk_checks = [
        ('hospital.Transaction', 'debit_account_id', 'financial transaction(s) (debit)'),
        ('hospital.Transaction', 'credit_account_id', 'financial transaction(s) (credit)'),
        ('hospital.PaymentVoucher', 'expense_account_id', 'payment voucher(s) (expense)'),
        ('hospital.PaymentVoucher', 'payment_account_id', 'payment voucher(s) (payment)'),
        ('hospital.ReceiptVoucher', 'revenue_account_id', 'receipt voucher(s) (revenue)'),
        ('hospital.ReceiptVoucher', 'cash_account_id', 'receipt voucher(s) (cash)'),
        ('hospital.Cashbook', 'cash_account_id', 'cashbook entry/entries'),
        ('hospital.Cashbook', 'revenue_account_id', 'cashbook revenue link(s)'),
        ('hospital.Cashbook', 'expense_account_id', 'cashbook expense link(s)'),
        ('hospital.PettyCashTransaction', 'expense_account_id', 'petty cash transaction(s)'),
        ('hospital.ProcurementPurchase', 'expense_account_id', 'procurement purchase(s)'),
        ('hospital.ProcurementPurchase', 'liability_account_id', 'procurement liability link(s)'),
        ('hospital.ProcurementPurchase', 'payment_account_id', 'procurement payment link(s)'),
        ('hospital.InsuranceReceivable', 'receivable_account_id', 'insurance receivable record(s)'),
        ('hospital.RegistrationFee', 'revenue_account_id', 'registration fee setup(s)'),
        ('hospital.CashSale', 'revenue_account_id', 'cash sale setup(s)'),
        ('hospital.CashSale', 'cash_account_id', 'cash sale payment setup(s)'),
        ('hospital.AccountingCorporateAccount', 'receivable_account_id', 'corporate account(s)'),
        ('hospital.WithholdingReceivable', 'receivable_account_id', 'withholding receivable(s)'),
        ('hospital.DoctorCommission', 'doctor_receivable_account_id', 'doctor commission setup(s)'),
        ('hospital.DoctorCommission', 'hospital_revenue_account_id', 'doctor commission setup(s)'),
        ('hospital.IncomeGroup', 'account_id', 'income group(s)'),
    ]

    for model_label, field_name, label in fk_checks:
        try:
            count = _count(model_label, **{field_name: account_id, 'is_deleted': False})
        except Exception:
            try:
                count = _count(model_label, **{field_name: account_id})
            except Exception:
                continue
        if count:
            reasons.append(f'Linked to {count} {label}')

    return reasons


def can_delete_account(account):
    return not get_account_delete_blockers(account)
