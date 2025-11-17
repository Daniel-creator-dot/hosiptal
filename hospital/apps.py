"""
Hospital App Configuration
"""

from django.apps import AppConfig


class HospitalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hospital'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import hospital.signals  # noqa: F401
            print("[INIT] Core hospital signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Core hospital signals not loaded: {e}")
        
        try:
            import hospital.signals_accounting
            print("[INIT] Accounting auto-sync signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Accounting signals not loaded: {e}")
        
        try:
            import hospital.signals_auto_attendance
            print("[INIT] Auto-attendance signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Auto-attendance signals not loaded: {e}")
        
        try:
            import hospital.signals_revenue
            print("[INIT] Revenue tracking signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Revenue tracking signals not loaded: {e}")

        try:
            import hospital.signals_auto_billing
            print("[INIT] Auto-billing signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Auto-billing signals not loaded: {e}")

        try:
            import hospital.signals_payment_clearance
            print("[INIT] Payment clearance signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Payment clearance signals not loaded: {e}")

        try:
            import hospital.models_pharmacy_walkin  # noqa: F401
            print("[INIT] Walk-in pharmacy models loaded [OK]")
        except Exception as e:
            print(f"[INIT] Walk-in pharmacy models not loaded: {e}")

        try:
            import hospital.signals_login_tracking  # noqa: F401
            print("[INIT] Login tracking signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Login tracking signals not loaded: {e}")

        try:
            import hospital.auth_session_utils  # noqa: F401
            print("[INIT] User session tracking loaded [OK]")
        except Exception as e:
            print(f"[INIT] User session tracking not loaded: {e}")