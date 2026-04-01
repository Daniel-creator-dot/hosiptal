#!/bin/sh
# Run migrations inside Docker (use on server: ./run_migrate.sh or docker compose exec web python manage.py migrate --noinput)
set -e
echo "Running database migrations..."
docker compose run --rm web python manage.py migrate --noinput
echo "Migrations applied successfully."
