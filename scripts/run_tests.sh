#!/usr/bin/env bash
set -e

echo "=== Running CarAfford Test Suite ==="
cd "$(dirname "$0")/.."

echo "1. Running Backend Unit and Integration Pytests..."
PYTHONPATH=backend ./backend/.venv/bin/pytest -v backend/tests/

if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    echo "2. Building & Typechecking Frontend..."
    cd frontend
    npm run build
    cd ..
fi

echo "=== All CarAfford Tests Passed Successfully! ==="
