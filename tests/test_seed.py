import json
import sqlite3
from pathlib import Path

import pytest

from scripts.export_supabase import (
    SeedExportError,
    build_seed_json,
    generate_sql,
    main,
    validate_export_rows,
)


def export_row(month: str = "2026-05-01", row_id: int = 1):
    return {
        "id": row_id,
        "summary_month": month,
        "petrol_news": "Prices rose by 1%.",
        "diesel_news": "Diesel is stable.",
        "unleaded93_inland": 23.25,
        "unleaded93_coast": 22.25,
        "unleaded95_inland": 24.25,
        "unleaded95_coast": 23.25,
        "diesel500_inland": 21.50,
        "diesel500_coast": 20.50,
        "diesel50_inland": 21.75,
        "diesel50_coast": 20.75,
        "lrp93_inland": 23.00,
        "lrp93_coast": 22.00,
    }


def test_seed_validation_sorts_rows_and_adds_source_metadata():
    rows = validate_export_rows(
        [export_row("2026-02-01", 2), export_row("2026-01-01", 1)],
        source_name="legacy-supabase",
        source_url="https://example.invalid/export",
        ingested_at="2026-08-02T00:00:00+00:00",
    )

    assert [item["summary_month"] for item in rows] == ["2026-01-01", "2026-02-01"]
    assert rows[0]["source_name"] == "legacy-supabase"
    assert rows[0]["source_url"] == "https://example.invalid/export"
    assert rows[0]["source_updated_on"] == "2026-01-01"
    assert rows[0]["source_row_id"] == "1"
    assert len(rows[0]["source_hash"]) == 64


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.pop("diesel50_coast"),
        lambda row: row.update(diesel50_coast=0),
        lambda row: row.update(diesel50_coast=100.01),
        lambda row: row.update(summary_month="2026-02-02"),
    ],
)
def test_seed_validation_rejects_invalid_rows(mutate):
    invalid = export_row()
    mutate(invalid)

    with pytest.raises(SeedExportError):
        validate_export_rows([invalid])


def test_seed_validation_rejects_duplicate_months():
    with pytest.raises(SeedExportError, match="duplicate summary_month"):
        validate_export_rows([export_row("2026-01-01", 1), export_row("2026-01-01", 2)])


def test_sql_is_deterministic_escaped_and_contains_ingestion_metadata():
    first = export_row("2026-01-01", 1)
    second = export_row("2026-02-01", 2)
    first["petrol_news"] = "O'Reilly reported a rise"

    normalized = validate_export_rows([second, first])
    sql = generate_sql(normalized)

    assert sql == generate_sql(validate_export_rows([first, second]))
    assert "O''Reilly reported a rise" in sql
    assert "INSERT INTO ingestion_runs" in sql
    assert "ON CONFLICT(summary_month) DO UPDATE" in sql
    assert "SUPABASE_KEY" not in sql
    assert "source_updated_on" in sql
    assert "source_row_id" in sql
    assert "source_hash" in sql
    assert "BEGIN;" not in sql
    assert "COMMIT;" not in sql


def test_source_hash_ignores_file_and_ingestion_metadata_but_changes_with_row_data():
    first = validate_export_rows(
        [export_row()],
        source_name="legacy-supabase",
        source_url="/private/tmp/one.json",
        ingested_at="2026-08-02T00:00:00+00:00",
    )[0]
    second = validate_export_rows(
        [export_row()],
        source_name="legacy-supabase",
        source_url="/private/tmp/two.json",
        ingested_at="2027-08-02T00:00:00+00:00",
    )[0]
    changed = export_row()
    changed["petrol_news"] = "A different canonical row"
    changed_hash = validate_export_rows(
        [changed],
        source_name="legacy-supabase",
        source_url="/private/tmp/one.json",
    )[0]["source_hash"]

    assert first["source_hash"] == second["source_hash"]
    assert first["source_hash"] != changed_hash


def test_json_seed_is_serializable_and_contains_both_tables():
    normalized = validate_export_rows([export_row()])

    payload = build_seed_json(normalized)
    encoded = json.dumps(payload, sort_keys=True)
    decoded = json.loads(encoded)

    assert len(decoded["fuel_prices"]) == 1
    assert decoded["ingestion_runs"][0]["status"] == "succeeded"


def test_cli_accepts_supabase_data_wrapper_and_writes_json(tmp_path):
    input_path = tmp_path / "export.json"
    output_path = tmp_path / "seed.json"
    input_path.write_text(json.dumps({"data": [export_row()]}), encoding="utf-8")

    result = main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--format",
            "json",
        ]
    )

    assert result == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["fuel_prices"][0]["source_name"] == "legacy-supabase-export"


def test_generated_sql_executes_against_owned_migration():
    normalized = validate_export_rows([export_row()])
    connection = sqlite3.connect(":memory:")
    connection.executescript(Path("migrations/0001_initial.sql").read_text(encoding="utf-8"))
    connection.executescript(generate_sql(normalized))

    assert connection.execute("SELECT COUNT(*) FROM fuel_prices").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0] == 1
    metadata = connection.execute(
        "SELECT source_updated_on, source_row_id, source_hash FROM fuel_prices"
    ).fetchone()
    assert metadata[0] == "2026-05-01"
    assert metadata[1] == "1"
    assert len(metadata[2]) == 64


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
