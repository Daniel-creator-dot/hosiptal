"""
Management command to create Marketing/Business Development department and role
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from hospital.models import Department
from django.db import transaction


class Command(BaseCommand):
    help = 'Create Marketing/Business Development department and role'

    def handle(self, *args, **options):
        self.stdout.write('Creating Marketing/Business Development department and role...')
        
        with transaction.atomic():
            # Create Department
            dept, created = Department.objects.get_or_create(
                name='Marketing & Business Development',
                defaults={
                    'code': 'MKTG',
                    'description': 'Marketing, Business Development, and Corporate Partnerships Department',
                    'is_active': True,
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created department: {dept.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  Department already exists: {dept.name}'))
            
            # Create or get Marketing/Business Development Group
            marketing_group, created = Group.objects.get_or_create(name='Marketing & Business Development')
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created group: {marketing_group.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  Group already exists: {marketing_group.name}'))
            
            # Add permissions for marketing models
            try:
                from hospital.models_marketing import (
                    MarketingObjective, MarketingTask, MarketingCampaign,
                    MarketingMetric, CorporatePartnership
                )
                
                # Get content types
                from django.contrib.contenttypes.models import ContentType
                
                models_to_permit = [
                    MarketingObjective,
                    MarketingTask,
                    MarketingCampaign,
                    MarketingMetric,
                    CorporatePartnership,
                ]
                
                permissions_added = 0
                for model in models_to_permit:
                    content_type = ContentType.objects.get_for_model(model)
                    permissions = Permission.objects.filter(content_type=content_type)
                    for perm in permissions:
                        marketing_group.permissions.add(perm)
                        permissions_added += 1
                
                self.stdout.write(self.style.SUCCESS(f'✅ Added {permissions_added} permissions to marketing group'))
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Could not add permissions: {e}'))
            
            self.stdout.write(self.style.SUCCESS('\n✅ Marketing/Business Development setup complete!'))
            self.stdout.write(f'   Department: {dept.name} (Code: {dept.code})')
            self.stdout.write(f'   Group: {marketing_group.name}')










