from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.repositories.tax_rule_repo import TaxRuleRepository
from app.schemas.tax_rule import (
    PaginatedTaxRuleResponse,
    TaxRuleCreate,
    TaxRuleDetailRead,
    TaxRuleRead,
    TaxRuleResolveResponse,
    TaxRuleUpdate,
    TaxRuleValidationResult,
)
from app.services.tax_rule_resolver import TaxRuleResolverService

router = APIRouter(prefix="/tax-rules", tags=["Tax & Registration Rules"])


@router.get("", response_model=PaginatedTaxRuleResponse)
async def list_tax_rules(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    city_id: Optional[int] = Query(None, description="Filter by City ID"),
    rto_id: Optional[int] = Query(None, description="Filter by RTO Office ID"),
    tax_type: Optional[str] = Query(None, description="Filter by tax/fee type (ROAD_TAX, REGISTRATION_FEE, etc.)"),
    rule_category: Optional[str] = Query(None, description="Filter by category (TAX, REGISTRATION, FEE, CESS)"),
    calculation_method: Optional[str] = Query(None, description="Filter by method (FIXED, PERCENTAGE, BRACKETED, FORMULA)"),
    fuel_type: Optional[str] = Query(None, description="Filter by applicable fuel type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search term across name, tax_type, description"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves paginated list of statutory vehicle taxation and registration charge rules."""
    items, total = await TaxRuleRepository.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        state_id=state_id,
        city_id=city_id,
        rto_id=rto_id,
        tax_type=tax_type,
        rule_category=rule_category,
        calculation_method=calculation_method,
        fuel_type=fuel_type,
        active=active,
        search=search,
    )
    page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return PaginatedTaxRuleResponse(
        items=items,
        total=total,
        page=page,
        page_size=limit,
        total_pages=total_pages,
    )


@router.get("/resolve", response_model=TaxRuleResolveResponse)
async def resolve_tax_rules(
    state_id: int = Query(..., description="Target State ID (required)"),
    city_id: Optional[int] = Query(None, description="Optional target City ID"),
    rto_id: Optional[int] = Query(None, description="Optional target RTO Office ID"),
    variant_id: Optional[int] = Query(None, description="Optional Vehicle Variant ID for automatic spec/price resolution"),
    fuel_type: Optional[str] = Query(None, description="Vehicle fuel type (Petrol, Diesel, Electric, CNG, Hybrid)"),
    engine_cc: Optional[int] = Query(None, ge=0, description="Vehicle engine capacity in CC"),
    ex_showroom_price: Optional[Decimal] = Query(None, ge=0, description="Ex-showroom retail price in INR"),
    is_ev: Optional[bool] = Query(None, description="Whether the vehicle is an EV"),
    vehicle_type: str = Query("CAR", description="Vehicle type (CAR, TWO_WHEELER, COMMERCIAL, ANY)"),
    usage_type: str = Query("PRIVATE", description="Usage type (PRIVATE, COMMERCIAL, ANY)"),
    calculation_date: Optional[datetime] = Query(None, description="Historical, current, or future calculation date (ISO-8601)"),
    is_bh_series: bool = Query(False, description="Whether to resolve Bharat (BH) series registration rules"),
    is_financed: bool = Query(True, description="Whether vehicle will be hypothecated under bank finance"),
    db: AsyncSession = Depends(get_db),
):
    """Deterministically resolves the exact applicable set of tax and registration rules for a specific
    vehicle, location, date, and finance condition.

    NOTE: This endpoint resolves applicable rules and does NOT calculate final on-road prices.
    """
    try:
        result = await TaxRuleResolverService.resolve_rules(
            db=db,
            state_id=state_id,
            city_id=city_id,
            rto_id=rto_id,
            variant_id=variant_id,
            fuel_type=fuel_type,
            engine_cc=engine_cc,
            ex_showroom_price=ex_showroom_price,
            is_ev=is_ev,
            vehicle_type=vehicle_type,
            usage_type=usage_type,
            calculation_date=calculation_date,
            is_bh_series=is_bh_series,
            is_financed=is_financed,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )


@router.post("/validate", response_model=TaxRuleValidationResult)
async def validate_tax_rule(
    rule_data: TaxRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Validates tax rule data against location hierarchy, bracket integrity, and overlapping active periods."""
    is_valid, errors, warnings = await TaxRuleRepository.validate_tax_rule_data(
        db, rule_data
    )
    return TaxRuleValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
    )


@router.get("/{id}", response_model=TaxRuleDetailRead)
async def get_tax_rule(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves single tax rule detail with bracket slabs, location hierarchy, and data source provenance."""
    rule = await TaxRuleRepository.get_by_id(db, id, include_relations=True)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TaxRule with ID={id} not found.",
        )
    return rule


@router.post("", response_model=TaxRuleRead, status_code=status.HTTP_201_CREATED)
async def create_tax_rule(
    rule_in: TaxRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Creates a new statutory tax or registration charge rule."""
    is_valid, errors, warnings = await TaxRuleRepository.validate_tax_rule_data(
        db, rule_in
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Tax rule validation failed", "errors": errors},
        )
    return await TaxRuleRepository.create(db, rule_in)


@router.put("/{id}", response_model=TaxRuleRead)
async def update_tax_rule(
    id: int,
    rule_in: TaxRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Updates an existing statutory tax rule."""
    db_rule = await TaxRuleRepository.get_by_id(db, id, include_relations=True)
    if not db_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TaxRule with ID={id} not found.",
        )
    return await TaxRuleRepository.update(db, db_rule, rule_in)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_rule(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Deletes an existing statutory tax rule."""
    success = await TaxRuleRepository.delete(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TaxRule with ID={id} not found.",
        )
