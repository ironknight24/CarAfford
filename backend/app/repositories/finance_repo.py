from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.finance import Bank, InterestRateSlab, LoanProduct


class FinanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_banks(self, active_only: bool = True) -> List[Bank]:
        stmt = select(Bank).options(
            selectinload(Bank.loan_products).selectinload(LoanProduct.interest_rate_slabs)
        )
        if active_only:
            stmt = stmt.where(Bank.is_active == True)
        stmt = stmt.order_by(Bank.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_loan_products(self, bank_id: Optional[int] = None) -> List[LoanProduct]:
        stmt = select(LoanProduct).options(
            selectinload(LoanProduct.bank),
            selectinload(LoanProduct.interest_rate_slabs),
        ).where(LoanProduct.is_active == True)

        if bank_id:
            stmt = stmt.where(LoanProduct.bank_id == bank_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_best_rate_for_cibil(self, cibil_score: int) -> Optional[InterestRateSlab]:
        stmt = (
            select(InterestRateSlab)
            .join(LoanProduct, InterestRateSlab.loan_product_id == LoanProduct.id)
            .options(selectinload(InterestRateSlab.loan_product).selectinload(LoanProduct.bank))
            .where(
                LoanProduct.is_active == True,
                InterestRateSlab.min_cibil_score <= cibil_score,
                InterestRateSlab.max_cibil_score >= cibil_score,
            )
            .order_by(InterestRateSlab.default_interest_rate.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
