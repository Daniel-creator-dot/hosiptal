"""
Compare Local and Server Databases
Compares two database summary JSON files to identify differences
"""
from django.core.management.base import BaseCommand
import json
import os

class Command(BaseCommand):
    help = 'Compare local and server database summaries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--local',
            type=str,
            default='database_summary_local.json',
            help='Local database summary file',
        )
        parser.add_argument(
            '--server',
            type=str,
            required=True,
            help='Server database summary file',
        )

    def handle(self, *args, **options):
        local_file = options['local']
        server_file = options['server']
        
        if not os.path.exists(local_file):
            self.stdout.write(self.style.ERROR(f'Local file not found: {local_file}'))
            return
        
        if not os.path.exists(server_file):
            self.stdout.write(self.style.ERROR(f'Server file not found: {server_file}'))
            return
        
        # Load summaries
        with open(local_file, 'r') as f:
            local_data = json.load(f)
        
        with open(server_file, 'r') as f:
            server_data = json.load(f)
        
        local_models = local_data.get('models', {})
        server_models = server_data.get('models', {})
        
        self.stdout.write(self.style.SUCCESS('\n=== Database Comparison Report ===\n'))
        
        # Key models to check (especially client/patient related)
        key_models = [
            'Patient',
            'Encounter',
            'Invoice',
            'PaymentReceipt',
            'Appointment',
            'LabTest',
            'LabResult',
            'Prescription',
            'PharmacyStock',
            'Staff',
            'Department',
            'Queue',
            'QueueEntry',
        ]
        
        differences = []
        missing_on_server = []
        missing_on_local = []
        count_differences = []
        
        all_models = set(local_models.keys()) | set(server_models.keys())
        
        for model_name in sorted(all_models):
            local_model = local_models.get(model_name, {})
            server_model = server_models.get(model_name, {})
            
            local_count = local_model.get('count', 0)
            server_count = server_model.get('count', 0)
            
            if model_name not in local_models:
                missing_on_local.append((model_name, server_count))
            elif model_name not in server_models:
                missing_on_server.append((model_name, local_count))
            elif local_count != server_count:
                count_differences.append((model_name, local_count, server_count))
                if model_name in key_models:
                    differences.append((model_name, local_count, server_count))
        
        # Report
        if missing_on_server:
            self.stdout.write(self.style.WARNING('\n⚠ Models missing on SERVER:'))
            for model_name, count in missing_on_server:
                self.stdout.write(f'  • {model_name}: {count} records (local)')
        
        if missing_on_local:
            self.stdout.write(self.style.WARNING('\n⚠ Models missing on LOCAL:'))
            for model_name, count in missing_on_local:
                self.stdout.write(f'  • {model_name}: {count} records (server)')
        
        if differences:
            self.stdout.write(self.style.ERROR('\n⚠ KEY MODELS WITH COUNT DIFFERENCES:'))
            self.stdout.write(f"{'Model':<30} {'Local':<15} {'Server':<15} {'Difference':<15}")
            self.stdout.write("-" * 75)
            for model_name, local_count, server_count in differences:
                diff = local_count - server_count
                status = self.style.ERROR if diff > 0 else self.style.WARNING
                self.stdout.write(
                    status(f"{model_name:<30} {local_count:<15} {server_count:<15} {diff:+d}")
                )
        
        if count_differences and len(count_differences) > len(differences):
            self.stdout.write(self.style.WARNING(f'\n⚠ Other models with count differences: {len(count_differences) - len(differences)}'))
            for model_name, local_count, server_count in count_differences:
                if model_name not in key_models:
                    diff = local_count - server_count
                    self.stdout.write(f'  • {model_name}: Local={local_count}, Server={server_count}, Diff={diff:+d}')
        
        # Summary
        if not differences and not missing_on_server and not missing_on_local:
            self.stdout.write(self.style.SUCCESS('\n✓ Databases are in sync!'))
        else:
            self.stdout.write(self.style.WARNING('\n⚠ Action Required:'))
            if missing_on_server or any(d[1] > d[2] for d in differences):
                self.stdout.write('  • Some data exists locally but not on server')
                self.stdout.write('  • Consider exporting and importing data to server')
            if missing_on_local or any(d[1] < d[2] for d in differences):
                self.stdout.write('  • Some data exists on server but not locally')
                self.stdout.write('  • Consider syncing from server to local')
        
        self.stdout.write('\n')



