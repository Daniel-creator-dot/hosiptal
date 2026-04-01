# Seeing Code Changes in Docker Desktop

When you make code changes but don't see them reflected when running the app in Docker:

## Quick fix: Restart the web container

The project uses `volumes: - .:/app` so your local code **is** mounted into the container. However, **Gunicorn** (the app server) loads and caches the application at startup. You need to restart the web service to pick up changes.

### Option 1: Restart only the web container (fastest)
```bash
docker compose restart web
```

### Option 2: Rebuild and restart (if changes include new dependencies or Dockerfile changes)
```bash
docker compose up -d --build
```

### Option 3: Full restart of all services
```bash
docker compose down
docker compose up -d
```

## Summary
- **Python/template changes** → `docker compose restart web`
- **New packages in requirements.txt** → `docker compose up -d --build`
- **Database migrations** → Run automatically on container start, or: `docker compose exec web python manage.py migrate`
