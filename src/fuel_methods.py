from collections.abc import Mapping, Sequence
from datetime import date
from math import isfinite
from typing import Any, Protocol

FUEL_TYPES = ("unleaded93", "unleaded95", "diesel500", "diesel50", "lrp93")
LOCATIONS = ("inland", "coast")
PRICE_COLUMNS = tuple(
    f"{fuel_type}_{location}" for fuel_type in FUEL_TYPES for location in LOCATIONS
)
PETROL_PRICE_COLUMNS = tuple(
    f"{fuel_type}_{location}"
    for fuel_type in ("unleaded93", "unleaded95", "lrp93")
    for location in LOCATIONS
)
DIESEL_PRICE_COLUMNS = tuple(
    f"{fuel_type}_{location}" for fuel_type in ("diesel500", "diesel50") for location in LOCATIONS
)
FUEL_ROW_FIELDS = (
    "id",
    "summary_month",
    "petrol_news",
    "diesel_news",
    *PRICE_COLUMNS,
    "source_name",
    "source_url",
    "source_updated_on",
    "source_row_id",
    "source_hash",
    "ingested_at",
)
REQUIRED_FUEL_FIELDS = ("summary_month", "petrol_news", "diesel_news", *PRICE_COLUMNS)
MIN_FUEL_PRICE = 0.01
MAX_FUEL_PRICE = 100.0
HISTORY_MONTH_LIMIT = 12


class FuelDataUnavailableError(RuntimeError):
    """Raised when D1 cannot provide a usable response."""


class D1Statement(Protocol):
    def bind(self, *values: object) -> "D1Statement": ...

    async def all(self) -> Any: ...


class D1Database(Protocol):
    def prepare(self, sql: str) -> D1Statement: ...


class FuelRepository(Protocol):
    async def latest_row(self) -> dict[str, Any] | None: ...

    async def history_rows(self, limit: int) -> list[dict[str, Any]]: ...


def is_valid_summary_month(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False

    return parsed.day == 1 and len(value) == 10


def is_valid_fuel_price(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False

    return isfinite(value) and MIN_FUEL_PRICE <= value <= MAX_FUEL_PRICE


def is_valid_fuel_row(row: Any) -> bool:
    if not isinstance(row, Mapping):
        return False

    if not is_valid_summary_month(row.get("summary_month")):
        return False

    if any(
        not isinstance(row.get(field), str) or not row[field].strip()
        for field in ("petrol_news", "diesel_news")
    ):
        return False

    return all(is_valid_fuel_price(row.get(column)) for column in PRICE_COLUMNS)


def _to_python(value: Any) -> Any:
    converter = getattr(value, "to_py", None)
    if callable(converter):
        converted = converter()
        if converted is not value:
            return converted
    return value


def _proxy_value(value: Any, key: str, default: Any = None) -> Any:
    value = _to_python(value)
    if isinstance(value, Mapping):
        return value.get(key, default)

    try:
        return getattr(value, key)
    except AttributeError:
        try:
            return value[key]
        except (KeyError, IndexError, TypeError):
            return default


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    row = _to_python(row)
    if isinstance(row, Mapping):
        return {key: _to_python(value) for key, value in row.items()}

    keys = getattr(row, "keys", None)
    if callable(keys):
        try:
            return {key: _to_python(row[key]) for key in keys()}
        except (KeyError, IndexError, TypeError):
            return None

    values: dict[str, Any] = {}
    for field in FUEL_ROW_FIELDS:
        try:
            values[field] = _to_python(row[field])
        except (KeyError, IndexError, TypeError):
            continue
    return values or None


def _extract_rows(result: Any) -> list[dict[str, Any]]:
    result = _to_python(result)
    if isinstance(result, Sequence) and not isinstance(result, (str, bytes, bytearray)):
        raw_rows = result
    elif isinstance(result, Mapping):
        raw_rows = result.get("results", [])
    else:
        raw_rows = _proxy_value(result, "results", [])
    raw_rows = _to_python(raw_rows)

    if raw_rows is None:
        return []

    if isinstance(raw_rows, Mapping):
        raw_rows = [raw_rows]

    return [normalized for row in raw_rows if (normalized := _row_to_dict(row)) is not None]


def _ensure_query_succeeded(result: Any) -> None:
    result = _to_python(result)
    success = result.get("success", True) if isinstance(result, Mapping) else _proxy_value(result, "success", True)
    success = _to_python(success)
    if success is False:
        raise RuntimeError("D1 query failed")


class D1FuelRepository:
    """Small async repository around one request's D1 binding."""

    def __init__(self, database: D1Database):
        self._database = database

    async def _query(
        self,
        sql: str,
        params: tuple[object, ...] = (),
        *,
        unavailable_message: str,
    ) -> list[dict[str, Any]]:
        try:
            statement = self._database.prepare(sql)
            if params:
                statement = statement.bind(*params)
            result = await statement.all()
            _ensure_query_succeeded(result)
            rows = _extract_rows(result)
        except Exception as exc:
            raise FuelDataUnavailableError(unavailable_message) from exc

        return rows

    async def latest_row(self) -> dict[str, Any] | None:
        rows = await self._query(
            f"SELECT {', '.join(FUEL_ROW_FIELDS)} "
            "FROM fuel_prices ORDER BY summary_month DESC, id DESC LIMIT 1",
            unavailable_message="Fuel data is unavailable",
        )
        return next((row for row in rows if is_valid_fuel_row(row)), None)

    async def history_rows(self, limit: int) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), HISTORY_MONTH_LIMIT))
        return await self._query(
            f"SELECT {', '.join(FUEL_ROW_FIELDS)} "
            "FROM fuel_prices ORDER BY summary_month DESC, id DESC LIMIT ?",
            (safe_limit,),
            unavailable_message="Fuel history is unavailable",
        )


async def get_latest_fuel_row(repository: FuelRepository) -> dict[str, Any] | None:
    return await repository.latest_row()


async def get_latest_fuel_price(
    repository: FuelRepository,
    fuel_type: str,
    location: str,
) -> dict[str, Any] | None:
    normalized_fuel_type = fuel_type.lower()
    normalized_location = location.lower()

    if normalized_fuel_type not in FUEL_TYPES or normalized_location not in LOCATIONS:
        return None

    row = await get_latest_fuel_row(repository)
    if row is None:
        return None

    column_name = f"{normalized_fuel_type}_{normalized_location}"
    return {
        "id": row["id"],
        "fuel_type": normalized_fuel_type,
        "location": normalized_location,
        "price": row[column_name],
        "price_date": row["summary_month"],
    }


async def get_all_latest_fuel_prices(repository: FuelRepository) -> list[dict[str, Any]]:
    row = await get_latest_fuel_row(repository)
    if row is None:
        return []

    return [
        {
            "id": row["id"],
            "fuel_type": fuel_type,
            "location": location,
            "price": row[f"{fuel_type}_{location}"],
            "price_date": row["summary_month"],
        }
        for fuel_type in FUEL_TYPES
        for location in LOCATIONS
    ]


async def get_latest_news(
    repository: FuelRepository,
    fuel_type: str | None = None,
) -> dict[str, Any] | None:
    row = await get_latest_fuel_row(repository)
    if row is None:
        return None

    if fuel_type:
        normalized_fuel_type = fuel_type.lower()
        if normalized_fuel_type not in ("petrol", "diesel"):
            return None

        return {
            "month": row["summary_month"],
            "fuel_type": normalized_fuel_type,
            "summary": row[f"{normalized_fuel_type}_news"],
        }

    return {
        "month": row["summary_month"],
        "petrol": row["petrol_news"],
        "diesel": row["diesel_news"],
    }


async def get_fuel_history(
    repository: FuelRepository,
    months: int = HISTORY_MONTH_LIMIT,
) -> list[dict[str, Any]]:
    safe_months = max(1, min(int(months), HISTORY_MONTH_LIMIT))
    rows = await repository.history_rows(safe_months)
    valid_rows = sorted(
        (row for row in rows if is_valid_fuel_row(row)),
        key=lambda row: row["summary_month"],
    )
    valid_rows = valid_rows[-safe_months:]

    return [
        {
            "month": row["summary_month"],
            "petrol": {
                column: row[column]
                for column in PETROL_PRICE_COLUMNS
                if row.get(column) is not None
            },
            "diesel": {
                column: row[column]
                for column in DIESEL_PRICE_COLUMNS
                if row.get(column) is not None
            },
            "news": {
                "petrol": row["petrol_news"],
                "diesel": row["diesel_news"],
            },
        }
        for row in valid_rows
    ]
