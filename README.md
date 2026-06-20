# NZ Trade Business Directory Data Extraction Pipeline

## Overview

This project is a Python data extraction pipeline for the public New Zealand TradeHQ business directory:

```text
https://tradehq.co.nz/directory/
```

It discovers trade categories, scrapes explicitly selected category pages with controlled pagination, visits business detail pages for fuller descriptions, cleans and deduplicates records, and delivers traceable CSV, Excel, and JSON outputs.

The project is a business directory scraperâ€”not an e-commerce scraper, AI/RAG application, or spam/lead-generation system. Sample outputs represent limited, controlled runs rather than a claim that the entire website was scraped.

## Problem This Project Solves

Public directory information is often spread across category pages, paginated listing cards, and individual business detail pages. A useful client deliverable requires more than copying visible card text:

- categories must be discovered and selected safely;
- pagination must be bounded and repeatable;
- fuller descriptions may require detail-page requests;
- phone numbers must remain text;
- duplicate listings must be removed;
- failures and source URLs must remain traceable;
- final files must be practical for spreadsheet review and downstream analysis.

This pipeline turns that public directory structure into a consistent, reviewable dataset while keeping request scope under explicit user control.

## Key Features

- Discovers trade categories from the main directory page
- Scrapes only explicitly selected trade categories
- Supports controlled category pagination with `--max-pages-per-category`
- Supports unlimited pagination for selected categories with `--max-pages-per-category 0`
- Limits total records per category with `--limit-per-category`
- Keeps category-page pagination sequential and predictable
- Visits each `listing_url` to collect fuller business descriptions
- Fetches detail pages concurrently with configurable `--detail-concurrency`
- Preserves original record order after concurrent requests
- Falls back to listing excerpts when detail-page requests fail
- Cleans description whitespace and punctuation
- Preserves phone values as text in CSV and Excel
- Removes duplicate records, preferring `listing_url`
- Records failed category and detail URLs
- Includes source URLs for traceability
- Generates a manual validation sample and report
- Includes automated tests for parsing, cleaning, pagination, concurrency, exports, and validation helpers

## Data Fields

The final business dataset uses exactly these fields:

| Field | Description |
|---|---|
| `business_name` | Publicly listed business name |
| `trade_category` | Trade or service category |
| `region` | Listed New Zealand region or location |
| `phone` | Public business phone, preserved as text |
| `description` | Cleaned detail-page description when available |
| `listing_url` | Individual TradeHQ business listing URL |
| `source_url` | Exact directory/category page where the record was found |

## Output Files

Normal scraping and category-scraping runs generate:

- `outputs/nz_trade_businesses_master.csv`
- `outputs/nz_trade_businesses_master.xlsx`
- `outputs/scraping_summary.json`
- `outputs/failed_urls.csv`

Category discovery generates:

- `outputs/trade_categories.csv`

Manual validation tooling generates:

- `outputs/validation_sample.csv`
- `outputs/validation_report.md`

The CSV and Excel Master sheet retain the final seven-field schema. Phone values are exported as text to preserve leading zeroes, plus signs, spaces, and punctuation and to prevent scientific notation.

## Excel Workbook Sheets

`outputs/nz_trade_businesses_master.xlsx` contains:

- `Master` â€” all final records using the seven-field schema
- `Summary` â€” scrape metrics plus records grouped by trade category and region
- `Failed URLs` â€” failed category/detail requests or a no-failures note
- `Categories` â€” discovered category names, URLs, and available listing counts
- `Data Quality Notes` â€” concise validation, phone-handling, description, and public-source notes

## Example Commands

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run tests:

```powershell
pytest
```

Discover categories:

```powershell
python main.py --mode discover-categories --url "https://tradehq.co.nz/directory/"
```

Scrape selected categories with a small controlled limit:

```powershell
python main.py --mode scrape-categories --url "https://tradehq.co.nz/directory/" --categories electricians,plumbers,builders --limit-per-category 5
```

Run the controlled pagination example:

```powershell
python main.py --mode scrape-categories --url "https://tradehq.co.nz/directory/" --categories electricians --limit-per-category 15 --max-pages-per-category 2
```

Use concurrent detail-page fetching:

```powershell
python main.py --mode scrape-categories --url "https://tradehq.co.nz/directory/" --categories electricians --limit-per-category 15 --max-pages-per-category 2 --detail-concurrency 5
```

Allow full pagination for one explicitly selected category:

```powershell
python main.py --mode scrape-categories --url "https://tradehq.co.nz/directory/" --categories electricians --max-pages-per-category 0
```

Create the manual validation sample and report:

```powershell
python tools/create_validation_report.py
```

## Pagination and Concurrency Options

### `--limit-per-category`

Controls the maximum total records collected from each selected category across all visited pages. For example, `--limit-per-category 15` stops after 15 records even if more pages exist.

### `--max-pages-per-category`

- `1` â€” scrape the first category page only
- `2` â€” scrape at most two pages
- `0` â€” continue until no next page exists, the record limit is reached, or a repeated page URL is detected

Unlimited pagination still applies only to explicitly selected categories. It does not trigger a full-site crawl.

### `--detail-concurrency`

Controls only concurrent business detail-page requests:

- `1` â€” sequential compatibility mode
- `3` â€” default, conservative concurrency
- `5` â€” up to five detail requests at once

Category pages and pagination remain sequential. Detail results are restored to their original listing order before export, and individual failures fall back to the listing-page excerpt.

## Validation and Data Quality

Manual validation was performed on 10 sampled records across three trade categories:

- Electricians
- Plumbers
- Builders

Results:

| Field | Validation result |
|---|---|
| `business_name` | 10/10 correct |
| `phone` | 10/10 correct |
| `trade_category` | 10/10 correct |
| `region` | 10/10 correct |
| `description` | 10/10 acceptable |
| `listing_url` | 10/10 correct |
| `source_url` | 10/10 correct |

Descriptions were considered acceptable when meaningful, cleaned, not visibly truncated, and reasonably matched the public detail-page content. An empty phone is not treated as a scraper defect when the source listing also has no phone.

### Controlled Pagination Test

A controlled Electricians test produced:

- category pages scraped: 2
- records scraped: 15
- final records: 15
- duplicates removed: 0

### Local Concurrency Comparison

A local comparison of detail-page fetching produced approximately:

- `--detail-concurrency 1`: 30.87 seconds
- `--detail-concurrency 5`: 14.88 seconds

These are local sample results, not guaranteed performance figures. Runtime depends on network conditions, machine performance, target-site response time, and the number of records requested.

The generated `scraping_summary.json` includes record totals, duplicate counts, failed URL counts, category-page metrics, detail-page success/fallback metrics, and the selected detail concurrency.

## Tech Stack

- Python
- Requests
- httpx and asyncio
- BeautifulSoup
- Pydantic
- openpyxl
- Tenacity
- pytest
- Standard-library CSV and JSON tools

## Project Structure

```text
nz-trade-business-directory-scraper/
|-- app/
|   |-- cleaner.py
|   |-- config.py
|   |-- exporter.py
|   |-- models.py
|   |-- scraper.py
|   |-- summary.py
|   `-- utils.py
|-- data/
|   `-- raw/
|-- outputs/
|-- tests/
|-- tools/
|   `-- create_validation_report.py
|-- main.py
|-- requirements.txt
|-- README.md
`-- sample_output_note.md
```

## Ethical and Public Data Note

This project extracts publicly available business directory information and includes source URLs for traceability. It does not bypass authentication, CAPTCHA challenges, access controls, or private-data restrictions.

Scraping should remain controlled and proportional to the actual project need. Before running larger jobs, review the target website's terms, robots guidance, request-rate expectations, and applicable laws. Full-category pagination should be used responsibly and only when required.

## What This Project Demonstrates

This project demonstrates practical, reusable data-extraction capabilities:

- inspecting and parsing real directory HTML;
- discovering and resolving category URLs;
- implementing safe pagination controls;
- combining sequential navigation with bounded async detail fetching;
- cleaning and validating structured business data;
- preserving phone and source information correctly;
- handling failed requests without losing the full run;
- deduplicating records across categories and pages;
- producing client-friendly CSV, multi-sheet Excel, JSON summary, failure, and validation deliverables;
- documenting limitations and validation results without overstating sample coverage.
