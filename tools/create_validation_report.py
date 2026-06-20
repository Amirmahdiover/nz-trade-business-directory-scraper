"""Create a small category-based sample for manual CSV validation."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MASTER_CSV = PROJECT_ROOT / "outputs" / "nz_trade_businesses_master.csv"
DEFAULT_SAMPLE_CSV = PROJECT_ROOT / "outputs" / "validation_sample.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "validation_report.md"

MASTER_FIELDS = [
    "business_name",
    "trade_category",
    "region",
    "phone",
    "description",
    "listing_url",
    "source_url",
]
STATUS_FIELDS = [
    "business_name_status",
    "phone_status",
    "trade_category_status",
    "region_status",
    "description_status",
    "listing_url_status",
    "source_url_status",
]
SAMPLE_FIELDS = [
    "original_csv_row_number",
    *MASTER_FIELDS,
    *STATUS_FIELDS,
    "notes",
]
CATEGORY_TARGETS = [
    ("Electricians", 3),
    ("Plumbers", 3),
    ("Builders", 4),
]

VALIDATION_REPORT = """# Category Scraping Validation Report

Checked 10 records across 3 trade categories:

* Electricians: 3 records
* Plumbers: 3 records
* Builders: 4 records

## Field Accuracy Summary

business_name: __/10 correct
phone: __/10 correct
trade_category: __/10 correct
region: __/10 correct
description: __/10 acceptable
listing_url: __/10 correct
source_url: __/10 correct

## Validation Notes

Phone rule:
If phone is empty in the output and the source page also has no phone, this is not a scraper bug.

Write as:
Phone empty, but source page also has no phone. Not a scraper bug.

Description rule:
Description is acceptable if it is meaningful, cleaned, not visibly truncated, and matches the business detail page content well enough for a business directory dataset.

## Problems

1. Row __
   Field:
   Current value:
   Correct value:
   Problem:

2. Row __
   Field:
   Current value:
   Correct value:
   Problem:

## Final Decision

Validation result: PASS / NEEDS FIXES

Notes:
"""


def normalize_category(value: str | None) -> str:
    """Return a case-insensitive, whitespace-tolerant category key."""

    return " ".join((value or "").split()).casefold()


def read_master_rows(
    master_csv: Path,
    output: TextIO,
) -> list[dict[str, str]] | None:
    """Read the master CSV and preserve spreadsheet-style row numbers."""

    if not master_csv.exists():
        print(f"Error: master CSV does not exist: {master_csv}", file=output)
        return None

    with master_csv.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        missing_columns = [
            field_name
            for field_name in MASTER_FIELDS
            if field_name not in fieldnames
        ]
        if missing_columns:
            print(
                "Error: master CSV is missing required columns: "
                + ", ".join(missing_columns),
                file=output,
            )
            return None

        rows = []
        for csv_row_number, row in enumerate(reader, start=2):
            rows.append(
                {
                    **{field_name: row.get(field_name, "") for field_name in MASTER_FIELDS},
                    "original_csv_row_number": str(csv_row_number),
                }
            )
        return rows


def select_validation_rows(
    rows: list[dict[str, str]],
    output: TextIO,
) -> list[dict[str, str]]:
    """Select the first requested records for each validation category."""

    selected: list[dict[str, str]] = []
    for category_name, required_count in CATEGORY_TARGETS:
        category_key = normalize_category(category_name)
        matches = [
            row
            for row in rows
            if normalize_category(row.get("trade_category")) == category_key
        ][:required_count]
        if len(matches) < required_count:
            print(
                f"Warning: {category_name} requires {required_count} records, "
                f"but only {len(matches)} were available.",
                file=output,
            )
        selected.extend(matches)
    return selected


def write_validation_sample(
    rows: list[dict[str, str]],
    sample_csv: Path,
) -> None:
    """Write selected rows with empty manual-validation fields."""

    sample_csv.parent.mkdir(parents=True, exist_ok=True)
    with sample_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SAMPLE_FIELDS,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    **{field_name: "" for field_name in STATUS_FIELDS},
                    "notes": "",
                }
            )


def write_validation_report(report_path: Path) -> None:
    """Write the requested manual validation report template."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(VALIDATION_REPORT, encoding="utf-8")


def create_validation_report(
    master_csv: Path = DEFAULT_MASTER_CSV,
    sample_csv: Path = DEFAULT_SAMPLE_CSV,
    report_path: Path = DEFAULT_REPORT_PATH,
    output: TextIO = sys.stdout,
) -> int:
    """Create the validation sample and report, returning a process exit code."""

    rows = read_master_rows(master_csv, output)
    if rows is None:
        return 1

    selected_rows = select_validation_rows(rows, output)
    write_validation_sample(selected_rows, sample_csv)
    write_validation_report(report_path)

    print(
        f"Created validation sample with {len(selected_rows)} record(s): "
        f"{sample_csv}",
        file=output,
    )
    print(f"Created validation report: {report_path}", file=output)
    return 0


def main() -> int:
    return create_validation_report()


if __name__ == "__main__":
    raise SystemExit(main())
