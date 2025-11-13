"""
Management command to set up Role-Based Access Control (RBAC)
Creates groups and assigns permissions for different hospital roles
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps


class Command(BaseCommand):
    help = 'Set up RBAC groups and permissions for HMS'

    def handle(self, *args, **options):
        # Define role permissions
        roles = {
            'Front Desk': {
                'can_view': ['patient', 'appointment', 'queue'],
                'can_add': ['patient', 'appointment'],
                'can_change': ['patient', 'appointment'],
                'can_delete': [],
            },
            'Nurse': {
                'can_view': ['patient', 'encounter', 'vitalsign', 'prescription', 'mar', 'handoversheet', 'fallriskassessment', 'pressureulcerriskassessment'],
                'can_add': ['vitalsign', 'mar', 'handoversheet', 'fallriskassessment', 'pressureulcerriskassessment'],
                'can_change': ['vitalsign', 'mar', 'handoversheet'],
                'can_delete': [],
            },
            'Doctor': {
                'can_view': ['patient', 'encounter', 'clinicalnote', 'careplan', 'problemlist', 'order', 'prescription', 'labresult', 'imagingsudy'],
                'can_add': ['encounter', 'clinicalnote', 'careplan', 'problemlist', 'order', 'prescription'],
                'can_change': ['encounter', 'clinicalnote', 'careplan', 'problemlist', 'order', 'prescription'],
                'can_delete': [],
            },
            'Pharmacist': {
                'can_view': ['prescription', 'pharmacystock', 'drug', 'mar'],
                'can_add': ['prescription'],
                'can_change': ['pharmacystock', 'prescription'],
                'can_delete': [],
            },
            'Lab Scientist': {
                'can_view': ['order', 'labtest', 'labresult', 'samplecollection'],
                'can_add': ['labresult', 'samplecollection'],
                'can_change': ['labresult', 'samplecollection'],
                'can_delete': [],
            },
            'Radiologist': {
                'can_view': ['imagingsudy', 'order'],
                'can_add': ['imagingsudy'],
                'can_change': ['imagingsudy'],
                'can_delete': [],
            },
            'Cashier': {
                'can_view': ['invoice', 'invoiceline', 'payer', 'servicecode'],
                'can_add': ['invoice', 'invoiceline'],
                'can_change': ['invoice', 'invoiceline'],
                'can_delete': [],
            },
            'Admin': {
                'can_view': ['__all__'],
                'can_add': ['__all__'],
                'can_change': ['__all__'],
                'can_delete': ['__all__'],
            }
        }
        
        # Create groups and assign permissions
        for role_name, permissions in roles.items():
            group, created = Group.objects.get_or_create(name=role_name)
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {role_name}'))
            else:
                self.stdout.write(f'Group {role_name} already exists')
            
            # Clear existing permissions
            group.permissions.clear()
            
            # Get all content types
            all_content_types = ContentType.objects.all()
            
            # Assign permissions
            assigned_count = 0
            for perm_type, models in permissions.items():
                if '__all__' in models:
                    # Assign all permissions
                    perms = Permission.objects.all()
                    group.permissions.add(*perms)
                    assigned_count = perms.count()
                else:
                    for model_name in models:
                        # Find content type for model
                        for ct in all_content_types:
                            if ct.model == model_name.lower().replace(' ', ''):
                                # Get permissions for this model
                                codename_prefix = perm_type.split('_')[1] if '_' in perm_type else perm_type
                                perms = Permission.objects.filter(
                                    content_type=ct,
                                    codename__startswith=codename_prefix
                                )
                                group.permissions.add(*perms)
                                assigned_count += perms.count()
                                break
            
            self.stdout.write(self.style.SUCCESS(f'  Assigned {assigned_count} permissions to {role_name}'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ RBAC setup completed!'))
        self.stdout.write('\nAvailable roles:')
        for role_name in roles.keys():
            self.stdout.write(f'  - {role_name}')

