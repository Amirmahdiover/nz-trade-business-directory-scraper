from app.models import BusinessRecord, FailedURL
from app.summary import build_summary


def test_summary_counts_missing_fields_duplicates_and_failed_urls():
    raw_records = [
        BusinessRecord(
            business_name="Example Builder",
            trade_category="Building",
            region="Auckland",
            phone="09 555 1111",
            description="Residential work.",
            source_url="https://directory.example/",
        ),
        BusinessRecord(
            business_name="Example Builder",
            source_url="https://directory.example/",
        ),
    ]
    final_records = [raw_records[1]]
    failed_urls = [
        FailedURL(
            url="https://directory.example/broken",
            error_type="Timeout",
            error_message="Timed out",
        )
    ]

    summary = build_summary(
        raw_records,
        final_records,
        failed_urls=failed_urls,
        output_files=["outputs/records.csv"],
        detail_metrics={
            "detail_concurrency": 3,
            "detail_pages_requested": 2,
            "detail_pages_successful": 1,
            "detail_pages_failed": 1,
            "descriptions_from_detail_page": 1,
            "descriptions_fallback_to_listing_excerpt": 1,
        },
        category_metrics={
            "categories_discovered": 64,
            "categories_requested": 3,
            "category_pages_scraped": 2,
        },
    )

    assert summary["total_records_scraped"] == 2
    assert summary["duplicates_removed"] == 1
    assert summary["final_records"] == 1
    assert summary["missing_business_name"] == 0
    assert summary["missing_trade_category"] == 1
    assert summary["missing_region"] == 1
    assert summary["missing_phone"] == 1
    assert summary["missing_description"] == 1
    assert summary["failed_urls_count"] == 1
    assert summary["output_files"] == ["outputs/records.csv"]
    assert summary["detail_pages_requested"] == 2
    assert summary["detail_concurrency"] == 3
    assert summary["detail_pages_successful"] == 1
    assert summary["detail_pages_failed"] == 1
    assert summary["descriptions_from_detail_page"] == 1
    assert summary["descriptions_fallback_to_listing_excerpt"] == 1
    assert summary["total_raw_records"] == 2
    assert summary["categories_discovered"] == 64
    assert summary["categories_requested"] == 3
    assert summary["category_pages_scraped"] == 2
