"""
Automated local -> live database sync for HMS.

Runs the existing staged sync scripts in order:
  1. Foundation (users, staff, patients, payers)
  2. Clinical (encounters, labs, prescriptions, imaging, ...)
  3. Financial (optional: export SQL from local, import to live)

Configure credentials in .env.sync (see env.sync.example).

Usage:
  python auto_sync_local_to_live.py --once
  python auto_sync_local_to_live.py --watch --interval 900
  python auto_sync_local_to_live.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOCK_FILE = ROOT / "tmp_local_to_live_sync.lock"
ENV_SYNC = ROOT / ".env.sync"

DEFAULT_LOCAL = "postgresql://hms_user:hms_password@localhost:5432/hms_db"


def load_env_sync() -> None:
    """Load .env.sync into os.environ (does not override existing vars)."""
    if not ENV_SYNC.exists():
        return
    for raw in ENV_SYNC.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / "local_to_live_sync.log"
    logger = logging.getLogger("local_to_live_sync")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def acquire_lock(logger: logging.Logger) -> bool:
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            pid_text = LOCK_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            age = 0
            pid_text = "?"
        if age < 7200:
            logger.warning(
                "Sync already running or stale lock (%s, pid=%s, age=%.0fs). Skipping.",
                LOCK_FILE,
                pid_text,
                age,
            )
            return False
        logger.warning("Removing stale lock file (age=%.0fs).", age)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def test_connection(label: str, url: str, ssl_mode: str) -> None:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for connection checks")
    connect_url = url
    if "sslmode=" not in connect_url:
        sep = "&" if "?" in connect_url else "?"
        connect_url = f"{connect_url}{sep}sslmode={ssl_mode}"
    conn = psycopg2.connect(connect_url, connect_timeout=15)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), inet_server_addr()::text")
            db_name, host = cur.fetchone()
        print(f"  {label}: OK ({db_name} @ {host or 'local'})")
    finally:
        conn.close()


def run_step(logger: logging.Logger, name: str, script: str, *args: str) -> None:
    cmd = [sys.executable, str(ROOT / script), *args]
    logger.info("--- Phase: %s (%s) ---", name, " ".join(cmd))
    t0 = time.time()
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        for line in result.stdout.splitlines():
            logger.info("[%s] %s", name, line)
    if result.stderr:
        for line in result.stderr.splitlines():
            logger.warning("[%s] %s", name, line)
    elapsed = time.time() - t0
    if result.returncode != 0:
        raise RuntimeError(f"Phase {name} failed (exit {result.returncode}) after {elapsed:.1f}s")
    logger.info("Phase %s completed in %.1fs", name, elapsed)


def run_sync(logger: logging.Logger, include_financial: bool) -> None:
    local_url = os.environ.get("LOCAL_DATABASE_URL", DEFAULT_LOCAL)
    live_url = os.environ.get("LIVE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not live_url:
        raise RuntimeError(
            "Set LIVE_DATABASE_URL in .env.sync (copy env.sync.example -> .env.sync)."
        )
    os.environ.setdefault("LOCAL_DATABASE_URL", local_url)
    os.environ["LIVE_DATABASE_URL"] = live_url

    logger.info("Pre-flight connection checks...")
    test_connection("LOCAL", local_url, "disable")
    test_connection("LIVE", live_url, "require")

    run_step(logger, "foundation", "sync_local_to_live.py", "all")
    run_step(logger, "clinical", "sync_clinical_to_live.py", "all")

    if include_financial:
        run_step(logger, "financial_export", "export_financial_sql.py")
        run_step(logger, "financial_import", "load_financial_sql_to_live.py")

    logger.info("Sync run finished successfully.")


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def main() -> int:
    load_env_sync()
    logger = setup_logging()

    parser = argparse.ArgumentParser(description="Automated local -> live HMS database sync")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one sync and exit (default)")
    mode.add_argument("--watch", action="store_true", help="Run sync repeatedly")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("SYNC_INTERVAL_SECONDS", "900")),
        help="Seconds between syncs in --watch mode (default: 900 = 15 min)",
    )
    parser.add_argument(
        "--skip-financial",
        action="store_true",
        help="Skip billing/financial tables",
    )
    parser.add_argument(
        "--include-financial",
        action="store_true",
        help="Include billing/financial tables",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test DB connections only; do not sync",
    )
    args = parser.parse_args()

    include_financial = args.include_financial or (
        not args.skip_financial and env_flag("SYNC_INCLUDE_FINANCIAL", default=True)
    )

    if args.dry_run:
        local_url = os.environ.get("LOCAL_DATABASE_URL", DEFAULT_LOCAL)
        live_url = os.environ.get("LIVE_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not live_url:
            print("ERROR: LIVE_DATABASE_URL not set. Copy env.sync.example to .env.sync")
            return 1
        print("Dry run — testing connections only:")
        test_connection("LOCAL", local_url, "disable")
        test_connection("LIVE", live_url, "require")
        print("Connections OK. Ready to sync.")
        return 0

    if not acquire_lock(logger):
        return 0

    try:
        if args.watch:
            logger.info(
                "Watch mode started (interval=%ss, financial=%s)",
                args.interval,
                include_financial,
            )
            while True:
                started = datetime.now(timezone.utc).isoformat()
                logger.info("=== Sync cycle start %s ===", started)
                try:
                    run_sync(logger, include_financial=include_financial)
                except Exception as exc:
                    logger.exception("Sync cycle failed: %s", exc)
                logger.info("Sleeping %ss until next cycle...", args.interval)
                time.sleep(args.interval)
        else:
            logger.info("Single sync started (financial=%s)", include_financial)
            run_sync(logger, include_financial=include_financial)
    except Exception as exc:
        logger.exception("Sync failed: %s", exc)
        return 1
    finally:
        release_lock()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
