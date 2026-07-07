"""
Shared backup / import file retention helpers.
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

BACKUP_EXTENSIONS = {'.sql', '.sqlite3', '.zip', '.dump', '.json', '.gz'}
IMPORT_EXTENSIONS = {'.sql', '.zip', '.gz'}


def _file_mtime_utc(path: Path):
    return timezone.datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _should_prune_file(path: Path, allowed_extensions: set[str]) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in allowed_extensions:
        return False
    name = path.name.lower()
    if name.endswith('.meta.json'):
        return True
    if name.startswith('hms_backup_'):
        return True
    if name.startswith('db_backup_') or name.startswith('db_auto_backup_'):
        return True
    if name.startswith('all_backups_'):
        return True
    if name.startswith('pg_backup_'):
        return True
    if path.suffix.lower() in allowed_extensions:
        return True
    return False


def prune_directory(
    directory: Path,
    *,
    keep_days: int,
    allowed_extensions: set[str],
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Remove files in directory older than keep_days.
    Returns (deleted_count, bytes_freed).
    """
    if keep_days <= 0 or not directory.exists():
        return 0, 0

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted = 0
    bytes_freed = 0

    for entry in directory.iterdir():
        if not _should_prune_file(entry, allowed_extensions):
            continue
        try:
            mtime = _file_mtime_utc(entry)
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        size = entry.stat().st_size
        if dry_run:
            logger.info('Would delete: %s (%s bytes)', entry, size)
        else:
            entry.unlink()
            logger.info('Deleted old file: %s (%s bytes)', entry, size)
        deleted += 1
        bytes_freed += size

    return deleted, bytes_freed


def prune_backup_folders(base_dir: Path, *, keep_days: int, dry_run: bool = False) -> tuple[int, int]:
    """Prune dated manual backup folders backup_YYYYMMDD_* older than keep_days."""
    if keep_days <= 0 or not base_dir.exists():
        return 0, 0

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted = 0
    bytes_freed = 0

    for entry in base_dir.iterdir():
        if not entry.is_dir() or not entry.name.startswith('backup_'):
            continue
        try:
            mtime = _file_mtime_utc(entry)
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        size = sum(f.stat().st_size for f in entry.rglob('*') if f.is_file())
        if dry_run:
            logger.info('Would delete folder: %s (%s bytes)', entry, size)
        else:
            shutil.rmtree(entry)
            logger.info('Deleted old backup folder: %s (%s bytes)', entry, size)
        deleted += 1
        bytes_freed += size

    return deleted, bytes_freed


def prune_all_retention_targets(*, keep_days: int, dry_run: bool = False) -> dict:
    """Prune backups/, import/, and related retention targets."""
    root = Path(settings.BASE_DIR)
    targets = [
        (root / 'backups' / 'automated', BACKUP_EXTENSIONS),
        (root / 'backups' / 'database', BACKUP_EXTENSIONS),
        (root / 'backups' / 'archived_databases', BACKUP_EXTENSIONS),
        (root / 'import', IMPORT_EXTENSIONS),
    ]

    summary = {'files_deleted': 0, 'folders_deleted': 0, 'bytes_freed': 0, 'dry_run': dry_run}

    for directory, extensions in targets:
        count, freed = prune_directory(directory, keep_days=keep_days, allowed_extensions=extensions, dry_run=dry_run)
        summary['files_deleted'] += count
        summary['bytes_freed'] += freed

    folder_count, folder_freed = prune_backup_folders(root / 'backups', keep_days=keep_days, dry_run=dry_run)
    summary['folders_deleted'] = folder_count
    summary['bytes_freed'] += folder_freed

    return summary


def get_retention_days(default: int = 14) -> int:
    """Read retention from HospitalSettings; fall back to default."""
    try:
        from hospital.models_settings import HospitalSettings

        days = HospitalSettings.get_solo().backup_retention_days
        if days is None:
            return default
        return int(days)
    except Exception:
        logger.debug('Could not load HospitalSettings.backup_retention_days; using default=%s', default)
        return default
