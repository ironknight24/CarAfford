from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.data_source import DataSource
from app.models.location import City, RtoOffice, State
from app.models.tax_rule import TaxRule, TaxRuleBracket
from app.schemas.tax_rule import TaxRuleBracketCreate, TaxRuleCreate, TaxRuleUpdate


class TaxRuleRepository:
    """Repository handling persistence, validation, querying, and candidate retrieval for TaxRules."""

    @staticmethod
    async def get_by_id(
        db: AsyncSession, rule_id: int, include_relations: bool = True
    ) -> Optional[TaxRule]:
        stmt = select(TaxRule).where(TaxRule.id == rule_id)
        if include_relations:
            stmt = stmt.options(
                selectinload(TaxRule.brackets),
                selectinload(TaxRule.state),
                selectinload(TaxRule.city),
                selectinload(TaxRule.rto),
                selectinload(TaxRule.source),
            )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_multi(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        state_id: Optional[int] = None,
        city_id: Optional[int] = None,
        rto_id: Optional[int] = None,
        tax_type: Optional[str] = None,
        rule_category: Optional[str] = None,
        calculation_method: Optional[str] = None,
        fuel_type: Optional[str] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[TaxRule], int]:
        stmt = select(TaxRule).options(
            selectinload(TaxRule.brackets),
            selectinload(TaxRule.state),
            selectinload(TaxRule.city),
            selectinload(TaxRule.rto),
            selectinload(TaxRule.source),
        )

        if state_id is not None:
            stmt = stmt.where(TaxRule.state_id == state_id)
        if city_id is not None:
            stmt = stmt.where(TaxRule.city_id == city_id)
        if rto_id is not None:
            stmt = stmt.where(TaxRule.rto_id == rto_id)
        if tax_type:
            stmt = stmt.where(TaxRule.tax_type.ilike(f"%{tax_type}%"))
        if rule_category:
            stmt = stmt.where(TaxRule.rule_category == rule_category.upper())
        if calculation_method:
            stmt = stmt.where(TaxRule.calculation_method == calculation_method.upper())
        if fuel_type:
            stmt = stmt.where(
                or_(
                    TaxRule.fuel_type.ilike(f"%{fuel_type}%"),
                    TaxRule.fuel_type == "ANY",
                    TaxRule.fuel_type.is_(None),
                )
            )
        if active is not None:
            stmt = stmt.where(TaxRule.active == active)
        if search:
            s = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    TaxRule.name.ilike(s),
                    TaxRule.tax_type.ilike(s),
                    TaxRule.description.ilike(s),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        # Order by state, priority desc, name
        stmt = stmt.order_by(TaxRule.state_id, TaxRule.priority.desc(), TaxRule.name)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def validate_tax_rule_data(
        db: AsyncSession, rule_data: TaxRuleCreate, rule_id: Optional[int] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """Performs strict domain validation on TaxRule data:
        1. Verifies location foreign keys and hierarchical integrity.
        2. Validates bracket continuity, ascending bounds, and non-overlap.
        3. Checks for invalid / conflicting overlapping active rules.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. State check
        state = await db.get(State, rule_data.state_id)
        if not state:
            errors.append(f"State with id={rule_data.state_id} does not exist.")
        else:
            # 2. City check within State
            if rule_data.city_id is not None:
                city = await db.get(City, rule_data.city_id)
                if not city:
                    errors.append(f"City with id={rule_data.city_id} does not exist.")
                elif city.state_id != state.id:
                    errors.append(
                        f"City '{city.name}' (state_id={city.state_id}) does not belong to specified State '{state.name}' (id={state.id})."
                    )

            # 3. RTO check within State
            if rule_data.rto_id is not None:
                rto = await db.get(RtoOffice, rule_data.rto_id)
                if not rto:
                    errors.append(f"RTO with id={rule_data.rto_id} does not exist.")
                elif rto.state_id != state.id:
                    errors.append(
                        f"RTO '{rto.code}' (state_id={rto.state_id}) does not belong to specified State '{state.name}' (id={state.id})."
                    )
                elif rule_data.city_id is not None and rto.city_id is not None and rto.city_id != rule_data.city_id:
                    warnings.append(
                        f"RTO '{rto.code}' is associated with city_id={rto.city_id}, while rule specified city_id={rule_data.city_id}."
                    )

        # 4. Data Source check
        if rule_data.source_id is not None:
            source = await db.get(DataSource, rule_data.source_id)
            if not source:
                errors.append(f"DataSource with id={rule_data.source_id} does not exist.")

        # 5. Calculation method specific validations
        if rule_data.calculation_method == "PERCENTAGE" and rule_data.rate is None:
            errors.append("Rule with calculation_method='PERCENTAGE' requires a valid 'rate' field.")
        elif rule_data.calculation_method == "FIXED" and (rule_data.fixed_amount is None or rule_data.fixed_amount < 0):
            errors.append("Rule with calculation_method='FIXED' requires a non-negative 'fixed_amount'.")
        elif rule_data.calculation_method == "BRACKETED":
            brackets = rule_data.brackets or []
            if not brackets:
                errors.append("Rule with calculation_method='BRACKETED' must contain at least one bracket slab.")
            else:
                # Sort brackets by minimum_value
                sorted_brackets = sorted(brackets, key=lambda b: b.minimum_value)
                for i, brk in enumerate(sorted_brackets):
                    if brk.minimum_value < 0:
                        errors.append(f"Bracket #{i+1}: minimum_value cannot be negative ({brk.minimum_value}).")
                    if brk.maximum_value is not None and brk.maximum_value <= brk.minimum_value:
                        errors.append(
                            f"Bracket #{i+1}: maximum_value ({brk.maximum_value}) must be > minimum_value ({brk.minimum_value})."
                        )
                    # Check overlap with previous bracket
                    if i > 0:
                        prev = sorted_brackets[i - 1]
                        if prev.maximum_value is None:
                            errors.append(
                                f"Bracket #{i}: Previous bracket has unbounded maximum, so subsequent bracket #{i+1} creates an invalid overlap."
                            )
                        elif brk.minimum_value < prev.maximum_value:
                            errors.append(
                                f"Bracket #{i+1} [min={brk.minimum_value}] overlaps with previous bracket #{i} [max={prev.maximum_value}]."
                            )
                        elif brk.minimum_value > prev.maximum_value:
                            warnings.append(
                                f"Gap detected between bracket #{i} [max={prev.maximum_value}] and bracket #{i+1} [min={brk.minimum_value}]."
                            )

        # 6. Check for unintended overlapping active rules for identical exact scope
        overlap_stmt = (
            select(TaxRule)
            .where(
                TaxRule.state_id == rule_data.state_id,
                TaxRule.city_id == rule_data.city_id,
                TaxRule.rto_id == rule_data.rto_id,
                TaxRule.tax_type == rule_data.tax_type,
                TaxRule.vehicle_type == rule_data.vehicle_type,
                TaxRule.fuel_type == rule_data.fuel_type,
                TaxRule.is_ev == rule_data.is_ev,
                TaxRule.usage_type == rule_data.usage_type,
                TaxRule.active == True,
            )
        )
        if rule_id is not None:
            overlap_stmt = overlap_stmt.where(TaxRule.id != rule_id)

        existing_res = await db.execute(overlap_stmt)
        existing_rules = existing_res.scalars().all()

        for ex in existing_rules:
            # Check temporal intersection: [start1, end1] and [start2, end2]
            # No overlap if end1 < start2 or end2 < start1
            start1 = rule_data.effective_from
            end1 = rule_data.effective_to
            start2 = ex.effective_from
            end2 = ex.effective_to

            is_separate = False
            if end1 is not None and end1 < start2:
                is_separate = True
            elif end2 is not None and end2 < start1:
                is_separate = True

            if not is_separate:
                errors.append(
                    f"Overlapping effective period detected with existing active rule id={ex.id} ('{ex.name}') "
                    f"[{start2.strftime('%Y-%m-%d')} to {end2.strftime('%Y-%m-%d') if end2 else 'ongoing'}] "
                    f"for identical scope ({rule_data.tax_type}, state_id={rule_data.state_id}, city_id={rule_data.city_id}, rto_id={rule_data.rto_id})."
                )

        is_valid = len(errors) == 0
        return is_valid, errors, warnings

    @classmethod
    async def create(cls, db: AsyncSession, obj_in: TaxRuleCreate) -> TaxRule:
        rule_dict = obj_in.model_dump(exclude={"brackets"})
        db_rule = TaxRule(**rule_dict)

        if obj_in.brackets:
            for b in obj_in.brackets:
                db_bracket = TaxRuleBracket(**b.model_dump())
                db_rule.brackets.append(db_bracket)

        db.add(db_rule)
        await db.flush()
        await db.refresh(db_rule, ["brackets", "state", "city", "rto", "source"])
        return db_rule

    @classmethod
    async def update(
        cls, db: AsyncSession, db_obj: TaxRule, obj_in: TaxRuleUpdate
    ) -> TaxRule:
        update_data = obj_in.model_dump(exclude_unset=True)

        if "brackets" in update_data and update_data["brackets"] is not None:
            # Replace existing brackets
            db_obj.brackets.clear()
            for b_data in update_data["brackets"]:
                db_obj.brackets.append(TaxRuleBracket(**b_data))
            del update_data["brackets"]

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        await db.flush()
        await db.refresh(db_obj, ["brackets", "state", "city", "rto", "source"])
        return db_obj

    @classmethod
    async def delete(cls, db: AsyncSession, rule_id: int) -> bool:
        db_rule = await cls.get_by_id(db, rule_id, include_relations=False)
        if not db_rule:
            return False
        await db.delete(db_rule)
        await db.flush()
        return True

    @staticmethod
    async def get_candidate_rules_for_resolution(
        db: AsyncSession,
        state_id: int,
        city_id: Optional[int],
        rto_id: Optional[int],
        calculation_date: datetime,
    ) -> List[TaxRule]:
        """Queries all potentially matching candidate active tax rules for a location and effective calculation date."""
        location_filters = [
            # State-level rules (no city or RTO restriction)
            and_(TaxRule.state_id == state_id, TaxRule.city_id.is_(None), TaxRule.rto_id.is_(None))
        ]
        if city_id is not None:
            location_filters.append(
                and_(TaxRule.state_id == state_id, TaxRule.city_id == city_id, TaxRule.rto_id.is_(None))
            )
        if rto_id is not None:
            location_filters.append(
                and_(TaxRule.state_id == state_id, TaxRule.rto_id == rto_id)
            )

        stmt = (
            select(TaxRule)
            .where(
                TaxRule.active == True,
                or_(*location_filters),
                TaxRule.effective_from <= calculation_date,
                or_(
                    TaxRule.effective_to.is_(None),
                    TaxRule.effective_to >= calculation_date,
                ),
            )
            .options(
                selectinload(TaxRule.brackets),
                selectinload(TaxRule.state),
                selectinload(TaxRule.city),
                selectinload(TaxRule.rto),
                selectinload(TaxRule.source),
            )
            .order_by(TaxRule.priority.desc(), TaxRule.id.asc())
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())
