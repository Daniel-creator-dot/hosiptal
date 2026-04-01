# HMS Performance Guide

Tips for keeping the app fast when many users are active.

## Already in place

- **Redis cache** for sessions and general cache (reduces DB load).
- **Staff activities** context processor cached per user (5 min) so every page load doesn’t hit the DB.
- **Session writes throttled** to at most once every 2 minutes per user (fewer Redis writes under load).
- **Gunicorn**: 6 workers × 6 threads = 36 concurrent requests (tune via `GUNICORN_WORKERS` / `GUNICORN_THREADS` if you use a custom command).
- **PostgreSQL**: `CONN_MAX_AGE=600`, `work_mem=16MB`, `statement_timeout=30s`.
- **Cached template loader** when `DEBUG=False`.
- **Dashboard counters** (pending appointments, lab, queue, low stock) cached 5–10 minutes.

## Recommended for production

1. **Run with `DEBUG=False`**  
   Enables template caching and avoids heavy debug middleware.

2. **Ensure Redis is up**  
   Session backend and cache use Redis; if it’s down, the app falls back to DB sessions and local memory cache.

3. **Scale Gunicorn if needed**  
   In `docker-compose.yml`, `web` uses `--workers 6 --threads 6`. For more concurrency, increase workers (and ensure DB `max_connections` and memory can handle it).

4. **Heavy cashier views**  
   Patient bills and centralized cashier dashboards use DB-level date filtering when “Today’s Pending” or a date is selected, so they only load that day’s data.

5. **Database indexes**  
   Migrations add indexes for common filters (e.g. pharmacy stock, encounters, patient lookups). Keep migrations applied.

   **After deploy or on first setup**, run so indexes and stats are in place:
   - `python manage.py optimize_for_300_users` (creates performance indexes; idempotent).
   - Optionally: `python manage.py optimize_database_performance --analyze-only` to inspect, then `--create-indexes` or `--all` (e.g. nightly; `--all` includes VACUUM and can be heavy).

6. **Optional: PgBouncer**  
   For many workers, add PgBouncer in front of PostgreSQL to pool connections and stay under `max_connections`.

7. **Celery result backend**  
   When Redis is available, Celery uses Redis for task results (DB `/3`) so the database is not used for result storage. If Redis is down, the app falls back to `django-db` for results.

8. **Cache warmup**  
   At startup, the web container runs `python manage.py warmup_cache` (after migrations). This warms dashboard stats, demographics, encounter stats, and catalog caches so the first user after deploy does not pay the full query cost. For even steadier performance, run warmup on a schedule (e.g. cron or Celery Beat every 5–10 min):  
   `python manage.py warmup_cache`

## Tuning via environment

- `DATABASE_CONN_MAX_AGE` (default 600) – seconds to keep DB connections (higher = fewer new connections).
- `REDIS_MAX_CONNECTIONS` (default 200) – Redis connection pool size.
- `GUNICORN_WORKERS` / `GUNICORN_THREADS` – if you switch to an env-driven Gunicorn command.

## Verification (enterprise SLAs and regression detection)

Use the verification command to establish baselines and catch regressions after deploys or schema changes.

**Command:** `python manage.py verify_performance [--cold] [--target-queries=N] [--target-ms=N] [--quiet]`

| Option | Meaning |
|--------|--------|
| `--cold` | Clear dashboard caches before measuring (simulates first user after deploy). Omit to measure with cache warm. |
| `--target-queries` | Fail (exit 1) if query count exceeds N (default: 25). |
| `--target-ms` | Fail (exit 1) if elapsed time exceeds N ms (default: 2000). |
| `--quiet` | Print only PASS/FAIL and exit code (for CI). |

**Targets (defaults):** Dashboard stats + demographics + encounter stats + extra stats should stay under **50 queries** and **2000 ms** on a cold run. Tune `--target-queries` and `--target-ms` for your environment (stricter in CI after further optimization).

**When to run:**
- **After deploy:** `python manage.py verify_performance --cold` to ensure worst-case (cache miss) is within SLA.
- **CI / release gate:** `python manage.py verify_performance --cold --quiet` and fail the build if exit code is 1.
- **Capacity / baselining:** Run with and without `--cold` and record results before/after major changes.

**Example (CI):**
```bash
python manage.py verify_performance --cold --target-queries=25 --target-ms=2000 --quiet || exit 1
```

## Finding slow requests

- Enable `django.db.backends` logging at DEBUG level temporarily to log SQL.
- Use Django Debug Toolbar (only in development) to inspect queries per view.
- Check Prometheus metrics at `/metrics` for request counts and latency if you use them.

## Optional: profiling in staging

- **django-silk**: Install only in staging (e.g. `DEBUG=True` or `SILK_ENABLED=True`) to profile SQL and request timing. Do not enable in production.
- **HistoryRequestMiddleware** (simple_history): Runs on every request. If profiling shows it is significant, consider excluding static or health-check paths in the middleware so `/health/` and static assets are not recorded.
