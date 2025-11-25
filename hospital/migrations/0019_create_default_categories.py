"""
Data migration to create default inventory categories
"""
from django.db import migrations


def create_default_categories(apps, schema_editor):
    """Create default inventory categories"""
    InventoryCategory = apps.get_model('hospital', 'InventoryCategory')
    
    categories = [
        {
            'name': 'Pharmacy / Pharmaceuticals',
            'code': 'PHARM',
            'is_for_pharmacy': True,
            'display_order': 1,
            'description': 'Pharmaceuticals, drugs, and medications',
            'is_active': True
        },
        {
            'name': 'Medical Equipment',
            'code': 'EQUIP',
            'is_for_pharmacy': False,
            'display_order': 2,
            'description': 'Medical equipment and devices',
            'is_active': True
        },
        {
            'name': 'Medical Supplies',
            'code': 'SUPPLY',
            'is_for_pharmacy': False,
            'display_order': 3,
            'description': 'Medical supplies and consumables (non-drug)',
            'is_active': True
        },
        {
            'name': 'Laboratory Supplies',
            'code': 'LAB',
            'is_for_pharmacy': False,
            'display_order': 4,
            'description': 'Laboratory supplies and reagents',
            'is_active': True
        },
        {
            'name': 'Furniture & Fixtures',
            'code': 'FURN',
            'is_for_pharmacy': False,
            'display_order': 5,
            'description': 'Furniture, chairs, desks, fixtures',
            'is_active': True
        },
        {
            'name': 'IT Equipment',
            'code': 'IT',
            'is_for_pharmacy': False,
            'display_order': 6,
            'description': 'Computers, printers, IT equipment',
            'is_active': True
        },
        {
            'name': 'General Supplies',
            'code': 'GEN',
            'is_for_pharmacy': False,
            'display_order': 7,
            'description': 'General office and facility supplies',
            'is_active': True
        },
    ]
    
    for cat_data in categories:
        InventoryCategory.objects.get_or_create(
            code=cat_data['code'],
            defaults=cat_data
        )


def reverse_create_categories(apps, schema_editor):
    """Remove default categories"""
    InventoryCategory = apps.get_model('hospital', 'InventoryCategory')
    InventoryCategory.objects.filter(
        code__in=['PHARM', 'EQUIP', 'SUPPLY', 'LAB', 'FURN', 'IT', 'GEN']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('hospital', '0018_add_inventory_category'),
    ]

    operations = [
        migrations.RunPython(create_default_categories, reverse_create_categories),
    ]





































