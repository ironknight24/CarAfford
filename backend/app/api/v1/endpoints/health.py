from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.config import settings
from app.core.redis import get_redis_client

router = APIRouter()


@router.get("", summary="Health Check")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    redis_status = "disabled"
    if settings.REDIS_ENABLED:
        try:
            client = await get_redis_client()
            redis_status = "ok" if client else "unreachable"
        except Exception as e:
            redis_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "redis": redis_status,
    }
