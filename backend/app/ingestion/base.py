import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionEntityType,
    IngestionRunStatus,
    VerificationStatus,
)


def compute_payload_hash(payload: Any) -> str:
    """Computes a deterministic SHA-256 hash of a JSON-serializable dictionary."""

    def default_serializer(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    canonical_json = json.dumps(payload, sort_keys=True, default=default_serializer)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class DataFetcher(ABC):
    """Abstract fetcher for acquiring external payloads (via API, file, feed, or database)."""

    @abstractmethod
    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        """Retrieves raw payloads from the source."""
        pass


class DataParser(ABC):
    """Abstract parser for parsing raw bytes/strings/dicts into intermediate structured dictionaries."""

    @abstractmethod
    def parse(self, raw_payload: Any) -> Dict[str, Any]:
        """Parses a single raw item into structured key-values."""
        pass


class DataNormalizer(ABC):
    """Abstract normalizer for standardizing types, fuel enums, units, and names."""

    @abstractmethod
    def normalize(self, parsed_item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes and cleans parsed field values."""
        pass


class DataValidator(ABC):
    """Abstract validator ensuring domain bounds, foreign keys, and date sanity."""

    @abstractmethod
    def validate(self, normalized_item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validates normalized item. Returns (is_valid, list_of_error_messages)."""
        pass


class CanonicalMapper(ABC):
    """Abstract mapper transforming validated payload into canonical domain entity attributes."""

    @abstractmethod
    def map_to_canonical(self, validated_item: Dict[str, Any]) -> Dict[str, Any]:
        """Maps attributes to target canonical model fields."""
        pass


class DataSourceAdapter(ABC):
    """Generic adapter combining Fetcher, Parser, Normalizer, Validator, and Mapper for an external source."""

    source_slug: str
    source_name: str
    source_type: DataSourceType
    dataset_name: str
    entity_type: IngestionEntityType

    @abstractmethod
    def get_fetcher(self) -> DataFetcher:
        pass

    @abstractmethod
    def get_parser(self) -> DataParser:
        pass

    @abstractmethod
    def get_normalizer(self) -> DataNormalizer:
        pass

    @abstractmethod
    def get_validator(self) -> DataValidator:
        pass

    @abstractmethod
    def get_mapper(self) -> CanonicalMapper:
        pass
