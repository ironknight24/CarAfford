from datetime import datetime
from decimal import Decimal
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AuditSchemaMixin(BaseModel):
    source: Optional[str] = None
    source_url: Optional[str] = None
    effective_date: Optional[datetime] = None
    last_verified_date: Optional[datetime] = None


class BaseResponse(BaseModel, Generic[T]):
    success: bool = True
    message: Optional[str] = None
    data: T


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
