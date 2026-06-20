"""Cleaning, normalization, and deduplication helpers."""

import re
from typing import Iterable, List, Optional
from urllib.parse import urlparse, urlunparse

from app.models import BusinessRecord
from app.utils import model_to_dict


def clean_text(text: Optional[str]) -> Optional[str]:
    """Normalize whitespace in a text field."""

    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    return cleaned or None


def clean_display_text(text: Optional[str]) -> Optional[str]:
    """Normalize human-readable text without modifying phones or URLs."""

    cleaned = clean_text(text)
    if not cleaned:
        return None

    protected_tokens: dict[str, str] = {}
    token_pattern = re.compile(
        r"https?://[^\s]+|www\.[^\s]+|"
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        flags=re.IGNORECASE,
    )

    def protect_token(match: re.Match) -> str:
        placeholder = f"TEXTTOKEN{len(protected_tokens)}"
        protected_tokens[placeholder] = match.group(0)
        return placeholder

    cleaned = token_pattern.sub(protect_token, cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z])([,;:!?])(?=[A-Za-z])", r"\1 ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    for placeholder, original in protected_tokens.items():
        cleaned = cleaned.replace(placeholder, original)

    return cleaned or None


def clean_phone(phone: Optional[str]) -> Optional[str]:
    """Clean a phone number while preserving it as human-readable text."""

    if phone is None:
        return None
    if not isinstance(phone, str):
        raise TypeError("phone must be a string or None")

    raw = phone.strip()
    if not raw:
        return None

    raw = re.sub(r"^tel:\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"(ext|extension|x)\s*\d+$", "", raw, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", raw)
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", cleaned):
        raise ValueError("phone must not use scientific notation")
    if not re.search(r"\d", cleaned):
        return None
    return cleaned


def phone_match_key(phone: Optional[str]) -> Optional[str]:
    """Return a string-only comparison key without changing the stored phone."""

    cleaned = clean_phone(phone)
    if not cleaned:
        return None

    digits = re.sub(r"\D", "", cleaned)
    if digits.startswith("0064"):
        return f"0{digits[4:]}"
    if digits.startswith("64"):
        return f"0{digits[2:]}"
    return digits or None


def clean_url(url: Optional[str]) -> Optional[str]:
    """Normalize an HTTP(S) URL while preserving its query string."""

    if url is None:
        return None

    value = str(url).strip()
    if not value:
        return None
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"

    parsed = urlparse(value)
    if not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/")
    cleaned = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return cleaned.rstrip("/")


def clean_business_record(record: BusinessRecord) -> BusinessRecord:
    """Return a cleaned copy of a business record."""

    data = model_to_dict(record)
    for field in [
        "business_name",
        "trade_category",
        "region",
        "description",
    ]:
        data[field] = clean_display_text(data.get(field))

    data["phone"] = clean_phone(data.get("phone"))
    data["listing_url"] = clean_url(data.get("listing_url"))
    data["source_url"] = clean_url(data.get("source_url"))
    return BusinessRecord(**data)


def _completeness(record: BusinessRecord) -> int:
    return sum(
        bool(clean_text(getattr(record, field)))
        for field in (
            "business_name",
            "trade_category",
            "region",
            "phone",
            "description",
            "listing_url",
            "source_url",
        )
    )


def deduplicate_records(records: Iterable[BusinessRecord]) -> List[BusinessRecord]:
    """Deduplicate by listing URL, then normalized business name and phone."""

    primary_records = {}
    alias_to_primary = {}
    ordered_primary_keys = []

    for record in records:
        name = (clean_text(record.business_name) or "").lower()
        phone = phone_match_key(record.phone)
        listing_url = clean_url(record.listing_url)

        aliases = []
        if listing_url:
            aliases.append(("listing_url", listing_url))
        if name and phone:
            aliases.append(("name_phone", name, phone))
        if name and record.region:
            aliases.append(("name_region", name, clean_text(record.region).lower()))
        if not aliases:
            aliases.append(("unique", name, clean_text(record.source_url)))

        primary_key = next((alias_to_primary[alias] for alias in aliases if alias in alias_to_primary), None)

        if primary_key is None:
            primary_key = aliases[0]
            ordered_primary_keys.append(primary_key)
            primary_records[primary_key] = record
            for alias in aliases:
                alias_to_primary[alias] = primary_key
            continue

        existing = primary_records[primary_key]
        if _completeness(record) > _completeness(existing):
            primary_records[primary_key] = record

        for alias in aliases:
            alias_to_primary[alias] = primary_key

    return [primary_records[key] for key in ordered_primary_keys]
