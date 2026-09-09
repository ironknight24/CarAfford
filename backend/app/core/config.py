from functools import lru_cache
from typing import List, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "CarAfford"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "carafford_user"
    POSTGRES_PASSWORD: str = "carafford_secret"
    POSTGRES_DB: str = "carafford_db"
    DATABASE_URL: Optional[str] = None
    ASYNC_DATABASE_URL: Optional[str] = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Domain Financial Defaults (India)
    DEFAULT_FOIR_LIMIT: float = 0.40  # Maximum 40% of net income to all EMIs
    DEFAULT_MAX_FOIR_LIMIT: float = 0.50  # Upper stretch boundary
    DEFAULT_ANNUAL_INTEREST_RATE: float = 8.75  # 8.75% standard SBI car loan rate
    DEFAULT_LOAN_TENURE_MONTHS: int = 60  # 5 years
    DEFAULT_DOWN_PAYMENT_MIN_PERCENT: float = 10.0  # 10% minimum down payment
    TCS_THRESHOLD_INR: float = 1000000.0  # ₹10,00,000 for 1% TCS under section 206C(1F)
    TCS_PERCENT: float = 1.0
    FASTAG_FEE_INR: float = 600.0
    REGISTRATION_BASE_FEE_INR: float = 1000.0
    HYPOTHECATION_FEE_INR: float = 1500.0
    DEFAULT_ANNUAL_MAINTENANCE_RATE: float = 0.015  # 1.5% of ex-showroom / yr
    DEFAULT_PETROL_PRICE_INR: float = 96.50
    DEFAULT_DIESEL_PRICE_INR: float = 89.50
    DEFAULT_CNG_PRICE_INR: float = 75.50
    DEFAULT_EV_PER_KWH_INR: float = 8.50

    @property
    def get_sync_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def get_async_database_url(self) -> str:
        if self.ASYNC_DATABASE_URL:
            return self.ASYNC_DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
