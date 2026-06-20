import asyncio

import httpx
import requests

from app.exporter import OUTPUT_FIELDS
from app.scraper import parse_business_listings
from app.scraper import (
    count_tradehq_listing_cards,
    enrich_records_with_detail_descriptions,
    enrich_records_with_detail_descriptions_async,
    extract_next_page_url,
    parse_detail_page,
    parse_trade_categories,
    parse_tradehq_directory_page,
    scrape_trade_category_pages,
)
from app.models import BusinessRecord


def test_parse_business_listings_uses_configurable_selectors():
    html = """
    <html>
      <body>
        <div class="directory-item">
          <h2>Example Builders NZ</h2>
          <span class="trade-category">Building</span>
          <a href="tel:+6495550101" class="phone">Call</a>
          <p class="description">Residential building services.</p>
        </div>
      </body>
    </html>
    """

    selectors = {
        "listing": ".directory-item",
        "business_name": "h2",
        "trade_category": ".trade-category",
        "phone": ".phone, a[href^='tel:']",
        "description": ".description",
    }
    records = parse_business_listings(
        html,
        "https://public-directory.example/builders",
        selectors=selectors,
    )

    assert len(records) == 1
    assert records[0].business_name == "Example Builders NZ"
    assert records[0].trade_category == "Building"
    assert records[0].phone == "+6495550101"
    assert isinstance(records[0].phone, str)
    assert records[0].description == "Residential building services."
    assert records[0].source_url == "https://public-directory.example/builders"


def test_parse_tradehq_directory_page_extracts_listing_fields():
    html = """
    <div id="listings">
      <div class="jet-listing-grid__item" data-post-id="1">
        <h3 class="elementor-heading-title">
          <a href="https://tradehq.co.nz/directory/example-builder/">Example Builder</a>
        </h3>
        <a href="https://tradehq.co.nz/location/auckland/">
          <span class="elementor-icon-list-text">Auckland</span>
        </a>
        <a href="tel:0800%20123%20456">
          <span class="elementor-icon-list-text">0800 123 456</span>
        </a>
        <a href="https://tradehq.co.nz/business-category/builders/" class="jet-listing-dynamic-terms__link">
          Builders
        </a>
        <div class="elementor-widget-theme-post-excerpt">
          <p>Residential building services.</p>
        </div>
      </div>
    </div>
    """

    assert count_tradehq_listing_cards(html) == 1
    records = parse_tradehq_directory_page(html, "https://tradehq.co.nz/directory/", limit=20)

    assert len(records) == 1
    assert records[0].business_name == "Example Builder"
    assert records[0].region == "Auckland"
    assert records[0].phone == "0800 123 456"
    assert records[0].trade_category == "Builders"
    assert records[0].description == "Residential building services."
    assert records[0].listing_url == "https://tradehq.co.nz/directory/example-builder/"


def test_trade_category_and_region_remain_separate_when_elements_are_adjacent():
    html = """
    <div id="listings">
      <div class="jet-listing-grid__item" data-post-id="2">
        <h3><a href="/directory/christchurch-electrician/">Christchurch Electrician</a></h3>
        <a href="/business-category/electricians/"
           class="jet-listing-dynamic-terms__link">Electricians</a><a
           href="/location/canterbury/"><span
           class="elementor-icon-list-text">Canterbury</span></a>
      </div>
    </div>
    """

    records = parse_tradehq_directory_page(
        html,
        "https://tradehq.co.nz/directory/",
    )

    assert records[0].trade_category == "Electricians"
    assert records[0].region == "Canterbury"
    assert records[0].trade_category != "ElectriciansCanterbury"


def test_parse_trade_categories_extracts_urls_and_optional_counts():
    html = """
    <div class="jet-listing-grid__item">
      <div class="jet-engine-listing-overlay-wrap"
           data-url="/business-category/electricians/">
        <h3 class="elementor-heading-title">
          <a href="/business-category/electricians/">Electricians</a>
        </h3>
        <div class="jet-listing-dynamic-field__content">(89)</div>
      </div>
    </div>
    <ul class="directory-service-list">
      <li><a href="/business-category/electricians/">Electricians</a></li>
      <li><a href="/business-category/plumbers/">Plumbers</a></li>
    </ul>
    """

    categories = parse_trade_categories(
        html,
        "https://tradehq.co.nz/directory/",
    )

    assert len(categories) == 2
    assert categories[0].trade_category == "Electricians"
    assert categories[0].category_url == (
        "https://tradehq.co.nz/business-category/electricians/"
    )
    assert categories[0].listed_count == 89
    assert categories[1].trade_category == "Plumbers"
    assert categories[1].listed_count is None


def test_extract_next_page_url_returns_absolute_wordpress_url():
    html = """
    <nav class="navigation pagination">
      <a class="next page-numbers" href="/business-category/electricians/page/2/">
        Next
      </a>
    </nav>
    """

    assert extract_next_page_url(
        html,
        "https://tradehq.co.nz/business-category/electricians/",
    ) == "https://tradehq.co.nz/business-category/electricians/page/2/"


def test_scrape_trade_category_pages_uses_category_as_source_url():
    category_url = "https://tradehq.co.nz/business-category/electricians/"
    listing_url = "https://tradehq.co.nz/directory/example-electrician/"
    category_html = f"""
    <div id="listings">
      <div class="jet-listing-grid__item" data-post-id="1">
        <h3 class="elementor-heading-title">
          <a href="{listing_url}">Example Electrician</a>
        </h3>
        <a href="/business-category/electricians/"
           class="jet-listing-dynamic-terms__link">Electricians</a>
        <a href="/location/auckland/">
          <span class="elementor-icon-list-text">Auckland</span>
        </a>
        <a href="tel:0800%20123%20456">0800 123 456</a>
        <div class="elementor-widget-theme-post-excerpt">
          <p>Short excerpt.</p>
        </div>
      </div>
    </div>
    """
    detail_html = """
    <div class="elementor-widget-theme-post-content">
      <div class="elementor-widget-container">Full description.</div>
    </div>
    """

    def fetcher(url):
        return category_html if url == category_url else detail_html

    async def detail_fetcher(_):
        return detail_html

    records, failures, metrics = scrape_trade_category_pages(
        [category_url],
        limit_per_category=10,
        fetcher=fetcher,
        async_detail_fetcher=detail_fetcher,
    )

    assert failures == []
    assert records[0].source_url == category_url
    assert records[0].listing_url == listing_url
    assert records[0].description == "Full description."
    assert list(records[0].model_dump().keys()) == OUTPUT_FIELDS
    assert metrics["categories_requested"] == 1
    assert metrics["category_pages_scraped"] == 1


def test_category_pagination_applies_total_limit_and_preserves_page_source():
    page_one_url = "https://tradehq.co.nz/business-category/electricians/"
    page_two_url = (
        "https://tradehq.co.nz/business-category/electricians/page/2/"
    )

    def category_page(start, next_url=None):
        cards = "".join(
            f"""
            <div class="jet-listing-grid__item" data-post-id="{index}">
              <h3 class="elementor-heading-title">
                <a href="/directory/business-{index}/">Business {index}</a>
              </h3>
              <a href="/business-category/electricians/"
                 class="jet-listing-dynamic-terms__link">Electricians</a>
            </div>
            """
            for index in range(start, start + 2)
        )
        next_link = (
            f'<a rel="next" href="{next_url}">Next</a>'
            if next_url
            else ""
        )
        return f'<div id="listings">{cards}</div>{next_link}'

    pages = {
        page_one_url: category_page(1, page_two_url),
        page_two_url: category_page(3),
    }
    detail_html = """
    <div class="elementor-widget-theme-post-content">
      <div class="elementor-widget-container">Full description.</div>
    </div>
    """

    records, failures, metrics = scrape_trade_category_pages(
        [page_one_url],
        limit_per_category=3,
        max_pages_per_category=2,
        fetcher=lambda url: pages.get(url, detail_html),
        async_detail_fetcher=lambda _: asyncio.sleep(0, result=detail_html),
    )

    assert failures == []
    assert len(records) == 3
    assert records[0].source_url == page_one_url
    assert records[1].source_url == page_one_url
    assert records[2].source_url == page_two_url
    assert metrics["category_pages_scraped"] == 2
    assert metrics["detail_pages_requested"] == 3


def test_scrape_trade_category_pages_reports_failed_category_url():
    category_url = "https://tradehq.co.nz/business-category/broken/"

    def failing_fetcher(_):
        raise requests.Timeout("Category page timed out")

    records, failures, metrics = scrape_trade_category_pages(
        [category_url],
        limit_per_category=10,
        fetcher=failing_fetcher,
    )

    assert records == []
    assert failures[0].url == category_url
    assert failures[0].error_type == "Timeout"
    assert metrics["category_pages_scraped"] == 0


def test_parse_detail_page_extracts_full_post_content():
    html = """
    <div class="elementor-widget-theme-post-content">
      <div class="elementor-widget-container">
        <p>First full-description paragraph.</p>
        <p>Second paragraph with the remaining business details.</p>
      </div>
    </div>
    """

    assert parse_detail_page(html) == (
        "First full-description paragraph. "
        "Second paragraph with the remaining business details."
    )


def test_parse_detail_page_cleans_nested_element_boundaries_and_punctuation():
    html = """
    <div class="elementor-widget-theme-post-content">
      <div class="elementor-widget-container">
        <p>No shortcuts, no <strong>guesswork</strong>.</p>
        <p>Honest pricing,quality workmanship.</p>
        <p>Professional <strong>removalists</strong> , providing support.</p>
      </div>
    </div>
    """

    description = parse_detail_page(html)

    assert description == (
        "No shortcuts, no guesswork. Honest pricing, quality workmanship. "
        "Professional removalists, providing support."
    )
    assert " ," not in description
    assert ",quality" not in description


def test_detail_description_replaces_listing_excerpt():
    record = BusinessRecord(
        business_name="Example Mover",
        trade_category="Movers",
        region="Auckland",
        phone="0800 123 456",
        description="Short listing excerpt that ends",
        listing_url="https://directory.example/example-mover",
        source_url="https://directory.example/",
    )
    detail_html = """
    <div class="elementor-widget-theme-post-content">
      <div class="elementor-widget-container">
        Full detail-page description with complete service information.
      </div>
    </div>
    """

    records, failures, metrics = enrich_records_with_detail_descriptions(
        [record],
        fetcher=lambda _: detail_html,
    )

    assert records[0].description == (
        "Full detail-page description with complete service information."
    )
    assert failures == []
    assert metrics["detail_pages_requested"] == 1
    assert metrics["detail_pages_successful"] == 1
    assert metrics["descriptions_from_detail_page"] == 1
    assert metrics["descriptions_fallback_to_listing_excerpt"] == 0


def test_missing_detail_description_falls_back_to_listing_excerpt():
    excerpt = "Directory-page excerpt."
    record = BusinessRecord(
        business_name="Example Electrician",
        description=excerpt,
        listing_url="https://directory.example/example-electrician",
        source_url="https://directory.example/",
    )

    records, failures, metrics = enrich_records_with_detail_descriptions(
        [record],
        fetcher=lambda _: "<html><body>No post content here.</body></html>",
    )

    assert records[0].description == excerpt
    assert failures[0].url == record.listing_url
    assert failures[0].error_type == "DescriptionNotFound"
    assert metrics["detail_pages_requested"] == 1
    assert metrics["detail_pages_failed"] == 1
    assert metrics["descriptions_fallback_to_listing_excerpt"] == 1


def test_detail_request_failure_falls_back_and_records_failed_url():
    record = BusinessRecord(
        business_name="Example Plumber",
        description="Listing excerpt.",
        listing_url="https://directory.example/example-plumber",
        source_url="https://directory.example/",
    )

    def failing_fetcher(_: str) -> str:
        raise requests.Timeout("Detail page timed out")

    records, failures, metrics = enrich_records_with_detail_descriptions(
        [record],
        fetcher=failing_fetcher,
    )

    assert records[0].description == "Listing excerpt."
    assert failures[0].error_type == "Timeout"
    assert metrics["detail_pages_failed"] == 1


def test_async_detail_enrichment_preserves_order_and_fallback():
    records = [
        BusinessRecord(
            business_name=f"Business {index}",
            description=f"Excerpt {index}",
            listing_url=f"https://directory.example/business-{index}",
            source_url="https://directory.example/category",
        )
        for index in range(1, 4)
    ]

    async def fetcher(url):
        index = int(url.rsplit("-", 1)[-1])
        await asyncio.sleep((4 - index) * 0.01)
        if index == 3:
            request = httpx.Request("GET", url)
            raise httpx.ReadTimeout("Timed out", request=request)
        return f"""
        <div class="elementor-widget-theme-post-content">
          <div class="elementor-widget-container">
            Full description {index}.
          </div>
        </div>
        """

    enriched, failures, metrics = asyncio.run(
        enrich_records_with_detail_descriptions_async(
            records,
            concurrency=2,
            async_fetcher=fetcher,
        )
    )

    assert [record.business_name for record in enriched] == [
        "Business 1",
        "Business 2",
        "Business 3",
    ]
    assert enriched[0].description == "Full description 1."
    assert enriched[1].description == "Full description 2."
    assert enriched[2].description == "Excerpt 3"
    assert failures[0].url == records[2].listing_url
    assert metrics["detail_concurrency"] == 2
    assert metrics["detail_pages_successful"] == 2
    assert metrics["detail_pages_failed"] == 1
