# Generated manually for Chart of Accounts subgroup layout

from django.db import migrations, models


def _numeric_code(account_code):
    digits = ''.join(c for c in (account_code or '') if c.isdigit())
    if not digits:
        return None
    try:
        return int(digits[:4])
    except ValueError:
        return None


def _infer_subgroup(account):
    if account.account_subgroup:
        return account.account_subgroup

    code = _numeric_code(account.account_code)
    name = (account.account_name or '').lower()
    acc_type = account.account_type

    if acc_type == 'asset':
        if code is not None:
            if 1800 <= code <= 1999:
                return 'non_current_asset'
            if 1000 <= code <= 1799:
                return 'current_asset'
        if any(k in name for k in ('depreciation', 'ppe', 'property', 'plant', 'equipment', 'land', 'building', 'intangible', 'long-term investment', 'deferred tax asset')):
            return 'non_current_asset'
        if any(k in name for k in ('cash', 'bank', 'receivable', 'inventory', 'prepayment', 'advance', 'undeposited')):
            return 'current_asset'
        return 'current_asset'

    if acc_type == 'liability':
        if code is not None:
            if 2500 <= code <= 2999:
                return 'non_current_liability'
            if 2000 <= code <= 2499:
                return 'current_liability'
        if any(k in name for k in ('long-term', 'long term', 'deferred tax liab')):
            return 'non_current_liability'
        return 'current_liability'

    if acc_type == 'expense':
        if code is not None:
            if 5100 <= code <= 5199:
                return 'direct_expense'
            if 5200 <= code <= 5999:
                return 'indirect_expense'
        if any(k in name for k in ('purchase', 'inventory', 'cost of sales', 'cogs', 'opening inventory', 'closing inventory')):
            return 'direct_expense'
        return 'indirect_expense'

    return ''


def backfill_account_subgroups(apps, schema_editor):
    Account = apps.get_model('hospital', 'Account')
    for account in Account.objects.filter(is_deleted=False):
        subgroup = _infer_subgroup(account)
        if subgroup and account.account_subgroup != subgroup:
            account.account_subgroup = subgroup
            account.save(update_fields=['account_subgroup'])


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1133_prescription_is_start_dose'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='account_subgroup',
            field=models.CharField(
                blank=True,
                choices=[
                    ('non_current_asset', 'Non-Current Asset'),
                    ('current_asset', 'Current Asset'),
                    ('non_current_liability', 'Non-Current Liability'),
                    ('current_liability', 'Current Liability'),
                    ('direct_expense', 'Direct Expense'),
                    ('indirect_expense', 'Indirect Expense'),
                ],
                default='',
                max_length=30,
            ),
        ),
        migrations.RunPython(backfill_account_subgroups, migrations.RunPython.noop),
    ]
