from fastapi import APIRouter
from app.api.v1.endpoints import (
    affordability,
    data_sources,
    finance,
    health,
    locations,
    pricing,
    recommendations,
    vehicles,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["Vehicles"])
api_router.include_router(pricing.router, prefix="/pricing", tags=["Pricing"])
api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])
api_router.include_router(affordability.router, prefix="/affordability", tags=["Affordability"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["Data Sources"])
