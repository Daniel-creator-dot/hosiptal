# Enable line-level waiver (Prescribe Sale items)

The message **"Line-level waiver is not available yet. Please run database migrations"** means the migration that adds `waived_at` / `waived_by` / `waiver_reason` to Prescribe Sale **line items** has not been applied on that environment.

## On the server (Docker, e.g. 192.168.2.216)

**If the web container is already running**, run:

```bash
docker compose exec web python manage.py migrate --noinput
```

Or with hyphen:

```bash
docker-compose exec web python manage.py migrate --noinput
```

**If you are not in the project directory**, either `cd` to the app directory first, or use:

```bash
docker compose -f /path/to/docker-compose.yml exec web python manage.py migrate --noinput
```

## From your PC (against the same Docker stack)

From the project folder (e.g. `d:\chm`):

```bash
RUN_MIGRATE_NOW.bat
```

That runs `docker-compose run --rm web python manage.py migrate --noinput`, which applies all pending migrations including `1100_walkinpharmacysaleitem_waiver`.

## Verify

After migrating, open a patient total bill, open **Service breakdown** for a Prescribe Sale, and use **Waive** on a line. It should succeed and the line should show as waived.
