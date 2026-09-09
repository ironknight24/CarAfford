#!/usr/bin/env sh
set -e

echo "Applying database migrations..."
alembic upgrade head || true

echo "Seeding catalog and tax data..."
python app/db/seed.py || true

echo "Starting CarAfford Backend API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
