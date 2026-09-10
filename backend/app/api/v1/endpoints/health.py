import time
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.database import engine
from app.core.redis import get_redis_client

router = APIRouter()


@router.get("/live", summary="Process Liveness Probe")
async def liveness_probe() -> Dict[str, Any]:
    """Kubernetes / Container liveness probe. Confirms process is responsive without touching DB."""
    return {
        "status": "alive",
        "timestamp": time.time(),
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@router.get("/ready", summary="Dependency Readiness Probe")
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Readiness probe verifying operational state of PostgreSQL and Redis dependencies."""
    checks: Dict[str, Any] = {}
    is_ready = True

    # 1. Database check
    t0 = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        checks["database"] = {
            "status": "ready",
            "latency_ms": db_latency_ms,
        }
    except Exception as e:
        is_ready = False
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # 2. Redis check
    if settings.REDIS_ENABLED:
        t0 = time.perf_counter()
        try:
            client = await get_redis_client()
            if client:
                await client.ping()
                redis_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                checks["redis"] = {
                    "status": "ready",
                    "latency_ms": redis_latency_ms,
                }
            else:
                checks["redis"] = {"status": "disabled_or_unavailable"}
        except Exception as e:
            checks["redis"] = {
                "status": "degraded",
                "error": str(e),
            }
    else:
        checks["redis"] = {"status": "disabled"}

    response_data = {
        "status": "ready" if is_ready else "not_ready",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }

    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response_data,
        )

    return response_data


@router.get("/metrics", summary="Application Observability Metrics")
async def application_metrics(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Observability endpoint exposing operational metrics and pool statistics."""
    pool = engine.pool
    pool_stats = {
        "size": pool.size(),
        "checkedin": pool.checkedin(),
        "checkedout": pool.checkedout(),
        "overflow": pool.overflow(),
    }

    return {
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database_pool": pool_stats,
        "rate_limiting": {
            "enabled": settings.RATE_LIMIT_ENABLED,
            "default_limit_per_min": settings.RATE_LIMIT_DEFAULT_PER_MIN,
            "auth_limit_per_min": settings.RATE_LIMIT_AUTH_PER_MIN,
        },
    }


@router.get("", summary="General Health Check")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Backward-compatible general health summary endpoint."""
    ready_status = await readiness_probe(db=db)
    return {
        "status": "healthy" if ready_status["status"] == "ready" else "degraded",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": ready_status["checks"]["database"]["status"],
        "redis": ready_status["checks"].get("redis", {}).get("status", "unknown"),
    }
