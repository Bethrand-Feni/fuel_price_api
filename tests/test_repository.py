from typing import Any

import pytest

from fuel_methods import (
    D1FuelRepository,
    FuelDataUnavailableError,
    get_fuel_history,
    get_latest_fuel_price,
    is_valid_fuel_row,
)


def row(month: str, row_id: int) -> dict[str, Any]:
    prices = {
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
    return {
        "id": row_id,
        "summary_month": month,
        "petrol_news": f"Petrol {row_id}",
        "diesel_news": f"Diesel {row_id}",
        "source_name": "fake",
        "source_url": None,
        "source_updated_on": month,
        "source_row_id": str(row_id),
        "source_hash": "a" * 64,
        "ingested_at": "2026-08-02T00:00:00+00:00",
        **prices,
    }


class FakeStatement:
    def __init__(self, database, sql: str):
        self.database = database
        self.sql = sql
        self.params: tuple[object, ...] = ()

    def bind(self, *params: object):
        self.params = params
        return self

    async def all(self):
        return {"results": self.database.results(self.sql, self.params)}


class FakeD1:
    def __init__(self, rows):
        self.rows = list(rows)
        self.statements: list[FakeStatement] = []

    def prepare(self, sql: str):
        statement = FakeStatement(self, sql)
        self.statements.append(statement)
        return statement

    def results(self, sql: str, params: tuple[object, ...]):
        rows = sorted(self.rows, key=lambda item: item["summary_month"], reverse=True)
        if "LIMIT 1" in sql:
            return rows[:1]
        return rows[: int(params[0])]


class FailingD1:
    def prepare(self, sql: str):
        raise RuntimeError("D1 is offline")


class UnsuccessfulD1:
    def prepare(self, sql: str):
        return UnsuccessfulStatement()


class UnsuccessfulStatement:
    async def all(self):
        return {"success": False, "results": []}


class ToPyRowProxy:
    def __init__(self, value):
        self.value = value

    def to_py(self):
        return self.value


class ToPyD1ResultProxy:
    def __init__(self, rows):
        self.rows = rows

    def to_py(self):
        return {
            "success": True,
            "results": [ToPyRowProxy(row) for row in self.rows],
        }


class ToPyStatement:
    def __init__(self, rows):
        self.rows = rows

    async def all(self):
        return ToPyD1ResultProxy(self.rows)


class ToPyD1:
    def __init__(self, rows):
        self.rows = rows

    def prepare(self, sql: str):
        return ToPyStatement(self.rows)


class MappingRowProxy:
    def __init__(self, value):
        self.value = value

    def keys(self):
        return self.value.keys()

    def __getitem__(self, key):
        return self.value[key]


class AttributeD1ResultProxy:
    success = True

    def __init__(self, rows):
        self.results = [MappingRowProxy(row) for row in rows]


class AttributeStatement:
    def __init__(self, rows):
        self.rows = rows

    async def all(self):
        return AttributeD1ResultProxy(self.rows)


class AttributeD1:
    def __init__(self, rows):
        self.rows = rows

    def prepare(self, sql: str):
        return AttributeStatement(self.rows)


@pytest.mark.asyncio
async def test_d1_repository_uses_async_prepared_queries_and_bound_limit():
    database = FakeD1([row("2026-01-01", 1), row("2026-02-01", 2)])
    repository = D1FuelRepository(database)

    latest = await repository.latest_row()
    history = await repository.history_rows(12)

    assert latest["summary_month"] == "2026-02-01"
    assert [item["summary_month"] for item in history] == ["2026-02-01", "2026-01-01"]
    assert database.statements[1].params == (12,)
    assert "SELECT id, summary_month" in database.statements[0].sql


@pytest.mark.asyncio
async def test_d1_repository_wraps_database_errors_without_leaking_details():
    repository = D1FuelRepository(FailingD1())

    with pytest.raises(FuelDataUnavailableError, match="Fuel data is unavailable"):
        await repository.latest_row()


@pytest.mark.asyncio
async def test_d1_repository_wraps_unsuccessful_d1_results():
    repository = D1FuelRepository(UnsuccessfulD1())

    with pytest.raises(FuelDataUnavailableError, match="Fuel data is unavailable"):
        await repository.latest_row()


@pytest.mark.asyncio
async def test_d1_repository_normalizes_proxy_result_and_row_objects():
    repository = D1FuelRepository(ToPyD1([row("2026-02-01", 2)]))

    latest = await repository.latest_row()

    assert latest["summary_month"] == "2026-02-01"
    assert latest["source_row_id"] == "2"


@pytest.mark.asyncio
async def test_d1_repository_normalizes_attribute_result_and_mapping_row_proxies():
    repository = D1FuelRepository(AttributeD1([row("2026-03-01", 3)]))

    latest = await repository.latest_row()

    assert latest["summary_month"] == "2026-03-01"
    assert latest["source_row_id"] == "3"


@pytest.mark.asyncio
async def test_public_transformers_preserve_latest_price_and_history_order():
    database = FakeD1([row("2026-02-01", 2), row("2026-01-01", 1)])
    repository = D1FuelRepository(database)

    price = await get_latest_fuel_price(repository, "unleaded93", "inland")
    history = await get_fuel_history(repository)

    assert price["price"] == 23.25
    assert [item["month"] for item in history] == ["2026-01-01", "2026-02-01"]


def test_fuel_row_validation_rejects_missing_or_out_of_range_prices():
    valid = row("2026-01-01", 1)
    missing = {**valid}
    del missing["diesel50_coast"]
    too_high = {**valid, "diesel50_coast": 100.01}

    assert is_valid_fuel_row(valid)
    assert not is_valid_fuel_row(missing)
    assert not is_valid_fuel_row(too_high)
