# ⚠️ Virtual Environment Issue

## Problem
The virtual environment (`venv`) is corrupted - pip is broken.

## Solutions

### Option 1: Use Docker (Easiest - Recommended)
```bash
docker-compose up -d web
```

This will start the web server in Docker with all dependencies already installed.

### Option 2: Recreate Virtual Environment
```bash
# Remove old venv
Remove-Item -Recurse -Force venv

# Create new venv
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start server
python manage.py runserver 0.0.0.0:8000
```

### Option 3: Use System Python (If Django is installed)
```bash
python manage.py runserver 0.0.0.0:8000
```

## Quick Fix - Use Docker

Since Docker was working before, the easiest solution is:

```bash
docker-compose up -d web
```

Then access: http://localhost:8000

The database is already running in Docker, so this will work immediately.

