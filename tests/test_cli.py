import sys

import pytest

import main as main_module


def test_detail_concurrency_rejects_values_below_one(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--mode",
            "scrape-categories",
            "--url",
            "https://tradehq.co.nz/directory/",
            "--categories",
            "electricians",
            "--detail-concurrency",
            "0",
        ],
    )

    with pytest.raises(
        SystemExit,
        match="--detail-concurrency must be at least 1",
    ):
        main_module.main()
