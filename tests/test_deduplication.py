from app.cleaner import clean_business_record, deduplicate_records
from app.models import BusinessRecord


def test_deduplicate_records_prefers_listing_url():
    records = [
        BusinessRecord(
            business_name="Auckland Plumbing Pros",
            phone="09 555 0123",
            listing_url="https://directory.example/auckland-plumbing/",
            source_url="https://directory.example/a",
        ),
        BusinessRecord(
            business_name="Auckland Plumbing Pros Ltd",
            phone="+64 9 555 0123",
            trade_category="Plumbing",
            listing_url="https://directory.example/auckland-plumbing/",
            source_url="https://directory.example/b",
        ),
    ]

    cleaned = [clean_business_record(record) for record in records]
    unique = deduplicate_records(cleaned)

    assert len(unique) == 1
    assert unique[0].trade_category == "Plumbing"


def test_deduplicate_records_uses_name_phone_fallback():
    records = [
        BusinessRecord(
            business_name="Rotorua Landscaping",
            phone="07 555 2020",
            source_url="https://directory.example/a",
        ),
        BusinessRecord(
            business_name="  Rotorua   Landscaping ",
            phone="+64 7 555 2020",
            trade_category="Landscaping",
            source_url="https://directory.example/b",
        ),
        BusinessRecord(
            business_name="Rotorua Landscaping",
            phone="07 555 9999",
            source_url="https://directory.example/c",
        ),
    ]

    cleaned = [clean_business_record(record) for record in records]
    unique = deduplicate_records(cleaned)

    assert len(unique) == 2
    assert unique[0].trade_category == "Landscaping"


def test_deduplicate_records_matches_name_and_phone():
    records = [
        BusinessRecord(
            business_name="Nelson Glass Repair",
            phone="03 555 1188",
            source_url="https://directory.example/a",
        ),
        BusinessRecord(
            business_name="Nelson Glass Repair",
            phone="+64 3 555 1188",
            source_url="https://directory.example/b",
        ),
    ]

    cleaned = [clean_business_record(record) for record in records]
    unique = deduplicate_records(cleaned)

    assert len(unique) == 1
    assert unique[0].business_name == "Nelson Glass Repair"


def test_deduplicate_records_across_category_source_pages_by_listing_url():
    listing_url = "https://tradehq.co.nz/directory/shared-business/"
    records = [
        BusinessRecord(
            business_name="Shared Trade Business",
            trade_category="Electricians",
            listing_url=listing_url,
            source_url=(
                "https://tradehq.co.nz/business-category/electricians/"
            ),
        ),
        BusinessRecord(
            business_name="Shared Trade Business",
            trade_category="Builders",
            listing_url=listing_url,
            source_url="https://tradehq.co.nz/business-category/builders/",
        ),
    ]

    unique = deduplicate_records(
        [clean_business_record(record) for record in records]
    )

    assert len(unique) == 1
    assert unique[0].listing_url == listing_url.rstrip("/")
