"""
Management command to set up login tracking tables
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Set up login location tracking tables'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Login Location Tracking System...')
        
        with connection.cursor() as cursor:
            # Create LoginHistory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_loginhistory (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    staff_id TEXT,
                    login_time DATETIME NOT NULL,
                    logout_time DATETIME,
                    session_key TEXT,
                    ip_address TEXT NOT NULL,
                    country TEXT,
                    country_code TEXT,
                    region TEXT,
                    city TEXT,
                    latitude DECIMAL(10,7),
                    longitude DECIMAL(10,7),
                    timezone_name TEXT,
                    isp TEXT,
                    organization TEXT,
                    user_agent TEXT,
                    browser TEXT,
                    browser_version TEXT,
                    os TEXT,
                    os_version TEXT,
                    device_type TEXT DEFAULT 'unknown',
                    device_name TEXT,
                    status TEXT DEFAULT 'success',
                    is_suspicious BOOLEAN NOT NULL DEFAULT 0,
                    is_new_location BOOLEAN NOT NULL DEFAULT 0,
                    is_new_device BOOLEAN NOT NULL DEFAULT 0,
                    failure_reason TEXT,
                    notes TEXT,
                    geo_api_response TEXT,
                    FOREIGN KEY (user_id) REFERENCES auth_user(id),
                    FOREIGN KEY (staff_id) REFERENCES hospital_staff(id)
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_loginhistory_user_time 
                ON hospital_loginhistory(user_id, login_time DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_loginhistory_ip 
                ON hospital_loginhistory(ip_address)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_loginhistory_suspicious 
                ON hospital_loginhistory(is_suspicious)
            """)
            
            # Create SecurityAlert table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_securityalert (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    login_history_id TEXT,
                    alert_time DATETIME NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    description TEXT NOT NULL,
                    ip_address TEXT,
                    location TEXT,
                    is_resolved BOOLEAN NOT NULL DEFAULT 0,
                    resolved_by_id INTEGER,
                    resolved_at DATETIME,
                    resolution_notes TEXT,
                    notification_sent BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES auth_user(id),
                    FOREIGN KEY (login_history_id) REFERENCES hospital_loginhistory(id),
                    FOREIGN KEY (resolved_by_id) REFERENCES auth_user(id)
                )
            """)
            
            # Create TrustedLocation table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_trustedlocation (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    location_name TEXT NOT NULL,
                    city TEXT,
                    country TEXT,
                    ip_address TEXT,
                    ip_range_start TEXT,
                    ip_range_end TEXT,
                    latitude DECIMAL(10,7),
                    longitude DECIMAL(10,7),
                    radius_km DECIMAL(6,2) DEFAULT 10.0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    last_used DATETIME,
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                )
            """)
            
            # Create TrustedDevice table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_trusteddevice (
                    id TEXT PRIMARY KEY,
                    created DATETIME NOT NULL,
                    modified DATETIME NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    device_name TEXT NOT NULL,
                    device_fingerprint TEXT UNIQUE NOT NULL,
                    os TEXT,
                    browser TEXT,
                    device_type TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    first_seen DATETIME NOT NULL,
                    last_seen DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                )
            """)
            
            self.stdout.write(self.style.SUCCESS('[OK] Login tracking tables created successfully!'))
            self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Login Location Tracking System is ready!'))
            self.stdout.write(self.style.SUCCESS('Access it at: http://127.0.0.1:8000/hms/my-login-history/'))





















