"""
WSGI config for hms project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import sys

# Fix for Windows colorama OSError: [Errno 22] Invalid argument
if sys.platform == 'win32':
    os.environ.setdefault('COLORAMA_DISABLE_AUTOWRAP', '1')
    os.environ.setdefault('FORCE_COLOR', '0')

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

application = get_wsgi_application()
