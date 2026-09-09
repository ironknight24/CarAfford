from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DataSourceBase(BaseModel):
    name: str
    slug: str
    provider_type: str
    base_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceRead(DataSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    last_synced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
