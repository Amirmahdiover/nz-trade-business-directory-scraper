"""Pydantic data models for directory records and failed requests."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, StrictStr


class BusinessRecord(BaseModel):
    """A normalized public business listing record."""

    business_name: str
    trade_category: Optional[str] = None
    region: Optional[str] = None
    phone: Optional[StrictStr] = None
    description: Optional[str] = None
    listing_url: Optional[str] = None
    source_url: str


class TradeCategory(BaseModel):
    """A public TradeHQ trade category discovered from the directory."""

    trade_category: str
    category_url: str
    listed_count: Optional[int] = None


class FailedURL(BaseModel):
    """A URL that could not be fetched or processed."""

    url: str
    error_type: str
    error_message: str
    status_code: Optional[int] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
