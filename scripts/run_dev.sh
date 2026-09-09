#!/usr/bin/env bash
set -e

echo "=== Starting CarAfford Local Development Environment ==="

# Check Python environment
if [ ! -d "backend/.venv" ]; then
    echo "Creating Python virtualenv..."
    python3 -m venv backend/.venv
    ./backend/.venv/bin/pip install --upgrade pip
    ./backend/.venv/bin/pip install -r backend/requirements-dev.txt
fi

# Run Postgres and Redis via Docker Compose if docker is available
if command -v docker &> /dev/null; then
    echo "Ensuring Postgres and Redis are running..."
    docker compose -f infrastructure/docker-compose.dev.yml up -d
fi

echo "Running database migrations..."
cd backend
PYTHONPATH=. ./alembic upgrade head || true
echo "Seeding initial catalog data..."
PYTHONPATH=. ./../scripts/seed_data.py || true
cd ..

echo "Starting Backend and Frontend services..."
echo "Backend: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"

(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &

wait
