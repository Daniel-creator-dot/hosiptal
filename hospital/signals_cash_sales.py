"""
Cash Sales Signals - Auto-create CashSale from WalkInPharmacySale
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

AUTO_CASH_SALE_ENABLED = True


@receiver(post_save, sender='hospital.WalkInPharmacySale')
def auto_create_cash_sale_from_walkin(sender, instance, created, **kwargs):
    """
    Automatically create CashSale when WalkInPharmacySale is paid
    """
    if not AUTO_CASH_SALE_ENABLED:
        return
    
    # Only create CashSale when payment is received (status changes to 'paid')
    if instance.payment_status != 'paid':
        return
    
    # Only create if payment method is cash
    # Note: WalkInPharmacySale doesn't have payment_method field directly,
    # so we'll create for all paid sales (can be filtered later if needed)
    
    try:
        with transaction.atomic():
            from .models_accounting_advanced import CashSale, Account
            
            # Check if CashSale already exists for this walk-in sale
            existing = CashSale.objects.filter(
                description__icontains=instance.sale_number,
                is_deleted=False
            ).first()
            
            if existing:
                logger.debug(f"CashSale already exists for walk-in sale {instance.sale_number}")
                return
            
            # Get or create accounts
            revenue_account, _ = Account.objects.get_or_create(
                account_code='4200',
                defaults={
                    'account_name': 'Pharmacy Sales Revenue',
                    'account_type': 'revenue',
                    'is_active': True,
                }
            )
            
            cash_account, _ = Account.objects.get_or_create(
                account_code='1000',
                defaults={
                    'account_name': 'Cash on Hand',
                    'account_type': 'asset',
                    'is_active': True,
                }
            )
            
            # Create CashSale
            cash_sale = CashSale.objects.create(
                sale_date=instance.sale_date.date() if hasattr(instance.sale_date, 'date') else instance.sale_date,
                customer_name=instance.customer_name,
                description=f"Walk-in Pharmacy Sale: {instance.sale_number}",
                total_amount=instance.total_amount,
                payment_method='cash',  # Default to cash for walk-in sales
                revenue_account=revenue_account,
                cash_account=cash_account,
                created_by=instance.served_by.user if hasattr(instance.served_by, 'user') and instance.served_by.user else None,
            )
            
            logger.info(
                f"✅ Auto-created cash sale {cash_sale.sale_number} "
                f"from prescribe sale {instance.sale_number} - GHS {instance.total_amount}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error creating cash sale for walk-in sale {instance.id}: {e}", exc_info=True)








