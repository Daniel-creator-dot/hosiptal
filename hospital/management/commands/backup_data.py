"""
Management command to backup data to JSON/CSV
"""
import json
import csv
from django.core.management.base import BaseCommand
from django.core import serializers
from django.conf import settings
from io import StringIO
import os
from datetime import datetime
from hospital.models import Patient, Encounter, Invoice, Admission


class Command(BaseCommand):
    help = 'Backs up key hospital data to JSON/CSV files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            default='json',
            choices=['json', 'csv'],
            help='Output format (json or csv)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Output directory for backup files'
        )
        parser.add_argument(
            '--models',
            type=str,
            nargs='+',
            default=['patient', 'encounter', 'invoice'],
            help='Models to backup'
        )

    def handle(self, *args, **options):
        format_type = options['format']
        output_dir = options['output_dir']
        models_to_backup = options['models']
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        model_map = {
            'patient': Patient,
            'encounter': Encounter,
            'invoice': Invoice,
            'admission': Admission,
        }
        
        for model_name in models_to_backup:
            if model_name.lower() not in model_map:
                self.stdout.write(self.style.WARNING(f'Unknown model: {model_name}'))
                continue
            
            model = model_map[model_name.lower()]
            queryset = model.objects.filter(is_deleted=False)
            
            filename = f'{model_name}_{timestamp}.{format_type}'
            filepath = os.path.join(output_dir, filename)
            
            if format_type == 'json':
                data = serializers.serialize('json', queryset)
                with open(filepath, 'w') as f:
                    f.write(data)
            elif format_type == 'csv':
                # Basic CSV export - would need to handle relations properly
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    if queryset.exists():
                        field_names = [f.name for f in model._meta.fields if not f.related_model]
                        writer = csv.DictWriter(f, fieldnames=field_names)
                        writer.writeheader()
                        for obj in queryset:
                            row = {field: str(getattr(obj, field)) for field in field_names}
                            writer.writerow(row)
            
            count = queryset.count()
            self.stdout.write(
                self.style.SUCCESS(f'Backed up {count} {model_name} records to {filepath}')
            )
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Backup completed! Files saved to {output_dir}/'))

