from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.pricing import ExShowroomPrice, PriceHistory


class PricingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_ex_showroom_price(
        self,
        variant_id: int,
        state_id: Optional[int] = None,
        city_id: Optional[int] = None,
    ) -> Optional[ExShowroomPrice]:
        # Try city specific first, then state specific, then nationwide (state_id is None)
        if city_id:
            stmt = select(ExShowroomPrice).where(
                ExShowroomPrice.variant_id == variant_id,
                ExShowroomPrice.city_id == city_id,
                ExShowroomPrice.is_current == True,
            )
            result = await self.session.execute(stmt)
            price = result.scalars().first()
            if price:
                return price

        if state_id:
            stmt = select(ExShowroomPrice).where(
                ExShowroomPrice.variant_id == variant_id,
                ExShowroomPrice.state_id == state_id,
                ExShowroomPrice.is_current == True,
            )
            result = await self.session.execute(stmt)
            price = result.scalars().first()
            if price:
                return price

        # Fallback to any current price for this variant
        stmt = select(ExShowroomPrice).where(
            ExShowroomPrice.variant_id == variant_id,
            ExShowroomPrice.is_current == True,
        ).order_by(ExShowroomPrice.id.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_price_history(self, variant_id: int) -> List[PriceHistory]:
        stmt = select(PriceHistory).where(PriceHistory.variant_id == variant_id).order_by(PriceHistory.recorded_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
