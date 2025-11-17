FROM python:3.11-slim

WORKDIR /app

# Update package lists and install required system dependencies
# Core compilation tools, PostgreSQL client, and PDF generation libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
        gcc \
        g++ \
        python3-dev \
        libpq-dev \
        libmagic1 \
        pkg-config \
        libcairo2-dev \
        libgirepository1.0-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/media /app/static /app/staticfiles /app/logs && \
    chmod 755 /app/logs /app/media /app/static /app/staticfiles

# Set environment variables
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=hms.settings
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV GUNICORN_WORKERS=6
ENV GUNICORN_THREADS=4
ENV GUNICORN_MAX_REQUESTS=1000
ENV GUNICORN_MAX_REQUESTS_JITTER=100
ENV GUNICORN_TIMEOUT=120

# Collect static files
RUN python manage.py collectstatic --no-input --clear || true

# Expose port (configurable via PORT env var)
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Use gunicorn for production (not Django runserver)
CMD ["/bin/sh", "-c", "gunicorn hms.wsgi:application \
    --bind 0.0.0.0:${PORT} \
    --worker-class gthread \
    --workers ${GUNICORN_WORKERS:-6} \
    --threads ${GUNICORN_THREADS:-4} \
    --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \
    --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level info"]
