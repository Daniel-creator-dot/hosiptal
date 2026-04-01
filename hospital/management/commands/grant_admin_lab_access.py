"""
Grant Admin group (and Administrator) full lab access.
Adds LabResult, LabTest, Order and related lab permissions to Admin/Administrator groups
so admins can use the Laboratory dashboard and Django admin for lab data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


# Lab-related models in hospital app (for Django permissions)
LAB_MODELS = [
    'labresult',
    'labtest',
    'order',  # lab orders
]


class Command(BaseCommand):
    help = 'Grant Admin and Administrator groups full lab access (Laboratory dashboard and Django admin)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group-only',
            action='store_true',
            help='Only add permissions to Admin/Administrator groups (default: also ensure groups exist)',
        )

    def handle(self, *args, **options):
        # Ensure Admin and Administrator groups exist and have lab permissions
        group_names = ['Admin', 'Administrator']
        perms_added = 0
        lab_permissions = []

        for model_name in LAB_MODELS:
            try:
                content_type = ContentType.objects.get(
                    app_label='hospital',
                    model=model_name
                )
                for perm in Permission.objects.filter(content_type=content_type):
                    lab_permissions.append(perm)
            except ContentType.DoesNotExist:
                continue

        if not lab_permissions:
            self.stdout.write(
                self.style.WARNING('No lab permissions found for hospital app (models: %s)' % ', '.join(LAB_MODELS))
            )
            return

        for name in group_names:
            group, created = Group.objects.get_or_create(name=name)
            for perm in lab_permissions:
                group.permissions.add(perm)
            group.save()
            perms_added += len(lab_permissions)
            self.stdout.write(
                self.style.SUCCESS(
                    'Group "%s": %s (lab permissions assigned)' % (name, 'created' if created else 'updated')
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                'Admin lab access applied. Users in Admin or Administrator group now have full lab access.'
            )
        )
