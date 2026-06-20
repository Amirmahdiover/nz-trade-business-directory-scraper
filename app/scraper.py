"""Reusable HTTP and parsing helpers for public business directories."""

import asyncio
import logging
import re
from typing import Awaitable, Callable, Dict, Iterable, List, Optional
from urllib.parse import unquote, urljoin

import httpx
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

from app.config import (
    DETAIL_DESCRIPTION_SELECTOR,
    REQUEST_TIMEOUT_SECONDS,
    SCRAPER_SELECTORS,
    USER_AGENT,
)
from app.cleaner import clean_display_text
from app.models import BusinessRecord, FailedURL, TradeCategory
from app.utils import model_to_dict

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True)
def fetch_page(
    url: str,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    session: Optional[requests.Session] = None,
) -> str:
    """Fetch a public page politely using requests."""

    headers = {"User-Agent": USER_AGENT}
    logger.info("Fetching page: %s", url)
    client = session or requests
    response = client.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _select_text(parent, selector: str) -> Optional[str]:
    element = parent.select_one(selector)
    if not element:
        return None
    return clean_display_text(element.get_text(separator=" ", strip=True))


def _select_href(parent, selector: str, source_url: str) -> Optional[str]:
    element = parent.select_one(selector)
    href = element.get("href") if element else None
    return urljoin(source_url, href) if href else None


def _select_phone(parent, selector: str) -> Optional[str]:
    element = parent.select_one(selector)
    if not element:
        return None

    text = element.get_text(" ", strip=True)
    if text:
        return text

    href = element.get("href")
    if href and href.lower().startswith("tel:"):
        return str(unquote(href[4:]))
    return None


def count_tradehq_listing_cards(html: str, selectors: Optional[Dict[str, str]] = None) -> int:
    """Count TradeHQ business listing cards before parsing."""

    selectors = {**SCRAPER_SELECTORS, **(selectors or {})}
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.select(selectors["listing"]))


def parse_trade_categories(
    html: str,
    source_url: str,
) -> list[TradeCategory]:
    """Extract unique TradeHQ category names, URLs, and optional listing counts."""

    soup = BeautifulSoup(html, "html.parser")
    categories_by_url: dict[str, TradeCategory] = {}

    for link in soup.select("a[href*='/business-category/']"):
        category_url = urljoin(source_url, link.get("href", ""))
        trade_category = clean_display_text(
            link.get_text(separator=" ", strip=True)
        )
        if not category_url or not trade_category:
            continue
        categories_by_url.setdefault(
            category_url,
            TradeCategory(
                trade_category=trade_category,
                category_url=category_url,
            ),
        )

    category_cards = soup.select(
        ".jet-listing-grid__item "
        ".jet-engine-listing-overlay-wrap[data-url*='/business-category/']"
    )
    for card in category_cards:
        category_url = urljoin(source_url, card.get("data-url", ""))
        name_element = card.select_one(
            "h1 a[href*='/business-category/'], "
            "h2 a[href*='/business-category/'], "
            "h3 a[href*='/business-category/'], "
            "h4 a[href*='/business-category/'], "
            "h5 a[href*='/business-category/'], "
            "h6 a[href*='/business-category/'], "
            ".elementor-heading-title a[href*='/business-category/']"
        )
        if not category_url or not name_element:
            continue

        trade_category = clean_display_text(
            name_element.get_text(separator=" ", strip=True)
        )
        if not trade_category:
            continue

        count_element = card.select_one(".jet-listing-dynamic-field__content")
        count_match = re.search(
            r"\(([\d,]+)\)",
            count_element.get_text(" ", strip=True) if count_element else "",
        )
        listed_count = (
            int(count_match.group(1).replace(",", ""))
            if count_match
            else None
        )
        categories_by_url[category_url] = TradeCategory(
            trade_category=trade_category,
            category_url=category_url,
            listed_count=listed_count,
        )

    return sorted(
        categories_by_url.values(),
        key=lambda category: category.trade_category.casefold(),
    )


def extract_next_page_url(html: str, current_url: str) -> Optional[str]:
    """Return the next WordPress-style pagination URL, if one exists."""

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all(["a", "link"], href=True)

    for link in links:
        rel_values = link.get("rel", [])
        if isinstance(rel_values, str):
            rel_values = rel_values.split()
        if any(str(value).casefold() == "next" for value in rel_values):
            return urljoin(current_url, link["href"])

    for link in soup.find_all("a", href=True):
        classes = " ".join(link.get("class", [])).casefold()
        if "next" in classes:
            return urljoin(current_url, link["href"])

    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True).casefold()
        if "next" in text:
            return urljoin(current_url, link["href"])

    for link in soup.find_all("a", href=True):
        if "/page/" in link["href"]:
            return urljoin(current_url, link["href"])

    return None


def parse_tradehq_directory_page(
    html: str,
    source_url: str,
    limit: int = 20,
    selectors: Optional[Dict[str, str]] = None,
) -> List[BusinessRecord]:
    """Parse the public TradeHQ directory page into business records.

    CSS selectors may need adjustment after inspecting the real HTML. This
    scraper is designed for public directory data only and does not log in,
    bypass protections, or collect private/restricted data.
    """

    selectors = {**SCRAPER_SELECTORS, **(selectors or {})}
    soup = BeautifulSoup(html, "html.parser")
    listing_nodes = soup.select(selectors["listing"])
    records: List[BusinessRecord] = []

    for node in listing_nodes[:limit]:
        business_name = _select_text(node, selectors["business_name"])
        if not business_name:
            continue

        records.append(
            BusinessRecord(
                business_name=business_name,
                region=_select_text(node, selectors["region"]),
                phone=_select_phone(node, selectors["phone"]),
                trade_category=_select_text(node, selectors["trade_category"]),
                description=_select_text(node, selectors["description"]),
                listing_url=_select_href(node, selectors["listing_url"], source_url),
                source_url=source_url,
            )
        )

    logger.info("Parsed %s TradeHQ listing(s) from %s", len(records), source_url)
    return records


def parse_detail_page(
    html: str,
    selector: str = DETAIL_DESCRIPTION_SELECTOR,
) -> Optional[str]:
    """Extract the full business description from a TradeHQ detail page."""

    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one(selector)
    if not element:
        return None
    return clean_display_text(element.get_text(separator=" ", strip=True))


def enrich_records_with_detail_descriptions(
    records: Iterable[BusinessRecord],
    fetcher: Callable[[str], str],
) -> tuple[list[BusinessRecord], list[FailedURL], dict]:
    """Replace card excerpts with full detail-page descriptions when available."""

    enriched_records: list[BusinessRecord] = []
    failed_urls: list[FailedURL] = []
    metrics = {
        "detail_pages_requested": 0,
        "detail_pages_successful": 0,
        "detail_pages_failed": 0,
        "descriptions_from_detail_page": 0,
        "descriptions_fallback_to_listing_excerpt": 0,
    }

    for record in records:
        if not record.listing_url:
            metrics["detail_pages_failed"] += 1
            metrics["descriptions_fallback_to_listing_excerpt"] += 1
            failed_urls.append(
                FailedURL(
                    url=record.source_url,
                    error_type="MissingListingURL",
                    error_message=(
                        f"No listing URL was available for {record.business_name}; "
                        "the directory-page description was retained."
                    ),
                )
            )
            enriched_records.append(record)
            continue

        metrics["detail_pages_requested"] += 1
        try:
            detail_html = fetcher(record.listing_url)
            full_description = parse_detail_page(detail_html)
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            metrics["detail_pages_failed"] += 1
            metrics["descriptions_fallback_to_listing_excerpt"] += 1
            failed_urls.append(
                FailedURL(
                    url=record.listing_url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    status_code=getattr(response, "status_code", None),
                )
            )
            enriched_records.append(record)
            continue

        if not full_description:
            metrics["detail_pages_failed"] += 1
            metrics["descriptions_fallback_to_listing_excerpt"] += 1
            failed_urls.append(
                FailedURL(
                    url=record.listing_url,
                    error_type="DescriptionNotFound",
                    error_message=(
                        "The detail page loaded, but the full description "
                        "container was not found; the directory-page excerpt "
                        "was retained."
                    ),
                )
            )
            enriched_records.append(record)
            continue

        data = model_to_dict(record)
        data["description"] = full_description
        enriched_records.append(BusinessRecord(**data))
        metrics["detail_pages_successful"] += 1
        metrics["descriptions_from_detail_page"] += 1

    return enriched_records, failed_urls, metrics


async def enrich_records_with_detail_descriptions_async(
    records: Iterable[BusinessRecord],
    concurrency: int = 3,
    async_fetcher: Optional[Callable[[str], Awaitable[str]]] = None,
) -> tuple[list[BusinessRecord], list[FailedURL], dict]:
    """Fetch detail pages concurrently while preserving record order."""

    record_list = list(records)
    semaphore = asyncio.Semaphore(concurrency)

    async def enrich_one(
        record: BusinessRecord,
        fetcher: Callable[[str], Awaitable[str]],
    ) -> tuple[BusinessRecord, Optional[FailedURL], str]:
        if not record.listing_url:
            return (
                record,
                FailedURL(
                    url=record.source_url,
                    error_type="MissingListingURL",
                    error_message=(
                        f"No listing URL was available for {record.business_name}; "
                        "the directory-page description was retained."
                    ),
                ),
                "fallback",
            )

        try:
            async with semaphore:
                detail_html = await fetcher(record.listing_url)
            full_description = parse_detail_page(detail_html)
        except (httpx.HTTPError, requests.RequestException) as exc:
            response = getattr(exc, "response", None)
            return (
                record,
                FailedURL(
                    url=record.listing_url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    status_code=getattr(response, "status_code", None),
                ),
                "fallback",
            )

        if not full_description:
            return (
                record,
                FailedURL(
                    url=record.listing_url,
                    error_type="DescriptionNotFound",
                    error_message=(
                        "The detail page loaded, but the full description "
                        "container was not found; the directory-page excerpt "
                        "was retained."
                    ),
                ),
                "fallback",
            )

        data = model_to_dict(record)
        data["description"] = full_description
        return BusinessRecord(**data), None, "full"

    async def run_batch(
        fetcher: Callable[[str], Awaitable[str]],
    ) -> tuple[list[BusinessRecord], list[FailedURL], dict]:
        results = await asyncio.gather(
            *(enrich_one(record, fetcher) for record in record_list)
        )
        enriched_records = [result[0] for result in results]
        failed_urls = [result[1] for result in results if result[1] is not None]
        full_count = sum(1 for result in results if result[2] == "full")
        fallback_count = sum(
            1 for result in results if result[2] == "fallback"
        )
        requested_count = sum(
            1 for record in record_list if record.listing_url
        )
        metrics = {
            "detail_concurrency": concurrency,
            "detail_pages_requested": requested_count,
            "detail_pages_successful": full_count,
            "detail_pages_failed": fallback_count,
            "descriptions_from_detail_page": full_count,
            "descriptions_fallback_to_listing_excerpt": fallback_count,
        }
        return enriched_records, failed_urls, metrics

    if async_fetcher is not None:
        return await run_batch(async_fetcher)

    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        async def fetch_detail(url: str) -> str:
            logger.debug("Fetching detail page: %s", url)
            response = await client.get(url)
            response.raise_for_status()
            return response.text

        return await run_batch(fetch_detail)


def enrich_records_with_detail_descriptions_concurrent(
    records: Iterable[BusinessRecord],
    concurrency: int = 3,
    async_fetcher: Optional[Callable[[str], Awaitable[str]]] = None,
) -> tuple[list[BusinessRecord], list[FailedURL], dict]:
    """Run bounded async detail enrichment from the synchronous pipeline."""

    return asyncio.run(
        enrich_records_with_detail_descriptions_async(
            records,
            concurrency=concurrency,
            async_fetcher=async_fetcher,
        )
    )


def scrape_trade_category_pages(
    category_urls: Iterable[str],
    limit_per_category: int,
    fetcher: Callable[[str], str],
    max_pages_per_category: int = 1,
    detail_concurrency: int = 3,
    async_detail_fetcher: Optional[
        Callable[[str], Awaitable[str]]
    ] = None,
) -> tuple[list[BusinessRecord], list[FailedURL], dict]:
    """Scrape selected category pages with total-record and page limits."""

    pending_records: list[BusinessRecord] = []
    failed_urls: list[FailedURL] = []
    metrics = {
        "categories_requested": 0,
        "category_pages_scraped": 0,
    }

    for category_url in category_urls:
        metrics["categories_requested"] += 1
        category_records_collected = 0
        category_page_url: Optional[str] = category_url
        visited_page_urls: set[str] = set()
        pages_scraped = 0

        while category_page_url:
            if category_page_url in visited_page_urls:
                break
            if (
                max_pages_per_category > 0
                and pages_scraped >= max_pages_per_category
            ):
                break
            if category_records_collected >= limit_per_category:
                break

            visited_page_urls.add(category_page_url)
            try:
                category_html = fetcher(category_page_url)
            except requests.RequestException as exc:
                response = getattr(exc, "response", None)
                failed_urls.append(
                    FailedURL(
                        url=category_page_url,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        status_code=getattr(response, "status_code", None),
                    )
                )
                break

            pages_scraped += 1
            metrics["category_pages_scraped"] += 1
            remaining_records = limit_per_category - category_records_collected
            category_records = parse_tradehq_directory_page(
                category_html,
                source_url=category_page_url,
                limit=remaining_records,
            )
            pending_records.extend(category_records)
            category_records_collected += len(category_records)

            if category_records_collected >= limit_per_category:
                break
            category_page_url = extract_next_page_url(
                category_html,
                category_page_url,
            )

    enriched, detail_failures, detail_metrics = (
        enrich_records_with_detail_descriptions_concurrent(
            pending_records,
            concurrency=detail_concurrency,
            async_fetcher=async_detail_fetcher,
        )
    )
    failed_urls.extend(detail_failures)
    metrics.update(detail_metrics)
    return enriched, failed_urls, metrics


def parse_business_listings(
    html: str,
    source_url: str,
    selectors: Optional[Dict[str, str]] = None,
) -> List[BusinessRecord]:
    """Parse business listings using generic CSS selectors.

    Real public directory sources usually need source-specific selectors.
    Edit app/config.py or pass a custom selectors dictionary after choosing
    and inspecting a legal, public business directory page.
    """

    selectors = {**SCRAPER_SELECTORS, **(selectors or {})}
    soup = BeautifulSoup(html, "html.parser")
    listing_nodes = soup.select(selectors["listing"])
    records: List[BusinessRecord] = []

    for node in listing_nodes:
        business_name = _select_text(node, selectors["business_name"])
        if not business_name:
            continue

        phone_element = node.select_one(selectors["phone"])
        phone_href = phone_element.get("href") if phone_element else None
        phone = (
            str(unquote(phone_href[4:]))
            if phone_href and phone_href.lower().startswith("tel:")
            else _select_text(node, selectors["phone"])
        )

        records.append(
            BusinessRecord(
                business_name=business_name,
                trade_category=_select_text(node, selectors["trade_category"]),
                region=_select_text(node, selectors["region"]),
                phone=phone,
                listing_url=_select_href(node, selectors["listing_url"], source_url),
                source_url=source_url,
                description=_select_text(node, selectors["description"]),
            )
        )

    logger.info("Parsed %s listing(s) from %s", len(records), source_url)
    return records
