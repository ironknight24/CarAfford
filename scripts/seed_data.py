#!/usr/bin/env python3
import asyncio
import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.seed import seed_database

if __name__ == "__main__":
    asyncio.run(seed_database())
