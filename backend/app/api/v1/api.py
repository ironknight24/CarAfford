from fastapi import APIRouter
from app.api.v1.endpoints import (
    affordability,
    data_sources,
    finance,
    health,
    locations,
    pricing,
    recommendations,
    tax_rules,
    vehicles,
)

api_router = APIRouter()

# Core Health
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# Locations Hierarchy & Search
api_router.include_router(locations.countries_router)
api_router.include_router(locations.states_router)
api_router.include_router(locations.cities_router)
api_router.include_router(locations.rtos_router)
api_router.include_router(locations.locations_router)

# Vehicle Catalogue & Search
api_router.include_router(vehicles.manufacturers_router)
api_router.include_router(vehicles.models_router)
api_router.include_router(vehicles.variants_router)
api_router.include_router(vehicles.vehicles_search_router)

# Tax & Registration Rules Domain
api_router.include_router(tax_rules.router)

# Pricing, Finance & Recommendations
api_router.include_router(pricing.router, prefix="/pricing", tags=["Pricing"])
api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])
api_router.include_router(affordability.router, prefix="/affordability", tags=["Affordability"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["Data Sources"])
