"""Command-line entry point for the NZ trade business directory pipeline."""

import argparse
import logging
import re
from urllib.parse import urljoin, urlparse

import requests

from app.cleaner import clean_business_record, deduplicate_records
from app.config import (
    CSV_OUTPUT_PATH,
    DEFAULT_CATEGORY_LIMIT,
    DEFAULT_SCRAPE_LIMIT,
    EXCEL_OUTPUT_PATH,
    FAILED_URLS_OUTPUT_PATH,
    SUMMARY_OUTPUT_PATH,
    TRADEHQ_RAW_HTML_PATH,
    TRADEHQ_TARGET_URL,
    TRADE_CATEGORIES_OUTPUT_PATH,
)
from app.exporter import (
    export_failed_urls,
    export_records,
    export_trade_categories,
)
from app.models import BusinessRecord, FailedURL, TradeCategory
from app.scraper import (
    count_tradehq_listing_cards,
    enrich_records_with_detail_descriptions,
    fetch_page,
    parse_trade_categories,
    parse_tradehq_directory_page,
    scrape_trade_category_pages,
)
from app.summary import build_summary
from app.utils import ensure_directory, setup_logging

logger = logging.getLogger(__name__)


def generate_sample_records() -> list[BusinessRecord]:
    """Generate messy sample/test records for pipeline verification only."""

    source = "https://sample-data.local/nz-trade-directory"
    sample_note = "SAMPLE/TEST DATA - for pipeline demonstration only."
    return [
        BusinessRecord(
            business_name="  Auckland Plumbing Pros Ltd ",
            trade_category=" Plumbing ",
            region="Auckland",
            phone="(09) 555 0123",
            listing_url="https://sample-data.local/nz-trade-directory/auckland-plumbing-pros",
            source_url=source,
            description=" Residential and commercial plumbing services. ",
        ),
        BusinessRecord(
            business_name="Auckland Plumbing Pros",
            trade_category="Plumbing",
            region="Auckland",
            phone="+64 9 555 0123",
            listing_url="https://sample-data.local/nz-trade-directory/auckland-plumbing-pros-duplicate",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Wellington Electrical Services",
            trade_category="Electrical",
            region="Wellington",
            phone="04 555 7788",
            listing_url="https://sample-data.local/nz-trade-directory/wellington-electrical-services",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Christchurch Roofing Co.",
            trade_category="Roofing",
            region="Canterbury",
            phone="03-555-3344",
            listing_url="https://sample-data.local/nz-trade-directory/christchurch-roofing",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Hamilton Heat Pumps",
            trade_category="HVAC",
            region="Waikato",
            phone="07 555 9001",
            listing_url="https://sample-data.local/nz-trade-directory/hamilton-heat-pumps",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Dunedin Joinery Workshop",
            trade_category="Joinery",
            region="Otago",
            phone="03 555 7781",
            listing_url="https://sample-data.local/nz-trade-directory/dunedin-joinery-workshop",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Tauranga Concrete & Paving",
            trade_category="Concrete",
            region="Bay of Plenty",
            phone="027 555 6600",
            listing_url="https://sample-data.local/nz-trade-directory/tauranga-concrete-paving",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Napier Painting Specialists",
            trade_category="Painting",
            region="Hawke's Bay",
            phone="06 555 5510",
            listing_url="https://sample-data.local/nz-trade-directory/napier-painting-specialists",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Nelson Glass Repair",
            trade_category="Glazing",
            region="Nelson",
            phone="03 555 1188",
            listing_url="https://sample-data.local/nz-trade-directory/nelson-glass-repair",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Rotorua Landscaping",
            trade_category="Landscaping",
            region="Bay of Plenty",
            phone="07 555 2020",
            listing_url="https://sample-data.local/nz-trade-directory/rotorua-landscaping",
            source_url=source,
            description=sample_note,
        ),
        BusinessRecord(
            business_name="Rotorua Landscaping ",
            trade_category=" Landscaping",
            region="Bay of Plenty",
            phone="+64 7 555 2020",
            listing_url="https://sample-data.local/nz-trade-directory/rotorua-landscaping-duplicate",
            source_url=source,
            description=f"{sample_note} Duplicate by name + phone.",
        ),
        BusinessRecord(
            business_name="Queenstown Builders Group",
            trade_category="Building",
            region="Otago",
            phone="03 555 8100",
            listing_url="https://sample-data.local/nz-trade-directory/queenstown-builders-group",
            source_url=source,
            description=sample_note,
        ),
    ]


def normalize_cli_url(url: str) -> str:
    """Accept plain URLs and common Markdown link formatting from copied text."""

    value = url.strip()
    markdown_match = re.search(r"\((https?://[^)]+)\)", value)
    if markdown_match:
        value = markdown_match.group(1)
    return value.strip("\"'")


def validate_public_url(url: str) -> str:
    """Validate that scrape mode received an HTTP(S) URL."""

    normalized = normalize_cli_url(url)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Scrape mode requires a valid public http(s) URL.")
    return normalized


def save_debug_html(html: str) -> None:
    """Save the first fetched TradeHQ page for selector debugging."""

    ensure_directory(TRADEHQ_RAW_HTML_PATH.parent)
    TRADEHQ_RAW_HTML_PATH.write_text(html, encoding="utf-8")


def scrape_records(
    url: str, limit: int = DEFAULT_SCRAPE_LIMIT, debug: bool = False
) -> tuple[list[BusinessRecord], list[FailedURL], dict]:
    """Fetch and parse records from one public directory page."""

    session = requests.Session()
    try:
        html = fetch_page(url, session=session)
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        failed_url = FailedURL(
            url=url,
            error_type=type(exc).__name__,
            error_message=str(exc),
            status_code=getattr(response, "status_code", None),
        )
        logger.error("Failed to fetch %s: %s", url, exc)
        return [], [failed_url], {}

    card_count = count_tradehq_listing_cards(html)

    if debug:
        save_debug_html(html)
        print(f"Debug: saved raw HTML to {TRADEHQ_RAW_HTML_PATH}")
        print(f"Debug: found {card_count} TradeHQ listing card(s) before parsing.")

    card_records = parse_tradehq_directory_page(
        html,
        source_url=url,
        limit=limit,
    )
    enriched_records, detail_failures, detail_metrics = (
        enrich_records_with_detail_descriptions(
            card_records,
            fetcher=lambda listing_url: fetch_page(
                listing_url,
                session=session,
            ),
        )
    )
    return enriched_records, detail_failures, detail_metrics


def discover_categories(
    url: str,
    session: requests.Session | None = None,
) -> tuple[list[TradeCategory], list[FailedURL]]:
    """Fetch the directory page and discover available trade categories."""

    session = session or requests.Session()
    try:
        html = fetch_page(url, session=session)
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        return [], [
            FailedURL(
                url=url,
                error_type=type(exc).__name__,
                error_message=str(exc),
                status_code=getattr(response, "status_code", None),
            )
        ]
    return parse_trade_categories(html, source_url=url), []


def parse_requested_categories(value: str) -> list[str]:
    """Parse a comma-separated list of category slugs or URLs."""

    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_category_urls(
    requested: list[str],
    discovered: list[TradeCategory],
    directory_url: str,
) -> tuple[list[str], list[FailedURL]]:
    """Resolve explicit category slugs/URLs without selecting every category."""

    discovered_by_slug = {
        urlparse(category.category_url).path.rstrip("/").split("/")[-1].lower():
        category.category_url
        for category in discovered
    }
    category_urls: list[str] = []
    failures: list[FailedURL] = []

    for item in requested:
        if item.lower().startswith(("http://", "https://")):
            try:
                category_url = validate_public_url(item)
            except ValueError as exc:
                failures.append(
                    FailedURL(
                        url=item,
                        error_type="InvalidCategoryURL",
                        error_message=str(exc),
                    )
                )
                continue
            if "/business-category/" not in urlparse(category_url).path:
                failures.append(
                    FailedURL(
                        url=category_url,
                        error_type="InvalidCategoryURL",
                        error_message=(
                            "The supplied URL is not a TradeHQ business "
                            "category URL."
                        ),
                    )
                )
                continue
            category_urls.append(category_url)
            continue

        slug = item.strip().strip("/").lower()
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            failures.append(
                FailedURL(
                    url=item,
                    error_type="InvalidCategory",
                    error_message=(
                        "Category values must be TradeHQ category slugs or "
                        "public HTTP(S) category URLs."
                    ),
                )
            )
            continue

        category_url = discovered_by_slug.get(slug)
        if not category_url:
            failures.append(
                FailedURL(
                    url=urljoin(directory_url, f"/business-category/{slug}/"),
                    error_type="CategoryNotDiscovered",
                    error_message=(
                        f"The requested category slug '{slug}' was not found "
                        "on the supplied directory page."
                    ),
                )
            )
            continue
        category_urls.append(category_url)

    return list(dict.fromkeys(category_urls)), failures


def scrape_selected_categories(
    directory_url: str,
    requested_categories: list[str],
    limit_per_category: int,
    max_pages_per_category: int = 1,
    detail_concurrency: int = 3,
) -> tuple[list[BusinessRecord], list[FailedURL], dict, dict]:
    """Discover and scrape only explicitly requested TradeHQ categories."""

    session = requests.Session()
    discovered, discovery_failures = discover_categories(
        directory_url,
        session=session,
    )
    category_urls, resolution_failures = resolve_category_urls(
        requested_categories,
        discovered,
        directory_url,
    )

    records, scrape_failures, scrape_metrics = scrape_trade_category_pages(
        category_urls,
        limit_per_category=limit_per_category,
        fetcher=lambda target_url: fetch_page(target_url, session=session),
        max_pages_per_category=max_pages_per_category,
        detail_concurrency=detail_concurrency,
    )
    scrape_metrics["categories_requested"] = len(requested_categories)
    category_metrics = {
        "categories_discovered": len(discovered),
        "categories_requested": len(requested_categories),
        "category_pages_scraped": scrape_metrics["category_pages_scraped"],
    }
    failures = discovery_failures + resolution_failures + scrape_failures
    return records, failures, scrape_metrics, category_metrics


def run_pipeline(
    raw_records: list[BusinessRecord],
    failed_urls: list[FailedURL] | None = None,
    detail_metrics: dict | None = None,
    category_metrics: dict | None = None,
) -> dict:
    """Clean, deduplicate, score, summarize, and export records."""

    failed_urls = failed_urls or []
    cleaned_records = [clean_business_record(record) for record in raw_records]
    deduplicated_records = deduplicate_records(cleaned_records)
    output_files = [
        f"outputs/{path.name}"
        for path in (
            CSV_OUTPUT_PATH,
            EXCEL_OUTPUT_PATH,
            SUMMARY_OUTPUT_PATH,
            FAILED_URLS_OUTPUT_PATH,
        )
    ]
    summary = build_summary(
        raw_records,
        deduplicated_records,
        failed_urls=failed_urls,
        output_files=output_files,
        detail_metrics=detail_metrics,
        category_metrics=category_metrics,
    )
    export_records(deduplicated_records, summary, failed_urls=failed_urls)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean and export public NZ trade/business directory records."
    )
    parser.add_argument(
        "--mode",
        choices=[
            "sample",
            "scrape",
            "discover-categories",
            "scrape-categories",
        ],
        required=True,
        help=(
            "Run sample data, scrape one directory page, discover categories, "
            "or scrape explicitly selected categories."
        ),
    )
    parser.add_argument(
        "--url",
        help=(
            "Directory URL required for scrape and category modes. "
            f"TradeHQ target: {TRADEHQ_TARGET_URL}"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_SCRAPE_LIMIT,
        help="Maximum number of records to parse in scrape mode.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save raw TradeHQ HTML and print listing-card count before parsing.",
    )
    parser.add_argument(
        "--categories",
        help=(
            "Comma-separated TradeHQ category slugs or URLs. Required for "
            "scrape-categories; no categories are selected automatically."
        ),
    )
    parser.add_argument(
        "--limit-per-category",
        type=int,
        default=DEFAULT_CATEGORY_LIMIT,
        help=(
            "Maximum listings per selected category "
            f"(default: {DEFAULT_CATEGORY_LIMIT})."
        ),
    )
    parser.add_argument(
        "--max-pages-per-category",
        type=int,
        default=1,
        help=(
            "Maximum category pages to scrape per selected category "
            "(default: 1; use 0 for unlimited pages)."
        ),
    )
    parser.add_argument(
        "--detail-concurrency",
        type=int,
        default=3,
        help=(
            "Maximum concurrent detail-page requests "
            "(default: 3; use 1 for sequential compatibility mode)."
        ),
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()

    if args.mode == "sample":
        logger.info("Running sample/test mode")
        print("Running SAMPLE/TEST mode. Generated records are not real scraped data.")
        raw_records = generate_sample_records()
        failed_urls = []
        detail_metrics = {}
        category_metrics = {}
    elif args.mode == "discover-categories":
        if not args.url:
            raise SystemExit(
                "Error: --url is required when --mode discover-categories is used."
            )
        try:
            url = validate_public_url(args.url)
        except ValueError as exc:
            raise SystemExit(f"Error: {exc}") from exc
        categories, failed_urls = discover_categories(url)
        export_trade_categories(categories)
        export_failed_urls(failed_urls)
        print(f"Discovered categories: {len(categories)}")
        print(f"Categories CSV: {TRADE_CATEGORIES_OUTPUT_PATH}")
        print(f"Failed URLs: {FAILED_URLS_OUTPUT_PATH}")
        return
    elif args.mode == "scrape-categories":
        if not args.url:
            raise SystemExit(
                "Error: --url is required when --mode scrape-categories is used."
            )
        if not args.categories:
            raise SystemExit(
                "Error: --categories is required for scrape-categories. "
                "No categories are scraped automatically."
            )
        if args.limit_per_category < 1:
            raise SystemExit("Error: --limit-per-category must be greater than 0.")
        if args.max_pages_per_category < 0:
            raise SystemExit(
                "Error: --max-pages-per-category cannot be negative."
            )
        if args.detail_concurrency < 1:
            raise SystemExit("Error: --detail-concurrency must be at least 1.")
        try:
            url = validate_public_url(args.url)
        except ValueError as exc:
            raise SystemExit(f"Error: {exc}") from exc
        requested_categories = parse_requested_categories(args.categories)
        if not requested_categories:
            raise SystemExit("Error: provide at least one category slug or URL.")
        print(
            "Running SELECTED CATEGORY scrape for: "
            f"{', '.join(requested_categories)}"
        )
        raw_records, failed_urls, detail_metrics, category_metrics = (
            scrape_selected_categories(
                url,
                requested_categories=requested_categories,
                limit_per_category=args.limit_per_category,
                max_pages_per_category=args.max_pages_per_category,
                detail_concurrency=args.detail_concurrency,
            )
        )
    else:
        if not args.url:
            raise SystemExit("Error: --url is required when --mode scrape is used.")
        if args.limit < 1:
            raise SystemExit("Error: --limit must be greater than 0.")
        try:
            url = validate_public_url(args.url)
        except ValueError as exc:
            raise SystemExit(f"Error: {exc}") from exc
        logger.info("Running scrape mode for %s", url)
        print(f"Running SCRAPE mode for public TradeHQ URL: {url}")
        raw_records, failed_urls, detail_metrics = scrape_records(
            url, limit=args.limit, debug=args.debug
        )
        category_metrics = {}

    summary = run_pipeline(
        raw_records,
        failed_urls,
        detail_metrics,
        category_metrics,
    )

    print("\nNZ trade business directory pipeline complete")
    print(f"Mode: {args.mode}")
    if args.mode == "scrape":
        print(f"Limit: {args.limit}")
    elif args.mode == "scrape-categories":
        print(f"Categories requested: {summary['categories_requested']}")
        print(f"Category pages scraped: {summary['category_pages_scraped']}")
        print(f"Limit per category: {args.limit_per_category}")
        print(f"Max pages per category: {args.max_pages_per_category}")
        print(f"Detail concurrency: {summary['detail_concurrency']}")
    print(f"Records scraped: {summary['total_records_scraped']}")
    print(f"Final records: {summary['final_records']}")
    print(f"Duplicates removed: {summary['duplicates_removed']}")
    if args.mode in {"scrape", "scrape-categories"}:
        print(
            "Detail descriptions: "
            f"{summary['descriptions_from_detail_page']} full, "
            f"{summary['descriptions_fallback_to_listing_excerpt']} fallback"
        )
    print(f"Excel: {EXCEL_OUTPUT_PATH}")
    print(f"CSV: {CSV_OUTPUT_PATH}")
    print(f"Summary JSON: {SUMMARY_OUTPUT_PATH}")
    print(f"Failed URLs: {FAILED_URLS_OUTPUT_PATH}")

    if args.mode in {"scrape", "scrape-categories"} and summary["total_raw_records"] == 0:
        print("No records were parsed. Check app/config.py selectors for the target website.")


if __name__ == "__main__":
    main()
