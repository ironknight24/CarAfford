from contextlib import asynccontextmanager
import logging
import uuid
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import CarAffordException
from app.core.middleware import (
    RateLimitingMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.redis import close_redis, get_redis_client
from app.db.seed import ensure_default_admin

# Configure structured logging format
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("carafford")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate environment settings in production
    settings.validate_production_configuration()
    logger.info(f"Initializing {settings.PROJECT_NAME} in [{settings.ENVIRONMENT.upper()}] environment...")

    # Initialize redis connection
    if settings.REDIS_ENABLED:
        try:
            await get_redis_client()
            logger.info("Connected to Redis cache layer.")
        except Exception as e:
            logger.warning(f"Redis connection warning: {e}")

    # Ensure default administrator exists
    try:
        async with AsyncSessionLocal() as session:
            await ensure_default_admin(session)
    except Exception as e:
        logger.warning(f"Admin seed verification: {e}")

    yield

    logger.info("Shutting down CarAfford application...")
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Indian Car Affordability, On-Road Pricing & Recommendation Platform",
    docs_url="/docs" if settings.ENVIRONMENT.lower() != "production" or settings.DEBUG else None,
    redoc_url="/redoc" if settings.ENVIRONMENT.lower() != "production" or settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# 1. Request ID Middleware
app.add_middleware(RequestIDMiddleware)

# 2. Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate Limiting Middleware
app.add_middleware(RateLimitingMiddleware)

# 4. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# =============================================================================
# STANDARDIZED API ERROR HANDLERS
# =============================================================================

@app.exception_handler(CarAffordException)
async def carafford_exception_handler(request: Request, exc: CarAffordException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": exc.message,
            "error": {
                "code": "BAD_REQUEST",
                "message": exc.message,
                "request_id": request_id,
                "details": exc.details,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    exc_headers = exc.headers or {}
    response_headers = {**exc_headers, "X-Request-ID": request_id}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": detail_msg,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": detail_msg,
                "request_id": request_id,
            }
        },
        headers=response_headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        errors.append({"field": loc, "message": err.get("msg")})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": errors,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request payload failed schema validation.",
                "request_id": request_id,
                "details": errors,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(f"[500 ERROR] req={request_id} path={request.url.path} exc={exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred. Please contact system support.",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


# Root Health Probes (Direct aliases for cloud orchestrators)
app.include_router(health.router, prefix="/health", tags=["Health Probes"])


@app.get("/", tags=["Root"])
async def root(request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {
        "message": "Welcome to CarAfford API - Indian Car Affordability Engine",
        "docs": "/docs",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "request_id": request_id,
    }


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)
