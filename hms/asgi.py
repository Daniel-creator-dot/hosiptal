"""
ASGI config for hms project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import sys
from pathlib import Path

# Add project directory to Python path (for server deployment)
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Fix for Windows colorama OSError: [Errno 22] Invalid argument
if sys.platform == 'win32':
    os.environ.setdefault('COLORAMA_DISABLE_AUTOWRAP', '1')
    os.environ.setdefault('FORCE_COLOR', '0')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

from django.core.asgi import get_asgi_application

# Fix for Python 3.14 compatibility with Django 4.2.7
# This patches Django's BaseContext.__copy__ method to work with Python 3.14
# Must be applied after Django is imported but before application is created
if sys.version_info >= (3, 14):
    try:
        import copy
        from django.template.context import BaseContext
        
        def _fixed_basecontext_copy(self):
            """Fixed __copy__ method for Python 3.14 compatibility"""
            # Create a new instance of the same class
            duplicate = self.__class__()
            # Copy the instance dictionary
            duplicate.__dict__.update(copy.copy(self.__dict__))
            # Manually copy the dicts list if it exists
            if hasattr(self, 'dicts'):
                duplicate.dicts = self.dicts[:]
            return duplicate
        
        # Apply the monkey patch
        BaseContext.__copy__ = _fixed_basecontext_copy
    except (ImportError, AttributeError):
        # If Django isn't loaded yet or the class doesn't exist, ignore
        pass

# Ensure required directories exist (for server deployment)
try:
    from django.conf import settings
    # Create directories if they don't exist
    for directory in [settings.STATIC_ROOT, settings.MEDIA_ROOT]:
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)
except Exception:
    # If settings can't be loaded, continue anyway
    pass

application = get_asgi_application()
