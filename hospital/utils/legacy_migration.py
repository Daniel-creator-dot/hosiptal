"""
Legacy System Migration Utilities
Helper functions for data migration from old system to new Django HMS
"""
import MySQLdb
import logging
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from hospital.models_legacy_mapping import LegacyIDMapping, MigrationLog

logger = logging.getLogger(__name__)


class LegacyDatabase:
    """
    Connection manager for legacy MySQL database
    """
    
    def __init__(self, host, user, password, database, port=3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.connection = None
    
    def connect(self):
        """Establish connection to legacy database"""
        try:
            self.connection = MySQLdb.connect(
                host=self.host,
                user=self.user,
                passwd=self.password,
                db=self.database,
                port=self.port,
                charset='utf8mb4'
            )
            logger.info(f"✅ Connected to legacy database: {self.database}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to legacy database: {str(e)}")
            return False
    
    def execute_query(self, query, params=None):
        """Execute SELECT query and return results as list of dicts"""
        try:
            cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            logger.error(f"Query error: {str(e)}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Legacy database connection closed")


class MigrationHelper:
    """
    Helper class for data migration operations
    """
    
    @staticmethod
    def create_id_mapping(legacy_table, legacy_id, new_model, new_id, batch_id='', notes=''):
        """Create ID mapping between legacy and new system"""
        try:
            mapping, created = LegacyIDMapping.objects.get_or_create(
                legacy_table=legacy_table,
                legacy_id=str(legacy_id),
                defaults={
                    'new_model': new_model,
                    'new_id': new_id,
                    'migration_batch': batch_id,
                    'notes': notes
                }
            )
            return mapping
        except Exception as e:
            logger.error(f"Error creating ID mapping: {str(e)}")
            return None
    
    @staticmethod
    def get_new_id(legacy_table, legacy_id):
        """Get new system ID for a legacy ID"""
        try:
            mapping = LegacyIDMapping.objects.get(
                legacy_table=legacy_table,
                legacy_id=str(legacy_id)
            )
            return mapping.new_id
        except LegacyIDMapping.DoesNotExist:
            return None
    
    @staticmethod
    def create_migration_log(migration_type, batch_id, user=None):
        """Create migration log entry"""
        return MigrationLog.objects.create(
            batch_id=batch_id,
            migration_type=migration_type,
            status='pending',
            initiated_by=user
        )
    
    @staticmethod
    def update_migration_log(log, status, total=None, successful=None, failed=None, 
                            skipped=None, error_log='', success_log=''):
        """Update migration log with progress"""
        log.status = status
        if total is not None:
            log.total_records = total
        if successful is not None:
            log.successful_records = successful
        if failed is not None:
            log.failed_records = failed
        if skipped is not None:
            log.skipped_records = skipped
        if error_log:
            log.error_log += f"\n{error_log}"
        if success_log:
            log.success_log += f"\n{success_log}"
        
        if status == 'in_progress' and not log.started_at:
            log.started_at = timezone.now()
        elif status in ['completed', 'failed']:
            log.completed_at = timezone.now()
        
        log.save()
        return log
    
    @staticmethod
    def clean_phone_number(phone):
        """Clean and format phone number"""
        if not phone:
            return ''
        # Remove non-numeric characters
        phone = ''.join(c for c in str(phone) if c.isdigit())
        # Add +233 prefix for Ghana if 10 digits starting with 0
        if len(phone) == 10 and phone.startswith('0'):
            phone = '+233' + phone[1:]
        return phone
    
    @staticmethod
    def parse_date(date_str):
        """Parse date string to date object"""
        if not date_str:
            return None
        try:
            if isinstance(date_str, datetime):
                return date_str.date()
            return datetime.strptime(str(date_str), '%Y-%m-%d').date()
        except:
            return None
    
    @staticmethod
    def generate_mrn():
        """Generate new Medical Record Number"""
        from hospital.models import Patient
        prefix = "MRN"
        year = datetime.now().strftime('%Y')
        
        # Get last MRN for this year
        last_patient = Patient.objects.filter(
            mrn__startswith=f"{prefix}{year}"
        ).order_by('-mrn').first()
        
        if last_patient:
            try:
                last_seq = int(last_patient.mrn[-5:])
                new_seq = last_seq + 1
            except:
                new_seq = 1
        else:
            new_seq = 1
        
        return f"{prefix}{year}{new_seq:05d}"
    
    @staticmethod
    def validate_patient_data(data):
        """Validate patient data before import"""
        errors = []
        warnings = []
        
        # Required fields
        if not data.get('fname'):
            errors.append("First name is required")
        if not data.get('lname'):
            errors.append("Last name is required")
        if not data.get('DOB'):
            errors.append("Date of birth is required")
        if not data.get('sex'):
            errors.append("Gender is required")
        
        # Warnings for missing optional but important fields
        if not data.get('phone_home') and not data.get('phone_cell'):
            warnings.append("No phone number provided")
        if not data.get('email'):
            warnings.append("No email provided")
        if not data.get('street') or not data.get('city'):
            warnings.append("Incomplete address")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @staticmethod
    def map_gender(legacy_gender):
        """Map legacy gender values to new system"""
        gender_map = {
            'Male': 'M',
            'male': 'M',
            'M': 'M',
            'Female': 'F',
            'female': 'F',
            'F': 'F',
            'Other': 'O',
            'other': 'O',
        }
        return gender_map.get(legacy_gender, 'M')  # Default to Male if unknown
    
    @staticmethod
    def batch_iterator(items, batch_size=100):
        """Yield items in batches"""
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]
























