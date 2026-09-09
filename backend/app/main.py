from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import CarAffordException
from app.core.redis import close_redis, get_redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("carafford")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing CarAfford application...")
    # Initialize redis connection
    if settings.REDIS_ENABLED:
        await get_redis_client()
    yield
    logger.info("Shutting down CarAfford application...")
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Indian Car Affordability, On-Road Pricing & Recommendation Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CarAffordException)
async def carafford_exception_handler(request: Request, exc: CarAffordException):
    return JSONResponse(
        status_code=400,
        content={"success": False, "message": exc.message, "details": exc.details},
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to CarAfford API - Indian Car Affordability Engine",
        "docs": "/docs",
        "version": settings.VERSION,
    }


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)
