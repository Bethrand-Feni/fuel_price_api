import sqlite3
from pathlib import Path

import pytest


def test_migration_allows_legacy_defaults_but_rejects_incomplete_new_rows():
    connection = sqlite3.connect(":memory:")
    connection.executescript(Path("migrations/0001_initial.sql").read_text(encoding="utf-8"))
    prices = ", ".join(["20.0"] * 10)

    connection.execute(
        "INSERT INTO fuel_prices (summary_month, petrol_news, diesel_news, "
        "unleaded93_inland, unleaded93_coast, unleaded95_inland, unleaded95_coast, "
        "diesel500_inland, diesel500_coast, diesel50_inland, diesel50_coast, "
        "lrp93_inland, lrp93_coast) VALUES (?, ?, ?, "
        f"{prices})",
        ("2026-01-01", "Petrol", "Diesel"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO fuel_prices (summary_month, petrol_news, diesel_news, "
            "unleaded93_inland, unleaded93_coast, unleaded95_inland, unleaded95_coast, "
            "diesel500_inland, diesel500_coast, diesel50_inland, diesel50_coast, "
            "lrp93_inland, lrp93_coast, source_name) VALUES (?, ?, ?, "
            f"{prices}, ?)",
            ("2026-02-01", "Petrol", "Diesel", "new-writer"),
        )
