"""
ASGI config for hms project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import sys

# Fix for Windows colorama OSError: [Errno 22] Invalid argument
if sys.platform == 'win32':
    os.environ.setdefault('COLORAMA_DISABLE_AUTOWRAP', '1')
    os.environ.setdefault('FORCE_COLOR', '0')

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

application = get_asgi_application()
