FROM python:3.12-slim

WORKDIR /app

# Update package lists and install required system dependencies
# Core compilation tools, PostgreSQL client, and PDF generation libraries
# Using latest package versions
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
        libgirepository1.0-dev \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/* \
        && rm -rf /tmp/* \
        && rm -rf /var/tmp/*

# Upgrade pip, setuptools, and wheel to latest versions
RUN pip install --upgrade pip setuptools wheel

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

# Latest features included:
# - Clinical consumables billing system (pharmacy can add consumables to patient bills)
# - Print functionality for cashier sessions
# - Accountant access to cashier history
# - Performance optimizations and duplicate prevention
# - Duplicate prevention system (MedicalRecord, ClinicalNote, LabResult, ImagingStudy, Transaction, PaymentReceipt)
# - Front desk enhancements (doctor assignment, consultation charges, patient deposits)
# - Performance optimizations (database indexes, query optimization)
# - Price import from legacy billing data
# - Lab test code display improvements

# Don't collect static files here - do it at runtime in docker-compose
# This ensures static files are always up-to-date on restart
# RUN python manage.py collectstatic --no-input --clear || true

# Expose port (configurable via PORT env var)
EXPOSE $PORT

# Health check (will be overridden by docker-compose healthcheck)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Default command (will be overridden by docker-compose)
# This ensures the container can start even without docker-compose
CMD ["/bin/sh", "-c", "echo 'Waiting for docker-compose command override...' && sleep infinity"]
