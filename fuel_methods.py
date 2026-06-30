import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL: str | None = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str | None = os.environ.get("SUPABASE_KEY")
CACHE_PATH = Path(__file__).with_name("latest_fuel_data.json")
CACHE_TTL_SECONDS = int(os.environ.get("FUEL_CACHE_TTL_SECONDS", "86400"))

FUEL_TYPES = ("unleaded93", "unleaded95", "diesel500", "diesel50", "lrp93")
LOCATIONS = ("inland", "coast")
PRICE_COLUMNS = tuple(f"{fuel_type}_{location}" for fuel_type in FUEL_TYPES for location in LOCATIONS)
PETROL_PRICE_COLUMNS = tuple(
    f"{fuel_type}_{location}"
    for fuel_type in ("unleaded93", "unleaded95", "lrp93")
    for location in LOCATIONS
)
DIESEL_PRICE_COLUMNS = tuple(
    f"{fuel_type}_{location}"
    for fuel_type in ("diesel500", "diesel50")
    for location in LOCATIONS
)
REQUIRED_ROW_FIELDS = ("summary_month", "petrol_news", "diesel_news", *PRICE_COLUMNS)

supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


class FuelDataUnavailableError(RuntimeError):
    """Raised when neither Supabase nor the local cache can provide fuel data."""


def _is_valid_fuel_row(row: Any) -> bool:
    if not isinstance(row, dict):
        return False

    missing_fields = [field for field in REQUIRED_ROW_FIELDS if field not in row]
    if missing_fields:
        logger.warning("Fuel cache row is missing required fields: %s", ", ".join(missing_fields))
        return False

    return bool(row.get("summary_month"))


def _read_cache() -> dict[str, Any] | None:
    if not CACHE_PATH.exists():
        return None

    try:
        with CACHE_PATH.open("r", encoding="utf-8") as cache_file:
            row = json.load(cache_file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read fuel cache %s: %s", CACHE_PATH, exc)
        return None

    return row if _is_valid_fuel_row(row) else None


def _is_cache_fresh(row: dict[str, Any]) -> bool:
    cached_at = row.get("cached_at")
    if not cached_at:
        return False

    try:
        cached_at_datetime = datetime.fromisoformat(cached_at)
    except ValueError:
        return False

    if cached_at_datetime.tzinfo is None:
        cached_at_datetime = cached_at_datetime.replace(tzinfo=timezone.utc)

    cache_age = datetime.now(timezone.utc) - cached_at_datetime
    return cache_age.total_seconds() < CACHE_TTL_SECONDS


def _write_cache(row: dict[str, Any]) -> None:
    cache_payload = {
        **row,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    with NamedTemporaryFile("w", encoding="utf-8", dir=CACHE_PATH.parent, delete=False) as temp_file:
        json.dump(cache_payload, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
        temp_path = Path(temp_file.name)

    temp_path.replace(CACHE_PATH)
    logger.info("Fuel cache refreshed at %s", CACHE_PATH)


def _fetch_latest_fuel_row_from_supabase() -> dict[str, Any] | None:
    if not supabase:
        raise FuelDataUnavailableError("Supabase client is not configured")

    response = (
        supabase.table("fuel_prices")
        .select("*")
        .order("summary_month", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    row = response.data[0]
    return row if _is_valid_fuel_row(row) else None


def _fetch_fuel_history_from_supabase(limit: int = 12) -> list[dict[str, Any]]:
    if not supabase:
        raise FuelDataUnavailableError("Supabase client is not configured")

    response = (
        supabase.table("fuel_prices")
        .select("*")
        .order("summary_month", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data or []


def get_latest_fuel_row() -> dict[str, Any]:
    cached_row = _read_cache()
    if cached_row and _is_cache_fresh(cached_row):
        return cached_row

    try:
        supabase_row = _fetch_latest_fuel_row_from_supabase()
    except Exception as exc:
        if cached_row:
            logger.warning("Serving stale fuel cache because Supabase fetch failed: %s", exc)
            return cached_row
        raise FuelDataUnavailableError("Fuel data is unavailable") from exc

    if not supabase_row:
        raise FuelDataUnavailableError("No fuel data found in Supabase")

    _write_cache(supabase_row)
    return supabase_row


def get_latest_fuel_price(fuel_type: str, location: str):
    normalized_fuel_type = fuel_type.lower()
    normalized_location = location.lower()

    if normalized_fuel_type not in FUEL_TYPES or normalized_location not in LOCATIONS:
        return None

    row = get_latest_fuel_row()
    column_name = f"{normalized_fuel_type}_{normalized_location}"

    if row.get(column_name) is None:
        return None

    return {
        "id": row.get("id", 0),
        "fuel_type": normalized_fuel_type,
        "location": normalized_location,
        "price": row[column_name],
        "price_date": row["summary_month"],
    }


def get_all_latest_fuel_prices():
    row = get_latest_fuel_row()
    results = []

    for column in PRICE_COLUMNS:
        if row.get(column) is None:
            continue

        fuel_type, location = column.split("_")
        results.append(
            {
                "id": row.get("id", 0),
                "fuel_type": fuel_type,
                "location": location,
                "price": row[column],
                "price_date": row["summary_month"],
            }
        )

    return results


def get_latest_news(fuel_type: str | None = None):
    row = get_latest_fuel_row()

    if fuel_type:
        normalized_fuel_type = fuel_type.lower()
        key = f"{normalized_fuel_type}_news"
        if key not in ("petrol_news", "diesel_news"):
            return None

        return {
            "month": row["summary_month"],
            "fuel_type": normalized_fuel_type,
            "summary": row[key],
        }

    return {
        "month": row["summary_month"],
        "petrol": row["petrol_news"],
        "diesel": row["diesel_news"],
    }


def get_fuel_history(months: int = 12):
    try:
        rows = _fetch_fuel_history_from_supabase(months)
    except Exception as exc:
        raise FuelDataUnavailableError("Fuel history is unavailable") from exc

    valid_rows = [row for row in rows if _is_valid_fuel_row(row)]
    if not valid_rows:
        return []

    history = []
    for row in reversed(valid_rows):
        history.append(
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
        )

    return history
