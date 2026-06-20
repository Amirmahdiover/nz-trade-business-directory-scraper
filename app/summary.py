"""Data-quality summary helpers."""

from datetime import datetime, timezone
from typing import Iterable

from app.models import BusinessRecord, FailedURL


def build_summary(
    raw_records: Iterable[BusinessRecord],
    clean_records: Iterable[BusinessRecord],
    failed_urls: Iterable[FailedURL] = (),
    output_files: Iterable[str] = (),
    detail_metrics: dict | None = None,
    category_metrics: dict | None = None,
) -> dict:
    """Build the JSON summary payload."""

    raw_list = list(raw_records)
    clean_list = list(clean_records)
    failed_list = list(failed_urls)
    detail_metrics = detail_metrics or {}
    category_metrics = category_metrics or {}

    summary = {
        "total_raw_records": len(raw_list),
        "total_records_scraped": len(raw_list),
        "duplicates_removed": len(raw_list) - len(clean_list),
        "final_records": len(clean_list),
        "missing_business_name": sum(
            1 for record in clean_list if not record.business_name
        ),
        "missing_trade_category": sum(
            1 for record in clean_list if not record.trade_category
        ),
        "missing_region": sum(1 for record in clean_list if not record.region),
        "missing_phone": sum(1 for record in clean_list if not record.phone),
        "missing_description": sum(
            1 for record in clean_list if not record.description
        ),
        "failed_urls_count": len(failed_list),
        "output_files": list(output_files),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary.update(
        {
            "detail_pages_requested": detail_metrics.get(
                "detail_pages_requested", 0
            ),
            "detail_concurrency": detail_metrics.get("detail_concurrency", 1),
            "detail_pages_successful": detail_metrics.get(
                "detail_pages_successful", 0
            ),
            "detail_pages_failed": detail_metrics.get("detail_pages_failed", 0),
            "descriptions_from_detail_page": detail_metrics.get(
                "descriptions_from_detail_page", 0
            ),
            "descriptions_fallback_to_listing_excerpt": detail_metrics.get(
                "descriptions_fallback_to_listing_excerpt", 0
            ),
        }
    )
    summary.update(
        {
            "categories_discovered": category_metrics.get(
                "categories_discovered", 0
            ),
            "categories_requested": category_metrics.get(
                "categories_requested", 0
            ),
            "category_pages_scraped": category_metrics.get(
                "category_pages_scraped", 0
            ),
        }
    )
    return summary
