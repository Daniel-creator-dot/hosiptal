"""
Backfill receipt and COGS journal entries for medical supplies / lab consumables.
Receipt: Dr 5120 Closing Inventory / Cr 2100 Trade Payables
Issue/transfer: Dr 5600 Purchases - Medical Supplies and Consumables / Cr 5120 Closing Inventory
Also captures supplier sub-ledger for InventoryItem preferred_supplier.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from hospital.models_inventory_advanced import InventoryTransaction
from hospital.models_lab_management import ReagentTransaction
from hospital.models_procurement import InventoryItem
from hospital.models_supplier_payables import (
    SupplierPayableLine,
    post_inventory_item_receipt_accounting,
    post_inventory_item_supplier_payable,
)
from hospital.services.inventory_account_mapping import (
    resolve_inventory_category_from_item,
    uses_closing_inventory_posting,
)
from hospital.services.inventory_gl_service import (
    _existing_posted_entry,
    post_inventory_cogs_gl,
    post_inventory_receipt_gl,
)


class Command(BaseCommand):
    help = (
        'Backfill medical supplies GL (5120/5600) and supplier AP for inventory '
        'and lab reagent transactions'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be posted without creating journals',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5000,
            help='Max rows per transaction type (default 5000)',
        )
        parser.add_argument(
            '--since',
            default=None,
            help='Optional filter: transaction/item created on/after YYYY-MM-DD',
        )
        parser.add_argument(
            '--until',
            default=None,
            help='Optional filter: transaction/item created on/before YYYY-MM-DD',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        since = date.fromisoformat(options['since']) if options['since'] else None
        until = date.fromisoformat(options['until']) if options['until'] else None
        posted = 0
        skipped = 0
        payables = 0

        receipt_qs = InventoryTransaction.objects.filter(
            transaction_type='receipt',
            is_deleted=False,
        )
        if since:
            receipt_qs = receipt_qs.filter(transaction_date__date__gte=since)
        if until:
            receipt_qs = receipt_qs.filter(transaction_date__date__lte=until)
        receipt_qs = (
            receipt_qs.select_related(
                'inventory_item',
                'inventory_item__category',
                'inventory_item__store',
                'inventory_item__preferred_supplier',
            )
            .order_by('created')[:limit]
        )
        for txn in receipt_qs:
            ref = f'STOCK-RCV-ITEM-{txn.pk}'
            if _existing_posted_entry(ref):
                skipped += 1
            else:
                item = txn.inventory_item
                category_key = resolve_inventory_category_from_item(item)
                amount = Decimal(str(txn.total_value or 0)).quantize(Decimal('0.01'))
                if amount <= 0:
                    skipped += 1
                elif dry_run:
                    self.stdout.write(
                        f'Would post receipt GHS {amount} ({category_key}) {ref} — {item.item_name}'
                    )
                    posted += 1
                else:
                    result = post_inventory_receipt_gl(
                        category_key=category_key,
                        amount=amount,
                        reference=ref,
                        description=f'Backfill store receipt: {item.item_name} qty {txn.quantity}',
                        entry_date=(
                            txn.transaction_date.date()
                            if txn.transaction_date
                            else timezone.now().date()
                        ),
                    )
                    if result.get('posted') or result.get('already_posted'):
                        posted += 1
                    else:
                        skipped += 1

            item = txn.inventory_item
            supplier = getattr(item, 'preferred_supplier', None)
            if supplier and not dry_run:
                qty = abs(Decimal(str(txn.quantity or 0)))
                unit = Decimal(str(txn.unit_cost or item.unit_cost or 0))
                line = post_inventory_item_supplier_payable(
                    inventory_item=item,
                    quantity=qty,
                    unit_cost=unit,
                    supplier=supplier,
                )
                if line:
                    payables += 1
            elif supplier and dry_run:
                ref_pay = f'INV-ITEM-{item.pk}'
                exists = SupplierPayableLine.objects.filter(
                    reference=ref_pay, is_deleted=False
                ).exists()
                if not exists:
                    payables += 1

        # Opening stock on InventoryItem with no receipt transactions (e.g. Neuseite supplies)
        item_qs = InventoryItem.objects.filter(is_deleted=False).select_related(
            'category', 'store', 'preferred_supplier'
        )
        if since:
            item_qs = item_qs.filter(created__date__gte=since)
        if until:
            item_qs = item_qs.filter(created__date__lte=until)
        item_qs = item_qs.order_by('created')[:limit]
        for item in item_qs:
            category_key = resolve_inventory_category_from_item(item)
            if not uses_closing_inventory_posting(category_key) and not item.preferred_supplier_id:
                continue
            qty = Decimal(str(item.quantity_on_hand or 0))
            unit = Decimal(str(item.unit_cost or 0))
            amount = (qty * unit).quantize(Decimal('0.01'))
            if amount <= 0:
                skipped += 1
                continue
            has_txn = InventoryTransaction.objects.filter(
                inventory_item=item, transaction_type='receipt', is_deleted=False
            ).exists()
            if has_txn:
                continue
            open_ref = f'STOCK-RCV-ITEMOPEN-{item.pk}'
            if _existing_posted_entry(open_ref):
                skipped += 1
            elif dry_run:
                self.stdout.write(
                    f'Would post opening receipt GHS {amount} ({category_key}) '
                    f'{open_ref} — {item.item_name} '
                    f'supplier={getattr(item.preferred_supplier, "name", None)}'
                )
                posted += 1
                if item.preferred_supplier_id:
                    payables += 1
            else:
                result = post_inventory_item_receipt_accounting(
                    inventory_item=item,
                    quantity=qty,
                    unit_cost=unit,
                    supplier=item.preferred_supplier,
                    reference=open_ref,
                    entry_date=item.created.date() if item.created else timezone.now().date(),
                )
                if result.get('gl') and (
                    result['gl'].get('posted') or result['gl'].get('already_posted')
                ):
                    posted += 1
                else:
                    # still count if GL skipped zero but payable created
                    skipped += 1
                if result.get('payable'):
                    payables += 1

        cogs_qs = InventoryTransaction.objects.filter(
            transaction_type__in=['transfer_out', 'issue'],
            is_deleted=False,
        )
        if since:
            cogs_qs = cogs_qs.filter(transaction_date__date__gte=since)
        if until:
            cogs_qs = cogs_qs.filter(transaction_date__date__lte=until)
        cogs_qs = (
            cogs_qs.select_related(
                'inventory_item', 'inventory_item__category', 'inventory_item__store'
            )
            .order_by('created')[:limit]
        )
        for txn in cogs_qs:
            prefix = 'COGS-XFER' if txn.transaction_type == 'transfer_out' else 'COGS-ISSUE'
            ref = f'{prefix}-{txn.pk}'
            if _existing_posted_entry(ref):
                skipped += 1
                continue
            item = txn.inventory_item
            category_key = resolve_inventory_category_from_item(item)
            if not uses_closing_inventory_posting(category_key):
                skipped += 1
                continue
            amount = Decimal(str(txn.total_value or 0)).quantize(Decimal('0.01'))
            if amount <= 0:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(
                    f'Would post COGS GHS {amount} ({category_key}) {ref} — {item.item_name}'
                )
                posted += 1
                continue
            result = post_inventory_cogs_gl(
                category_key=category_key,
                amount=amount,
                reference=ref,
                description=f'Backfill {txn.transaction_type}: {item.item_name}',
                entry_date=(
                    txn.transaction_date.date()
                    if txn.transaction_date
                    else timezone.now().date()
                ),
            )
            if result.get('posted') or result.get('already_posted'):
                posted += 1
            else:
                skipped += 1

        reagent_qs = ReagentTransaction.objects.filter(
            transaction_type='used',
            is_deleted=False,
            gl_journal_entry__isnull=True,
        )
        if since:
            reagent_qs = reagent_qs.filter(created__date__gte=since)
        if until:
            reagent_qs = reagent_qs.filter(created__date__lte=until)
        reagent_qs = reagent_qs.select_related('reagent').order_by('created')[:limit]
        for txn in reagent_qs:
            ref = f'COGS-REAGENT-{txn.pk}'
            if _existing_posted_entry(ref):
                skipped += 1
                continue
            unit_cost = txn.reagent.unit_cost or Decimal('0')
            amount = (
                Decimal(str(txn.quantity or 0)) * Decimal(str(unit_cost))
            ).quantize(Decimal('0.01'))
            if amount <= 0:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(
                    f'Would post reagent COGS GHS {amount} {ref} — {txn.reagent.name}'
                )
                posted += 1
                continue
            result = post_inventory_cogs_gl(
                category_key='lab',
                amount=amount,
                reference=ref,
                description=f'Backfill lab reagent COGS: {txn.reagent.name}',
                reagent_transaction=txn,
                entry_date=txn.created.date() if txn.created else timezone.now().date(),
            )
            if result.get('posted') or result.get('already_posted'):
                posted += 1
            else:
                skipped += 1

        mode = 'DRY RUN' if dry_run else 'LIVE'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: {posted} posted/would-post, {skipped} skipped, '
                f'{payables} supplier payable lines'
            )
        )
