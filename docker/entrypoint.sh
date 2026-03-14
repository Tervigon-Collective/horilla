#!/bin/bash
set -e

echo "Starting Horilla HR..."

# Wait for PostgreSQL to be ready (skip if using external DB)
if [[ "${DATABASE_URL}" == *"@db:"* ]] || [[ -z "${DATABASE_URL}" ]]; then
  echo "Waiting for PostgreSQL..."
  while ! nc -z db 5432; do
    sleep 0.1
  done
  echo "PostgreSQL is ready!"
else
  echo "Using external database, skipping wait."
fi

# Run migrations (skip makemigrations - migrations are committed; avoids history check on existing DBs)
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

echo "Starting server..."
exec "$@"
