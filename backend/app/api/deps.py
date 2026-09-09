from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session

# Re-export for standard injection
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session
