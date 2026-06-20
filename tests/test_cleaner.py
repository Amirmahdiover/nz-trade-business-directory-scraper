import pytest
from pydantic import ValidationError

from app.cleaner import (
    clean_business_record,
    clean_display_text,
    clean_phone,
    clean_text,
    clean_url,
    phone_match_key,
)
from app.models import BusinessRecord


def test_clean_text_normalizes_whitespace():
    assert clean_text("  Auckland   Plumbing\nPros  ") == "Auckland Plumbing Pros"
    assert clean_text("   ") is None
    assert clean_text(None) is None


def test_clean_display_text_normalizes_spacing_and_punctuation():
    assert clean_display_text("professional removalists , providing") == (
        "professional removalists, providing"
    )
    assert clean_display_text("pricing,quality workmanship") == (
        "pricing, quality workmanship"
    )
    assert clean_display_text("multiple   spaces\nbecome one") == (
        "multiple spaces become one"
    )


def test_clean_display_text_preserves_urls_and_emails():
    text = "Visit https://example.co.nz/path?a=1,b=2 or email hello@example.co.nz."
    assert clean_display_text(text) == text


def test_clean_phone_normalizes_new_zealand_numbers():
    assert clean_phone("(09) 555 0123") == "(09) 555 0123"
    assert clean_phone("+64 21 555 123") == "+64 21 555 123"
    assert clean_phone("0800 123 456") == "0800 123 456"
    assert clean_phone("tel:+64 4 555 1111") == "+64 4 555 1111"
    assert clean_phone("") is None


def test_phone_rejects_numeric_types_and_scientific_notation():
    with pytest.raises(ValidationError):
        BusinessRecord(
            business_name="Example",
            phone=64800555207,
            source_url="https://directory.example/",
        )

    with pytest.raises(TypeError):
        clean_phone(64800555207)

    with pytest.raises(ValueError):
        clean_phone("6.480056e+10")


def test_phone_match_key_is_string_only_and_keeps_nz_formats_comparable():
    assert phone_match_key("07 555 2020") == "075552020"
    assert phone_match_key("+64 7 555 2020") == "075552020"
    assert isinstance(phone_match_key("+64 7 555 2020"), str)


def test_clean_url_normalizes_directory_url():
    cleaned = clean_url(" TradeHQ.co.nz/directory/example/?ref=directory ")
    assert cleaned == "https://tradehq.co.nz/directory/example?ref=directory"


def test_clean_business_record_normalizes_expected_fields():
    record = BusinessRecord(
        business_name="  Example   Builder ",
        trade_category=" Building ",
        region=" Auckland ",
        phone="09 555 1111",
        description=" Honest pricing,quality workmanship . ",
        listing_url="directory.example/listing/example",
        source_url="https://directory.example/listing/",
    )
    cleaned = clean_business_record(record)

    assert cleaned.business_name == "Example Builder"
    assert cleaned.trade_category == "Building"
    assert cleaned.region == "Auckland"
    assert cleaned.phone == "09 555 1111"
    assert isinstance(cleaned.phone, str)
    assert cleaned.description == "Honest pricing, quality workmanship."
