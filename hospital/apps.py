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