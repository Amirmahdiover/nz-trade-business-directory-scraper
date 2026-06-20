import csv
from io import StringIO

from tools.create_validation_report import (
    MASTER_FIELDS,
    SAMPLE_FIELDS,
    VALIDATION_REPORT,
    create_validation_report,
)


def _write_master_csv(path, categories, fieldnames=MASTER_FIELDS):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for index, category in enumerate(categories, start=1):
            row = {
                "business_name": f"Business {index}",
                "trade_category": category,
                "region": "Auckland",
                "phone": f"0800 000 {index:03d}",
                "description": f"Description {index}",
                "listing_url": f"https://example.test/listing-{index}",
                "source_url": "https://example.test/category",
            }
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def test_create_validation_report_selects_categories_and_preserves_row_numbers(
    tmp_path,
):
    master_path = tmp_path / "master.csv"
    sample_path = tmp_path / "validation_sample.csv"
    report_path = tmp_path / "validation_report.md"
    categories = [
        "Other",
        " electricians ",
        "ELECTRICIANS",
        "Electricians",
        "Plumbers",
        " plumbers ",
        "PLUMBERS",
        "Builders",
        " builders ",
        "BUILDERS",
        "Builders",
        "Builders",
    ]
    _write_master_csv(master_path, categories)

    result = create_validation_report(
        master_path,
        sample_path,
        report_path,
        output=StringIO(),
    )

    assert result == 0
    with sample_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 10
    assert list(rows[0].keys()) == SAMPLE_FIELDS
    assert [row["original_csv_row_number"] for row in rows] == [
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
    ]
    assert all(
        not row[field]
        for row in rows
        for field in SAMPLE_FIELDS
        if field.endswith("_status") or field == "notes"
    )
    assert report_path.read_text(encoding="utf-8") == VALIDATION_REPORT


def test_create_validation_report_warns_and_uses_available_records(tmp_path):
    master_path = tmp_path / "master.csv"
    sample_path = tmp_path / "validation_sample.csv"
    report_path = tmp_path / "validation_report.md"
    output = StringIO()
    _write_master_csv(master_path, ["Electricians", "Plumbers", "Builders"])

    result = create_validation_report(
        master_path,
        sample_path,
        report_path,
        output=output,
    )

    assert result == 0
    assert "Warning: Electricians requires 3 records" in output.getvalue()
    assert "Warning: Plumbers requires 3 records" in output.getvalue()
    assert "Warning: Builders requires 4 records" in output.getvalue()
    with sample_path.open(encoding="utf-8", newline="") as file:
        assert len(list(csv.DictReader(file))) == 3


def test_create_validation_report_reports_missing_master_csv(tmp_path):
    output = StringIO()
    result = create_validation_report(
        tmp_path / "missing.csv",
        tmp_path / "sample.csv",
        tmp_path / "report.md",
        output=output,
    )

    assert result == 1
    assert "Error: master CSV does not exist" in output.getvalue()


def test_create_validation_report_reports_missing_columns(tmp_path):
    master_path = tmp_path / "master.csv"
    output = StringIO()
    _write_master_csv(
        master_path,
        ["Electricians"],
        fieldnames=["business_name", "trade_category"],
    )

    result = create_validation_report(
        master_path,
        tmp_path / "sample.csv",
        tmp_path / "report.md",
        output=output,
    )

    assert result == 1
    assert "missing required columns" in output.getvalue()
    assert "region" in output.getvalue()
    assert "source_url" in output.getvalue()
