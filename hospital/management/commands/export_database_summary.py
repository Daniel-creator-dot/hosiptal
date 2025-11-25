"""
Export Database Summary
Exports a summary of all database records for comparison with server
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.utils import timezone
import json
import os

class Command(BaseCommand):
    help = 'Export database summary for comparison with server'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='database_summary.json',
            help='Output file path (default: database_summary.json)',
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        self.stdout.write('Generating database summary...')
        
        summary = {
            'timestamp': timezone.now().isoformat(),
            'database_name': connection.settings_dict.get('NAME'),
            'models': {}
        }
        
        # Get all models from hospital app
        hospital_models = []
        for model in apps.get_models():
            if model._meta.app_label == 'hospital':
                hospital_models.append(model)
        
        hospital_models.sort(key=lambda x: x.__name__)
        
        for model in hospital_models:
            try:
                # Check if table exists
                with connection.cursor() as cursor:
                    table_name = model._meta.db_table
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        );
                    """, [table_name])
                    table_exists = cursor.fetchone()[0]
                    
                    if not table_exists:
                        summary['models'][model.__name__] = {
                            'table_exists': False,
                            'count': 0,
                            'error': 'Table missing'
                        }
                        continue
                
                # Check if model has is_deleted field
                has_is_deleted = 'is_deleted' in [f.name for f in model._meta.get_fields()]
                
                # Count records
                qs = model.objects.all()
                if has_is_deleted:
                    qs = qs.filter(is_deleted=False)
                count = qs.count()
                
                # Get sample IDs (first 10)
                sample_ids = list(qs.values_list('id', flat=True)[:10])
                
                # Get latest created date if available
                latest_created = None
                if hasattr(model, 'created'):
                    latest = qs.order_by('-created').first()
                    if latest:
                        latest_created = latest.created.isoformat() if hasattr(latest.created, 'isoformat') else str(latest.created)
                
                summary['models'][model.__name__] = {
                    'table_exists': True,
                    'table_name': table_name,
                    'count': count,
                    'has_is_deleted': has_is_deleted,
                    'sample_ids': sample_ids,
                    'latest_created': latest_created,
                }
                
            except Exception as e:
                summary['models'][model.__name__] = {
                    'table_exists': True,
                    'count': 0,
                    'error': str(e)
                }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        total_records = sum(m.get('count', 0) for m in summary['models'].values())
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Database summary exported to: {output_file}'))
        self.stdout.write(f'  Total models: {len(summary["models"])}')
        self.stdout.write(f'  Total records: {total_records:,}')
        self.stdout.write(f'\nYou can compare this file with the server database summary.')



