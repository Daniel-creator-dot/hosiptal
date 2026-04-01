#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Compatibility shim for libraries still using pkgutil.find_loader (removed in Python 3.14)
try:
    import pkgutil
    import importlib.util
    if not hasattr(pkgutil, "find_loader"):
        pkgutil.find_loader = importlib.util.find_spec  # type: ignore[attr-defined]
except Exception:
    # Do not block startup if shim fails
    pass

# Fix for Windows colorama OSError: [Errno 22] Invalid argument
if sys.platform == 'win32':
    os.environ.setdefault('COLORAMA_DISABLE_AUTOWRAP', '1')
    os.environ.setdefault('FORCE_COLOR', '0')


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
    try:
        from django.core.management import execute_from_command_line
        
        # Fix for Python 3.14 compatibility with Django 4.2.7
        # This patches Django's BaseContext.__copy__ method to work with Python 3.14
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
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
