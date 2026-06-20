# Sample Output Note

The files under `outputs/` are included for portfolio review. They demonstrate the dataset schema, cleaned public business-directory records, traceable source URLs, summary metrics, failed-URL reporting, professional Excel workbook structure, and manual validation workflow.

The sample output comes from limited, controlled TradeHQ runs using selected trade categories and explicit record/page limits. It should not be interpreted as a complete scrape of the TradeHQ website.

Generated outputs can be recreated with the commands documented in `README.md`, including:

- trade-category discovery;
- selected-category scraping;
- controlled pagination;
- bounded concurrent detail-page fetching;
- validation sample and report generation.

The final business fields are:

```text
business_name
trade_category
region
phone
description
listing_url
source_url
```

Phone values remain text in CSV and Excel. Descriptions use public detail-page content when available, with cleaned listing excerpts retained as fallbacks when needed.

Larger or full-category scraping should be performed responsibly, only when required, and with appropriate limits, request rates, and review of the target site's terms and public-access guidance.
