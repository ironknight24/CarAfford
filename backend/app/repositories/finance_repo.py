from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.finance import (
    Bank,
    InterestRate,
    InterestRateSlab,
    LoanEligibilityRule,
    LoanFee,
    LoanProduct,
)


class FinanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # 1. Banks
    # =========================================================================

    async def get_banks(
        self,
        page: int = 1,
        page_size: int = 20,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Bank], int]:
        stmt = select(Bank).options(
            selectinload(Bank.loan_products).selectinload(LoanProduct.interest_rates),
            selectinload(Bank.source),
        )
        count_stmt = select(func.count(Bank.id))

        if active is not None:
            stmt = stmt.where(Bank.active == active)
            count_stmt = count_stmt.where(Bank.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                Bank.name.ilike(search_term),
                Bank.slug.ilike(search_term),
                Bank.bank_type.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Bank.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_bank_by_id(self, bank_id: int) -> Optional[Bank]:
        stmt = (
            select(Bank)
            .options(
                selectinload(Bank.loan_products).selectinload(LoanProduct.interest_rates),
                selectinload(Bank.loan_products).selectinload(LoanProduct.fees),
                selectinload(Bank.loan_products).selectinload(LoanProduct.eligibility_rules),
                selectinload(Bank.source),
            )
            .where(Bank.id == bank_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_bank_by_slug(self, slug: str) -> Optional[Bank]:
        stmt = (
            select(Bank)
            .options(
                selectinload(Bank.loan_products).selectinload(LoanProduct.interest_rates),
                selectinload(Bank.source),
            )
            .where(Bank.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # =========================================================================
    # 2. Loan Products
    # =========================================================================

    async def get_loan_products(
        self,
        page: int = 1,
        page_size: int = 20,
        bank_id: Optional[int] = None,
        vehicle_type: Optional[str] = None,
        vehicle_condition: Optional[str] = None,
        product_category: Optional[str] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[LoanProduct], int]:
        stmt = select(LoanProduct).options(
            selectinload(LoanProduct.bank),
            selectinload(LoanProduct.interest_rates).selectinload(InterestRate.source),
            selectinload(LoanProduct.fees).selectinload(LoanFee.source),
            selectinload(LoanProduct.eligibility_rules).selectinload(LoanEligibilityRule.source),
            selectinload(LoanProduct.interest_rate_slabs),
        )
        count_stmt = select(func.count(LoanProduct.id))

        if bank_id:
            stmt = stmt.where(LoanProduct.bank_id == bank_id)
            count_stmt = count_stmt.where(LoanProduct.bank_id == bank_id)

        if vehicle_type and vehicle_type != "ANY":
            stmt = stmt.where(
                or_(LoanProduct.vehicle_type == vehicle_type, LoanProduct.vehicle_type == "ANY")
            )
            count_stmt = count_stmt.where(
                or_(LoanProduct.vehicle_type == vehicle_type, LoanProduct.vehicle_type == "ANY")
            )

        if vehicle_condition and vehicle_condition != "ANY":
            stmt = stmt.where(
                or_(
                    LoanProduct.vehicle_condition == vehicle_condition,
                    LoanProduct.vehicle_condition == "ANY",
                )
            )
            count_stmt = count_stmt.where(
                or_(
                    LoanProduct.vehicle_condition == vehicle_condition,
                    LoanProduct.vehicle_condition == "ANY",
                )
            )

        if product_category:
            stmt = stmt.where(LoanProduct.product_category == product_category)
            count_stmt = count_stmt.where(LoanProduct.product_category == product_category)

        if active is not None:
            stmt = stmt.where(LoanProduct.active == active)
            count_stmt = count_stmt.where(LoanProduct.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                LoanProduct.name.ilike(search_term),
                LoanProduct.slug.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(LoanProduct.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_loan_product_by_id(self, product_id: int) -> Optional[LoanProduct]:
        stmt = (
            select(LoanProduct)
            .options(
                selectinload(LoanProduct.bank),
                selectinload(LoanProduct.interest_rates).selectinload(InterestRate.source),
                selectinload(LoanProduct.fees).selectinload(LoanFee.source),
                selectinload(LoanProduct.eligibility_rules).selectinload(
                    LoanEligibilityRule.source
                ),
                selectinload(LoanProduct.interest_rate_slabs),
            )
            .where(LoanProduct.id == product_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_loan_products_for_comparison(
        self,
        vehicle_type: str = "CAR",
        vehicle_condition: str = "NEW",
        is_ev: bool = False,
    ) -> List[LoanProduct]:
        """Retrieves all active loan products from active banks with preloaded rates, fees, and rules."""
        stmt = (
            select(LoanProduct)
            .join(Bank, LoanProduct.bank_id == Bank.id)
            .options(
                selectinload(LoanProduct.bank),
                selectinload(LoanProduct.interest_rates).selectinload(InterestRate.source),
                selectinload(LoanProduct.fees).selectinload(LoanFee.source),
                selectinload(LoanProduct.eligibility_rules).selectinload(
                    LoanEligibilityRule.source
                ),
                selectinload(LoanProduct.interest_rate_slabs),
            )
            .where(
                Bank.active == True,
                LoanProduct.active == True,
                or_(LoanProduct.vehicle_type == vehicle_type, LoanProduct.vehicle_type == "ANY"),
                or_(
                    LoanProduct.vehicle_condition == vehicle_condition,
                    LoanProduct.vehicle_condition == "ANY",
                ),
            )
            .order_by(Bank.name, LoanProduct.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # 3. Interest Rates
    # =========================================================================

    async def get_interest_rates(
        self,
        page: int = 1,
        page_size: int = 20,
        loan_product_id: Optional[int] = None,
        active: Optional[bool] = None,
    ) -> Tuple[List[InterestRate], int]:
        stmt = select(InterestRate).options(
            selectinload(InterestRate.loan_product).selectinload(LoanProduct.bank),
            selectinload(InterestRate.source),
        )
        count_stmt = select(func.count(InterestRate.id))

        if loan_product_id:
            stmt = stmt.where(InterestRate.loan_product_id == loan_product_id)
            count_stmt = count_stmt.where(InterestRate.loan_product_id == loan_product_id)

        if active is not None:
            stmt = stmt.where(InterestRate.active == active)
            count_stmt = count_stmt.where(InterestRate.active == active)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            stmt.order_by(InterestRate.priority.desc(), InterestRate.annual_interest_rate.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_interest_rate_by_id(self, rate_id: int) -> Optional[InterestRate]:
        stmt = (
            select(InterestRate)
            .options(
                selectinload(InterestRate.loan_product).selectinload(LoanProduct.bank),
                selectinload(InterestRate.source),
            )
            .where(InterestRate.id == rate_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # =========================================================================
    # 4. Legacy helpers for recommendation engine
    # =========================================================================

    async def get_best_rate_for_cibil(self, cibil_score: int) -> Optional[InterestRateSlab]:
        stmt = (
            select(InterestRateSlab)
            .join(LoanProduct, InterestRateSlab.loan_product_id == LoanProduct.id)
            .options(selectinload(InterestRateSlab.loan_product).selectinload(LoanProduct.bank))
            .where(
                LoanProduct.active == True,
                InterestRateSlab.min_cibil_score <= cibil_score,
                InterestRateSlab.max_cibil_score >= cibil_score,
            )
            .order_by(InterestRateSlab.default_interest_rate.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
