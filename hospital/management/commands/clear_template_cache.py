"""
Management command to clear Django template cache
"""
from django.core.management.base import BaseCommand
from django.template import engines


class Command(BaseCommand):
    help = 'Clear Django template cache'

    def handle(self, *args, **options):
        self.stdout.write('Clearing template cache...')
        
        # Clear cached template loader
        for engine in engines.all():
            if hasattr(engine, 'engine'):
                # Clear the template loader cache
                for loader in engine.engine.template_loaders:
                    if hasattr(loader, 'template_cache'):
                        loader.template_cache.clear()
                        self.stdout.write(self.style.SUCCESS(f'Cleared cache from {loader.__class__.__name__}'))
        
        self.stdout.write(self.style.SUCCESS('Template cache cleared! Restart server to fully clear.'))



