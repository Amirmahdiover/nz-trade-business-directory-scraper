"""Project configuration values."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = BASE_DIR / "outputs"

EXCEL_OUTPUT_PATH = OUTPUTS_DIR / "nz_trade_businesses_master.xlsx"
CSV_OUTPUT_PATH = OUTPUTS_DIR / "nz_trade_businesses_master.csv"
SUMMARY_OUTPUT_PATH = OUTPUTS_DIR / "scraping_summary.json"
FAILED_URLS_OUTPUT_PATH = OUTPUTS_DIR / "failed_urls.csv"
TRADE_CATEGORIES_OUTPUT_PATH = OUTPUTS_DIR / "trade_categories.csv"
TRADEHQ_RAW_HTML_PATH = RAW_DATA_DIR / "tradehq_directory.html"

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_LEVEL = "INFO"

TRADEHQ_TARGET_URL = "https://tradehq.co.nz/directory/"
DEFAULT_SCRAPE_LIMIT = 20
DEFAULT_CATEGORY_LIMIT = 10
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = (
    "Mozilla/5.0 (compatible; NZTradeBusinessDirectoryScraper/1.0; "
    "+https://github.com/portfolio-project)"
)

# TradeHQ CSS selectors for the first real scraping version.
# These may need adjustment if TradeHQ changes its Elementor/JetEngine HTML.
# The scraper is designed for public directory data only.
LISTING_CARD_SELECTOR = "#listings .jet-listing-grid__item[data-post-id]"
BUSINESS_NAME_SELECTOR = "h3.elementor-heading-title a, h3 a"
REGION_SELECTOR = "a[href*='/location/'] .elementor-icon-list-text, a[href*='/location/']"
PHONE_SELECTOR = "a[href^='tel:'] .elementor-icon-list-text, a[href^='tel:']"
TRADE_CATEGORY_SELECTOR = "a[href*='/business-category/'].jet-listing-dynamic-terms__link"
DESCRIPTION_SELECTOR = ".elementor-widget-theme-post-excerpt p"
DETAIL_DESCRIPTION_SELECTOR = (
    ".elementor-widget-theme-post-content .elementor-widget-container"
)
LISTING_URL_SELECTOR = "h3.elementor-heading-title a[href*='/directory/'], a.elementor-button[href*='/directory/']"

SCRAPER_SELECTORS = {
    "listing": LISTING_CARD_SELECTOR,
    "business_name": BUSINESS_NAME_SELECTOR,
    "trade_category": TRADE_CATEGORY_SELECTOR,
    "region": REGION_SELECTOR,
    "phone": PHONE_SELECTOR,
    "description": DESCRIPTION_SELECTOR,
    "listing_url": LISTING_URL_SELECTOR,
}

# TODO: Revalidate TRADE_CATEGORY_SELECTOR and REGION_SELECTOR against saved
# TradeHQ HTML whenever merged values such as "ElectriciansCanterbury" appear.
# They currently target separate anchors and should not be broadened to a
# shared parent without manually checking the live listing-card markup.
