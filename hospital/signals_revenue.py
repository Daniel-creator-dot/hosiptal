"""
Revenue Tracking Signals
Automatically create Revenue records when services are provided
REAL-TIME REVENUE TRACKING
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal


# Register ambulance billing signal
try:
    from .models_ambulance import AmbulanceBilling
    
    @receiver(post_save, sender=AmbulanceBilling)
    def sync_ambulance_revenue(sender, instance, **kwargs):
        """Ensure ambulance billing creates/updates revenue"""
        try:
            instance.create_revenue_record()
        except Exception as e:
            print(f"⚠️  Error syncing ambulance revenue: {e}")
        
except ImportError:
    pass


print("[INIT] Revenue tracking signals loaded [OK]")

