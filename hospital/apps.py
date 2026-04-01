"""
Hospital App Configuration
"""

from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate


def enable_sqlite_wal(sender, connection, **kwargs):
    """Enable WAL mode for SQLite databases to improve concurrency"""
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL;")
            # Set busy timeout to 60 seconds
            cursor.execute("PRAGMA busy_timeout=60000;")
            # Set synchronous mode to NORMAL for better performance
            cursor.execute("PRAGMA synchronous=NORMAL;")


class HospitalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hospital'
    
    def ready(self):
        """Import signals when app is ready"""
        # Enable SQLite WAL mode for better concurrency
        connection_created.connect(enable_sqlite_wal)

        def seed_staff_data(sender, **kwargs):
            """Ensure staff fixtures exist after migrations finish."""
            try:
                from hospital.seed_data.staff_seed import ensure_staff_seeded

                ensure_staff_seeded()
            except Exception as exc:  # noqa: BLE001 - log but don't crash startup
                print(f"[INIT] Staff seed skipped: {exc}")

        post_migrate.connect(seed_staff_data, sender=self, dispatch_uid='hospital_seed_staff')
        
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
        
        try:
            import hospital.signals_audit  # noqa: F401
            print("[INIT] Audit logging signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Audit logging signals not loaded: {e}")
        
        try:
            import hospital.signals_patient_deposits  # noqa: F401
            print("[INIT] Patient deposit signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Patient deposit signals not loaded: {e}")
        
        try:
            import hospital.signals_cashbook  # noqa: F401
            print("[INIT] Cashbook auto-recording signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Cashbook signals not loaded: {e}")
        
        try:
            import hospital.signals_cash_sales  # noqa: F401
            print("[INIT] Cash sales auto-recording signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Cash sales signals not loaded: {e}")
        
        try:
            import hospital.signals_performance  # noqa: F401
            print("[INIT] Performance tracking signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Performance tracking signals not loaded: {e}")
        
        try:
            import hospital.signals_visit_payer_sync  # noqa: F401
            print("[INIT] Visit payer sync signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Visit payer sync signals not loaded: {e}")
        
        try:
            import hospital.signals_insurance  # noqa: F401
            print("[INIT] Insurance claim signals loaded [OK]")
        except Exception as e:
            print(f"[INIT] Insurance claim signals not loaded: {e}")
        
        # Fix for Python 3.14 compatibility with Django 4.2.7
        # This patches Django's BaseContext and Context __copy__ methods to work with Python 3.14
        # The issue: Python 3.14 changed how super().__copy__() works, causing AttributeError
        # when Django tries to copy template contexts (especially with crispy_forms)
        import sys
        if sys.version_info >= (3, 14):
            try:
                import copy
                from django.template.context import BaseContext, Context
                
                # Store original methods
                _original_basecontext_copy = BaseContext.__copy__
                
                def _fixed_basecontext_copy(self):
                    """Fixed __copy__ method for Python 3.14 compatibility - avoids super() call"""
                    # Use __new__ to create an uninitialized instance (avoids __init__ requirements)
                    duplicate = self.__class__.__new__(self.__class__)
                    # Copy the instance dictionary
                    duplicate.__dict__.update(copy.copy(self.__dict__))
                    # Manually copy the dicts list if it exists
                    if hasattr(self, 'dicts'):
                        duplicate.dicts = self.dicts[:]
                    return duplicate
                
                # Patch BaseContext
                BaseContext.__copy__ = _fixed_basecontext_copy
                
                # Also patch Context if it has its own __copy__ that uses super()
                if hasattr(Context, '__copy__'):
                    _original_context_copy = Context.__copy__
                    
                    def _fixed_context_copy(self):
                        """Fixed Context.__copy__ method for Python 3.14 compatibility"""
                        # Use __new__ to create an uninitialized instance (avoids __init__ requirements)
                        # This handles RequestContext and other subclasses that require constructor args
                        duplicate = self.__class__.__new__(self.__class__)
                        # Copy the instance dictionary
                        duplicate.__dict__.update(copy.copy(self.__dict__))
                        # Manually copy the dicts list
                        if hasattr(self, 'dicts'):
                            duplicate.dicts = self.dicts[:]
                        # Copy render_context if it exists
                        if hasattr(self, 'render_context'):
                            duplicate.render_context = copy.copy(self.render_context)
                        return duplicate
                    
                    Context.__copy__ = _fixed_context_copy
                
                print("[INIT] Python 3.14 Django Context compatibility patch applied [OK]")
            except (ImportError, AttributeError) as e:
                print(f"[INIT] Python 3.14 compatibility patch failed: {e}")