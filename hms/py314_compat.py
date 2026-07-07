"""Python 3.14 compatibility shims for third-party libraries."""
import importlib.util
import pkgutil


def apply_pkgutil_find_loader_shim():
    """Restore pkgutil.find_loader removed in Python 3.14 (used by django-filter)."""
    if not hasattr(pkgutil, 'find_loader'):
        pkgutil.find_loader = importlib.util.find_spec  # type: ignore[attr-defined]
