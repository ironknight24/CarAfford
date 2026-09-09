#!/usr/bin/env sh
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Seeding catalog and tax data..."
PYTHONPATH=/app python -m app.db.seed

echo "Starting CarAfford Backend API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
