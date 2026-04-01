"""
Management command to seed default contract categories for hospitals.
Adds categories commonly used: Corporate Contract, Insurance, Staff, etc.
"""
from django.core.management.base import BaseCommand
from hospital.models_contracts import ContractCategory


# Default contract categories hospitals commonly use
DEFAULT_CATEGORIES = [
    {
        'name': 'Corporate Contract',
        'category_type': 'corporate',
        'description': 'Corporate agreements, MOU, and business partnerships',
        'color_code': '#0d9488',
    },
    {
        'name': 'Insurance',
        'category_type': 'insurance',
        'description': 'Insurance company agreements, NHIS, and health insurance contracts',
        'color_code': '#2563eb',
    },
    {
        'name': 'Staff / Employment',
        'category_type': 'employment',
        'description': 'Employment contracts, consultancy agreements, and staff agreements',
        'color_code': '#7c3aed',
    },
    {
        'name': 'Medical Equipment Supplier',
        'category_type': 'supplier',
        'description': 'Medical equipment, devices, and diagnostic equipment suppliers',
        'color_code': '#059669',
    },
    {
        'name': 'Pharmaceutical Supplier',
        'category_type': 'supplier',
        'description': 'Drug and pharmaceutical supply agreements',
        'color_code': '#0891b2',
    },
    {
        'name': 'Laboratory Service',
        'category_type': 'service',
        'description': 'Lab services, pathology, and diagnostic testing contracts',
        'color_code': '#dc2626',
    },
    {
        'name': 'Service Provider',
        'category_type': 'service',
        'description': 'General service providers (cleaning, security, catering, etc.)',
        'color_code': '#ea580c',
    },
    {
        'name': 'Lease / Rental',
        'category_type': 'lease',
        'description': 'Property, equipment, or vehicle lease agreements',
        'color_code': '#ca8a04',
    },
    {
        'name': 'Maintenance',
        'category_type': 'maintenance',
        'description': 'Equipment maintenance, HVAC, and facility maintenance agreements',
        'color_code': '#4f46e5',
    },
    {
        'name': 'Partnership',
        'category_type': 'partnership',
        'description': 'Clinical partnerships, referral agreements, and collaborations',
        'color_code': '#be185d',
    },
    {
        'name': 'Other',
        'category_type': 'other',
        'description': 'Other contracts not fitting the above categories',
        'color_code': '#6b7280',
    },
]


class Command(BaseCommand):
    help = 'Seed default contract categories for hospitals (Corporate, Insurance, Staff, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-create categories even if they exist (updates description/color)',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        created_count = 0
        updated_count = 0

        for cat_data in DEFAULT_CATEGORIES:
            obj, created = ContractCategory.objects.update_or_create(
                name=cat_data['name'],
                defaults={
                    'category_type': cat_data['category_type'],
                    'description': cat_data['description'],
                    'color_code': cat_data['color_code'],
                    'is_active': True,
                    'is_deleted': False,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  + Created: {obj.name}'))
            elif force:
                updated_count += 1
                self.stdout.write(f'  ~ Updated: {obj.name}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. Created {created_count}, updated {updated_count} contract categories.'
        ))
