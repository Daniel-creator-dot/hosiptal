from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Initialize the HMS system with default data'

    def handle(self, *args, **options):
        self.stdout.write('Initializing HMS system...')
        
        # Create superuser if it doesn't exist
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@hms.local',
                password='admin123'
            )
            self.stdout.write(
                self.style.SUCCESS('Superuser "admin" created successfully')
            )
        else:
            self.stdout.write('Superuser "admin" already exists')
        
        # Update site domain
        site = Site.objects.get_current()
        site.domain = 'localhost:8000'
        site.name = 'Hospital Management System'
        site.save()
        
        self.stdout.write(
            self.style.SUCCESS('HMS system initialized successfully!')
        )
