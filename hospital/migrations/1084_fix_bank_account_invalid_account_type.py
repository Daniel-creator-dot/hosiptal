# Data migration: set invalid BankAccount.account_type to 'checking'

from django.db import migrations


VALID_ACCOUNT_TYPES = {'checking', 'savings', 'credit', 'operating', 'other'}


def fix_invalid_account_types(apps, schema_editor):
    BankAccount = apps.get_model('hospital', 'BankAccount')
    updated = BankAccount.objects.exclude(account_type__in=VALID_ACCOUNT_TYPES).update(account_type='checking')
    if updated:
        pass  # optional: log updated count


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1083_screening_template_for_company'),
    ]

    operations = [
        migrations.RunPython(fix_invalid_account_types, noop),
    ]
